"""
Minimal drone interface for single-drone system
"""

import time
from .position import Position

class Drone:
    """Simplified drone interface for single-drone system"""
    def __init__(self, is_simulated: bool = True, drone_id: str = "drone_0"):
        self.id = drone_id
        self.is_simulated = is_simulated
        self.position = Position(0, 0, 0)
        self.battery = 100.0
        self.connected = False
        self.state = "IDLE"
        self.last_heartbeat = time.time()
        self.camera = None
        self.health_history = []
    
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
    
    def record_health(self):
        """Record current health snapshot"""
        self.health_history.append({
            'timestamp': time.time(),
            'battery': self.battery,
            'connected': self.connected,
            'healthy': self.is_healthy()
        })
        
        # Keep only last 10 records
        if len(self.health_history) > 10:
            self.health_history.pop(0)