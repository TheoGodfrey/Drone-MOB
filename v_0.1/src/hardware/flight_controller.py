"""
Flight controller interface
Supports both real hardware (DroneKit) and simulation
"""

import time
import math
from abc import ABC, abstractmethod

try:
    from utils.geometry import Position
except ImportError:
    import sys
    from pathlib import Path
    src_path = Path(__file__).parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from utils.geometry import Position


class FlightController(ABC):
    """Abstract base class for flight controller"""
    
    @abstractmethod
    def connect(self):
        """Connect to flight controller"""
        pass
    
    @abstractmethod
    def takeoff(self, altitude: float):
        """Takeoff to specified altitude"""
        pass
    
    @abstractmethod
    def goto_position(self, position: Position, speed: float):
        """Navigate to position at specified speed"""
        pass
    
    @abstractmethod
    def get_position(self) -> Position:
        """Get current position"""
        pass
    
    @abstractmethod
    def get_altitude(self) -> float:
        """Get current altitude"""
        pass
    
    @abstractmethod
    def hover(self):
        """Maintain current position"""
        pass
    
    @abstractmethod
    def land(self):
        """Land at current position"""
        pass
    
    @abstractmethod
    def is_armable(self) -> bool:
        """Check if drone is ready to arm"""
        pass


class SimulatedFlightController(FlightController):
    """Simulated flight controller for testing without hardware"""
    
    def __init__(self):
        self.current_position = Position(0, 0, 0)
        self.target_position = None
        self.target_altitude = 0
        self.is_connected = False
        self.is_armed = False
        
    def connect(self):
        """Simulate connection"""
        print("[Flight] Connecting to simulated flight controller...")
        time.sleep(0.5)
        self.is_connected = True
        print("[Flight] ✓ Connected (SIMULATION MODE)")
    
    def takeoff(self, altitude: float):
        """Simulate takeoff"""
        print(f"[Flight] Taking off to {altitude}m (simulated)")
        self.target_altitude = altitude
        self.is_armed = True
    
    def goto_position(self, position: Position, speed: float):
        """Simulate navigation"""
        print(f"[Flight] Going to {position} at {speed}m/s (simulated)")
        self.target_position = position
    
    def get_position(self) -> Position:
        """Simulate position with gradual movement"""
        if self.target_position:
            # Gradually move toward target
            current = self.current_position
            target = self.target_position
            
            dx = target.x - current.x
            dy = target.y - current.y
            dz = target.altitude - current.altitude
            dist = math.sqrt(dx**2 + dy**2 + dz**2)
            
            if dist > 1.0:
                # Move 1m per step
                self.current_position.x += dx / dist
                self.current_position.y += dy / dist
                self.current_position.altitude += dz / dist
            else:
                self.current_position = Position(
                    target.x, target.y, target.altitude
                )
        
        return self.current_position
    
    def get_altitude(self) -> float:
        """Simulate altitude with gradual climb"""
        if self.current_position.altitude < self.target_altitude:
            self.current_position.altitude += 2.0  # 2m per check
        return self.current_position.altitude
    
    def hover(self):
        """Simulate hover"""
        print("[Flight] Hovering (simulated)")
    
    def land(self):
        """Simulate landing"""
        print("[Flight] Landing (simulated)")
        self.target_altitude = 0
        while self.current_position.altitude > 0:
            self.current_position.altitude = max(
                0, self.current_position.altitude - 1.0
            )
            time.sleep(0.2)
        self.is_armed = False
        print("[Flight] ✓ Landed")
    
    def is_armable(self) -> bool:
        """Always armable in simulation"""
        return True


class DroneKitFlightController(FlightController):
    """Real flight controller using DroneKit"""
    
    def __init__(self, connection_string: str, baud: int = 57600):
        """
        Args:
            connection_string: Serial port or network address
            baud: Baud rate for serial connection
        """
        self.connection_string = connection_string
        self.baud = baud
        self.vehicle = None
    
    def connect(self):
        """Connect to real flight controller"""
        try:
            from dronekit import connect
            print(f"[Flight] Connecting to {self.connection_string}...")
            self.vehicle = connect(
                self.connection_string,
                wait_ready=True,
                baud=self.baud
            )
            print("[Flight] ✓ Connected to flight controller")
        except ImportError:
            raise RuntimeError(
                "DroneKit not installed. Install with: pip install dronekit"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to connect to flight controller: {e}")
    
    def takeoff(self, altitude: float):
        """Real takeoff"""
        from dronekit import VehicleMode
        
        print(f"[Flight] Arming and taking off to {altitude}m...")
        
        # Arm and takeoff
        self.vehicle.mode = VehicleMode("GUIDED")
        self.vehicle.armed = True
        
        # Wait for arming
        while not self.vehicle.armed:
            time.sleep(1)
        
        print("[Flight] Armed, taking off...")
        self.vehicle.simple_takeoff(altitude)
    
    def goto_position(self, position: Position, speed: float):
        """Navigate to position"""
        from dronekit import LocationGlobalRelative
        
        self.vehicle.airspeed = speed
        target = LocationGlobalRelative(
            position.x,
            position.y,
            position.altitude
        )
        self.vehicle.simple_goto(target)
    
    def get_position(self) -> Position:
        """Get current position"""
        loc = self.vehicle.location.global_relative_frame
        return Position(loc.lat, loc.lon, loc.alt)
    
    def get_altitude(self) -> float:
        """Get current altitude"""
        return self.vehicle.location.global_relative_frame.alt
    
    def hover(self):
        """Maintain position"""
        from dronekit import VehicleMode
        self.vehicle.mode = VehicleMode("GUIDED")
    
    def land(self):
        """Land"""
        from dronekit import VehicleMode
        print("[Flight] Landing...")
        self.vehicle.mode = VehicleMode("LAND")
    
    def is_armable(self) -> bool:
        """Check if ready to arm"""
        return self.vehicle.is_armable if self.vehicle else False
