import time
import requests
from datetime import datetime, timezone

BASE_URL = "http://localhost:8000/api/v1"

def simulate_esp32_device():
    print("==================================================")
    print("ROADSentinel — ESP32 Hardware Ingestion Simulator")
    print("==================================================")
    
    # 1. Device Session Authentication using provisioning key
    device_id = "esp32-4F2A-000183"
    credential = "esp32_secret_token_183"

    print(f"1. Authenticating ESP32 Device '{device_id}'...")
    auth_resp = requests.post(f"{BASE_URL}/devices/{device_id}/auth", json={"device_credential": credential})
    if auth_resp.status_code != 200:
        print(f"FAILED: Device authentication returned {auth_resp.status_code}: {auth_resp.text}")
        return
        
    dev_token = auth_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {dev_token}"}
    print("   -> Success! Access Token obtained.")

    # 2. Ingest Raw IMU Event (Constraint #3)
    event_idempotency_key = f"esp32-sim-{int(time.time())}"
    payload = {
        "schema_version": "1.0",
        "device_event_id": event_idempotency_key,
        "vehicle_id": "veh_1183", # Cross-checked against active device assignment
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {
            "latitude": 19.0728,
            "longitude": 72.8826,
            "accuracy_m": 2.8,
            "source": "gnss"
        },
        "modality_sources": ["imu"],
        "sensor_data": {
            "imu_window": {
                "z_accel": [9.81, 14.2, 19.8, 9.75] # Spike > 18.0 -> Critical pothole classification
            }
        },
        "firmware_version": "0.9.3"
    }

    print("\n2. Ingesting Raw IMU Acceleration Spike (Threshold Mode)...")
    ingest_resp = requests.post(f"{BASE_URL}/events", json=payload, headers=headers)
    print(f"   Response Status Code: {ingest_resp.status_code}")
    print(f"   Payload Response: {ingest_resp.json()}")

    # 3. Test Idempotency Retry
    print("\n3. Testing Idempotency Retry with same device_event_id...")
    retry_resp = requests.post(f"{BASE_URL}/events", json=payload, headers=headers)
    print(f"   Retry Response Status: {retry_resp.status_code}")
    print(f"   Retry Payload Response: {retry_resp.json()}")
    print("\nSimulation complete!")

if __name__ == "__main__":
    simulate_esp32_device()
