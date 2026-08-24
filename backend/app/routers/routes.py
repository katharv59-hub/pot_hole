import json
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.domain import RoadEvent, RoadSegment
from app.schemas.domain_schemas import RouteSafetyRequest, RouteSafetyResponse, RoadEventResponse
from app.services.event_service import calculate_haversine_distance_m

router = APIRouter(prefix="/routes", tags=["Route Safety Annotation"])

@router.post("/safety", response_model=RouteSafetyResponse)
def get_route_safety(req: RouteSafetyRequest, db: Session = Depends(get_db)):
    """
    Spec §15 & Frontend Spec §4.1:
    Route-risk scoring (0-100 scale). Annotates planned route polyline with hazard hazards.
    """
    if not req.polyline or len(req.polyline) < 2:
        raise HTTPException(status_code=400, detail="Polyline must contain at least 2 coordinate pairs")

    # Fetch all active/unresolved events
    active_events = db.query(RoadEvent).filter(RoadEvent.status.in_(["unverified", "verified"])).all()

    matched_hazards = []
    total_penalty = 0.0

    for pt in req.polyline:
        lat, lon = pt[0], pt[1]
        for evt in active_events:
            dist = calculate_haversine_distance_m(lat, lon, evt.latitude, evt.longitude)
            if dist <= 50.0:  # Within 50 meters of route path
                if evt not in matched_hazards:
                    matched_hazards.append(evt)
                    # Higher severity & confidence = higher safety penalty
                    penalty = (evt.severity * 25.0) * (0.8 + 0.2 * evt.confidence)
                    total_penalty += penalty

    # Overall safety score calculation (100 = perfectly safe)
    overall_score = max(0.0, min(100.0, round(100.0 - total_penalty, 1)))

    # Segment annotation
    segment_scores = []
    for i in range(len(req.polyline) - 1):
        segment_scores.append({
            "segment_index": i,
            "start_point": req.polyline[i],
            "end_point": req.polyline[i+1],
            "is_road_network_scored": False, # Flag per Spec §0 Constraint #1
            "framing_label": "Hazard Location Intelligence Stretch",
            "local_safety_score": max(50.0, overall_score)
        })

    hazards_response = [RoadEventResponse.model_validate(h) for h in matched_hazards]

    return RouteSafetyResponse(
        overall_safety_score=overall_score,
        scored_segments_count=0, # v1 baseline has 0 backfilled OSM segments
        unscored_stretches_count=len(req.polyline) - 1,
        detected_hazards_on_route=hazards_response,
        segment_scores=segment_scores
    )
