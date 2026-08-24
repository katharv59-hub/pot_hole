import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "ROADSentinel Engine"
    API_V1_STR: str = "/api/v1"
    
    # Security Configuration — SECRET_KEY has no default; it MUST be provided.
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # User JWT: 24 hours
    DEVICE_TOKEN_EXPIRE_MINUTES: int = 60      # Device JWT: 1 hour (Spec §5.2)
    
    # Database Configuration (PostgreSQL + PostGIS — sole v0.4 datastore)
    DATABASE_URL: str = ""
    
    # Media Storage Configuration
    STORAGE_PROVIDER: str = "local"  # local | s3
    MEDIA_UPLOAD_DIR: str = os.path.join(os.path.dirname(__file__), "..", "uploads")
    S3_BUCKET_NAME: str = "roadsentinel-media"
    DEFAULT_MEDIA_RETENTION_DAYS: int = 90
    
    # Google Maps & Mapbox Integration
    GOOGLE_MAPS_API_KEY: str = ""
    MAPBOX_ACCESS_TOKEN: str = ""
    
    # Raw Threshold Classification Parameters (ESP32 Baseline)
    IMU_ACCEL_THRESHOLD_HIGH: float = 18.0  # m/s^2 z-axis spike -> High Severity
    IMU_ACCEL_THRESHOLD_MED: float = 14.0   # m/s^2 z-axis spike -> Med Severity
    IMU_ACCEL_THRESHOLD_LOW: float = 11.5   # m/s^2 z-axis spike -> Low Severity
    
    # Corroboration & Spatial Indexing
    CORROBORATION_DISTANCE_METERS: float = 25.0 # Spatial radius to match corroboration events
    CORROBORATION_TIME_WINDOW_MINS: int = 1440   # 24 hours
    
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

settings = Settings()

# Fail-fast validation: SECRET_KEY must be explicitly provided
if not settings.SECRET_KEY:
    raise RuntimeError(
        "FATAL: SECRET_KEY is not configured. "
        "Set SECRET_KEY to a secure random string (64+ characters) via environment variable or .env file. "
        "Do NOT use a hardcoded default in production."
    )

# Fail-fast validation: DATABASE_URL must be explicitly provided
if not settings.DATABASE_URL:
    raise RuntimeError(
        "FATAL: DATABASE_URL is not configured. "
        "Set DATABASE_URL=postgresql+psycopg2://user:pass@host:port/dbname"
    )

os.makedirs(settings.MEDIA_UPLOAD_DIR, exist_ok=True)
