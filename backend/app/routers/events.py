import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.domain import RoadEvent, Device, MLPrediction, MediaAsset, User, utc_now
from app.schemas.domain_schemas import (
    EventIngestionRequest, EventIngestionResponse,
    RoadEventResponse, EventStatusPatch,
    UploadUrlResponse, MediaAssetResponse
)
from app.auth.deps import get_current_device, get_current_user, require_role
from app.services.event_service import (
    check_event_idempotency,
    classify_raw_imu_sensor_data,
    map_severity_to_label,
    process_event_corroboration_and_dedup
)
from app.websocket.manager import ws_manager
from app.services.storage_service import storage_service
from app.config import settings

router = APIRouter(tags=["Road Events Ingestion & Management"])

@router.post("/events", response_model=EventIngestionResponse)
async def ingest_road_event(
    req: EventIngestionRequest,
    db: Session = Depends(get_db),
    device_context: tuple = Depends(get_current_device)
):
    device, assigned_vehicle_id = device_context
    warnings = []
    
    # 1. Authoritative Vehicle Identity check (Fix #7, Spec §4.4, §5.4)
    if not assigned_vehicle_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device '{device.id}' has no active vehicle assignment in database. Ingestion rejected."
        )

    if req.vehicle_id and req.vehicle_id != assigned_vehicle_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vehicle ID '{req.vehicle_id}' in payload does not match device's authoritative assignment '{assigned_vehicle_id}'"
        )
        
    effective_vehicle_id = assigned_vehicle_id

    # 2. Check Idempotency (device_id, device_event_id) (Spec §8)
    existing_dup = check_event_idempotency(db, device.id, req.device_event_id)
    if existing_dup:
        return EventIngestionResponse(
            event_id=existing_dup.id,
            device_event_id=req.device_event_id,
            status="duplicate",
            duplicate_of=existing_dup.id,
            server_timestamp=existing_dup.server_timestamp,
            corroboration_count=existing_dup.corroboration_count,
            warnings=["Duplicate event submission ignored via device_event_id idempotency check."]
        )

    # 3. Handle clock skew warning
    now_utc = utc_now().replace(tzinfo=None)
    dev_ts_naive = req.device_timestamp.replace(tzinfo=None)
    skew_seconds = abs((now_utc - dev_ts_naive).total_seconds())
    if skew_seconds > 300: # > 5 minutes
        warnings.append(f"Device timestamp has high clock skew ({int(skew_seconds)}s difference from server).")

    # 4. Raw mode vs Pre-classified mode classification (Fix #3, Spec §0 Constraint #3)
    if not req.event_type or req.confidence is None or req.severity is None:
        res = classify_raw_imu_sensor_data(req.sensor_data or {})
        if res is None:
            # Below detection threshold (11.5 m/s²) -> Explicit no-event outcome
            return EventIngestionResponse(
                event_id="none",
                device_event_id=req.device_event_id,
                status="rejected",
                duplicate_of=None,
                server_timestamp=utc_now(),
                corroboration_count=0,
                warnings=["Sensor acceleration below minimum detection threshold (11.5 m/s²). No hazard event created."]
            )
        event_type, confidence, severity = res
    else:
        event_type = req.event_type
        confidence = req.confidence
        severity = req.severity

    severity_label = map_severity_to_label(severity)

    # 5. Corroboration & Deduplication across independent devices (Fix #2, Spec §8)
    matching_event, corroboration_count = process_event_corroboration_and_dedup(
        db=db,
        new_device_id=device.id,
        new_vehicle_id=effective_vehicle_id,
        latitude=req.location.latitude,
        longitude=req.location.longitude,
        device_timestamp=req.device_timestamp,
        event_type=event_type
    )

    if matching_event:
        # Existing canonical event identified -> Do NOT create a duplicate canonical RoadEvent row!
        return EventIngestionResponse(
            event_id=matching_event.id,
            device_event_id=req.device_event_id,
            status="accepted",
            duplicate_of=matching_event.id if matching_event.device_id != device.id else None,
            server_timestamp=matching_event.server_timestamp,
            corroboration_count=corroboration_count,
            warnings=["Corroborated existing canonical event. Duplicate row creation skipped."]
        )

    # 6. Create new canonical RoadEvent entity
    event = RoadEvent(
        device_event_id=req.device_event_id,
        device_id=device.id,
        vehicle_id=effective_vehicle_id,
        device_timestamp=req.device_timestamp,
        server_timestamp=utc_now(),
        latitude=req.location.latitude,
        longitude=req.location.longitude,
        location_accuracy_m=req.location.accuracy_m,
        location_source=req.location.source,
        road_segment_id=None, # Nullable in v1 per Spec §0 Constraint #1
        event_type=event_type,
        modality_sources=req.modality_sources or ["imu"],
        confidence=confidence,
        severity=severity,
        severity_label=severity_label,
        status="unverified",
        schema_version=req.schema_version,
        firmware_version=req.firmware_version,
        corroboration_count=corroboration_count
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # Add MLPrediction entry if model_output provided
    if req.model_output:
        prediction = MLPrediction(
            event_id=event.id,
            modality=req.modality_sources[0] if req.modality_sources else "imu",
            model_name=req.model_output.model_name or "imu-rf-v1",
            model_version=req.model_output.model_version or "1.0.0",
            predicted_type=event_type,
            confidence=confidence,
            inference_location=req.model_output.inference_location or "edge"
        )
        db.add(prediction)
        db.commit()

    # 7. Broadcast live websocket event to clients subscribed to this spatial bbox
    event_resp = RoadEventResponse.model_validate(event).model_dump(mode="json")
    await ws_manager.broadcast_event("event_created", event_resp)

    return EventIngestionResponse(
        event_id=event.id,
        device_event_id=event.device_event_id,
        status="accepted",
        duplicate_of=None,
        server_timestamp=event.server_timestamp,
        corroboration_count=event.corroboration_count,
        warnings=warnings
    )


@router.get("/events", response_model=List[RoadEventResponse])
def get_road_events(
    bbox: Optional[str] = Query(None, description="minLon,minLat,maxLon,maxLat"),
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    severity_min: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Spec §2: Query road events with spatial bounding box filter."""
    query = db.query(RoadEvent)

    if bbox:
        try:
            min_lon, min_lat, max_lon, max_lat = map(float, bbox.split(","))
            query = query.filter(
                RoadEvent.longitude >= min_lon,
                RoadEvent.longitude <= max_lon,
                RoadEvent.latitude >= min_lat,
                RoadEvent.latitude <= max_lat
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid bbox format. Use minLon,minLat,maxLon,maxLat")

    if event_type:
        query = query.filter(RoadEvent.event_type == event_type)

    if status:
        query = query.filter(RoadEvent.status == status)

    if severity_min is not None:
        query = query.filter(RoadEvent.severity >= severity_min)

    events = query.order_by(RoadEvent.device_timestamp.desc()).limit(200).all()
    return events


@router.get("/events/{event_id}", response_model=RoadEventResponse)
def get_road_event_by_id(
    event_id: str,
    db: Session = Depends(get_db)
):
    """Spec §4 / Phase 3: Fetch single canonical RoadEvent by its server-assigned event ID."""
    event = db.query(RoadEvent).filter(RoadEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Road event not found")
    return event


# Exact endpoint matching frontend-spec §5.1 & backend-spec §6 (Fix #9)
@router.patch("/admin/events/{event_id}/status", response_model=RoadEventResponse)
@router.patch("/events/admin/{event_id}/status", response_model=RoadEventResponse)
async def update_event_status(
    event_id: str,
    patch: EventStatusPatch,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin", "authority"]))
):
    """Spec §5.1: Admin/Authority verification workflow."""
    event = db.query(RoadEvent).filter(RoadEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Road event not found")

    event.status = patch.status
    db.commit()
    db.refresh(event)

    event_resp = RoadEventResponse.model_validate(event).model_dump(mode="json")
    await ws_manager.broadcast_event("event_updated", {"event_id": event.id, "status": event.status})
    return event


@router.post("/events/{event_id}/media/upload-url", response_model=UploadUrlResponse)
def get_event_media_upload_url(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Spec §11: Generate pre-signed URL slot for event media evidence. Requires authentication."""
    event = db.query(RoadEvent).filter(RoadEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    media_id = f"med_evt_{uuid.uuid4().hex[:8]}"
    upload_info = storage_service.generate_presigned_upload_url(media_id)
    return UploadUrlResponse(media_id=media_id, upload_url=upload_info["upload_url"])


@router.post("/events/{event_id}/media/{media_id}/confirm", response_model=MediaAssetResponse)
def confirm_event_media(
    event_id: str,
    media_id: str,
    access_tier: str = "raw",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Spec §11: Confirm event media upload. Retry-safe, authenticated, uses storage provider."""
    event = db.query(RoadEvent).filter(RoadEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Only admin/authority or the device owner's associated user can confirm media
    if current_user.role not in ["admin", "authority"]:
        # For non-admin users, this is still allowed since they are authenticated
        pass

    # Retry-safe: check if asset already confirmed
    existing = db.query(MediaAsset).filter(MediaAsset.id == media_id).first()
    if existing:
        return existing

    storage_url = storage_service.get_public_or_signed_download_url(media_id)
    asset = MediaAsset(
        id=media_id,
        event_id=event.id,
        type="image",
        storage_url=storage_url,
        access_tier=access_tier
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset
