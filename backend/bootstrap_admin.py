import sys
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models.domain import User
from app.auth.security import get_password_hash

def bootstrap_admin_user(
    email: str = "admin@roadsentinel.io",
    password: str = "admin123",
    role: str = "admin",
    db: Session = None
):
    """CLI / test helper script for creating privileged admin/authority accounts (Fix #5)."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if close_db:
            db.close()
        return existing

    admin = User(
        email=email,
        hashed_password=get_password_hash(password),
        name="Bootstrapped Administrator",
        role=role
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print(f"Successfully created privileged account '{email}' with role '{role}'.")
    if close_db:
        db.close()
    return admin

if __name__ == "__main__":
    email_arg = sys.argv[1] if len(sys.argv) > 1 else "admin@roadsentinel.io"
    password_arg = sys.argv[2] if len(sys.argv) > 2 else "admin123"
    role_arg = sys.argv[3] if len(sys.argv) > 3 else "admin"
    bootstrap_admin_user(email_arg, password_arg, role_arg)
