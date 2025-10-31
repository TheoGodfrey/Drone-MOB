"""
The Coordinator: Central brain for the Drone-MOB fleet.
- Manages fleet state (who is online, what is their status).
- Listens for events (e.g., GCS 'Trigger MOB' button).
- Dispatches commands to drones via MQTT.
- Forwards telemetry and events from MQTT to the GCS.
"""

import asyncio
import time
from typing import Dict, Any

# --- Robust Import Logic ---
import sys
from pathlib import Path
# Get the absolute path of this file (e.g., /path/to/drone-mob/coordinator/coordinator.py)
FILE = Path(__file__).resolve()
# Get the project root (e.g., /path/to/drone-mob)
ROOT = FILE.parent.parent
# Add the directory containing the 'core' package to the system path
CORE_PATH = ROOT / "v_0.2" / "scout_drone"
if str(CORE_PATH) not in sys.path:
    sys.path.append(str(CORE_PATH))
# --- End Import Logic ---

from core.config_models import Settings, DroneConfig
from core.comms import MqttClient
from core.drone import Telemetry
from core.position import Position  # <--- CORRECTION: Added missing import
from coordinator.gcs_server import GcsServer # Uses relative import

class FleetVehicle:
    """A simple class to hold the last known state of a fleet vehicle."""
    def __init__(self, config):
        self.config = config
        self.telemetry: Telemetry | None = None
        self.mission_phase: str = "UNKNOWN"
        self.last_seen: float = 0.0

class Coordinator:
    """Manages all fleet operations."""
    
    def __init__(self, config: Settings, mqtt: MqttClient, gcs: GcsServer):
        self.config = config
        self.mqtt = mqtt
        self.gcs = gcs
        self.fleet: Dict[str, FleetVehicle] = {}
        
        # Initialize fleet from config
        for drone_cfg in config.drones:
            self.fleet[drone_cfg.id] = FleetVehicle(drone_cfg)
            print(f"[Coordinator] Registered drone: {drone_cfg.id} (Role: {drone_cfg.role})")

    async def run(self):
        """Main run loop for the Coordinator."""
        print("[Coordinator] Running. Subscribing to fleet topics...")
        
        # Subscribe to all relevant fleet topics
        await self.mqtt.subscribe("fleet/connect")
        await self.mqtt.subscribe("fleet/telemetry/+") # '+' is a single-level wildcard
        await self.mqtt.subscribe("fleet/state/+")
        await self.mqtt.subscribe("fleet/event/+")

        # Listen for messages from drones and GCS
        async for topic, payload in self.mqtt.listen():
            try:
                if topic == "fleet/connect":
                    await self._handle_connect(payload)
                elif topic.startswith("fleet/telemetry/"):
                    drone_id = topic.split('/')[-1]
                    await self._handle_telemetry(drone_id, payload)
                elif topic.startswith("fleet/state/"):
                    drone_id = topic.split('/')[-1]
                    await self._handle_state(drone_id, payload)
                elif topic.startswith("fleet/event/"):
                    drone_id = topic.split('/')[-1]
                    await self._handle_event(drone_id, payload)
            except Exception as e:
                print(f"[Coordinator] Error handling MQTT message on {topic}: {e}")

    # --- MQTT Handlers ---

    async def _handle_connect(self, payload: dict):
        """Handle a drone announcing it's online."""
        drone_id = payload.get('drone_id')
        if drone_id in self.fleet:
            print(f"[Coordinator] Drone '{drone_id}' connected.")
            self.fleet[drone_id].mission_phase = "IDLE"
            # We could send a 'config' message back to the drone here
        else:
            print(f"[Coordinator] Warning: Unknown drone connected: {drone_id}")

    async def _handle_telemetry(self, drone_id: str, payload: dict):
        """Handle incoming telemetry and forward to GCS."""
        if drone_id in self.fleet:
            # Parse payload back into a Telemetry object
            # This is a bit simplified; real parsing would be more robust
            telemetry = Telemetry(**payload)
            self.fleet[drone_id].telemetry = telemetry
            
            # Forward to GCS
            await self.gcs.broadcast_telemetry(
                drone_id,
                telemetry,
                self.fleet[drone_id].mission_phase
            )
        
    async def _handle_state(self, drone_id: str, payload: dict):
        """Handle a drone reporting a change in its mission phase."""
        if drone_id in self.fleet:
            new_state = payload.get('state', 'UNKNOWN')
            self.fleet[drone_id].mission_phase = new_state
            print(f"[Coordinator] Drone '{drone_id}' is now in state: {new_state}")
            
            # Forward this to GCS as well
            if self.fleet[drone_id].telemetry:
                await self.gcs.broadcast_telemetry(
                    drone_id,
                    self.fleet[drone_id].telemetry,
                    new_state
                )

    async def _handle_event(self, drone_id: str, payload: dict):
        """Handle special events from drones, like 'PENDING_CONFIRMATION'."""
        event_type = payload.get('type')
        print(f"[Coordinator] Received event '{event_type}' from '{drone_id}'")
        
        if event_type == 'PENDING_CONFIRMATION':
            # Add drone_id to the payload and forward to GCS
            payload['data']['drone_id'] = drone_id
            await self.gcs.broadcast_event('PENDING_CONFIRMATION', payload['data'])
    
    # --- GCS Command Handlers ---

    async def handle_operator_confirmation(self, drone_id: str | None):
        """Send 'CONFIRM_TARGET' command to the specific drone."""
        if not drone_id: return
        print(f"[Coordinator] Relaying CONFIRM_TARGET to '{drone_id}'")
        await self.mqtt.publish(f"drone/command/{drone_id}", {
            "command": "OPERATOR_CONFIRM_TARGET"
        })
        await self.gcs.broadcast_event("TARGET_CONFIRMED", {"drone_id": drone_id})

    async def handle_operator_rejection(self, drone_id: str | None):
        """Send 'REJECT_TARGET' command to the specific drone."""
        if not drone_id: return
        print(f"[Coordinator] Relaying REJECT_TARGET to '{drone_id}'")
        await self.mqtt.publish(f"drone/command/{drone_id}", {
            "command": "OPERATOR_REJECT_TARGET"
        })
        await self.gcs.broadcast_event("TARGET_REJECTED", {"drone_id": drone_id})

    async def trigger_mob_event(self):
        """
        --- THIS IS THE CORE 3-DRONE LOGIC ---
        This is the "Two-Drone Standard" (plus Utility).
        """
        print("[Coordinator] === MOB EVENT TRIGGERED ===")
        
        # 1. Find the Primary Scout
        scout = self._find_drone_by_role("scout")
        if scout and self.fleet[scout].mission_phase in ["IDLE", "PATROLLING"]:
            print(f"[Coordinator] Tasking Scout '{scout}' to begin search.")
            await self.mqtt.publish(f"drone/command/{scout}", {
                "command": "START_MISSION",
                "type": "MOB_SEARCH"
            })
        else:
            print(f"[Coordinator] Primary Scout '{scout}' is busy or offline. Attempting failover.")
            # 2. Failover: Find the Utility drone
            utility = self._find_drone_by_role("utility")
            if utility and self.fleet[utility].mission_phase in ["IDLE", "PATROLLING"]:
                print(f"[Coordinator] FAILOVER: Tasking Utility '{utility}' to begin search.")
                await self.mqtt.publish(f"drone/command/{utility}", {
                    "command": "START_MISSION",
                    "type": "MOB_SEARCH"
                })
            else:
                print(f"[Coordinator] FATAL: No available Scout or Utility drone for MOB event.")
                await self.gcs.broadcast_event("ERROR", {"message": "No available search drone."})
                return

        # 3. Find and task the Payload drone to standby
        payload_drone = self._find_drone_by_role("payload")
        if payload_drone and self.fleet[payload_drone].mission_phase == "IDLE":
            print(f"[Coordinator] Tasking Payload '{payload_drone}' to launch and standby.")
            standby_pos = self.config.strategies.search.area # TODO: Get a real standby pos
            await self.mqtt.publish(f"drone/command/{payload_drone}", {
                "command": "LAUNCH_AND_STANDBY",
                "position": {"x": standby_pos.x, "y": standby_pos.y, "z": 30.0}
            })
        else:
            print(f"[Coordinator] Warning: Payload drone '{payload_drone}' is busy or offline.")
            # The mission can continue, but delivery will fail.
            await self.gcs.broadcast_event("WARNING", {"message": "Payload drone not available."})

    def _find_drone_by_role(self, role: str) -> str | None:
        """Find the first available drone_id for a given role."""
        for drone_id, vehicle in self.fleet.items():
            if vehicle.config.role == role:
                return drone_id
        return None

