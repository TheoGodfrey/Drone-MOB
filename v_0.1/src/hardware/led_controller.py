"""
LED status indicator controller
"""

from abc import ABC, abstractmethod


class LEDController(ABC):
    """Abstract base class for LED control"""
    
    @abstractmethod
    def set_red(self):
        """Set LED to red (searching)"""
        pass
    
    @abstractmethod
    def set_green(self):
        """Set LED to green (target found)"""
        pass
    
    @abstractmethod
    def set_off(self):
        """Turn LED off"""
        pass


class SimulatedLEDController(LEDController):
    """Simulated LED for testing"""
    
    def __init__(self):
        self.current_color = "off"
    
    def set_red(self):
        """Simulated red LED"""
        self.current_color = "red"
        print("[LED] 🔴 RED - Searching")
    
    def set_green(self):
        """Simulated green LED"""
        self.current_color = "green"
        print("[LED] 🟢 GREEN - Person Found!")
    
    def set_off(self):
        """Simulated LED off"""
        self.current_color = "off"
        print("[LED] ⚫ OFF")


class GPIOLEDController(LEDController):
    """Real LED control via Raspberry Pi GPIO"""
    
    def __init__(self, red_pin: int = 17, green_pin: int = 27):
        """
        Args:
            red_pin: GPIO pin for red LED
            green_pin: GPIO pin for green LED
        """
        self.red_pin = red_pin
        self.green_pin = green_pin
        self.gpio = None
        self._initialize_gpio()
    
    def _initialize_gpio(self):
        """Initialize GPIO pins"""
        try:
            import RPi.GPIO as GPIO
            self.gpio = GPIO
            
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self.red_pin, GPIO.OUT)
            GPIO.setup(self.green_pin, GPIO.OUT)
            
            # Start with both off
            GPIO.output(self.red_pin, GPIO.LOW)
            GPIO.output(self.green_pin, GPIO.LOW)
            
            print("[LED] ✓ GPIO initialized")
        except ImportError:
            raise RuntimeError(
                "RPi.GPIO not installed. Install with: pip install RPi.GPIO"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize GPIO: {e}")
    
    def set_red(self):
        """Turn LED red"""
        if self.gpio:
            self.gpio.output(self.red_pin, self.gpio.HIGH)
            self.gpio.output(self.green_pin, self.gpio.LOW)
            print("[LED] 🔴 RED - Searching")
    
    def set_green(self):
        """Turn LED green"""
        if self.gpio:
            self.gpio.output(self.red_pin, self.gpio.LOW)
            self.gpio.output(self.green_pin, self.gpio.HIGH)
            print("[LED] 🟢 GREEN - Person Found!")
    
    def set_off(self):
        """Turn LED off"""
        if self.gpio:
            self.gpio.output(self.red_pin, self.gpio.LOW)
            self.gpio.output(self.green_pin, self.gpio.LOW)
            print("[LED] ⚫ OFF")
    
    def cleanup(self):
        """Clean up GPIO resources"""
        if self.gpio:
            self.gpio.cleanup()
