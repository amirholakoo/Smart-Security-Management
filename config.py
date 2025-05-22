import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Base directory of the application
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Camera settings
CAMERA_RESOLUTION = (1920, 1080)
CAMERA_FRAMERATE = 30
CAMERA_ROTATION = 0  # Rotate camera if needed (0, 90, 180, 270)

# License plate recognition settings
PLATE_CONFIDENCE_THRESHOLD = 0.7
PLATE_DETECTION_INTERVAL = 1  # seconds between detection attempts
PLATE_MATCH_THRESHOLD = 0.8  # similarity threshold for plate matching

# Face recognition settings
FACE_RECOGNITION_ENABLED = False  # For future implementation
FACE_DETECTION_INTERVAL = 1  # seconds between detection attempts
FACE_MATCH_THRESHOLD = 0.6  # lower = more strict

# Relay settings
RELAY_PIN_GATE = 17  # GPIO pin for gate relay
RELAY_ACTIVATION_TIME = 3  # seconds to keep relay activated

# Database settings
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'sms.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Flask settings
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

# Access control settings
GATE_OPEN_DURATION = 10  # seconds to keep gate open
ACCESS_LOG_RETENTION_DAYS = 30  # days to keep access logs

# Paths for storing images
PLATE_IMAGES_DIR = os.path.join(BASE_DIR, 'static', 'img', 'plates')
FACE_IMAGES_DIR = os.path.join(BASE_DIR, 'static', 'img', 'faces')
LOG_IMAGES_DIR = os.path.join(BASE_DIR, 'static', 'img', 'logs')

# Create directories if they don't exist
for directory in [PLATE_IMAGES_DIR, FACE_IMAGES_DIR, LOG_IMAGES_DIR]:
    os.makedirs(directory, exist_ok=True)
