"""
Pydantic models for validating the mission_config.yaml file.
"""
from typing import List, Tuple, Literal

from pydantic import BaseModel, Field

# --- Camera Models ---

class ThermalCameraConfig(BaseModel):
    type: Literal["simulated", "flir_lepton", "seek_thermal"]
    resolution: Tuple[int, int]
    water_temp: float = 15.0
    ambient_temp: float = 20.0

class VisualCameraConfig(BaseModel):
    type: Literal["simulated", "opencv", "picamera"]
    resolution: Tuple[int, int]

class RecordingConfig(BaseModel):
    enabled: bool = True
    output_dir: str = "recordings"

class CameraConfig(BaseModel):
    thermal: ThermalCameraConfig
    visual: VisualCameraConfig
    recording: RecordingConfig

# --- Detection Models ---

class ThermalDetectionConfig(BaseModel):
    temp_threshold: float = 10.0
    min_area: int = 50
    max_area: int = 500
    min_confidence: float = 0.5

class VisualDetectionConfig(BaseModel):
    use_color: bool = True
    use_motion: bool = True
    min_confidence: float = 0.6

class FusionDetectionConfig(BaseModel):
    thermal_weight: float = 0.7
    visual_weight: float = 0.3
    fusion_threshold: float = 0.75
    max_position_error: int = 50

class DetectionConfig(BaseModel):
    method: Literal["fusion", "thermal_only", "visual_only"]
    thermal: ThermalDetectionConfig
    visual: VisualDetectionConfig
    fusion: FusionDetectionConfig

# --- Strategy Models ---

class SearchAreaConfig(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

class SearchStrategyConfig(BaseModel):
    algorithm: Literal["vertical_ascent", "random"]
    area: SearchAreaConfig
    size: float = 1000.0

class FlightStrategyConfig(BaseModel):
    algorithm: Literal["precision_hover", "direct"]

class StrategyConfig(BaseModel):
    search: SearchStrategyConfig
    flight: FlightStrategyConfig

# --- Other Component Models ---

class MissionConfig(BaseModel):
    max_search_iterations: int = 30
    search_timeout_seconds: int = 300

class LoggingConfig(BaseModel):
    log_dir: str = "logs"
    max_logs: int = 50

class DroneConfig(BaseModel):
    id: str
    type: Literal["simulated", "real"]
    role: str

class VerticalAscentConfig(BaseModel):
    max_altitude: float = 150.0
    step_size: float = 5.0

class PrecisionHoverConfig(BaseModel):
    altitude_offset: float = 2.0

# --- Top-Level Settings Model ---

class Settings(BaseModel):
    """The root model for the entire mission_config.yaml."""
    mission: MissionConfig
    logging: LoggingConfig
    drones: List[DroneConfig]
    cameras: CameraConfig
    detection: DetectionConfig
    strategies: StrategyConfig
    vertical_ascent: VerticalAscentConfig = Field(default_factory=VerticalAscentConfig)
    precision_hover: PrecisionHoverConfig = Field(default_factory=PrecisionHoverConfig)