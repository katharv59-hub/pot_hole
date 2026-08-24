# ROADSentinel — Backend & AI Pipeline Specification

**Author:** Atharv (Software + AI/ML Systems)
**Status:** Draft v0.4 — Final implementation-readiness clarifications
**Companion doc:** `frontend-spec.md` (dashboard/UI)

**Changelog v0.1 → v0.2:** Responds to the first spec review. The overall architecture is unchanged — `RoadEvent` as the core abstraction, hardware/vehicle-agnostic design, PostgreSQL+PostGIS, and the driver/admin split all stay as-is. Previously hand-wavy areas (API contract, device auth, RBAC, real-time transport, telemetry, idempotency, timestamps/location, fusion, and segments) were specified concretely.

**Changelog v0.2 → v0.3:** Responds to the second review: report-specific media flow, explicit separation of device-credential auth from driver-JWT auth for event ingestion, a documented WebSocket scaling boundary, reinforced geohash ≠ road segment framing, and baseline media privacy/retention rules.

**Changelog v0.3 → v0.4:** Responds to the third and (per reviewer) final review before implementation planning: (1) device identity is now explicitly derived from the authenticated credential, never trusted from the request body, (2) PostgreSQL/PostGIS is stated as the sole authoritative v1 datastore with Firebase strictly a temporary migration bridge, (3) `Telemetry` gets a concrete v1 retention/sampling/storage-scaling note, (4) the `/events` vs `/telemetry` vs `MLPrediction` boundary is stated as an explicit rule, (5) camera/continuous-frame ingestion is explicitly called out as edge-processed, not raw-JSON-through-`/events`, and (6) `corroboration_count` is precisely defined as independent-device count, not submission/retry count. No architectural changes.

**v0.4 is the implementation baseline.** The next review will compare shipped code against this document, not another architecture pass. §0 below captures four binding constraints for that first implementation pass, called out separately from the rest of the spec so they're easy to check off during code review.

---

## 0. Binding Implementation Constraints for the First Build

These are non-negotiable for the initial implementation. Each one is already implied elsewhere in this spec, but is restated here explicitly so it can't be lost in the detail of individual sections, and so the next review has a short checklist to hold the code against.

1. **Geohash is never presented or persisted as a real `RoadSegment`.** `GeoIndexBucket` (§12) is a spatial-indexing/corroboration convenience only. `road_segment_id` on `RoadEvent` stays nullable in v1 and is only ever populated by the async road-network backfill described in §13 — it must never be set to, or derived directly from, a geohash value. If the implementation is tempted to "just use the geohash cell as the segment for now," that is exactly the shortcut this constraint rules out. See §13 for the full rationale and §10 of `frontend-spec.md` for how this must be framed in the UI.
2. **`/events`, `/telemetry`, and `MLPrediction` stay strictly separated, per §4.1.** `/events` only ever accepts hazard/detection candidates. `/telemetry` only ever accepts raw sensor data with no hazard claim. `MLPrediction` rows are never created by a direct device-facing endpoint — they are always written by the backend as part of processing a `RoadEvent`. No implementation shortcut should merge these paths (e.g. no "just also write an `MLPrediction` row from the `/telemetry` handler" and no "let `/events` accept a raw continuous stream").
3. **The first end-to-end pipeline must work against the existing ESP32 + IMU + GPS prototype, with no camera/ML/fusion dependency.** Concretely: `POST /events` in **raw mode** (device sends `sensor_data`, no `model_output`) must be a fully supported, complete path on its own — the backend applies a simple threshold/rule-based classification (consistent with the current prototype's acceleration-threshold approach) to produce `event_type`/`confidence`/`severity` without requiring any trained model, camera input, or fusion logic to exist. Camera ingestion (§9), multimodal fusion (§9), and trained ML models (§17) are additive layers on top of this path, not prerequisites for it. The first implementation milestone is considered done when an ESP32 device can provision, authenticate, and successfully post raw IMU+GPS events end-to-end into the database and back out through a read endpoint — with zero ML/camera code required to reach that milestone.
4. **Do not build deferred infrastructure unless an actual v1 requirement forces it.** Redis/Celery, Kafka, MQTT-scale broker infrastructure, a full MLOps/model registry, and similar items listed in §18 stay deferred. If, during implementation, one of these starts to look necessary, that's a signal to flag it for discussion rather than to add it quietly — not a green light to add it because it's convenient or "good practice." The bar is an actual blocking requirement, not anticipated future scale.

---

## 1. Guiding Principles (unchanged)

- **Hardware-agnostic**: nothing in the backend assumes a specific sensor board (ESP32 today, Jetson/edge-AI computer tomorrow).
- **Vehicle-agnostic**: same schema for two-wheelers, cars, buses, trucks, fleet vehicles.
- **Event-centric**: the core unit of data is a `RoadEvent`, not a raw sensor reading.
- **Confidence + severity first-class**: every detection carries a confidence score and severity estimate, not a binary flag.
- **Progressive rollout**: v1 backend must work with today's IMU/GPS-only prototype, but must not need a rewrite when camera/edge-AI is added.
- **v1 vs future is explicit everywhere** (new): every section below marks what must be built now vs what is deliberately deferred, so implementation isn't ambiguous.

---

## 2. High-Level Data Flow (unchanged)

```
Camera / IMU / GPS / Speed / (optional CAN-OBD)
              ↓
        Edge Device (ESP32 today → Edge-AI computer later)
              ↓
     Local Pre-processing / On-device Inference (optional)
              ↓
        Backend Ingestion API
              ↓
      Validation → Enrichment → Fusion
              ↓
           Database
              ↓
   ┌──────────┴──────────┐
   ↓                      ↓
User Dashboard      Admin/Authority Dashboard
   ↓                      ↓
Navigation/Alerts     Analytics/Reports
```

Two ingestion modes remain supported:
1. **Raw sensor event** — device sends acceleration spike + GPS → backend classifies.
2. **Pre-classified event** — device sends `event_type + confidence` already computed on-device → backend validates, deduplicates, fuses.

---

## 3. Backend Architecture (stack unchanged, scope note added)

### 3.1 Stack
- **Language/Framework:** Python + FastAPI
- **Primary DB:** PostgreSQL + PostGIS. **PostgreSQL/PostGIS is the sole authoritative datastore for all v1 data** — every entity in §12 lives there. Firebase (used by the current prototype) is strictly a **temporary migration/legacy bridge**: existing prototype data is migrated in, and any interim dual-write period (if the current prototype can't be cut over instantly) treats Firebase as read-path-only for legacy clients while Postgres is the single source of truth for writes. Firebase is not authoritative for any v1 entity going forward, and the migration bridge is expected to be decommissioned once cutover is complete — it is not a permanent second datastore.
- **Object storage:** S3-compatible bucket (or Firebase Storage initially) for images/video/clips
- **Real-time layer (v1 decision — see §7):** WebSocket, served directly from the FastAPI app
- **Auth:** JWT-based, separate flows for devices vs users vs admins (see §5)
- **Deferred to future work:** Redis/Celery queueing, full MLOps/model registry, large-scale MQTT infrastructure. v1 ingestion volume does not need these; revisit once event throughput requires decoupling.

---

## 4. RoadEvent API Contract (new — was previously underspecified)

This is the single most important contract in the system: it's what every device, past or future, must speak.

### 4.1 Design rules
- Every event has a **schema_version** so the contract can evolve without breaking old devices.
- Every field is explicitly **required** or **optional** — devices with fewer sensors simply omit optional fields, they never send placeholder/zero values.
- All timestamps are **ISO 8601 UTC** (e.g. `2026-08-22T14:03:11.500Z`).
- All angles are decimal degrees (WGS84); all distances/speeds are metric (meters, m/s) unless explicitly labeled.
- Confidence and severity are both **0.0–1.0 floats**, not enums, so they can be recomputed/rescaled later without a schema change. A separate human-readable `severity_label` (low/medium/high/critical) is derived server-side from the float, never sent by the device.
- **Device identity is never trusted from the request body (new — critical):** the backend does **not** treat a `device_id` field in the payload as authoritative. The authenticated `device_id` is derived server-side from the access token presented on the connection/request (issued via §5.1's device auth flow) — the payload's job is only to carry `vehicle_id` and detection data, not to assert who the sender is. If a payload includes a `device_id` field at all, it is either ignored or, if present, cross-checked against the authenticated identity and rejected (409) on mismatch — it is never used to determine the identity itself. See §5.4 for the full flow: **device credential → authenticated device → current assignment → accepted vehicle.**
- **`/events` vs. `/telemetry` vs. `MLPrediction` — explicit ingestion boundary (new):**
  - `POST /events` accepts only **event/detection candidates** — something has crossed the threshold of "this might be a road hazard worth recording," whether classified on-device (pre-classified mode) or left for the backend to classify (raw mode via inline `sensor_data`, intended for small evidence windows only, not continuous streams).
  - `POST /telemetry` (§12) accepts **raw/continuous sensor data** that is not itself a hazard claim — smooth-road baselines, negative samples, or continuous IMU/GPS streams collected for later ML dataset curation. This is never surfaced on the map or to drivers; it exists purely for the ML pipeline (§17).
  - `MLPrediction` rows are never submitted directly by a device — they are created by the backend (or by an edge device's classification result being recorded as part of a `POST /events` pre-classified payload). A device never writes to an `MLPrediction`-equivalent endpoint directly; predictions are always attached to a `RoadEvent` they were classifying.
  - **Rule of thumb for implementers:** if the payload is claiming "a hazard happened here," it goes through `/events`. If it's just sensor data with no hazard claim attached, it goes through `/telemetry`. Nothing should ever be sent to both endpoints for the same physical measurement.

### 4.2 `POST /events` — Request

```json
{
  "schema_version": "1.0",
  "device_event_id": "esp32-4F2A-000183",      // required — see §8 idempotency
  // NOTE: no "device_id" field here — the authenticated device identity comes
  // from the access token on the request itself (see §4.1, §5.4), not the payload.
  "vehicle_id": "veh_1183",                     // required — cross-checked against the authenticated device's current assignment (§5.4)
  "device_timestamp": "2026-08-22T14:03:11.500Z", // required — device's own clock
  "location": {                                  // required
    "latitude": 19.0728,
    "longitude": 72.8826,
    "accuracy_m": 4.5,                           // optional — GPS HDOP-derived accuracy
    "source": "gnss"                             // required if location present: gnss | network | fused
  },
  "speed_mps": 8.3,                              // optional
  "event_type": "pothole",                       // optional at ingestion time if backend is expected to classify
  "confidence": 0.82,                            // optional — omitted if device sends raw-only mode
  "severity": 0.55,                              // optional — same as above
  "modality_sources": ["imu"],                   // required — see §9, e.g. ["imu"], ["camera"], ["imu","camera"]
  "model_output": {                              // optional — present only in pre-classified mode
    "model_name": "imu-rf-v1",
    "model_version": "1.4.2",
    "inference_location": "edge"
  },
  "sensor_data": {                               // optional — raw supporting data inline for small payloads
    "imu_window": { "...": "..." }
  },
  "firmware_version": "0.9.3"                    // required
}
```

### 4.3 `POST /events` — Response

```json
{
  "event_id": "evt_7a41c9",         // server-assigned canonical ID
  "device_event_id": "esp32-4F2A-000183",
  "status": "accepted",             // accepted | duplicate | rejected
  "duplicate_of": null,             // set if status == duplicate (see §8)
  "server_timestamp": "2026-08-22T14:03:12.100Z",
  "corroboration_count": 1
}
```

### 4.4 Validation rules
- Reject (401/403) if the access token is missing/invalid/expired, or if it doesn't resolve to an active device (see §5.4) — this check happens before any payload field is even considered.
- Reject (400) if `location`, `vehicle_id`, `device_timestamp`, `modality_sources`, or `device_event_id` are missing.
- Reject (409) if the (server-resolved) authenticated device is not currently assigned to the `vehicle_id` in the payload (§5.4).
- Reject if neither `event_type`+`confidence` (pre-classified mode) nor `sensor_data` (raw mode) is present — the backend needs at least one to act on.
- Accept but flag (`status: "accepted"`, with a `warnings` array) if `device_timestamp` is more than a configurable threshold (e.g. 5 minutes) away from server time, since this usually signals a device clock issue worth surfacing to admins.

### 4.5 Media attachment
`POST /events/{event_id}/media` is **not** a JSON body upload. See §11 (media strategy) — large binary payloads use pre-signed upload URLs, not inline JSON.

---

## 5. Device Authentication & Provisioning (new — was previously one line)

Previously: `auth_key/token` and `/devices/{id}/auth` with no detail. Now specified:

### 5.1 Provisioning flow
1. Device is registered by an admin (or fleet operator) via `POST /devices/register`, producing a `device_id` and a **provisioning secret** (delivered out-of-band — QR code, flashed at manufacturing time, or admin-issued one-time code — never returned again after this call).
2. On first boot, the device exchanges the provisioning secret for a long-lived **device credential** via `POST /devices/{id}/provision`. This is a one-time exchange; the provisioning secret is invalidated after use.
3. For each session, the device exchanges its device credential for a short-lived JWT via `POST /devices/{id}/auth` (access token, ~1 hour expiry). The device credential itself is never sent on every request.

### 5.2 Credential lifecycle
- **Rotation:** `POST /devices/{id}/credential/rotate` — issues a new device credential, invalidates the old one after a grace period (to allow in-flight devices to pick up the new one).
- **Revocation:** `POST /devices/{id}/revoke` — immediately invalidates the device credential and any outstanding access tokens (for lost/stolen/decommissioned hardware).
- **Disabling vs revoking:** "disabled" (`PATCH /devices/{id}` with `status: disabled`) is a soft, reversible state (e.g. vehicle temporarily out of service) that stops new events from being accepted but keeps the credential valid. "Revoked" is hard and irreversible without re-provisioning.

### 5.3 Device-to-vehicle reassignment
- `POST /devices/{id}/reassign` — changes `vehicle_id` on a device record, closing out the association with an `assigned_from` / `assigned_to` timestamp range so historical events remain correctly attributed to the vehicle that was active at the time, not the device's current assignment.

### 5.4 Event ingestion uses device auth, not driver auth (new — clarifies RBAC §6)
- `POST /events` is authenticated with the **device's** short-lived access token (issued via §5.1's `/devices/{id}/auth` flow), never with a driver's/user's JWT. A driver logging into the dashboard has no mechanism to submit a `RoadEvent` directly — only their vehicle's device can.
- **Identity derivation chain (new — see §4.1):** `device credential → authenticated device_id → current DeviceVehicleAssignment lookup → accepted vehicle_id`. The backend never trusts a client-asserted `device_id`; it resolves the device solely from the access token, then looks up that device's *current* assignment, then checks the payload's `vehicle_id` against that lookup.
- On every `POST /events`, the backend checks the `vehicle_id` in the payload against the (server-resolved) device's **current** assignment (`DeviceVehicleAssignment`, §12) at `device_timestamp`. If the device isn't currently assigned to that vehicle, the request is rejected (409) rather than silently accepted — this prevents a misconfigured or reassigned device from attributing events to the wrong vehicle.
- The RBAC table's "Events — create (own vehicle only)" row for **Driver** (§6) describes the real-world outcome (events end up attributed to the driver's vehicle) but the actual bearer of the write credential is always the device, not the driver's session. This distinction matters for incident response: revoking a driver's dashboard access does **not** stop their vehicle's device from uploading events — that requires device revocation (§5.2).

---

## 6. RBAC — Role Permissions (new — was previously just role names)

Frontend route guards are **not** a security boundary — every permission below is enforced server-side, in addition to whatever the UI hides.

| Resource | Driver | Admin | Authority |
|---|---|---|---|
| Events — read (own vicinity/route) | ✅ | ✅ (all) | ✅ (all) |
| Events — read (full history/raw sensor data) | ❌ | ✅ | ✅ (read-only) |
| Events — create (via device under their vehicle) | ✅ (own vehicle only) | ✅ | ❌ |
| Events — update status (verify/duplicate/resolve) | ❌ | ✅ | ✅ |
| Events — delete | ❌ | ✅ (soft-delete only) | ❌ |
| Reports — create | ✅ | ✅ | ✅ |
| Reports — read (own) | ✅ | ✅ (all) | ✅ (all) |
| Media — upload | ✅ (own reports/vehicle) | ✅ | ❌ |
| Media — read | ✅ (own) | ✅ (all) | ✅ (all) |
| Devices — register/provision/revoke | ❌ | ✅ | ❌ |
| Devices — reassign | ❌ (self-service reassignment of own vehicle's device is a future option) | ✅ | ❌ |
| Vehicles — create/update (own) | ✅ | ✅ | ❌ |
| Analytics — view | ❌ | ✅ | ✅ |
| Analytics — export | ❌ | ✅ | ✅ |

Notes:
- "Authority" is treated as a **read-mostly + verification** role — they can confirm/resolve events and view analytics, but don't manage devices or vehicles. If the real-world authority workflow needs more (e.g. commissioning repairs), that's a future extension, not a v1 blocker.
- Permission checks live in a single backend authorization layer (e.g. a dependency/middleware in FastAPI keyed off the JWT's role claim), not scattered per-endpoint, so this table stays the single source of truth.

---

## 7. Real-Time Architecture — v1 Decision (new — was "WebSocket/MQTT", now decided)

- **v1: WebSocket only**, served by the backend app itself. MQTT is **not** part of v1 — it remains a possible future option for internal IoT device-to-cloud transport (not dashboard-facing) if device fleets grow large enough to need pub/sub at that layer.
- **Auth:** client connects with a short-lived JWT (same access token used for REST calls) passed as a query param or subprotocol header at connection time; connection is rejected if invalid/expired.
- **Subscription model:** client sends a `subscribe` message with a bounding box (`{"type": "subscribe", "bbox": [minLon, minLat, maxLon, maxLat]}`) after connecting. Server only pushes events whose location falls in the current subscribed bbox. Client re-subscribes (replacing the previous bbox) whenever the visible map area changes significantly — not on every pixel of pan/zoom, but debounced.
- **Message format:**
  ```json
  { "type": "event_created", "event": { /* same shape as the /events response, enriched */ } }
  { "type": "event_updated", "event_id": "evt_7a41c9", "status": "verified" }
  ```
- **Reconnect behaviour:** client uses exponential backoff (e.g. 1s, 2s, 4s... capped at 30s); on reconnect, re-sends the last known bbox subscription. The server does **not** replay missed messages — on reconnect, the client is expected to re-fetch current state via `GET /events?bbox=...` to reconcile, then resume live updates. This keeps v1 simple; a message-replay/offset-based reconnect model is future work if gaps become a real problem.
- **Scaling boundary (new):** serving WebSocket connections directly from the FastAPI app assumes a **single backend instance** at v1 scale. This is fine for the expected v1 device/user count. If the backend is later horizontally scaled across multiple instances, in-process WebSocket fan-out no longer works on its own — a shared pub-sub layer (e.g. Redis pub/sub, or the MQTT broker mentioned as a future option) will be needed to fan events out to whichever instance holds a given client's connection. This is documented here as a known boundary, not something v1 needs to build.

---

## 8. Event Idempotency (new)

- Every device-submitted event carries a **`device_event_id`** — generated by the device itself (e.g. a local monotonic counter or UUID), stable across retries of the *same* physical detection.
- The backend enforces uniqueness on `(device_id, device_event_id)`. If a device retries an upload (bad connectivity, no ack received) with the same `device_event_id`, the backend returns `status: "duplicate"` with the original `event_id` in `duplicate_of`, and does **not** create a second row.
- This is distinct from **corroboration** (§10-adjacent concept): idempotency prevents the *same device* from double-submitting the *same physical detection*; corroboration is about *different vehicles* independently detecting the *same real-world hazard*. Both matter, but they operate at different layers — idempotency is a hard uniqueness constraint at ingestion, corroboration is a fuzzy spatial/temporal match applied after ingestion.
- **`corroboration_count` definition (new — was ambiguous):** this counter increments only when a **different device** (equivalently, in v1, a different vehicle — see §5.3 on reassignment for why device-level and vehicle-level are treated as equivalent here) submits an event that spatially/temporally matches an existing `RoadEvent`. It does **not** increment on: (a) the same `device_event_id` being retried (blocked entirely by the idempotency constraint above, never reaches the counter), or (b) the same device submitting a second, distinct-but-nearby detection of what is likely the same physical hazard (this is deduplicated against the *same* `RoadEvent` but does not itself add corroboration weight, since it's not independent evidence). Concretely: Device A detects a pothole (`corroboration_count = 1`); Device A retries the same detection (still `1`, blocked by idempotency); Device B independently detects the same pothole (`corroboration_count = 2`). This count is what feeds confidence aggregation (§4.1) — only independent-device corroboration should increase confidence, not repeated reports from one source.

---

## 9. Multimodal Fusion — Modality Attribution (new — was previously unclear)

Previously, `inference_location` (edge vs cloud) told us *where* inference happened but not *which sensor modality* produced a given prediction. Fixed as follows:

- Every `RoadEvent` carries a required **`modality_sources`** array (e.g. `["imu"]`, `["camera"]`, `["imu", "camera"]`) at the top level, describing what data contributed to this event overall.
- Each individual `MLPrediction` row (see §12 schema) carries its own **`modality`** field (`imu` | `camera` | `fused`) plus `inference_location` (`edge` | `cloud`) — so a single `RoadEvent` can have multiple `MLPrediction` rows, one per modality, plus optionally one `fused` prediction that combines them.
- **Fusion record:** when more than one modality contributes, a fusion step produces a top-level prediction with `modality: "fused"` and references the contributing predictions (`fused_from: ["pred_id_1", "pred_id_2"]`). v1 fusion is late fusion (simple weighted/rule-based combination of independent modality confidences); learned/joint fusion models are future work once multimodal labeled data exists.
- **Camera ingestion stays out of `/events`/`/telemetry` JSON entirely (new — explicit callout to prevent a future implementation mistake):** once camera/edge-AI hardware arrives, continuous camera frames are **never** sent as part of a normal `/events` or `/telemetry` JSON payload. Camera data is processed **on the edge device** — frame-by-frame inference happens locally, and only the resulting classification (`event_type`, `confidence`, `modality: "camera"`) travels through `/events` like any other pre-classified detection. If supporting visual evidence is wanted (a still frame or short clip around the detection), it goes through the pre-signed media upload flow (§11), attached to the resulting `RoadEvent` — it is never inlined as base64/binary inside a JSON request. This keeps the ingestion API's payload size and shape identical regardless of whether a device has a camera at all.

---

## 10. Timestamp & Location Quality (new)

- Every event stores **two** timestamps: `device_timestamp` (device's own clock at capture time) and `server_timestamp` (set by the backend on receipt). Geospatial/segment matching and corroboration windows use `device_timestamp` as the primary signal but fall back to `server_timestamp` if the device clock looks unreliable (see §4.4 validation warning).
- Location carries `accuracy_m` (when available from GNSS HDOP or similar) and `source` (`gnss` | `network` | `fused`). Events with poor accuracy (above a configurable threshold) are still accepted but flagged, and are weighted lower in `RoadSegment` assignment and corroboration matching.

---

## 11. Media Upload Strategy (new — "should clarify" item)

Large images/video are **not** sent as part of the `/events` JSON payload or as a simple `POST` body through the API server.

1. Client (device or dashboard) requests an upload slot: `POST /events/{event_id}/media/upload-url` → backend returns a pre-signed upload URL (S3-compatible) plus a `media_id`.
2. Client uploads the binary directly to that URL.
3. Client confirms completion: `POST /events/{event_id}/media/{media_id}/confirm` → backend verifies the object exists, records it as a `MediaAsset` row, and (for v1) queues no further processing. Thumbnail generation / video transcoding is future work, not a v1 requirement.

This keeps the API server from handling large binary traffic directly and matches how object storage is meant to be used.

### 11.1 Report media flow (new — was unspecified)

A user-submitted `Report` (§12) is a separate entity from a `RoadEvent`, and it gets its **own** media endpoints rather than requiring a report to be linked to an event first:

1. `POST /reports/{report_id}/media/upload-url` → same pre-signed-URL pattern as events, returns a `media_id`.
2. Client uploads directly to the returned URL.
3. `POST /reports/{report_id}/media/{media_id}/confirm` → backend records the `MediaAsset` row with `report_id` set (instead of `event_id`).

`MediaAsset` (§12 schema) therefore takes **either** an `event_id` **or** a `report_id` (mutually exclusive, both nullable) rather than assuming every media asset belongs to an event. This matters because a report is often submitted with no corresponding sensor-detected `RoadEvent` at all — requiring an event to exist first would block the common case of a driver manually photographing a hazard their vehicle's sensors never triggered on.

If an admin later links a `Report` to an existing `RoadEvent` (e.g. confirming it's the same hazard a sensor already detected), the report's media stays attached to the report — it is not moved or duplicated onto the event.

---

## 12. Database Design (entities revised)

```
Vehicle
├── id
├── type (2-wheeler | car | bus | truck | fleet | other)
├── owner_id (nullable, for private vs fleet)
└── metadata (make, model, etc.)

Device
├── id
├── vehicle_id (FK, nullable — device can be unassigned between reassignments)
├── hardware_type (ESP32 | edge-ai | other)
├── firmware_version
├── credential_hash                      // NEW — never store raw credential
├── status (provisioning | active | disabled | revoked)  // NEW
└── last_seen_at

DeviceVehicleAssignment                  // NEW — historical device↔vehicle mapping
├── id
├── device_id (FK)
├── vehicle_id (FK)
├── assigned_from
└── assigned_to (nullable = current)

RoadEvent
├── id                                    // == event_id
├── device_event_id                       // NEW — idempotency key, unique with device_id
├── device_id (FK)
├── vehicle_id (FK)
├── device_timestamp                      // NEW — split from single "timestamp"
├── server_timestamp                      // NEW
├── latitude / longitude
├── location_accuracy_m                   // NEW
├── location_source (gnss | network | fused)  // NEW
├── road_segment_id (FK, nullable — resolved async)
├── event_type (pothole | speed_breaker | crack | waterlogging | debris | manhole | edge_damage | other)
├── modality_sources (array)              // NEW
├── confidence (0–1)
├── severity (0–1 float)
├── severity_label (derived: low|medium|high|critical)  // NEW
├── status (unverified | verified | duplicate | resolved)
├── schema_version                        // NEW
├── firmware_version
└── corroboration_count

Telemetry                                 // NEW — replaces event-only SensorData for raw/negative data
├── id
├── device_id (FK)
├── vehicle_id (FK)
├── device_timestamp
├── server_timestamp
├── latitude / longitude
├── raw_payload (JSON — IMU window, speed, etc.)
├── label (nullable — e.g. "smooth_road", "confirmed_pothole", set during dataset curation)
└── linked_event_id (FK, nullable — set if this telemetry was later associated with a RoadEvent)

**Telemetry retention & storage strategy (v1 — new, addresses reviewer concern about scale):**
- **What's retained in v1:** event-window telemetry only — a bounded window immediately surrounding a detection (e.g. ~2–5 seconds of IMU samples at the device's native rate, roughly 100–500 samples depending on sensor rate, plus matching GPS/speed) — not continuous always-on streaming from every device. Continuous background telemetry (for building a broader negative/smooth-road dataset) is collected deliberately and sparingly in v1 — e.g. periodic short samples (a few seconds every N minutes) from a limited subset of instrumented vehicles for dataset-building purposes, not from the full fleet continuously.
- **Why this matters:** `raw_payload` JSON blobs grow fast — continuous full-fleet streaming would make this table the dominant source of storage/IO load well before `RoadEvent` volume becomes a concern. Bounding collection to event-windows plus sparse sampled negatives keeps v1 storage proportional to detected-event volume, not to fleet-wide continuous sensor throughput.
- **Storage:** PostgreSQL JSON storage for `raw_payload` is acceptable at v1 scale (expected device counts in the tens–low hundreds). This is explicitly **not** assumed to hold at 1,000+ continuously-reporting devices — at that scale, `Telemetry` volume should move toward table partitioning (by time), and/or offloading `raw_payload` blobs to object storage with only a pointer kept in Postgres, and/or a dedicated time-series store. None of this is a v1 requirement; it's flagged here so the schema choice isn't mistaken for one that scales indefinitely as-is.
- **Retention:** event-window telemetry that gets linked to a `RoadEvent` (`linked_event_id` set) follows the same retention as the linked event's media (`§13A`, baseline 90 days, admin-extendable). Unlinked telemetry collected purely for dataset-building is retained longer by default (e.g. 1 year) since it has ongoing ML training value independent of any specific event, but is still subject to a defined expiry rather than indefinite accumulation — the exact duration is a product/ML-team call, not fixed here, but "indefinite" is explicitly not the v1 default.

SensorData                                // now specifically event-linked evidence
├── id
├── event_id (FK)
├── source (imu | gps | speed | can_obd)
└── raw_payload (JSON)

MediaAsset
├── id
├── event_id (FK, nullable)               // NEW — mutually exclusive with report_id
├── report_id (FK, nullable)              // NEW — mutually exclusive with event_id
├── type (image | video)
├── storage_url
├── captured_at
├── retention_expires_at                  // NEW — see §13A
└── access_tier (raw | processed)         // NEW — see §13A

MLPrediction
├── id
├── event_id (FK)
├── modality (imu | camera | fused)       // NEW — was missing, only had inference_location
├── model_name
├── model_version
├── predicted_type
├── confidence
├── inference_location (edge | cloud)
└── fused_from (array of MLPrediction ids, nullable — only set when modality == fused)  // NEW

RoadSegment                               // clarified — see §13
├── id
├── road_network_ref (nullable — external road-network dataset ID, e.g. OSM way ID, if/when integrated)
├── geometry (actual road-network polyline, not a geohash cell)
├── safety_score
└── last_updated

GeoIndexBucket                            // NEW — purely technical, for dedup/indexing, not a "segment"
├── geohash
└── (used internally for corroboration matching before road-network mapping is available)

User
├── id
├── role (driver | admin | authority)
├── auth_info
└── saved_locations

Report
├── id
├── user_id (FK)
├── event_id (FK, nullable — may not match a sensor event)
├── description
├── media
└── status
```

---

## 13. RoadSegment vs. Geohash (new — was conflated)

- **`RoadSegment`** represents an actual segment of the real-world road network (ideally referencing an external road-network dataset like OpenStreetMap ways, once that integration exists) — this is the semantically meaningful unit for safety scoring, repair prioritization, and route-risk queries.
- **Geohash** (via `GeoIndexBucket`) is purely a spatial-indexing convenience used for fast proximity lookups and initial corroboration matching (has another event already been reported near here recently?) — it is **not** a substitute for a road segment and should never be surfaced to users/admins as if it were one.
- **v1 approach:** since full road-network integration is a larger effort, v1 can assign events to geohash buckets for corroboration/dedup immediately, while `road_segment_id` remains nullable and gets backfilled asynchronously (a batch job that maps events to real road segments) once road-network data is integrated. This avoids blocking v1 launch on a road-network integration that isn't ready yet.
- **Frontend framing (new — see `frontend-spec.md §9`):** because `road_segment_id` is frequently null in v1, the frontend must not present a geohash-bucketed cluster of events as if it were a true road-network safety segment. Until road-network backfill exists for a given area, hazard clustering should be labeled as location-based hazard intelligence, not a "segment," in any UI copy.

---

## 13A. Media Privacy & Retention (new — baseline rules, not a full privacy system)

Future camera/video collection raises questions this spec should at least acknowledge now, even if the full policy is refined later:

- **Who can see raw media:** per RBAC (§6), admin and authority roles can view raw media attached to events and reports. Drivers can view raw media only for their **own** reports/vehicle; they do not see other vehicles' raw source images/video by default.
- **Raw vs. processed evidence for drivers:** on the driver-facing dashboard, hazards detected by *other* vehicles show processed evidence (event type, confidence, severity, and — if available — a representative image already surfaced by an admin as verification evidence), not raw sensor/camera feeds from other users' vehicles. This is reflected in `MediaAsset.access_tier` (`raw` | `processed`) — driver-facing queries for third-party events filter to `processed` media only.
- **Retention (v1 baseline):** `retention_expires_at` is set on ingestion using a configurable default (e.g. raw media retained 90 days, long enough for verification/dispute workflows, then eligible for deletion by a scheduled cleanup job). Verified events that get referenced in analytics/exports can have their retention extended, but this is a manual admin action in v1, not automatic indefinite retention.
- **Explicitly future work:** a full consent/privacy framework (e.g. per-jurisdiction data protection rules, driver opt-out of camera capture, blurring faces/plates in stored media) is **not** designed here. This section only establishes that retention and access-tier fields exist in the schema so that policy can be layered on without another schema migration later.

---

## 14. Safety Score Contract (new — "should clarify" item)

- **Range:** 0–100 (not 0–1, to distinguish it visually/semantically from per-event confidence/severity floats).
- **Interpretation:** higher = safer. 100 = no known hazards; lower scores reflect more/higher-severity unresolved events on that segment.
- **Inputs (v1):** count and severity of unresolved verified events on the segment, weighted by recency (older unresolved events decay in weight slowly, reflecting that road conditions do get repaired even without an explicit "resolved" status update).
- **Update behaviour:** recomputed asynchronously (not on every single event write) — e.g. on a scheduled job or triggered after N new events land on a segment — since this is a rollup, not a hot-path value.
- **Future work:** incorporating traffic volume, road class/speed limit, or historical incident data into the score is a later refinement, not a v1 requirement.

---

## 15. Route-Risk Scoring vs. Alternative-Route Generation (new — "should clarify" item)

These are explicitly two different features, and v1 only commits to the first:

- **v1 — Route-risk scoring:** given a route (polyline from an external routing/navigation provider), return the aggregated safety scores of the segments it passes through — `GET /routes/safety?polyline=...`. This is read-only annotation of a route the client already has.
- **Future work — Alternative-route generation:** actually computing a *different*, safer route is a routing-engine problem (needs full road-network graph + routing algorithm), not something this backend takes on in v1. If needed later, this likely integrates with or wraps an external routing provider rather than building one from scratch.

---

## 16. IoT Offline Buffering & Retry (new — "should clarify" item, kept lightweight for v1)

- **v1 requirement:** device firmware should buffer events locally (bounded ring buffer, e.g. last N events) when connectivity is unavailable, and retry upload with backoff when connectivity returns. Because of `device_event_id` idempotency (§8), retries are safe by design — no dedup logic needed on the firmware side beyond "keep sending until acked."
- **Future work:** prioritized buffering (e.g. high-severity events evicted last), store-and-forward across multiple backend endpoints, or on-device compression for large media buffers are not v1 requirements.

---

## 17. ML Pipeline (unchanged from v0.1, model provenance note added)

### 17.1 Pipeline Stages
```
Raw Data Collection
      ↓
Dataset Curation (per sensor modality)
      ↓
Labelling (manual + semi-automated bootstrapping from IMU threshold events)
      ↓
Preprocessing (normalization, windowing, image augmentation)
      ↓
Feature Extraction (IMU windows, image crops/embeddings)
      ↓
Model Training (per-modality, then fusion)
      ↓
Evaluation (precision/recall per event type, false-positive rate on smooth roads)
      ↓
Edge Deployment (quantization/pruning for on-device inference)
      ↓
Real-World Testing (shadow mode before it drives alerts)
```

### 17.2 Data Requirements
- IMU time-series windows around confirmed hazard events — now sourced from `Telemetry` (§12), including standalone negative/smooth-road samples that never became a `RoadEvent`.
- GPS + speed at time of event, for impact-magnitude normalization.
- Camera frames/clips around the same timestamp, once camera hardware is available.
- Negative samples (smooth road, non-damage speed bumps) — critical to reduce false positives, and now explicitly storable via `Telemetry.label` without forcing a `RoadEvent` to exist.
- Metadata: vehicle type, suspension type if available.

### 17.3 Candidate Models (not finalized)
- **Sensor-only baseline:** classical ML (Random Forest / gradient boosting) on IMU-derived features.
- **Vision:** YOLO-family detection for potholes/debris/open manholes; segmentation for cracks/uneven surfaces/waterlogging extent.
- **Fusion:** late fusion in v1 (see §9); learned fusion is future work.
- **Anomaly detection:** for novel/unclassified hazards.

### 17.4 Model Provenance (new — "should clarify" item)
Every `MLPrediction` records `model_name` + `model_version` + `modality` (§9) + `inference_location`. This four-tuple is the minimum provenance needed to answer "which model, trained on what, running where, using what data, produced this prediction" — without standing up a full model registry, which remains future work.

### 17.5 Evaluation
- Per-event-type precision/recall, not just overall accuracy.
- False-positive rate on "known smooth" road segments.
- Cross-vehicle generalization.
- Latency/footprint benchmarks for edge deployment candidates.

### 17.6 Edge Deployment Path
```
Trained Model → Quantization/Pruning → Edge Runtime (ONNX/TensorRT/TFLite)
      ↓
On-device Inference → {event_type, confidence, modality}
      ↓
Bundled with GPS + IMU → sent to Backend API
```

---

## 18. Explicitly Deferred to Future Work

Per review, these are intentionally **not** part of v1 and should not block implementation:
- Redis/Celery or other async task queues
- Full MLOps/model registry
- Large-scale MQTT infrastructure (MQTT may still be used internally between edge devices later, but not as the v1 dashboard real-time transport)
- Advanced route optimization / alternative-route generation
- Complete offline-first frontend architecture
- Message-replay/offset-based WebSocket reconnect
- Media thumbnailing/transcoding pipeline
- Road-network-integrated `RoadSegment` at launch (geohash-based v1 approach, see §13)
- Full media privacy/consent framework (blurring, per-jurisdiction rules, opt-outs) — v1 only ships baseline retention + access-tier fields (§13A)
- Multi-instance WebSocket fan-out / shared pub-sub broker (§7) — v1 assumes single-instance scale

---

## 19. Immediate Next Steps

1. Implement `RoadEvent` schema + `/events` endpoint exactly per §4, including `device_event_id` idempotency (§8) from day one — retrofitting idempotency later is much harder once devices are in the field.
2. Implement device provisioning/auth flow (§5) before any real device goes into the field, even in prototype form — auth_key-in-firmware is not acceptable beyond a lab bench test.
3. Stand up the RBAC authorization layer (§6) as a single enforcement point before building out admin endpoints, so permissions aren't retrofitted per-route.
4. Implement WebSocket real-time (§7) with bbox subscription — skip MQTT entirely for v1.
5. Add `Telemetry` table (§12) alongside `RoadEvent` so negative/smooth-road data collection can start immediately, in parallel with event ingestion.
6. Define the dynamic configuration endpoints needed by the frontend (see `frontend-spec.md §3` — `event_type` list, severity scale, vehicle types) so the frontend's dynamic-config assumption has something to actually call.
7. Implement report-specific media endpoints (§11.1) alongside event media endpoints from the start — don't build only the event path and retrofit reports later, since manual reporting without a prior event is the common driver use case.
8. Confirm device-vehicle-assignment validation (§5.4) is enforced on the `/events` write path before any field device goes live, so a reassigned or misconfigured device can't silently attribute events to the wrong vehicle — and confirm the identity derivation chain (§4.1, §5.4) is implemented as auth-token-first, with any `device_id` in a payload never trusted.
9. Implement the `/events` vs `/telemetry` boundary (§4.1) and the `corroboration_count` independent-device semantics (§8) together in the first ingestion pass — both are easy to get subtly wrong if implemented separately without referencing this shared definition.
10. Treat the PostgreSQL/Firebase note (§3.1) as a migration-planning input immediately: confirm which current prototype data needs migrating and on what timeline, so Firebase is never accidentally treated as a second authoritative store past the migration window.
