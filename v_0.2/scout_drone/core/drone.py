"""
Drone interface and Hardware Abstraction Layer (HAL) for flight controllers.
Includes Base, Simulated, and MAVLink implementations.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from .position import Position

# --- Telemetry Dataclass (No Change) ---

@dataclass
class Telemetry:
    """Holds the complete state of the drone."""
    position: Position = Position(0, 0, 0)
    battery: float = 100.0
    is_connected: bool = False
    state: str = "IDLE"  # e.g., IDLE, FLYING, HOVERING, LANDING
    led_color: str = "off"
    last_heartbeat: float = 0.0

# --- BaseFlightController Interface (No Change) ---

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

# --- Drone Class (No Change) ---

class Drone:
    """
    High-level Drone class.
    Manages state and delegates flight commands to a controller (HAL).
    """
    def __init__(self, controller: BaseFlightController, drone_id: str = "drone_0"):
        self.id = drone_id
        self.controller = controller
        self.telemetry = Telemetry()
        self.health_history = []

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


# --- SimulatedFlightController Implementation (No Change) ---

class SimulatedFlightController(BaseFlightController):
    """
    Simulation of the flight controller that implements the abstract interface.
    """
    def __init__(self):
        self._telemetry = Telemetry()
        print("[SimulatedController] Initialized.")

    async def connect(self) -> bool:
        print("[SimulatedController] Connecting...")
        await asyncio.sleep(0.5)
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
        await asyncio.sleep(2.0)
        self._telemetry.position.z = altitude
        self._telemetry.state = "HOVERING"
        print(f"[SimulatedController] At altitude {self._telemetry.position.z}m.")
        return True

    async def go_to(self, position: Position) -> bool:
        current_pos = self._telemetry.position
        dist = current_pos.distance_to(position)
        print(f"[SimulatedController] Flying from {current_pos} to {position} ({dist:.1f}m)...")
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
        await asyncio.sleep(2.0)
        self._telemetry.position.z = 0
        self._telemetry.state = "IDLE"
        print("[SimulatedController] Landed.")
        return True

    async def set_led(self, color: str):
        print(f"[SimulatedController] LED set to {color.upper()}")
        self._telemetry.led_color = color
        await asyncio.sleep(0.01)

    async def get_telemetry(self) -> Telemetry:
        if self._telemetry.state != "IDLE":
            self._telemetry.battery -= 0.01
        self._telemetry.last_heartbeat = time.time()
        return self.telemetry


# --- NEW: MavlinkFlightController Implementation ---

class MavlinkController(BaseFlightController):
    """
    Hardware implementation of the flight controller using MAVLink.
    This class would wrap a library like DroneKit or PyMAVLink.
    
    NOTE: This is a *simulated* implementation of the real-world logic.
    """
    def __init__(self, connection_string: str = "udp:127.0.0.1:14550"):
        # In a real implementation, you would initialize the connection here.
        # e.g., from dronekit import connect
        # self.vehicle = None
        self.connection_string = connection_string
        self._telemetry = Telemetry()
        print(f"[MavlinkController] Initialized. Will connect to {connection_string}")

    async def connect(self) -> bool:
        print(f"[MavlinkController] Connecting to {self.connection_string}...")
        # e.g., self.vehicle = connect(self.connection_string, wait_ready=True)
        await asyncio.sleep(2.0) # Simulate connection timeout
        
        # Check if connection was successful
        # if not self.vehicle:
        #    print("[MavlinkController] ERROR: Connection failed.")
        #    return False
            
        self._telemetry.is_connected = True
        self._telemetry.last_heartbeat = time.time()
        print("[MavlinkController] Vehicle connected.")
        return True

    async def disconnect(self) -> None:
        print("[MavlinkController] Disconnecting...")
        # e.g., self.vehicle.close()
        await asyncio.sleep(0.1)
        self._telemetry.is_connected = False
        print("[MavlinkController] Disconnected.")

    async def takeoff(self, altitude: float) -> bool:
        print("[MavlinkController] Arming vehicle...")
        # e.g., self.vehicle.mode = VehicleMode("GUIDED")
        # e.g., self.vehicle.armed = True
        await asyncio.sleep(1.0) # Simulate mode change and arming
        
        # while not self.vehicle.armed:
        #    print("...waiting to arm")
        #    await asyncio.sleep(0.5)
            
        print(f"[MavlinkController] Sending takeoff command to {altitude}m...")
        # e.g., self.vehicle.simple_takeoff(altitude)
        
        # In a real implementation, you would loop until target altitude is reached
        await asyncio.sleep(3.0) # Simulate climb
        
        self._telemetry.position.z = altitude
        self._telemetry.state = "HOVERING"
        print(f"[MavlinkController] Takeoff complete.")
        return True

    async def go_to(self, position: Position) -> bool:
        print(f"[MavlinkController] Setting mode to GUIDED...")
        # e.g., self.vehicle.mode = VehicleMode("GUIDED")
        
        print(f"[MavlinkController] Flying to {position}...")
        # e.g., loc = LocationGlobalRelative(position.x, position.y, position.z)
        # e.g., self.vehicle.simple_goto(loc)
        
        # In a real implementation, you would loop until target is reached
        await asyncio.sleep(2.0) # Simulate flight
        
        self._telemetry.position = position
        self._telemetry.state = "HOVERING"
        print(f"[MavlinkController] Arrived at {position}.")
        return True

    async def hover(self) -> bool:
        print("[MavlinkController] Setting mode to LOITER/HOVER...")
        # e.g., self.vehicle.mode = VehicleMode("LOITER")
        self._telemetry.state = "HOVERING"
        await asyncio.sleep(0.2)
        return True

    async def land(self) -> bool:
        print("[MavlinkController] Setting mode to LAND...")
        # e.g., self.vehicle.mode = VehicleMode("LAND")
        
        # In a real implementation, you would loop until disarmed
        await asyncio.sleep(3.0) # Simulate landing
        
        self._telemetry.position.z = 0
        self._telemetry.state = "IDLE"
        print("[MavlinkController] Landed and disarmed.")
        return True

    async def set_led(self, color: str):
        # MAVLink doesn't have a universal LED command,
        # this would be a custom MAVLink message or GPIO control.
        print(f"[MavlinkController] (SIMULATED) Set LED to {color.upper()}")
        self._telemetry.led_color = color
        await asyncio.sleep(0.01)

    async def get_telemetry(self) -> Telemetry:
        # In a real implementation, you would read from the vehicle object
        # e.g., pos = self.vehicle.location.global_relative_frame
        # e.g., batt = self.vehicle.battery
        
        # Simulating live updates
        if self._telemetry.state != "IDLE":
            self._telemetry.battery -= 0.02 # Real drones use more power
        
        self._telemetry.last_heartbeat = time.time()
        
        # print("[MavlinkController] Telemetry polled.")
        return self._telemetry