import json
import logging
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, Base
from app.routers import auth, devices, events, reports, telemetry, config, routes, analytics
from app.websocket.manager import ws_manager
from app.auth.security import decode_jwt_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("roadsentinel_backend")

# Production schema management is strictly authoritative via Alembic migrations.

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.4.0",
    description="ROADSentinel — Road Hazard Detection & Spatial Intelligence Platform (v0.4 Implementation Baseline)"
)

# Enable CORS for Vite dev server and web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static media upload handler
app.mount("/uploads", StaticFiles(directory=settings.MEDIA_UPLOAD_DIR), name="uploads")

# Mount API Routers under /api/v1
api_prefix = settings.API_V1_STR
app.include_router(auth.router, prefix=api_prefix)
app.include_router(devices.router, prefix=api_prefix)
app.include_router(events.router, prefix=api_prefix)
app.include_router(reports.router, prefix=api_prefix)
app.include_router(telemetry.router, prefix=api_prefix)
app.include_router(config.router, prefix=api_prefix)
app.include_router(routes.router, prefix=api_prefix)
app.include_router(analytics.router, prefix=api_prefix)


@app.get("/")
def root():
    return {
        "status": "online",
        "system": settings.PROJECT_NAME,
        "spec_version": "v0.4 baseline",
        "documentation": "/docs"
    }


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(None)
):
    """Spec §7 & Phase 6: Authenticated Real-time WebSocket connection endpoint."""
    # 1. Extract token from query parameter or Authorization header
    query_token = token or websocket.query_params.get("token")
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        query_token = auth_header.split(" ")[1]

    # 2. Reject missing token (Phase 6 requirement)
    if not query_token:
        logger.warning("WebSocket connection attempt rejected: missing authentication token.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication token missing")
        return

    # 3. Validate token before accepting connection (Phase 6 requirement)
    payload = decode_jwt_token(query_token)
    if not payload:
        logger.warning("WebSocket connection attempt rejected: invalid or expired access token.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired access token")
        return

    # 4. Accept connection after successful authentication
    await ws_manager.connect(websocket)
    
    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                if msg.get("type") == "subscribe" and "bbox" in msg:
                    bbox = msg.get("bbox")
                    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                        try:
                            min_lon, min_lat, max_lon, max_lat = [float(c) for c in bbox]
                            if (-180.0 <= min_lon <= 180.0 and -180.0 <= max_lon <= 180.0 and
                                -90.0 <= min_lat <= 90.0 and -90.0 <= max_lat <= 90.0 and
                                min_lon <= max_lon and min_lat <= max_lat):
                                ws_manager.update_subscription(websocket, [min_lon, min_lat, max_lon, max_lat])
                                await websocket.send_text(json.dumps({
                                    "type": "subscription_ack",
                                    "bbox": [min_lon, min_lat, max_lon, max_lat]
                                }))
                            else:
                                await websocket.send_text(json.dumps({
                                    "type": "error",
                                    "message": "Invalid bbox coordinates: bounds must be [minLon, minLat, maxLon, maxLat] with valid geographical ranges."
                                }))
                        except (ValueError, TypeError):
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": "Malformed bbox: coordinates must be numeric."
                            }))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Malformed bbox: expected 4-element array [minLon, minLat, maxLon, maxLat]."
                        }))
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON message payload."
                }))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
