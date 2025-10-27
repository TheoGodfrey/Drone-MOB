"""
Main entry point for single-drone MOB system with dual cameras
"""

import yaml
import sys
from pathlib import Path
from core.drone import Drone
from core.cameras.dual_camera import DualCameraSystem
from core.cameras.thermal.simulated import SimulatedThermalCamera
from core.cameras.visual.simulated import SimulatedVisualCamera
from core.logger import MissionLogger
from core.mission import MissionController
from strategies import get_search_strategy, get_flight_strategy

def load_config(config_path: str = "config/mission_config.yaml") -> dict:
    """Load configuration"""
    config_file = Path(__file__).parent / config_path
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def create_cameras(config: dict) -> DualCameraSystem:
    """Create camera system based on configuration"""
    camera_config = config.get('cameras', {})
    
    # Create thermal camera
    thermal_type = camera_config.get('thermal', {}).get('type', 'simulated')
    if thermal_type == 'simulated':
        thermal_res = tuple(camera_config['thermal']['resolution'])
        thermal_cam = SimulatedThermalCamera(
            resolution=thermal_res,
            water_temp=camera_config['thermal'].get('water_temp', 15.0),
            ambient_temp=camera_config['thermal'].get('ambient_temp', 20.0)
        )
    else:
        raise ValueError(f"Unknown thermal camera type: {thermal_type}")
    
    # Create visual camera
    visual_type = camera_config.get('visual', {}).get('type', 'simulated')
    if visual_type == 'simulated':
        visual_res = tuple(camera_config['visual']['resolution'])
        visual_cam = SimulatedVisualCamera(resolution=visual_res)
    else:
        raise ValueError(f"Unknown visual camera type: {visual_type}")
    
    # Create dual camera system
    recording_enabled = camera_config.get('recording', {}).get('enabled', True)
    dual_camera = DualCameraSystem(thermal_cam, visual_cam, recording_enabled)
    
    return dual_camera

def main():
    """Main entry point with dual camera support"""
    try:
        # Load configuration
        config = load_config()
        
        # Get drone configuration
        drone_config = config['drones'][0]
        drone_type = drone_config.get('type', 'simulated')
        drone_id = drone_config.get('id', 'drone_1')
        is_simulated = drone_type == 'simulated'
        
        # Create components
        drone = Drone(is_simulated, drone_id=drone_id)
        drone.dual_camera = create_cameras(config)
        
        search_strategy = get_search_strategy(config['strategies']['search']['algorithm'])
        flight_strategy = get_flight_strategy(config['strategies']['flight']['algorithm'])
        
        logger = MissionLogger()
        
        # Create mission controller
        mission = MissionController(
            drone=drone,
            search_strategy=search_strategy,
            flight_strategy=flight_strategy,
            config=config,
            logger=logger
        )
        
        # Execute mission
        input("Press ENTER to start mission (Ctrl+C to abort)...")
        mission.execute()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()