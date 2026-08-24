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
    Spec §0 Constraint #2 & §4.1:
    /telemetry accepts raw sensor data with NO hazard claim attached (for ML dataset curation).
    """
    device, assigned_vehicle_id = device_context
    
    telemetry = Telemetry(
        device_id=device.id,
        vehicle_id=req.vehicle_id,
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
