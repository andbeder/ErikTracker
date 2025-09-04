"""
Erik Tracking API Blueprint
Handles Erik position tracking and mobile interface
"""

import os
import json
from flask import Blueprint, request, jsonify, current_app, render_template, send_from_directory

bp = Blueprint('erik', __name__)

@bp.route('/mobile')
def mobile_interface():
    """Mobile interface for Erik tracking"""
    # This would render a mobile-optimized template
    # For now, redirect to main interface or return simple response
    return render_template('mobile.html') if os.path.exists('templates/mobile.html') else jsonify({
        'message': 'Mobile interface not yet implemented',
        'redirect_to': '/'
    })

@bp.route('/api/erik/map-config', methods=['GET'])
def get_erik_map_config():
    """Get Erik map configuration for tracking interface"""
    try:
        yard_service = current_app.yard_service
        
        # Get active yard map info
        map_info = yard_service.get_active_map_info()
        
        # Default configuration if no active map
        default_config = {
            'map_available': False,
            'map_url': None,
            'bounds': {
                'xmin': -10.0,
                'xmax': 10.0,
                'ymin': -10.0,
                'ymax': 10.0
            },
            'grid_resolution': 0.1,
            'projection': 'xy'
        }
        
        if map_info:
            config = {
                'map_available': True,
                'map_url': '/static/active_yard_map.png',
                'map_info': map_info,
                'bounds': map_info.get('bounds', default_config['bounds']),
                'grid_resolution': map_info.get('parameters', {}).get('grid_resolution', 0.1),
                'projection': map_info.get('parameters', {}).get('projection', 'xy')
            }
        else:
            config = default_config
        
        return jsonify(config)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/erik/live-position', methods=['GET'])
def get_erik_live_position():
    """Get Erik's current live position from tracking system"""
    try:
        # Get recent detection matches from MQTT
        mqtt_service = current_app.mqtt_service
        recent_matches = mqtt_service.get_detection_matches()
        
        # Find most recent position with high confidence
        current_position = None
        if recent_matches:
            for match in recent_matches:
                confidence = match.get('confidence', 0)
                if confidence > 0.7:  # High confidence threshold
                    current_position = {
                        'x': match.get('x', 0),
                        'y': match.get('y', 0),
                        'confidence': confidence,
                        'camera': match.get('camera', 'unknown'),
                        'timestamp': match.get('received_time'),
                        'detection_id': match.get('detection_id')
                    }
                    break
        
        response = {
            'position_available': current_position is not None,
            'current_position': current_position,
            'total_recent_detections': len(recent_matches),
            'last_update': recent_matches[0].get('received_time') if recent_matches else None
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/erik/position-history', methods=['GET'])
def get_erik_position_history():
    """Get Erik's position history over time"""
    try:
        # Get parameters
        limit = request.args.get('limit', 50, type=int)
        min_confidence = request.args.get('min_confidence', 0.5, type=float)
        
        mqtt_service = current_app.mqtt_service
        all_matches = mqtt_service.get_detection_matches()
        
        # Filter by confidence and limit
        filtered_positions = []
        for match in all_matches:
            if match.get('confidence', 0) >= min_confidence:
                filtered_positions.append({
                    'x': match.get('x', 0),
                    'y': match.get('y', 0),
                    'confidence': match.get('confidence', 0),
                    'camera': match.get('camera', 'unknown'),
                    'timestamp': match.get('received_time'),
                    'detection_id': match.get('detection_id')
                })
            
            if len(filtered_positions) >= limit:
                break
        
        return jsonify({
            'positions': filtered_positions,
            'total_positions': len(filtered_positions),
            'filters': {
                'limit': limit,
                'min_confidence': min_confidence
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/erik/detection-stats', methods=['GET'])
def get_erik_detection_stats():
    """Get Erik detection statistics"""
    try:
        mqtt_service = current_app.mqtt_service
        all_matches = mqtt_service.get_detection_matches()
        
        if not all_matches:
            return jsonify({
                'total_detections': 0,
                'stats': {}
            })
        
        # Calculate statistics
        total_detections = len(all_matches)
        
        # Count by camera
        camera_counts = {}
        confidence_levels = {'high': 0, 'medium': 0, 'low': 0}
        
        for match in all_matches:
            camera = match.get('camera', 'unknown')
            camera_counts[camera] = camera_counts.get(camera, 0) + 1
            
            confidence = match.get('confidence', 0)
            if confidence >= 0.8:
                confidence_levels['high'] += 1
            elif confidence >= 0.6:
                confidence_levels['medium'] += 1
            else:
                confidence_levels['low'] += 1
        
        # Get recent activity (last hour if timestamps available)
        recent_count = 0
        if all_matches and 'received_time' in all_matches[0]:
            # This would normally check timestamps
            # For now, just count recent matches
            recent_count = min(10, total_detections)
        
        stats = {
            'total_detections': total_detections,
            'recent_detections': recent_count,
            'camera_breakdown': camera_counts,
            'confidence_levels': confidence_levels,
            'most_active_camera': max(camera_counts.items(), key=lambda x: x[1])[0] if camera_counts else None
        }
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/erik/tracking-status', methods=['GET'])
def get_erik_tracking_status():
    """Get overall Erik tracking system status"""
    try:
        mqtt_service = current_app.mqtt_service
        yard_service = current_app.yard_service
        frigate_service = current_app.frigate_service
        
        # Check MQTT connection
        mqtt_status = 'connected' if mqtt_service.is_running() else 'disconnected'
        
        # Check active yard map
        map_available = yard_service.get_active_map_info() is not None
        
        # Check configured cameras
        camera_names = frigate_service.get_camera_names()
        
        # Get recent detection activity
        recent_matches = mqtt_service.get_detection_matches()[:5]
        last_detection = recent_matches[0] if recent_matches else None
        
        status = {
            'system_status': 'active' if mqtt_status == 'connected' else 'inactive',
            'mqtt_connection': mqtt_status,
            'yard_map_available': map_available,
            'configured_cameras': len(camera_names),
            'camera_list': camera_names,
            'recent_activity': {
                'last_detection': last_detection,
                'recent_detections_count': len(recent_matches)
            },
            'timestamp': '2024-01-01T00:00:00Z'  # Would use actual timestamp
        }
        
        return jsonify(status)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/erik/camera-zones', methods=['GET'])
def get_erik_camera_zones():
    """Get camera detection zones for Erik tracking"""
    try:
        frigate_service = current_app.frigate_service
        camera_names = frigate_service.get_camera_names()
        
        zones = []
        for camera_name in camera_names:
            camera_config = frigate_service.get_camera_config(camera_name)
            if camera_config and 'zones' in camera_config:
                for zone_name, zone_config in camera_config['zones'].items():
                    zones.append({
                        'camera': camera_name,
                        'zone_name': zone_name,
                        'coordinates': zone_config.get('coordinates', []),
                        'objects': zone_config.get('objects', []),
                        'filters': zone_config.get('filters', {})
                    })
        
        return jsonify({
            'zones': zones,
            'total_zones': len(zones)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/settings/global', methods=['GET'])
def get_global_settings():
    """Get global application settings"""
    try:
        # Load settings from file if it exists
        settings_path = current_app.config.get('GLOBAL_SETTINGS_PATH', './global_settings.json')
        
        default_settings = {
            'external_ip': current_app.config.get('EXTERNAL_IP', '24.147.52.91'),
            'upload_folder': current_app.config.get('UPLOAD_FOLDER'),
            'mesh_folder': current_app.config.get('MESH_FOLDER'),
            'mqtt_host': current_app.config.get('MQTT_HOST', 'localhost'),
            'mqtt_port': current_app.config.get('MQTT_PORT', 1883)
        }
        
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                saved_settings = json.load(f)
                default_settings.update(saved_settings)
        
        return jsonify(default_settings)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/settings/global', methods=['POST'])
def update_global_settings():
    """Update global application settings"""
    try:
        settings_path = current_app.config.get('GLOBAL_SETTINGS_PATH', './global_settings.json')
        new_settings = request.json
        
        if not new_settings:
            return jsonify({'error': 'No settings provided'}), 400
        
        # Save settings to file
        with open(settings_path, 'w') as f:
            json.dump(new_settings, f, indent=2)
        
        return jsonify({
            'status': 'success',
            'message': 'Settings updated',
            'settings': new_settings
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/static/active_yard_map.png')
def serve_active_yard_map():
    """Serve the active yard map image"""
    try:
        yard_service = current_app.yard_service
        
        if os.path.exists(yard_service.active_yard_map_path):
            return send_from_directory(
                os.path.dirname(yard_service.active_yard_map_path),
                os.path.basename(yard_service.active_yard_map_path),
                mimetype='image/png'
            )
        else:
            return jsonify({'error': 'Active yard map not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500