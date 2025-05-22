import cv2
import numpy as np
import os
import time
import threading
import logging
from pathlib import Path
import config
from database import find_vehicle_by_plate, get_all_vehicles, log_access

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LicensePlateRecognizer:
    """Recognizes license plates in images and matches them against the database"""
    
    def __init__(self, confidence_threshold=None, match_threshold=None):
        """Initialize license plate recognizer"""
        self.confidence_threshold = confidence_threshold or config.PLATE_CONFIDENCE_THRESHOLD
        self.match_threshold = match_threshold or config.PLATE_MATCH_THRESHOLD
        self.detector = None
        self.running = False
        self.lock = threading.Lock()
        self.templates = {}
        
        # Templates will be loaded on first use or when explicitly called
        logger.info("Plate recognizer initialized; templates will be loaded when needed")
        
    def load_templates(self):
        """Load all registered license plate images as templates for matching"""
        try:
            # Clear existing templates
            self.templates = {}
            
            # Import here to avoid circular imports
            from flask import current_app
            
            # Check if we're in an application context
            if not current_app._get_current_object():
                logger.warning("No Flask application context available to load templates")
                return
            
            # Get all active vehicles from the database
            from database import get_all_vehicles
            vehicles = get_all_vehicles(active_only=True)
            
            # Load plate images for each vehicle
            for vehicle in vehicles:
                plate_images = []
                for plate_image in vehicle.plate_images:
                    # Check if file exists
                    if os.path.exists(plate_image.file_path):
                        try:
                            # Load image
                            img = cv2.imread(plate_image.file_path, cv2.IMREAD_GRAYSCALE)
                            if img is not None:
                                plate_images.append(img)
                        except Exception as e:
                            logger.error(f"Error loading plate image {plate_image.file_path}: {str(e)}")
                
                # Store plate images for this vehicle
                if plate_images:
                    self.templates[vehicle.license_plate] = plate_images
                    logger.info(f"Loaded {len(plate_images)} template(s) for plate {vehicle.license_plate}")
            
            logger.info(f"Loaded templates for {len(self.templates)} license plates")
            
        except Exception as e:
            logger.error(f"Error loading license plate templates: {str(e)}")
            # Initialize with empty templates
            self.templates = {}
    
    def preprocess(self, image):
        """Preprocess image for license plate detection"""
        if image is None:
            return None
            
        # Convert to grayscale if image is in color
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Apply bilateral filter to reduce noise while preserving edges
        filtered = cv2.bilateralFilter(gray, 11, 17, 17)
        
        # Apply Canny edge detection
        edges = cv2.Canny(filtered, 30, 200)
        
        return edges
    
    def find_plate_region(self, image):
        """
        Attempt to find license plate regions in the image
        Returns a list of potential license plate regions as (x, y, w, h)
        """
        if image is None:
            return []
            
        # Preprocess image
        processed = self.preprocess(image)
        if processed is None:
            return []
        
        # Find contours
        contours, _ = cv2.findContours(processed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours by size and shape
        plate_regions = []
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
            # Get approximate polygon
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            
            # If polygon has 4 points, it might be a license plate
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                
                # Filter by aspect ratio (license plates are typically wider than tall)
                aspect_ratio = float(w) / h
                if 1.0 < aspect_ratio < 5.0 and w > 100 and h > 20:
                    plate_regions.append((x, y, w, h))
        
        return plate_regions

    def extract_plate(self, image, region):
        """Extract license plate from image using the given region"""
        if image is None or region is None:
            return None
            
        x, y, w, h = region
        
        # Extract plate region
        plate = image[y:y+h, x:x+w]
        
        # Convert to grayscale
        if len(plate.shape) == 3:
            plate_gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
        else:
            plate_gray = plate.copy()
        
        # Resize to standard size for matching
        plate_resized = cv2.resize(plate_gray, (240, 80))
        
        # Apply threshold to enhance contrast
        _, plate_threshold = cv2.threshold(plate_resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return plate_threshold
    
    def match_plate(self, plate_image):
        """
        Match plate image against templates
        Returns (license_plate, confidence) of the best match
        """
        if plate_image is None:
            return None, 0.0
            
        # Make sure templates are loaded
        if not self.templates:
            self.load_templates()
            
        # If still no templates after loading attempt, return no match
        if not self.templates:
            return None, 0.0
        
        best_match = None
        best_confidence = 0.0
        
        # For each template in the database
        for license_plate, templates in self.templates.items():
            # Try to match against each template for this plate
            for template in templates:
                # Resize template to match the extracted plate
                template_resized = cv2.resize(template, (plate_image.shape[1], plate_image.shape[0]))
                
                # Apply template matching
                result = cv2.matchTemplate(plate_image, template_resized, cv2.TM_CCOEFF_NORMED)
                _, confidence, _, _ = cv2.minMaxLoc(result)
                
                # Update best match if this one is better
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = license_plate
        
        return best_match, best_confidence
    
    def recognize_plate(self, image):
        """
        Recognize license plate in the image
        Returns (license_plate, confidence, plate_image, region) if found
        """
        if image is None:
            return None, 0.0, None, None
        
        # Find potential plate regions
        regions = self.find_plate_region(image)
        
        # Extract and match each region
        best_match = None
        best_confidence = 0.0
        best_plate_image = None
        best_region = None
        
        for region in regions:
            # Extract plate
            plate_image = self.extract_plate(image, region)
            if plate_image is None:
                continue
            
            # Match plate
            license_plate, confidence = self.match_plate(plate_image)
            
            # Update best match if this one is better
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = license_plate
                best_plate_image = plate_image
                best_region = region
        
        return best_match, best_confidence, best_plate_image, best_region
    
    def process_frame(self, frame):
        """
        Process a frame from the camera
        Returns (vehicle, confidence, plate_image, region) if a plate is recognized
        """
        try:
            # Recognize license plate
            license_plate, confidence, plate_image, region = self.recognize_plate(frame)
            
            # Check confidence threshold
            if license_plate and confidence >= self.confidence_threshold:
                try:
                    # Import here to avoid circular imports
                    from flask import current_app
                    from database import find_vehicle_by_plate
                    
                    # Check if we're in an application context
                    if current_app._get_current_object():
                        # Look up vehicle in database
                        vehicle = find_vehicle_by_plate(license_plate)
                        # Return vehicle and recognition details
                        return vehicle, confidence, plate_image, region
                    else:
                        logger.warning("No Flask application context available to find vehicle")
                        return None, confidence, plate_image, region
                except Exception as e:
                    logger.error(f"Error finding vehicle: {str(e)}")
            
            return None, confidence, plate_image, region
        except Exception as e:
            logger.error(f"Error in process_frame: {str(e)}")
            return None, 0.0, None, None
    
    def allow_access(self, vehicle, frame, confidence):
        """
        Allow access to vehicle by activating the gate relay
        Logs the access event in the database
        """
        try:
            from flask import current_app
            from hardware import get_relay_controller
            
            # Convert frame to binary for storage
            _, jpg_data = cv2.imencode('.jpg', frame)
            binary_image = jpg_data.tobytes()
            
            # Check if we're in an application context
            if not current_app._get_current_object():
                logger.warning("No Flask application context available to log access")
                # Still try to open gate if vehicle is recognized
                if vehicle:
                    try:
                        relay = get_relay_controller()
                        relay.open_gate()
                        return True
                    except Exception as e:
                        logger.error(f"Error activating gate relay: {str(e)}")
                return False
            
            # Import here to avoid circular imports
            from database import log_access
            
            if vehicle:
                # Log authorized access
                log_access(
                    access_type='vehicle',
                    recognition_type='plate',
                    image_data=binary_image,
                    vehicle_id=vehicle.id,
                    user_id=vehicle.owner_id,
                    is_authorized=True,
                    confidence_score=confidence,
                    notes=f"License plate recognized: {vehicle.license_plate}"
                )
                
                # Activate gate relay
                try:
                    relay = get_relay_controller()
                    relay.open_gate()
                    return True
                except Exception as e:
                    logger.error(f"Error activating gate relay: {str(e)}")
                    return False
            else:
                # Log unauthorized access attempt
                log_access(
                    access_type='vehicle',
                    recognition_type='plate',
                    image_data=binary_image,
                    is_authorized=False,
                    confidence_score=confidence,
                    notes="Unrecognized license plate"
                )
                return False
        except Exception as e:
            logger.error(f"Error in allow_access: {str(e)}")
            return False


# Singleton recognizer instance for global use
_recognizer_instance = None

def get_plate_recognizer():
    """Get the global plate recognizer instance, initializing if necessary"""
    global _recognizer_instance
    if _recognizer_instance is None:
        _recognizer_instance = LicensePlateRecognizer()
    return _recognizer_instance


class PlateDetectionService:
    """Service for continuously detecting license plates from camera feed"""
    
    def __init__(self, interval=None):
        """Initialize plate detection service"""
        self.interval = interval or config.PLATE_DETECTION_INTERVAL
        self.running = False
        self.detection_thread = None
    
    def start(self):
        """Start the plate detection service"""
        if self.running:
            logger.warning("Plate detection service is already running")
            return
            
        self.running = True
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
        logger.info("Plate detection service started")
    
    def stop(self):
        """Stop the plate detection service"""
        if not self.running:
            logger.warning("Plate detection service is not running")
            return
            
        self.running = False
        
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=2.0)
            
        logger.info("Plate detection service stopped")
    
    def _detection_loop(self):
        """Main detection loop that runs in a background thread"""
        from hardware import get_camera
        
        # Get camera and recognizer instances
        camera = get_camera()
        recognizer = get_plate_recognizer()
        
        # Start camera if not already started
        if not camera.is_running:
            camera.start()
        
        # Main detection loop
        last_detection_time = 0
        while self.running:
            try:
                # Get current time
                current_time = time.time()
                
                # Check if it's time for next detection
                if current_time - last_detection_time >= self.interval:
                    # Update last detection time
                    last_detection_time = current_time
                    
                    # Capture frame from camera
                    frame = camera.get_frame()
                    if frame is None:
                        continue
                    
                    # Process frame to detect license plate
                    vehicle, confidence, plate_image, region = recognizer.process_frame(frame)
                    
                    # If vehicle is recognized with sufficient confidence, allow access
                    if vehicle and confidence >= recognizer.confidence_threshold:
                        logger.info(f"Recognized license plate: {vehicle.license_plate} "
                                   f"with confidence: {confidence:.2f}")
                        
                        # Allow access
                        recognizer.allow_access(vehicle, frame, confidence)
                    
                    elif confidence > 0:
                        logger.info(f"Detected plate with insufficient confidence: {confidence:.2f}")
                
                # Sleep briefly to avoid hogging CPU
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in plate detection loop: {str(e)}")
                time.sleep(1.0)  # Sleep longer on error
    
    def __del__(self):
        """Ensure the service is stopped when object is destroyed"""
        self.stop()


# Singleton detection service instance for global use
_detection_service = None

def get_plate_detection_service():
    """Get the global plate detection service instance, initializing if necessary"""
    global _detection_service
    if _detection_service is None:
        _detection_service = PlateDetectionService()
    return _detection_service
