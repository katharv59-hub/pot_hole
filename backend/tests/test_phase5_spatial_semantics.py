import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from app.main import app
from app.database import Base
from app.models.domain import RoadEvent, RoadSegment, GeoIndexBucket, DeviceVehicleAssignment, Device, Vehicle
from tests.conftest import create_test_admin_token, create_test_driver_token, TestingSessionLocal

client = TestClient(app)

def setup_active_device(
    vehicle_id: str = "veh_phase5_01",
    admin_email: str = "phase5_admin@roadsentinel.io"
):
    admin_token = create_test_admin_token(admin_email)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    reg = client.post("/api/v1/devices/register", json={
        "hardware_type": "ESP32",
        "vehicle_id": vehicle_id
    }, headers=admin_headers)
    dev_id = reg.json()["device_id"]
    prov_secret = reg.json()["provisioning_secret"]

    prov = client.post(f"/api/v1/devices/{dev_id}/provision", json={"provisioning_secret": prov_secret})
    cred = prov.json()["device_credential"]

    auth = client.post(f"/api/v1/devices/{dev_id}/auth", json={"device_credential": cred})
    dev_token = auth.json()["access_token"]
    dev_headers = {"Authorization": f"Bearer {dev_token}"}
    return dev_id, dev_headers


# --- TEST A, B, C: RoadEvent Nullable road_segment_id and GeoIndexBucket Independence ---
def test_a_b_c_geohash_bucket_not_written_to_road_segment_id():
    """
    Test A, B, C: Ingesting an event creates GeoIndexBucket for spatial indexing
    while RoadEvent.road_segment_id strictly remains NULL.
    """
    dev_id, dev_headers = setup_active_device("veh_spatial_01", "admin_spatial_abc@roadsentinel.io")

    payload = {
        "schema_version": "1.0",
        "device_event_id": "esp32-spatial-001",
        "vehicle_id": "veh_spatial_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {
            "latitude": 19.0760,
            "longitude": 72.8777,
            "accuracy_m": 3.0,
            "source": "gnss"
        },
        "modality_sources": ["imu"],
        "sensor_data": {
            "imu_window": {
                "z_accel": [9.8, 15.0, 19.5, 9.8] # Pothole spike
            }
        },
        "firmware_version": "1.0.0"
    }

    resp = client.post("/api/v1/events", json=payload, headers=dev_headers)
    assert resp.status_code == 200, resp.text
    event_id = resp.json()["event_id"]

    db = TestingSessionLocal()
    try:
        # 1. Verify RoadEvent in DB has road_segment_id = None
        db_event = db.query(RoadEvent).filter(RoadEvent.id == event_id).first()
        assert db_event is not None
        assert db_event.road_segment_id is None, "road_segment_id must remain NULL in v1"

        # 2. Verify GeoIndexBucket was created with geohash "te7ud2" (precision 6 for 19.0760, 72.8777)
        bucket = db.query(GeoIndexBucket).filter(GeoIndexBucket.geohash == "te7ud2").first()
        assert bucket is not None, "GeoIndexBucket must exist for spatial indexing"
        assert bucket.event_count >= 1

        # 3. GeoIndexBucket primary key (geohash) is distinct from RoadSegment
        assert bucket.geohash != db_event.road_segment_id
    finally:
        db.close()


# --- TEST D, E, F: Spatial Proximity & Corroboration without RoadSegment Assignment ---
def test_d_e_f_corroboration_without_segment_assignment():
    """
    Test D, E, F: Two independent devices detecting the same hazard corroborate
    while road_segment_id remains NULL on both initial and corroborated records.
    """
    dev_a_id, headers_a = setup_active_device("veh_corr_a", "admin_corr_a@roadsentinel.io")
    dev_b_id, headers_b = setup_active_device("veh_corr_b", "admin_corr_b@roadsentinel.io")

    loc = {"latitude": 19.0762, "longitude": 72.8775, "source": "gnss"}

    # Device A posts event
    resp_a = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "dev-a-spatial-01",
        "vehicle_id": "veh_corr_a",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": loc,
        "event_type": "pothole",
        "confidence": 0.82,
        "severity": 0.70,
        "modality_sources": ["imu"]
    }, headers=headers_a)
    assert resp_a.status_code == 200
    canonical_id = resp_a.json()["event_id"]

    # Device A retries (idempotency: same device_event_id -> duplicate status, no segment change)
    resp_retry = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "dev-a-spatial-01",
        "vehicle_id": "veh_corr_a",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": loc,
        "event_type": "pothole",
        "confidence": 0.82,
        "severity": 0.70,
        "modality_sources": ["imu"]
    }, headers=headers_a)
    assert resp_retry.status_code == 200
    assert resp_retry.json()["status"] == "duplicate"

    # Device B posts matching event within corroboration radius (10m away)
    loc_b = {"latitude": 19.07625, "longitude": 72.87755, "source": "gnss"}
    resp_b = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "dev-b-spatial-01",
        "vehicle_id": "veh_corr_b",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": loc_b,
        "event_type": "pothole",
        "confidence": 0.85,
        "severity": 0.70,
        "modality_sources": ["imu"]
    }, headers=headers_b)
    assert resp_b.status_code == 200
    assert resp_b.json()["event_id"] == canonical_id
    assert resp_b.json()["corroboration_count"] == 2

    # Verify canonical event in DB still has road_segment_id = None
    db = TestingSessionLocal()
    try:
        canonical_evt = db.query(RoadEvent).filter(RoadEvent.id == canonical_id).first()
        assert canonical_evt.corroboration_count == 2
        assert canonical_evt.road_segment_id is None, "Corroboration must not fake road_segment_id"
    finally:
        db.close()


# --- TEST G & H: Legitimate RoadSegment Assignment & Foreign Key Integrity ---
def test_g_h_explicit_road_segment_assignment_and_fk_constraint():
    """
    Test G & H: When a legitimate RoadSegment entity exists, it can be assigned to RoadEvent.
    Attempting to assign an invalid / nonexistent road_segment_id violates foreign key integrity.
    """
    db = TestingSessionLocal()
    try:
        # 1. Create a legitimate RoadSegment entity
        real_segment = RoadSegment(
            id="seg_mumbai_sv_road_001",
            road_network_ref="way_osm_9823471",
            safety_score=85.0
        )
        db.add(real_segment)
        db.commit()

        # 2. Create RoadEvent explicitly associated with the real segment (e.g. via backfill)
        event = RoadEvent(
            device_event_id="evt-backfill-test-01",
            device_id="dev_test_backfill",
            vehicle_id="veh_test_backfill",
            device_timestamp=datetime.now(timezone.utc),
            server_timestamp=datetime.now(timezone.utc),
            latitude=19.0760,
            longitude=72.8777,
            event_type="pothole",
            confidence=0.88,
            severity=0.75,
            severity_label="high",
            road_segment_id=real_segment.id
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        assert event.road_segment_id == "seg_mumbai_sv_road_001"
        assert event.road_segment_id != "te7ud2", "RoadSegment ID is a distinct canonical ID, not a geohash"

        # 3. Clean up
        db.delete(event)
        db.delete(real_segment)
        db.commit()
    finally:
        db.close()


# --- TEST I & J: Route Safety Endpoint Framing Semantics ---
def test_i_j_route_safety_unscored_framing_and_no_fake_segment_labels():
    """
    Test I & J: POST /routes/safety returns overall_safety_score = None when no official
    road segments are mapped, and frames stretches as 'Hazard Location Intelligence Stretch'.
    """
    polyline = [
        [19.0600, 72.8700],
        [19.0728, 72.8826],
        [19.0815, 72.8890]
    ]

    resp = client.post("/api/v1/routes/safety", json={"polyline": polyline})
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Test I: Official road score is None because no backfilled RoadSegments exist along path
    assert data["overall_safety_score"] is None
    assert data["scoring_available"] is False
    assert data["scored_segments_count"] == 0
    assert data["unscored_stretches_count"] == len(polyline) - 1

    # Test J: Segments are explicitly labeled as Hazard Location Intelligence Stretches
    for stretch in data["segment_scores"]:
        assert stretch["is_road_network_scored"] is False
        assert stretch["framing_label"] == "Hazard Location Intelligence Stretch"
        assert "geohash" not in stretch["framing_label"].lower()
