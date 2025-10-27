"""
Minimal mission controller for single-drone system (composition-based)
"""

import time
from .drone import Drone
from .position import Position
from .camera import Camera
from .logger import MissionLogger
from .state_machine import MissionState, MissionPhase
from .behaviors import SearchBehavior, DeliveryBehavior

class MissionController:
    """Mission controller that composes strategies"""
    
    def __init__(self, drone: Drone, search_strategy, flight_strategy, config: dict, logger: MissionLogger):
        self.drone = drone
        self.search_strategy = search_strategy
        self.flight_strategy = flight_strategy
        self.config = config
        self.logger = logger
        self.mission_state = MissionState()
        self.target = None
        
        # Create behaviors
        self.search_behavior = SearchBehavior(drone, search_strategy, flight_strategy, config)
        self.delivery_behavior = DeliveryBehavior(drone, flight_strategy)
        
        self.logger.log(f"Initialized mission for {drone.id}", "info")
        self.logger.log(f"Using search strategy: {self.search_strategy.name}", "info")
        self.logger.log(f"Using flight strategy: {self.flight_strategy.name}", "info")

    def execute(self) -> None:
        """Execute mission using composed strategies"""
        try:
            self.logger.log("Starting mission", "info")
            
            # Preflight checks
            self.mission_state.transition_to(MissionPhase.PREFLIGHT)
            self._preflight_check()
            
            # Takeoff to search altitude
            self.mission_state.transition_to(MissionPhase.TAKEOFF)
            self.drone.takeoff(15.0)
            self.logger.log("Takeoff complete", "info")
            
            # Start mission
            self.mission_state.transition_to(MissionPhase.SEARCHING)
            self.logger.log("Beginning search pattern", "info")
            
            # Scan for target with limit to prevent infinite loop
            iterations = 0
            
            while self.mission_state.phase == MissionPhase.SEARCHING:
                iterations += 1
                should_continue = self._scan_for_target()
                
                if not should_continue:
                    if self.target:
                        self.mission_state.transition_to(MissionPhase.TARGET_FOUND)
                        self.logger.log(f"Target found at iteration {iterations}", "info")
                    else:
                        self.logger.log(f"Search completed after {iterations} iterations - no target found", "warning")
                    break
                
                # Brief pause between search points
                time.sleep(0.5)
            
            # Deliver payload if target found
            if self.mission_state.phase == MissionPhase.TARGET_FOUND:
                self.mission_state.transition_to(MissionPhase.DELIVERING)
                self._deliver_payload()
                
            # Return to home and land
            self.mission_state.transition_to(MissionPhase.RETURNING)
            self._return_to_home()
            
            # Mission complete
            self.mission_state.transition_to(MissionPhase.COMPLETED)
            self._log_mission_summary(iterations)
        
        except KeyboardInterrupt:
            self.logger.log("Mission interrupted by user", "warning")
            self._emergency_land()
        except Exception as e:
            self.logger.log(f"Mission error: {e}", "error")
            self._emergency_land()

    def _preflight_check(self) -> None:
        """Minimal preflight check"""
        self.drone.connect()
        self.drone.camera.connect()
        
        # Check battery levels
        if self.drone.battery < 20.0:
            raise RuntimeError(f"{self.drone.id} - Low battery")
        
        self.logger.log("Preflight check complete", "info")

    def _scan_for_target(self) -> bool:
        """
        Scan for MOB using composed search behavior.
        Returns True if should continue searching, False if done.
        """
        # Record health
        self.drone.record_health()
        
        # Execute search step
        should_continue, detection = self.search_behavior.search_step()
        
        self.logger.log(f"Searching at position: {self.drone.position}", "debug")
        
        if detection:
            self.target = detection
            self.logger.log(f"Target detected at {detection.position}", "info")
            return False
        
        return should_continue

    def _deliver_payload(self) -> None:
        """Deliver payload using composed delivery behavior"""
        self.logger.log(f"Delivering payload to {self.target.position}", "info")
        self.delivery_behavior.deliver_to(self.target.position)
        self.logger.log("Payload delivered", "info")

    def _return_to_home(self) -> None:
        """Return to home position"""
        home_position = Position(0, 0, 15)
        self.drone.go_to(home_position)
        self.logger.log("Returning to home position", "info")
        time.sleep(1.0)
        
        self.mission_state.transition_to(MissionPhase.LANDING)
        self.drone.land()
        self.logger.log("Landed successfully", "info")

    def _emergency_land(self) -> None:
        """Emergency landing for drone"""
        self.logger.log("Initiating emergency landing", "error")
        self.mission_state.transition_to(MissionPhase.EMERGENCY)
        if self.drone.is_healthy():
            self.drone.land()
    
    def _log_mission_summary(self, iterations: int):
        """Log mission summary"""
        self.logger.log("=== MISSION SUMMARY ===", "info")
        self.logger.log(f"Drone ID: {self.drone.id}", "info")
        self.logger.log(f"Search strategy: {self.search_strategy.name}", "info")
        self.logger.log(f"Flight strategy: {self.flight_strategy.name}", "info")
        self.logger.log(f"Search iterations: {iterations}", "info")
        self.logger.log(f"Max altitude reached: {self.drone.position.z}m", "info")
        self.logger.log(f"Target found: {self.target is not None}", "info")
        if self.target:
            self.logger.log(f"Target position: {self.target.position}", "info")
        self.logger.log(f"Final battery: {self.drone.battery}%", "info")
        self.logger.log(f"Detections: {self.drone.camera.detection_count}", "info")
        self.logger.log(f"Final LED state: {self.drone.led_color}", "info")
        self.logger.log("Mission completed successfully", "info")