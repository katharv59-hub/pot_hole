# ROADSentinel — Frontend & Dashboard Specification

**Author:** Atharv (Software + AI/ML Systems)
**Status:** Draft v0.4 — Aligned with backend-spec v0.4
**Companion doc:** `backend-spec.md` (API, database, ML pipeline)

**Changelog v0.1 → v0.2:** Responds to the first spec review. Direction unchanged — map-first, role-based (driver vs admin/authority), data-driven rendering. Resolved: dynamic-configuration endpoints, v1 real-time transport decision, server-side RBAC confirmation, media upload flow, offline/stale-data behaviour.

**Changelog v0.2 → v0.3:** Responds to the second review. Resolved: the report-specific media flow (separate from event media), explicit note that event ingestion auth is device-level not driver-level, a stated WebSocket scaling boundary, firmer UI framing that a geohash cluster is not a road segment, a baseline media privacy/retention note for the driver view, and concrete v1 library choices (was previously "X or Y"). This is the version treated as ready for implementation planning.

**Changelog v0.3 → v0.4:** The third review's clarifications (device-identity derivation, PostgreSQL/Firebase authority, telemetry retention/scale, `/events` vs `/telemetry` boundary, camera ingestion path, `corroboration_count` semantics) were all backend-only concerns — no frontend behaviour changes as a result. Version bumped to stay aligned with `backend-spec.md v0.4`; §5's note that the driver dashboard never itself calls `/events` is consistent with the more detailed identity-derivation chain now spelled out on the backend side.

**v0.4 is the implementation baseline** — see `backend-spec.md §0` for the four binding constraints for the first build. The one directly relevant to this document is: **geohash-based clustering must never be presented as a real road segment** — §10 below already establishes this UI framing and remains the authoritative reference for it.

---

## 1. Guiding Principles (unchanged)

- **Role-based, not app-based**: the same platform serves drivers and admins/authorities, with shared components but separate views and permissions.
- **Data-driven rendering**: hazard types, severity levels, and vehicle types are fetched from the backend, not hardcoded (see §3 — now backed by real endpoints).
- **Map-first**: nearly every meaningful view is spatial.
- **Trust through evidence**: confidence, severity, and supporting media/corroboration count are always visible alongside a hazard, not hidden behind a click.
- **Frontend is not the security boundary** (new — see §7): all role guards in the UI are a UX convenience. Every read/write is independently authorized server-side per `backend-spec.md §6`.

---

## 2. Where the Frontend Sits in the System

```
Backend API (see backend-spec.md)
        ↓
   Read endpoints (/events, /segments, /routes/safety, /config/*)
   Real-time channel (WebSocket, v1 — see §5)
        ↓
┌───────────────┴───────────────┐
↓                               ↓
User Dashboard            Admin/Authority Dashboard
(driver-facing)           (verification + analytics)
```

The frontend consumes:
- `GET /events?bbox=...` for map hazard layers
- `GET /segments/{id}/score` and `GET /routes/safety?polyline=...` for route/segment risk overlays (route-risk *scoring* only — see backend-spec.md §15 for why alternative-route generation is out of scope for v1)
- `GET /config/event-types`, `GET /config/severity-scale`, `GET /config/vehicle-types` (new — see §3) for dynamic rendering
- A WebSocket subscription scoped to the visible map bounding box (see §5) for live hazard updates
- `POST /reports` for manual user-submitted hazards
- The pre-signed media upload flow (see §6) for photos attached to reports

---

## 3. Dynamic Configuration (resolved — was a gap between the two docs)

Previously, this spec assumed hazard types/severity levels/vehicle types would come from the backend, but no such endpoint existed. These are now defined:

- `GET /config/event-types` → returns the current `event_type` enum (`pothole`, `speed_breaker`, `crack`, `waterlogging`, `debris`, `manhole`, `edge_damage`, `other`, ...) plus a display label and icon key for each, so new hazard types added on the backend (`backend-spec.md §4`) show up in the UI without a frontend redeploy.
- `GET /config/severity-scale` → returns how the 0–1 float severity maps to the human-readable `severity_label` buckets (low/medium/high/critical) and their associated colors, so both frontend and backend stay in sync on the same thresholds instead of the frontend guessing.
- `GET /config/vehicle-types` → returns the current vehicle type list for report/vehicle forms.

**v1 behaviour:** the frontend fetches these once per session (cached client-side; low change frequency), rather than re-fetching per view. A manual refresh path (or app restart) picks up changes — real-time config push is not a v1 requirement.

---

## 4. User (Driver) View (unchanged in scope, media flow updated)

### 4.1 Core Screens
- **Live map** — current location, nearby hazards rendered as markers/clusters, color-coded by severity (using `§3`'s severity-scale colors, not hardcoded ones)
- **Hazard warnings** — proximity-based alert (visual + optional audio/voice) as the driver approaches a high-confidence hazard
- **Route safety** — overlay segment-level safety scores (`backend-spec.md §14`, 0–100 scale) along a planned route; this is annotation only, not alternate-route suggestion (see §2 note)
- **Manual reporting** — tap location (or use current GPS), optional photo via the pre-signed upload flow (§6), optional description, submit
- **Report history** — user's own submitted reports and status (pending/verified/resolved)
- **Saved locations** — home/work/frequent routes for faster route-safety checks

### 4.2 UX Notes
- Alerts are based on severity + confidence thresholds, not every detected event.
- Voice alerts are short and non-distracting; visual-only fallback when audio isn't appropriate.
- Offline behaviour (see §8): last-fetched nearby hazard set is cached locally so alerts still function with intermittent connectivity, but this is explicitly a **cache**, not a full offline-first architecture (that remains future work per `backend-spec.md §18`).

---

## 5. Admin / Authority View (unchanged in scope, RBAC + real-time notes added)

### 5.1 Core Screens
- **Full road hazard map** — all events, filterable by type, severity, status, date range, vehicle type
- **Event detail view** — confidence, severity, media evidence, corroboration count, source device/vehicle, model version, and now also **modality** (`backend-spec.md §9` — which sensor(s) produced this detection) and both `device_timestamp`/`server_timestamp` (`backend-spec.md §10`), since a mismatch between the two is useful diagnostic info for admins
- **Verification workflow** — mark verified/duplicate/resolved; this action is a `PATCH /admin/events/{id}/status` call, permitted for admin/authority roles per the RBAC table (`backend-spec.md §6`) — the UI hides this control from drivers, but the server would reject the call regardless
- **Road-condition analytics** — hotspot trends, severity distribution, repeat-detection heatmaps, resolution turnaround time
- **Segment-level safety dashboard** — using the 0–100 safety score contract (`backend-spec.md §14`)

### 5.2 UX Notes
- Default admin view surfaces unverified, high-confidence, high-severity events first — a triage queue, not a flat list.
- Analytics support export (CSV/PDF) — export permission is itself RBAC-gated (`backend-spec.md §6`: admin and authority can export, driver cannot).
- Bulk actions (multi-select for e.g. batch-resolving low-confidence duplicates) are worth designing the table/list view for from the start, even if not built in v1.
- Live updates in this view use the same WebSocket bbox-subscription mechanism as the driver map (§5 below), just typically with a wider/whole-region bbox for admins monitoring a larger area.

---

## 6. Media Upload Flow (new — frontend side of `backend-spec.md §11`)

Photos/video are never sent as part of a JSON `POST` body. The frontend flow:

These are now two distinct flows, matching `backend-spec.md §11` and `§11.1` — a report does **not** need to be linked to an event before a photo can be attached:

**Attaching media to an event** (e.g. admin adding supplementary evidence to a sensor-detected event):
1. `POST /events/{event_id}/media/upload-url` → pre-signed URL + `media_id`.
2. Upload the file directly to that URL (not through the API server).
3. `POST /events/{event_id}/media/{media_id}/confirm`.

**Attaching media to a manual report** (the common driver flow — no prior event required):
1. `POST /reports/{report_id}/media/upload-url` → pre-signed URL + `media_id`.
2. Upload the file directly to that URL.
3. `POST /reports/{report_id}/media/{media_id}/confirm`.

UI implication: the report-creation screen should be able to attach a photo immediately as part of submitting a `Report`, without waiting on or requiring any `event_id` — the "report a hazard" flow and the "add evidence to an existing event" flow (admin-only) use different endpoints even though the upload mechanics (pre-signed URL → direct upload → confirm) are identical. Upload progress should track against the direct storage upload, and a failed confirm step should be retryable without re-uploading the file.

---

## 7. RBAC in the Frontend (new — clarifies role of route guards)

- Route guards (hiding admin screens from a driver-role user, etc.) exist purely for UX — they prevent a legitimate user from wandering into a view that isn't meaningful for their role.
- They are **not** a security control. Every read/write the frontend makes is independently authorized server-side against the RBAC table in `backend-spec.md §6`. A compromised or modified frontend client cannot gain access beyond what the user's JWT role permits.
- Practical implication: the frontend can optimistically hide a button (e.g. "Verify") for a driver, but doesn't need special handling for "what if the API call fails due to permissions" beyond normal error handling, since a driver's client should never be constructing that call in the first place.
- **Event creation is not a dashboard action** (new — clarifies `backend-spec.md §5.4`): the driver dashboard never itself submits a `RoadEvent` to `/events` using the driver's session — that write only ever comes from the vehicle's device, authenticated with its own device credential. The dashboard's "driver can create events" behaviour in the RBAC table describes the outcome (events end up attributed to their vehicle), not a button the driver dashboard exposes. The one exception is manual `Report` creation (§6), which genuinely is a driver-session-authenticated write.

---

## 8. Real-Time Architecture — v1 (resolved — matches `backend-spec.md §7`)

- **v1 transport: WebSocket** (not MQTT — MQTT remains a possible future internal IoT option only, not dashboard-facing).
- **Connection:** frontend connects using the same short-lived access token used for REST calls.
- **Subscription:** on connect (and whenever the visible map area changes significantly, debounced — not per pixel of pan/zoom), the frontend sends a `subscribe` message with the current bounding box.
- **Incoming messages:** `event_created` (new hazard entering the subscribed area) and `event_updated` (status change, e.g. verified) — the frontend merges these into its local map state rather than re-fetching the whole bbox.
- **Reconnect behaviour:** exponential backoff on disconnect; on reconnect, the frontend does **not** expect replayed missed messages — it re-fetches current state via `GET /events?bbox=...` to reconcile, then resumes live updates via a fresh subscription. This is a deliberate v1 simplification (`backend-spec.md §7`); message-replay is future work.
- **Scaling note (new):** v1 WebSocket is served from a single backend instance (`backend-spec.md §7`). The frontend's reconnect-and-reconcile approach above is what keeps this transparent to the client even if that changes later (e.g. a shared broker fans out events across multiple instances) — no frontend change should be needed when that migration happens, since the client already treats "reconnect" as "reconcile via REST, then resume."

---

## 9. Offline / Stale-Data Behaviour (resolved — "should clarify" item)

- **v1 scope:** the frontend keeps a local cache of the last successfully fetched nearby-hazard set (from the most recent `GET /events?bbox=...` or WebSocket updates), so driver alerts can continue briefly during a connectivity gap.
- **Staleness indication:** when the cache is being used because live data isn't available, the UI should visibly indicate this (e.g. a "showing last known data, updated Xm ago" indicator) rather than presenting stale data as current.
- **Explicitly out of scope for v1:** full offline-first architecture (local write queue for reports made while offline, background sync, conflict resolution) — this is future work per `backend-spec.md §18`. In v1, actions requiring connectivity (submitting a report, verifying an event) simply fail with a clear error and retry prompt when offline, rather than being silently queued.

---

## 10. RoadSegment Framing in the UI (new — clarifies `backend-spec.md §13`)

Because `road_segment_id` is frequently null in v1 (road-network backfill hasn't run for most areas yet), the UI must not present a cluster of nearby events as if it were an official road-network safety segment:

- Where events are grouped for display (e.g. a marker cluster, or a "hazard density" overlay), label this as **hazard location intelligence** — nearby detected/reported issues — rather than calling it a "segment" or implying a formally scored stretch of road.
- The 0–100 **safety score** (`backend-spec.md §14`) should only be shown for a location where a real `road_segment_id` exists and a score has actually been computed. Where it's null, show the raw event list/density instead of fabricating or approximating a score client-side.
- This distinction matters most in the route-safety overlay (§4) — a route passing through an area with no resolved `RoadSegment` yet should show "no scored data for this stretch," not silently omit or estimate a score.

---

## 11. Media Privacy in the Driver View (new — frontend side of `backend-spec.md §13A`)

- On the driver dashboard, hazards reported by **other** vehicles show processed evidence only (event type, confidence, severity, and an admin-surfaced representative image where available) — never another user's raw source photo/video feed. This follows `MediaAsset.access_tier` from the backend; the frontend simply must not attempt to fetch or render raw-tier media for third-party events.
- A driver's own submitted reports/media remain fully visible to them (raw tier), consistent with RBAC (§7).
- No additional UI is needed for retention (`backend-spec.md §13A` handles expiry server-side) — if a raw media asset has been cleaned up after its retention window, the UI should degrade gracefully (show the event details without the image, not an error state).

---

## 12. Frontend Stack Notes (v1 libraries finalized — was "X or Y")

- **Map layer: Mapbox GL JS** (chosen for v1 over Leaflet — better native vector-tile performance for the marker-clustering + bbox-subscription pattern used throughout this spec, and it has first-class support for the kind of live-updating layers §8/§9 need). Leaflet remains a viable fallback only if Mapbox's pricing/tile terms become a blocker later.
- **State/data fetching: TanStack Query (React Query)** (chosen for v1 — handles the map-bounds-triggered refetching in §4/§5 and merging WebSocket messages into cached query data cleanly via its cache-update APIs).
- **Auth/routing:** role-based layouts within a single codebase, per §7 — UX convenience, not a security layer.
- **Dynamic config:** consumed once per session per §3, cached client-side.

---

## 13. Explicitly Deferred to Future Work

Matches `backend-spec.md §18` from the frontend's perspective:
- Full offline-first architecture (local write queue, background sync, conflict resolution)
- Alternative safer-route generation (route-risk *scoring* is v1; generating a different route is not)
- Real-time push of config changes (manual refresh/session-based fetch is v1)
- WebSocket message-replay on reconnect (re-fetch-and-reconcile is v1)
- Media thumbnailing/preview generation in the UI (raw asset display is v1)
- Full privacy/consent framework in the UI (blurring, opt-outs) — matches `backend-spec.md §18`

---

## 14. Immediate Next Steps

1. Build the minimal read-only map view against `/events` and the new `/config/*` endpoints together, so hazard rendering is data-driven from day one rather than hardcoded and needing rework later.
2. Implement the WebSocket bbox-subscription client (§8) alongside the map view — validates the real-time contract early, before admin tooling is built.
3. Build the pre-signed media upload flow (§6) for the manual reporting screen — using the report-specific endpoints, not the event ones — since this is required for even the simplest driver-facing feature beyond map viewing.
4. Stub the admin verification workflow against mock data while backend RBAC and ingestion stabilize, but wire it to the real `PATCH /admin/events/{id}/status` endpoint as soon as it's available, since permission enforcement lives server-side (§7) and should be tested against the real API, not assumed from UI role guards.
5. When building the route-safety overlay and any clustering view, implement the "no scored data" / "hazard intelligence, not a segment" framing (§10) from the start, rather than defaulting to treating every cluster as a scored segment and retrofitting the distinction later.
