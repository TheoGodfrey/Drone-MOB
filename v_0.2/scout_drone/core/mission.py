"""
Asynchronous, event-driven mission controller.
(Refactored for GCS integration and safety decorators)
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
from .gcs_server import GcsServer # NEW

class MissionController:
    """
    Asynchronous mission controller.
    This class *is* the model for the state machine.
    """
    
    def __init__(self, 
                 drone: Drone, 
                 dual_camera: DualCameraSystem,
                 search_strategy, 
                 flight_strategy, 
                 config: Settings,
                 logger: MissionLogger):
        
        self.drone = drone
        self.dual_camera = dual_camera
        self.search_strategy = search_strategy
        self.flight_strategy = flight_strategy
        self.config = config
        self.logger = logger
        self.target = None # This will be set by the search behavior
        
        self.telemetry_logger = TelemetryLogger(
            log_dir=config.logging.log_dir + "/telemetry"
        )
        
        # NEW: Instantiate the GCS Server
        self.gcs_server = GcsServer(config.gcs, self)
        
        self.search_behavior = SearchBehavior(
            drone=drone,
            dual_camera=self.dual_camera,
            search_strategy=search_strategy,
            flight_strategy=flight_strategy,
            config=config # Pass full config
        )
        # HACK: Pass config to delivery behavior (needs a cleaner way)
        self.delivery_behavior = DeliveryBehavior(
            drone=drone,
            flight_strategy=flight_strategy
        )
        self.delivery_behavior.drone.config = config # Attach config to drone for access

        self.state_machine = MissionStateMachine(self)
        
        self.logger.log(f"Initialized mission for {drone.id}", "info")
        self.logger.log(f"Using search strategy: {config.strategies.search.algorithm}", "info")
        self.logger.log(f"Using flight strategy: {config.strategies.flight.algorithm}", "info")

    async def run(self) -> None:
        """
        Execute the main asynchronous mission loop.
        """
        # NEW: Run the GCS server as a concurrent task
        gcs_task = asyncio.create_task(self.gcs_server.run())
        
        try:
            self.logger.log("Starting mission", "info")
            await self.start_mission() 
            
            while self.state not in [MissionPhase.COMPLETED, MissionPhase.EMERGENCY]:
                
                if self.state not in [MissionPhase.IDLE, MissionPhase.PREFLIGHT]:
                    await self.drone.update_telemetry()
                
                    if not self.drone.is_healthy():
                        self.logger.log("Drone unhealthy, transitioning to EMERGENCY.", "error")
                        await self.trigger_emergency(event=None)
                        continue
                        
                    # Broadcast telemetry to GCS
                    await self.gcs_server.broadcast_telemetry(self.drone, self.state.value)
                    
                    # Log to file
                    await self.telemetry_logger.log_snapshot(
                        mission_state=self.state.value,
                        drone=self.drone,
                        detections=self.search_behavior.get_last_detections()
                    )
                
                await asyncio.sleep(1.0) # Main loop interval
            
            self.logger.log(f"Mission loop finished with state: {self.state.value}", "info")

        except (KeyboardInterrupt, asyncio.CancelledError):
            self.logger.log("Mission interrupted by user", "warning")
            await self.trigger_emergency(event=None)
        except Exception as e:
            self.logger.log(f"Fatal mission error: {e}", "error")
            traceback.print_exc()
            await self.trigger_emergency(event=None)
        finally:
            self.logger.log("Cleaning up resources...", "info")
            gcs_task.cancel() # Stop the GCS server
            self.telemetry_logger.close()
            await self.drone.disconnect()
            await self.dual_camera.disconnect()
            self.logger.log("Cleanup complete.", "info")

    # --- NEW: Public methods for GCS to call ---
    
    async def operator_confirm_target(self):
        """Called by GcsServer when operator confirms target."""
        if self.state == MissionPhase.TARGET_PENDING_CONFIRMATION:
            await self.operator_confirm_target() # This is the state machine trigger
        
    async def operator_reject_target(self):
        """Called by GcsServer when operator rejects target."""
        if self.state == MissionPhase.TARGET_PENDING_CONFIRMATION:
            self.target = None # Clear the rejected target
            await self.operator_reject_target() # This is the state machine trigger

    # --- State Machine Callbacks ---

    async def _run_preflight(self, event):
        self.logger.log(f"Entering PREFLIGHT state from {event.source.value}", "info")
        try:
            results = await asyncio.gather(
                self.drone.connect(),
                self.dual_camera.connect(),
            )
            if not all(results): raise Exception("Drone or Camera failed to connect.")
            await self.drone.update_telemetry()
            if self.drone.telemetry.battery < self.config.health.min_battery_preflight:
                raise Exception(f"{self.drone.id} - Low battery")
            
            self.logger.log("Preflight check complete", "info")
            await self.preflight_success()
        except Exception as e:
            self.logger.log(f"Preflight failed: {e}", "error")
            await self.trigger_emergency(event=event)

    async def _run_takeoff(self, event):
        self.logger.log(f"Entering TAKEOFF state from {event.source.value}", "info")
        try:
            takeoff_alt = self.config.strategies.search.area.z + 15.0
            if not await self.drone.takeoff(takeoff_alt):
                raise Exception("Takeoff command failed.")
            self.logger.log(f"Takeoff complete to {takeoff_alt}m", "info")
            await self.takeoff_success()
        except Exception as e:
            self.logger.log(f"Takeoff failed: {e}", "error")
            await self.trigger_emergency(event=event)

    async def _run_search_step(self, event):
        self.logger.log(f"Entering SEARCHING state from {event.source.value}", "info")
        
        while self.state == MissionPhase.SEARCHING:
            try:
                # Health is checked in the main run loop
                should_continue, detection = await self.search_behavior.search_step()
                
                if detection:
                    self.target = detection # Store target for confirmation
                    self.logger.log(f"Target sighted at {detection.position_world}", "info")
                    await self.target_sighted() # Trigger PENDING_CONFIRMATION
                    break
                elif not should_continue:
                    self.logger.log("Search complete, no target found.", "warning")
                    await self.search_complete_negative()
                    break
                
                await asyncio.sleep(0.5)
            
            except Exception as e:
                self.logger.log(f"Error during search step: {e}", "error")
                await self.trigger_emergency(event=event)
                break
    
    # NEW GCS CALLBACK
    async def _run_pending_confirmation(self, event):
        """Awaiting operator confirmation."""
        self.logger.log(f"Entering PENDING_CONFIRMATION from {event.source.value}", "info")
        if not self.target:
            self.logger.log("ERROR: Entered pending state with no target.", "error")
            await self.operator_reject_target() # Auto-reject
            return

        # Send the event to the GCS
        target_data = {
            "source": self.target.source,
            "confidence": self.target.confidence,
            "position": {
                "x": self.target.position_world.x,
                "y": self.target.position_world.y,
            },
            # TODO: Add a Base64-encoded image snapshot
            "target_image": "iVBOR...[base64_image_data]...RK5CYII=" 
        }
        await self.gcs_server.broadcast_event('PENDING_CONFIRMATION', target_data)

    async def _run_delivery(self, event):
        self.logger.log(f"Entering DELIVERING state from {event.source.value}", "info")
        try:
            if not self.target: raise Exception("Delivery called with no target.")
            self.logger.log(f"Delivering payload to {self.target.position_world}", "info")
            await self.delivery_behavior.deliver_to(self.target.position_world)
            self.logger.log("Payload delivered", "info")
            self.target = None # Clear target after delivery
            await self.delivery_complete()
        except Exception as e:
            self.logger.log(f"Delivery failed: {e}", "error")
            await self.trigger_emergency(event=event)

    async def _run_return_to_home(self, event):
        self.logger.log(f"Entering RETURNING state from {event.source.value}", "info")
        try:
            await self.drone.set_led("red")
            home_pos_safe = Position(0, 0, self.drone.telemetry.position.z)
            await self.drone.go_to(home_pos_safe)
            landing_approach = Position(0, 0, self.config.precision_hover.altitude_offset + 3.0)
            await self.drone.go_to(landing_approach)
            await self.drone.set_led("off")
            self.logger.log("Arrived at home landing approach.", "info")
            await self.arrived_home()
        except Exception as e:
            self.logger.log(f"Return to home failed: {e}", "error")
            await self.trigger_emergency(event=event)

    async def _run_land(self, event):
        self.logger.log(f"Entering LANDING state from {event.source.value}", "info")
        try:
            await self.drone.land()
            self.logger.log("Landed successfully", "info")
            await self.land_complete()
        except Exception as e:
            self.logger.log(f"Landing failed: {e}", "error")
            await self.trigger_emergency(event=event)

    async def _run_emergency_land(self, event):
        if event:
             self.logger.log(f"Entering EMERGENCY state from {event.source.value}", "error")
        else:
             self.logger.log(f"Entering EMERGENCY state from external trigger", "error")
        if self.drone.telemetry.is_connected:
            await self.drone.land()
            self.logger.log("Emergency land complete.", "error")
    
    async def _log_mission_summary(self, event):
        self.logger.log(f"Entering COMPLETED state from {event.source.value}", "info")
        iterations = self.search_behavior.iteration
        summary_data = {
            "Drone ID": self.drone.id,
            "Search strategy": self.config.strategies.search.algorithm,
            "Flight strategy": self.config.strategies.flight.algorithm,
            "Search iterations": iterations,
            "Target found": "Yes" if self.target else "No", # Note: self.target is cleared on reject/deliver
            "Final battery": f"{self.drone.telemetry.battery:.1f}%",
        }
        self.logger.log_summary(summary_data)
