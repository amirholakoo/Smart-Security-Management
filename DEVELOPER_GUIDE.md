# Security Management System (SSMv3) - Developer Guide

## 1. Introduction

Welcome to the SSMv3 Developer Guide! This document provides an overview of the Security Management System, its architecture, and guidelines for developers looking to contribute or understand the codebase.

SSMv3 is a Flask-based web application designed for license plate and face recognition, primarily for security and access control purposes. It's built to be modular and can run on a Raspberry Pi with camera hardware or in a simulated environment.

## 2. Technology Stack

### Backend:
- **Python 3**: Core programming language.
- **Flask**: Web framework for building the application.
  - **Flask-SQLAlchemy**: ORM for database interactions.
  - **Flask-Login**: User session management.
  - **Flask-Migrate**: Database schema migrations.
  - **Flask-Bcrypt**: Password hashing.
- **OpenCV (cv2)**: For image processing, license plate, and face recognition.
- **Picamera2/libcamera**: For Raspberry Pi camera interface (with mock fallback).
- **SQLite**: Default database (can be configured for others like PostgreSQL).

### Frontend:
- **HTML5**: Structure of the web pages.
- **CSS3 (Bootstrap 5)**: Styling and responsive design.
- **JavaScript (Vanilla JS, jQuery)**: Client-side interactivity.
- **Jinja2**: Templating engine used by Flask to render dynamic HTML.
- **Chart.js**: For rendering charts and statistics.

### Development & Deployment:
- **Git**: Version control.
- **Virtual Environments (venv)**: Isolating project dependencies.
- **Gunicorn/Waitress**: WSGI server for production (optional).

## 3. Project Structure

```
SSMv3/
├── app.py                     # Main Flask application, routes, and core logic
├── config.py                  # Configuration settings (database, camera, paths)
├── requirements.txt           # Python dependencies
├── DEVELOPER_GUIDE.md         # This guide
├── README.md                  # Project overview and setup for users
├── instance/                  # Instance-specific files (e.g., database file)
│   └── ssm_database.db
├── static/                    # Static assets (CSS, JS, images)
│   ├── css/
│   ├── js/
│   └── images/
├── templates/                 # HTML templates (Jinja2)
│   ├── auth/                  # Authentication related pages (login, register)
│   ├── includes/              # Reusable HTML partials (navbar, footer)
│   └── ...                    # Other feature-specific pages
├── database/
│   ├── models.py              # SQLAlchemy database models
│   └── db_utils.py            # Database utility functions (init, backup)
├── hardware/
│   ├── camera.py              # Camera interface (real and mock)
│   ├── relay_control.py       # Relay control interface (real and mock)
│   └── __init__.py
├── recognition/
│   ├── face_recognition_module.py  # Face recognition logic
│   ├── plate_recognition_module.py # License plate recognition logic
│   └── __init__.py
├── utils/
│   ├── helpers.py             # General helper functions
│   └── logger_config.py       # Logging configuration
├── logs/                      # Application logs
├── migrations/                # Flask-Migrate migration scripts
└── tests/                     # Unit and integration tests (to be developed)
```

## 4. Backend Development

The backend is built using Flask and is responsible for handling HTTP requests, business logic, database interactions, and interfacing with hardware/recognition modules.

### Key Components:

- **`app.py`**: 
  - Initializes the Flask application and its extensions (SQLAlchemy, LoginManager, etc.).
  - Defines all routes (URL endpoints) for the application.
  - Handles request processing, calls appropriate service functions, and renders templates.
  - Manages application context for tasks like database operations within recognition threads.

- **`config.py`**: 
  - Stores all configuration variables, such as database URI, secret key, camera settings, and file paths.
  - Uses environment variables for sensitive information where possible.

- **`database/models.py`**: 
  - Defines the structure of the database tables using SQLAlchemy ORM classes (e.g., `User`, `Vehicle`, `AccessLog`).

- **`database/db_utils.py`**: 
  - Contains utility functions for database management, such as initializing the database, creating tables, and performing backups.

- **`hardware/camera.py`**: 
  - Provides an abstraction layer for camera operations.
  - Implements `Camera` class with methods to start, stop, capture frames, and get status.
  - Supports both real Raspberry Pi camera (using `picamera2`) and a mock camera for development/testing without hardware.
  - Handles camera detection, initialization retries, and error logging.

- **`hardware/relay_control.py`**: 
  - (If applicable) Manages control of physical relays (e.g., for opening gates/doors).
  - Includes real and mock implementations.

- **`recognition/` modules**: 
  - `face_recognition_module.py`: Contains logic for detecting faces in camera frames and recognizing known individuals.
  - `plate_recognition_module.py`: Contains logic for detecting license plates in camera frames and recognizing registered vehicles.
  - These modules typically run in background threads and interact with `app.py` or `camera.py` for frames and with `database/models.py` for verification.

- **Authentication (`Flask-Login`)**: 
  - Manages user sessions, login, logout, and access control using decorators like `@login_required` and role checks.

### Workflow:
1. A user request hits a route defined in `app.py`.
2. The route handler function processes the request, potentially interacting with:
   - Database models (`database/models.py`) for CRUD operations.
   - Recognition modules (`recognition/`) for processing images/video streams.
   - Hardware modules (`hardware/`) for camera or relay control.
3. Data is fetched or processed.
4. An HTML template from the `templates/` directory is rendered with the processed data and sent back to the client.

### Logging:
- The application uses Python's `logging` module, configured in `utils/logger_config.py` (if present, otherwise standard Flask logging).
- Logs are crucial for debugging, especially for hardware interactions and background processes.

## 5. Frontend Development

The frontend is responsible for presenting data to the user and capturing user input. It's built with HTML, CSS (Bootstrap), and JavaScript, rendered server-side by Flask using Jinja2 templates.

### Key Components:

- **`templates/` directory**: Contains all Jinja2 HTML templates.
  - `base.html`: The main layout template that other templates extend. Includes common elements like navbar, footer, and imports for CSS/JS.
  - `includes/`: Reusable partial templates (e.g., `_navbar.html`, `_flashes.html`).
  - Feature-specific templates (e.g., `dashboard.html`, `manage_users.html`, `live_camera.html`).

- **`static/` directory**: Contains static assets.
  - `css/`: Custom CSS files and Bootstrap framework.
  - `js/`: Custom JavaScript files for client-side interactions (e.g., form validation, AJAX requests, dynamic content updates, Chart.js integration).
  - `images/`: Static images used in the UI.

### Jinja2 Templating:
- Flask uses Jinja2 to render dynamic HTML content.
- **Syntax**: `{{ variable }}`, `{% for item in items %}`, `{% if condition %}`.
- **Template Inheritance**: Use `{% extends 'base.html' %}` and `{% block content %}` for consistent page layouts.
- **URL Generation**: `url_for('route_function_name')` to generate URLs dynamically.
- **Static Files**: `url_for('static', filename='css/style.css')`.

### JavaScript:
- Used for enhancing user experience, making AJAX calls, and interacting with elements like charts or camera feeds.
- **AJAX**: Fetch data from backend API endpoints without full page reloads (e.g., updating live camera feed, refreshing log entries).
- **Event Handling**: Respond to user actions (clicks, form submissions).
- **DOM Manipulation**: Update page content dynamically.

### CSS (Bootstrap):
- Bootstrap 5 is used for a responsive, mobile-first design.
- Utilize Bootstrap classes for layout (grid system), components (buttons, forms, modals), and utilities.
- Custom styles can be added in `static/css/custom.css` to override or extend Bootstrap.

## 6. Key Features & Modules (Code Pointers)

- **User Authentication & Management**:
  - Models: `database/models.py` (`User`)
  - Routes: `app.py` (e.g., `/login`, `/register`, `/logout`, `/admin/users`)
  - Templates: `templates/auth/`, `templates/admin/manage_users.html`

- **Vehicle & License Plate Management**:
  - Models: `database/models.py` (`Vehicle`, `Plate`)
  - Routes: `app.py` (e.g., `/vehicles`, `/vehicles/add`)
  - Templates: `templates/manage_vehicles.html`

- **License Plate Recognition**:
  - Module: `recognition/plate_recognition_module.py`
  - Integration: `app.py` (routes consuming recognition results), `hardware/camera.py` (providing frames)

- **Face Recognition**:
  - Module: `recognition/face_recognition_module.py`
  - Integration: `app.py`, `hardware/camera.py`

- **Camera Interface & Streaming**:
  - Module: `hardware/camera.py`
  - Routes: `app.py` (e.g., `/video_feed`, `/live_camera`, `/test_camera`)
  - Templates: `templates/live_camera.html`, `templates/test_camera.html`
  - JS: `static/js/camera_feed.js` (for updating image source)

- **Access Logs & Statistics**:
  - Models: `database/models.py` (`AccessLog`)
  - Routes: `app.py` (e.g., `/access_logs`, `/dashboard`)
  - Templates: `templates/access_logs.html`, `templates/dashboard.html`
  - JS: `static/js/charts.js` (for rendering statistics with Chart.js)

## 7. Setting Up Development Environment

1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd SSMv3
    ```
2.  **Create and activate a virtual environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Set up the database**:
    -   Ensure `config.py` has the correct `SQLALCHEMY_DATABASE_URI`.
    -   Initialize the database and apply migrations:
        ```bash
        flask db init  # Only if migrations folder doesn't exist
        flask db migrate -m "Initial migration"
        flask db upgrade
        ```
    -   Alternatively, if using `db_utils.py` for setup:
        ```python
        from database.db_utils import init_db
        init_db() # Run this from a Python shell or a setup script within app context
        ```
5.  **Set Environment Variables (if any)**:
    -   Create a `.env` file if the application uses `python-dotenv` or set them in your shell.
    -   Example: `FLASK_APP=app.py`, `FLASK_DEBUG=1`, `FORCE_MOCK_CAMERA=1` (for development without camera).
6.  **Run the development server**:
    ```bash
    flask run
    # or
    python app.py
    ```
    The application should be accessible at `http://127.0.0.1:5000`.

## 8. Contribution Guidelines

-   **Branching**: Create a new feature branch from `main` or `develop` (if used) for your changes (e.g., `feature/new-reporting-page`, `fix/camera-bug`).
-   **Commits**: Write clear, concise commit messages.
-   **Code Style**: Follow PEP 8 for Python code. Keep code clean and well-commented where necessary.
-   **Testing**: Write unit tests for new functionality if a testing framework is in place.
-   **Pull Requests (PRs)**: 
    -   Ensure your branch is up-to-date with the target branch before submitting a PR.
    -   Provide a clear description of the changes in the PR.
    -   Link to any relevant issues.
-   **Dependencies**: If adding new dependencies, update `requirements.txt` (`pip freeze > requirements.txt`).

## 9. Troubleshooting Common Issues

-   **`ModuleNotFoundError`**: Ensure your virtual environment is active and all dependencies in `requirements.txt` are installed.
-   **Database Errors**: 
    -   Check `SQLALCHEMY_DATABASE_URI` in `config.py`.
    -   Ensure migrations are applied (`flask db upgrade`).
    -   If `instance/ssm_database.db` is corrupted, you might need to delete it and re-initialize (losing data unless backed up).
-   **Camera Not Detected (Raspberry Pi)**:
    -   Run `sudo raspi-config` and enable the camera under Interface Options.
    -   Check physical cable connections.
    -   Ensure `libcamera-apps` and `python3-picamera2` are installed (`sudo apt install python3-picamera2 libcamera-apps`).
    -   Check logs in `app.py` and `hardware/camera.py` for specific error messages.
    -   Test with `libcamera-hello` or `libcamera-jpeg -o test.jpg` from the terminal.
-   **Permission Errors**: Ensure the user running the Flask app has permissions to access hardware (e.g., camera `/dev/video0`, GPIO pins if used).
-   **Frontend Issues (CSS/JS not loading)**:
    -   Clear browser cache.
    -   Check browser's developer console for errors (e.g., 404 for static files).
    -   Verify paths in `url_for('static', ...)` calls in templates.

## 10. Further Development Ideas

-   Implement a comprehensive test suite (unit, integration).
-   Enhance security (e.g., two-factor authentication, more robust input validation).
-   Add support for more database backends.
-   Improve UI/UX with a modern JavaScript framework (React, Vue, Angular) if desired.
-   Develop a mobile application.
-   Integrate with other security systems or notification services.

--- 

This guide should provide a solid foundation for working with the SSMv3 project. Happy coding!
