from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.domain import Telemetry, utc_now
from app.schemas.domain_schemas import TelemetryIngestionRequest
from app.auth.deps import get_current_device

router = APIRouter(prefix="/telemetry", tags=["Telemetry Data Streams"])

@router.post("", status_code=status.HTTP_201_CREATED)
def ingest_telemetry(
    req: TelemetryIngestionRequest,
    db: Session = Depends(get_db),
    device_context: tuple = Depends(get_current_device)
):
    """
    Spec §0 Constraint #2, §4.1 & Phase 5:
    /telemetry accepts raw continuous sensor streams with NO hazard claim attached (for ML dataset curation).
    Strictly independent: does NOT create RoadEvent or MLPrediction rows.
    """
    device, assigned_vehicle_id = device_context
    
    # Authoritative Vehicle Identity check (Phase 5)
    if not assigned_vehicle_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device '{device.id}' has no active vehicle assignment in database. Telemetry rejected."
        )

    if req.vehicle_id and req.vehicle_id != assigned_vehicle_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vehicle ID '{req.vehicle_id}' in payload does not match active device assignment '{assigned_vehicle_id}'"
        )

    effective_vehicle_id = assigned_vehicle_id
    
    telemetry = Telemetry(
        device_id=device.id,
        vehicle_id=effective_vehicle_id,
        device_timestamp=req.device_timestamp,
        server_timestamp=utc_now(),
        latitude=req.latitude,
        longitude=req.longitude,
        raw_payload=req.raw_payload,
        label=req.label,
        linked_event_id=req.linked_event_id
    )
    db.add(telemetry)
    db.commit()
    return {"status": "accepted", "id": telemetry.id}
