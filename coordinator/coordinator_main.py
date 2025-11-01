"""
Main entry point for the Drone-MOB Coordinator.

This process runs at the "docking station" and manages the entire fleet.
It connects to the MQTT broker and starts the Coordinator, GCS Server,
and new Media Server.
"""
import asyncio
import yaml
import sys
import traceback
from pathlib import Path

# --- Robust Import Logic ---
FILE = Path(__file__).resolve()
ROOT = FILE.parent
CORE_PATH = ROOT / "v_0_2" / "scout_drone"
if str(CORE_PATH) not in sys.path:
    sys.path.append(str(CORE_PATH))
# --- End Import Logic ---

from core.config_models import Settings
from core.comms import MqttClient
from coordinator.coordinator import Coordinator
from coordinator.gcs_server import GcsServer
from coordinator.media_server import MediaServer # NEW

def load_config(config_path: str = "v_0_2/scout_drone/config/mission_config.yaml") -> Settings:
    # ... (no change from previous version)
    config_file = ROOT / config_path
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
    mqtt_client = None
    try:
        # 1. Load configuration
        config = load_config()

        # 2. Create MQTT Comms Client
        mqtt_client = MqttClient(config.mqtt, client_id="coordinator")
        await mqtt_client.connect()
        if not mqtt_client.is_connected:
            raise ConnectionError("Failed to connect to MQTT broker.")

        # 3. Create GCS Server
        gcs_server = GcsServer(config.gcs)

        # 4. Create Media Server (NEW)
        # The Media Server needs to send frames to the GCS clients
        media_server = MediaServer(gcs_server)

        # 5. Create the Coordinator
        coordinator = Coordinator(config, mqtt_client, gcs_server, media_server)
        
        # 6. Link GCS Server back to Coordinator
        gcs_server.set_controller(coordinator)

        # 7. Run all services concurrently
        print("[CoordinatorMain] Running all services...")
        await asyncio.gather(
            coordinator.run(),
            gcs_server.run(),
            media_server.run() # NEW: Run the media server
        )

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[CoordinatorMain] Shutting down...")
    except Exception as e:
        print(f"[CoordinatorMain] Fatal error: {e}")
        traceback.print_exc()
    finally:
        if mqtt_client and mqtt_client.is_connected:
            await mqtt_client.disconnect()
        print("[CoordinatorMain] Shutdown complete.")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())

