import cv2
import numpy as np
import os
import time
import threading
import logging
import face_recognition
import pickle
from pathlib import Path
import config
from database import log_access

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FaceRecognizer:
    """Recognizes faces in images and matches them against the database"""
    
    def __init__(self, match_threshold=None):
        """Initialize face recognizer"""
        self.match_threshold = match_threshold or config.FACE_MATCH_THRESHOLD
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_face_user_ids = []
        self.lock = threading.Lock()
        
        # Encodings will be loaded on first use or when explicitly called
        logger.info("Face recognizer initialized; encodings will be loaded when needed")
        
    def load_face_encodings(self):
        """Load face encodings from the database"""
        try:
            # Import here to avoid circular imports
            from flask import current_app
            
            with self.lock:
                # Clear existing encodings
                self.known_face_encodings = []
                self.known_face_names = []
                self.known_face_user_ids = []
                
                # Check if we're in an application context
                if not current_app._get_current_object():
                    logger.warning("No Flask application context available to load face encodings")
                    return
                
                # Import here to avoid circular imports
                from database import User, Face, db
                
                # Get all active users with face records
                users = User.query.filter_by(is_active=True).all()
                
                for user in users:
                    # Get all active faces for this user
                    faces = Face.query.filter_by(user_id=user.id, is_active=True).all()
                    
                    for face in faces:
                        # Check if encoding file exists
                        if face.encoding_path and os.path.exists(face.encoding_path):
                            try:
                                # Load encoding from file
                                with open(face.encoding_path, 'rb') as f:
                                    encoding = pickle.load(f)
                                    
                                # Add to known faces
                                self.known_face_encodings.append(encoding)
                                self.known_face_names.append(f"{user.first_name} {user.last_name}")
                                self.known_face_user_ids.append(user.id)
                                
                            except Exception as e:
                                logger.error(f"Error loading face encoding {face.encoding_path}: {str(e)}")
                        
                        # If no encoding file but image file exists, generate encoding
                        elif face.file_path and os.path.exists(face.file_path):
                            try:
                                # Load image
                                image = face_recognition.load_image_file(face.file_path)
                                
                                # Generate encoding
                                encodings = face_recognition.face_encodings(image)
                                
                                # If face found in image, use first encoding
                                if encodings:
                                    encoding = encodings[0]
                                    
                                    # Save encoding to file
                                    encoding_filename = f"{os.path.splitext(os.path.basename(face.file_path))[0]}_encoding.dat"
                                    encoding_path = os.path.join(config.FACE_IMAGES_DIR, encoding_filename)
                                    
                                    with open(encoding_path, 'wb') as f:
                                        pickle.dump(encoding, f)
                                    
                                    # Update database record
                                    face.encoding_path = encoding_path
                                    db.session.commit()
                                    
                                    # Add to known faces
                                    self.known_face_encodings.append(encoding)
                                    self.known_face_names.append(f"{user.first_name} {user.last_name}")
                                    self.known_face_user_ids.append(user.id)
                                    
                            except Exception as e:
                                logger.error(f"Error generating face encoding for {face.file_path}: {str(e)}")
                
                logger.info(f"Loaded {len(self.known_face_encodings)} face encodings")
        except Exception as e:
            logger.error(f"Error loading face encodings: {str(e)}")
    
    def recognize_faces(self, frame):
        """
        Recognize faces in the given frame
        Returns list of (name, user_id, confidence, face_location) tuples
        """
        if frame is None:
            return []
        
        # Make sure encodings are loaded
        if not self.known_face_encodings:
            self.load_face_encodings()
            
        # If still no encodings after loading attempt, return empty list
        if not self.known_face_encodings:
            return []
            
        # Resize frame for faster face recognition
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        
        # Convert from BGR to RGB (face_recognition uses RGB)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        # Find face locations and encodings
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
        
        # Match each face against known faces
        recognized_faces = []
        
        for face_encoding, face_location in zip(face_encodings, face_locations):
            # Compare face with known faces
            matches = face_recognition.compare_faces(
                self.known_face_encodings, face_encoding, tolerance=self.match_threshold)
            
            # Calculate face distances for confidence score
            face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
            
            if any(matches) and len(face_distances) > 0:
                # Find the best match
                best_match_index = np.argmin(face_distances)
                
                if matches[best_match_index]:
                    name = self.known_face_names[best_match_index]
                    user_id = self.known_face_user_ids[best_match_index]
                    confidence = 1.0 - face_distances[best_match_index]  # Convert distance to confidence score
                    
                    # Scale face location back to original frame size
                    top, right, bottom, left = face_location
                    top *= 4
                    right *= 4
                    bottom *= 4
                    left *= 4
                    
                    recognized_faces.append((name, user_id, confidence, (top, right, bottom, left)))
        
        return recognized_faces
    
    def process_frame(self, frame):
        """
        Process a frame to recognize faces
        Returns list of (name, user_id, confidence, face_location) tuples
        """
        with self.lock:
            return self.recognize_faces(frame)
    
    def allow_access(self, user_id, name, frame, confidence):
        """
        Allow access to user by activating the appropriate relay
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
                logger.warning("No Flask application context available to log face access")
                # Still try to open gate
                try:
                    relay = get_relay_controller()
                    relay.open_gate()
                    return True
                except Exception as e:
                    logger.error(f"Error activating relay: {str(e)}")
                return False
            
            # Import here to avoid circular imports
            from database import log_access
            
            # Log authorized access
            log_access(
                access_type='pedestrian',
                recognition_type='face',
                image_data=binary_image,
                user_id=user_id,
                is_authorized=True,
                confidence_score=confidence,
                notes=f"Face recognized: {name}"
            )
            
            # Activate appropriate relay (can be extended for different doors)
            try:
                relay = get_relay_controller()
                relay.open_gate()  # For now, use the same gate relay
                return True
            except Exception as e:
                logger.error(f"Error activating relay: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Error in face allow_access: {str(e)}")
            return False


# Singleton recognizer instance for global use
_recognizer_instance = None

def get_face_recognizer():
    """Get the global face recognizer instance, initializing if necessary"""
    global _recognizer_instance
    if _recognizer_instance is None:
        _recognizer_instance = FaceRecognizer()
    return _recognizer_instance


class FaceDetectionService:
    """Service for continuously detecting faces from camera feed"""
    
    def __init__(self, interval=None):
        """Initialize face detection service"""
        self.interval = interval or config.FACE_DETECTION_INTERVAL
        self.running = False
        self.detection_thread = None
    
    def start(self):
        """Start the face detection service"""
        if not config.FACE_RECOGNITION_ENABLED:
            logger.info("Face recognition is disabled in configuration")
            return
            
        if self.running:
            logger.warning("Face detection service is already running")
            return
            
        self.running = True
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
        logger.info("Face detection service started")
    
    def stop(self):
        """Stop the face detection service"""
        if not self.running:
            logger.warning("Face detection service is not running")
            return
            
        self.running = False
        
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=2.0)
            
        logger.info("Face detection service stopped")
    
    def _detection_loop(self):
        """Main detection loop that runs in a background thread"""
        from hardware import get_camera
        
        # Get camera and recognizer instances
        camera = get_camera()
        recognizer = get_face_recognizer()
        
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
                    
                    # Process frame to detect faces
                    recognized_faces = recognizer.process_frame(frame)
                    
                    # Allow access for each recognized face with sufficient confidence
                    for name, user_id, confidence, face_location in recognized_faces:
                        logger.info(f"Recognized face: {name} with confidence: {confidence:.2f}")
                        
                        # Allow access
                        recognizer.allow_access(user_id, name, frame, confidence)
                
                # Sleep briefly to avoid hogging CPU
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in face detection loop: {str(e)}")
                time.sleep(1.0)  # Sleep longer on error
    
    def __del__(self):
        """Ensure the service is stopped when object is destroyed"""
        self.stop()


# Singleton detection service instance for global use
_detection_service = None

def get_face_detection_service():
    """Get the global face detection service instance, initializing if necessary"""
    global _detection_service
    if _detection_service is None:
        _detection_service = FaceDetectionService()
    return _detection_service
