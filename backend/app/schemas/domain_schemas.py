from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, EmailStr, Field

# --- User & Auth Schemas ---

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Optional[str] = "driver" # driver, admin, authority

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    saved_locations: Optional[List[Dict[str, Any]]] = []

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- Device & Provisioning Schemas ---

class DeviceRegisterRequest(BaseModel):
    hardware_type: Optional[str] = "ESP32"
    firmware_version: Optional[str] = "1.0.0"
    vehicle_id: Optional[str] = None

class DeviceRegisterResponse(BaseModel):
    device_id: str
    provisioning_secret: str
    status: str

class DeviceProvisionRequest(BaseModel):
    provisioning_secret: str

class DeviceProvisionResponse(BaseModel):
    device_id: str
    device_credential: str
    status: str

class DeviceAuthRequest(BaseModel):
    device_credential: str

class DeviceAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    device_id: str
    vehicle_id: Optional[str]

class DeviceReassignRequest(BaseModel):
    new_vehicle_id: str

class DeviceResponse(BaseModel):
    id: str
    vehicle_id: Optional[str]
    hardware_type: str
    firmware_version: str
    status: str
    last_seen_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Vehicle Schemas ---

class VehicleCreate(BaseModel):
    type: str = "car" # 2-wheeler, car, bus, truck, fleet, other
    owner_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = {}

class VehicleResponse(BaseModel):
    id: str
    type: str
    owner_id: Optional[str]
    metadata_json: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


# --- RoadEvent Ingestion & Query Schemas ---

class LocationSchema(BaseModel):
    latitude: float
    longitude: float
    accuracy_m: Optional[float] = None
    source: str = "gnss" # gnss, network, fused

class ModelOutputSchema(BaseModel):
    model_name: Optional[str] = "imu-rf-v1"
    model_version: Optional[str] = "1.4.2"
    inference_location: Optional[str] = "edge"

class EventIngestionRequest(BaseModel):
    schema_version: str = "1.0"
    device_event_id: str  # Mandatory idempotency key
    vehicle_id: str       # Cross-checked against server-resolved device assignment
    device_timestamp: datetime
    location: LocationSchema
    speed_mps: Optional[float] = None
    event_type: Optional[str] = None # Optional if raw mode
    confidence: Optional[float] = None
    severity: Optional[float] = None
    modality_sources: List[str] = ["imu"]
    model_output: Optional[ModelOutputSchema] = None
    sensor_data: Optional[Dict[str, Any]] = None # Raw IMU data window
    firmware_version: str = "1.0.0"

class EventIngestionResponse(BaseModel):
    event_id: str
    device_event_id: str
    status: str  # accepted | duplicate | rejected
    duplicate_of: Optional[str] = None
    server_timestamp: datetime
    corroboration_count: int
    warnings: Optional[List[str]] = []

class EventStatusPatch(BaseModel):
    status: str  # verified | duplicate | resolved

class MediaAssetResponse(BaseModel):
    id: str
    event_id: Optional[str]
    report_id: Optional[str]
    type: str
    storage_url: str
    captured_at: datetime
    retention_expires_at: Optional[datetime]
    access_tier: str

    class Config:
        from_attributes = True

class MLPredictionResponse(BaseModel):
    id: str
    modality: str
    model_name: str
    model_version: str
    predicted_type: str
    confidence: float
    inference_location: str
    fused_from: Optional[List[str]]

    class Config:
        from_attributes = True

class RoadEventResponse(BaseModel):
    id: str
    device_event_id: str
    device_id: str
    vehicle_id: str
    device_timestamp: datetime
    server_timestamp: datetime
    latitude: float
    longitude: float
    location_accuracy_m: Optional[float]
    location_source: str
    road_segment_id: Optional[str]
    event_type: str
    modality_sources: List[str]
    confidence: float
    severity: float
    severity_label: str
    status: str
    schema_version: str
    firmware_version: str
    corroboration_count: int
    media_assets: Optional[List[MediaAssetResponse]] = []
    ml_predictions: Optional[List[MLPredictionResponse]] = []

    class Config:
        from_attributes = True


# --- Telemetry Ingestion Schema ---

class TelemetryIngestionRequest(BaseModel):
    vehicle_id: str
    device_timestamp: datetime
    latitude: float
    longitude: float
    raw_payload: Dict[str, Any]
    label: Optional[str] = None
    linked_event_id: Optional[str] = None


# --- Manual Report Schemas ---

class ReportCreate(BaseModel):
    latitude: float
    longitude: float
    description: Optional[str] = None

class ReportResponse(BaseModel):
    id: str
    user_id: str
    event_id: Optional[str]
    description: Optional[str]
    latitude: float
    longitude: float
    status: str
    created_at: datetime
    media_assets: Optional[List[MediaAssetResponse]] = []

    class Config:
        from_attributes = True


# --- Media Pre-signed Upload Schemas ---

class UploadUrlResponse(BaseModel):
    media_id: str
    upload_url: str
    expires_in_seconds: int = 3600


# --- Dynamic Config Schemas ---

class EventTypeConfig(BaseModel):
    key: str
    label: str
    icon: str
    description: str

class SeverityScaleConfig(BaseModel):
    min_val: float
    max_val: float
    buckets: Dict[str, Dict[str, Any]] # low: {min: 0.0, max: 0.4, color: "#22c55e", label: "Low"}

class VehicleTypeConfig(BaseModel):
    key: str
    label: str
    icon: str

class ConfigBundleResponse(BaseModel):
    event_types: List[EventTypeConfig]
    severity_scale: SeverityScaleConfig
    vehicle_types: List[VehicleTypeConfig]


# --- Route Safety & Analytics Schemas ---

class RouteSafetyRequest(BaseModel):
    polyline: List[List[float]] # [[lat, lon], ...]

class RouteSafetyResponse(BaseModel):
    overall_safety_score: float # 0 - 100
    scored_segments_count: int
    unscored_stretches_count: int
    detected_hazards_on_route: List[RoadEventResponse]
    segment_scores: List[Dict[str, Any]]
