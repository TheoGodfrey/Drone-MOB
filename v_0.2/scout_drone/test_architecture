"""Test that architecture supports future 2-drone coordination"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / 'v_0.2' / 'scout_drone'))

from core.drone import Drone
from core.position import Position
from core.camera import Camera
from core.behaviors import SearchBehavior, DeliveryBehavior
from core.state_machine import MissionState, MissionPhase
from strategies import get_search_strategy, get_flight_strategy

def test_can_create_multiple_drones():
    """Verify drones have unique IDs"""
    print("Testing: Multiple drone creation...")
    drone1 = Drone(is_simulated=True, drone_id="drone_1")
    drone2 = Drone(is_simulated=True, drone_id="drone_2")
    assert drone1.id != drone2.id
    assert drone1.id == "drone_1"
    assert drone2.id == "drone_2"
    print("✓ Multiple drones can be created with unique IDs")

def test_position_is_standalone():
    """Verify Position can be used independently"""
    print("Testing: Position independence...")
    pos1 = Position(100, 200, 15)
    pos2 = Position(150, 250, 15)
    distance = pos1.distance_to(pos2)
    assert distance > 0
    assert isinstance(str(pos1), str)
    print("✓ Position works independently")

def test_behaviors_are_reusable():
    """Verify behaviors work with any drone"""
    print("Testing: Behavior reusability...")
    
    drone1 = Drone(is_simulated=True, drone_id="drone_1")
    drone1.camera = Camera(is_simulated=True)
    drone2 = Drone(is_simulated=True, drone_id="drone_2")
    drone2.camera = Camera(is_simulated=True)
    
    search_strategy = get_search_strategy('random')
    flight_strategy = get_flight_strategy('direct')
    
    config = {
        'mission': {'max_search_iterations': 5},
        'strategies': {
            'search': {'area': {'x': 0, 'y': 0, 'z': 0}, 'size': 100}
        }
    }
    
    behavior1 = SearchBehavior(drone1, search_strategy, flight_strategy, config)
    behavior2 = SearchBehavior(drone2, search_strategy, flight_strategy, config)
    
    # Both should work independently
    assert behavior1.drone.id != behavior2.drone.id
    assert behavior1.drone.id == "drone_1"
    assert behavior2.drone.id == "drone_2"
    print("✓ Behaviors are reusable across drones")

def test_state_is_shareable():
    """Verify state can be shared between drones"""
    print("Testing: Shared state...")
    state = MissionState()
    
    # Simulate drone 1 finding target
    state.transition_to(MissionPhase.TARGET_FOUND)
    state.target_position = Position(100, 200, 0)
    
    # Simulate drone 2 reading state
    assert state.phase == MissionPhase.TARGET_FOUND
    assert state.target_position is not None
    print("✓ State can be shared between drones")

def test_health_tracking():
    """Verify health tracking works"""
    print("Testing: Health tracking...")
    drone = Drone(is_simulated=True, drone_id="test_drone")
    
    assert len(drone.health_history) == 0
    
    drone.record_health()
    assert len(drone.health_history) == 1
    
    for _ in range(15):
        drone.record_health()
    
    # Should keep only last 10
    assert len(drone.health_history) == 10
    print("✓ Health tracking works correctly")

def test_strategy_independence():
    """Verify strategies don't depend on specific drone"""
    print("Testing: Strategy independence...")
    
    drone1 = Drone(is_simulated=True, drone_id="drone_1")
    drone2 = Drone(is_simulated=True, drone_id="drone_2")
    
    strategy = get_search_strategy('random')
    
    # Same strategy can be used with different drones
    pos1 = strategy.get_next_position(drone1, Position(0, 0, 0), 100)
    pos2 = strategy.get_next_position(drone2, Position(0, 0, 0), 100)
    
    assert isinstance(pos1, Position)
    assert isinstance(pos2, Position)
    print("✓ Strategies are drone-independent")

def run_all_tests():
    """Run all architecture validation tests"""
    print("\n" + "="*50)
    print("Architecture Validation Tests")
    print("="*50 + "\n")
    
    tests = [
        test_can_create_multiple_drones,
        test_position_is_standalone,
        test_behaviors_are_reusable,
        test_state_is_shareable,
        test_health_tracking,
        test_strategy_independence
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} error: {e}")
            failed += 1
        print()
    
    print("="*50)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*50)
    
    if failed == 0:
        print("\n✅ All tests passed! Architecture is ready for 2-drone expansion.\n")
    else:
        print(f"\n❌ {failed} test(s) failed. Please fix before proceeding.\n")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)