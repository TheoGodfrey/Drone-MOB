"""
Main entry point for the Drone-MOB Coordinator.

This process runs at the "docking station" and manages the entire fleet.
It connects to the MQTT broker and starts the Coordinator and GCS Server.
"""
import asyncio
import yaml
import sys
import traceback
from pathlib import Path

# Add the project's v_0.2/scout_drone directory to the Python path
# This allows us to import from 'core'
script_dir = Path(__file__).parent
project_root = script_dir
sys.path.append(str(project_root / "v_0.2" / "scout_drone"))

from core.config_models import Settings
from core.comms import MqttClient
from coordinator.coordinator import Coordinator
from coordinator.gcs_server import GcsServer

def load_config(config_path: str = "v_0.2/scout_drone/config/mission_config.yaml") -> Settings:
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

async def main():
    """Main asynchronous entry point for the Coordinator."""
    try:
        # 1. Load configuration
        config = load_config()

        # 2. Create MQTT Comms Client for the Coordinator
        mqtt_client = MqttClient(config.mqtt, client_id="coordinator")
        await mqtt_client.connect()

        # 3. Create GCS Server
        # The GCS Server now gets the Coordinator as its controller
        gcs_server = GcsServer(config.gcs)

        # 4. Create the Coordinator
        coordinator = Coordinator(config, mqtt_client, gcs_server)
        
        # 5. Link GCS Server back to Coordinator
        # This allows the GCS to call methods on the Coordinator
        gcs_server.set_controller(coordinator)

        # 6. Run all services concurrently
        print("[CoordinatorMain] Running all services...")
        await asyncio.gather(
            coordinator.run(),
            gcs_server.run()
        )

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[CoordinatorMain] Shutting down...")
    except Exception as e:
        print(f"[CoordinatorMain] Fatal error: {e}")
        traceback.print_exc()
    finally:
        if 'mqtt_client' in locals() and mqtt_client.is_connected:
            await mqtt_client.disconnect()
        print("[CoordinatorMain] Shutdown complete.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
