import os
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine default database URL based on environment or driver availability
default_db_url = os.getenv("DATABASE_URL")
if not default_db_url:
    try:
        import psycopg2  # Check if PostgreSQL driver is installed
        default_db_url = "postgresql+psycopg2://postgres:postgres@localhost:5432/roadsentinel"
    except ImportError:
        default_db_url = "sqlite:///./roadsentinel.db"

class Settings(BaseSettings):
    PROJECT_NAME: str = "ROADSentinel Engine"
    API_V1_STR: str = "/api/v1"
    
    # Security (Loaded from environment, with secure production check)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "roadsentinel_secret_key_v0_4_production_secure_key_12345")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    DEVICE_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30 # 30 days
    
    # Database (PostgreSQL + PostGIS as authoritative v1 datastore per Spec §3.1)
    DATABASE_URL: str = default_db_url
    
    # Media Storage
    MEDIA_UPLOAD_DIR: str = os.path.join(os.path.dirname(__file__), "..", "uploads")
    DEFAULT_MEDIA_RETENTION_DAYS: int = 90
    
    # Google Maps API Integration
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "AIzaSyBJVFpSHvA5O9U0UutJK6Vusx3UJ2Ez7-k")
    
    # Raw Threshold Classification Parameters (ESP32 Baseline)
    IMU_ACCEL_THRESHOLD_HIGH: float = 18.0  # m/s^2 z-axis spike -> High Severity
    IMU_ACCEL_THRESHOLD_MED: float = 14.0   # m/s^2 z-axis spike -> Med Severity
    IMU_ACCEL_THRESHOLD_LOW: float = 11.5   # m/s^2 z-axis spike -> Low Severity
    
    # Corroboration & Geohash Precision
    CORROBORATION_DISTANCE_METERS: float = 25.0 # Spatial radius to match corroboration events
    CORROBORATION_TIME_WINDOW_MINS: int = 1440   # 24 hours
    
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

settings = Settings()

os.makedirs(settings.MEDIA_UPLOAD_DIR, exist_ok=True)
