"""
Frigate Configuration API Blueprint
Handles Frigate camera configuration and management
"""

import os
import json
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import logging
from app.services.frigate_service import FrigateService

logger = logging.getLogger(__name__)
bp = Blueprint('frigate', __name__, url_prefix='/frigate')

@bp.route('/config')
def get_config():
    """Get Frigate configuration"""
    frigate_service = current_app.frigate_service
    config = frigate_service.load_config()
    
    if config:
        return jsonify(config)
    else:
        return jsonify({'error': 'Could not load configuration'}), 500

@bp.route('/config/camera/<camera_name>')
def get_camera_config(camera_name):
    """Get configuration for a specific camera"""
    frigate_service = current_app.frigate_service
    camera_config = frigate_service.get_camera_config(camera_name)
    
    if camera_config:
        # Add web URL for camera access
        web_url = frigate_service.extract_camera_ip(camera_config)
        
        return jsonify({
            'camera_name': camera_name,
            'config': camera_config,
            'web_url': web_url
        })
    else:
        return jsonify({'error': f'Camera {camera_name} not found'}), 404

@bp.route('/config/camera/<camera_name>', methods=['POST'])
def update_camera_config(camera_name):
    """Update configuration for a specific camera"""
    try:
        frigate_service = current_app.frigate_service
        camera_data = request.json
        
        if not camera_data:
            return jsonify({'error': 'No configuration data provided'}), 400
        
        # Validate camera configuration
        is_valid, message = frigate_service.validate_camera_config(camera_data)
        if not is_valid:
            return jsonify({'error': f'Invalid configuration: {message}'}), 400
        
        # Update camera configuration
        if frigate_service.update_camera_config(camera_name, camera_data):
            return jsonify({
                'status': 'success',
                'message': f'Updated configuration for {camera_name}'
            })
        else:
            return jsonify({'error': 'Failed to save configuration'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config/global', methods=['POST'])
def update_global_config():
    """Update global Frigate configuration"""
    try:
        frigate_service = current_app.frigate_service
        config_data = request.json
        
        if not config_data:
            return jsonify({'error': 'No configuration data provided'}), 400
        
        # Save the entire configuration
        if frigate_service.save_config(config_data):
            return jsonify({
                'status': 'success',
                'message': 'Global configuration updated'
            })
        else:
            return jsonify({'error': 'Failed to save configuration'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config/backup', methods=['POST'])
def backup_config():
    """Create backup of current Frigate configuration"""
    try:
        frigate_service = current_app.frigate_service
        config = frigate_service.load_config()
        
        if config:
            # The save_config method already creates backups
            if frigate_service.save_config(config):
                return jsonify({
                    'status': 'success',
                    'message': 'Configuration backup created'
                })
            else:
                return jsonify({'error': 'Failed to create backup'}), 500
        else:
            return jsonify({'error': 'No configuration to backup'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config/backup/restore')
def restore_backup():
    """Restore configuration from backup"""
    try:
        frigate_service = current_app.frigate_service
        backup_path = frigate_service.backup_path
        
        if os.path.exists(backup_path):
            import yaml
            with open(backup_path, 'r') as f:
                backup_config = yaml.safe_load(f)
            
            return jsonify({
                'status': 'available',
                'backup_config': backup_config,
                'backup_path': backup_path
            })
        else:
            return jsonify({
                'status': 'no_backup',
                'message': 'No backup file found'
            }), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config/camera', methods=['POST'])
def add_camera():
    """Add a new camera to the configuration"""
    try:
        frigate_service = current_app.frigate_service
        data = request.json
        
        camera_name = data.get('camera_name')
        camera_config = data.get('camera_config')
        
        if not camera_name or not camera_config:
            return jsonify({'error': 'Camera name and configuration required'}), 400
        
        # Validate camera configuration
        is_valid, message = frigate_service.validate_camera_config(camera_config)
        if not is_valid:
            return jsonify({'error': f'Invalid configuration: {message}'}), 400
        
        # Check if camera already exists
        if frigate_service.get_camera_config(camera_name):
            return jsonify({'error': f'Camera {camera_name} already exists'}), 409
        
        # Add new camera
        if frigate_service.update_camera_config(camera_name, camera_config):
            # Try to auto-assign port for camera web interface
            camera_ip = None
            if 'ffmpeg' in camera_config and 'inputs' in camera_config['ffmpeg']:
                for input_stream in camera_config['ffmpeg']['inputs']:
                    if 'path' in input_stream:
                        import re
                        ip_match = re.search(r'@([0-9.]+):', input_stream['path'])
                        if ip_match:
                            camera_ip = ip_match.group(1)
                            break
            
            response = {
                'status': 'success',
                'message': f'Added camera {camera_name}',
                'camera_name': camera_name
            }
            
            if camera_ip:
                assigned_port = frigate_service.auto_assign_camera_port(camera_ip)
                if assigned_port:
                    response['web_port'] = assigned_port
                    response['web_url'] = f"http://localhost:{assigned_port}"
            
            return jsonify(response)
        else:
            return jsonify({'error': 'Failed to add camera'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config/camera/<camera_name>', methods=['DELETE'])
def delete_camera(camera_name):
    """Delete a camera from the configuration"""
    try:
        frigate_service = current_app.frigate_service
        
        # Check if camera exists
        if not frigate_service.get_camera_config(camera_name):
            return jsonify({'error': f'Camera {camera_name} not found'}), 404
        
        # Delete camera
        if frigate_service.delete_camera_config(camera_name):
            return jsonify({
                'status': 'success',
                'message': f'Deleted camera {camera_name}'
            })
        else:
            return jsonify({'error': 'Failed to delete camera'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/cameras')
def list_cameras():
    """List all configured cameras"""
    frigate_service = current_app.frigate_service
    camera_names = frigate_service.get_camera_names()
    
    cameras = []
    for name in camera_names:
        config = frigate_service.get_camera_config(name)
        if config:
            web_url = frigate_service.extract_camera_ip(config)
            cameras.append({
                'name': name,
                'web_url': web_url,
                'config': config
            })
    
    return jsonify({
        'cameras': cameras,
        'total_count': len(cameras)
    })

@bp.route('/restart', methods=['POST'])
def restart_frigate():
    """Restart Frigate container"""
    frigate_service = current_app.frigate_service
    
    if frigate_service.restart_frigate():
        return jsonify({
            'status': 'success',
            'message': 'Frigate restarted successfully'
        })
    else:
        return jsonify({'error': 'Failed to restart Frigate'}), 500

@bp.route('/status')
def get_status():
    """Get Frigate service status"""
    try:
        # Check if Frigate container is running
        import subprocess
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=frigate', '--format', '{{.Status}}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout.strip():
            status = 'running'
            status_detail = result.stdout.strip()
        else:
            status = 'not_running'
            status_detail = 'Container not found or stopped'
        
        return jsonify({
            'status': status,
            'detail': status_detail,
            'timestamp': '2024-01-01T00:00:00Z'  # Would use actual timestamp
        })
        
    except Exception as e:
        return jsonify({
            'status': 'unknown',
            'error': str(e)
        })

@bp.route('/logs')
def get_logs():
    """Get Frigate container logs"""
    try:
        import subprocess
        result = subprocess.run(
            ['docker', 'logs', '--tail', '100', 'frigate'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return jsonify({
                'status': 'success',
                'logs': result.stdout.split('\n')
            })
        else:
            return jsonify({'error': 'Failed to get logs'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/camera-config/<camera_name>')
def get_camera_detection_config(camera_name):
    """Get detection configuration for a specific camera"""
    try:
        frigate_service = FrigateService()
        config = frigate_service.get_config()
        
        if not config or 'cameras' not in config:
            return jsonify({'error': 'No Frigate configuration found'}), 404
        
        if camera_name not in config['cameras']:
            return jsonify({'error': f'Camera {camera_name} not found'}), 404
        
        camera_config = config['cameras'][camera_name]
        
        # Return structured detection settings
        return jsonify({
            'camera_name': camera_name,
            'detect': camera_config.get('detect', {}),
            'objects': camera_config.get('objects', {}),
            'motion': camera_config.get('motion', {}),
            'zones': camera_config.get('zones', {}),
            'record': camera_config.get('record', {}),
            'snapshots': camera_config.get('snapshots', {}),
            'ffmpeg': camera_config.get('ffmpeg', {}),
            'live': camera_config.get('live', {}),
            'ui': camera_config.get('ui', {}),
            'mqtt': camera_config.get('mqtt', {}),
            'birdseye': camera_config.get('birdseye', {}),
            # Custom Erik detection settings (if any)
            'erik_detection': camera_config.get('erik_detection', {
                'enabled': False,
                'reference_images': 5,
                'confidence_threshold': 0.8,
                'tracking_modes': ['face', 'body'],
                'update_interval': 3
            })
        })
        
    except Exception as e:
        logger.error(f"Error getting camera config for {camera_name}: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/camera-config/<camera_name>', methods=['PUT'])
def update_camera_detection_config(camera_name):
    """Update detection configuration for a specific camera"""
    try:
        new_config = request.get_json()
        if not new_config:
            return jsonify({'error': 'No configuration provided'}), 400
        
        frigate_service = FrigateService()
        config = frigate_service.get_config()
        
        if not config or 'cameras' not in config:
            return jsonify({'error': 'No Frigate configuration found'}), 404
        
        if camera_name not in config['cameras']:
            return jsonify({'error': f'Camera {camera_name} not found'}), 404
        
        # Update camera configuration
        camera_config = config['cameras'][camera_name]
        
        # Update detection settings
        if 'detect' in new_config:
            camera_config['detect'] = {
                **camera_config.get('detect', {}),
                **new_config['detect']
            }
        
        # Update objects and filters
        if 'objects' in new_config:
            camera_config['objects'] = {
                **camera_config.get('objects', {}),
                **new_config['objects']
            }
        
        # Update motion settings
        if 'motion' in new_config:
            camera_config['motion'] = {
                **camera_config.get('motion', {}),
                **new_config['motion']
            }
        
        # Update zones
        if 'zones' in new_config:
            camera_config['zones'] = new_config['zones']
        
        # Update recording settings
        if 'record' in new_config:
            camera_config['record'] = {
                **camera_config.get('record', {}),
                **new_config['record']
            }
        
        # Update snapshot settings
        if 'snapshots' in new_config:
            camera_config['snapshots'] = {
                **camera_config.get('snapshots', {}),
                **new_config['snapshots']
            }
        
        # Update Erik detection settings (custom)
        if 'erik_detection' in new_config:
            camera_config['erik_detection'] = new_config['erik_detection']
        
        # Save updated configuration
        success = frigate_service.update_config(config)
        
        if success:
            # Restart Frigate to apply changes (optional - can be done manually)
            restart_requested = new_config.get('restart_frigate', False)
            if restart_requested:
                try:
                    frigate_service.restart_frigate()
                except Exception as restart_error:
                    logger.warning(f"Config saved but failed to restart Frigate: {restart_error}")
            
            return jsonify({
                'status': 'success',
                'message': f'Camera {camera_name} configuration updated',
                'restart_required': not restart_requested
            })
        else:
            return jsonify({'error': 'Failed to save configuration'}), 500
        
    except Exception as e:
        logger.error(f"Error updating camera config for {camera_name}: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/detection-presets')
def get_detection_presets():
    """Get available detection presets"""
    presets = {
        'high-security': {
            'name': 'High Security',
            'description': 'Maximum detection accuracy with high resource usage',
            'detect': {
                'enabled': True,
                'fps': 15,
                'width': 1280,
                'height': 720,
                'stationary': {'interval': 10, 'threshold': 25},
                'max_disappeared': 25
            },
            'motion': {
                'threshold': 30,
                'contour_area': 1000,
                'delta_alpha': 0.2,
                'frame_alpha': 0.2,
                'improve_contrast': True
            },
            'objects': {
                'track': ['person', 'car', 'dog', 'cat', 'bicycle', 'motorcycle'],
                'filters': {
                    'person': {
                        'min_area': 2000,
                        'max_area': 200000,
                        'threshold': 0.8,
                        'min_score': 0.6
                    }
                }
            }
        },
        'balanced': {
            'name': 'Balanced',
            'description': 'Good balance of detection accuracy and performance',
            'detect': {
                'enabled': True,
                'fps': 10,
                'width': 640,
                'height': 480,
                'stationary': {'interval': 30, 'threshold': 50},
                'max_disappeared': 15
            },
            'motion': {
                'threshold': 50,
                'contour_area': 2000,
                'delta_alpha': 0.2,
                'frame_alpha': 0.2,
                'improve_contrast': False
            },
            'objects': {
                'track': ['person', 'car'],
                'filters': {
                    'person': {
                        'min_area': 3000,
                        'max_area': 100000,
                        'threshold': 0.7,
                        'min_score': 0.5
                    }
                }
            }
        },
        'performance': {
            'name': 'High Performance',
            'description': 'Optimized for low resource usage and speed',
            'detect': {
                'enabled': True,
                'fps': 5,
                'width': 320,
                'height': 240,
                'stationary': {'interval': 60, 'threshold': 100},
                'max_disappeared': 10
            },
            'motion': {
                'threshold': 70,
                'contour_area': 3000,
                'delta_alpha': 0.3,
                'frame_alpha': 0.3,
                'improve_contrast': False
            },
            'objects': {
                'track': ['person'],
                'filters': {
                    'person': {
                        'min_area': 5000,
                        'max_area': 50000,
                        'threshold': 0.6,
                        'min_score': 0.4
                    }
                }
            }
        },
        'erik-tracking': {
            'name': 'Erik Tracking',
            'description': 'Optimized for tracking a specific child (Erik)',
            'detect': {
                'enabled': True,
                'fps': 12,
                'width': 640,
                'height': 480,
                'stationary': {'interval': 20, 'threshold': 40},
                'max_disappeared': 20
            },
            'motion': {
                'threshold': 40,
                'contour_area': 1500,
                'delta_alpha': 0.2,
                'frame_alpha': 0.2,
                'improve_contrast': True
            },
            'objects': {
                'track': ['person'],
                'filters': {
                    'person': {
                        'min_area': 2000,
                        'max_area': 100000,
                        'threshold': 0.75,
                        'min_score': 0.55
                    }
                }
            },
            'erik_detection': {
                'enabled': True,
                'reference_images': 5,
                'confidence_threshold': 0.8,
                'tracking_modes': ['face', 'body', 'clothing'],
                'update_interval': 2
            }
        }
    }
    
    return jsonify(presets)


@bp.route('/apply-preset/<camera_name>/<preset_name>', methods=['POST'])
def apply_detection_preset(camera_name, preset_name):
    """Apply a detection preset to a camera"""
    try:
        # Get preset configuration
        presets_response = get_detection_presets()
        presets = presets_response.get_json()
        
        if preset_name not in presets:
            return jsonify({'error': f'Preset {preset_name} not found'}), 404
        
        preset_config = presets[preset_name]
        
        # Remove metadata fields
        config_to_apply = {k: v for k, v in preset_config.items() 
                          if k not in ['name', 'description']}
        
        # Apply the preset configuration
        request.json = config_to_apply
        return update_camera_detection_config(camera_name)
        
    except Exception as e:
        logger.error(f"Error applying preset {preset_name} to {camera_name}: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/validate-config', methods=['POST'])
def validate_config():
    """Validate Frigate configuration before applying"""
    try:
        config_data = request.get_json()
        if not config_data:
            return jsonify({'error': 'No configuration provided'}), 400
        
        validation_errors = []
        warnings = []
        
        # Validate detection settings
        if 'detect' in config_data:
            detect_config = config_data['detect']
            
            # Validate FPS
            fps = detect_config.get('fps', 10)
            if fps < 1 or fps > 30:
                validation_errors.append('Detection FPS must be between 1 and 30')
            elif fps > 15:
                warnings.append('High FPS may increase resource usage significantly')
            
            # Validate resolution
            width = detect_config.get('width', 640)
            height = detect_config.get('height', 480)
            if width < 320 or width > 1920:
                validation_errors.append('Detection width must be between 320 and 1920')
            if height < 240 or height > 1080:
                validation_errors.append('Detection height must be between 240 and 1080')
            
            if width > 1280 or height > 720:
                warnings.append('High resolution may significantly impact performance')
        
        # Validate object filters
        if 'objects' in config_data and 'filters' in config_data['objects']:
            for obj_type, filters in config_data['objects']['filters'].items():
                min_area = filters.get('min_area', 0)
                max_area = filters.get('max_area', 1000000)
                
                if min_area >= max_area:
                    validation_errors.append(f'{obj_type}: min_area must be less than max_area')
                
                if min_area < 500:
                    warnings.append(f'{obj_type}: Very low min_area may cause false positives')
        
        # Validate zones
        if 'zones' in config_data:
            for zone_name, zone_config in config_data['zones'].items():
                coordinates = zone_config.get('coordinates', [])
                if len(coordinates) < 3:
                    validation_errors.append(f'Zone {zone_name}: Must have at least 3 coordinates')
        
        return jsonify({
            'valid': len(validation_errors) == 0,
            'errors': validation_errors,
            'warnings': warnings
        })
        
    except Exception as e:
        logger.error(f"Error validating config: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/test-detection/<camera_name>')
def test_detection(camera_name):
    """Test current detection settings for a camera"""
    try:
        # This would integrate with the actual Frigate detection pipeline
        # For now, return simulated test results
        
        test_results = {
            'camera_name': camera_name,
            'test_timestamp': datetime.now().isoformat(),
            'detection_active': True,
            'current_objects': [
                {
                    'type': 'person',
                    'confidence': 0.87,
                    'area': 15420,
                    'bbox': [245, 123, 89, 156],
                    'zone': 'backyard'
                }
            ],
            'motion_detected': True,
            'motion_areas': [
                {
                    'area': 8934,
                    'bbox': [200, 100, 120, 180]
                }
            ],
            'performance_metrics': {
                'detection_fps': 9.2,
                'inference_time': 45.3,
                'cpu_usage': 23.5,
                'memory_usage': 156.7
            }
        }
        
        return jsonify(test_results)
        
    except Exception as e:
        logger.error(f"Error testing detection for {camera_name}: {e}")
        return jsonify({'error': str(e)}), 500