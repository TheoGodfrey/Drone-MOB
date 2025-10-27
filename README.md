# Scout Drone - Man Overboard Rescue System

Minimal single-drone prototype for autonomous man overboard (MOB) detection and rescue.

**Architecture designed for future 2-drone coordination with role-switching and failover.**

## Features

- Autonomous search patterns (Random)
- Flight strategies (Direct)
- Simulated camera detection
- Mission logging
- Extensible strategy system
- **Health tracking** (for future failover)
- **Dependency injection** (for future coordination)
- **Reusable behaviors** (ready to become roles)

## Installation
```bash
pip install -r requirements.txt
```

## Configuration

Edit `config/mission_config.yaml`:
```yaml
mission:
  max_search_iterations: 50

drones:
  - id: drone_1
    type: simulated

strategies:
  search:
    algorithm: random
    area:
      x: 0.0
      y: 0.0
      z: 0.0
    size: 1000.0
  flight:
    algorithm: direct
```

## Usage
```bash
cd v_0.2/scout_drone
python main.py
```

Press ENTER to start mission, Ctrl+C to abort.

## Testing

Run architecture validation tests:
```bash
python test_architecture.py
```

## Project Structure
```
scout_drone/
├── config/
│   └── mission_config.yaml    # Mission configuration
├── core/
│   ├── position.py            # Position utilities (standalone)
│   ├── drone.py               # Drone interface (with ID & health)
│   ├── camera.py              # Camera & detection
│   ├── behaviors.py           # Reusable behaviors (future roles)
│   ├── state_machine.py       # Mission state management
│   ├── logger.py              # Logging
│   └── mission.py             # Mission controller
├── strategies/
│   ├── flight/
│   │   └── direct.py          # Direct flight strategy
│   └── search/
│       └── random.py          # Random search strategy
├── main.py                    # Entry point (dependency injection)
└── test_architecture.py       # Architecture validation tests
```

## Architecture Notes

This prototype is designed to **evolve cleanly to 2-drone coordination**:

- **Drones have IDs** - ready for multi-drone tracking
- **Behaviors are composable** - will become roles (SpotterRole, PayloadRole)
- **State is explicit** - ready to be shared via telemetry
- **Dependencies are injected** - easy to create multiple drones
- **Health is tracked** - foundation for failover logic

When adding 2-drone support, you'll add:
1. `core/telemetry.py` - shared state
2. `roles/` - wrap behaviors as roles
3. `coordination/coordinator.py` - manage multiple drones

**Current code won't need rewrites.**

## Adding New Strategies

### Search Strategy

1. Create file in `strategies/search/`
2. Implement class with `get_next_position(drone, search_area, search_size)` method
3. Add `name` and `description` attributes
4. Add factory function
5. Register in `strategies/__init__.py`

### Flight Strategy

1. Create file in `strategies/flight/`
2. Implement class with `get_next_position(drone, target_position)` method
3. Add `name` and `description` attributes
4. Add factory function
5. Register in `strategies/__init__.py`

## Logs

Mission logs are written to `mission.log` in the current directory.
```

---

## 📁 Final Directory Structure
```
scout_drone/
├── .gitignore
├── README.md
├── requirements.txt
├── test_architecture.py
└── v_0.2/
    └── scout_drone/
        ├── config/
        │   └── mission_config.yaml
        ├── core/
        │   ├── __init__.py
        │   ├── position.py          # NEW
        │   ├── drone.py              # UPDATED
        │   ├── camera.py
        │   ├── state_machine.py      # NEW
        │   ├── behaviors.py          # NEW
        │   ├── logger.py
        │   └── mission.py            # UPDATED
        ├── strategies/
        │   ├── __init__.py
        │   ├── base.py
        │   ├── flight/
        │   │   ├── __init__.py
        │   │   └── direct.py
        │   └── search/
        │       ├── __init__.py
        │       └── random.py
        └── main.py                   # UPDATED