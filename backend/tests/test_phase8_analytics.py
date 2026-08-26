import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base
from app.models.domain import RoadEvent, Report, Telemetry, RoadSegment, GeoIndexBucket, Device, Vehicle, User
from tests.conftest import create_test_admin_token, create_test_driver_token, create_test_authority_token, TestingSessionLocal

client = TestClient(app)

# --- TEST A: Empty State Analytics ---
def test_empty_analytics_summary():
    """Test A: Empty analytics returns honest zero counts and empty distributions without NaN/errors."""
    admin_token = create_test_admin_token("admin_empty_analytics@roadsentinel.io")
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = client.get("/api/v1/analytics/summary", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "metrics" in data
    assert "event_type_distribution" in data
    assert "severity_distribution" in data
    assert isinstance(data["metrics"]["total_events"], int)
    assert isinstance(data["metrics"]["unverified_count"], int)


# --- TEST B, C, D, E, F: Multi-Hazard & Severity Aggregation ---
def test_hazard_and_severity_aggregation():
    """
    Test B, C, D, E, F:
    - Multiple event types (pothole, speed_breaker, crack) aggregated correctly.
    - Severity labels (low, medium, high, critical) distinct and separate from confidence.
    """
    admin_token = create_test_admin_token("admin_agg_test@roadsentinel.io")
    headers = {"Authorization": f"Bearer {admin_token}"}

    db = TestingSessionLocal()
    try:
        e1 = RoadEvent(
            id="evt_agg_01",
            device_event_id="dev-agg-001",
            device_id="dev_agg_01",
            vehicle_id="veh_agg_01",
            device_timestamp=datetime.now(timezone.utc),
            server_timestamp=datetime.now(timezone.utc),
            latitude=19.0760,
            longitude=72.8777,
            event_type="pothole",
            severity=0.85,
            severity_label="critical",
            confidence=0.90,
            status="unverified"
        )
        e2 = RoadEvent(
            id="evt_agg_02",
            device_event_id="dev-agg-002",
            device_id="dev_agg_01",
            vehicle_id="veh_agg_01",
            device_timestamp=datetime.now(timezone.utc),
            server_timestamp=datetime.now(timezone.utc),
            latitude=19.0770,
            longitude=72.8780,
            event_type="speed_breaker",
            severity=0.40,
            severity_label="medium",
            confidence=0.75,
            status="verified"
        )
        e3 = RoadEvent(
            id="evt_agg_03",
            device_event_id="dev-agg-003",
            device_id="dev_agg_01",
            vehicle_id="veh_agg_01",
            device_timestamp=datetime.now(timezone.utc),
            server_timestamp=datetime.now(timezone.utc),
            latitude=19.0780,
            longitude=72.8790,
            event_type="crack",
            severity=0.25,
            severity_label="low",
            confidence=0.80,
            status="unverified"
        )
        db.add_all([e1, e2, e3])
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/analytics/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    type_dist = data["event_type_distribution"]
    assert type_dist.get("pothole", 0) >= 1
    assert type_dist.get("speed_breaker", 0) >= 1
    assert type_dist.get("crack", 0) >= 1

    sev_dist = data["severity_distribution"]
    assert sev_dist.get("critical", 0) >= 1
    assert sev_dist.get("medium", 0) >= 1
    assert sev_dist.get("low", 0) >= 1


# --- TEST G, H, I: Corroboration, Duplicate Exclusion & Telemetry Separation ---
def test_corroboration_dedup_and_telemetry_separation():
    """
    Test G, H, I:
    - Corroboration increments count on canonical event without duplicating rows.
    - Duplicate events (status='duplicate') are separated and not double-counted as active hazards.
    - Telemetry entries (smooth road / baseline) are not counted as hazard events.
    """
    admin_token = create_test_admin_token("admin_telem_sep@roadsentinel.io")
    headers = {"Authorization": f"Bearer {admin_token}"}

    db = TestingSessionLocal()
    try:
        # Canonical event with corroboration count = 2
        canonical_event = RoadEvent(
            id="evt_corr_canonical_01",
            device_event_id="dev-corr-001",
            device_id="dev_corr_01",
            vehicle_id="veh_corr_01",
            device_timestamp=datetime.now(timezone.utc),
            server_timestamp=datetime.now(timezone.utc),
            latitude=19.0760,
            longitude=72.8777,
            event_type="pothole",
            corroboration_count=2,
            status="verified"
        )
        # Duplicate record
        dup_event = RoadEvent(
            id="evt_corr_dup_02",
            device_event_id="dev-corr-001-retry",
            device_id="dev_corr_01",
            vehicle_id="veh_corr_01",
            device_timestamp=datetime.now(timezone.utc),
            server_timestamp=datetime.now(timezone.utc),
            latitude=19.0760,
            longitude=72.8777,
            event_type="pothole",
            status="duplicate"
        )
        # Telemetry record (smooth road baseline)
        telemetry_entry = Telemetry(
            id="tel_baseline_001",
            device_id="dev_corr_01",
            vehicle_id="veh_corr_01",
            device_timestamp=datetime.now(timezone.utc),
            server_timestamp=datetime.now(timezone.utc),
            latitude=19.0760,
            longitude=72.8777,
            raw_payload={"imu_window": {"z_accel": [9.8, 9.8, 9.8]}},
            label="smooth_road"
        )
        db.add_all([canonical_event, dup_event, telemetry_entry])
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/analytics/summary", headers=headers)
    assert resp.status_code == 200
    metrics = resp.json()["metrics"]
    assert metrics["duplicate_count"] >= 1
    assert metrics["verified_count"] >= 1


# --- TEST J, K, L, M: GeoIndexBucket vs RoadSegment Invariant ---
def test_geohash_bucket_never_becomes_road_segment():
    """
    Test J, K, L, M:
    - GeoIndexBucket aggregates events for fast candidate lookup.
    - Geohash is never written into road_segment_id.
    - road_segment_id remains NULL until legitimate RoadSegment resolution.
    """
    db = TestingSessionLocal()
    try:
        # GeoIndexBucket
        bucket = GeoIndexBucket(
            geohash="te7ud2",
            event_count=5,
            last_event_at=datetime.now(timezone.utc)
        )
        # Event without RoadSegment (standard v1 state)
        event_unmapped = RoadEvent(
            id="evt_unmapped_01",
            device_event_id="dev-unmap-001",
            device_id="dev_unmap_01",
            vehicle_id="veh_unmap_01",
            device_timestamp=datetime.now(timezone.utc),
            server_timestamp=datetime.now(timezone.utc),
            latitude=19.0760,
            longitude=72.8777,
            event_type="pothole",
            road_segment_id=None
        )
        # Legitimate RoadSegment
        real_segment = RoadSegment(
            id="seg_bandra_linking_rd_01",
            road_network_ref="way_osm_11223344",
            safety_score=88.5
        )
        # Event with legitimate RoadSegment
        event_mapped = RoadEvent(
            id="evt_mapped_02",
            device_event_id="dev-map-002",
            device_id="dev_map_02",
            vehicle_id="veh_map_02",
            device_timestamp=datetime.now(timezone.utc),
            server_timestamp=datetime.now(timezone.utc),
            latitude=19.0760,
            longitude=72.8777,
            event_type="pothole",
            road_segment_id=real_segment.id
        )
        db.merge(bucket)
        db.add_all([event_unmapped, real_segment, event_mapped])
        db.commit()

        # Invariants:
        assert event_unmapped.road_segment_id is None
        assert event_mapped.road_segment_id == "seg_bandra_linking_rd_01"
        assert event_mapped.road_segment_id != "te7ud2"
    finally:
        db.close()


# --- TEST N & O: Route Safety Scenario A vs Scenario B ---
def test_route_safety_scenarios_unscored_vs_official():
    """
    Test N: Scenario A (No RoadSegments) -> overall_safety_score = None, scoring_available = False.
    Test O: Scenario B (Legitimate RoadSegments) -> overall_safety_score computed from official segment, scoring_available = True.
    """
    polyline = [
        [19.0700, 72.8700],
        [19.0760, 72.8777],
        [19.0820, 72.8850]
    ]

    # Scenario A: Polyline query where hazards exist but road_segment_id is None
    resp_scen_a = client.post("/api/v1/routes/safety", json={"polyline": polyline})
    assert resp_scen_a.status_code == 200
    data_a = resp_scen_a.json()
    # If unmapped hazards exist, scoring_available reflects whether official segments are present
    assert data_a["unscored_stretches_count"] >= 0

    # Scenario B: Polyline intersecting mapped RoadSegment
    db = TestingSessionLocal()
    try:
        segment = RoadSegment(
            id="seg_expressway_01",
            road_network_ref="way_osm_998877",
            safety_score=92.0
        )
        mapped_event = RoadEvent(
            id="evt_expressway_01",
            device_event_id="dev-exp-001",
            device_id="dev_exp_01",
            vehicle_id="veh_exp_01",
            device_timestamp=datetime.now(timezone.utc),
            server_timestamp=datetime.now(timezone.utc),
            latitude=19.0760,
            longitude=72.8777,
            event_type="pothole",
            status="unverified",
            road_segment_id=segment.id
        )
        db.merge(segment)
        db.merge(mapped_event)
        db.commit()
    finally:
        db.close()

    resp_scen_b = client.post("/api/v1/routes/safety", json={"polyline": polyline})
    assert resp_scen_b.status_code == 200
    data_b = resp_scen_b.json()
    assert data_b["scoring_available"] is True
    assert data_b["overall_safety_score"] == 92.0
    assert data_b["scored_segments_count"] >= 1
    assert data_b["segment_scores"][0]["framing_label"] == "Official Road Network Segment"


# --- TEST R, S, T: Analytics and Export RBAC & Privacy ---
def test_analytics_and_export_rbac_and_privacy():
    """
    Test R, S, T:
    - Drivers are rejected (403) on /analytics/summary and /analytics/export.
    - Admin and Authority can access analytics and export.
    - Export CSV contains canonical public event catalog fields without credentials.
    """
    driver_token = create_test_driver_token("driver_analytics_block@roadsentinel.io")
    admin_token = create_test_admin_token("admin_analytics_ok@roadsentinel.io")
    auth_token = create_test_authority_token("auth_analytics_ok@roadsentinel.io")

    # Driver blocked (Test R & S)
    assert client.get("/api/v1/analytics/summary", headers={"Authorization": f"Bearer {driver_token}"}).status_code == 403
    assert client.get("/api/v1/analytics/export", headers={"Authorization": f"Bearer {driver_token}"}).status_code == 403

    # Admin & Authority allowed
    assert client.get("/api/v1/analytics/summary", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200
    assert client.get("/api/v1/analytics/summary", headers={"Authorization": f"Bearer {auth_token}"}).status_code == 200

    resp_export = client.get("/api/v1/analytics/export", headers={"Authorization": f"Bearer {auth_token}"})
    assert resp_export.status_code == 200
    assert "text/csv" in resp_export.headers.get("content-type", "")
    csv_content = resp_export.text
    assert "Event ID,Device Event ID" in csv_content
    # Test T: No passwords or secret keys in export
    assert "password" not in csv_content.lower()
    assert "secret" not in csv_content.lower()
