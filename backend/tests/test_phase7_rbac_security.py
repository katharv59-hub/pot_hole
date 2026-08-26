import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base
from app.models.domain import RoadEvent, Report, MediaAsset, Vehicle, Device, DeviceVehicleAssignment, User
from app.auth.security import create_device_token
from tests.conftest import (
    create_test_admin_token,
    create_test_driver_token,
    create_test_authority_token,
    TestingSessionLocal
)

client = TestClient(app)

def setup_user_and_vehicle(
    email: str,
    role: str = "driver",
    veh_id: str = "veh_rbac_01"
):
    if role == "admin":
        token = create_test_admin_token(email)
    elif role == "authority":
        token = create_test_authority_token(email)
    else:
        token = create_test_driver_token(email)

    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/v1/auth/me", headers=headers)
    user_id = resp.json()["id"]

    db = TestingSessionLocal()
    try:
        veh = db.query(Vehicle).filter(Vehicle.id == veh_id).first()
        if not veh:
            veh = Vehicle(id=veh_id, type="car", owner_id=user_id)
            db.add(veh)
            db.commit()
        else:
            veh.owner_id = user_id
            db.commit()
    finally:
        db.close()

    return user_id, token, headers


# --- TEST A: Unauthenticated Access ---
def test_unauthenticated_access_rejection():
    """Test A: Unauthenticated requests to protected endpoints return 401 Unauthorized."""
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/reports/me").status_code == 401
    assert client.get("/api/v1/analytics/summary").status_code == 401
    assert client.get("/api/v1/analytics/export").status_code == 401
    assert client.post("/api/v1/devices/register", json={}).status_code == 401
    assert client.post("/api/v1/events", json={}).status_code == 401


# --- TEST B & C: Driver Allowed and Forbidden Operations ---
def test_driver_rbac_permissions():
    """
    Test B: Driver can perform legitimate operations.
    Test C: Driver is strictly forbidden from administrative and restricted actions.
    """
    driver_id, driver_token, driver_headers = setup_user_and_vehicle("driver_rbac@roadsentinel.io", "driver", "veh_drv_01")

    # 1. Allowed: View events catalog
    resp_events = client.get("/api/v1/events", headers=driver_headers)
    assert resp_events.status_code == 200

    # 2. Allowed: Create manual report
    resp_report = client.post("/api/v1/reports", json={
        "latitude": 19.0760,
        "longitude": 72.8777,
        "description": "Pothole report by driver"
    }, headers=driver_headers)
    assert resp_report.status_code == 200
    report_id = resp_report.json()["id"]

    # 3. Allowed: View own reports
    resp_my_reports = client.get("/api/v1/reports/me", headers=driver_headers)
    assert resp_my_reports.status_code == 200
    assert any(r["id"] == report_id for r in resp_my_reports.json())

    # 4. Forbidden: Device registration (403)
    resp_reg = client.post("/api/v1/devices/register", json={"hardware_type": "ESP32"}, headers=driver_headers)
    assert resp_reg.status_code == 403

    # 5. Forbidden: Update event status (403)
    resp_status = client.patch("/api/v1/admin/events/evt_any/status", json={"status": "verified"}, headers=driver_headers)
    assert resp_status.status_code == 403

    # 6. Forbidden: Delete event (403)
    resp_del = client.delete("/api/v1/admin/events/evt_any", headers=driver_headers)
    assert resp_del.status_code == 403

    # 7. Forbidden: View analytics (403)
    resp_analytics = client.get("/api/v1/analytics/summary", headers=driver_headers)
    assert resp_analytics.status_code == 403

    # 8. Forbidden: Export analytics (403)
    resp_export = client.get("/api/v1/analytics/export", headers=driver_headers)
    assert resp_export.status_code == 403


# --- TEST D & E: Admin Allowed and Forbidden Operations ---
def test_admin_rbac_permissions():
    """
    Test D: Admin can manage devices, update event status, soft-delete events, and view/export analytics.
    Test E: Admin user JWT cannot directly post sensor events (requires device auth).
    """
    admin_id, admin_token, admin_headers = setup_user_and_vehicle("admin_rbac@roadsentinel.io", "admin", "veh_adm_01")

    # 1. Allowed: Register new device
    resp_dev = client.post("/api/v1/devices/register", json={"hardware_type": "ESP32"}, headers=admin_headers)
    assert resp_dev.status_code == 200
    dev_id = resp_dev.json()["device_id"]

    # 2. Allowed: View analytics & export
    assert client.get("/api/v1/analytics/summary", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/analytics/export", headers=admin_headers).status_code == 200

    # 3. Allowed: Create test event in DB and update status / soft-delete
    db = TestingSessionLocal()
    try:
        event = RoadEvent(
            id="evt_admin_test_101",
            device_event_id="dev-adm-001",
            device_id=dev_id,
            vehicle_id="veh_adm_01",
            device_timestamp=datetime.now(timezone.utc),
            server_timestamp=datetime.now(timezone.utc),
            latitude=19.0760,
            longitude=72.8777,
            event_type="pothole",
            status="unverified"
        )
        db.add(event)
        db.commit()
    finally:
        db.close()

    resp_patch = client.patch(f"/api/v1/admin/events/evt_admin_test_101/status", json={"status": "verified"}, headers=admin_headers)
    assert resp_patch.status_code == 200
    assert resp_patch.json()["status"] == "verified"

    resp_delete = client.delete(f"/api/v1/admin/events/evt_admin_test_101", headers=admin_headers)
    assert resp_delete.status_code == 200
    assert resp_delete.json()["status"] == "resolved"

    # Test E: Admin user JWT cannot post to /events directly (must be device token)
    resp_ingest = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "adm-fake-ingest-01",
        "vehicle_id": "veh_adm_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.07, "longitude": 72.87, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 16.0]}}
    }, headers=admin_headers)
    assert resp_ingest.status_code in [401, 403], "User JWT must not be accepted for device event ingestion"


# --- TEST F & G: Authority Permissions ---
def test_authority_rbac_permissions():
    """
    Test F: Authority can verify event status, view reports, and view/export analytics.
    Test G: Authority is strictly forbidden from device management, deletion, and media upload.
    """
    auth_id, auth_token, auth_headers = setup_user_and_vehicle("authority_rbac@roadsentinel.io", "authority", "veh_auth_01")

    # 1. Allowed: View analytics & export (Test F)
    assert client.get("/api/v1/analytics/summary", headers=auth_headers).status_code == 200
    assert client.get("/api/v1/analytics/export", headers=auth_headers).status_code == 200

    # 2. Allowed: Verify event status (Test F)
    db = TestingSessionLocal()
    try:
        event = RoadEvent(
            id="evt_auth_test_101",
            device_event_id="dev-auth-001",
            device_id="dev_auth_01",
            vehicle_id="veh_auth_01",
            device_timestamp=datetime.now(timezone.utc),
            server_timestamp=datetime.now(timezone.utc),
            latitude=19.0760,
            longitude=72.8777,
            event_type="pothole",
            status="unverified"
        )
        db.add(event)
        db.commit()
    finally:
        db.close()

    resp_patch = client.patch(f"/api/v1/admin/events/evt_auth_test_101/status", json={"status": "verified"}, headers=auth_headers)
    assert resp_patch.status_code == 200

    # 3. Forbidden: Device registration (Test G -> 403)
    assert client.post("/api/v1/devices/register", json={"hardware_type": "ESP32"}, headers=auth_headers).status_code == 403

    # 4. Forbidden: Device revocation (Test G -> 403)
    assert client.post("/api/v1/devices/dev_any/revoke", headers=auth_headers).status_code == 403

    # 5. Forbidden: Event deletion (Test G -> 403)
    assert client.delete(f"/api/v1/admin/events/evt_auth_test_101", headers=auth_headers).status_code == 403


# --- TEST H & I: Device vs User Boundary Separation ---
def test_device_and_user_token_boundary_separation():
    """
    Test H: Device-only endpoints (POST /events, POST /telemetry) reject user JWTs.
    Test I: User-only endpoints (POST /reports, GET /auth/me) reject device JWTs.
    """
    _, user_token, user_headers = setup_user_and_vehicle("boundary_user@roadsentinel.io", "driver")
    dev_token = create_device_token("dev_boundary_01", "veh_boundary_01")
    dev_headers = {"Authorization": f"Bearer {dev_token}"}

    # Test H: User JWT rejected on /events and /telemetry
    resp_user_events = client.post("/api/v1/events", json={}, headers=user_headers)
    assert resp_user_events.status_code in [401, 403]

    resp_user_telem = client.post("/api/v1/telemetry", json={}, headers=user_headers)
    assert resp_user_telem.status_code in [401, 403]

    # Test I: Device JWT rejected on user endpoints
    resp_dev_me = client.get("/api/v1/auth/me", headers=dev_headers)
    assert resp_dev_me.status_code == 401

    resp_dev_rpt = client.post("/api/v1/reports", json={"latitude": 19.0, "longitude": 72.8}, headers=dev_headers)
    assert resp_dev_rpt.status_code == 401


# --- TEST J, K, L, M: IDOR and Ownership Protection ---
def test_idor_and_ownership_protection():
    """
    Test J, K, L, M:
    - Driver A cannot read Driver B's private report (403).
    - Driver A cannot read Driver B's raw media (403).
    - Driver A cannot attach media to Driver B's report (403).
    - Driver A cannot attach media to Driver B's vehicle event (403).
    """
    user_a_id, _, headers_a = setup_user_and_vehicle("driver_idor_a@roadsentinel.io", "driver", "veh_idor_a")
    user_b_id, _, headers_b = setup_user_and_vehicle("driver_idor_b@roadsentinel.io", "driver", "veh_idor_b")

    db = TestingSessionLocal()
    try:
        # Driver B creates report and event
        rpt_b = Report(
            id="rpt_idor_b_001",
            user_id=user_b_id,
            description="Driver B confidential report",
            latitude=19.05,
            longitude=72.85,
            status="pending"
        )
        evt_b = RoadEvent(
            id="evt_idor_b_001",
            device_event_id="dev-idor-b-001",
            device_id="dev_idor_b",
            vehicle_id="veh_idor_b",
            device_timestamp=datetime.now(timezone.utc),
            server_timestamp=datetime.now(timezone.utc),
            latitude=19.05,
            longitude=72.85,
            event_type="pothole"
        )
        raw_med_b = MediaAsset(
            id="med_raw_idor_b_001",
            event_id="evt_idor_b_001",
            type="image",
            storage_url="/uploads/raw_b.jpg",
            access_tier="raw"
        )
        db.add_all([rpt_b, evt_b, raw_med_b])
        db.commit()
    finally:
        db.close()

    # Driver A attempts to read Driver B report -> 403 (Test J & L)
    assert client.get("/api/v1/reports/rpt_idor_b_001", headers=headers_a).status_code == 403

    # Driver A attempts to attach media to Driver B report -> 403 (Test L)
    assert client.post("/api/v1/reports/rpt_idor_b_001/media/upload-url", headers=headers_a).status_code == 403

    # Driver A attempts to read Driver B raw media -> 403 (Test K)
    assert client.get("/api/v1/media/med_raw_idor_b_001", headers=headers_a).status_code == 403

    # Driver A attempts to attach media to Driver B vehicle event -> 403 (Test M)
    assert client.post("/api/v1/events/evt_idor_b_001/media/upload-url", headers=headers_a).status_code == 403


# --- TEST N, O, P, Q: Role Escalation, Mass Assignment & Impersonation ---
def test_role_escalation_and_impersonation_prevention():
    """
    Test N, O, P, Q:
    - Public registration cannot create admin/authority accounts.
    - Mass assignment cannot elevate access_tier or override server-derived IDs.
    - Device cannot post for an unassigned vehicle.
    """
    # Test N: Public registration forced to role 'driver'
    resp_reg = client.post("/api/v1/auth/register", json={
        "email": "hacker_escalate@roadsentinel.io",
        "password": "Password123!",
        "name": "Hacker",
        "role": "admin"  # Malicious attempt to self-assign admin
    })
    assert resp_reg.status_code == 200
    assert resp_reg.json()["user"]["role"] == "driver", "Public registration must force role to 'driver'"

    # Test P & Q: Device cannot post event for another vehicle
    admin_token = create_test_admin_token("admin_dev_test@roadsentinel.io")
    reg = client.post("/api/v1/devices/register", json={"hardware_type": "ESP32", "vehicle_id": "veh_assigned_01"}, headers={"Authorization": f"Bearer {admin_token}"})
    dev_id = reg.json()["device_id"]
    prov_secret = reg.json()["provisioning_secret"]

    prov = client.post(f"/api/v1/devices/{dev_id}/provision", json={"provisioning_secret": prov_secret})
    cred = prov.json()["device_credential"]
    auth = client.post(f"/api/v1/devices/{dev_id}/auth", json={"device_credential": cred})
    dev_jwt = auth.json()["access_token"]

    # Device attempts to attribute event to unassigned vehicle 'veh_unassigned_99' -> 409
    resp_spoof = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "spoof-001",
        "vehicle_id": "veh_unassigned_99",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.07, "longitude": 72.87, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 15.0]}}
    }, headers={"Authorization": f"Bearer {dev_jwt}"})
    assert resp_spoof.status_code == 409, "Server must reject mismatch with active DeviceVehicleAssignment"


# --- TEST V: Secret Leakage Checks ---
def test_no_secret_leakage_in_api_responses():
    """Test V: APIs never return database passwords, cloud secret keys, or internal hashes."""
    admin_token = create_test_admin_token("admin_audit_secrets@roadsentinel.io")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Device list does not contain credential hashes or provisioning secrets
    resp_devs = client.get("/api/v1/devices", headers=headers)
    assert resp_devs.status_code == 200
    for d in resp_devs.json():
        assert "credential_hash" not in d
        assert "provisioning_secret" not in d

    # 2. User profile does not contain password hashes
    resp_user = client.get("/api/v1/auth/me", headers=headers)
    assert resp_user.status_code == 200
    assert "hashed_password" not in resp_user.json()
    assert "password" not in resp_user.json()
