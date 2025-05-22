import os
import cv2
import numpy as np
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import time
import threading

# Import configuration
import config

# Import database models and utilities
from database import (
    db, init_db, User, Vehicle, PlateImage, Face, AccessLog,
    register_vehicle, save_plate_image, save_face_image, log_access,
    get_all_vehicles, get_all_users, find_vehicle_by_plate
)

# Import hardware interfaces
from hardware import get_camera, get_relay_controller

# Import recognition modules
from recognition import (
    get_plate_recognizer, get_plate_detection_service,
    get_face_recognizer, get_face_detection_service
)

# Initialize Flask app
app = Flask(__name__)
app.config.from_object('config')

# Initialize database
db.init_app(app)

# Configure login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Global detection services
plate_detection_service = None
face_detection_service = None

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helper function for generating camera frames
def generate_camera_frames():
    """Generate frames from the camera for video streaming"""
    camera = get_camera()
    
    # Start camera if not already running
    if not camera.is_running:
        camera.start()
    
    while True:
        # Get frame from camera
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.1)
            continue
        
        # Encode frame as JPEG
        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            continue
            
        # Convert to bytes
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

# Routes
@app.route('/')
@login_required
def index():
    """Dashboard/home page"""
    # Get stats for dashboard
    vehicle_count = Vehicle.query.filter_by(is_active=True).count()
    user_count = User.query.filter_by(is_active=True).count()
    
    # Get recent access logs
    recent_logs = AccessLog.query.order_by(AccessLog.timestamp.desc()).limit(10).all()
    
    return render_template('index.html', 
                           vehicle_count=vehicle_count,
                           user_count=user_count,
                           recent_logs=recent_logs)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Login successful', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('users/login.html')

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

# User management routes
@app.route('/users')
@login_required
def users():
    """List all users"""
    if current_user.role != 'admin':
        flash('You do not have permission to view users', 'danger')
        return redirect(url_for('index'))
    
    users = User.query.all()
    return render_template('users/index.html', users=users)

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    """Add a new user"""
    if current_user.role != 'admin':
        flash('You do not have permission to add users', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        role = request.form.get('role', 'user')
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('add_user'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('add_user'))
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('User created successfully', 'success')
        return redirect(url_for('users'))
    
    return render_template('users/add.html')

@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    """Edit an existing user"""
    if current_user.role != 'admin' and current_user.id != user_id:
        flash('You do not have permission to edit this user', 'danger')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        # Only admin can change roles
        if current_user.role == 'admin':
            role = request.form.get('role')
            if role:
                user.role = role
            
            is_active = request.form.get('is_active')
            user.is_active = True if is_active == 'on' else False
        
        # Update user info
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        
        # Check if email changed and already exists
        if email != user.email and User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('edit_user', user_id=user_id))
        
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        
        # Update password if provided
        password = request.form.get('password')
        if password:
            user.password_hash = generate_password_hash(password)
        
        db.session.commit()
        
        flash('User updated successfully', 'success')
        return redirect(url_for('users') if current_user.role == 'admin' else url_for('index'))
    
    return render_template('users/edit.html', user=user)

@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    """Delete a user"""
    if current_user.role != 'admin':
        flash('You do not have permission to delete users', 'danger')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    
    # Don't allow deleting self
    if user.id == current_user.id:
        flash('You cannot delete your own account', 'danger')
        return redirect(url_for('users'))
    
    # Delete user
    db.session.delete(user)
    db.session.commit()
    
    flash('User deleted successfully', 'success')
    return redirect(url_for('users'))

# Vehicle routes
@app.route('/vehicles')
@login_required
def vehicles():
    """List all vehicles"""
    if current_user.role == 'admin':
        vehicles = Vehicle.query.all()
    else:
        vehicles = Vehicle.query.filter_by(owner_id=current_user.id).all()
    
    return render_template('plates/index.html', vehicles=vehicles)

@app.route('/vehicles/add', methods=['GET', 'POST'])
@login_required
def add_vehicle():
    """Add a new vehicle"""
    if request.method == 'POST':
        license_plate = request.form.get('license_plate')
        make = request.form.get('make')
        model = request.form.get('model')
        color = request.form.get('color')
        notes = request.form.get('notes')
        
        # Admin can assign vehicle to any user
        if current_user.role == 'admin':
            owner_id = request.form.get('owner_id')
        else:
            owner_id = current_user.id
        
        # Check if license plate already exists
        if Vehicle.query.filter_by(license_plate=license_plate).first():
            flash('License plate already registered', 'danger')
            return redirect(url_for('add_vehicle'))
        
        # Create new vehicle
        vehicle = register_vehicle(
            owner_id=owner_id,
            license_plate=license_plate,
            make=make,
            model=model,
            color=color,
            notes=notes
        )
        
        # Handle plate image upload
        plate_image = request.files.get('plate_image')
        if plate_image and plate_image.filename:
            image_data = plate_image.read()
            save_plate_image(vehicle.id, image_data)
        
        flash('Vehicle registered successfully', 'success')
        return redirect(url_for('vehicles'))
    
    # Get list of users for admin
    users = []
    if current_user.role == 'admin':
        users = User.query.filter_by(is_active=True).all()
    
    return render_template('plates/add.html', users=users)

@app.route('/vehicles/<int:vehicle_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_vehicle(vehicle_id):
    """Edit an existing vehicle"""
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    
    # Check if user has permission to edit this vehicle
    if current_user.role != 'admin' and vehicle.owner_id != current_user.id:
        flash('You do not have permission to edit this vehicle', 'danger')
        return redirect(url_for('vehicles'))
    
    if request.method == 'POST':
        license_plate = request.form.get('license_plate')
        make = request.form.get('make')
        model = request.form.get('model')
        color = request.form.get('color')
        notes = request.form.get('notes')
        
        # Check if license plate changed and already exists
        if license_plate != vehicle.license_plate and Vehicle.query.filter_by(license_plate=license_plate).first():
            flash('License plate already registered', 'danger')
            return redirect(url_for('edit_vehicle', vehicle_id=vehicle_id))
        
        # Admin can change owner
        if current_user.role == 'admin':
            owner_id = request.form.get('owner_id')
            if owner_id:
                vehicle.owner_id = owner_id
            
            is_active = request.form.get('is_active')
            vehicle.is_active = True if is_active == 'on' else False
        
        # Update vehicle info
        vehicle.license_plate = license_plate
        vehicle.make = make
        vehicle.model = model
        vehicle.color = color
        vehicle.notes = notes
        
        db.session.commit()
        
        # Handle plate image upload
        plate_image = request.files.get('plate_image')
        if plate_image and plate_image.filename:
            image_data = plate_image.read()
            save_plate_image(vehicle.id, image_data)
        
        flash('Vehicle updated successfully', 'success')
        return redirect(url_for('vehicles'))
    
    # Get list of users for admin
    users = []
    if current_user.role == 'admin':
        users = User.query.filter_by(is_active=True).all()
    
    return render_template('plates/edit.html', vehicle=vehicle, users=users)

@app.route('/vehicles/<int:vehicle_id>/delete', methods=['POST'])
@login_required
def delete_vehicle(vehicle_id):
    """Delete a vehicle"""
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    
    # Check if user has permission to delete this vehicle
    if current_user.role != 'admin' and vehicle.owner_id != current_user.id:
        flash('You do not have permission to delete this vehicle', 'danger')
        return redirect(url_for('vehicles'))
    
    # Delete vehicle
    db.session.delete(vehicle)
    db.session.commit()
    
    flash('Vehicle deleted successfully', 'success')
    return redirect(url_for('vehicles'))

@app.route('/vehicles/<int:vehicle_id>/plates')
@login_required
def vehicle_plates(vehicle_id):
    """View plate images for a vehicle"""
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    
    # Check if user has permission to view this vehicle
    if current_user.role != 'admin' and vehicle.owner_id != current_user.id:
        flash('You do not have permission to view this vehicle', 'danger')
        return redirect(url_for('vehicles'))
    
    return render_template('plates/images.html', vehicle=vehicle)

@app.route('/vehicles/<int:vehicle_id>/plates/<int:plate_id>/delete', methods=['POST'])
@login_required
def delete_plate_image(vehicle_id, plate_id):
    """Delete a plate image"""
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    plate_image = PlateImage.query.get_or_404(plate_id)
    
    # Check if user has permission
    if current_user.role != 'admin' and vehicle.owner_id != current_user.id:
        flash('You do not have permission to delete this image', 'danger')
        return redirect(url_for('vehicle_plates', vehicle_id=vehicle_id))
    
    # Check if plate image belongs to vehicle
    if plate_image.vehicle_id != vehicle_id:
        flash('Image does not belong to this vehicle', 'danger')
        return redirect(url_for('vehicle_plates', vehicle_id=vehicle_id))
    
    # Delete file if it exists
    if plate_image.file_path and os.path.exists(plate_image.file_path):
        os.remove(plate_image.file_path)
    
    # Delete database record
    db.session.delete(plate_image)
    db.session.commit()
    
    flash('Plate image deleted successfully', 'success')
    return redirect(url_for('vehicle_plates', vehicle_id=vehicle_id))

# Face routes
@app.route('/faces')
@login_required
def faces():
    """List all faces for the current user, or all faces for admin"""
    if current_user.role == 'admin':
        user_faces = Face.query.all()
    else:
        user_faces = Face.query.filter_by(user_id=current_user.id).all()
    
    return render_template('users/faces.html', faces=user_faces)

@app.route('/faces/add', methods=['GET', 'POST'])
@login_required
def add_face():
    """Add a new face for a user"""
    if request.method == 'POST':
        # Admin can add face for any user
        if current_user.role == 'admin':
            user_id = request.form.get('user_id')
        else:
            user_id = current_user.id
        
        # Handle face image upload
        face_image = request.files.get('face_image')
        if face_image and face_image.filename:
            image_data = face_image.read()
            save_face_image(user_id, image_data)
            
            # Reload face recognizer
            face_recognizer = get_face_recognizer()
            face_recognizer.load_face_encodings()
            
            flash('Face added successfully', 'success')
            return redirect(url_for('faces'))
        else:
            flash('No face image provided', 'danger')
    
    # Get list of users for admin
    users = []
    if current_user.role == 'admin':
        users = User.query.filter_by(is_active=True).all()
    
    return render_template('users/add_face.html', users=users)

@app.route('/faces/<int:face_id>/delete', methods=['POST'])
@login_required
def delete_face(face_id):
    """Delete a face"""
    face = Face.query.get_or_404(face_id)
    
    # Check if user has permission
    if current_user.role != 'admin' and face.user_id != current_user.id:
        flash('You do not have permission to delete this face', 'danger')
        return redirect(url_for('faces'))
    
    # Delete files if they exist
    if face.file_path and os.path.exists(face.file_path):
        os.remove(face.file_path)
    
    if face.encoding_path and os.path.exists(face.encoding_path):
        os.remove(face.encoding_path)
    
    # Delete database record
    db.session.delete(face)
    db.session.commit()
    
    # Reload face recognizer
    face_recognizer = get_face_recognizer()
    face_recognizer.load_face_encodings()
    
    flash('Face deleted successfully', 'success')
    return redirect(url_for('faces'))

# Access log routes
@app.route('/logs')
@login_required
def access_logs():
    """View access logs"""
    if current_user.role == 'admin':
        logs = AccessLog.query.order_by(AccessLog.timestamp.desc()).limit(100).all()
    else:
        # Regular users can only see logs related to their vehicles or their face
        vehicle_ids = [v.id for v in Vehicle.query.filter_by(owner_id=current_user.id).all()]
        logs = AccessLog.query.filter(
            (AccessLog.user_id == current_user.id) | 
            (AccessLog.vehicle_id.in_(vehicle_ids))
        ).order_by(AccessLog.timestamp.desc()).limit(100).all()
    
    return render_template('access_logs/index.html', logs=logs)

# Camera stream routes
@app.route('/video_feed')
@login_required
def video_feed():
    """Video streaming route for the camera"""
    return Response(generate_camera_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/camera')
@login_required
def camera():
    """Camera monitoring page"""
    return render_template('camera.html')

# Testing routes for manual control
@app.route('/test/open_gate', methods=['POST'])
@login_required
def test_open_gate():
    """Test gate opening"""
    if current_user.role != 'admin':
        flash('You do not have permission to test the gate', 'danger')
        return redirect(url_for('index'))
    
    relay = get_relay_controller()
    relay.open_gate()
    
    flash('Gate opened for testing', 'success')
    return redirect(url_for('index'))

@app.route('/test/close_gate', methods=['POST'])
@login_required
def test_close_gate():
    """Test gate closing"""
    if current_user.role != 'admin':
        flash('You do not have permission to test the gate', 'danger')
        return redirect(url_for('index'))
    
    relay = get_relay_controller()
    relay.close_gate()
    
    flash('Gate closed for testing', 'success')
    return redirect(url_for('index'))

@app.route('/test/pulse_gate', methods=['POST'])
@login_required
def test_pulse_gate():
    """Test gate pulsing"""
    if current_user.role != 'admin':
        flash('You do not have permission to test the gate', 'danger')
        return redirect(url_for('index'))
    
    relay = get_relay_controller()
    relay.pulse_gate()
    
    flash('Gate pulsed for testing', 'success')
    return redirect(url_for('index'))

@app.route('/api/status')
def api_status():
    """API endpoint for system status"""
    return jsonify({
        'status': 'online',
        'version': '3.0.0',
        'time': datetime.now().isoformat()
    })

def start_services():
    """Start all background services"""
    global plate_detection_service, face_detection_service
    
    # Start plate detection service
    plate_detection_service = get_plate_detection_service()
    plate_detection_service.start()
    
    # Start face detection service if enabled
    if config.FACE_RECOGNITION_ENABLED:
        face_detection_service = get_face_detection_service()
        face_detection_service.start()

# Register startup function to be executed with app context
@app.before_request
def check_services():
    """Ensure services are running before handling requests"""
    global plate_detection_service, face_detection_service
    
    # Start services if they're not already running
    if plate_detection_service is None:
        start_services()

def stop_services():
    """Stop all background services"""
    global plate_detection_service, face_detection_service
    
    # Stop plate detection service
    if plate_detection_service:
        plate_detection_service.stop()
    
    # Stop face detection service
    if face_detection_service:
        face_detection_service.stop()
    
    # Stop camera
    camera = get_camera()
    camera.stop()
    
    # Clean up relay controller
    relay = get_relay_controller()
    relay.cleanup()

def initialize_app():
    """Initialize the application, database, and services"""
    # Create directories for storing images if they don't exist
    os.makedirs(config.PLATE_IMAGES_DIR, exist_ok=True)
    os.makedirs(config.FACE_IMAGES_DIR, exist_ok=True)
    os.makedirs(config.LOG_IMAGES_DIR, exist_ok=True)
    
    # Create database tables if they don't exist
    with app.app_context():
        init_db()

# Entry point
if __name__ == '__main__':
    try:
        # Initialize application
        initialize_app()
        
        # Start the application
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Ensure services are stopped on shutdown
        with app.app_context():
            stop_services()
        print("Services stopped.")
