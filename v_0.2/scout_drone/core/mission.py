"""
Asynchronous mission controller for single-drone system (composition-based)
"""

import asyncio
import traceback
from .drone import Drone  # NEW: Imports the refactored Drone
from .position import Position
from .logger import MissionLogger
from .state_machine import MissionState, MissionPhase
from .behaviors import SearchBehavior, DeliveryBehavior
# NEW: Import the camera system
from .cameras.dual_camera import DualCameraSystem 

class MissionController:
    """
    Asynchronous mission controller that manages the mission state loop.
    """
    
    def __init__(self, 
                 drone: Drone, 
                 dual_camera: DualCameraSystem,
                 search_strategy, 
                 flight_strategy, 
                 config: dict, 
                 logger: MissionLogger):
        
        self.drone = drone
        self.dual_camera = dual_camera  # NEW: Camera system is injected
        self.search_strategy = search_strategy
        self.flight_strategy = flight_strategy
        self.config = config
        self.logger = logger
        self.mission_state = MissionState()
        self.target = None
        
        # CHANGED: Behaviors now get the drone and camera system
        self.search_behavior = SearchBehavior(
            drone=drone,
            dual_camera=self.dual_camera,
            search_strategy=search_strategy,
            flight_strategy=flight_strategy,
            config=config
        )
        self.delivery_behavior = DeliveryBehavior(
            drone=drone,
            flight_strategy=flight_strategy
        )
        
        self.logger.log(f"Initialized mission for {drone.id}", "info")
        self.logger.log(f"Using search strategy: {self.search_strategy.name}", "info")
        self.logger.log(f"Using flight strategy: {self.flight_strategy.name}", "info")

    # CHANGED: This is the new main entry point, replacing execute()
    async def run(self) -> None:
        """
        Execute the main asynchronous mission loop.
        This loop is driven by the mission state.
        """
        try:
            self.logger.log("Starting mission", "info")
            self.mission_state.transition_to(MissionPhase.PREFLIGHT)
            
            # This loop runs the mission, state by state
            while self.mission_state.phase not in [MissionPhase.COMPLETED, MissionPhase.EMERGENCY]:
                
                # Update drone telemetry
                await self.drone.update_telemetry()
                
                if not self.drone.is_healthy() and self.mission_state.phase.is_active():
                    self.logger.log("Drone unhealthy, transitioning to EMERGENCY.", "error")
                    self.mission_state.transition_to(MissionPhase.EMERGENCY)
                    continue

                # --- State-Driven Logic ---
                if self.mission_state.phase == MissionPhase.PREFLIGHT:
                    if await self._run_preflight():
                        self.mission_state.transition_to(MissionPhase.TAKEOFF)
                    else:
                        self.logger.log("Preflight failed, aborting.", "error")
                        self.mission_state.transition_to(MissionPhase.EMERGENCY)
                
                elif self.mission_state.phase == MissionPhase.TAKEOFF:
                    if await self._run_takeoff():
                        self.mission_state.transition_to(MissionPhase.SEARCHING)
                    else:
                        self.logger.log("Takeoff failed, transitioning to EMERGENCY.", "error")
                        self.mission_state.transition_to(MissionPhase.EMERGENCY)
                
                elif self.mission_state.phase == MissionPhase.SEARCHING:
                    await self._run_search_step()
                
                elif self.mission_state.phase == MissionPhase.TARGET_FOUND:
                    # This state is set by _run_search_step,
                    # so we immediately transition to delivering.
                    self.mission_state.transition_to(MissionPhase.DELIVERING)
                
                elif self.mission_state.phase == MissionPhase.DELIVERING:
                    await self._run_delivery()
                    self.mission_state.transition_to(MissionPhase.RETURNING)
                
                elif self.mission_state.phase == MissionPhase.RETURNING:
                    await self._run_return_to_home()
                    self.mission_state.transition_to(MissionPhase.LANDING)

                elif self.mission_state.phase == MissionPhase.LANDING:
                    await self.drone.land()
                    self.logger.log("Landed successfully", "info")
                    self.mission_state.transition_to(MissionPhase.COMPLETED)
                
                # Non-blocking delay
                await asyncio.sleep(0.1)  # Main loop tick
            
            # --- End of Loop ---
            
            if self.mission_state.phase == MissionPhase.EMERGENCY:
                await self._run_emergency_land()

            self._log_mission_summary()
            self.logger.log("Mission run complete.", "info")

        except (KeyboardInterrupt, asyncio.CancelledError):
            self.logger.log("Mission interrupted by user", "warning")
            await self._run_emergency_land()
        except Exception as e:
            self.logger.log(f"Fatal mission error: {e}", "error")
            traceback.print_exc()
            await self._run_emergency_land()
        finally:
            self.logger.log("Cleaning up resources...", "info")
            await self.drone.disconnect()
            await self.dual_camera.disconnect()

    # --- Private Async State Methods ---

    async def _run_preflight(self) -> bool:
        """Minimal preflight check."""
        # CHANGED: Connect to drone and camera concurrently
        results = await asyncio.gather(
            self.drone.connect(),
            self.dual_camera.connect(),
            return_exceptions=True
        )
        
        for res in results:
            if isinstance(res, Exception) or res is False:
                self.logger.log(f"Preflight check failed: {res}", "error")
                return False
        
        if self.drone.telemetry.battery < 20.0:
            self.logger.log(f"{self.drone.id} - Low battery", "error")
            return False
            
        self.logger.log("Preflight check complete", "info")
        return True

    async def _run_takeoff(self) -> bool:
        self.logger.log("Taking off...", "info")
        return await self.drone.takeoff(15.0) # TODO: Get from config

    async def _run_search_step(self) -> None:
        """
        Scan for MOB using composed search behavior.
        Transitions state if target is found or search completes.
        """
        # CHANGED: search_step is now async
        should_continue, detection = await self.search_behavior.search_step()
        
        self.logger.log(f"Searching at position: {self.drone.telemetry.position}", "debug")
        
        if detection:
            self.target = detection
            self.logger.log(f"Target detected at {detection.position_world}", "info")
            self.mission_state.transition_to(MissionPhase.TARGET_FOUND)
        elif not should_continue:
            self.logger.log("Search complete, no target found.", "warning")
            self.mission_state.transition_to(MissionPhase.RETURNING)
        
        # Brief pause between search points
        await asyncio.sleep(0.5)

    async def _run_delivery(self) -> None:
        """Deliver payload using composed delivery behavior."""
        if not self.target:
            self.logger.log("Delivery called with no target.", "error")
            return

        self.logger.log(f"Delivering payload to {self.target.position_world}", "info")
        # CHANGED: deliver_to is now async
        await self.delivery_behavior.deliver_to(self.target.position_world)
        self.logger.log("Payload delivered", "info")

    async def _run_return_to_home(self) -> None:
        """Return to home position."""
        self.logger.log("Returning to home position", "info")
        await self.drone.set_led("red")
        
        # Return to home at safe altitude first
        home_pos_safe = Position(0, 0, self.drone.telemetry.position.z)
        await self.drone.go_to(home_pos_safe)
        
        # Descend to landing approach
        landing_approach = Position(0, 0, 5)
        await self.drone.go_to(landing_approach)
        
        await self.drone.set_led("off")

    async def _run_emergency_land(self) -> None:
        """Emergency landing for drone."""
        self.logger.log("Initiating emergency landing", "error")
        self.mission_state.transition_to(MissionPhase.EMERGENCY)
        if self.drone.telemetry.is_connected:
            await self.drone.land()
    
    def _log_mission_summary(self):
        """Log mission summary."""
        # Note: iterations are now tracked by the SearchBehavior
        iterations = self.search_behavior.iteration
        
        summary_data = {
            "Drone ID": self.drone.id,
            "Search strategy": self.search_strategy.name,
            "Flight strategy": self.flight_strategy.name,
            "Search iterations": iterations,
            "Max altitude reached": f"{self.drone.telemetry.position.z}m", # TODO: Need to track max
            "Target found": "Yes" if self.target else "No",
            "Target position": str(self.target.position_world) if self.target else "N/A",
            "Detection confidence": f"{self.target.confidence:.2f}" if self.target else "N/A",
            "Detection source": self.target.source if self.target else "N/A",
            "Final battery": f"{self.drone.telemetry.battery:.1f}%",
            "Final LED state": self.drone.telemetry.led_color
        }
        
        self.logger.log_summary(summary_data)