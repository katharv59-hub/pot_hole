import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.domain import Report, MediaAsset, User, utc_now
from app.schemas.domain_schemas import (
    ReportCreate, ReportResponse, UploadUrlResponse, MediaAssetResponse
)
from app.auth.deps import get_current_user, require_role
from app.services.storage_service import storage_service

router = APIRouter(prefix="/reports", tags=["Manual Driver Reporting"])

@router.post("", response_model=ReportResponse)
def create_manual_report(
    req: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Spec §6 & Phase 10: Manual user-submitted hazard report bound to driver identity."""
    report = Report(
        user_id=current_user.id,
        description=req.description,
        latitude=req.latitude,
        longitude=req.longitude,
        status="pending"
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/me", response_model=List[ReportResponse])
def get_my_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Spec §4.1 & Phase 10: Driver views their own report history."""
    return db.query(Report).filter(Report.user_id == current_user.id).order_by(Report.created_at.desc()).all()


@router.get("/admin", response_model=List[ReportResponse])
def get_all_reports(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin", "authority"]))
):
    """Admin views all submitted reports."""
    return db.query(Report).order_by(Report.created_at.desc()).all()


@router.post("/{report_id}/media/upload-url", response_model=UploadUrlResponse)
def get_report_media_upload_url(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Spec §11.1 & Phase 9: Report-specific pre-signed upload URL."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    if report.user_id != current_user.id and current_user.role not in ["admin", "authority"]:
        raise HTTPException(status_code=403, detail="Not authorized to attach media to this report")

    media_id = f"med_rpt_{uuid.uuid4().hex[:8]}"
    upload_info = storage_service.generate_presigned_upload_url(media_id)
    return UploadUrlResponse(media_id=media_id, upload_url=upload_info["upload_url"])


@router.post("/{report_id}/media/{media_id}/confirm", response_model=MediaAssetResponse)
def confirm_report_media(
    report_id: str,
    media_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Spec §11.1 & Phase 9: Confirm media asset upload (retry-safe & user-authorized)."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if report.user_id != current_user.id and current_user.role not in ["admin", "authority"]:
        raise HTTPException(status_code=403, detail="Not authorized to confirm media for this report")

    # Phase 9: Make confirmation retry-safe by checking existing asset
    existing = db.query(MediaAsset).filter(MediaAsset.id == media_id).first()
    if existing:
        return existing

    storage_url = storage_service.get_public_or_signed_download_url(media_id)
    asset = MediaAsset(
        id=media_id,
        report_id=report.id,
        type="image",
        storage_url=storage_url,
        access_tier="raw"
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset
