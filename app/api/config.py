"""
Configuration API endpoints for client-side configuration management
"""
from flask import Blueprint, jsonify, current_app
from app.config import config as config_dict
import os

bp = Blueprint('config', __name__, url_prefix='/api/config')

@bp.route('/', methods=['GET'])
@bp.route('/client', methods=['GET'])
def get_client_config():
    """Return client-side configuration values"""
    try:
        return jsonify({
            'colmap': {
                'projects_dir': current_app.config['COLMAP_PROJECTS_DIR'],
                'supported_video_formats': list(current_app.config['VIDEO_EXTENSIONS']),
                'max_video_size': current_app.config['MAX_VIDEO_SIZE'],
                'max_file_size': current_app.config['MAX_FILE_SIZE']
            },
            'images': {
                'upload_folder': current_app.config['UPLOAD_FOLDER'],
                'supported_formats': list(current_app.config['ALLOWED_EXTENSIONS']),
                'max_file_size': current_app.config['MAX_FILE_SIZE'],
                'thumbnail_size': current_app.config['THUMBNAIL_SIZE']
            },
            'mesh': {
                'mesh_folder': current_app.config['MESH_FOLDER'],
                'supported_formats': list(current_app.config['MESH_EXTENSIONS']),
                'max_file_size': current_app.config['MAX_FILE_SIZE']
            },
            'yard_map': {
                'map_path': current_app.config['YARD_MAP_PATH'],
                'active_map_path': current_app.config['ACTIVE_YARD_MAP_PATH'],
                'active_map_json': current_app.config['ACTIVE_YARD_MAP_JSON']
            },
            'network': {
                'external_ip': current_app.config['EXTERNAL_IP'],
                'mqtt_host': current_app.config['MQTT_HOST'],
                'mqtt_port': current_app.config['MQTT_PORT']
            },
            'frigate': {
                'config_path': current_app.config['FRIGATE_CONFIG_PATH'],
                'backup_path': current_app.config['FRIGATE_CONFIG_BACKUP_PATH']
            },
            'ui': {
                'app_title': 'Erik Image Manager',
                'app_description': 'Manage reference images and view live detections from the Hybrid Erik Tracker',
                'auto_refresh_interval': 30000,  # 30 seconds
                'erik_tracking_interval': 2000,  # 2 seconds
                'match_refresh_interval': 30000  # 30 seconds
            },
            'features': {
                'live_mapping': True,
                'colmap_reconstruction': True,
                'frigate_integration': True,
                'erik_tracking': True,
                'camera_management': True,
                'yard_mapping': True
            }
        })
    except Exception as e:
        return jsonify({'error': f'Failed to load configuration: {str(e)}'}), 500

@bp.route('/environment', methods=['GET'])
def get_environment_info():
    """Return environment information for debugging"""
    try:
        return jsonify({
            'environment': os.environ.get('FLASK_ENV', 'development'),
            'debug': current_app.config.get('DEBUG', False),
            'config_name': getattr(current_app, 'config_name', 'unknown'),
            'upload_folder_exists': os.path.exists(current_app.config['UPLOAD_FOLDER']),
            'mesh_folder_exists': os.path.exists(current_app.config['MESH_FOLDER']),
            'frigate_config_exists': os.path.exists(current_app.config['FRIGATE_CONFIG_PATH']),
            'version': '2.0.0-phase3'
        })
    except Exception as e:
        return jsonify({'error': f'Failed to get environment info: {str(e)}'}), 500

@bp.route('/paths', methods=['GET'])
def get_paths():
    """Return all configured paths for client use"""
    try:
        return jsonify({
            'upload_folder': current_app.config['UPLOAD_FOLDER'],
            'mesh_folder': current_app.config['MESH_FOLDER'],
            'video_folder': current_app.config['VIDEO_FOLDER'],
            'yard_map_path': current_app.config['YARD_MAP_PATH'],
            'active_yard_map_path': current_app.config['ACTIVE_YARD_MAP_PATH'],
            'active_yard_map_json': current_app.config['ACTIVE_YARD_MAP_JSON'],
            'frigate_config_path': current_app.config['FRIGATE_CONFIG_PATH'],
            'colmap_projects_dir': current_app.config['COLMAP_PROJECTS_DIR'],
            'global_settings_path': current_app.config['GLOBAL_SETTINGS_PATH']
        })
    except Exception as e:
        return jsonify({'error': f'Failed to get paths: {str(e)}'}), 500

@bp.route('/limits', methods=['GET'])  
def get_limits():
    """Return file size limits and constraints"""
    try:
        return jsonify({
            'max_file_size': current_app.config['MAX_FILE_SIZE'],
            'max_video_size': current_app.config['MAX_VIDEO_SIZE'],
            'max_content_length': current_app.config['MAX_CONTENT_LENGTH'],
            'thumbnail_size': current_app.config['THUMBNAIL_SIZE'],
            'match_thumbnail_size': current_app.config['MATCH_THUMBNAIL_SIZE'],
            'allowed_extensions': {
                'images': list(current_app.config['ALLOWED_EXTENSIONS']),
                'meshes': list(current_app.config['MESH_EXTENSIONS']),
                'videos': list(current_app.config['VIDEO_EXTENSIONS'])
            }
        })
    except Exception as e:
        return jsonify({'error': f'Failed to get limits: {str(e)}'}), 500