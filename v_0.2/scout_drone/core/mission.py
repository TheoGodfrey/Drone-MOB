"""
Minimal mission controller for single-drone system
"""

import time
from .drone import Drone
from .camera import Camera
from strategies import SearchStrategy, FlightStrategy
from .logger import MissionLogger

class MissionController:
    """Simplified mission controller for single-drone system"""
    def __init__(self, config: dict):
        self.config = config
        self.state = "IDLE"
        self.drones = [Drone(config['drones']['type'] == 'simulated')]
        self.drones[0].camera = Camera(config['drones']['type'] == 'simulated')
        self.target = None
        self.logger = MissionLogger()
        
        # Create search and flight strategies
        self.search_strategy = SearchStrategy.create(
            config.get('search_algorithm', 'random')
        )
        self.flight_strategy = FlightStrategy.create(
            config.get('flight_algorithm', 'direct')
        )

    def execute(self) -> None:
        """Execute mission with minimal state management"""
        try:
            # Preflight checks
            self._preflight_check()
            
            # Start mission
            self.state = "SCANNING"
            
            # Scan for target
            while self.state == "SCANNING":
                self._scan_for_target()
                if self.target:
                    self.state = "TARGET_FOUND"
                    break
            
            # Deliver payload
            if self.state == "TARGET_FOUND":
                self._deliver_payload()
                
            # Mission complete
            self.state = "COMPLETED"
        
        except KeyboardInterrupt:
            self._emergency_land()
        except Exception as e:
            self._emergency_land()

    def _preflight_check(self) -> None:
        """Minimal preflight check"""
        self.drones[0].connect()
        self.drones[0].camera.connect()
        
        # Check battery levels
        if self.drones[0].battery < 20.0:
            raise RuntimeError("Drone - Low battery")
        
        self.logger.log("Preflight check complete", "info")

    def _scan_for_target(self) -> None:
        """Scan for MOB with minimal logic"""
        drone = self.drones[0]
        
        # Get next position to search
        next_position = self.search_strategy.get_next_position(
            drone, 
            self.config['search_area'],
            self.config['search_size']
        )
        
        # Fly to position
        drone.go_to(next_position)
        
        # Wait for drone to reach position
        while drone.position.distance_to(next_position) > 1.0:
            time.sleep(0.5)
        
        # Capture and analyze frame
        frame = drone.camera.capture()
        detections = drone.camera.detect(frame)
        
        # Process detections
        for detection in detections:
            if detection.is_person and detection.confidence >= 0.7:
                self.target = detection
                return

    def _deliver_payload(self) -> None:
        """Deliver payload to target with minimal logic"""
        drone = self.drones[0]
        
        # Fly to target
        drone.go_to(self.target.position)
        
        # Wait for drone to reach position
        while drone.position.distance_to(self.target.position) > 1.0:
            time.sleep(0.5)
        
        # Hover over target
        drone.hover()
        self.logger.log("Payload delivered", "info")
        time.sleep(5.0)  # Simulate delivery time

    def _emergency_land(self) -> None:
        """Emergency landing for drone"""
        for drone in self.drones:
            if drone.is_healthy():
                drone.land()