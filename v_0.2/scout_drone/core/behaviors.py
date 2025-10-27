"""Reusable mission behaviors"""
from .position import Position
from .drone import Drone
from .detection.fusion_detector import FusionDetector
import time

class SearchBehavior:
    """Encapsulates search behavior with dual camera detection"""
    def __init__(self, drone: Drone, search_strategy, flight_strategy, config):
        self.drone = drone
        self.search_strategy = search_strategy
        self.flight_strategy = flight_strategy
        self.config = config
        self.iteration = 0
        
        # Create detector based on config
        detection_config = config.get('detection', {})
        self.detector = FusionDetector(detection_config)
    
    def search_step(self) -> tuple:
        """
        Execute one search step with dual camera detection.
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
        
        # Fly to position
        flight_position = self.flight_strategy.get_next_position(self.drone, next_position)
        self.drone.go_to(flight_position)
        
        # Capture synchronized frame from both cameras
        dual_frame = self.drone.dual_camera.capture_synchronized()
        
        # Detect using sensor fusion
        detections = self.detector.detect(dual_frame)
        
        # Return first high-confidence detection
        for detection in detections:
            if detection.is_person and detection.confidence >= 0.7:
                # Convert image coordinates to world position
                detection.position_world = self._image_to_world_position(
                    detection.position_image,
                    self.drone.position
                )
                return False, detection  # Found!
        
        self.iteration += 1
        return True, None  # Keep searching
    
    def _image_to_world_position(self, image_pos: tuple, drone_pos: Position) -> Position:
        """
        Convert image coordinates to world position
        Simplified - assumes nadir (straight down) view
        """
        # For now, place detection at ground level below drone
        # In real system, would use camera calibration + altitude
        return Position(
            drone_pos.x,
            drone_pos.y,
            0.0  # Water surface
        )

class DeliveryBehavior:
    """Encapsulates payload delivery with LED signaling"""
    def __init__(self, drone: Drone, flight_strategy):
        self.drone = drone
        self.flight_strategy = flight_strategy
    
    def deliver_to(self, target_position: Position):
        """Deliver payload to target with LED signaling"""
        # Set LED to red (searching/approaching)
        self.drone.set_led("red")
        
        # Fly to delivery position (2m above target)
        delivery_position = self.flight_strategy.get_next_position(
            self.drone,
            target_position
        )
        self.drone.go_to(delivery_position)
        self.drone.hover()
        
        # Simulate payload delivery sequence
        time.sleep(1.0)
        
        # Change LED to green (delivery complete)
        self.drone.set_led("green")
        
        # Hold position briefly
        time.sleep(2.0)