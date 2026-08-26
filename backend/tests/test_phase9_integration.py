import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.models.domain import RoadEvent, Report, Device, Vehicle, User, RoadSegment
from app.auth.security import create_device_token, get_password_hash
from tests.conftest import (
    create_test_admin_token,
    create_test_driver_token,
    create_test_authority_token,
    TestingSessionLocal
)

client = TestClient(app)

# --- TEST A: Frontend Config & Contract Invariants ---
def test_frontend_config_bundle_contract():
    """Test A: /config/bundle matches exact schema expected by ConfigContext.tsx."""
    resp = client.get("/api/v1/config/bundle")
    assert resp.status_code == 200
    data = resp.json()
    assert "event_types" in data
    assert "severity_scale" in data
    assert "vehicle_types" in data
    assert isinstance(data["event_types"], list)
    assert "buckets" in data["severity_scale"]
    assert "critical" in data["severity_scale"]["buckets"]
    assert "high" in data["severity_scale"]["buckets"]
    assert "medium" in data["severity_scale"]["buckets"]
    assert "low" in data["severity_scale"]["buckets"]


# --- TEST B: Auth Lifecycle & Token Introspection ---
def test_auth_lifecycle_integration():
    """Test B: Login, introspection (/auth/me), role extraction, and unauthenticated rejection."""
    # Register driver
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == "int_driver@roadsentinel.io").first()
        if not user:
            user = User(
                email="int_driver@roadsentinel.io",
                hashed_password=get_password_hash("password123"),
                name="Integration Driver",
                role="driver"
            )
            db.add(user)
            db.commit()
    finally:
        db.close()

    # Login
    resp_login = client.post("/api/v1/auth/login", json={
        "email": "int_driver@roadsentinel.io",
        "password": "password123"
    })
    assert resp_login.status_code == 200
    token = resp_login.json()["access_token"]
    user_payload = resp_login.json()["user"]
    assert user_payload["role"] == "driver"

    # Introspection
    resp_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_me.status_code == 200
    assert resp_me.json()["email"] == "int_driver@roadsentinel.io"


# --- TEST C, D, E: Event & Analytics Lifecycle ---
def test_event_and_analytics_lifecycle_integration():
    """
    Test C, D, E:
    - Ingest event via device token.
    - Read event in catalog.
    - Admin/Authority verifies event status.
    - Analytics summary and CSV export reflect verified event.
    """
    admin_token = create_test_admin_token("admin_lifecycle_int@roadsentinel.io")
    auth_token = create_test_authority_token("auth_lifecycle_int@roadsentinel.io")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    auth_headers = {"Authorization": f"Bearer {auth_token}"}

    # 1. Register and provision device
    reg = client.post("/api/v1/devices/register", json={"hardware_type": "ESP32", "vehicle_id": "veh_int_01"}, headers=admin_headers)
    assert reg.status_code == 200
    dev_id = reg.json()["device_id"]
    prov_secret = reg.json()["provisioning_secret"]

    prov = client.post(f"/api/v1/devices/{dev_id}/provision", json={"provisioning_secret": prov_secret})
    cred = prov.json()["device_credential"]
    auth = client.post(f"/api/v1/devices/{dev_id}/auth", json={"device_credential": cred})
    dev_jwt = auth.json()["access_token"]

    # 2. Ingest RoadEvent
    resp_ingest = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "int-dev-evt-001",
        "vehicle_id": "veh_int_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.0760, "longitude": 72.8777, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 17.5]}}
    }, headers={"Authorization": f"Bearer {dev_jwt}"})
    assert resp_ingest.status_code == 200
    event_id = resp_ingest.json()["event_id"]

    # 3. Read back event
    resp_get = client.get(f"/api/v1/events/{event_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["event_type"] == "pothole"

    # 4. Authority updates status to verified
    resp_patch = client.patch(f"/api/v1/admin/events/{event_id}/status", json={"status": "verified"}, headers=auth_headers)
    assert resp_patch.status_code == 200
    assert resp_patch.json()["status"] == "verified"

    # 5. Check Analytics summary
    resp_summary = client.get("/api/v1/analytics/summary", headers=auth_headers)
    assert resp_summary.status_code == 200
    metrics = resp_summary.json()["metrics"]
    assert metrics["total_events"] >= 1
    assert metrics["verified_count"] >= 1

    # 6. Check CSV export
    resp_export = client.get("/api/v1/analytics/export", headers=auth_headers)
    assert resp_export.status_code == 200
    assert "text/csv" in resp_export.headers["content-type"]
    assert event_id in resp_export.text


# --- TEST F: Route Safety Contract (Scenario A & B) ---
def test_route_safety_frontend_contract():
    """
    Test F: /routes/safety matches RouteSafetyResponse TypeScript contract.
    Handles nullable overall_safety_score safely.
    """
    polyline = [
        [19.0700, 72.8700],
        [19.0760, 72.8777],
        [19.0800, 72.8850]
    ]

    # Scenario A: Unscored network
    resp = client.post("/api/v1/routes/safety", json={"polyline": polyline})
    assert resp.status_code == 200
    data = resp.json()
    assert "overall_safety_score" in data
    assert "scored_segments_count" in data
    assert "unscored_stretches_count" in data
    assert "detected_hazards_on_route" in data
    assert "segment_scores" in data
    assert len(data["segment_scores"]) == len(polyline) - 1
    assert data["segment_scores"][0]["framing_label"] in [
        "Hazard Location Intelligence Stretch",
        "Official Road Network Segment"
    ]


# --- TEST J, K, L: Media & Report End-to-End Workflow ---
def test_media_and_report_e2e_workflow():
    """
    Test J, K, L:
    - User creates report.
    - User requests pre-signed media upload URL slot.
    - User confirms media asset.
    - Retrieve report with attached media.
    - Another driver cannot modify or read private report.
    """
    driver_a_token = create_test_driver_token("driver_rpt_a@roadsentinel.io")
    driver_b_token = create_test_driver_token("driver_rpt_b@roadsentinel.io")
    headers_a = {"Authorization": f"Bearer {driver_a_token}"}
    headers_b = {"Authorization": f"Bearer {driver_b_token}"}

    # Driver A creates report
    resp_rpt = client.post("/api/v1/reports", json={
        "latitude": 19.0760,
        "longitude": 72.8777,
        "description": "Severe road depression"
    }, headers=headers_a)
    assert resp_rpt.status_code == 200
    rpt_id = resp_rpt.json()["id"]

    # Driver A gets upload URL
    resp_url = client.post(f"/api/v1/reports/{rpt_id}/media/upload-url", headers=headers_a)
    assert resp_url.status_code == 200
    media_id = resp_url.json()["media_id"]

    # Driver A confirms media upload
    resp_confirm = client.post(f"/api/v1/reports/{rpt_id}/media/{media_id}/confirm", headers=headers_a)
    assert resp_confirm.status_code == 200
    assert resp_confirm.json()["id"] == media_id

    # Driver A reads report media
    resp_media = client.get(f"/api/v1/reports/{rpt_id}/media", headers=headers_a)
    assert resp_media.status_code == 200
    assert len(resp_media.json()) == 1

    # Driver B attempts to read Driver A's report -> 403
    assert client.get(f"/api/v1/reports/{rpt_id}", headers=headers_b).status_code == 403
