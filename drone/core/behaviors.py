"""
Reusable asynchronous mission behaviors
(Refactored for async, AI/Tracker, and Geolocation)
"""
import asyncio
import time
from .position import Position
from .drone import Drone, Telemetry
from .cameras.dual_camera import DualCameraSystem
from .detection.fusion_detector import FusionDetector
# --- FIX: Import specific configs ---
from .config_models import Settings, PrecisionHoverConfig, CameraIntrinsicsConfig
from typing import List, Tuple
from .cameras.base import Detection
from .navigation import CameraIntrinsics, image_to_world_position

class SearchBehavior:
    """Encapsulates search behavior with dual camera and fusion tracker."""
    
    def __init__(self, 
                 drone: Drone, 
                 dual_camera: DualCameraSystem,
                 search_strategy, 
                 flight_strategy, 
                 config: Settings,
                 mqtt: "MqttClient", # <-- FIX
                 logger: "MissionLogger"): # <-- FIX
        
        self.drone = drone
        self.dual_camera = dual_camera
        self.search_strategy = search_strategy
        self.flight_strategy = flight_strategy
        self.config = config
        self.mqtt = mqtt # <-- FIX
        self.logger = logger # <-- FIX
        self.iteration = 0
        
        self.detector = FusionDetector(config.detection)
        
        # --- FIX: Correctly access intrinsics from *visual* camera ---
        self.intrinsics = CameraIntrinsics(config.cameras.visual.intrinsics)
        # -------------------------------------------------------------
        
        self.last_detections: List[Detection] = []
    
    async def search_step(self) -> Tuple[bool, Detection | None]:
        """
        Execute one asynchronous search step.
        This is now a *passive scan* commanded by the Coordinator.
        Returns: (should_continue, confirmed_detection_or_none)
        """
        
        # --- FIX: This is now a passive scan loop ---
        # The drone no longer moves itself during 'SEARCHING'
        # It just scans at its current location.
        # The Coordinator's AI tells it where to go via GOTO_WAYPOINT commands.
        self.logger.log(f"Scanning at {self.drone.telemetry.position}...", "debug")
        
        # 1. Capture synchronized frame
        dual_frame = await self.dual_camera.capture_synchronized()
        
        # 2. Get latest telemetry
        current_telemetry = self.drone.telemetry
        
        # 3. Detect
        confirmed_detections = await self.detector.detect(dual_frame)
        self.last_detections = confirmed_detections
        
        self.iteration += 1
        
        # 4. Report *raw* detections to Coordinator's AI
        # This feeds the probabilistic map
        if confirmed_detections:
            best_detection = max(confirmed_detections, key=lambda d: d.confidence)
            
            best_detection.position_world = self._image_to_world_position(
                best_detection.position_image,
                current_telemetry
            )
            
            # Send an event to the Coordinator's Probabilistic AI
            await self.mqtt.publish(f"fleet/event/{self.drone.id}", {
                "type": "AI_DETECTION",
                "data": {
                    "position": best_detection.position_world.model_dump(),
                    "confidence": best_detection.confidence
                }
            })
            
            # --- FIX: Check if this detection is a *confirmed* target ---
            # This logic is now simplified: if the tracker has high confidence,
            # we ask the operator to confirm.
            if best_detection.confidence > self.config.detection.fusion.fusion_threshold:
                 # Return the detection to trigger 'target_sighted'
                 return True, best_detection

        # 5. Check for max iterations
        max_iter = self.config.mission.max_search_iterations
        if self.iteration >= max_iter:
            return False, None # Search complete (timeout)
        
        return True, None  # Keep searching
        # -------------------------------------------
    
    def get_last_detections(self) -> List[Detection]:
        return self.last_detections

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
    
    # --- FIX: Correctly accept PrecisionHoverConfig ---
    def __init__(self, drone: Drone, flight_strategy, config: PrecisionHoverConfig):
        self.drone = drone
        self.flight_strategy = flight_strategy
        self.config = config # This is now the PrecisionHoverConfig
    # -------------------------------------------------
    
    async def deliver_to(self, target_position: Position):
        """Deliver payload to target with LED signaling."""
        await self.drone.set_led("red")
        
        # --- FIX: Access config directly ---
        delivery_position = Position(
             target_position.x, 
             target_position.y,
             target_position.z + self.config.altitude_offset
        )
        # -----------------------------------
        
        await self.drone.go_to(delivery_position)
        await self.drone.hover()
        await asyncio.sleep(1.0)
        await self.drone.set_led("green")
        await asyncio.sleep(2.0)

