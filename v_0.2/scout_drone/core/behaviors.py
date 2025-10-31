"""
Reusable asynchronous mission behaviors
(Refactored for async, AI/Tracker, and Geolocation)
"""
import asyncio
import time
from .position import Position
from .drone import Drone, Telemetry # NEW: Import Telemetry
from .cameras.dual_camera import DualCameraSystem
from .detection.fusion_detector import FusionDetector
from .config_models import Settings
from typing import List, Tuple
from .cameras.base import Detection
# NEW: Import geolocation tools
from .navigation import CameraIntrinsics, image_to_world_position

class SearchBehavior:
    """Encapsulates search behavior with dual camera and fusion tracker."""
    
    def __init__(self, 
                 drone: Drone, 
                 dual_camera: DualCameraSystem,
                 search_strategy, 
                 flight_strategy, 
                 config: Settings):
        
        self.drone = drone
        self.dual_camera = dual_camera
        self.search_strategy = search_strategy
        self.flight_strategy = flight_strategy
        self.config = config
        self.iteration = 0
        
        self.detector = FusionDetector(config.detection)
        
        # NEW: Create an intrinsics object from the config
        self.intrinsics = CameraIntrinsics(config.cameras.intrinsics)
        
        self.last_detections: List[Detection] = []
    
    async def search_step(self) -> Tuple[bool, Detection | None]:
        """
        Execute one asynchronous search step.
        Returns: (should_continue, confirmed_detection_or_none)
        """
        max_iter = self.config.mission.max_search_iterations
        if self.iteration >= max_iter:
            return False, None
        
        # 1. Get next search position
        search_area_cfg = self.config.strategies.search.area
        search_area_pos = Position(search_area_cfg.x, search_area_cfg.y, search_area_cfg.z)
        search_size = self.config.strategies.search.size
        
        next_position = self.search_strategy.get_next_position(
            self.drone, search_area_pos, search_size
        )
        
        # 2. Fly to position
        flight_position = self.flight_strategy.get_next_position(self.drone, next_position)
        await self.drone.go_to(flight_position)
        
        # 3. Capture synchronized frame
        dual_frame = await self.dual_camera.capture_synchronized()
        
        # 4. Get latest telemetry (crucial for geolocation)
        # We assume update_telemetry() was called in the main mission loop,
        # so self.drone.telemetry is up-to-date.
        current_telemetry = self.drone.telemetry
        
        # 5. Detect
        confirmed_detections = await self.detector.detect(dual_frame)
        self.last_detections = confirmed_detections
        
        self.iteration += 1
        
        # 6. Return first high-confidence detection
        if confirmed_detections:
            best_detection = max(confirmed_detections, key=lambda d: d.confidence)
            
            # --- CHANGED: Use real geolocation ---
            best_detection.position_world = self._image_to_world_position(
                best_detection.position_image,
                current_telemetry
            )
            return False, best_detection  # Found!
        
        return True, None  # Keep searching
    
    def get_last_detections(self) -> List[Detection]:
        return self.last_detections

    # --- CHANGED: This now calls the real function ---
    def _image_to_world_position(self, 
                                 image_pos: tuple, 
                                 drone_telemetry: Telemetry) -> Position:
        """
        Wrapper for the real geolocation function.
        """
        return image_to_world_position(
            pixel=image_pos,
            drone_telemetry=drone_telemetry,
            intrinsics=self.intrinsics
            # ground_level_z can be passed from config if needed
        )

class DeliveryBehavior:
    """Encapsulates payload delivery with LED signaling."""
    
    def __init__(self, drone: Drone, flight_strategy):
        self.drone = drone
        self.flight_strategy = flight_strategy
    
    async def deliver_to(self, target_position: Position):
        """Deliver payload to target with LED signaling."""
        await self.drone.set_led("red")
        
        # Fly to delivery position (e.g., 2m above target)
        # We get the altitude offset from the config
        hover_config = self.drone.config.precision_hover # <-- This is a bit of a hack
        delivery_position = Position(
             target_position.x, 
             target_position.y,
             target_position.z + hover_config.altitude_offset
        )
        
        await self.drone.go_to(delivery_position)
        await self.drone.hover()
        await asyncio.sleep(1.0)
        await self.drone.set_led("green")
        await asyncio.sleep(2.0)
