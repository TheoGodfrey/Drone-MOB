"""
Geometry utilities for position and coordinate handling
"""

import math
from dataclasses import dataclass
from typing import Tuple


@dataclass
class Position:
    """3D position in local frame"""
    x: float  # meters (East)
    y: float  # meters (North)
    altitude: float  # meters above ground
    
    def distance_to(self, other: 'Position') -> float:
        """Calculate 3D Euclidean distance to another position"""
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.altitude - other.altitude
        return math.sqrt(dx**2 + dy**2 + dz**2)
    
    def horizontal_distance_to(self, other: 'Position') -> float:
        """Calculate horizontal distance only (ignore altitude)"""
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx**2 + dy**2)
    
    def __str__(self) -> str:
        return f"Position(x={self.x:.1f}, y={self.y:.1f}, alt={self.altitude:.1f})"


def pixel_to_world(
    pixel_x: float,
    pixel_y: float,
    altitude: float,
    fov_horizontal: float,
    fov_vertical: float,
    resolution: Tuple[int, int]
) -> Position:
    """
    Convert pixel coordinates to world position
    
    Args:
        pixel_x, pixel_y: Pixel coordinates in image
        altitude: Current drone altitude (m)
        fov_horizontal, fov_vertical: Camera field of view (degrees)
        resolution: Camera resolution (width, height) in pixels
    
    Returns:
        Position in world coordinates (relative to drone)
    """
    # Calculate ground coverage
    fov_h_rad = math.radians(fov_horizontal)
    fov_v_rad = math.radians(fov_vertical)
    
    ground_width = 2 * altitude * math.tan(fov_h_rad / 2)
    ground_height = 2 * altitude * math.tan(fov_v_rad / 2)
    
    # Convert pixel to position relative to image center
    center_x = resolution[0] / 2
    center_y = resolution[1] / 2
    
    offset_x = (pixel_x - center_x) / resolution[0] * ground_width
    offset_y = (pixel_y - center_y) / resolution[1] * ground_height
    
    return Position(offset_x, offset_y, 0)


def pixel_area_to_meters(
    pixel_area: float,
    altitude: float,
    fov_horizontal: float,
    resolution_x: int
) -> float:
    """
    Convert pixel area to real-world area in m²
    
    Args:
        pixel_area: Area in pixels²
        altitude: Current drone altitude (m)
        fov_horizontal: Camera horizontal FOV (degrees)
        resolution_x: Image width in pixels
    
    Returns:
        Area in m²
    """
    # Calculate ground sample distance (GSD)
    fov_rad = math.radians(fov_horizontal)
    ground_width = 2 * altitude * math.tan(fov_rad / 2)
    meters_per_pixel = ground_width / resolution_x
    
    # Convert pixel area to m²
    area_m2 = pixel_area * (meters_per_pixel ** 2)
    
    return area_m2
