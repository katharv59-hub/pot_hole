import json
import httpx
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.domain import RoadEvent
from app.schemas.domain_schemas import RouteSafetyRequest, RouteSafetyResponse, RoadEventResponse
from app.services.event_service import calculate_haversine_distance_m
from app.config import settings

router = APIRouter(prefix="/routes", tags=["Route Safety Annotation"])

def decode_polyline(polyline_str: str) -> List[List[float]]:
    """Decodes Google Maps encoded polyline string into [[lat, lon], ...]."""
    index, lat, lng = 0, 0, 0
    coordinates = []
    length = len(polyline_str)

    while index < length:
        b, shift, result = 0, 0, 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        shift, result = 0, 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        coordinates.append([lat / 1e5, lng / 1e5])

    return coordinates


async def fetch_google_directions(origin: str, destination: str) -> Optional[List[List[float]]]:
    """Queries Google Maps Directions API for driving polyline."""
    if not settings.GOOGLE_MAPS_API_KEY:
        return None
        
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": destination,
        "key": settings.GOOGLE_MAPS_API_KEY
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("routes") and len(data["routes"]) > 0:
                encoded_poly = data["routes"][0]["overview_polyline"]["points"]
                return decode_polyline(encoded_poly)
    return None


@router.post("/safety", response_model=RouteSafetyResponse)
async def get_route_safety(
    req: RouteSafetyRequest,
    origin: Optional[str] = Query(None, description="e.g. Bandra West, Mumbai"),
    destination: Optional[str] = Query(None, description="e.g. Andheri East, Mumbai"),
    db: Session = Depends(get_db)
):
    """
    Spec §0 Constraint #1, Spec §13, §15 & Phase 8:
    Annotates spatial hazard risk along a trip polyline.
    Strict Framing: Polyline stretches without official road_segment_id mapping are framed
    strictly as 'Hazard Location Intelligence Stretches', never as fabricated official RoadSegments.
    """
    polyline = req.polyline

    # Query Google Maps Directions API if origin & destination are provided
    if origin and destination:
        google_poly = await fetch_google_directions(origin, destination)
        if google_poly:
            polyline = google_poly

    if not polyline or len(polyline) < 2:
        raise HTTPException(status_code=400, detail="Must provide valid polyline or origin & destination search parameters")

    # Query active spatial hazards along path
    active_events = db.query(RoadEvent).filter(RoadEvent.status.in_(["unverified", "verified"])).all()

    matched_hazards = []
    total_penalty = 0.0

    for pt in polyline:
        lat, lon = pt[0], pt[1]
        for evt in active_events:
            dist = calculate_haversine_distance_m(lat, lon, evt.latitude, evt.longitude)
            if dist <= 50.0:  # Within 50 meters of driving path
                if evt not in matched_hazards:
                    matched_hazards.append(evt)
                    penalty = (evt.severity * 25.0) * (0.8 + 0.2 * evt.confidence)
                    total_penalty += penalty

    overall_score = max(0.0, min(100.0, round(100.0 - total_penalty, 1)))

    # Phase 8: Do NOT fabricate official RoadSegment objects.
    # Framed as Hazard Location Intelligence Stretches.
    segment_stretches = []
    for i in range(len(polyline) - 1):
        segment_stretches.append({
            "stretch_index": i,
            "start_point": polyline[i],
            "end_point": polyline[i+1],
            "is_road_network_scored": False, # Official segment score requires backfilled road_segment_id
            "framing_label": "Hazard Location Intelligence Stretch",
            "hazard_density_penalty": round(total_penalty / (len(polyline) - 1), 2)
        })

    hazards_response = [RoadEventResponse.model_validate(h) for h in matched_hazards]

    return RouteSafetyResponse(
        overall_safety_score=overall_score,
        scored_segments_count=0, # 0 fabricated official segments per Phase 8
        unscored_stretches_count=len(polyline) - 1,
        detected_hazards_on_route=hazards_response,
        segment_scores=segment_stretches
    )
