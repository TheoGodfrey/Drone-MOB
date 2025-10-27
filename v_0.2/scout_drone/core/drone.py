"""
Minimal drone interface for single-drone system
"""

from dataclasses import dataclass
import time

@dataclass
class Position:
    """3D position (x, y, z)"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def distance_to(self, other: 'Position') -> float:
        """Calculate Euclidean distance"""
        return ((self.x - other.x)**2 + 
                (self.y - other.y)**2 + 
                (self.z - other.z)**2)**0.5

class Drone:
    """Simplified drone interface for single-drone system"""
    def __init__(self, is_simulated: bool = True):
        self.is_simulated = is_simulated
        self.position = Position(0, 0, 0)
        self.battery = 100.0
        self.connected = False
        self.state = "IDLE"
        self.last_heartbeat = time.time()
        self.camera = None
    
    def connect(self) -> bool:
        """Connect to drone (simplified)"""
        self.connected = True
        return True
    
    def takeoff(self, altitude: float) -> bool:
        """Takeoff (simplified)"""
        self.state = "CLIMBING"
        return True
    
    def go_to(self, position: Position) -> bool:
        """Navigate to position (simplified)"""
        self.state = "APPROACHING"
        # Simulate movement in simulation mode
        if self.is_simulated:
            self.position = position
        return True
    
    def hover(self) -> bool:
        """Hover (simplified)"""
        self.state = "ON_TARGET"
        return True
    
    def land(self) -> bool:
        """Land (simplified)"""
        self.state = "LANDING"
        return True
    
    def is_healthy(self) -> bool:
        """Check if drone is healthy"""
        return self.connected and self.battery > 5.0
    
    def update_position(self, new_position: Position) -> None:
        """Update drone position (for simulation)"""
        self.position = new_position