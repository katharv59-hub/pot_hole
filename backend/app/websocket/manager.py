import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger("websocket_manager")

class ConnectionManager:
    def __init__(self):
        # Active connections mapping: websocket -> bbox [min_lon, min_lat, max_lon, max_lat]
        self.active_connections: Dict[WebSocket, Optional[List[float]]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = None
        logger.info(f"WebSocket client connected. Total active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]
            logger.info(f"WebSocket client disconnected. Total active: {len(self.active_connections)}")

    def update_subscription(self, websocket: WebSocket, bbox: List[float]):
        """Updates the subscribed bounding box [min_lon, min_lat, max_lon, max_lat] for a client."""
        if len(bbox) == 4:
            self.active_connections[websocket] = bbox
            logger.info(f"Updated bbox subscription for client: {bbox}")

    async def broadcast_event(self, event_type: str, event_data: Dict[str, Any]):
        """
        Broadcasts event_created or event_updated to clients whose subscribed bbox includes the event location.
        """
        message = {
            "type": event_type,
            "event": event_data
        }
        
        lat = event_data.get("latitude")
        lon = event_data.get("longitude")
        
        to_remove = []
        for ws, bbox in self.active_connections.items():
            # If client has a bbox subscription, check point-in-bbox
            if bbox and len(bbox) == 4 and lat is not None and lon is not None:
                min_lon, min_lat, max_lon, max_lat = bbox
                if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                    continue  # Outside client's bbox
            
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception as e:
                logger.warning(f"Error sending WebSocket message: {e}")
                to_remove.append(ws)

        for ws in to_remove:
            self.disconnect(ws)

ws_manager = ConnectionManager()
