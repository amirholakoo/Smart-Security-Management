# Security Management System (SSMv3)

A comprehensive security system for managing access control through license plate recognition and face detection.

## Features

- License plate recognition for vehicle access control
- Face recognition for pedestrian access (future expansion)
- Web-based management interface for registering authorized users
- Access logging and reporting
- Relay control for gate automation

## Hardware Requirements

- Raspberry Pi 5
- 8MP NoIR v2 Camera
- 3 Relay HAT

## Installation

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Configure your system in `config.py`
4. Run the application:
   ```
   python app.py
   ```

## System Architecture

The system is built with modularity in mind:

- `hardware/`: Interfaces with camera and relay hardware
- `recognition/`: Contains recognition algorithms
- `database/`: Manages data storage and retrieval
- `templates/` & `static/`: Web interface components

## License

This project is proprietary and confidential.
