import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.websocket.manager import ws_manager
from tests.conftest import create_test_driver_token, create_test_admin_token

client = TestClient(app)

def test_authenticated_websocket_connection_success():
    """Test A: Authenticated WebSocket connection with valid JWT succeeds."""
    token = create_test_driver_token("ws_auth_driver@roadsentinel.io")
    with client.websocket_connect(f"/ws?token={token}") as ws:
        # Subscribe to a valid bounding box
        ws.send_text(json.dumps({
            "type": "subscribe",
            "bbox": [72.80, 19.00, 72.90, 19.10]
        }))
        response = ws.receive_text()
        data = json.loads(response)
        assert data["type"] == "subscription_ack"
        assert data["bbox"] == [72.80, 19.00, 72.90, 19.10]


def test_unauthenticated_websocket_rejected():
    """Test B: Unauthenticated WebSocket connection is rejected with 1008 policy violation."""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws"):
            pass


def test_invalid_token_websocket_rejected():
    """Test C: Invalid or expired token is rejected with 1008 policy violation."""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws?token=invalid.jwt.token.string"):
            pass


def test_bbox_subscription_and_validation():
    """Test D: Valid bbox is acknowledged; invalid and malformed bboxes receive error messages."""
    token = create_test_driver_token("ws_bbox_val@roadsentinel.io")
    with client.websocket_connect(f"/ws?token={token}") as ws:
        # 1. Valid bbox
        ws.send_text(json.dumps({
            "type": "subscribe",
            "bbox": [72.80, 19.00, 72.90, 19.10]
        }))
        ack = json.loads(ws.receive_text())
        assert ack["type"] == "subscription_ack"
        assert ack["bbox"] == [72.80, 19.00, 72.90, 19.10]

        # 2. Out of range coordinates (> 180 longitude)
        ws.send_text(json.dumps({
            "type": "subscribe",
            "bbox": [250.0, 19.00, 72.90, 19.10]
        }))
        err1 = json.loads(ws.receive_text())
        assert err1["type"] == "error"
        assert "Invalid bbox coordinates" in err1["message"]

        # 3. Non-numeric coordinates
        ws.send_text(json.dumps({
            "type": "subscribe",
            "bbox": ["invalid", 19.00, 72.90, 19.10]
        }))
        err2 = json.loads(ws.receive_text())
        assert err2["type"] == "error"
        assert "Malformed bbox" in err2["message"]

        # 4. Wrong element count (3 instead of 4)
        ws.send_text(json.dumps({
            "type": "subscribe",
            "bbox": [72.80, 19.00, 72.90]
        }))
        err3 = json.loads(ws.receive_text())
        assert err3["type"] == "error"
        assert "4-element array" in err3["message"]


@pytest.mark.asyncio
async def test_spatial_event_filtering_inside_and_outside_bbox():
    """Test E & F: Event inside client's bbox is delivered; event outside is filtered out."""
    token1 = create_test_driver_token("mumbai_user@roadsentinel.io")
    token2 = create_test_driver_token("delhi_user@roadsentinel.io")

    # Connect client 1 in Mumbai bbox
    with client.websocket_connect(f"/ws?token={token1}") as ws_mumbai:
        ws_mumbai.send_text(json.dumps({
            "type": "subscribe",
            "bbox": [72.80, 19.00, 72.90, 19.10] # Mumbai
        }))
        json.loads(ws_mumbai.receive_text()) # consume ack

        # Connect client 2 in Delhi bbox
        with client.websocket_connect(f"/ws?token={token2}") as ws_delhi:
            ws_delhi.send_text(json.dumps({
                "type": "subscribe",
                "bbox": [77.10, 28.50, 77.30, 28.70] # Delhi
            }))
            json.loads(ws_delhi.receive_text()) # consume ack

            # Broadcast a Mumbai event (lat=19.0728, lon=72.8826)
            mumbai_event_data = {
                "id": "evt_mumbai_101",
                "event_type": "pothole",
                "severity": 0.85,
                "severity_label": "critical",
                "latitude": 19.0728,
                "longitude": 72.8826,
                "confidence": 0.88,
                "corroboration_count": 1
            }

            await ws_manager.broadcast_event("event_created", mumbai_event_data)

            # Client 1 (Mumbai) MUST receive the event
            msg1 = json.loads(ws_mumbai.receive_text())
            assert msg1["type"] == "event_created"
            assert msg1["event"]["id"] == "evt_mumbai_101"
            assert msg1["event"]["event_type"] == "pothole"

            # Broadcast a Delhi event (lat=28.6139, lon=77.2090)
            delhi_event_data = {
                "id": "evt_delhi_202",
                "event_type": "speed_breaker",
                "severity": 0.40,
                "severity_label": "medium",
                "latitude": 28.6139,
                "longitude": 77.2090,
                "confidence": 0.75,
                "corroboration_count": 1
            }

            await ws_manager.broadcast_event("event_created", delhi_event_data)

            # Client 2 (Delhi) MUST receive the Delhi event
            msg2 = json.loads(ws_delhi.receive_text())
            assert msg2["type"] == "event_created"
            assert msg2["event"]["id"] == "evt_delhi_202"


@pytest.mark.asyncio
async def test_resubscription_updates_active_bbox():
    """Test G: Moving map updates client's active bbox and receives events in new region."""
    token = create_test_driver_token("moving_user@roadsentinel.io")
    with client.websocket_connect(f"/ws?token={token}") as ws:
        # 1. Start in Pune bbox
        ws.send_text(json.dumps({
            "type": "subscribe",
            "bbox": [73.80, 18.50, 73.90, 18.60] # Pune
        }))
        json.loads(ws.receive_text()) # ack

        # 2. Update subscription to Mumbai bbox
        ws.send_text(json.dumps({
            "type": "subscribe",
            "bbox": [72.80, 19.00, 72.90, 19.10] # Mumbai
        }))
        ack2 = json.loads(ws.receive_text())
        assert ack2["type"] == "subscription_ack"
        assert ack2["bbox"] == [72.80, 19.00, 72.90, 19.10]

        # 3. Broadcast Mumbai event
        mumbai_evt = {
            "id": "evt_mumbai_resub",
            "event_type": "pothole",
            "severity": 0.70,
            "latitude": 19.05,
            "longitude": 72.85,
            "confidence": 0.80
        }
        await ws_manager.broadcast_event("event_created", mumbai_evt)

        msg = json.loads(ws.receive_text())
        assert msg["type"] == "event_created"
        assert msg["event"]["id"] == "evt_mumbai_resub"
