from .models import db, User, Vehicle, PlateImage, Face, AccessLog
from .db_utils import (
    init_db,
    create_admin_user,
    register_vehicle,
    save_plate_image,
    save_face_image,
    log_access,
    get_all_vehicles,
    get_all_users,
    find_vehicle_by_plate,
    cleanup_old_logs
)

__all__ = [
    'db',
    'User',
    'Vehicle',
    'PlateImage',
    'Face',
    'AccessLog',
    'init_db',
    'create_admin_user',
    'register_vehicle',
    'save_plate_image',
    'save_face_image',
    'log_access',
    'get_all_vehicles',
    'get_all_users',
    'find_vehicle_by_plate',
    'cleanup_old_logs'
]
