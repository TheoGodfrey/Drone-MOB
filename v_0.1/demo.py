#!/usr/bin/env python3
"""
Demo script - runs mission automatically without user input
For testing and demonstration purposes
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

import yaml
from core.mission import ScoutMission
from hardware.flight_controller import SimulatedFlightController
from hardware.thermal_camera import SimulatedThermalCamera
from hardware.led_controller import SimulatedLEDController
from detection.classifier import ThermalClassifier


def load_config():
    """Load configuration"""
    config_file = Path(__file__).parent / 'config' / 'mission_config.yaml'
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Run demo mission"""
    print("\n" + "="*60)
    print("SCOUT DRONE V1 - DEMO MODE")
    print("="*60 + "\n")
    
    # Load config
    config = load_config()
    
    # Create hardware (simulation mode)
    classifier = ThermalClassifier(config)
    flight = SimulatedFlightController()
    thermal = SimulatedThermalCamera(classifier)
    led = SimulatedLEDController()
    
    # Create and run mission
    mission = ScoutMission(flight, thermal, led, config)
    mission.execute()


if __name__ == "__main__":
    main()
