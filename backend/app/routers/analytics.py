import csv
import io
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.domain import RoadEvent, Report, Device, User
from app.auth.deps import require_role

router = APIRouter(prefix="/analytics", tags=["Admin & Authority Analytics"])

@router.get("/summary")
def get_analytics_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["admin", "authority"]))
):
    """Spec §5.1: Spatial & Hazard Analytics summary dashboard."""
    total_events = db.query(RoadEvent).count()
    unverified_count = db.query(RoadEvent).filter(RoadEvent.status == "unverified").count()
    verified_count = db.query(RoadEvent).filter(RoadEvent.status == "verified").count()
    resolved_count = db.query(RoadEvent).filter(RoadEvent.status == "resolved").count()
    duplicate_count = db.query(RoadEvent).filter(RoadEvent.status == "duplicate").count()

    # Event Type Breakdown
    type_counts = db.query(
        RoadEvent.event_type, func.count(RoadEvent.id)
    ).group_by(RoadEvent.event_type).all()

    # Severity Label Breakdown
    severity_counts = db.query(
        RoadEvent.severity_label, func.count(RoadEvent.id)
    ).group_by(RoadEvent.severity_label).all()

    total_devices = db.query(Device).count()
    active_devices = db.query(Device).filter(Device.status == "active").count()
    total_reports = db.query(Report).count()

    return {
        "metrics": {
            "total_events": total_events,
            "unverified_count": unverified_count,
            "verified_count": verified_count,
            "resolved_count": resolved_count,
            "duplicate_count": duplicate_count,
            "active_devices": active_devices,
            "total_devices": total_devices,
            "total_manual_reports": total_reports
        },
        "event_type_distribution": {k: v for k, v in type_counts},
        "severity_distribution": {k: v for k, v in severity_counts}
    }


@router.get("/export")
def export_analytics_csv(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["admin", "authority"]))
):
    """Spec §5.1 & §6: Export hazard event catalog as CSV."""
    events = db.query(RoadEvent).order_by(RoadEvent.device_timestamp.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Event ID", "Device Event ID", "Device ID", "Vehicle ID",
        "Device Timestamp", "Server Timestamp", "Latitude", "Longitude",
        "Event Type", "Severity Float", "Severity Label", "Confidence",
        "Corroboration Count", "Status", "Modality Sources"
    ])

    for e in events:
        writer.writerow([
            e.id, e.device_event_id, e.device_id, e.vehicle_id,
            e.device_timestamp.isoformat(), e.server_timestamp.isoformat(),
            e.latitude, e.longitude, e.event_type, e.severity, e.severity_label,
            e.confidence, e.corroboration_count, e.status, ",".join(e.modality_sources or [])
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=roadsentinel_hazards.csv"}
    )
