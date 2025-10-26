# Scout Drone V1 - Man Overboard Detection

Single drone prototype that climbs vertically, scans with thermal camera, classifies targets (person vs boat), and approaches person targets.

## Features

- ✈️ Vertical climb to maximize search aperture
- 🌡️ Thermal imaging for detection
- 🤖 Automatic classification (Person vs Boat)
- 🎯 Autonomous approach to person targets
- 🔴🟢 LED status indicator (Red=searching, Green=person found)
- 🏠 Automatic return to home

## Quick Start

### Simulation Mode (No Hardware)

```bash
# Install dependencies
pip install -r requirements.txt

# Run simulation
python src/main.py
```

### Hardware Mode

```bash
# Edit config/mission_config.yaml to set hardware=true
# Connect flight controller and thermal camera
python src/main.py
```

## Project Structure

```
scout-drone-v1/
├── config/
│   └── mission_config.yaml    # Mission parameters
├── src/
│   ├── main.py               # Entry point
│   ├── core/                 # Core mission logic
│   ├── hardware/             # Hardware interfaces
│   ├── detection/            # Classification logic
│   └── utils/                # Utilities
└── tests/                    # Unit tests
```

## Configuration

Edit `config/mission_config.yaml` to adjust:
- Search altitude
- Detection thresholds
- Speed settings
- Classification parameters

## Hardware Requirements

- Flight controller: PX4 or ArduPilot compatible
- Thermal camera: FLIR Lepton, Seek Thermal, or similar
- LED: Red/Green dual-color LED
- Companion computer: Raspberry Pi 4 or similar

## Mission Phases

1. **Climb** - Vertical ascent to search altitude
2. **Scan** - 360° thermal scan with classification
3. **Approach** - Fly to person target (ignore boats)
4. **Signal** - LED turns green at 1m above person
5. **Return** - Automatic return to home and land

## Safety

- Always test in simulation first
- Maintain visual line of sight
- Follow local drone regulations
- Have manual override ready
