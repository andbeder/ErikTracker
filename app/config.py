"""
Configuration management for Erik Image Manager
"""
import os
from pathlib import Path

class Config:
    """Base configuration"""
    # Application settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'erik-image-manager-secret-key-change-in-production')
    
    # File upload settings
    UPLOAD_FOLDER = os.environ.get('ERIK_IMAGES_FOLDER', '/app/erik_images')
    MESH_FOLDER = os.environ.get('MESH_FOLDER', '/home/andrew/nvr/meshes')
    VIDEO_FOLDER = os.environ.get('VIDEO_FOLDER', './uploaded_videos')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp'}
    MESH_EXTENSIONS = {'ply', 'obj', 'stl'}
    VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv'}
    MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB for images and meshes
    MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB for videos
    MAX_BYO_MODEL_SIZE = 2 * 1024 * 1024 * 1024  # 2GB for BYO model files
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2GB Flask upload limit
    THUMBNAIL_SIZE = (200, 200)
    MATCH_THUMBNAIL_SIZE = (150, 150)
    
    # Network settings
    EXTERNAL_IP = os.environ.get('EXTERNAL_IP', '24.147.52.91')  # Cable modem external IP
    
    # Frigate Configuration
    FRIGATE_CONFIG_PATH = os.environ.get('FRIGATE_CONFIG_PATH', '/home/andrew/nvr/frigate/config/config.yaml')
    FRIGATE_CONFIG_BACKUP_PATH = os.environ.get('FRIGATE_CONFIG_BACKUP_PATH', '/home/andrew/nvr/frigate/config/backup_config.yaml')
    
    # MQTT Configuration
    MQTT_HOST = os.environ.get('MQTT_HOST', 'localhost')
    MQTT_PORT = int(os.environ.get('MQTT_PORT', '1883'))
    
    # COLMAP settings
    COLMAP_PROJECTS_DIR = os.environ.get('COLMAP_PROJECTS_DIR', '/home/andrew/nvr/reconstruction')
    COLMAP_DOCKER_IMAGE = os.environ.get('COLMAP_DOCKER_IMAGE', 'colmap/colmap:latest')
    
    # Yard map settings
    YARD_MAP_PATH = os.environ.get('YARD_MAP_PATH', './yard_map.png')
    ACTIVE_YARD_MAP_PATH = os.environ.get('ACTIVE_YARD_MAP_PATH', './active_yard_map.png')
    ACTIVE_YARD_MAP_JSON = os.environ.get('ACTIVE_YARD_MAP_JSON', './active_yard_map.json')
    
    # Global settings
    GLOBAL_SETTINGS_PATH = os.environ.get('GLOBAL_SETTINGS_PATH', './global_settings.json')
    
    @staticmethod
    def init_app(app):
        """Initialize application with this config"""
        pass

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    
    # Override paths for development if needed
    UPLOAD_FOLDER = os.environ.get('ERIK_IMAGES_FOLDER', './erik_images')
    MESH_FOLDER = os.environ.get('MESH_FOLDER', './meshes')
    
    @staticmethod
    def init_app(app):
        """Initialize application for development"""
        Config.init_app(app)
        # Development-specific initialization
        import logging
        logging.basicConfig(level=logging.DEBUG)

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    
    @staticmethod
    def init_app(app):
        """Initialize application for production"""
        Config.init_app(app)
        # Production-specific initialization
        import logging
        logging.basicConfig(level=logging.INFO)

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    
    # Use temporary directories for testing
    UPLOAD_FOLDER = '/tmp/test_erik_images'
    MESH_FOLDER = '/tmp/test_meshes'
    
    @staticmethod
    def init_app(app):
        """Initialize application for testing"""
        Config.init_app(app)
        # Create temporary directories for testing
        Path('/tmp/test_erik_images').mkdir(parents=True, exist_ok=True)
        Path('/tmp/test_meshes').mkdir(parents=True, exist_ok=True)

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}