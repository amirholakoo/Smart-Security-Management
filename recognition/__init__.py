from .plate_recognition import (
    get_plate_recognizer,
    get_plate_detection_service,
    LicensePlateRecognizer,
    PlateDetectionService
)

from .face_recognition import (
    get_face_recognizer,
    get_face_detection_service,
    FaceRecognizer,
    FaceDetectionService
)

__all__ = [
    'get_plate_recognizer',
    'get_plate_detection_service',
    'LicensePlateRecognizer',
    'PlateDetectionService',
    'get_face_recognizer',
    'get_face_detection_service',
    'FaceRecognizer',
    'FaceDetectionService'
]
