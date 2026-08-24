from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.domain import Device, DeviceVehicleAssignment, Vehicle, User, utc_now
from app.schemas.domain_schemas import (
    DeviceRegisterRequest, DeviceRegisterResponse,
    DeviceProvisionRequest, DeviceProvisionResponse,
    DeviceAuthRequest, DeviceAuthResponse,
    DeviceReassignRequest, DeviceResponse
)
from app.auth.security import generate_random_secret, hash_credential, create_device_token
from app.auth.deps import require_role

router = APIRouter(prefix="/devices", tags=["Device Provisioning & Lifecycle"])

@router.post("/register", response_model=DeviceRegisterResponse)
def register_device(
    req: DeviceRegisterRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin"]))
):
    """Spec §5.1 & Phase 3: Admin registers new hardware device, producing single-use provisioning secret."""
    prov_secret = generate_random_secret()
    device = Device(
        hardware_type=req.hardware_type or "ESP32",
        firmware_version=req.firmware_version or "1.0.0",
        vehicle_id=req.vehicle_id,
        provisioning_secret=prov_secret,
        status="provisioning"
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    
    if req.vehicle_id:
        assignment = DeviceVehicleAssignment(
            device_id=device.id,
            vehicle_id=req.vehicle_id,
            assigned_from=utc_now()
        )
        db.add(assignment)
        db.commit()
        
    return DeviceRegisterResponse(
        device_id=device.id,
        provisioning_secret=prov_secret,
        status=device.status
    )


@router.post("/{device_id}/provision", response_model=DeviceProvisionResponse)
def provision_device(device_id: str, req: DeviceProvisionRequest, db: Session = Depends(get_db)):
    """Spec §5.1 & Phase 3: Single-use exchange of provisioning secret for long-lived device credential."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device or not device.provisioning_secret or device.provisioning_secret != req.provisioning_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device_id or provisioning secret")
    
    if device.status == "revoked":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device has been permanently revoked")
        
    credential = generate_random_secret()
    device.credential_hash = hash_credential(credential)
    device.provisioning_secret = None  # Single-use provisioning secret invalidated!
    device.status = "active"
    device.last_seen_at = utc_now()
    db.commit()
    
    return DeviceProvisionResponse(
        device_id=device.id,
        device_credential=credential,
        status=device.status
    )


@router.post("/{device_id}/auth", response_model=DeviceAuthResponse)
def authenticate_device(device_id: str, req: DeviceAuthRequest, db: Session = Depends(get_db)):
    """Spec §5.1 & Phase 3: Device exchanges credential for 1-hour short-lived device access token."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device or not device.credential_hash or device.credential_hash != hash_credential(req.device_credential):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device credential")
        
    if device.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device status is '{device.status}'. Active status required to authenticate."
        )
        
    device.last_seen_at = utc_now()
    db.commit()
    
    token = create_device_token(device_id=device.id, vehicle_id=device.vehicle_id)
    return DeviceAuthResponse(
        access_token=token,
        device_id=device.id,
        vehicle_id=device.vehicle_id
    )


@router.post("/{device_id}/rotate-credential", response_model=DeviceProvisionResponse)
def rotate_device_credential(
    device_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin"]))
):
    """Phase 3: Rotate device credential secret for security lifecycle maintenance."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.status == "revoked":
        raise HTTPException(status_code=403, detail="Cannot rotate credentials for revoked device")

    new_credential = generate_random_secret()
    device.credential_hash = hash_credential(new_credential)
    db.commit()
    return DeviceProvisionResponse(
        device_id=device.id,
        device_credential=new_credential,
        status=device.status
    )


@router.post("/{device_id}/disable")
def disable_device(
    device_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin"]))
):
    """Phase 3: Admin disables device, blocking authentication and ingestion."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.status = "disabled"
    db.commit()
    return {"message": f"Device {device_id} disabled", "status": "disabled"}


@router.post("/{device_id}/enable")
def enable_device(
    device_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin"]))
):
    """Phase 3: Admin enables device."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.status == "revoked":
        raise HTTPException(status_code=403, detail="Cannot enable permanently revoked device")
    device.status = "active"
    db.commit()
    return {"message": f"Device {device_id} enabled", "status": "active"}


@router.post("/{device_id}/reassign", response_model=DeviceResponse)
def reassign_device_vehicle(
    device_id: str,
    req: DeviceReassignRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin"]))
):
    """Spec §5.3 & Phase 3: Reassign device to new vehicle, preserving historical assignment timestamps."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    # Close out previous active assignment (assigned_to = utc_now())
    current_assignment = db.query(DeviceVehicleAssignment).filter(
        DeviceVehicleAssignment.device_id == device.id,
        DeviceVehicleAssignment.assigned_to.is_(None)
    ).first()
    
    if current_assignment:
        current_assignment.assigned_to = utc_now()
        
    # Create new assignment record
    new_assignment = DeviceVehicleAssignment(
        device_id=device.id,
        vehicle_id=req.new_vehicle_id,
        assigned_from=utc_now()
    )
    device.vehicle_id = req.new_vehicle_id
    db.add(new_assignment)
    db.commit()
    db.refresh(device)
    return device


@router.post("/{device_id}/revoke")
def revoke_device(
    device_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin"]))
):
    """Spec §5.2 & Phase 3: Permanently revoke device credential."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.status = "revoked"
    device.credential_hash = None
    db.commit()
    return {"message": f"Device {device_id} successfully revoked", "status": "revoked"}


@router.get("", response_model=List[DeviceResponse])
def list_devices(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["admin", "authority"]))
):
    return db.query(Device).order_by(Device.created_at.desc()).all()
