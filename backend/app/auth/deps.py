from typing import List, Tuple, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.domain import User, Device, DeviceVehicleAssignment
from app.auth.security import decode_jwt_token

security_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_jwt_token(credentials.credentials)
    if not payload or payload.get("type") != "user":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired user authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User associated with token not found"
        )
    return user


def require_role(allowed_roles: List[str]):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{current_user.role}' is not authorized to perform this operation. Required: {allowed_roles}"
            )
        return current_user
    return role_checker


def get_current_device(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Tuple[Device, Optional[str]]:
    """
    Derived server-side identity chain (Spec §4.1, §5.4):
    token -> device_id -> active Device -> current DeviceVehicleAssignment -> vehicle_id
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device authentication token missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_jwt_token(credentials.credentials)
    if not payload or payload.get("type") != "device":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired device token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    device_id = payload.get("sub")
    device = db.query(Device).filter(Device.id == device_id).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Device {device_id} not found"
        )
        
    if device.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device status is '{device.status}'. Active status required."
        )
    
    # Query current active vehicle assignment (assigned_to is NULL)
    assignment = db.query(DeviceVehicleAssignment).filter(
        DeviceVehicleAssignment.device_id == device.id,
        DeviceVehicleAssignment.assigned_to.is_(None)
    ).order_by(DeviceVehicleAssignment.assigned_from.desc()).first()
    
    assigned_vehicle_id = assignment.vehicle_id if assignment else device.vehicle_id
    return device, assigned_vehicle_id
