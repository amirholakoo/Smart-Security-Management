import os
import shutil
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from .models import db, User, Vehicle, PlateImage, Face, AccessLog
import config

def init_db():
    """Initialize the database and create tables"""
    db.create_all()
    
    # Create admin user if no users exist
    if User.query.count() == 0:
        create_admin_user('admin', 'admin@example.com', 'admin123')
        
def create_admin_user(username, email, password):
    """Create an admin user"""
    admin = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        first_name='Admin',
        last_name='User',
        role='admin'
    )
    db.session.add(admin)
    db.session.commit()
    return admin

def register_vehicle(owner_id, license_plate, make=None, model=None, color=None, notes=None):
    """Register a new vehicle with license plate"""
    vehicle = Vehicle(
        owner_id=owner_id,
        license_plate=license_plate,
        make=make,
        model=model,
        color=color,
        notes=notes
    )
    db.session.add(vehicle)
    db.session.commit()
    return vehicle

def save_plate_image(vehicle_id, image_data, filename=None):
    """Save a license plate image for a vehicle"""
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return None
        
    # Generate filename if not provided
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{vehicle.license_plate}_{timestamp}.jpg"
    
    # Create full file path
    file_path = os.path.join(config.PLATE_IMAGES_DIR, filename)
    
    # Save image
    with open(file_path, 'wb') as f:
        f.write(image_data)
    
    # Create database record
    plate_image = PlateImage(
        vehicle_id=vehicle_id,
        file_path=file_path
    )
    db.session.add(plate_image)
    db.session.commit()
    
    return plate_image

def save_face_image(user_id, image_data, encoding_data=None, filename=None):
    """Save a face image and optional encoding for a user"""
    user = User.query.get(user_id)
    if not user:
        return None
        
    # Generate filename if not provided
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{user.username}_{timestamp}.jpg"
    
    # Create full file path
    file_path = os.path.join(config.FACE_IMAGES_DIR, filename)
    
    # Save image
    with open(file_path, 'wb') as f:
        f.write(image_data)
    
    # Save encoding if provided
    encoding_path = None
    if encoding_data:
        encoding_filename = f"{os.path.splitext(filename)[0]}_encoding.dat"
        encoding_path = os.path.join(config.FACE_IMAGES_DIR, encoding_filename)
        with open(encoding_path, 'wb') as f:
            f.write(encoding_data)
    
    # Create database record
    face = Face(
        user_id=user_id,
        file_path=file_path,
        encoding_path=encoding_path
    )
    db.session.add(face)
    db.session.commit()
    
    return face

def log_access(access_type, recognition_type, image_data=None, 
               vehicle_id=None, user_id=None, is_authorized=False, 
               confidence_score=None, notes=None):
    """Log an access attempt"""
    # Save access image if provided
    image_path = None
    if image_data:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"access_{timestamp}.jpg"
        image_path = os.path.join(config.LOG_IMAGES_DIR, filename)
        with open(image_path, 'wb') as f:
            f.write(image_data)
    
    # Create log entry
    log = AccessLog(
        access_type=access_type,
        recognition_type=recognition_type,
        is_authorized=is_authorized,
        confidence_score=confidence_score,
        image_path=image_path,
        vehicle_id=vehicle_id,
        user_id=user_id,
        notes=notes
    )
    db.session.add(log)
    db.session.commit()
    
    return log

def get_all_vehicles(active_only=True):
    """Get all vehicles, optionally filtered by active status"""
    query = Vehicle.query
    if active_only:
        query = query.filter_by(is_active=True)
    return query.all()

def get_all_users(active_only=True):
    """Get all users, optionally filtered by active status"""
    query = User.query
    if active_only:
        query = query.filter_by(is_active=True)
    return query.all()

def find_vehicle_by_plate(license_plate):
    """Find a vehicle by its license plate"""
    return Vehicle.query.filter_by(license_plate=license_plate).first()

def cleanup_old_logs(days=None):
    """Remove access logs older than specified days"""
    if days is None:
        days = config.ACCESS_LOG_RETENTION_DAYS
        
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    old_logs = AccessLog.query.filter(AccessLog.timestamp < cutoff_date).all()
    
    # Delete associated images
    for log in old_logs:
        if log.image_path and os.path.exists(log.image_path):
            os.remove(log.image_path)
    
    # Delete log entries
    AccessLog.query.filter(AccessLog.timestamp < cutoff_date).delete()
    db.session.commit()
    
    return len(old_logs)
