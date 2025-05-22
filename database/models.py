from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    """User model for authentication and access control"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), default='user')  # admin, user
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    vehicles = db.relationship('Vehicle', back_populates='owner', lazy=True)
    faces = db.relationship('Face', back_populates='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Vehicle(db.Model):
    """Vehicle model with license plate info"""
    id = db.Column(db.Integer, primary_key=True)
    license_plate = db.Column(db.String(20), unique=True, nullable=False)
    make = db.Column(db.String(50))
    model = db.Column(db.String(50))
    color = db.Column(db.String(30))
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign keys
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    owner = db.relationship('User', back_populates='vehicles')
    plate_images = db.relationship('PlateImage', back_populates='vehicle', lazy=True)
    access_logs = db.relationship('AccessLog', back_populates='vehicle', lazy=True)
    
    def __repr__(self):
        return f'<Vehicle {self.license_plate}>'

class PlateImage(db.Model):
    """Stores license plate images for matching"""
    id = db.Column(db.Integer, primary_key=True)
    file_path = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign keys
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    
    # Relationships
    vehicle = db.relationship('Vehicle', back_populates='plate_images')
    
    def __repr__(self):
        return f'<PlateImage {self.id} for {self.vehicle.license_plate}>'

class Face(db.Model):
    """Stores face images and encodings for recognition"""
    id = db.Column(db.Integer, primary_key=True)
    file_path = db.Column(db.String(255), unique=True, nullable=False)
    encoding_path = db.Column(db.String(255), unique=True, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    user = db.relationship('User', back_populates='faces')
    
    def __repr__(self):
        return f'<Face {self.id} for {self.user.username}>'

class AccessLog(db.Model):
    """Logs all access attempts, whether successful or not"""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    access_type = db.Column(db.String(20), nullable=False)  # vehicle, pedestrian
    recognition_type = db.Column(db.String(20), nullable=False)  # plate, face
    is_authorized = db.Column(db.Boolean, default=False)
    confidence_score = db.Column(db.Float)
    image_path = db.Column(db.String(255))
    notes = db.Column(db.Text)
    
    # Foreign keys - can be null for unrecognized/unauthorized access attempts
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationships
    vehicle = db.relationship('Vehicle', back_populates='access_logs')
    user = db.relationship('User', backref='access_logs')
    
    def __repr__(self):
        return f'<AccessLog {self.id} at {self.timestamp}>'
