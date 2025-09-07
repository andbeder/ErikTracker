"""
Flask Application Factory for Erik Image Manager
"""
import os
import logging
from flask import Flask
from pathlib import Path

logger = logging.getLogger(__name__)

def create_app(config_name='development'):
    """Create and configure the Flask application"""
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    
    # Load configuration
    from app.config import config
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Set secret key (should be in config in production)
    app.secret_key = app.config.get('SECRET_KEY', 'erik-image-manager-secret-key-change-in-production')
    
    # Ensure required directories exist
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
    Path(app.config['MESH_FOLDER']).mkdir(parents=True, exist_ok=True)
    
    # Initialize services (will be moved to services module later)
    # For now, we'll initialize them here to maintain compatibility
    init_services(app)
    
    # Register blueprints
    register_blueprints(app)
    
    return app

def init_services(app):
    """Initialize services with the Flask app"""
    with app.app_context():
        # Initialize services with app configuration
        from app.services.mqtt_service import MQTTService
        from app.services.colmap_service import COLMAPService
        from app.services.frigate_service import FrigateService
        from app.services.yard_service import YardMappingService
        from app.services.camera_service import CameraService
        from app.services.file_service import FileService
        
        # Store service instances in app context for access by routes
        app.mqtt_service = MQTTService(app.config)
        app.colmap_service = COLMAPService(app.config)
        app.frigate_service = FrigateService(app.config)
        app.yard_service = YardMappingService(app.config)
        app.camera_service = CameraService(app.config)
        app.file_service = FileService(app.config)
        
        # Start MQTT listener
        app.mqtt_service.start_listener()

def register_blueprints(app):
    """Register Flask blueprints"""
    # Import and register all API blueprints
    from app.api.images import bp as images_bp
    from app.api.colmap import bp as colmap_bp
    from app.api.orient import bp as orient_bp
    from app.api.frigate import bp as frigate_bp
    from app.api.yard_map import bp as yard_map_bp
    from app.api.cameras import bp as cameras_bp
    from app.api.erik import bp as erik_bp
    from app.api.config import bp as config_bp
    from app.api.mqtt_settings import bp as mqtt_bp
    from app.api.pose import bp as pose_bp
    
    app.register_blueprint(images_bp)
    app.register_blueprint(colmap_bp)
    app.register_blueprint(orient_bp)
    app.register_blueprint(frigate_bp)
    app.register_blueprint(yard_map_bp)
    app.register_blueprint(cameras_bp)
    app.register_blueprint(erik_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(mqtt_bp, url_prefix='/api/mqtt')
    app.register_blueprint(pose_bp)