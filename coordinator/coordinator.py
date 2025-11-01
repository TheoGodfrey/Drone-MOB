"""
The Coordinator: Central brain for the Drone-MOB fleet.

(Refactored for Probabilistic AI and Media Server)

- Manages fleet state (who is online, what is their status).
- Listens for events (e.g., GCS 'Trigger MOB' button, drone detections).
- Dispatches commands to drones via MQTT.
- Runs the probabilistic search AI [cite: patent_1_probabilistic_search_delivery_improved.md] to guide the scout.
- Forwards all data to the GCS and Media Server.
"""

import asyncio
import time
import json
import traceback
from typing import Dict, Any

# --- Robust Import Logic ---
import sys
from pathlib import Path
# Get the absolute path of this file (e.g., /path/to/drone-mob/coordinator/coordinator.py)
FILE = Path(__file__).resolve()
# Get the project root (e.g., /path/to/drone-mob)
ROOT = FILE.parent.parent
# Add the directory containing the 'core' package to the system path
CORE_PATH = ROOT / "v_0_2" / "scout_drone"
if str(CORE_PATH) not in sys.path:
    sys.path.append(str(CORE_PATH))
# --- End Import Logic ---

from core.config_models import Settings, DroneConfig
from core.comms import MqttClient
from core.drone import Telemetry
from core.position import Position  # <-- FIX: Added missing import for Position
from coordinator.gcs_server import GcsServer
from coordinator.media_server import MediaServer
from coordinator.prob_search import ProbabilisticSearchManager

class FleetVehicle:
    """A simple class to hold the last known state of a fleet vehicle."""
    def __init__(self, config: DroneConfig):
        self.config = config
        self.telemetry: Telemetry | None = None
        self.mission_phase: str = "UNKNOWN"
        self.last_seen: float = time.time()

class Coordinator:
    """Manages all fleet operations."""
    
    def __init__(self, config: Settings, mqtt: MqttClient, gcs: GcsServer, media_server: MediaServer):
        self.config = config
        self.mqtt = mqtt
        self.gcs = gcs
        self.media_server = media_server
        self.fleet: Dict[str, FleetVehicle] = {}
        
        # The probabilistic search AI (Item 5)
        self.prob_search = ProbabilisticSearchManager(
            config.prob_search,
            config.strategies.search.area
        )
        
        # Task handle for the search loop
        self.prob_search_loop_task: asyncio.Task | None = None
        
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

        # Start a background task to evolve the probability map
        asyncio.create_task(self._evolve_map_loop())

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

    # --- NEW: Background AI Loop ---
    
    async def _evolve_map_loop(self):
        """Periodically evolves the probability map to simulate drift."""
        while True:
            await asyncio.sleep(self.config.prob_search.evolve_interval_s)
            
            # Only evolve map if a search is active
            scout = self._find_drone_by_role("scout")
            if scout and self.fleet.get(scout) and self.fleet[scout].mission_phase == "SEARCHING":
                self.prob_search.evolve_map(dt=self.config.prob_search.evolve_interval_s)
                print("[Coordinator] Evolved probability map (drift).")

    async def _probabilistic_search_loop(self, scout_id: str):
        """
        The core AI control loop (Item 5).
        Continuously finds the best place to look and sends the drone there.
        """
        print(f"[Coordinator] Starting probabilistic search loop for '{scout_id}'.")
        try:
            while True:
                # 1. Check if the scout is still searching
                if not self.fleet.get(scout_id) or self.fleet[scout_id].mission_phase != "SEARCHING":
                    print(f"[Coordinator] Scout '{scout_id}' is no longer SEARCHING. Stopping search loop.")
                    break
                    
                # 2. Get the next best waypoint from the AI
                waypoint = self.prob_search.get_next_search_waypoint()
                
                # 3. Send the drone to that waypoint
                print(f"[Coordinator] Tasking '{scout_id}' to new high-probability waypoint: {waypoint}")
                await self.mqtt.publish(f"drone/command/{scout_id}", {
                    "command": "GOTO_WAYPOINT",
                    "position": waypoint.model_dump()
                })
                
                # 4. Wait for the drone to move and scan
                await asyncio.sleep(self.config.prob_search.waypoint_interval_s)
                
        except asyncio.CancelledError:
            print(f"[Coordinator] Probabilistic search loop for '{scout_id}' cancelled.")
        except Exception as e:
            print(f"[Coordinator] FATAL ERROR in search loop: {e}")
            traceback.print_exc()

    # --- MQTT Handlers (Updated) ---

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
                # Parse payload back into a Telemetry object
                
                # <-- FIX: Re-create Position object from dict before Telemetry parsing
                if 'position' in payload and isinstance(payload['position'], dict):
                    payload['position'] = Position(**payload['position'])
                
                telemetry = Telemetry(**payload)
                self.fleet[drone_id].telemetry = telemetry
                self.fleet[drone_id].last_seen = time.time()
                
                # --- Feed data into the Probabilistic AI ---
                if self.fleet[drone_id].mission_phase == "SEARCHING":
                    # A 'ping' from a search drone is a 'no-detection' observation
                    self.prob_search.update_map(
                        drone_pos=telemetry.position,
                        drone_altitude=telemetry.position.z,
                        has_detection=False # Detections are handled by _handle_event
                    )
                
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
            old_state = self.fleet[drone_id].mission_phase
            self.fleet[drone_id].mission_phase = new_state
            self.fleet[drone_id].last_seen = time.time()
            print(f"[Coordinator] Drone '{drone_id}' state: {old_state} -> {new_state}")
            
            # --- Stop media stream if drone stops overwatch ---
            if old_state == "OVERWATCH" and new_state != "OVERWATCH":
                await self.media_server.stop_stream(drone_id)

            if self.fleet[drone_id].telemetry:
                await self.gcs.broadcast_telemetry(
                    drone_id,
                    self.fleet[drone_id].telemetry,
                    new_state
                )

    async def _handle_event(self, drone_id: str, payload: dict):
        """Handle special events from drones."""
        event_type = payload.get('type')
        print(f"[Coordinator] Received event '{event_type}' from '{drone_id}'")
        
        if event_type == 'PENDING_CONFIRMATION':
            # Forward to GCS for operator
            payload_data = payload.get('data', {})
            payload_data['drone_id'] = drone_id
            await self.gcs.broadcast_event('PENDING_CONFIRMATION', payload_data)
        
        elif event_type == 'TARGET_DELIVERY_REQUEST':
            # Scout has confirmed target and is requesting payload
            target_pos_dict = payload.get('data', {}).get('position')
            if target_pos_dict:
                # Confirm the target in the probability map
                self.prob_search.confirm_target_at(Position(**target_pos_dict))
                # Task the payload drone
                await self._task_payload_drone(Position(**target_pos_dict))
            else:
                print(f"[Coordinator] Error: TARGET_DELIVERY_REQUEST from {drone_id} had no position.")
        
        elif event_type == 'AI_DETECTION':
            # A drone's onboard AI found *something*
            det_data = payload.get('data', {})
            pos = Position(**det_data.get('position'))
            # Update the probability map with this new (unconfirmed) data
            self.prob_search.update_map(pos, pos.z, has_detection=True)


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
        --- UPDATED MOB EVENT ---
        Now uses the Probabilistic AI.
        """
        print("[Coordinator] === MOB EVENT TRIGGERED ===")
        
        # 1. Initialize the probability map
        self.prob_search.initialize_map()
        
        # 2. Find and task Scout
        scout = self._find_drone_by_role("scout")
        scout_available = scout and self.fleet.get(scout) and self.fleet[scout].mission_phase in ["IDLE", "PATROLLING"]
        
        if scout_available:
            print(f"[Coordinator] Tasking Scout '{scout}' to begin probabilistic search.")
            await self.mqtt.publish(f"drone/command/{scout}", {
                "command": "START_MISSION", "type": "MOB_SEARCH"
            })
            
            # --- Start the AI control loop ---
            if self.prob_search_loop_task:
                self.prob_search_loop_task.cancel()
            self.prob_search_loop_task = asyncio.create_task(
                self._probabilistic_search_loop(scout)
            )
            
        else:
            # 3. Failover: Find and task Utility
            utility = self._find_drone_by_role("utility")
            utility_available = utility and self.fleet.get(utility) and self.fleet[utility].mission_phase in ["IDLE", "PATROLLING"]
            if utility_available:
                print(f"[Coordinator] FAILOVER: Tasking Utility '{utility}' to begin probabilistic search.")
                await self.mqtt.publish(f"drone/command/{utility}", {
                    "command": "START_MISSION", "type": "MOB_SEARCH"
                })
                
                # --- Start the AI control loop for the Utility drone ---
                if self.prob_search_loop_task:
                    self.prob_search_loop_task.cancel()
                self.prob_search_loop_task = asyncio.create_task(
                    self._probabilistic_search_loop(utility)
                )
            else:
                print(f"[Coordinator] FATAL: No available Scout or Utility drone.")
                await self.gcs.broadcast_event("ERROR", {"message": "No available search drone."})
                return

        # 4. Pre-check Payload drone
        payload_drone = self._find_drone_by_role("payload")
        if not (payload_drone and self.fleet.get(payload_drone) and self.fleet[payload_drone].mission_phase == "IDLE"):
            print(f"[Coordinator] Warning: Payload drone '{payload_drone}' is busy or offline.")
            await self.gcs.broadcast_event("WARNING", {"message": "Payload drone not available."})

    async def trigger_patrol_mode(self):
        """Task the Utility drone to begin its patrol pattern."""
        print("[Coordinator] === PATROL MODE TRIGGERED ===")
        utility = self._find_drone_by_role("utility")
        if utility and self.fleet.get(utility) and self.fleet[utility].mission_phase == "IDLE":
            print(f"[Coordinator] Tasking Utility '{utility}' to begin patrol.")
            await self.mqtt.publish(f"drone/command/{utility}", {
                "command": "START_PATROL"
            })
        else:
            print(f"[Coordinator] Utility drone '{utility}' is busy or not available.")
            await self.gcs.broadcast_event("ERROR", {"message": "Utility drone is not available."})
            
    async def trigger_overwatch_mode(self, data: dict):
        """Task the nearest available drone to orbit a point and start streaming."""
        print("[Coordinator] === OVERWATCH MODE TRIGGERED ===")
        target_pos = Position(**data.get('position', {}))
        
        # 1. Find a drone (prefer Utility, fallback to Scout)
        drone_to_task = None
        utility = self._find_drone_by_role("utility")
        if utility and self.fleet.get(utility) and self.fleet[utility].mission_phase in ["IDLE", "PATROLLING"]:
            drone_to_task = utility
        else:
            scout = self._find_drone_by_role("scout")
            if scout and self.fleet.get(scout) and self.fleet[scout].mission_phase in ["IDLE", "PATROLLING"]:
                drone_to_task = scout
        
        if drone_to_task:
            print(f"[Coordinator] Tasking '{drone_to_task}' to overwatch {target_pos}.")
            
            # 2. Tell drone to start its video stream
            # (The drone will reply with an event containing its RTSP URL)
            await self.mqtt.publish(f"drone/command/{drone_to_task}", {
                "command": "START_VIDEO_STREAM"
            })
            
            # 3. Tell drone to fly to the overwatch position
            await self.mqtt.publish(f"drone/command/{drone_to_task}", {
                "command": "START_OVERWATCH",
                "position": target_pos.model_dump()
            })
            
            # 4. Tell Media Server to connect
            # This is a simulated URL. In reality, we'd wait for the drone's reply
            # event from _run_start_video_stream in mission.py
            sim_rtsp_url = f"rtsp://drone.local/{drone_to_task}/stream"
            await self.media_server.start_stream(drone_to_task, sim_rtsp_url)
            
        else:
            print(f"[Coordinator] No available drone for overwatch.")
            await self.gcs.broadcast_event("ERROR", {"message": "No drone available for overwatch."})

    async def _task_payload_drone(self, target_position: Position):
        """Find and task the payload drone to a specific coordinate."""
        print(f"[Coordinator] Received target position. Tasking payload drone.")
        payload_drone = self._find_drone_by_role("payload")
        payload_available = payload_drone and self.fleet.get(payload_drone) and self.fleet[payload_drone].mission_phase == "IDLE"

        if payload_available:
            print(f"[Coordinator] Tasking Payload '{payload_drone}' to deliver to {target_position}.")
            await self.mqtt.publish(f"drone/command/{payload_drone}", {
                "command": "START_MISSION",
                "type": "PAYLOAD_DELIVERY",
                "position": target_position.model_dump()
            })
        else:
            print(f"[Coordinator] Error: Payload delivery requested but drone '{payload_drone}' is not available.")
            await self.gcs.broadcast_event("ERROR", {"message": "Payload drone not available for delivery."})


    def _find_drone_by_role(self, role: str) -> str | None:
        """Find the first available drone_id for a given role."""
        for drone_id, vehicle in self.fleet.items():
            if vehicle.config.role == role:
                return drone_id
        return None

