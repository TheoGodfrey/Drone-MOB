"""
Minimal camera interface for single-drone system
"""
import time
import random
from .drone import Position

class Detection:
    """Detected target"""
    def __init__(self, position: Position, is_person: bool, confidence: float):
        self.position = position
        self.is_person = is_person
        self.confidence = confidence

class Camera:
    """Simplified camera interface for single-drone system"""
    def __init__(self, is_simulated: bool = True):
        self.is_simulated = is_simulated
        self.connected = False
        self.detection_count = 0
    
    def connect(self) -> bool:
        """Connect to camera (simplified)"""
        self.connected = True
        return True
    
    def capture(self) -> dict:
        """Capture frame (simplified)"""
        return {"timestamp": time.time(), "data": "frame"}
    
    def detect(self, frame: dict) -> list:
        """Detect objects with simulation"""
        detections = []
        
        # Simulate occasional detections for testing
        if self.is_simulated and random.random() < 0.2:  # 20% chance
            self.detection_count += 1
            x = random.uniform(-200, 200)
            y = random.uniform(-200, 200)
            detections.append(Detection(
                Position(x, y, 0), 
                True, 
                random.uniform(0.7, 0.95)
            ))
        
        return detections