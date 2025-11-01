"""
GCS (Ground Control Station) WebSocket Server.
(Refactored to handle video frame broadcasts)
"""
import asyncio
import json
import websockets
import base64 # NEW
import cv2 # NEW
import numpy as np # NEW
from typing import Set

# --- Robust Import Logic ---
import sys
from pathlib import Path
FILE = Path(__file__).resolve()
ROOT = FILE.parent.parent
CORE_PATH = ROOT / "v_0_2" / "scout_drone"
if str(CORE_PATH) not in sys.path:
    sys.path.append(str(CORE_PATH))
# --- End Import Logic ---

from core.config_models import GcsConfig
from core.drone import Telemetry
from core.position import Position

# --- Type Hinting ---
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .coordinator import Coordinator
    from .media_server import MediaServer

class GcsServer:
    """
    Manages WebSocket communication with GCS clients.
    """
    
    def __init__(self, config: GcsConfig):
        self.config = config
        self.controller: 'Coordinator' | None = None
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        print(f"[GcsServer] Initialized. Will listen on {config.host}:{config.port}")
    
    def set_controller(self, controller: 'Coordinator'):
        # ... (no change)
        self.controller = controller

    async def _register(self, websocket: websockets.WebSocketServerProtocol):
        # ... (no change)
        self.clients.add(websocket)
        print(f"[GcsServer] Client connected: {websocket.remote_address}. Total clients: {len(self.clients)}")

    async def _unregister(self, websocket: websockets.WebSocketServerProtocol):
        # ... (no change)
        self.clients.remove(websocket)
        print(f"[GcsServer] Client disconnected: {websocket.remote_address}. Total clients: {len(self.clients)}")

    async def _handle_message(self, message: str):
        # ... (no change from previous version)
        if not self.controller:
            print("[GcsServer] Error: Controller not set. Ignoring message.")
            return
            
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'TRIGGER_MOB_MODE':
                print("[GcsServer] Received TRIGGER_MOB_MODE from operator.")
                await self.controller.trigger_mob_event()
            
            elif msg_type == 'CONFIRM_TARGET':
                print("[GcsServer] Received CONFIRM_TARGET from operator.")
                await self.controller.handle_operator_confirmation(data.get('drone_id'))
                
            elif msg_type == 'REJECT_TARGET':
                print("[GcsServer] Received REJECT_TARGET from operator.")
                await self.controller.handle_operator_rejection(data.get('drone_id'))
            
            elif msg_type == 'TRIGGER_PATROL_MODE':
                print("[GcsServer] Received TRIGGER_PATROL_MODE from operator.")
                await self.controller.trigger_patrol_mode()
            
            elif msg_type == 'TRIGGER_OVERWATCH_MODE':
                print("[GcsServer] Received TRIGGER_OVERWATCH_MODE from operator.")
                default_pos = {"x": 100, "y": 100, "z": 0}
                pos_data = data.get('data', {"position": default_pos})
                await self.controller.trigger_overwatch_mode(pos_data)

            else:
                print(f"[GcsServer] Unknown message type: {msg_type}")
                
        except json.JSONDecodeError:
            print(f"[GcsServer] Received invalid JSON: {message}")
        except Exception as e:
            print(f"[GcsServer] Error handling message: {e}")

    async def _connection_handler(self, websocket: websockets.WebSocketServerProtocol, path: str):
        # ... (no change)
        await self._register(websocket)
        try:
            async for message in websocket:
                await self._handle_message(str(message))
        except websockets.exceptions.ConnectionClosed:
            print(f"[GcsServer] Connection closed by client.")
        finally:
            await self._unregister(websocket)

    async def run(self):
        # ... (no change)
        print(f"[GcsServer] Starting server on ws://{self.config.host}:{self.config.port}...")
        try:
            server = await websockets.serve(
                self._connection_handler,
                self.config.host,
                self.config.port,
                max_size=1_000_000 # Increase max message size if needed
            )
            await server.wait_closed()
        except OSError as e:
            print(f"[GcsServer] FATAL: Could not start server (port {self.config.port} likely in use). {e}")
            raise
            
    async def broadcast(self, payload: dict):
        # ... (no change)
        if not self.clients:
            return
        message = json.dumps(payload, default=vars)
        tasks = [client.send(message) for client in self.clients]
        await asyncio.gather(*tasks, return_exceptions=True)

    # --- NEW: Video Frame Broadcast Method ---
    
    async def broadcast_video_frame(self, frame: np.ndarray):
        """Encode a numpy frame and broadcast it as a base64 string."""
        if not self.clients:
            return # Don't waste CPU encoding if no one is watching
        
        try:
            # 1. Encode the frame as JPEG
            # Use low quality for high speed
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if not ret:
                print("[GcsServer] Error: Could not encode video frame.")
                return
            
            # 2. Convert to base64 string
            frame_b64 = base64.b64encode(buffer).decode('utf-8')
            
            # 3. Create payload
            payload = {
                "type": "video_frame",
                "data": frame_b64
            }
            
            # 4. Broadcast to all clients
            message = json.dumps(payload)
            tasks = [client.send(message) for client in self.clients]
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            # Catch errors (e.g., client disconnected mid-send)
            print(f"[GcsServer] Error broadcasting video frame: {e}")
        
    async def broadcast_telemetry(self, drone_id: str, telemetry: Telemetry, state: str):
        # ... (no change from previous version)
        payload = {
            "type": "telemetry",
            "data": {
                "drone_id": drone_id,
                "position": telemetry.position.model_dump(),
                "attitude": {
                    "roll": round(telemetry.attitude_roll, 1),
                    "pitch": round(telemetry.attitude_pitch, 1),
                    "yaw": round(telemetry.attitude_yaw, 1),
                },
                "battery": round(telemetry.battery, 1),
                "state": telemetry.state,
                "mission_phase": state,
            }
        }
        await self.broadcast(payload)

    async def broadcast_event(self, event_type: str, data: dict):
        # ... (no change from previous version)
        payload = {
            "type": event_type,
            "data": data
        }
        await self.broadcast(payload)

