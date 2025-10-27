# Scout Drone - Man Overboard Rescue System

Minimal single-drone prototype for autonomous man overboard (MOB) detection and rescue.

## Features

- Autonomous search patterns (Random)
- Flight strategies (Direct)
- Simulated camera detection
- Mission logging
- Extensible strategy system

## Installation
```bash
pip install -r requirements.txt
```

## Configuration

Edit `config/mission_config.yaml`:
```yaml
drones:
  type: simulated          # 'simulated' or 'real'
search_algorithm: random   # Search pattern
flight_algorithm: direct   # Flight path algorithm
search_area:
  x: 0.0                  # Center point (meters)
  y: 0.0
  z: 0.0
search_size: 1000.0       # Search area size (meters)
max_search_iterations: 50 # Max search points
```

## Usage
```bash
cd v_0.2/scout_drone
python main.py
```

Press ENTER to start mission, Ctrl+C to abort.

## Project Structure
```
scout_drone/
├── config/
│   └── mission_config.yaml
├── core/
│   ├── camera.py         # Camera and detection
│   ├── drone.py          # Drone control
│   ├── logger.py         # Mission logging
│   └── mission.py        # Mission controller
├── strategies/
│   ├── flight/
│   │   └── direct.py     # Direct flight strategy
│   └── search/
│       └── random.py     # Random search strategy
└── main.py               # Entry point
```

## Adding New Strategies

### Search Strategy

1. Create file in `strategies/search/`
2. Implement class with `get_next_position(drone, search_area, search_size)` method
3. Add factory function
4. Register in `strategies/__init__.py`

### Flight Strategy

1. Create file in `strategies/flight/`
2. Implement class with `get_next_position(drone, target_position)` method
3. Add factory function
4. Register in `strategies/__init__.py`

## Logs

Mission logs are written to `mission.log` in the current directory.