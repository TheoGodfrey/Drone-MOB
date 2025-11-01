"""
Main entry point for a *single* Drone-MOB client.

This process runs on the drone's companion computer.
It connects to the MQTT broker and awaits commands from the Coordinator.
"""

import yaml
import sys
import asyncio 
import traceback
import argparse
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
from core.safety import CollisionAvoider, StubObstacleSensor
from core.comms import MqttClient

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
            ambient_temp=thermal_cfg.ambient_temp,
            intrinsics=thermal_cfg.intrinsics
        )
    else:
        raise ValueError(f"Real thermal camera type '{thermal_cfg.type}' not implemented.")
    
    visual_cfg = config.cameras.visual
    if visual_cfg.type == 'simulated':
        visual_cam = SimulatedVisualCamera(
            resolution=visual_cfg.resolution,
            intrinsics=visual_cfg.intrinsics
        )
    else:
        raise ValueError(f"Real visual camera type '{visual_cfg.type}' not implemented.")
    
    recording_cfg = config.cameras.recording
    dual_camera = DualCameraSystem(
        thermal_cam, 
        visual_cam, 
        recording_cfg.enabled
    )
    return dual_camera

async def main(drone_id: str):
    """Main asynchronous entry point for the Drone Client."""
    mqtt_client = None
    try:
        # 1. Load configuration
        config = load_config()
        
        # 2. Find this drone's specific config
        drone_config = next((d for d in config.drones if d.id == drone_id), None)
        if not drone_config:
            print(f"FATAL: No configuration found for drone_id '{drone_id}' in config file.")
            sys.exit(1)

        print(f"--- Booting Drone Client ---")
        print(f"  ID: {drone_config.id}")
        print(f"  Role: {drone_config.role}")
        print(f"  Type: {drone_config.type}")
        print(f"--------------------------")

        # 3. Create components
        # 3a. Create MQTT Client for this drone
        mqtt_client = MqttClient(config.mqtt, client_id=drone_id)
        await mqtt_client.connect()
        if not mqtt_client.is_connected:
            raise ConnectionError("Failed to connect to MQTT broker.")
        
        # 3b. Create the base flight controller
        if drone_config.type == 'simulated':
            base_controller = SimulatedFlightController()
        elif drone_config.type == 'real':
            base_controller = MavlinkController(connection_string="udp:127.0.0.1:14550")
        else:
            raise ValueError(f"Unknown drone type: '{drone_config.type}'")
            
        # 3c. Create the safety sensor and decorator
        obstacle_sensor = StubObstacleSensor()
        safe_controller = CollisionAvoider(base_controller, obstacle_sensor, mqtt_client)
        
        # 3d. Create the Drone instance
        drone = Drone(safe_controller, drone_id=drone_config.id)
        
        # 3e. Create other components
        dual_camera = None
        if drone_config.role in ["scout", "utility"]:
            dual_camera = create_cameras(config)
        
        # NEW: Instantiate all strategies
        search_strategies = {
            "vertical_ascent": get_search_strategy("vertical_ascent", config.vertical_ascent),
            "random": get_search_strategy("random", None), # No config
            "lawnmower": get_search_strategy("lawnmower", config.lawnmower)
        }
        flight_strategies = {
            "direct": get_flight_strategy("direct", None), # No config
            "precision_hover": get_flight_strategy("precision_hover", config.precision_hover),
            "orbit": get_flight_strategy("orbit", config.orbit)
        }
        
        logger = MissionLogger(log_dir=config.logging.log_dir, drone_id=drone_id)
        
        # 4. Create mission controller
        mission = MissionController(
            drone=drone,
            dual_camera=dual_camera,
            search_strategies=search_strategies, # Pass dict
            flight_strategies=flight_strategies, # Pass dict
            config=config,
            logger=logger,
            mqtt_client=mqtt_client
        )
        
        # 5. Execute mission (which now listens for commands)
        await mission.run()
        
    except (KeyboardInterrupt, asyncio.CancelledError):
        print(f"\n[DroneClient {drone_id}] Shutting down...")
    except Exception as e:
        print(f"[DroneClient {drone_id}] Fatal error: {e}")
        traceback.print_exc()
    finally:
        if mqtt_client and mqtt_client.is_connected:
            await mqtt_client.publish(f"fleet/state/{drone_id}", {"state": "OFFLINE"})
            await mqtt_client.disconnect()
        print(f"[DroneClient {drone_id}] Shutdown complete.")
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drone-MOB Client")
    parser.add_argument(
        "--id", 
        type=str, 
        required=True, 
        help="The unique ID of this drone (e.g., 'scout_1')"
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(drone_id=args.id))
    except KeyboardInterrupt:
        pass


