"""
Minimal mission controller for single-drone system (composition-based)
"""

import time
from core.drone import Drone, Position
from core.camera import Camera
from core.logger import MissionLogger
from strategies import get_flight_strategy, get_search_strategy, list_available_strategies

class MissionController:
    """Mission controller that composes strategies"""
    
    def __init__(self, config: dict):
        self.config = config
        self.state = "IDLE"
        
        # Initialize drone and camera
        drone_type = config.get('drones', {}).get('type', 'simulated')
        is_simulated = drone_type == 'simulated'
        
        self.drone = Drone(is_simulated)
        self.drone.camera = Camera(is_simulated)
        self.target = None
        self.logger = MissionLogger()
        
        # Compose strategies (no inheritance)
        search_algo = config.get('search_algorithm', 'random')
        flight_algo = config.get('flight_algorithm', 'direct')
        
        self.search_strategy = get_search_strategy(search_algo)
        self.flight_strategy = get_flight_strategy(flight_algo)
        
        self.logger.log(f"Using search strategy: {self.search_strategy.name}", "info")
        self.logger.log(f"Using flight strategy: {self.flight_strategy.name}", "info")

    def execute(self) -> None:
        """Execute mission using composed strategies"""
        try:
            self.logger.log("Starting mission", "info")
            
            # Preflight checks
            self._preflight_check()
            
            # Takeoff to search altitude
            self.drone.takeoff(15.0)
            self.logger.log("Takeoff complete", "info")
            
            # Start mission
            self.state = "SCANNING"
            self.logger.log("Beginning search pattern", "info")
            
            # Scan for target with limit to prevent infinite loop
            max_search_iterations = self.config.get('max_search_iterations', 50)
            iterations = 0
            
            while self.state == "SCANNING" and iterations < max_search_iterations:
                iterations += 1
                self._scan_for_target()
                if self.target:
                    self.state = "TARGET_FOUND"
                    self.logger.log(f"Target found at iteration {iterations}", "info")
                    break
                
                # Brief pause between search points
                time.sleep(0.5)
            
            # Deliver payload if target found
            if self.state == "TARGET_FOUND":
                self._deliver_payload()
            else:
                self.logger.log(f"Search completed after {iterations} iterations - no target found", "warning")
                
            # Return to home and land
            self._return_to_home()
            
            # Mission complete
            self.state = "COMPLETED"
            self.logger.log("Mission completed successfully", "info")
        
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
            raise RuntimeError("Drone - Low battery")
        
        # Log available strategies for debugging
        available = list_available_strategies()
        self.logger.log(f"Available strategies: {available}", "debug")
        
        self.logger.log("Preflight check complete", "info")

    def _scan_for_target(self) -> None:
        """Scan for MOB using composed search strategy"""
        # Get next position from search strategy
        next_position = self.search_strategy.get_next_position(
            self.drone, 
            self.config['search_area'],
            self.config['search_size']
        )
        
        # Fly to position using flight strategy
        delivery_position = self.flight_strategy.get_next_position(
            self.drone, 
            next_position
        )
        
        self.drone.go_to(delivery_position)
        self.logger.log(f"Searching at position: {delivery_position}", "debug")
        
        # Capture and analyze frame
        frame = self.drone.camera.capture()
        detections = self.drone.camera.detect(frame)
        
        # Process detections
        for detection in detections:
            if detection.is_person and detection.confidence >= 0.7:
                self.target = detection
                self.logger.log(f"Target detected at {detection.position}", "info")
                return

    def _deliver_payload(self) -> None:
        """Deliver payload using composed flight strategy"""
        # Use flight strategy to get delivery position
        delivery_position = self.flight_strategy.get_next_position(
            self.drone, 
            self.target.position
        )
        
        self.drone.go_to(delivery_position)
        self.logger.log(f"Delivering payload to {delivery_position}", "info")
        
        # Hover over target
        self.drone.hover()
        self.logger.log("Payload delivered", "info")
        time.sleep(2.0)  # Simulate delivery time

    def _return_to_home(self) -> None:
        """Return to home position"""
        home_position = Position(0, 0, 15)
        self.drone.go_to(home_position)
        self.logger.log("Returning to home position", "info")
        time.sleep(1.0)
        self.drone.land()
        self.logger.log("Landed successfully", "info")

    def _emergency_land(self) -> None:
        """Emergency landing for drone"""
        self.logger.log("Initiating emergency landing", "error")
        if self.drone.is_healthy():
            self.drone.land()
        self.state = "EMERGENCY"