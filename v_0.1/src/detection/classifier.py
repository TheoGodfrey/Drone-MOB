"""
Thermal target classification (Person vs Boat)
"""

from typing import Optional

# Import from absolute path
try:
    from detection.thermal_processing import ThermalBlob, Detection
    from core.state_machine import TargetType
    from utils.geometry import Position, pixel_to_world, pixel_area_to_meters
except ImportError:
    import sys
    from pathlib import Path
    src_path = Path(__file__).parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from detection.thermal_processing import ThermalBlob, Detection
    from core.state_machine import TargetType
    from utils.geometry import Position, pixel_to_world, pixel_area_to_meters


class ThermalClassifier:
    """Classifies thermal signatures as person, boat, or other"""
    
    def __init__(self, config: dict):
        """
        Args:
            config: Detection configuration from mission_config.yaml
        """
        self.config = config
        
        # Camera parameters
        self.fov_horizontal = config['camera']['fov_horizontal']
        self.fov_vertical = config['camera']['fov_vertical']
        self.resolution = (
            config['camera']['resolution_x'],
            config['camera']['resolution_y']
        )
        
        # Detection thresholds
        self.person_temp_min = config['detection']['person_temp_min']
        self.person_temp_max = config['detection']['person_temp_max']
        self.person_size_min = config['detection']['person_size_min']
        self.person_size_max = config['detection']['person_size_max']
        self.boat_size_min = config['detection']['boat_size_min']
        self.boat_temp_threshold = config['detection']['boat_temp_threshold']
        
        # Current altitude (updated by camera)
        self.altitude = 50.0
    
    def set_altitude(self, altitude: float):
        """Update current altitude for size calculations"""
        self.altitude = altitude
    
    def classify_blob(self, blob: ThermalBlob) -> Optional[Detection]:
        """
        Classify a thermal blob as person, boat, or other
        
        Args:
            blob: Thermal blob from image processing
        
        Returns:
            Detection with classification, or None if not interesting
        """
        # Convert pixel measurements to real-world
        size_m2 = pixel_area_to_meters(
            blob.area,
            self.altitude,
            self.fov_horizontal,
            self.resolution[0]
        )
        
        position = pixel_to_world(
            blob.center_x,
            blob.center_y,
            self.altitude,
            self.fov_horizontal,
            self.fov_vertical,
            self.resolution
        )
        
        # Classify based on characteristics
        target_type, confidence = self._classify(blob, size_m2)
        
        # Log classification
        if target_type == TargetType.BOAT:
            print(f"[Classifier] 🚢 BOAT: {size_m2:.1f}m², {blob.max_temp:.1f}°C max")
        elif target_type == TargetType.PERSON:
            print(f"[Classifier] 🏊 PERSON: {size_m2:.1f}m², {blob.mean_temp:.1f}°C avg")
        else:
            print(f"[Classifier] ❓ Unknown: {size_m2:.1f}m², {blob.mean_temp:.1f}°C")
        
        return Detection(
            position=position,
            target_type=target_type,
            confidence=confidence,
            temperature=blob.mean_temp,
            size=size_m2
        )
    
    def _classify(self, blob: ThermalBlob, size_m2: float) -> tuple[TargetType, float]:
        """
        Determine target type and confidence
        
        Returns:
            (TargetType, confidence)
        """
        # Check if it's a BOAT
        if self._is_boat(blob, size_m2):
            return TargetType.BOAT, 0.9
        
        # Check if it's a PERSON
        if self._is_person(blob, size_m2):
            return TargetType.PERSON, 0.85
        
        # Unknown or debris
        return TargetType.DEBRIS, 0.3
    
    def _is_boat(self, blob: ThermalBlob, size_m2: float) -> bool:
        """
        Determine if blob characteristics match a boat
        
        Boats typically have:
        - Large size (> 5 m²)
        - Very hot spots from engine (> 50°C)
        - High aspect ratio (long and narrow)
        - Large temperature variance (hot engine, cooler hull)
        """
        is_large = size_m2 > self.boat_size_min
        has_hot_spot = blob.max_temp > self.boat_temp_threshold
        is_elongated = blob.aspect_ratio > 1.8
        has_variance = (blob.max_temp - blob.min_temp) > 20
        
        # Need at least 3/4 criteria for boat classification
        boat_score = sum([is_large, has_hot_spot, is_elongated, has_variance])
        
        return boat_score >= 3
    
    def _is_person(self, blob: ThermalBlob, size_m2: float) -> bool:
        """
        Determine if blob characteristics match a person
        
        Person in water typically has:
        - Small size (0.3 - 2 m²)
        - Body temperature (30-37°C, lower when wet)
        - Roughly circular (aspect ratio ~1-1.5)
        - Relatively uniform temperature
        """
        is_person_sized = (self.person_size_min <= size_m2 <= self.person_size_max)
        is_body_temp = (self.person_temp_min <= blob.mean_temp <= self.person_temp_max)
        is_roundish = blob.aspect_ratio < 1.8
        is_uniform = (blob.max_temp - blob.min_temp) < 10
        
        # Need at least 3/4 criteria for person classification
        person_score = sum([is_person_sized, is_body_temp, is_roundish, is_uniform])
        
        return person_score >= 3
