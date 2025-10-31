"""
Main entry point for single-drone MOB system.
(Refactored for GCS, Safety Decorators, and Async)
"""

import yaml
import sys
import asyncio 
import traceback
from pathlib import Path

# Import all core components
from core.drone import Drone, SimulatedFlightController, MavlinkController
from core.cameras.dual_camera import DualCameraSystem
from core.cameras.thermal.simulated import SimulatedThermalCamera
from core.cameras.visual.simulated import SimulatedVisualCamera
from core.logger import MissionLogger
from core.mission import MissionController
from strategies import get_search_strategy, get_flight_strategy
from core.config_models import Settings
from core.safety import CollisionAvoider, StubObstacleSensor # NEW

def load_config(config_path: str = "config/mission_config.yaml") -> Settings:
    """Load and validate configuration."""
    config_file = Path(__file__).parent / config_path
    try:
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        settings = Settings(**config_data)
        return settings
    except FileNotFoundError:
        print(f"FATAL: Configuration file not found at {config_file}")
        sys.exit(1)
    except Exception as e:
        print(f"FATAL: Error validating configuration file {config_file}:\n{e}")
        sys.exit(1)

def create_cameras(config: Settings) -> DualCameraSystem:
    """Create camera system based on validated configuration."""
    thermal_cfg = config.cameras.thermal
    if thermal_cfg.type == 'simulated':
        thermal_cam = SimulatedThermalCamera(
            resolution=thermal_cfg.resolution,
            water_temp=thermal_cfg.water_temp,
            ambient_temp=thermal_cfg.ambient_temp
        )
    else:
        raise ValueError(f"Real thermal camera type '{thermal_cfg.type}' not implemented.")
    
    visual_cfg = config.cameras.visual
    if visual_cfg.type == 'simulated':
        visual_cam = SimulatedVisualCamera(resolution=visual_cfg.resolution)
    else:
        raise ValueError(f"Real visual camera type '{visual_cfg.type}' not implemented.")
    
    recording_cfg = config.cameras.recording
    dual_camera = DualCameraSystem(
        thermal_cam, 
        visual_cam, 
        recording_cfg.enabled
    )
    return dual_camera

async def main():
    """Main asynchronous entry point."""
    try:
        # 1. Load configuration
        config = load_config()
        
        # 2. Get drone configuration
        drone_config = config.drones[0]
        
        # 3. Create components
        # --- NEW: Apply Safety Decorator ---
        
        # 3a. Create the base flight controller
        if drone_config.type == 'simulated':
            base_controller = SimulatedFlightController()
            print("Using SIMULATED Flight Controller")
        elif drone_config.type == 'real':
            base_controller = MavlinkController(connection_string="udp:127.0.0.1:14550")
            print("Using REAL (Mavlink) Flight Controller")
        else:
            raise ValueError(f"Unknown drone type in config: '{drone_config.type}'")
            
        # 3b. Create the sensor suite for the avoider
        # (In production, this would be a real sensor)
        obstacle_sensor = StubObstacleSensor()
            
        # 3c. Wrap the base controller with the safety decorator
        safe_controller = CollisionAvoider(base_controller, obstacle_sensor)
        
        # 3d. Create the Drone instance with the *safe* controller
        drone = Drone(safe_controller, drone_id=drone_config.id)
        
        # --- End of Safety Decorator ---
        
        dual_camera = create_cameras(config) 
        
        search_strategy = get_search_strategy(
            config.strategies.search.algorithm,
            config.vertical_ascent
        )
        flight_strategy = get_flight_strategy(
            config.strategies.flight.algorithm,
            config.precision_hover
        )
        
        logger = MissionLogger(log_dir=config.logging.log_dir)
        
        # 4. Create mission controller
        mission = MissionController(
            drone=drone,
            dual_camera=dual_camera,
            search_strategy=search_strategy,
            flight_strategy=flight_strategy,
            config=config,
            logger=logger
        )
        
        # 5. Execute mission
        print("---")
        print("GCS Frontend is available at 'gcs_frontend.html'")
        print("Starting mission... (Press Ctrl+C to abort)")
        print("---")
        
        await mission.run()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMission aborted by user.")
