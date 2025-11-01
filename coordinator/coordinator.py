"""
The Coordinator: Central brain for the Drone-MOB fleet.
- Manages fleet state (who is online, what is their status).
- Listens for events (e.g., GCS 'Trigger MOB' button).
- Dispatches commands to drones via MQTT.
- Forwards telemetry and events from MQTT to the GCS.
"""

import asyncio
import time
import traceback
from typing import Dict, Any

# --- Robust Import Logic ---
import sys
from pathlib import Path
FILE = Path(__file__).resolve()
ROOT = FILE.parent.parent
CORE_PATH = ROOT / "v_0_2" / "scout_drone"
if str(CORE_PATH) not in sys.path:
    sys.path.append(str(CORE_PATH))
# --- End Import Logic ---

from core.config_models import Settings, DroneConfig
from core.comms import MqttClient
from core.drone import Telemetry
from core.position import Position
from coordinator.gcs_server import GcsServer # Uses relative import

class FleetVehicle:
    """A simple class to hold the last known state of a fleet vehicle."""
    def __init__(self, config: DroneConfig): # <-- FIX: Type hint
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
                traceback.print_exc() # Added for detailed debugging

    # --- MQTT Handlers ---

    async def _handle_connect(self, payload: dict):
        """Handle a drone announcing it's online."""
        drone_id = payload.get('drone_id')
        if drone_id in self.fleet:
            print(f"[Coordinator] Drone '{drone_id}' connected.")
            self.fleet[drone_id].mission_phase = "IDLE"
            self.fleet[drone_id].last_seen = time.time()
        else:
            print(f"[Coordinator] Warning: Unknown drone connected: {drone_id}")

    async def _handle_telemetry(self, drone_id: str, payload: dict):
        """Handle incoming telemetry and forward to GCS."""
        if drone_id in self.fleet:
            try:
                # --- FIX: CRITICAL PARSING BUG ---
                # The payload['position'] is a dict. We must convert
                # it to a Position object *before* parsing the Telemetry.
                if 'position' in payload and isinstance(payload['position'], dict):
                    payload['position'] = Position(**payload['position'])
                # ---------------------------------
                
                telemetry = Telemetry(**payload)
                self.fleet[drone_id].telemetry = telemetry
                self.fleet[drone_id].last_seen = time.time()
                
                # Forward to GCS
                await self.gcs.broadcast_telemetry(
                    drone_id,
                    telemetry,
                    self.fleet[drone_id].mission_phase
                )
            except Exception as e:
                print(f"[Coordinator] Error parsing telemetry from '{drone_id}': {e}")
        
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
            payload_data = payload.get('data', {})
            payload_data['drone_id'] = drone_id # Ensure drone_id is in the data
            await self.gcs.broadcast_event('PENDING_CONFIRMATION', payload_data)
        
        # --- FIX: ADDED MISSING LOGIC ---
        elif event_type == 'TARGET_DELIVERY_REQUEST':
            # The scout has confirmed a target and is requesting payload delivery
            target_pos_dict = payload.get('data', {}).get('position')
            if target_pos_dict:
                await self._task_payload_drone(Position(**target_pos_dict))
            else:
                print(f"[Coordinator] Error: TARGET_DELIVERY_REQUEST from {drone_id} had no position.")
        # --------------------------------

    # --- GCS Command Handlers ---

    async def handle_operator_confirmation(self, drone_id: str | None):
        """Send 'CONFIRM_TARGET' command to the specific drone."""
        if not drone_id:
            print("[Coordinator] Error: Operator confirmed, but no drone_id provided.")
            return
        print(f"[Coordinator] Relaying CONFIRM_TARGET to '{drone_id}'")
        await self.mqtt.publish(f"drone/command/{drone_id}", {
            "command": "OPERATOR_CONFIRM_TARGET"
        })
        await self.gcs.broadcast_event("TARGET_CONFIRMED", {"drone_id": drone_id})

    async def handle_operator_rejection(self, drone_id: str | None):
        """Send 'REJECT_TARGET' command to the specific drone."""
        if not drone_id:
            print("[Coordinator] Error: Operator rejected, but no drone_id provided.")
            return
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
        scout_available = scout and self.fleet[scout].mission_phase in ["IDLE", "PATROLLING"]

        if scout_available:
            print(f"[Coordinator] Tasking Scout '{scout}' to begin search.")
            await self.mqtt.publish(f"drone/command/{scout}", {
                "command": "START_MISSION",
                "type": "MOB_SEARCH"
            })
        else:
            print(f"[Coordinator] Primary Scout '{scout}' is busy or offline. Attempting failover.")
            # 2. Failover: Find the Utility drone
            utility = self._find_drone_by_role("utility")
            utility_available = utility and self.fleet[utility].mission_phase in ["IDLE", "PATROLLING"]
            if utility_available:
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

    # --- NEW: Added function to handle TARGET_DELIVERY_REQUEST ---
    async def _task_payload_drone(self, target_position: Position):
        """Find and task the payload drone to a specific coordinate."""
        print(f"[Coordinator] Received target position. Tasking payload drone.")
        payload_drone = self._find_drone_by_role("payload")
        payload_available = payload_drone and self.fleet[payload_drone].mission_phase in ["IDLE", "STANDBY"]

        if payload_available:
            print(f"[Coordinator] Tasking Payload '{payload_drone}' to deliver to {target_position}.")
            await self.mqtt.publish(f"drone/command/{payload_drone}", {
                "command": "START_DELIVERY_MISSION",
                "position": target_position.model_dump() # Use model_dump() for Pydantic
            })
        else:
            print(f"[Coordinator] Error: Payload delivery requested but drone '{payload_drone}' is not available.")
            await self.gcs.broadcast_event("ERROR", {"message": "Payload drone not available for delivery."})
    # --------------------------------------------------------

    async def trigger_patrol_mode(self):
        """Task the Utility drone to begin its patrol pattern."""
        print("[Coordinator] === PATROL MODE TRIGGERED ===")
        utility = self._find_drone_by_role("utility")
        if utility and self.fleet[utility].mission_phase == "IDLE":
            print(f"[Coordinator] Tasking Utility '{utility}' to begin patrol.")
            await self.mqtt.publish(f"drone/command/{utility}", {
                "command": "START_PATROL"
            })
        else:
            print(f"[Coordinator] Utility drone '{utility}' is busy or not available.")
            await self.gcs.broadcast_event("ERROR", {"message": "Utility drone is not available."})
            
    async def trigger_overwatch_mode(self, data: dict):
        """Task an available drone to orbit a point of interest."""
        print("[Coordinator] === OVERWATCH MODE TRIGGERED ===")
        target_pos = Position(**data.get('position', {}))
        
        # Find the best drone for the job (Utility > Scout)
        drone_to_task = None
        utility = self._find_drone_by_role("utility")
        if utility and self.fleet[utility].mission_phase in ["IDLE", "PATROLLING"]:
            drone_to_task = utility
        else:
            scout = self._find_drone_by_role("scout")
            if scout and self.fleet[scout].mission_phase in ["IDLE", "PATROLLING"]:
                drone_to_task = scout
        
        if drone_to_task:
            print(f"[Coordinator] Tasking '{drone_to_task}' to overwatch {target_pos}.")
            await self.mqtt.publish(f"drone/command/{drone_to_task}", {
                "command": "START_OVERWATCH",
                "position": target_pos.model_dump()
            })
        else:
            print(f"[Coordinator] No available drone for overwatch.")
            await self.gcs.broadcast_event("ERROR", {"message": "No drone available for overwatch."})

    def _find_drone_by_role(self, role: str) -> str | None:
        """Find the first available drone_id for a given role."""
        for drone_id, vehicle in self.fleet.items():
            if vehicle.config.role == role:
                return drone_id
        return None

