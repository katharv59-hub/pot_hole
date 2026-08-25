import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base
from app.models.domain import RoadEvent, Telemetry, MLPrediction, DeviceVehicleAssignment, Device
from tests.conftest import create_test_admin_token, create_test_driver_token, TestingSessionLocal

client = TestClient(app)

def setup_active_device_and_vehicle(
    vehicle_id: str = "veh_active_01",
    admin_email: str = "phase3_admin@roadsentinel.io",
    hardware_type: str = "ESP32",
    firmware_version: str = "1.0.0"
):
    """Helper to register, provision, and authenticate an active device with assigned vehicle."""
    admin_token = create_test_admin_token(admin_email)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    reg_resp = client.post("/api/v1/devices/register", json={
        "hardware_type": hardware_type,
        "firmware_version": firmware_version,
        "vehicle_id": vehicle_id
    }, headers=admin_headers)
    assert reg_resp.status_code == 200
    dev_id = reg_resp.json()["device_id"]
    prov_secret = reg_resp.json()["provisioning_secret"]

    prov_resp = client.post(f"/api/v1/devices/{dev_id}/provision", json={
        "provisioning_secret": prov_secret
    })
    assert prov_resp.status_code == 200
    cred = prov_resp.json()["device_credential"]

    auth_resp = client.post(f"/api/v1/devices/{dev_id}/auth", json={
        "device_credential": cred
    })
    assert auth_resp.status_code == 200
    dev_token = auth_resp.json()["access_token"]
    dev_headers = {"Authorization": f"Bearer {dev_token}"}

    return dev_id, prov_secret, cred, dev_token, dev_headers


# --- TEST A & B: Device Provisioning & Single-Use Secret ---
def test_a_b_device_provisioning_and_secret_single_use():
    """Test A & B: Device registers, provisions, and secret cannot be reused."""
    admin_token = create_test_admin_token("test_ab_admin@roadsentinel.io")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    reg = client.post("/api/v1/devices/register", json={
        "hardware_type": "ESP32",
        "vehicle_id": "veh_ab_01"
    }, headers=admin_headers)
    assert reg.status_code == 200
    dev_id = reg.json()["device_id"]
    prov_secret = reg.json()["provisioning_secret"]

    # Test A: Successful provisioning
    prov = client.post(f"/api/v1/devices/{dev_id}/provision", json={"provisioning_secret": prov_secret})
    assert prov.status_code == 200
    assert "device_credential" in prov.json()
    assert prov.json()["status"] == "active"

    # Test B: Provisioning secret reuse fails with 401
    reuse = client.post(f"/api/v1/devices/{dev_id}/provision", json={"provisioning_secret": prov_secret})
    assert reuse.status_code == 401


# --- TEST C: Device Auth Returns Usable JWT ---
def test_c_device_auth_token_issuance():
    """Test C: Device credential exchange returns short-lived device JWT."""
    dev_id, _, cred, token, headers = setup_active_device_and_vehicle(
        vehicle_id="veh_c_01",
        admin_email="test_c_admin@roadsentinel.io"
    )
    assert bool(token) is True
    assert headers["Authorization"].startswith("Bearer ")


# --- TEST D & E: Auth Rejection Rules for POST /events ---
def test_d_e_event_ingestion_auth_guards():
    """Test D & E: POST /events rejects missing auth, bad token, and driver/user JWT."""
    payload = {
        "schema_version": "1.0",
        "device_event_id": "evt-auth-guard-01",
        "vehicle_id": "veh_guard_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.07, "longitude": 72.88, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 18.5, 9.8]}}
    }

    # Test D.1: Missing auth header -> 401
    resp_no_auth = client.post("/api/v1/events", json=payload)
    assert resp_no_auth.status_code == 401

    # Test D.2: Corrupted token -> 401
    resp_bad_auth = client.post("/api/v1/events", json=payload, headers={"Authorization": "Bearer bad.token.here"})
    assert resp_bad_auth.status_code == 401

    # Test E: Driver user JWT -> 401 (Only device JWT accepted)
    driver_token = create_test_driver_token("driver_guard@roadsentinel.io")
    resp_driver_auth = client.post("/api/v1/events", json=payload, headers={"Authorization": f"Bearer {driver_token}"})
    assert resp_driver_auth.status_code == 401
    assert "device token" in resp_driver_auth.json()["detail"].lower()


# --- TEST F & G: Unassigned Device and Wrong Vehicle ID Rejections ---
def test_f_g_unassigned_and_mismatched_vehicle_rejections():
    """Test F & G: Unassigned device and payload vehicle mismatch return 409."""
    admin_token = create_test_admin_token("test_fg_admin@roadsentinel.io")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Test F: Unassigned device (no vehicle_id at registration)
    reg_unassigned = client.post("/api/v1/devices/register", json={"hardware_type": "ESP32"}, headers=admin_headers)
    dev_f_id = reg_unassigned.json()["device_id"]
    prov_f = client.post(f"/api/v1/devices/{dev_f_id}/provision", json={"provisioning_secret": reg_unassigned.json()["provisioning_secret"]})
    auth_f = client.post(f"/api/v1/devices/{dev_f_id}/auth", json={"device_credential": prov_f.json()["device_credential"]})
    headers_f = {"Authorization": f"Bearer {auth_f.json()['access_token']}"}

    payload_f = {
        "schema_version": "1.0",
        "device_event_id": "evt-f-01",
        "vehicle_id": "veh_attempted_f",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.07, "longitude": 72.88, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 19.0]}}
    }
    resp_f = client.post("/api/v1/events", json=payload_f, headers=headers_f)
    assert resp_f.status_code == 409
    assert "no active vehicle assignment" in resp_f.json()["detail"].lower()

    # Test G: Assigned to veh_real_g, but payload specifies veh_fake_g
    dev_g_id, _, _, _, headers_g = setup_active_device_and_vehicle(
        vehicle_id="veh_real_g",
        admin_email="test_g_admin@roadsentinel.io"
    )
    payload_g = {
        "schema_version": "1.0",
        "device_event_id": "evt-g-01",
        "vehicle_id": "veh_fake_g", # Mismatch!
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.07, "longitude": 72.88, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 19.0]}}
    }
    resp_g = client.post("/api/v1/events", json=payload_g, headers=headers_g)
    assert resp_g.status_code == 409
    assert "does not match" in resp_g.json()["detail"].lower()


# --- TEST H, I, J: Raw Mode & Pre-Classified Mode Ingestion ---
def test_h_i_raw_mode_rule_based_classification_and_storage():
    """Test H & I: Raw IMU acceleration spikes classified by backend and persisted."""
    dev_id, _, _, _, dev_headers = setup_active_device_and_vehicle(
        vehicle_id="veh_raw_01",
        admin_email="test_hi_admin@roadsentinel.io"
    )

    # Spike of 19.2 m/s² -> High threshold (>= 18.0) -> Pothole (conf=0.88, sev=0.85, label=critical)
    raw_payload = {
        "schema_version": "1.0",
        "device_event_id": "esp32-raw-imu-101",
        "vehicle_id": "veh_raw_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {
            "latitude": 19.0728,
            "longitude": 72.8826,
            "accuracy_m": 2.5,
            "source": "gnss"
        },
        "modality_sources": ["imu"],
        "sensor_data": {
            "imu_window": {
                "z_accel": [9.8, 12.0, 19.2, 9.8]
            }
        },
        "firmware_version": "1.0.0"
    }

    resp = client.post("/api/v1/events", json=raw_payload, headers=dev_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["corroboration_count"] == 1
    event_id = data["event_id"]

    # Verify directly in database
    db = TestingSessionLocal()
    db_event = db.query(RoadEvent).filter(RoadEvent.id == event_id).first()
    assert db_event is not None
    assert db_event.event_type == "pothole"
    assert db_event.confidence == 0.88
    assert db_event.severity == 0.85
    assert db_event.severity_label == "critical"
    assert db_event.device_id == dev_id
    assert db_event.vehicle_id == "veh_raw_01"
    assert db_event.road_segment_id is None # Nullable in v1
    db.close()


def test_j_pre_classified_mode_ingestion():
    """Test J: Pre-classified event with model_output succeeds and attaches MLPrediction."""
    dev_id, _, _, _, dev_headers = setup_active_device_and_vehicle(
        vehicle_id="veh_pre_01",
        admin_email="test_j_admin@roadsentinel.io"
    )

    pre_payload = {
        "schema_version": "1.0",
        "device_event_id": "esp32-pre-classified-201",
        "vehicle_id": "veh_pre_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {
            "latitude": 19.0800,
            "longitude": 72.8900,
            "source": "gnss"
        },
        "event_type": "speed_breaker",
        "confidence": 0.92,
        "severity": 0.40,
        "modality_sources": ["imu"],
        "model_output": {
            "model_name": "imu-edge-classifier",
            "model_version": "2.1.0",
            "inference_location": "edge"
        }
    }

    resp = client.post("/api/v1/events", json=pre_payload, headers=dev_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "accepted"

    # Verify RoadEvent and attached MLPrediction
    db = TestingSessionLocal()
    db_event = db.query(RoadEvent).filter(RoadEvent.id == data["event_id"]).first()
    assert db_event.event_type == "speed_breaker"
    assert db_event.confidence == 0.92
    assert db_event.severity == 0.40
    assert db_event.severity_label == "medium"

    prediction = db.query(MLPrediction).filter(MLPrediction.event_id == db_event.id).first()
    assert prediction is not None
    assert prediction.model_name == "imu-edge-classifier"
    assert prediction.model_version == "2.1.0"
    assert prediction.confidence == 0.92
    db.close()


# --- TEST K, L, M: Idempotency on Retry ---
def test_k_l_m_event_idempotency_retry():
    """Test K, L, M: Same device_event_id retry returns duplicate without extra rows or incremented count."""
    dev_id, _, _, _, dev_headers = setup_active_device_and_vehicle(
        vehicle_id="veh_idemp_01",
        admin_email="test_klm_admin@roadsentinel.io"
    )

    payload = {
        "schema_version": "1.0",
        "device_event_id": "esp32-retry-key-301",
        "vehicle_id": "veh_idemp_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.0750, "longitude": 72.8850, "source": "gnss"},
        "event_type": "pothole",
        "confidence": 0.85,
        "severity": 0.70,
        "modality_sources": ["imu"]
    }

    # Initial submission
    resp1 = client.post("/api/v1/events", json=payload, headers=dev_headers)
    assert resp1.status_code == 200
    orig_id = resp1.json()["event_id"]
    assert resp1.json()["status"] == "accepted"
    assert resp1.json()["corroboration_count"] == 1

    # Retry submission
    resp2 = client.post("/api/v1/events", json=payload, headers=dev_headers)
    assert resp2.status_code == 200
    data2 = resp2.json()

    # Test K: Status duplicate and points to original event
    assert data2["status"] == "duplicate"
    assert data2["duplicate_of"] == orig_id

    # Test L: Exactly 1 row in database
    db = TestingSessionLocal()
    total_events = db.query(RoadEvent).filter(RoadEvent.device_id == dev_id).count()
    assert total_events == 1

    # Test M: Corroboration count not incremented on retry
    db_event = db.query(RoadEvent).filter(RoadEvent.id == orig_id).first()
    assert db_event.corroboration_count == 1
    db.close()


# --- TEST N: Corroboration from Different Devices ---
def test_n_different_device_corroboration():
    """Test N: Independent detection from different device increments corroboration_count on canonical event."""
    dev_a_id, _, _, _, headers_a = setup_active_device_and_vehicle(
        vehicle_id="veh_dev_a",
        admin_email="test_n_admin_a@roadsentinel.io"
    )
    dev_b_id, _, _, _, headers_b = setup_active_device_and_vehicle(
        vehicle_id="veh_dev_b",
        admin_email="test_n_admin_b@roadsentinel.io"
    )

    loc = {"latitude": 19.0765, "longitude": 72.8780, "source": "gnss"}

    # Device A detects pothole
    resp_a = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "dev-a-evt-001",
        "vehicle_id": "veh_dev_a",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": loc,
        "event_type": "pothole",
        "confidence": 0.80,
        "severity": 0.65,
        "modality_sources": ["imu"]
    }, headers=headers_a)
    assert resp_a.status_code == 200
    canonical_id = resp_a.json()["event_id"]
    assert resp_a.json()["corroboration_count"] == 1

    # Device B independently detects the same pothole at the same spot
    resp_b = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "dev-b-evt-001",
        "vehicle_id": "veh_dev_b",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": loc,
        "event_type": "pothole",
        "confidence": 0.85,
        "severity": 0.65,
        "modality_sources": ["imu"]
    }, headers=headers_b)
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["event_id"] == canonical_id
    assert data_b["corroboration_count"] == 2

    # Verify in DB
    db = TestingSessionLocal()
    canonical_event = db.query(RoadEvent).filter(RoadEvent.id == canonical_id).first()
    assert canonical_event.corroboration_count == 2
    assert canonical_event.confidence > 0.80 # Boosted by independent evidence
    db.close()


# --- TEST O: Event Read Endpoints ---
def test_o_event_read_endpoints():
    """Test O: Stored event can be retrieved via GET /events and GET /events/{id}."""
    dev_id, _, _, _, dev_headers = setup_active_device_and_vehicle(
        vehicle_id="veh_read_01",
        admin_email="test_o_admin@roadsentinel.io"
    )

    ingest_resp = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "evt-read-501",
        "vehicle_id": "veh_read_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.0728, "longitude": 72.8826, "source": "gnss"},
        "event_type": "pothole",
        "confidence": 0.88,
        "severity": 0.85,
        "modality_sources": ["imu"]
    }, headers=dev_headers)
    event_id = ingest_resp.json()["event_id"]

    # 1. Read single event by canonical ID
    get_single = client.get(f"/api/v1/events/{event_id}")
    assert get_single.status_code == 200
    single_data = get_single.json()
    assert single_data["id"] == event_id
    assert single_data["event_type"] == "pothole"
    assert single_data["vehicle_id"] == "veh_read_01"
    assert single_data["device_id"] == dev_id
    assert single_data["severity_label"] == "critical"

    # 2. Query events list with spatial bbox
    bbox = "72.80,19.00,72.90,19.10"
    get_list = client.get(f"/api/v1/events?bbox={bbox}")
    assert get_list.status_code == 200
    event_ids = [e["id"] for e in get_list.json()]
    assert event_id in event_ids


# --- TEST P: /telemetry Boundary Separation ---
def test_p_telemetry_boundary_separation():
    """Test P: Ingesting to /telemetry creates Telemetry row and does NOT create RoadEvent or MLPrediction."""
    dev_id, _, _, _, dev_headers = setup_active_device_and_vehicle(
        vehicle_id="veh_telem_01",
        admin_email="test_p_admin@roadsentinel.io"
    )

    telem_payload = {
        "vehicle_id": "veh_telem_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "latitude": 19.0728,
        "longitude": 72.8826,
        "raw_payload": {
            "stream_sample": [0.1, 0.2, 0.05],
            "speed_kmh": 45.0
        }
    }

    telem_resp = client.post("/api/v1/telemetry", json=telem_payload, headers=dev_headers)
    assert telem_resp.status_code == 201
    telem_id = telem_resp.json()["id"]

    # Verify Telemetry row exists, and NO RoadEvent or MLPrediction was created
    db = TestingSessionLocal()
    telem_row = db.query(Telemetry).filter(Telemetry.id == telem_id).first()
    assert telem_row is not None

    event_count = db.query(RoadEvent).count()
    ml_count = db.query(MLPrediction).count()
    assert event_count == 0
    assert ml_count == 0
    db.close()
