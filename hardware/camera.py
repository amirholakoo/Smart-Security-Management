import time
import cv2
import numpy as np
import threading
import config
import logging

# Try to import picamera2, but provide fallback if not available
PICAMERA_AVAILABLE = False
try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Picamera2 not available! Using mock camera implementation.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Camera:
    """Interface for the Raspberry Pi Camera"""
    
    def __init__(self, resolution=None, framerate=None, rotation=None):
        """Initialize camera with specified parameters or use defaults from config"""
        self.resolution = resolution or config.CAMERA_RESOLUTION
        self.framerate = framerate or config.CAMERA_FRAMERATE
        self.rotation = rotation if rotation is not None else config.CAMERA_ROTATION
        self.picam = None
        self.is_running = False
        self.current_frame = None
        self.lock = threading.Lock()
        self.capture_thread = None
        self.use_mock = not PICAMERA_AVAILABLE
        
        logger.info(f"Initializing camera with resolution: {self.resolution}, "
                   f"framerate: {self.framerate}, rotation: {self.rotation}")
        
        if self.use_mock:
            logger.warning("Using mock camera implementation (no hardware access)")
    
    def start(self):
        """Start the camera and begin capturing frames"""
        if self.is_running:
            logger.warning("Camera is already running")
            return
            
        try:
            if not self.use_mock:
                # Initialize and configure the real camera
                self.picam = Picamera2()
                
                # Configure the camera
                camera_config = self.picam.create_preview_configuration(
                    main={"size": self.resolution},
                    controls={"FrameRate": self.framerate}
                )
                self.picam.configure(camera_config)
                
                # Start the camera
                self.picam.start()
                
                # Set rotation if needed
                if self.rotation:
                    self.picam.set_rotation(self.rotation)
            else:
                # Using mock camera - create a fake black frame
                logger.info("Starting mock camera")
                
            self.is_running = True
            
            # Start capture thread
            self.capture_thread = threading.Thread(target=self._capture_loop)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            
            logger.info("Camera started successfully")
            
        except Exception as e:
            logger.error(f"Error starting camera: {str(e)}")
            if self.picam:
                self.picam.close()
                self.picam = None
            self.is_running = False
            raise
    
    def stop(self):
        """Stop the camera and release resources"""
        if not self.is_running:
            logger.warning("Camera is not running")
            return
            
        self.is_running = False
        
        # Wait for capture thread to finish
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=1.0)
            
        # Close the camera if using real hardware
        if not self.use_mock and self.picam:
            self.picam.close()
            self.picam = None
            
        logger.info("Camera stopped")
    
    def _capture_loop(self):
        """Background thread to continuously capture frames"""
        while self.is_running:
            try:
                if not self.use_mock:
                    # Capture a real frame from hardware
                    frame = self.picam.capture_array()
                    
                    # Convert to BGR format for OpenCV compatibility
                    if frame.shape[2] == 4:  # If RGBA
                        frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
                else:
                    # Generate a mock frame (black with text)
                    width, height = self.resolution
                    frame = np.zeros((height, width, 3), dtype=np.uint8)
                    
                    # Add some text to the mock frame
                    text = "MOCK CAMERA - NO HARDWARE"  
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    text_size = cv2.getTextSize(text, font, 1, 2)[0]
                    
                    # Position text in center
                    text_x = (width - text_size[0]) // 2
                    text_y = (height + text_size[1]) // 2
                    
                    cv2.putText(frame, text, (text_x, text_y), font, 1, (0, 255, 0), 2)
                    
                    # Add timestamp
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    cv2.putText(frame, timestamp, (10, height - 20), font, 0.5, (255, 255, 255), 1)
                
                # Store the frame
                with self.lock:
                    self.current_frame = frame
                    
                # Sleep briefly to simulate camera framerate in mock mode
                if self.use_mock:
                    time.sleep(1.0 / self.framerate)
                    
            except Exception as e:
                logger.error(f"Error in capture loop: {str(e)}")
                time.sleep(0.1)  # Avoid tight loop on error
    
    def get_frame(self):
        """Get the latest camera frame"""
        with self.lock:
            if self.current_frame is None:
                return None
            return self.current_frame.copy()
    
    def capture_image(self):
        """Capture a single image and return it"""
        frame = self.get_frame()
        if frame is None:
            logger.warning("No frame available for capture")
        return frame
    
    def save_image(self, file_path):
        """Capture an image and save it to the specified path"""
        frame = self.get_frame()
        if frame is None:
            logger.warning("No frame available to save")
            return False
            
        try:
            cv2.imwrite(file_path, frame)
            logger.info(f"Image saved to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving image: {str(e)}")
            return False
            
    def __del__(self):
        """Ensure resources are released when object is destroyed"""
        self.stop()


# Singleton camera instance for global use
_camera_instance = None

def get_camera():
    """Get the global camera instance, initializing if necessary"""
    global _camera_instance
    if _camera_instance is None:
        _camera_instance = Camera()
    return _camera_instance
