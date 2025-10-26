"""
Scout Drone V1 - Main Entry Point
Man overboard detection prototype
"""

import yaml
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from core.mission import ScoutMission
from hardware.flight_controller import SimulatedFlightController, DroneKitFlightController
from hardware.thermal_camera import SimulatedThermalCamera, FLIRLeptonCamera, SeekThermalCamera
from hardware.led_controller import SimulatedLEDController, GPIOLEDController
from detection.classifier import ThermalClassifier


def load_config(config_path: str = "../config/mission_config.yaml") -> dict:
    """Load mission configuration from YAML"""
    config_file = Path(__file__).parent / config_path
    
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def create_hardware(config: dict):
    """
    Create hardware interfaces based on configuration
    
    Returns:
        (flight_controller, thermal_camera, led_controller)
    """
    simulation = config['hardware']['simulation']
    
    # Create classifier
    classifier = ThermalClassifier(config)
    
    # Flight controller
    if simulation:
        print("[Setup] Using SIMULATED flight controller")
        flight = SimulatedFlightController()
    else:
        print("[Setup] Using REAL flight controller")
        connection_string = config['hardware']['flight_controller_port']
        baud = config['hardware']['flight_controller_baud']
        flight = DroneKitFlightController(connection_string, baud)
    
    # Thermal camera
    if simulation:
        print("[Setup] Using SIMULATED thermal camera")
        thermal = SimulatedThermalCamera(classifier)
    else:
        # TODO: Auto-detect or configure camera type
        print("[Setup] Using REAL thermal camera (FLIR Lepton)")
        thermal = FLIRLeptonCamera(classifier)
    
    # LED controller
    if simulation:
        print("[Setup] Using SIMULATED LED")
        led = SimulatedLEDController()
    else:
        print("[Setup] Using REAL LED (GPIO)")
        red_pin = config['led']['red_pin']
        green_pin = config['led']['green_pin']
        led = GPIOLEDController(red_pin, green_pin)
    
    return flight, thermal, led


def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("SCOUT DRONE V1 PROTOTYPE")
    print("Man Overboard Detection System")
    print("="*60 + "\n")
    
    try:
        # Load configuration
        print("[Setup] Loading configuration...")
        config = load_config()
        
        # Create hardware interfaces
        print("[Setup] Initializing hardware...")
        flight, thermal, led = create_hardware(config)
        
        # Create mission
        print("[Setup] Creating mission...")
        mission = ScoutMission(flight, thermal, led, config)
        
        # Execute mission
        print("[Setup] ✓ Ready to start mission\n")
        input("Press ENTER to start mission (Ctrl+C to abort)...")
        print()
        
        mission.execute()
        
    except FileNotFoundError as e:
        print(f"\n❌ Configuration file not found: {e}")
        print("Make sure config/mission_config.yaml exists")
        sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Mission aborted by user")
        sys.exit(0)
    
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
