import math
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional, List, Dict, Any
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.config import settings
from app.models.domain import RoadEvent, GeoIndexBucket, MLPrediction, DeviceVehicleAssignment, utc_now

# Standard Geohash Base32 encoder for spatial indexing
GEOHASH_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

def encode_geohash(latitude: float, longitude: float, precision: int = 6) -> str:
    lat_interval = (-90.0, 90.0)
    lon_interval = (-180.0, 180.0)
    geohash = []
    bits = [16, 8, 4, 2, 1]
    bit = 0
    ch = 0
    even = True

    while len(geohash) < precision:
        if even:
            mid = (lon_interval[0] + lon_interval[1]) / 2
            if longitude >= mid:
                ch |= bits[bit]
                lon_interval = (mid, lon_interval[1])
            else:
                lon_interval = (lon_interval[0], mid)
        else:
            mid = (lat_interval[0] + lat_interval[1]) / 2
            if latitude >= mid:
                ch |= bits[bit]
                lat_interval = (mid, lat_interval[1])
            else:
                lat_interval = (lat_interval[0], mid)
        
        even = not even
        if bit < 4:
            bit += 1
        else:
            geohash.append(GEOHASH_BASE32[ch])
            bit = 0
            ch = 0

    return "".join(geohash)


def calculate_haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Returns distance between two coordinates in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def map_severity_to_label(severity_val: float) -> str:
    if severity_val >= 0.75:
        return "critical"
    elif severity_val >= 0.50:
        return "high"
    elif severity_val >= 0.25:
        return "medium"
    else:
        return "low"


def resolve_temporal_vehicle_assignment(db: Session, device_id: str, timestamp: datetime) -> Optional[str]:
    """
    Spec §4.1 & Post-Audit Remediation:
    Resolves the authoritative vehicle assignment for `device_id` valid at `timestamp`.
    Satisfies `assigned_from <= timestamp` and `(assigned_to IS NULL OR assigned_to >= timestamp)`.
    Returns vehicle_id or None if no valid assignment existed at that timestamp.
    """
    ts_naive = timestamp.replace(tzinfo=None) if timestamp.tzinfo else timestamp
    assignment = db.query(DeviceVehicleAssignment).filter(
        DeviceVehicleAssignment.device_id == device_id,
        DeviceVehicleAssignment.assigned_from <= ts_naive,
        or_(
            DeviceVehicleAssignment.assigned_to.is_(None),
            DeviceVehicleAssignment.assigned_to >= ts_naive
        )
    ).order_by(DeviceVehicleAssignment.assigned_from.desc()).first()
    return assignment.vehicle_id if assignment else None


def classify_raw_imu_sensor_data(sensor_data: Dict[str, Any]) -> Optional[Tuple[str, float, float]]:
    """
    Spec §0 Binding Constraint #3 & §2 Raw Mode classification:
    Evaluates IMU window data for acceleration spikes to produce event_type, confidence, severity.
    Returns None if max acceleration is below minimum detection threshold (11.5 m/s²).
    """
    if not sensor_data:
        return None
    
    imu_window = sensor_data.get("imu_window", {})
    z_accel_samples = imu_window.get("z_accel", [])
    if not z_accel_samples:
        return None

    max_accel = max([abs(x) for x in z_accel_samples])

    if max_accel >= settings.IMU_ACCEL_THRESHOLD_HIGH:
        return ("pothole", 0.88, 0.85)  # Critical severity
    elif max_accel >= settings.IMU_ACCEL_THRESHOLD_MED:
        return ("pothole", 0.80, 0.60)  # High severity
    elif max_accel >= settings.IMU_ACCEL_THRESHOLD_LOW:
        return ("speed_breaker", 0.72, 0.35)  # Medium severity
    else:
        # Explicit no-event / insufficient-evidence signal (Fix #3)
        return None


def check_event_idempotency(db: Session, device_id: str, device_event_id: str) -> Optional[RoadEvent]:
    """
    Spec §8: Enforces uniqueness on (device_id, device_event_id).
    Returns existing event if duplicate upload attempt.
    """
    return db.query(RoadEvent).filter(
        RoadEvent.device_id == device_id,
        RoadEvent.device_event_id == device_event_id
    ).first()


def process_event_corroboration_and_dedup(
    db: Session,
    new_device_id: str,
    new_vehicle_id: str,
    latitude: float,
    longitude: float,
    device_timestamp: datetime,
    event_type: str
) -> Tuple[Optional[RoadEvent], int]:
    """
    Spec §8 & Post-Audit Remediation: Deterministic Corroboration & Deduplication:
    Candidates within spatial & temporal window are ranked deterministically by:
    1. Temporal distance ascending (abs(seconds difference))
    2. Spatial distance ascending (meters)
    3. Canonical event ID ascending (tie-breaker)
    Increments corroboration_count ONLY when a DIFFERENT device submits a matching event.
    """
    time_window_start = device_timestamp - timedelta(minutes=settings.CORROBORATION_TIME_WINDOW_MINS)
    time_window_end = device_timestamp + timedelta(minutes=settings.CORROBORATION_TIME_WINDOW_MINS)
    
    candidates = db.query(RoadEvent).filter(
        RoadEvent.status.in_(["unverified", "verified"]),
        RoadEvent.device_timestamp >= time_window_start,
        RoadEvent.device_timestamp <= time_window_end,
        RoadEvent.event_type == event_type
    ).all()
    
    dev_ts_naive = device_timestamp.replace(tzinfo=None) if device_timestamp.tzinfo else device_timestamp
    eligible_candidates = []
    
    for cand in candidates:
        cand_ts_naive = cand.device_timestamp.replace(tzinfo=None) if cand.device_timestamp.tzinfo else cand.device_timestamp
        dist_m = calculate_haversine_distance_m(latitude, longitude, cand.latitude, cand.longitude)
        if dist_m <= settings.CORROBORATION_DISTANCE_METERS:
            temporal_diff_s = abs((dev_ts_naive - cand_ts_naive).total_seconds())
            # Deterministic tuple: (temporal_distance, spatial_distance, event_id, event_obj)
            eligible_candidates.append((temporal_diff_s, dist_m, cand.id, cand))
            
    matching_event = None
    if eligible_candidates:
        # Deterministic sorting guarantee independent of DB row retrieval order
        eligible_candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        matching_event = eligible_candidates[0][3]
            
    if matching_event:
        # Check if it's an independent device (different device_id)
        if matching_event.device_id != new_device_id:
            matching_event.corroboration_count += 1
            # Increase confidence with independent evidence
            matching_event.confidence = min(1.0, round(matching_event.confidence + 0.05, 2))
            db.commit()
            db.refresh(matching_event)
        return matching_event, matching_event.corroboration_count
    
    # Update Spatial GeoIndexBucket
    gh = encode_geohash(latitude, longitude, precision=6)
    bucket = db.query(GeoIndexBucket).filter(GeoIndexBucket.geohash == gh).first()
    if not bucket:
        bucket = GeoIndexBucket(geohash=gh, event_count=1, last_event_at=utc_now())
        db.add(bucket)
    else:
        bucket.event_count += 1
        bucket.last_event_at = utc_now()
    
    db.commit()
    return None, 1
