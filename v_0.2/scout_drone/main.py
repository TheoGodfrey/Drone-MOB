"""
Minimal main entry point for single-drone MOB system
"""

import yaml
import sys
from pathlib import Path
from core.mission import MissionController

def load_config(config_path: str = "config/mission_config.yaml") -> dict:
    """Load minimal configuration"""
    config_file = Path(__file__).parent / config_path
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def main():
    """Minimal main entry point"""
    try:
        # Load configuration
        config = load_config()
        
        # Create mission controller
        mission = MissionController(config)
        
        # Execute mission
        input("Press ENTER to start mission (Ctrl+C to abort)...")
        mission.execute()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()