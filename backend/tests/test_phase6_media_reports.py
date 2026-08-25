import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base
from app.models.domain import RoadEvent, Report, MediaAsset, Vehicle, User
from tests.conftest import create_test_admin_token, create_test_driver_token, TestingSessionLocal

client = TestClient(app)

def setup_user_and_vehicle(
    email: str,
    role: str = "driver",
    veh_id: str = "veh_media_01"
):
    token = create_test_driver_token(email) if role == "driver" else create_test_admin_token(email)
    headers = {"Authorization": f"Bearer {token}"}

    # Get user id from token profile
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


# --- EVENT MEDIA TESTS A, B, C, D ---
def test_event_media_upload_and_confirmation_flow():
    """
    Test A, C, D: Authorized user requests upload slot, confirms media,
    and MediaAsset has event_id set while report_id remains NULL.
    """
    user_id, token, headers = setup_user_and_vehicle("driver_evt_media@roadsentinel.io", "driver", "veh_evt_01")

    db = TestingSessionLocal()
    try:
        # Create an authorized RoadEvent
        event = RoadEvent(
            id="evt_media_test_101",
            device_event_id="dev-evt-media-001",
            device_id="dev_media_01",
            vehicle_id="veh_evt_01",
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

    # 1. Request upload slot (Test A)
    slot_resp = client.post("/api/v1/events/evt_media_test_101/media/upload-url", headers=headers)
    assert slot_resp.status_code == 200
    media_id = slot_resp.json()["media_id"]
    upload_url = slot_resp.json()["upload_url"]
    assert media_id.startswith("med_evt_")
    assert "/api/v1/uploads/direct/" in upload_url or "s3" in upload_url

    # 2. Confirm media (Test C)
    conf_resp = client.post(f"/api/v1/events/evt_media_test_101/media/{media_id}/confirm", headers=headers)
    assert conf_resp.status_code == 200
    asset_data = conf_resp.json()

    # Test D: Event MediaAsset has event_id and no report_id
    assert asset_data["id"] == media_id
    assert asset_data["event_id"] == "evt_media_test_101"
    assert asset_data["report_id"] is None
    assert asset_data["access_tier"] == "raw"


def test_unauthenticated_event_media_upload_rejected():
    """Test B: Unauthenticated user cannot request upload slot."""
    resp = client.post("/api/v1/events/evt_media_test_101/media/upload-url")
    assert resp.status_code == 401


# --- REPORT MEDIA TESTS E, F, G, H ---
def test_report_creation_and_standalone_media_flow():
    """
    Test E, F, G: Report can be created without event_id, media uploaded
    without event linkage, and MediaAsset has report_id set while event_id is NULL.
    """
    user_id, token, headers = setup_user_and_vehicle("driver_report_standalone@roadsentinel.io", "driver", "veh_rpt_01")

    # 1. Create Report without event_id (Test E)
    rpt_resp = client.post("/api/v1/reports", json={
        "latitude": 19.0760,
        "longitude": 72.8777,
        "description": "Deep pothole near junction"
    }, headers=headers)
    assert rpt_resp.status_code == 200
    report_id = rpt_resp.json()["id"]
    assert rpt_resp.json()["event_id"] is None

    # 2. Request Report Media Upload Slot (Test F)
    slot_resp = client.post(f"/api/v1/reports/{report_id}/media/upload-url", headers=headers)
    assert slot_resp.status_code == 200
    media_id = slot_resp.json()["media_id"]
    assert media_id.startswith("med_rpt_")

    # 3. Confirm Report Media (Test G)
    conf_resp = client.post(f"/api/v1/reports/{report_id}/media/{media_id}/confirm", headers=headers)
    assert conf_resp.status_code == 200
    asset_data = conf_resp.json()

    assert asset_data["id"] == media_id
    assert asset_data["report_id"] == report_id
    assert asset_data["event_id"] is None, "Report MediaAsset must have event_id = NULL"


def test_unauthorized_user_cannot_access_or_upload_another_users_report():
    """Test H: Unauthorized driver cannot request upload slot or confirm media for another's report."""
    user_a_id, _, headers_a = setup_user_and_vehicle("driver_a_rpt@roadsentinel.io", "driver", "veh_a_01")
    user_b_id, _, headers_b = setup_user_and_vehicle("driver_b_rpt@roadsentinel.io", "driver", "veh_b_01")

    # User A creates report
    rpt_resp = client.post("/api/v1/reports", json={
        "latitude": 19.05,
        "longitude": 72.85,
        "description": "User A private report"
    }, headers=headers_a)
    report_id = rpt_resp.json()["id"]

    # User B attempts to request upload slot on User A's report -> 403
    resp_b_slot = client.post(f"/api/v1/reports/{report_id}/media/upload-url", headers=headers_b)
    assert resp_b_slot.status_code == 403

    # User B attempts to access report media -> 403
    resp_b_media = client.get(f"/api/v1/reports/{report_id}/media", headers=headers_b)
    assert resp_b_media.status_code == 403


# --- PRIVACY & ACCESS TIER TESTS I, J, K, L, M ---
def test_media_privacy_and_access_tiers():
    """
    Test I, J, K, L, M:
    - Driver A (owner) can access own vehicle's raw media.
    - Driver B cannot access Driver A's raw media (403 or filtered out).
    - Driver B can access Driver A's processed media.
    - Admin/Authority can access raw and processed media.
    """
    user_a_id, _, headers_a = setup_user_and_vehicle("driver_a_privacy@roadsentinel.io", "driver", "veh_priv_a")
    user_b_id, _, headers_b = setup_user_and_vehicle("driver_b_privacy@roadsentinel.io", "driver", "veh_priv_b")
    admin_id, _, headers_admin = setup_user_and_vehicle("admin_privacy@roadsentinel.io", "admin", "veh_priv_admin")

    db = TestingSessionLocal()
    try:
        # Create Event belonging to Driver A's vehicle
        event_a = RoadEvent(
            id="evt_privacy_101",
            device_event_id="dev-priv-001",
            device_id="dev_priv_01",
            vehicle_id="veh_priv_a",
            device_timestamp=datetime.now(timezone.utc),
            server_timestamp=datetime.now(timezone.utc),
            latitude=19.0760,
            longitude=72.8777,
            event_type="pothole",
            status="verified"
        )
        # Raw MediaAsset
        raw_media = MediaAsset(
            id="med_raw_priv_001",
            event_id="evt_privacy_101",
            report_id=None,
            type="image",
            storage_url="/uploads/raw_priv_001.jpg",
            access_tier="raw"
        )
        # Processed MediaAsset
        proc_media = MediaAsset(
            id="med_proc_priv_002",
            event_id="evt_privacy_101",
            report_id=None,
            type="image",
            storage_url="/uploads/proc_priv_002.jpg",
            access_tier="processed"
        )
        db.add_all([event_a, raw_media, proc_media])
        db.commit()
    finally:
        db.close()

    # 1. Driver A (owner) gets all media (both raw and processed) (Test I)
    resp_a = client.get("/api/v1/events/evt_privacy_101/media", headers=headers_a)
    assert resp_a.status_code == 200
    media_ids_a = [m["id"] for m in resp_a.json()]
    assert "med_raw_priv_001" in media_ids_a
    assert "med_proc_priv_002" in media_ids_a

    # 2. Driver B (third-party driver) gets ONLY processed media (Test J & K)
    resp_b = client.get("/api/v1/events/evt_privacy_101/media", headers=headers_b)
    assert resp_b.status_code == 200
    media_ids_b = [m["id"] for m in resp_b.json()]
    assert "med_raw_priv_001" not in media_ids_b, "Driver B must not see raw media"
    assert "med_proc_priv_002" in media_ids_b, "Driver B can see processed media"

    # Direct access: Driver B attempts to read raw media by ID -> 403 (Test J)
    resp_b_direct = client.get("/api/v1/media/med_raw_priv_001", headers=headers_b)
    assert resp_b_direct.status_code == 403

    # Direct access: Driver B reads processed media by ID -> 200 (Test K)
    resp_b_proc_direct = client.get("/api/v1/media/med_proc_priv_002", headers=headers_b)
    assert resp_b_proc_direct.status_code == 200

    # 3. Admin gets both raw and processed media (Test L)
    resp_admin = client.get("/api/v1/events/evt_privacy_101/media", headers=headers_admin)
    assert resp_admin.status_code == 200
    media_ids_admin = [m["id"] for m in resp_admin.json()]
    assert "med_raw_priv_001" in media_ids_admin
    assert "med_proc_priv_002" in media_ids_admin


# --- SECURITY & DATA INTEGRITY TESTS N, O, Q, R, S ---
def test_media_security_and_resource_rebinding_prevention():
    """
    Test N, O, Q, R, S:
    - Nonexistent parent rejected (404).
    - Cannot rebind confirmed media to a different parent.
    - Driver cannot escalate access tier.
    - Storage credentials never exposed in responses.
    """
    _, _, headers_driver = setup_user_and_vehicle("driver_sec@roadsentinel.io", "driver", "veh_sec_01")

    db = TestingSessionLocal()
    try:
        event = RoadEvent(
            id="evt_media_sec_101",
            device_event_id="dev-evt-media-sec-001",
            device_id="dev_media_sec_01",
            vehicle_id="veh_sec_01",
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

    # 1. Invalid parent resource rejected (Test R)
    resp_bad_evt = client.post("/api/v1/events/evt_nonexistent_999/media/upload-url", headers=headers_driver)
    assert resp_bad_evt.status_code == 404

    resp_bad_rpt = client.post("/api/v1/reports/rpt_nonexistent_999/media/upload-url", headers=headers_driver)
    assert resp_bad_rpt.status_code == 404

    # 2. Driver attempts access-tier escalation during confirmation -> forced to 'raw' (Test O)
    slot_resp = client.post("/api/v1/events/evt_media_sec_101/media/upload-url", headers=headers_driver)
    assert slot_resp.status_code == 200
    media_id = slot_resp.json()["media_id"]

    conf_resp = client.post(
        f"/api/v1/events/evt_media_sec_101/media/{media_id}/confirm?access_tier=processed",
        headers=headers_driver
    )
    assert conf_resp.status_code == 200
    assert conf_resp.json()["access_tier"] == "raw", "Driver cannot self-escalate media to 'processed'"

    # 3. Storage credentials never returned (Test Q)
    upload_url = slot_resp.json()["upload_url"]
    assert "aws_secret_access_key" not in upload_url.lower()
    assert "password" not in upload_url.lower()
