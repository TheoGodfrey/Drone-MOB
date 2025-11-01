"""
Asynchronous, event-driven, MQTT-controlled mission controller.
(Refactored for Fleet Operations & Operational Modes)
"""

import asyncio
import traceback
from .drone import Drone
from .position import Position
from .logger import MissionLogger
from .state_machine import MissionStateMachine, MissionPhase
from .config_models import Settings 
from .behaviors import SearchBehavior, DeliveryBehavior
from .cameras.dual_camera import DualCameraSystem 
from .telemetry_logger import TelemetryLogger
from .comms import MqttClient

class MissionController:
    """
    Asynchronous mission controller for a *single* drone.
    This class *is* the model for the state machine.
    It now listens for commands from the Coordinator via MQTT.
    """
    
    def __init__(self, 
                 drone: Drone, 
                 dual_camera: DualCameraSystem | None,
                 search_strategies: dict, # NEW: Pass in all strategies
                 flight_strategies: dict, # NEW: Pass in all strategies
                 config: Settings,
                 logger: MissionLogger,
                 mqtt_client: MqttClient):
        
        self.drone = drone
        self.dual_camera = dual_camera
        self.search_strategies = search_strategies
        self.flight_strategies = flight_strategies
        self.config = config
        self.logger = logger
        self.mqtt = mqtt_client
        self.target = None
        self.target_position = None # For payload/overwatch/standby
        self.current_mission_type = "IDLE" # For state machine conditions
        
        self.telemetry_logger = None 
        self.search_behavior = None
        self.delivery_behavior = None

        # Only create camera-dependent components if cameras exist
        if self.dual_camera:
            self.telemetry_logger = TelemetryLogger(
                log_dir=f"{config.logging.log_dir}/{drone.id}"
            )
            self.search_behavior = SearchBehavior(
                drone=drone,
                dual_camera=self.dual_camera,
                search_strategy=None, # Will be set by the mission
                flight_strategy=flight_strategies['direct'], # Default
                config=config
            )
        
        # Delivery behavior doesn't need cameras
        self.delivery_behavior = DeliveryBehavior(
            drone=drone,
            flight_strategy=flight_strategies['precision_hover']
        )
        
        self.state_machine = MissionStateMachine(self, mqtt_client)
        
        self.logger.log(f"Initialized mission for {drone.id}", "info")
        self.logger.log(f"Role: {self._get_role()}")

    def _get_role(self):
        """Get the drone's role from the config."""
        for d in self.config.drones:
            if d.id == self.drone.id:
                return d.role
        return "unknown"

    async def run(self) -> None:
        """
        Execute the main asynchronous mission loop.
        Listens for commands and runs the health monitor.
        """
        try:
            command_topic = f"drone/command/{self.drone.id}"
            await self.mqtt.subscribe(command_topic)
            self.logger.log(f"Listening for commands on {command_topic}", "info")
            
            # Announce connection (will be picked up by Coordinator)
            await self.mqtt.publish("fleet/connect", {"drone_id": self.drone.id})

            await asyncio.gather(
                self._command_listener(),
                self._health_monitor()
            )

        except (KeyboardInterrupt, asyncio.CancelledError):
            self.logger.log("Mission interrupted by user/system", "warning")
            await self.trigger_emergency(event=None)
        except Exception as e:
            self.logger.log(f"Fatal mission error: {e}", "error")
            traceback.print_exc()
            await self.trigger_emergency(event=None)
        finally:
            self.logger.log("Cleaning up resources...", "info")
            if self.telemetry_logger:
                self.telemetry_logger.close()
            
            if self.drone.telemetry.is_connected:
                await self.drone.disconnect()
            
            if self.dual_camera and self.dual_camera.connected:
                await self.dual_camera.disconnect()
            
            self.logger.log("Cleanup complete.", "info")
    
    async def _command_listener(self):
        """Main loop that waits for commands from the Coordinator."""
        async for topic, payload in self.mqtt.listen():
            if not topic.startswith(f"drone/command/{self.drone.id}"):
                continue

            command = payload.get("command")
            self.logger.log(f"Received command: {command}", "info")
            
            # Save target position if provided
            if "position" in payload and payload["position"] is not None:
                self.target_position = Position(**payload["position"])
            
            # --- Command Handling ---
            
            if command == "START_MISSION":
                mission_type = payload.get("type")
                if self.state == MissionPhase.IDLE:
                    if mission_type == "MOB_SEARCH":
                        if self._get_role() not in ["scout", "utility"]:
                            self.logger.log(f"Role {self._get_role()} cannot perform MOB_SEARCH. Ignoring.", "error")
                            continue
                        self.current_mission_type = "MOB_SEARCH"
                        self.search_behavior.search_strategy = self.search_strategies[
                            self.config.strategies.search.algorithm
                        ]
                        await self.start_mission()
                    else:
                        self.logger.log(f"Unknown START_MISSION type: {mission_type}", "warning")

            elif command == "START_PATROL":
                if self.state == MissionPhase.IDLE:
                    if self._get_role() != "utility":
                        self.logger.log(f"Role {self._get_role()} cannot PATROL. Ignoring.", "error")
                        continue
                    self.current_mission_type = "PATROL"
                    self.search_behavior.search_strategy = self.search_strategies['lawnmower']
                    await self.start_patrol_mission()

            elif command == "START_OVERWATCH":
                if self.state in [MissionPhase.IDLE, MissionPhase.PATROLLING, MissionPhase.STANDBY]:
                    if self._get_role() not in ["scout", "utility"]:
                        self.logger.log(f"Role {self._get_role()} cannot OVERWATCH. Ignoring.", "error")
                        continue
                    self.current_mission_type = "OVERWATCH"
                    await self.start_overwatch_mission()

            elif command == "LAUNCH_AND_STANDBY":
                if self.state == MissionPhase.IDLE:
                    if self._get_role() != "payload":
                        self.logger.log(f"Role {self._get_role()} cannot STANDBY. Ignoring.", "error")
                        continue
                    self.current_mission_type = "STANDBY"
                    await self.start_standby_mission()
            
            elif command == "START_DELIVERY_MISSION":
                 if self.state in [MissionPhase.IDLE, MissionPhase.STANDBY]:
                    if self._get_role() != "payload":
                        self.logger.log(f"Role {self._get_role()} cannot DELIVER. Ignoring.", "error")
                        continue
                    self.current_mission_type = "PAYLOAD_DELIVERY"
                    await self.start_delivery_mission()

            elif command == "OPERATOR_CONFIRM_TARGET":
                if self.state == MissionPhase.TARGET_PENDING_CONFIRMATION:
                    await self.confirm_target()
            
            elif command == "OPERATOR_REJECT_TARGET":
                if self.state == MissionPhase.TARGET_PENDING_CONFIRMATION:
                    await self.reject_target()
            
            elif command == "RETURN_TO_HOME":
                if self.state not in [MissionPhase.EMERGENCY, MissionPhase.LANDING]:
                    self.logger.log("Operator commanded Return-to-Home.", "info")
                    # Use the 'negative' search complete trigger, it leads to RETURNING
                    await self.search_complete_negative() 
            
    async def _health_monitor(self):
        """Periodic loop to update telemetry and check health."""
        while True:
            try:
                if self.state not in [MissionPhase.IDLE, MissionPhase.PREFLIGHT]:
                    await self.drone.update_telemetry()
                    
                    # --- Local Operator Takeover Logic ---
                    is_manual = self.drone.telemetry.state == "MANUAL"
                    is_in_local_control = self.state == MissionPhase.LOCAL_OPERATOR_CONTROL
                    
                    if is_manual and not is_in_local_control:
                        # Operator has taken control via RC
                        self.logger.log("!!! Local Operator Takeover Detected !!!", "warning")
                        await self.local_operator_takeover()
                    elif not is_manual and is_in_local_control:
                        # Operator has given back control
                        self.logger.log("Local Operator has released control.", "info")
                        await self.local_operator_release()
                    
                    # Don't check health if operator is in control
                    if not is_in_local_control and not self.drone.is_healthy():
                        self.logger.log("Drone unhealthy, transitioning to EMERGENCY.", "error")
                        await self.trigger_emergency(event=None)
                        continue
                        
                    # Publish telemetry
                    await self.mqtt.publish(
                        f"fleet/telemetry/{self.drone.id}",
                        self.drone.telemetry.model_dump()
                    )

                    # Log to machine-readable file if logger exists
                    if self.telemetry_logger:
                        await self.telemetry_logger.log_snapshot(
                            mission_state=self.state.value,
                            drone=self.drone,
                            detections=self.search_behavior.get_last_detections() if self.search_behavior else []
                        )
                
                await asyncio.sleep(1.0) # Health check / Telemetry publish interval
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.log(f"Error in health monitor: {e}", "error")
                await self.trigger_emergency(event=None)

    # --- State Machine Callbacks (Updated for new modes) ---

    async def _run_preflight(self, event):
        self.logger.log(f"Entering PREFLIGHT state for {self.current_mission_type}", "info")
        try:
            if not await self.drone.connect():
                 raise Exception("Drone failed to connect.")
            
            # Only connect cameras if this role needs them
            role = self._get_role()
            if role in ["scout", "utility"]:
                if not self.dual_camera or not await self.dual_camera.connect():
                    raise Exception("Camera system failed to connect.")

            await self.drone.update_telemetry()
            if self.drone.telemetry.battery < self.config.health.min_battery_preflight:
                raise Exception(f"{self.drone.id} - Low battery")
            
            self.logger.log("Preflight check complete", "info")
            await self.preflight_success()
        except Exception as e:
            self.logger.log(f"Preflight failed: {e}", "error")
            await self.trigger_emergency(event=event)

    async def _run_takeoff(self, event):
        self.logger.log(f"Entering TAKEOFF state", "info")
        try:
            # Determine takeoff altitude based on mission
            if self.current_mission_type == "PATROL":
                alt = self.config.lawnmower.patrol_altitude
            elif self.current_mission_type == "OVERWATCH":
                alt = self.target_position.z + self.config.orbit.altitude_offset
            elif self.current_mission_type == "STANDBY":
                alt = self.target_position.z
            elif self.current_mission_type == "PAYLOAD_DELIVERY":
                alt = 30.0 # Delivery cruise altitude
            else: # MOB_SEARCH
                alt = self.config.strategies.search.area.z + 15.0 # Default search alt
            
            if not await self.drone.takeoff(alt):
                raise Exception("Takeoff command failed.")
            self.logger.log(f"Takeoff complete to {alt}m", "info")
            await self.takeoff_success()
        except Exception as e:
            self.logger.log(f"Takeoff failed: {e}", "error")
            await self.trigger_emergency(event=event)

    async def _run_search_step(self, event):
        self.logger.log(f"Entering SEARCHING state", "info")
        if not self.search_behavior:
            self.logger.log("Error: Cannot enter SEARCHING (no camera/behavior).", "error")
            await self.trigger_emergency(event=event)
            return

        while self.state == MissionPhase.SEARCHING:
            try:
                should_continue, detection = await self.search_behavior.search_step()
                
                if detection:
                    self.target = detection # Save the detection object
                    await self.target_sighted() # Trigger confirmation state
                    break
                elif not should_continue:
                    await self.search_complete_negative() # Trigger RTL
                    break
                
                await asyncio.sleep(0.5) # Brief pause between search steps
            
            except Exception as e:
                self.logger.log(f"Error during search step: {e}", "error")
                await self.trigger_emergency(event=event)
                break
    
    async def _run_patrol(self, event):
        self.logger.log(f"Entering PATROLLING state", "info")
        if not self.search_behavior:
             self.logger.log("Error: Cannot enter PATROLLING (no camera/behavior).", "error")
             await self.trigger_emergency(event=event)
             return
        
        self.search_behavior.search_strategy.current_leg = 0 # Reset strategy
        
        while self.state == MissionPhase.PATROLLING:
            try:
                if self.drone.telemetry.battery < self.config.health.min_battery_patrol_rtl:
                    self.logger.log("Patrol battery low. Returning to home.", "warning")
                    await self.patrol_battery_low()
                    break

                next_pos = self.search_behavior.search_strategy.get_next_position(self.drone, self.config.strategies.search.area, self.config.strategies.search.size)
                
                if next_pos is None:
                    self.logger.log("Patrol pattern complete. Returning to home.", "info")
                    await self.patrol_complete()
                    break
                
                self.logger.log(f"Patrolling to {next_pos}", "debug")
                await self.drone.go_to(next_pos)
                
                await asyncio.sleep(1.0) # Pause at point

            except Exception as e:
                self.logger.log(f"Error during patrol: {e}", "error")
                await self.trigger_emergency(event=event)
                break

    async def _run_overwatch(self, event):
        self.logger.log(f"Entering OVERWATCH state at {self.target_position}", "info")
        orbit_strategy = self.flight_strategies['orbit']
        
        while self.state == MissionPhase.OVERWATCH:
            try:
                if self.drone.telemetry.battery < self.config.health.min_battery_emergency:
                    self.logger.log("Overwatch battery low. Returning to home.", "warning")
                    await self.overwatch_complete()
                    break
                
                next_pos = orbit_strategy.get_next_position(self.drone, self.target_position)
                
                self.logger.log(f"Orbiting to {next_pos}", "debug")
                await self.drone.go_to(next_pos)
                
                await asyncio.sleep(1.0) # Time between orbit waypoints

            except Exception as e:
                self.logger.log(f"Error during overwatch: {e}", "error")
                await self.trigger_emergency(event=event)
                break
    
    async def _run_local_operator_takeover(self, event):
        self.logger.log(f"!!! LOCAL OPERATOR CONTROL ACTIVE (from {event.source.value}) !!!", "warning")
        # Just stay in this state. The health monitor handles everything.
    
    async def _run_local_operator_release(self, event):
        self.logger.log("!!! Local Operator control released. Returning to home.", "info")
        # State machine automatically transitions to RETURNING.

    async def _request_operator_confirmation(self, event):
        self.logger.log("Target sighted. Requesting operator confirmation...", "info")
        await self.mqtt.publish(f"fleet/event/{self.drone.id}", {
            "type": "PENDING_CONFIRMATION",
            "data": { 
                "drone_id": self.drone.id, 
                "position": self.target.position_world.model_dump(), 
                "confidence": self.target.confidence 
            }
        })
        
    async def _handle_rejection(self, event):
        self.logger.log("Operator rejected target. Resuming search.", "warning")
        self.target = None
        # State machine automatically transitions back to SEARCHING
        
    async def _request_delivery(self, event):
        """Scout confirms target and requests delivery."""
        self.logger.log("Target confirmed. Requesting payload drone delivery.", "info")
        
        # --- FIX: Send delivery request, then go home ---
        # The scout's job is to find the target, not manage delivery.
        await self.mqtt.publish(f"fleet/event/{self.drone.id}", {
            "type": "TARGET_DELIVERY_REQUEST",
            "data": { "position": self.target.position_world.model_dump() }
        })
        # This state transition (delivery_request_sent) now goes to RETURNING
        await self.delivery_request_sent() 
        # ------------------------------------------------
        
    async def _run_payload_delivery(self, event):
        self.logger.log(f"Entering DELIVERING state", "info")
        try:
            if not self.target_position: raise Exception("Delivery mission started with no target_position.")
            self.logger.log(f"Delivering payload to {self.target_position}", "info")
            await self.delivery_behavior.deliver_to(self.target_position)
            self.logger.log("Payload delivered", "info")
            await self.delivery_complete()
        except Exception as e:
            self.logger.log(f"Delivery failed: {e}", "error")
            await self.trigger_emergency(event=event)
            
    async def _run_standby(self, event):
        self.logger.log(f"Entering STANDBY state", "info")
        try:
            if not self.target_position: raise Exception("Standby mission started with no target_position.")
            self.logger.log(f"Flying to standby position: {self.target_position}", "info")
            await self.drone.go_to(self.target_position)
            self.logger.log("At standby. Awaiting delivery command.", "info")
            # Drone will now just sit in this state, running the health monitor
        except Exception as e:
            self.logger.log(f"Standby failed: {e}", "error")
            await self.trigger_emergency(event=event)

    async def _run_return_to_home(self, event):
        self.logger.log(f"Entering RETURNING state from {event.source.value}", "info")
        try:
            await self.drone.set_led("red")
            home_pos_safe = Position(x=0, y=0, z=self.drone.telemetry.position.z) # Go to 0,0 at current alt
            await self.drone.go_to(home_pos_safe)
            landing_approach = Position(x=0, y=0, z=5.0) # 5m alt at 0,0
            await self.drone.go_to(landing_approach)
            await self.drone.set_led("off")
            self.logger.log("Arrived at home landing approach.", "info")
            await self.arrived_home()
        except Exception as e:
            self.logger.log(f"Return to home failed: {e}", "error")
            await self.trigger_emergency(event=event)

    async def _run_land(self, event):
        self.logger.log(f"Entering LANDING state", "info")
        try:
            await self.drone.land()
            self.logger.log("Landed successfully", "info")
            await self.land_complete()
        except Exception as e:
            self.logger.log(f"Landing failed: {e}", "error")
            await self.trigger_emergency(event=event)

    async def _run_emergency_land(self, event):
        if event: self.logger.log(f"Entering EMERGENCY state from {event.source.value}", "error")
        else: self.logger.log(f"Entering EMERGENCY state from external trigger", "error")
        if self.drone.telemetry.is_connected:
            await self.drone.land()
            self.logger.log("Emergency land complete.", "error")
    
    async def _log_mission_summary(self, event):
        self.logger.log(f"Entering COMPLETED state from {event.source.value}", "info")
        iterations = 0
        if self.search_behavior: iterations = self.search_behavior.iteration
        
        summary_data = {
            "Drone ID": self.drone.id, "Role": self._get_role(),
            "Search iterations": iterations,
            "Target found": "Yes" if self.target else "No",
            "Target position": str(self.target.position_world) if self.target else "N/A",
            "Final battery": f"{self.drone.telemetry.battery:.1f}%",
        }
        self.logger.log_summary(summary_data)

