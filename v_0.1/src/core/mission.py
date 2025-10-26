"""
Mission orchestration for scout drone
Manages the complete mission lifecycle
"""

import time
from typing import Optional, List

try:
    from core.state_machine import DroneState, TargetType
    from hardware.flight_controller import FlightController
    from hardware.thermal_camera import ThermalCamera
    from hardware.led_controller import LEDController
    from detection.thermal_processing import Detection
    from utils.geometry import Position
except ImportError:
    import sys
    from pathlib import Path
    src_path = Path(__file__).parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from core.state_machine import DroneState, TargetType
    from hardware.flight_controller import FlightController
    from hardware.thermal_camera import ThermalCamera
    from hardware.led_controller import LEDController
    from detection.thermal_processing import Detection
    from utils.geometry import Position


class ScoutMission:
    """Main mission controller for scout drone"""
    
    def __init__(
        self,
        flight: FlightController,
        thermal: ThermalCamera,
        led: LEDController,
        config: dict
    ):
        """
        Args:
            flight: Flight controller interface
            thermal: Thermal camera interface
            led: LED controller interface
            config: Mission configuration
        """
        self.flight = flight
        self.thermal = thermal
        self.led = led
        self.config = config
        
        # Mission state
        self.state = DroneState.IDLE
        self.target: Optional[Detection] = None
        self.home_position = Position(0, 0, 0)
        self.all_detections: List[Detection] = []
        
        # Mission parameters
        self.search_altitude = config['mission']['search_altitude']
        self.approach_altitude = config['mission']['approach_altitude']
        self.return_speed = config['mission']['return_speed']
        self.approach_speed = config['mission']['approach_speed']
        self.scan_rate = config['mission']['scan_rate']
        self.hover_duration = config['mission']['hover_duration']
        self.thermal_threshold = config['detection']['thermal_threshold']
    
    def execute(self):
        """Execute complete mission"""
        print("=" * 60)
        print("SCOUT DRONE V1 - MAN OVERBOARD DETECTION")
        print("=" * 60)
        
        try:
            self._preflight_check()
            self._phase_climb()
            self._phase_scan()
            self._phase_approach()
            self._phase_return()
            self._phase_complete()
            
        except KeyboardInterrupt:
            print("\n[Mission] ⚠️ Interrupted by user")
            self._emergency_land()
        except Exception as e:
            print(f"\n[Mission] ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            self._emergency_land()
    
    def _preflight_check(self):
        """Pre-flight system checks"""
        print("\n=== PREFLIGHT CHECKS ===")
        self.state = DroneState.PREFLIGHT
        
        # Connect to hardware
        print("[Preflight] Connecting to systems...")
        self.flight.connect()
        self.thermal.connect()
        
        # Test LED
        print("[Preflight] Testing LED...")
        self.led.set_red()
        time.sleep(0.3)
        self.led.set_green()
        time.sleep(0.3)
        self.led.set_off()
        
        # Check flight controller status
        if not self.flight.is_armable():
            raise RuntimeError("Flight controller not armable!")
        
        # Record home position
        self.home_position = self.flight.get_position()
        print(f"[Preflight] Home position: {self.home_position}")
        
        print("[Preflight] ✓ All systems ready\n")
    
    def _phase_climb(self):
        """Phase 1: Vertical climb to search altitude"""
        print(f"=== PHASE 1: CLIMB TO {self.search_altitude}m ===")
        self.state = DroneState.CLIMBING
        self.led.set_red()
        
        # Takeoff
        self.flight.takeoff(self.search_altitude)
        
        # Monitor climb
        print("[Climb] Ascending...")
        while self.flight.get_altitude() < self.search_altitude * 0.95:
            current_alt = self.flight.get_altitude()
            progress = (current_alt / self.search_altitude) * 100
            print(f"[Climb] Altitude: {current_alt:.1f}m ({progress:.0f}%)")
            
            # Update thermal camera with current altitude
            self.thermal.set_altitude(current_alt)
            
            time.sleep(1.0)
        
        print(f"[Climb] ✓ Reached {self.search_altitude}m")
        self.thermal.set_altitude(self.search_altitude)
        self.flight.hover()
        print()
    
    def _phase_scan(self):
        """Phase 2: Thermal scan and classification"""
        print("=== PHASE 2: THERMAL SCAN ===")
        self.state = DroneState.SCANNING
        self.led.set_red()
        
        print("[Scan] Searching for PERSON (ignoring boats)...")
        print(f"[Scan] Scan rate: {self.scan_rate} Hz")
        print(f"[Scan] Detection threshold: {self.thermal_threshold:.0%}\n")
        
        scan_interval = 1.0 / self.scan_rate
        scan_count = 0
        
        while self.target is None:
            scan_count += 1
            
            # Capture and analyze thermal frame
            frame = self.thermal.capture_frame()
            detections = self.thermal.detect_and_classify(frame)
            
            if detections:
                for detection in detections:
                    self.all_detections.append(detection)
                    
                    if detection.is_boat():
                        print(f"[Scan] ⚠️  Boat detected - IGNORING")
                        print(f"       {detection}\n")
                    
                    elif (detection.is_person() and 
                          detection.confidence >= self.thermal_threshold):
                        # FOUND A PERSON!
                        self.target = detection
                        self.state = DroneState.TARGET_ACQUIRED
                        print(f"\n[Scan] 🎯 PERSON TARGET ACQUIRED!")
                        print(f"[Scan]   {detection}")
                        break
            else:
                if scan_count % 5 == 0:
                    print(f"[Scan] Scanning... ({scan_count} frames)")
            
            if self.target:
                break
            
            time.sleep(scan_interval)
        
        print()
    
    def _phase_approach(self):
        """Phase 3: Approach person target"""
        print("=== PHASE 3: APPROACH TARGET ===")
        self.state = DroneState.APPROACHING
        
        if not self.target or not self.target.is_person():
            print("[Approach] ❌ No person target!")
            return
        
        # Calculate target position (relative to current position)
        current_pos = self.flight.get_position()
        target_position = Position(
            current_pos.x + self.target.position.x,
            current_pos.y + self.target.position.y,
            self.approach_altitude
        )
        
        print(f"[Approach] Target: {target_position}")
        print(f"[Approach] Flying at {self.approach_speed}m/s...")
        
        self.flight.goto_position(target_position, self.approach_speed)
        
        # Monitor approach
        while True:
            current_pos = self.flight.get_position()
            distance = current_pos.distance_to(target_position)
            
            if distance > 5.0:
                if int(distance) % 10 == 0:
                    print(f"[Approach] Distance: {distance:.0f}m")
            else:
                print(f"[Approach] Distance: {distance:.1f}m")
            
            # Within 1.5m = on target
            if distance < 1.5:
                self.state = DroneState.ON_TARGET
                print(f"\n[Approach] ✓ ON TARGET ({distance:.2f}m above person)")
                
                # LED turns green!
                self.led.set_green()
                break
            
            time.sleep(0.5)
        
        # Hover over person
        self.flight.hover()
        print(f"[Approach] Hovering for {self.hover_duration}s...")
        print("[Approach] Ready for payload delivery or rescue operation")
        time.sleep(self.hover_duration)
        print()
    
    def _phase_return(self):
        """Phase 4: Return to home"""
        print("=== PHASE 4: RETURN TO HOME ===")
        self.state = DroneState.RETURNING
        self.led.set_off()
        
        print(f"[Return] Returning to home position...")
        print(f"[Return] Home: {self.home_position}")
        
        # Return at higher speed
        self.flight.goto_position(self.home_position, self.return_speed)
        
        # Monitor return
        while True:
            current_pos = self.flight.get_position()
            distance = current_pos.horizontal_distance_to(self.home_position)
            
            if distance > 5.0:
                if int(distance) % 20 == 0:
                    print(f"[Return] Distance to home: {distance:.0f}m")
            else:
                print(f"[Return] Distance to home: {distance:.1f}m")
            
            # Within 2m of home
            if distance < 2.0:
                print("[Return] ✓ Arrived at home position")
                break
            
            time.sleep(0.5)
        
        print()
    
    def _phase_complete(self):
        """Phase 5: Mission complete and land"""
        print("=== PHASE 5: LANDING ===")
        self.state = DroneState.LANDING
        
        # Mission summary
        print("\n[Summary] Mission Statistics:")
        print(f"  Total detections: {len(self.all_detections)}")
        boats = sum(1 for d in self.all_detections if d.is_boat())
        persons = sum(1 for d in self.all_detections if d.is_person())
        print(f"  Boats detected (ignored): {boats}")
        print(f"  Persons detected: {persons}")
        if self.target:
            print(f"  Target: {self.target.target_type.value}")
            print(f"  Confidence: {self.target.confidence:.2%}")
        
        # Land
        print("\n[Landing] Initiating landing sequence...")
        self.flight.land()
        
        self.state = DroneState.MISSION_COMPLETE
        
        print("\n" + "=" * 60)
        print("✓ MISSION COMPLETE")
        print("=" * 60)
    
    def _emergency_land(self):
        """Emergency landing procedure"""
        print("\n[EMERGENCY] ⚠️ INITIATING EMERGENCY LANDING")
        self.state = DroneState.EMERGENCY
        self.led.set_red()
        
        try:
            self.flight.land()
        except Exception as e:
            print(f"[EMERGENCY] ❌ Landing failed: {e}")
        
        print("[EMERGENCY] Landed (check drone status)")
