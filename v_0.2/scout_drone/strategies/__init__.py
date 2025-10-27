"""
Strategy registry and factory (composition-based)
"""

# Registry of available strategies (no inheritance required)
_FLIGHT_STRATEGIES = {}
_SEARCH_STRATEGIES = {}

def register_flight_strategy(name: str, strategy_factory):
    """Register a flight strategy factory function"""
    _FLIGHT_STRATEGIES[name] = strategy_factory

def register_search_strategy(name: str, strategy_factory):
    """Register a search strategy factory function"""
    _SEARCH_STRATEGIES[name] = strategy_factory

def get_flight_strategy(name: str):
    """Get flight strategy by name - returns whatever the factory creates"""
    if name not in _FLIGHT_STRATEGIES:
        raise ValueError(f"Unknown flight strategy: {name}")
    return _FLIGHT_STRATEGIES[name]()

def get_search_strategy(name: str):
    """Get search strategy by name - returns whatever the factory creates"""
    if name not in _SEARCH_STRATEGIES:
        raise ValueError(f"Unknown search strategy: {name}")
    return _SEARCH_STRATEGIES[name]()

def list_available_strategies():
    """List all available strategies"""
    return {
        "flight": list(_FLIGHT_STRATEGIES.keys()),
        "search": list(_SEARCH_STRATEGIES.keys())
    }

# Auto-register strategies using factory functions
from .flight.direct import create_direct_flight_strategy
from .search.random import create_random_search_strategy

register_flight_strategy('direct', create_direct_flight_strategy)
register_search_strategy('random', create_random_search_strategy)