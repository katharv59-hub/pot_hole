from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.domain import User
from app.schemas.domain_schemas import UserCreate, UserLogin, UserResponse, TokenResponse
from app.auth.security import verify_password, get_password_hash, create_access_token
from app.auth.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["User Authentication"])

@router.post("/register", response_model=TokenResponse)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Public registration endpoint.
    Fix #5: Public registration creates a normal 'driver' account by default.
    Privileged roles ('admin', 'authority') cannot be assigned via public registration.
    """
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    hashed_pwd = get_password_hash(user_in.password)
    # Hardcode role to "driver" for public registrations to prevent escalation
    user = User(
        email=user_in.email,
        hashed_password=hashed_pwd,
        name=user_in.name,
        role="driver" # Forced driver role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = create_access_token(subject=user.id, role=user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login_user(user_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    token = create_access_token(subject=user.id, role=user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user
