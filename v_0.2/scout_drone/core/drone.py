"""
Drone interface and Hardware Abstraction Layer (HAL) for flight controllers.
Includes Base, Simulated, and MAVLink implementations.
"""

import asyncio
import time
import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from .position import Position

# --- Telemetry Dataclass (Updated) ---
@dataclass
class Telemetry:
    """Holds the complete state of the drone."""
    position: Position = Position(0, 0, 0)
    attitude_roll: float = 0.0   # NEW: Roll in degrees
    attitude_pitch: float = 0.0  # NEW: Pitch in degrees
    attitude_yaw: float = 0.0    # NEW: Yaw in degrees
    battery: float = 100.0
    is_connected: bool = False
    state: str = "IDLE"
    led_color: str = "off"
    last_heartbeat: float = 0.0


# --- BaseFlightController Interface (Unchanged) ---
class BaseFlightController(ABC):
    
    @abstractmethod
    async def connect(self) -> bool: pass
    @abstractmethod
    async def disconnect(self) -> None: pass
    @abstractmethod
    async def takeoff(self, altitude: float) -> bool: pass
    @abstractmethod
    async def go_to(self, position: Position) -> bool: pass
    @abstractmethod
    async def hover(self) -> bool: pass
    @abstractmethod
    async def land(self) -> bool: pass
    @abstractmethod
    async def set_led(self, color: str) -> None: pass
    @abstractmethod
    async def get_telemetry(self) -> Telemetry: pass


# --- Drone Class (Unchanged) ---
class Drone:
    """High-level Drone class. Manages state and delegates flight commands."""
    def __init__(self, controller: BaseFlightController, drone_id: str = "drone_0"):
        self.id = drone_id
        self.controller = controller
        self.telemetry = Telemetry()
        self.health_history = []

    async def connect(self) -> bool:
        success = await self.controller.connect()
        self.telemetry.is_connected = success
        return success

    async def disconnect(self) -> None:
        await self.controller.disconnect()
        self.telemetry.is_connected = False

    async def takeoff(self, altitude: float) -> bool:
        self.telemetry.state = "TAKING_OFF"
        success = await self.controller.takeoff(altitude)
        if success: self.telemetry.state = "HOVERING"
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
        self.telemetry = await self.controller.get_telemetry()
        self.telemetry.last_heartbeat = time.time()
        self.record_health()

    def is_healthy(self) -> bool:
        return (
            self.telemetry.is_connected and
            self.telemetry.battery > 20.0 and
            (time.time() - self.telemetry.last_heartbeat) < 5.0
        )

    def record_health(self):
        self.health_history.append(self.telemetry)
        if len(self.health_history) > 10: self.health_history.pop(0)


# --- SimulatedFlightController (Updated) ---
class SimulatedFlightController(BaseFlightController):
    """Simulation of the flight controller."""
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
        
        # Simulate yaw (drone turns to face target)
        self._telemetry.attitude_yaw = math.degrees(math.atan2(position.y - current_pos.y, position.x - current_pos.x))
        # Simulate slight roll/pitch during movement
        self._telemetry.attitude_pitch = random.uniform(-5.0, 5.0)

        await asyncio.sleep(dist / 10.0) 
        self._telemetry.position = position
        self._telemetry.state = "HOVERING"
        self._telemetry.attitude_pitch = 0.0 # Level out
        print(f"[SimulatedController] Arrived at {position}.")
        return True

    async def hover(self) -> bool:
        print("[SimulatedController] Hovering.")
        self._telemetry.state = "HOVERING"
        self._telemetry.attitude_pitch = random.uniform(-0.5, 0.5) # Slight hover movement
        self._telemetry.attitude_roll = random.uniform(-0.5, 0.5)
        await asyncio.sleep(0.1)
        return True

    async def land(self) -> bool:
        print("[SimulatedController] Landing...")
        await asyncio.sleep(2.0)
        self._telemetry.position.z = 0
        self._telemetry.state = "IDLE"
        self._telemetry.attitude_pitch = 0.0
        self._telemetry.attitude_roll = 0.0
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
        # Add slight hover drift to attitude
        if self._telemetry.state == "HOVERING":
             self._telemetry.attitude_pitch = random.uniform(-0.5, 0.5)
             self._telemetry.attitude_roll = random.uniform(-0.5, 0.5)
        return self._telemetry


# --- MavlinkFlightController (Updated) ---
class MavlinkController(BaseFlightController):
    """Hardware implementation of the flight controller using MAVLink."""
    def __init__(self, connection_string: str = "udp:127.0.0.1:14550"):
        # e.g., from dronekit import connect, VehicleMode, LocationGlobalRelative
        # self.vehicle = None
        self.connection_string = connection_string
        self._telemetry = Telemetry()
        print(f"[MavlinkController] Initialized. Will connect to {connection_string}")

    async def connect(self) -> bool:
        print(f"[MavlinkController] Connecting to {self.connection_string}...")
        # e.g., self.vehicle = connect(self.connection_string, wait_ready=True, timeout=10)
        await asyncio.sleep(2.0) # Simulate connection timeout
        # if not self.vehicle: ...
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
        await asyncio.sleep(1.0) 
        print(f"[MavlinkController] Sending takeoff command to {altitude}m...")
        # e.g., self.vehicle.simple_takeoff(altitude)
        await asyncio.sleep(3.0) # Simulate climb
        self._telemetry.position.z = altitude
        self._telemetry.state = "HOVERING"
        print(f"[MavlinkController] Takeoff complete.")
        return True

    async def go_to(self, position: Position) -> bool:
        print(f"[MavlinkController] Setting mode to GUIDED...")
        print(f"[MavlinkController] Flying to {position}...")
        # e.g., loc = LocationGlobalRelative(position.x, position.y, position.z)
        # e.g., self.vehicle.simple_goto(loc)
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
        await asyncio.sleep(3.0) # Simulate landing
        self._telemetry.position.z = 0
        self._telemetry.state = "IDLE"
        print("[MavlinkController] Landed and disarmed.")
        return True

    async def set_led(self, color: str):
        print(f"[MavlinkController] (SIMULATED) Set LED to {color.upper()}")
        self._telemetry.led_color = color
        await asyncio.sleep(0.01)

    async def get_telemetry(self) -> Telemetry:
        # --- Real MAVLink Implementation ---
        # if self.vehicle:
        #    loc = self.vehicle.location.global_relative_frame
        #    att = self.vehicle.attitude
        #    batt = self.vehicle.battery
        #    self._telemetry.position = Position(loc.lat, loc.lon, loc.alt) # NOTE: Lat/Lon, not X/Y
        #    self._telemetry.attitude_roll = math.degrees(att.roll)
        #    self._telemetry.attitude_pitch = math.degrees(att.pitch)
        #    self._telemetry.attitude_yaw = math.degrees(att.yaw)
        #    self._telemetry.battery = batt.level
        #    self._telemetry.is_connected = True
        #    self._telemetry.state = self.vehicle.mode.name
        # else:
        #    self._telemetry.is_connected = False

        # --- Simulated MAVLink Implementation ---
        if self._telemetry.state != "IDLE":
            self._telemetry.battery -= 0.02
        self._telemetry.last_heartbeat = time.time()
        
        return self._telemetry
