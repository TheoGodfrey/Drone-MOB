"""Reusable mission behaviors"""
from .position import Position
from .drone import Drone

class SearchBehavior:
    """Encapsulates search behavior"""
    def __init__(self, drone: Drone, search_strategy, flight_strategy, config):
        self.drone = drone
        self.search_strategy = search_strategy
        self.flight_strategy = flight_strategy
        self.config = config
        self.iteration = 0
    
    def search_step(self) -> tuple:
        """
        Execute one search step.
        Returns: (should_continue, detection_or_none)
        """
        if self.iteration >= self.config['mission']['max_search_iterations']:
            return False, None
        
        # Get next search position
        search_area = self.config['strategies']['search']['area']
        search_area_pos = Position(
            search_area['x'],
            search_area['y'],
            search_area['z']
        )
        
        next_position = self.search_strategy.get_next_position(
            self.drone,
            search_area_pos,
            self.config['strategies']['search']['size']
        )
        
        # Fly and scan
        flight_position = self.flight_strategy.get_next_position(self.drone, next_position)
        self.drone.go_to(flight_position)
        
        frame = self.drone.camera.capture()
        detections = self.drone.camera.detect(frame)
        
        for detection in detections:
            if detection.is_person and detection.confidence >= 0.7:
                return False, detection  # Found!
        
        self.iteration += 1
        return True, None  # Keep searching

class DeliveryBehavior:
    """Encapsulates payload delivery"""
    def __init__(self, drone: Drone, flight_strategy):
        self.drone = drone
        self.flight_strategy = flight_strategy
    
    def deliver_to(self, target_position: Position):
        """Deliver payload to target"""
        delivery_position = self.flight_strategy.get_next_position(
            self.drone,
            target_position
        )
        self.drone.go_to(delivery_position)
        self.drone.hover()
        import time
        time.sleep(2.0)