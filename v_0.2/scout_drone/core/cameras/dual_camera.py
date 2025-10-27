"""
Synchronized dual camera system (Thermal + Visual)
"""
import time
from dataclasses import dataclass
from typing import Optional, Tuple
from .base import ThermalFrame, VisualFrame

@dataclass
class DualFrame:
    """Synchronized frame from both cameras"""
    thermal: ThermalFrame
    visual: VisualFrame
    sync_timestamp: float
    time_delta: float  # Sync accuracy (ms)

class DualCameraSystem:
    """Manages thermal + visual camera system"""
    
    def __init__(self, thermal_camera, visual_camera, recording_enabled: bool = True):
        """
        Initialize dual camera system
        
        Args:
            thermal_camera: ThermalCamera instance
            visual_camera: VisualCamera instance
            recording_enabled: Enable video recording
        """
        self.thermal = thermal_camera
        self.visual = visual_camera
        self.recording_enabled = recording_enabled
        self.recorder = None
        
        self.connected = False
        self.frame_count = 0
        
        # Sync parameters
        self.max_sync_delta = 0.1  # Max 100ms between frames
    
    def connect(self) -> bool:
        """Connect both cameras"""
        print("[DualCamera] Connecting cameras...")
        
        thermal_ok = self.thermal.connect()
        visual_ok = self.visual.connect()
        
        if not (thermal_ok and visual_ok):
            print("[DualCamera] Failed to connect cameras")
            return False
        
        # Initialize video recorder if enabled
        if self.recording_enabled:
            from core.recording.video_recorder import VideoRecorder
            self.recorder = VideoRecorder(
                visual_resolution=self.visual.get_resolution(),
                thermal_resolution=self.thermal.get_resolution()
            )
            self.recorder.start()
        
        self.connected = True
        print("[DualCamera] Both cameras connected")
        return True
    
    def capture_synchronized(self) -> DualFrame:
        """Capture synchronized frame from both cameras"""
        if not self.connected:
            raise RuntimeError("Cameras not connected")
        
        # Capture from both cameras as close in time as possible
        sync_start = time.time()
        
        thermal_frame = self.thermal.capture()
        visual_frame = self.visual.capture()
        
        sync_timestamp = time.time()
        time_delta = abs(thermal_frame.timestamp - visual_frame.timestamp) * 1000  # ms
        
        self.frame_count += 1
        
        # Record if enabled
        if self.recorder:
            self.recorder.write_frame(thermal_frame, visual_frame)
        
        # Warn if sync is poor
        if time_delta > self.max_sync_delta * 1000:
            print(f"[DualCamera] Warning: Sync delta {time_delta:.1f}ms > {self.max_sync_delta*1000}ms")
        
        return DualFrame(
            thermal=thermal_frame,
            visual=visual_frame,
            sync_timestamp=sync_timestamp,
            time_delta=time_delta
        )
    
    def disconnect(self):
        """Disconnect both cameras and stop recording"""
        if self.recorder:
            self.recorder.stop()
        
        self.thermal.disconnect()
        self.visual.disconnect()
        self.connected = False
        print("[DualCamera] Disconnected")