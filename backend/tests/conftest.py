import os

# Test-only environment configuration — set BEFORE any app imports.
os.environ["TESTING"] = "true"
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://test:test@localhost:5432/test_roadsentinel")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production-use-1234567890abcdef")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models.domain import User
from app.auth.security import get_password_hash, create_access_token

# Isolated test database — SQLite is intentionally used ONLY here in test fixtures.
# This is NOT a runtime fallback; it is an explicit test infrastructure choice.
TEST_DB_FILE = "./test_roadsentinel.db"
SQLALCHEMY_TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(autouse=True, scope="function")
def setup_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture
def client():
    return TestClient(app)

def create_test_admin_token(email: str = "testadmin@roadsentinel.io") -> str:
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            hashed_password=get_password_hash("adminpassword123"),
            name="Test Admin",
            role="admin"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    token = create_access_token(subject=user.id, role="admin")
    db.close()
    return token

def create_test_driver_token(email: str = "testdriver@roadsentinel.io") -> str:
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            hashed_password=get_password_hash("driverpassword123"),
            name="Test Driver",
            role="driver"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    token = create_access_token(subject=user.id, role="driver")
    db.close()
    return token
