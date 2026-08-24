from fastapi import APIRouter
from app.schemas.domain_schemas import (
    EventTypeConfig, SeverityScaleConfig, VehicleTypeConfig, ConfigBundleResponse
)

router = APIRouter(prefix="/config", tags=["Dynamic System Configuration"])

EVENT_TYPES = [
    EventTypeConfig(key="pothole", label="Pothole", icon="alert-circle", description="Sunken road depression or structural pit"),
    EventTypeConfig(key="speed_breaker", label="Speed Breaker", icon="shield-alert", description="Unmarked or damaged speed bump"),
    EventTypeConfig(key="crack", label="Fissure / Crack", icon="activity", description="Longitudinal or alligator road surface crack"),
    EventTypeConfig(key="waterlogging", label="Waterlogging", icon="droplet", description="Submerged or flooded road surface"),
    EventTypeConfig(key="debris", label="Debris / Obstruction", icon="box", description="Loose rocks, tire fragments, or fallen debris"),
    EventTypeConfig(key="manhole", label="Open/Uneven Manhole", icon="disc", description="Protruding, sunken, or missing manhole cover"),
    EventTypeConfig(key="edge_damage", label="Edge Damage", icon="trending-down", description="Eroded or collapsing road shoulder"),
    EventTypeConfig(key="other", label="General Hazard", icon="help-circle", description="Unclassified road anomaly")
]

SEVERITY_SCALE = SeverityScaleConfig(
    min_val=0.0,
    max_val=1.0,
    buckets={
        "low": {"min": 0.0, "max": 0.35, "color": "#22c55e", "label": "Low", "bg": "#f0fdf4"},
        "medium": {"min": 0.35, "max": 0.60, "color": "#eab308", "label": "Medium", "bg": "#fefce8"},
        "high": {"min": 0.60, "max": 0.80, "color": "#f97316", "label": "High", "bg": "#fff7ed"},
        "critical": {"min": 0.80, "max": 1.00, "color": "#ef4444", "label": "Critical", "bg": "#fef2f2"}
    }
)

VEHICLE_TYPES = [
    VehicleTypeConfig(key="2-wheeler", label="Two Wheeler / Scooter", icon="bike"),
    VehicleTypeConfig(key="car", label="Passenger Car / SUV", icon="car"),
    VehicleTypeConfig(key="bus", label="Public / Private Bus", icon="bus"),
    VehicleTypeConfig(key="truck", label="Heavy Goods Truck", icon="truck"),
    VehicleTypeConfig(key="fleet", label="Commercial Fleet Vehicle", icon="truck-fleet"),
    VehicleTypeConfig(key="other", label="Other Transport", icon="more-horizontal")
]

@router.get("/event-types", response_model=list[EventTypeConfig])
def get_event_types():
    return EVENT_TYPES

@router.get("/severity-scale", response_model=SeverityScaleConfig)
def get_severity_scale():
    return SEVERITY_SCALE

@router.get("/vehicle-types", response_model=list[VehicleTypeConfig])
def get_vehicle_types():
    return VEHICLE_TYPES

@router.get("/bundle", response_model=ConfigBundleResponse)
def get_config_bundle():
    """Frontend Spec §3: Single session-level config fetch."""
    return ConfigBundleResponse(
        event_types=EVENT_TYPES,
        severity_scale=SEVERITY_SCALE,
        vehicle_types=VEHICLE_TYPES
    )
