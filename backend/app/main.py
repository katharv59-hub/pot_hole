import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, Base
from app.routers import auth, devices, events, reports, telemetry, config, routes, analytics
from app.websocket.manager import ws_manager

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
async def websocket_endpoint(websocket: WebSocket):
    """Spec §7: Real-time WebSocket connection endpoint with bbox subscriptions."""
    await ws_manager.connect(websocket)
    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                if msg.get("type") == "subscribe" and "bbox" in msg:
                    ws_manager.update_subscription(websocket, msg["bbox"])
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
