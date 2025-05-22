import time
import threading
import logging
import config

# Try to import GPIO, but provide fallback if not available
GPIO_AVAILABLE = False
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    logging.warning("RPi.GPIO not available! Using mock relay implementation.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RelayController:
    """Controls relay HAT for gate and other access points"""
    
    def __init__(self, gate_pin=None):
        """Initialize relay controller with specified pins or use defaults"""
        self.gate_pin = gate_pin if gate_pin is not None else config.RELAY_PIN_GATE
        self.initialized = False
        self.lock = threading.Lock()
        self.use_mock = not GPIO_AVAILABLE
        self.gate_status = False  # For mock implementation (False = closed, True = open)
        
        if self.use_mock:
            logging.warning("Using mock relay implementation (no hardware access)")
        
    def initialize(self):
        """Set up GPIO pins for relay control"""
        if self.initialized:
            return
            
        try:
            if not self.use_mock:
                # Set up real GPIO hardware
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                
                # Set up gate relay pin as output
                GPIO.setup(self.gate_pin, GPIO.OUT)
                
                # Ensure relay is off (relay is typically active-low)
                GPIO.output(self.gate_pin, GPIO.HIGH)
            else:
                # Using mock implementation
                self.gate_status = False  # Initialize gate as closed
                
            self.initialized = True
            logger.info(f"Relay controller initialized with gate pin: {self.gate_pin}")
            
        except Exception as e:
            logger.error(f"Error initializing relay controller: {str(e)}")
            self.cleanup()
            raise
    
    def open_gate(self, duration=None):
        """
        Activate the gate relay for the specified duration
        Returns a threading.Timer object that can be cancelled if needed
        """
        if not self.initialized:
            self.initialize()
            
        # Use default duration if not specified
        if duration is None:
            duration = config.GATE_OPEN_DURATION
            
        with self.lock:
            try:
                if not self.use_mock:
                    # Activate real hardware relay (LOW to turn on)
                    GPIO.output(self.gate_pin, GPIO.LOW)
                else:
                    # Update mock gate status
                    self.gate_status = True
                    
                logger.info(f"Gate opened, will close in {duration} seconds")
                
                # Set up timer to close gate after duration
                timer = threading.Timer(duration, self.close_gate)
                timer.daemon = True
                timer.start()
                
                return timer
                
            except Exception as e:
                logger.error(f"Error opening gate: {str(e)}")
                self.close_gate()  # Attempt to close gate for safety
                return None
    
    def close_gate(self):
        """Deactivate the gate relay to close the gate"""
        if not self.initialized:
            logger.warning("Relay controller not initialized")
            return
            
        with self.lock:
            try:
                if not self.use_mock:
                    # Deactivate real hardware relay (HIGH to turn off)
                    GPIO.output(self.gate_pin, GPIO.HIGH)
                else:
                    # Update mock gate status
                    self.gate_status = False
                    
                logger.info("Gate closed")
                
            except Exception as e:
                logger.error(f"Error closing gate: {str(e)}")
    
    def pulse_gate(self, pulse_duration=None):
        """
        Activate the gate relay for a short pulse
        Useful for triggering toggle-type gate controllers
        """
        if pulse_duration is None:
            pulse_duration = config.RELAY_ACTIVATION_TIME
            
        if not self.initialized:
            self.initialize()
            
        with self.lock:
            try:
                if not self.use_mock:
                    # Activate relay on real hardware
                    GPIO.output(self.gate_pin, GPIO.LOW)
                else:
                    # Mock implementation - toggle gate status
                    self.gate_status = True
                
                logger.info(f"Gate relay pulsed for {pulse_duration} seconds")
                
                # Wait for pulse duration
                time.sleep(pulse_duration)
                
                if not self.use_mock:
                    # Deactivate relay on real hardware
                    GPIO.output(self.gate_pin, GPIO.HIGH)
                else:
                    # Mock implementation - toggle gate status back
                    self.gate_status = False
                
            except Exception as e:
                logger.error(f"Error pulsing gate relay: {str(e)}")
                # Ensure relay is off
                if not self.use_mock:
                    GPIO.output(self.gate_pin, GPIO.HIGH)
                else:
                    self.gate_status = False
    
    def cleanup(self):
        """Release GPIO resources"""
        if self.initialized:
            try:
                # Ensure gate is closed
                self.close_gate()
                
                # Clean up GPIO if using real hardware
                if not self.use_mock and GPIO_AVAILABLE:
                    GPIO.cleanup(self.gate_pin)
                    
                self.initialized = False
                logger.info("Relay controller resources released")
                
            except Exception as e:
                logger.error(f"Error cleaning up relay controller: {str(e)}")
    
    def __del__(self):
        """Ensure resources are released when object is destroyed"""
        self.cleanup()


# Singleton relay controller instance for global use
_relay_instance = None

def get_relay_controller():
    """Get the global relay controller instance, initializing if necessary"""
    global _relay_instance
    if _relay_instance is None:
        _relay_instance = RelayController()
    return _relay_instance
