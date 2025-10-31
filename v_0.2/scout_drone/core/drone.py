"""
Drone interface and Hardware Abstraction Layer (HAL) for flight controllers.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from .position import Position

# NEW: A standardized dataclass for all drone telemetry.
@dataclass
class Telemetry:
    """Holds the complete state of the drone."""
    position: Position = Position(0, 0, 0)
    battery: float = 100.0
    is_connected: bool = False
    state: str = "IDLE"  # e.g., IDLE, FLYING, HOVERING, LANDING
    led_color: str = "off"
    last_heartbeat: float = 0.0


# NEW: Defines the "engine" or "driver" for a drone.
class BaseFlightController(ABC):
    """Abstract interface for a flight controller (real or simulated)."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the flight controller."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection."""
        pass
    
    @abstractmethod
    async def takeoff(self, altitude: float) -> bool:
        """Arm and take off to a specific relative altitude."""
        pass

    @abstractmethod
    async def go_to(self, position: Position) -> bool:
        """Navigate to a new 3D position in the world frame."""
        pass

    @abstractmethod
    async def hover(self) -> bool:
        """Stop and hover at the current position."""
        pass

    @abstractmethod
    async def land(self) -> bool:
        """Land at the current x,y position."""
        pass
    
    @abstractmethod
    async def set_led(self, color: str) -> None:
        """Set the color of an onboard indicator LED."""
        pass

    @abstractmethod
    async def get_telemetry(self) -> Telemetry:
        """Get the latest telemetry data from the drone."""
        pass


class Drone:
    """
    High-level Drone class.
    Manages state and delegates flight commands to a controller (HAL).
    """
    def __init__(self, controller: BaseFlightController, drone_id: str = "drone_0"):
        self.id = drone_id
        self.controller = controller  # CHANGED: Now uses dependency injection
        self.telemetry = Telemetry()
        self.health_history = []
        
        # CHANGED: The drone no longer owns the camera system.
        # It is a separate component.

    async def connect(self) -> bool:
        """Connect to the flight controller and update state."""
        success = await self.controller.connect()
        self.telemetry.is_connected = success
        return success

    async def disconnect(self) -> None:
        await self.controller.disconnect()
        self.telemetry.is_connected = False

    async def takeoff(self, altitude: float) -> bool:
        self.telemetry.state = "TAKING_OFF"
        success = await self.controller.takeoff(altitude)
        if success:
            self.telemetry.state = "HOVERING"
        return success

    async def go_to(self, position: Position) -> bool:
        self.telemetry.state = "FLYING"
        return await self.controller.go_to(position)

    async def hover(self) -> bool:
        self.telemetry.state = "HOVERING"
        return await self.controller.hover()

    async def land(self) -> bool:
        self.telemetry.state = "LANDING"
        return await self.controller.land()

    async def set_led(self, color: str):
        await self.controller.set_led(color)
        self.telemetry.led_color = color

    async def update_telemetry(self) -> None:
        """Poll the controller for the latest state."""
        self.telemetry = await self.controller.get_telemetry()
        self.telemetry.last_heartbeat = time.time()
        
        # CHANGED: Health is recorded based on telemetry, not internal state
        self.record_health()

    def is_healthy(self) -> bool:
        """Check if drone is healthy based on latest telemetry."""
        return (
            self.telemetry.is_connected and
            self.telemetry.battery > 20.0 and # TODO: Use config value
            (time.time() - self.telemetry.last_heartbeat) < 5.0
        )

    def record_health(self):
        """Record current health snapshot."""
        self.health_history.append(self.telemetry)
        if len(self.health_history) > 10:
            self.health_history.pop(0)


# --- Implementation Example ---

class SimulatedFlightController(BaseFlightController):
    """
    Simulation of the flight controller that implements the abstract interface.
    This contains the logic from the *original* Drone class.
    """
    def __init__(self):
        self._telemetry = Telemetry()
        print("[SimulatedController] Initialized.")

    async def connect(self) -> bool:
        print("[SimulatedController] Connecting...")
        await asyncio.sleep(0.5)  # Simulate connection delay
        self._telemetry.is_connected = True
        self._telemetry.last_heartbeat = time.time()
        print("[SimulatedController] Connected.")
        return True

    async def disconnect(self) -> None:
        print("[SimulatedController] Disconnecting...")
        await asyncio.sleep(0.1)
        self._telemetry.is_connected = False
        print("[SimulatedController] Disconnected.")

    async def takeoff(self, altitude: float) -> bool:
        print(f"[SimulatedController] Taking off to {altitude}m...")
        await asyncio.sleep(2.0)  # Simulate climbing
        self._telemetry.position.z = altitude
        self._telemetry.state = "HOVERING"
        print(f"[SimulatedController] At altitude {self._telemetry.position.z}m.")
        return True

    async def go_to(self, position: Position) -> bool:
        current_pos = self._telemetry.position
        dist = current_pos.distance_to(position)
        print(f"[SimulatedController] Flying from {current_pos} to {position} ({dist:.1f}m)...")
        
        # Simulate flight time (10 m/s)
        await asyncio.sleep(dist / 10.0) 
        
        self._telemetry.position = position
        self._telemetry.state = "HOVERING"
        print(f"[SimulatedController] Arrived at {position}.")
        return True

    async def hover(self) -> bool:
        print("[SimulatedController] Hovering.")
        self._telemetry.state = "HOVERING"
        await asyncio.sleep(0.1)
        return True

    async def land(self) -> bool:
        print("[SimulatedController] Landing...")
        await asyncio.sleep(2.0)  # Simulate landing
        self._telemetry.position.z = 0
        self._telemetry.state = "IDLE"
        print("[SimulatedController] Landed.")
        return True

    async def set_led(self, color: str):
        print(f"[SimulatedController] LED set to {color.upper()}")
        self._telemetry.led_color = color
        await asyncio.sleep(0.01)  # Simulate hardware call

    async def get_telemetry(self) -> Telemetry:
        # Simulate battery drain
        if self._telemetry.state != "IDLE":
            self._telemetry.battery -= 0.01
        
        # Simulate position drift (small noise)
        # self._telemetry.position.x += random.uniform(-0.01, 0.01)
        
        self._telemetry.last_heartbeat = time.time()
        # Return a copy so the drone class can't modify the internal state
        return self._telemetry