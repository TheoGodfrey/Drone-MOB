"""Position utilities - shared across system"""
from dataclasses import dataclass

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