from datetime import datetime, timedelta, timezone
from app.database import SessionLocal, engine, Base
from app.models.domain import (
    User, Vehicle, Device, DeviceVehicleAssignment,
    RoadEvent, Report, MediaAsset, MLPrediction, GeoIndexBucket, utc_now
)
from app.auth.security import get_password_hash, hash_credential

def seed_database():
    db = SessionLocal()
    
    # Check if already seeded
    if db.query(User).filter(User.email == "admin@roadsentinel.io").first():
        print("Database already seeded. Skipping.")
        db.close()
        return

    print("Seeding ROADSentinel database...")

    # 1. Users
    admin_user = User(
        id="usr_admin001",
        email="admin@roadsentinel.io",
        hashed_password=get_password_hash("admin123"),
        name="Chief Admin (Road Authority)",
        role="admin"
    )
    
    driver_user = User(
        id="usr_driver001",
        email="driver@roadsentinel.io",
        hashed_password=get_password_hash("driver123"),
        name="Alex Driver",
        role="driver",
        saved_locations=[
            {"name": "Home", "latitude": 19.0760, "longitude": 72.8777},
            {"name": "Office", "latitude": 19.1197, "longitude": 72.8464}
        ]
    )
    db.add(admin_user)
    db.add(driver_user)
    db.commit()

    # 2. Vehicles
    vehicle_1 = Vehicle(
        id="veh_1183",
        type="car",
        owner_id=driver_user.id,
        metadata_json={"make": "Toyota", "model": "Corolla 2024"}
    )
    vehicle_2 = Vehicle(
        id="veh_9920",
        type="truck",
        owner_id=admin_user.id,
        metadata_json={"make": "Volvo", "model": "FH16 Fleet"}
    )
    db.add(vehicle_1)
    db.add(vehicle_2)
    db.commit()

    # 3. Devices
    device_1 = Device(
        id="esp32-4F2A-000183",
        vehicle_id=vehicle_1.id,
        hardware_type="ESP32",
        firmware_version="0.9.3",
        credential_hash=hash_credential("esp32_secret_token_183"),
        status="active",
        last_seen_at=utc_now()
    )
    device_2 = Device(
        id="edge-ai-9920",
        vehicle_id=vehicle_2.id,
        hardware_type="edge-ai",
        firmware_version="1.2.0",
        credential_hash=hash_credential("edge_ai_secret_token_920"),
        status="active",
        last_seen_at=utc_now()
    )
    db.add(device_1)
    db.add(device_2)
    db.commit()

    # 4. Device Vehicle Assignments
    assign_1 = DeviceVehicleAssignment(
        id="dva_001",
        device_id=device_1.id,
        vehicle_id=vehicle_1.id,
        assigned_from=utc_now() - timedelta(days=30)
    )
    assign_2 = DeviceVehicleAssignment(
        id="dva_002",
        device_id=device_2.id,
        vehicle_id=vehicle_2.id,
        assigned_from=utc_now() - timedelta(days=30)
    )
    db.add(assign_1)
    db.add(assign_2)
    db.commit()

    # 5. Sample Road Events (Mumbai area sample coordinates)
    sample_events = [
        RoadEvent(
            id="evt_001_pothole_high",
            device_event_id="esp32-001",
            device_id=device_1.id,
            vehicle_id=vehicle_1.id,
            device_timestamp=utc_now() - timedelta(hours=2),
            server_timestamp=utc_now() - timedelta(hours=2),
            latitude=19.0728,
            longitude=72.8826,
            location_accuracy_m=3.2,
            location_source="gnss",
            event_type="pothole",
            modality_sources=["imu"],
            confidence=0.88,
            severity=0.78,
            severity_label="high",
            status="unverified",
            corroboration_count=2
        ),
        RoadEvent(
            id="evt_002_speedbreaker",
            device_event_id="esp32-002",
            device_id=device_1.id,
            vehicle_id=vehicle_1.id,
            device_timestamp=utc_now() - timedelta(hours=1),
            server_timestamp=utc_now() - timedelta(hours=1),
            latitude=19.0815,
            longitude=72.8890,
            location_accuracy_m=4.0,
            location_source="gnss",
            event_type="speed_breaker",
            modality_sources=["imu"],
            confidence=0.92,
            severity=0.45,
            severity_label="medium",
            status="verified",
            corroboration_count=4
        ),
        RoadEvent(
            id="evt_003_critical_pit",
            device_event_id="edge-001",
            device_id=device_2.id,
            vehicle_id=vehicle_2.id,
            device_timestamp=utc_now() - timedelta(minutes=30),
            server_timestamp=utc_now() - timedelta(minutes=30),
            latitude=19.0950,
            longitude=72.8710,
            location_accuracy_m=2.5,
            location_source="gnss",
            event_type="pothole",
            modality_sources=["imu", "camera"],
            confidence=0.96,
            severity=0.92,
            severity_label="critical",
            status="unverified",
            corroboration_count=1
        ),
        RoadEvent(
            id="evt_004_waterlogging",
            device_event_id="edge-002",
            device_id=device_2.id,
            vehicle_id=vehicle_2.id,
            device_timestamp=utc_now() - timedelta(minutes=10),
            server_timestamp=utc_now() - timedelta(minutes=10),
            latitude=19.1020,
            longitude=72.8550,
            location_accuracy_m=3.0,
            location_source="gnss",
            event_type="waterlogging",
            modality_sources=["camera"],
            confidence=0.85,
            severity=0.65,
            severity_label="high",
            status="unverified",
            corroboration_count=1
        )
    ]
    for e in sample_events:
        db.add(e)
    db.commit()

    # 6. Sample Manual Report
    report_1 = Report(
        id="rpt_001",
        user_id=driver_user.id,
        description="Deep pothole near Western Express Highway junction, causing heavy traffic slowdown.",
        latitude=19.0950,
        longitude=72.8710,
        status="pending"
    )
    db.add(report_1)
    db.commit()

    print("Database seeding completed successfully!")
    print("Default Admin: admin@roadsentinel.io / admin123")
    print("Default Driver: driver@roadsentinel.io / driver123")
    print("Default ESP32 Device ID: esp32-4F2A-000183 (Credential: esp32_secret_token_183)")
    db.close()

if __name__ == "__main__":
    seed_database()
