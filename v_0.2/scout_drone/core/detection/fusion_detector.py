"""
Sensor fusion detector - combines thermal + visual for high confidence
"""
from typing import List, Tuple, Optional
from ..cameras.base import Detection
from ..cameras.dual_camera import DualFrame
from .thermal_detector import ThermalDetector
from .visual_detector import VisualDetector

class FusionDetector:
    """Fuses thermal and visual detections for high-confidence MOB detection"""
    
    def __init__(self, config: dict):
        """
        Initialize fusion detector
        
        Config parameters:
            - thermal_weight: Weight for thermal detection (default: 0.7)
            - visual_weight: Weight for visual confirmation (default: 0.3)
            - fusion_threshold: Min confidence for fusion detection (default: 0.75)
            - max_position_error: Max pixel distance to associate detections (default: 50)
        """
        self.thermal_detector = ThermalDetector(config.get('thermal', {}))
        self.visual_detector = VisualDetector(config.get('visual', {}))
        
        self.thermal_weight = config.get('thermal_weight', 0.7)
        self.visual_weight = config.get('visual_weight', 0.3)
        self.fusion_threshold = config.get('fusion_threshold', 0.75)
        self.max_position_error = config.get('max_position_error', 50)
        
        self.detection_history = []
        self.max_history = 10
    
    def detect(self, dual_frame: DualFrame) -> List[Detection]:
        """
        Perform sensor fusion detection
        
        Returns detections that are confirmed by BOTH sensors
        """
        # Get detections from both sensors
        thermal_detections = self.thermal_detector.detect(dual_frame.thermal)
        visual_detections = self.visual_detector.detect(dual_frame.visual)
        
        # Fuse detections
        fused_detections = self._fuse_detections(
            thermal_detections,
            visual_detections,
            dual_frame
        )
        
        # Track detection history for temporal filtering
        self.detection_history.append(len(fused_detections) > 0)
        if len(self.detection_history) > self.max_history:
            self.detection_history.pop(0)
        
        return fused_detections
    
    def _fuse_detections(
        self,
        thermal_detections: List[Detection],
        visual_detections: List[Detection],
        dual_frame: DualFrame
    ) -> List[Detection]:
        """Fuse thermal and visual detections"""
        
        fused = []
        
        # For each thermal detection, look for visual confirmation
        for thermal_det in thermal_detections:
            # Find closest visual detection
            visual_match, distance = self._find_closest_detection(
                thermal_det,
                visual_detections
            )
            
            if visual_match and distance < self.max_position_error:
                # Calculate fused confidence
                fused_confidence = (
                    self.thermal_weight * thermal_det.confidence +
                    self.visual_weight * visual_match.confidence
                )
                
                # Only accept if above fusion threshold
                if fused_confidence >= self.fusion_threshold:
                    # Create fused detection
                    fused_detection = Detection(
                        position_image=thermal_det.position_image,
                        position_world=thermal_det.position_world,
                        confidence=fused_confidence,
                        is_person=True,  # Both confirmed
                        source='fusion',
                        metadata={
                            'thermal_confidence': thermal_det.confidence,
                            'visual_confidence': visual_match.confidence,
                            'position_error_pixels': distance,
                            'thermal_temp': thermal_det.metadata.get('temperature', 0),
                            'has_visual_confirmation': True
                        }
                    )
                    fused.append(fused_detection)
            else:
                # Thermal detection without visual confirmation
                # Lower confidence, but still report if thermal is very confident
                if thermal_det.confidence > 0.85:
                    thermal_det.metadata['has_visual_confirmation'] = False
                    thermal_det.confidence *= 0.8  # Reduce confidence
                    fused.append(thermal_det)
        
        return fused
    
    def _find_closest_detection(
        self,
        thermal_det: Detection,
        visual_detections: List[Detection]
    ) -> Tuple[Optional[Detection], float]:
        """Find the closest visual detection to thermal detection"""
        
        if not visual_detections:
            return None, float('inf')
        
        tx, ty = thermal_det.position_image
        
        closest = None
        min_distance = float('inf')
        
        for visual_det in visual_detections:
            vx, vy = visual_det.position_image
            distance = ((tx - vx)**2 + (ty - vy)**2) ** 0.5
            
            if distance < min_distance:
                min_distance = distance
                closest = visual_det
        
        return closest, min_distance
    
    def get_detection_stability(self) -> float:
        """Get detection stability (0.0-1.0) based on history"""
        if not self.detection_history:
            return 0.0
        
        return sum(self.detection_history) / len(self.detection_history)