"""
Minimal main entry point for single-drone MOB system
"""

import yaml
import sys
from pathlib import Path
from core.drone import Drone
from core.camera import Camera
from core.logger import MissionLogger
from core.mission import MissionController
from strategies import get_search_strategy, get_flight_strategy

def load_config(config_path: str = "config/mission_config.yaml") -> dict:
    """Load minimal configuration"""
    config_file = Path(__file__).parent / config_path
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def main():
    """Main entry point with dependency injection"""
    try:
        # Load configuration
        config = load_config()
        
        # Get drone configuration
        drone_config = config['drones'][0]  # Single drone for now
        drone_type = drone_config.get('type', 'simulated')
        drone_id = drone_config.get('id', 'drone_1')
        is_simulated = drone_type == 'simulated'
        
        # Create components (dependency injection)
        drone = Drone(is_simulated, drone_id=drone_id)
        drone.camera = Camera(is_simulated)
        
        search_strategy = get_search_strategy(config['strategies']['search']['algorithm'])
        flight_strategy = get_flight_strategy(config['strategies']['flight']['algorithm'])
        
        logger = MissionLogger()
        
        # Create mission controller with all dependencies injected
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
        sys.exit(1)

if __name__ == "__main__":
    main()