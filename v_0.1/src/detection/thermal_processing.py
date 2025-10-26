"""
Thermal image processing data structures
"""

from dataclasses import dataclass
from typing import Optional, Any

# Import from absolute path when run as module
try:
    from utils.geometry import Position
    from core.state_machine import TargetType
except ImportError:
    # Fallback for when importing from different contexts
    import sys
    from pathlib import Path
    src_path = Path(__file__).parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from utils.geometry import Position
    from core.state_machine import TargetType


@dataclass
class ThermalFrame:
    """Thermal image frame"""
    data: Any  # Thermal image data (numpy array or None for simulation)
    metadata: dict
    timestamp: float = 0.0


@dataclass
class ThermalBlob:
    """A contiguous hot region in thermal image"""
    center_x: float  # pixel coordinates
    center_y: float
    area: float  # pixels²
    mean_temp: float  # °C
    max_temp: float  # °C
    min_temp: float  # °C
    aspect_ratio: float  # width/height (for shape analysis)
    
    def __str__(self) -> str:
        return (f"ThermalBlob(center=({self.center_x:.0f}, {self.center_y:.0f}), "
                f"area={self.area:.0f}px², temp={self.mean_temp:.1f}°C)")


@dataclass
class Detection:
    """Detected target with classification"""
    position: Position
    target_type: TargetType
    confidence: float
    temperature: float  # °C
    size: float  # m²
    
    def is_person(self) -> bool:
        """Check if detection is classified as person"""
        return self.target_type == TargetType.PERSON
    
    def is_boat(self) -> bool:
        """Check if detection is classified as boat"""
        return self.target_type == TargetType.BOAT
    
    def __str__(self) -> str:
        return (f"Detection({self.target_type.value}, "
                f"pos={self.position}, "
                f"conf={self.confidence:.2f}, "
                f"temp={self.temperature:.1f}°C, "
                f"size={self.size:.2f}m²)")
