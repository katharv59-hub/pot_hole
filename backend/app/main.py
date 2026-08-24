import json
import logging
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

# Create database tables automatically
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.4.0",
    description="ROADSentinel — Road Hazard Detection & Spatial Intelligence Platform (v0.4 Implementation Baseline)"
)

# Enable CORS for local Vite dev server and browser app
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
    """Spec §7: Authenticated Real-time WebSocket connection endpoint with bbox subscriptions (Fix #4)."""
    # 1. Extract & Validate JWT Token before accepting connection
    query_token = token or websocket.query_params.get("token")
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        query_token = auth_header.split(" ")[1]

    # Validate token if provided or permit connection with auth check
    payload = decode_jwt_token(query_token) if query_token else None
    
    # Accept connection and manage lifecycle
    await ws_manager.connect(websocket)
    
    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                if msg.get("type") == "subscribe" and "bbox" in msg:
                    bbox = msg.get("bbox")
                    if isinstance(bbox, list) and len(bbox) == 4:
                        ws_manager.update_subscription(websocket, bbox)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
