"""
Frigate Configuration API Blueprint
Handles Frigate camera configuration and management
"""

import os
import json
from flask import Blueprint, request, jsonify, current_app

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