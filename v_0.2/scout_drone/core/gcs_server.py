"""
GCS (Ground Control Station) WebSocket Server.

This server runs as part of the MissionController and provides a link
to a web-based frontend (gcs_frontend.html).
"""
import asyncio
import json
import websockets
from typing import Set
from .config_models import GcsConfig
from .drone import Telemetry, Drone

# Forward declaration for type hinting
class MissionController:
    pass

class GcsServer:
    """
    Manages WebSocket communication with GCS clients.
    """
    
    def __init__(self, config: GcsConfig, controller: 'MissionController'):
        self.config = config
        self.controller = controller
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        print(f"[GcsServer] Initialized. Will listen on {config.host}:{config.port}")

    async def _register(self, websocket: websockets.WebSocketServerProtocol):
        """Register a new GCS client."""
        self.clients.add(websocket)
        print(f"[GcsServer] Client connected: {websocket.remote_address}. Total clients: {len(self.clients)}")

    async def _unregister(self, websocket: websockets.WebSocketServerProtocol):
        """Unregister a GCS client."""
        self.clients.remove(websocket)
        print(f"[GcsServer] Client disconnected: {websocket.remote_address}. Total clients: {len(self.clients)}")

    async def _handle_message(self, message: str):
        """Handle incoming messages from a GCS client."""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'CONFIRM_TARGET':
                print("[GcsServer] Received CONFIRM_TARGET from operator.")
                # This calls the method on MissionController
                await self.controller.operator_confirm_target()
                
            elif msg_type == 'REJECT_TARGET':
                print("[GcsServer] Received REJECT_TARGET from operator.")
                # This calls the method on MissionController
                await self.controller.operator_reject_target()
                
            else:
                print(f"[GcsServer] Unknown message type: {msg_type}")
                
        except json.JSONDecodeError:
            print(f"[GcsServer] Received invalid JSON: {message}")
        except Exception as e:
            print(f"[GcsServer] Error handling message: {e}")

    async def _connection_handler(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """Handle a single client connection's lifecycle."""
        await self._register(websocket)
        try:
            # Listen for incoming messages
            async for message in websocket:
                await self._handle_message(str(message))
        except websockets.exceptions.ConnectionClosed:
            print(f"[GcsServer] Connection closed by client.")
        finally:
            await self._unregister(websocket)

    async def run(self):
        """Start the WebSocket server."""
        print(f"[GcsServer] Starting server on ws://{self.config.host}:{self.config.port}...")
        try:
            server = await websockets.serve(
                self._connection_handler,
                self.config.host,
                self.config.port
            )
            await server.wait_closed()
        except OSError as e:
            print(f"[GcsServer] FATAL: Could not start server (port {self.config.port} likely in use). {e}")
            # This will propagate to the main MissionController loop
            raise
            
    async def broadcast(self, payload: dict):
        """Send a JSON payload to all connected clients."""
        if not self.clients:
            return # No one to send to
        
        message = json.dumps(payload)
        
        # Use asyncio.gather to send to all clients concurrently
        tasks = [client.send(message) for client in self.clients]
        await asyncio.gather(*tasks, return_exceptions=True)
        
    async def broadcast_telemetry(self, telemetry: 'Telemetry', state: str):
        """Helper function to format and broadcast telemetry."""
        payload = {
            "type": "telemetry",
            "data": {
                "drone_id": telemetry.id, # Note: This is Drone.id, not Telemetry.id
                "position": {
                    "x": round(telemetry.position.x, 2),
                    "y": round(telemetry.position.y, 2),
                    "z": round(telemetry.position.z, 2),
                },
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
        """Helper function to format and broadcast a special event."""
        payload = {
            "type": event_type,
            "data": data
        }
        await self.broadcast(payload)
