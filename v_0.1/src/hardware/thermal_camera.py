"""
Thermal camera interface
Supports both real hardware and simulation
"""

import time
from typing import List
from abc import ABC, abstractmethod

try:
    from detection.thermal_processing import ThermalFrame, ThermalBlob, Detection
    from detection.classifier import ThermalClassifier
except ImportError:
    import sys
    from pathlib import Path
    src_path = Path(__file__).parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from detection.thermal_processing import ThermalFrame, ThermalBlob, Detection
    from detection.classifier import ThermalClassifier


class ThermalCamera(ABC):
    """Abstract base class for thermal camera"""
    
    def __init__(self, classifier: ThermalClassifier):
        self.classifier = classifier
    
    @abstractmethod
    def connect(self):
        """Connect to camera"""
        pass
    
    @abstractmethod
    def capture_frame(self) -> ThermalFrame:
        """Capture thermal image"""
        pass
    
    @abstractmethod
    def find_thermal_blobs(self, frame: ThermalFrame) -> List[ThermalBlob]:
        """Find hot regions in thermal image"""
        pass
    
    def detect_and_classify(self, frame: ThermalFrame) -> List[Detection]:
        """Find thermal blobs and classify them"""
        blobs = self.find_thermal_blobs(frame)
        
        detections = []
        for blob in blobs:
            detection = self.classifier.classify_blob(blob)
            if detection:
                detections.append(detection)
        
        return detections
    
    def set_altitude(self, altitude: float):
        """Update altitude for size calculations"""
        self.classifier.set_altitude(altitude)


class SimulatedThermalCamera(ThermalCamera):
    """Simulated thermal camera for testing"""
    
    def __init__(self, classifier: ThermalClassifier):
        super().__init__(classifier)
        self.frame_count = 0
        self.is_connected = False
    
    def connect(self):
        """Simulate connection"""
        print("[Thermal] Connecting to simulated thermal camera...")
        time.sleep(0.5)
        self.is_connected = True
        print("[Thermal] ✓ Connected (SIMULATION MODE)")
    
    def capture_frame(self) -> ThermalFrame:
        """Simulate frame capture"""
        self.frame_count += 1
        return ThermalFrame(
            data=None,
            metadata={'frame_number': self.frame_count},
            timestamp=time.time()
        )
    
    def find_thermal_blobs(self, frame: ThermalFrame) -> List[ThermalBlob]:
        """
        Simulate thermal blob detection
        
        Frame 5: Detect a boat
        Frame 12: Detect a person
        """
        blobs = []
        
        # Simulate boat detection at frame 5
        if self.frame_count == 5:
            blobs.append(ThermalBlob(
                center_x=80,
                center_y=60,
                area=500,  # Large (boat)
                mean_temp=45.0,
                max_temp=85.0,  # Hot engine
                min_temp=25.0,
                aspect_ratio=2.5  # Elongated
            ))
        
        # Simulate person detection at frame 12
        elif self.frame_count == 12:
            blobs.append(ThermalBlob(
                center_x=100,
                center_y=80,
                area=50,  # Small (person)
                mean_temp=33.0,
                max_temp=36.5,
                min_temp=31.0,
                aspect_ratio=1.2  # Roughly circular
            ))
        
        return blobs


class FLIRLeptonCamera(ThermalCamera):
    """FLIR Lepton thermal camera"""
    
    def __init__(self, classifier: ThermalClassifier):
        super().__init__(classifier)
        self.camera = None
    
    def connect(self):
        """Connect to FLIR Lepton"""
        try:
            from flirpy.camera.lepton import Lepton
            print("[Thermal] Connecting to FLIR Lepton...")
            self.camera = Lepton()
            print("[Thermal] ✓ Connected to FLIR Lepton")
        except ImportError:
            raise RuntimeError(
                "flirpy not installed. Install with: pip install flirpy"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to connect to thermal camera: {e}")
    
    def capture_frame(self) -> ThermalFrame:
        """Capture frame from FLIR Lepton"""
        data = self.camera.grab()
        return ThermalFrame(
            data=data,
            metadata={},
            timestamp=time.time()
        )
    
    def find_thermal_blobs(self, frame: ThermalFrame) -> List[ThermalBlob]:
        """
        Find thermal blobs using image processing
        
        This is a simplified example. Real implementation should use:
        - Adaptive thresholding
        - Morphological operations
        - Contour detection (cv2.findContours)
        """
        import numpy as np
        
        # Simple threshold: anything above 25°C
        threshold = 25.0
        mask = frame.data > threshold
        
        # TODO: Implement proper blob detection
        # Use cv2.findContours to find connected components
        # Calculate blob statistics (area, centroid, aspect ratio, etc.)
        
        # For now, return empty list
        # Real implementation would analyze contours
        return []


class SeekThermalCamera(ThermalCamera):
    """Seek Thermal camera"""
    
    def __init__(self, classifier: ThermalClassifier):
        super().__init__(classifier)
        self.camera = None
    
    def connect(self):
        """Connect to Seek Thermal"""
        try:
            from pyseek import SeekThermal
            print("[Thermal] Connecting to Seek Thermal...")
            self.camera = SeekThermal()
            print("[Thermal] ✓ Connected to Seek Thermal")
        except ImportError:
            raise RuntimeError(
                "pyseek not installed. Install with: pip install pyseek"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to connect to thermal camera: {e}")
    
    def capture_frame(self) -> ThermalFrame:
        """Capture frame from Seek Thermal"""
        data = self.camera.read()
        return ThermalFrame(
            data=data,
            metadata={},
            timestamp=time.time()
        )
    
    def find_thermal_blobs(self, frame: ThermalFrame) -> List[ThermalBlob]:
        """Find thermal blobs in Seek thermal image"""
        # Similar to FLIR implementation
        # Use image processing to find hot regions
        return []
