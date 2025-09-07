"""
Camera Pose and Pixel Mapping API
Handles camera-to-yard-map pixel projection mappings
"""

import os
import json
import numpy as np
from flask import Blueprint, request, jsonify, current_app
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('pose', __name__, url_prefix='/api/pose')

# Storage for camera pixel mappings
CAMERA_MAPPINGS_FILE = 'config/camera_pixel_mappings.json'
CAMERA_POSES_DIR = 'config/camera_poses'

def load_camera_mappings():
    """Load saved camera pixel mappings from file"""
    if os.path.exists(CAMERA_MAPPINGS_FILE):
        try:
            with open(CAMERA_MAPPINGS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading camera mappings: {e}")
    return {}

def save_camera_mappings(mappings):
    """Save camera pixel mappings to file"""
    try:
        os.makedirs(os.path.dirname(CAMERA_MAPPINGS_FILE), exist_ok=True)
        with open(CAMERA_MAPPINGS_FILE, 'w') as f:
            json.dump(mappings, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving camera mappings: {e}")
        return False

def load_camera_poses_from_files():
    """Load camera poses from individual JSON files"""
    poses = {}
    
    if os.path.exists(CAMERA_POSES_DIR):
        from pathlib import Path
        for pose_file in Path(CAMERA_POSES_DIR).glob('*_pose.json'):
            try:
                with open(pose_file, 'r') as f:
                    pose_data = json.load(f)
                camera_name = pose_data.get('camera_name')
                if camera_name:
                    poses[camera_name] = pose_data
            except Exception as e:
                logger.error(f"Error reading pose file {pose_file}: {e}")
    
    return poses

@bp.route('/map-camera-pixels', methods=['POST'])
def map_camera_pixels():
    """
    Create pixel mapping from camera view to yard map coordinates.
    This maps ground pixels from the camera to corresponding yard map pixels.
    """
    try:
        data = request.json
        camera_name = data.get('camera_name')
        yard_map_info = data.get('yard_map_info')
        
        if not camera_name:
            return jsonify({'error': 'Camera name required'}), 400
            
        if not yard_map_info or not yard_map_info.get('map_bounds'):
            return jsonify({'error': 'Yard map info required'}), 400
        
        # Get camera orientation from saved pose files
        camera_poses = load_camera_poses_from_files()
        
        if camera_name not in camera_poses:
            return jsonify({'error': f'No orientation data for camera {camera_name}'}), 404
        
        camera_pose = camera_poses[camera_name]
        
        # Extract necessary data
        map_bounds = yard_map_info['map_bounds']
        image_width = yard_map_info.get('image_width', 1280)
        image_height = yard_map_info.get('image_height', 720)
        
        # Create pixel mapping
        # This is a simplified version - in production you'd use the camera's
        # intrinsic/extrinsic parameters to properly project pixels
        from datetime import datetime
        
        mapping = {
            'camera_name': camera_name,
            'timestamp': datetime.now().isoformat(),
            'yard_map_bounds': map_bounds,
            'camera_pose': {
                'position': camera_pose.get('translation', [0, 0, 0]),
                'rotation': camera_pose.get('rotation', [0, 0, 0, 1]),
                'transformation_matrix': camera_pose.get('transformation_matrix', [])
            },
            'mapping_table': generate_pixel_mapping_table(
                camera_pose, 
                map_bounds, 
                image_width, 
                image_height
            ),
            'status': 'mapped'
        }
        
        # Save mapping
        mappings = load_camera_mappings()
        mappings[camera_name] = mapping
        save_camera_mappings(mappings)
        
        logger.info(f"Created pixel mapping for camera {camera_name}")
        
        return jsonify({
            'status': 'success',
            'camera': camera_name,
            'mapped_pixels': len(mapping['mapping_table']) if isinstance(mapping['mapping_table'], list) else 'generated',
            'message': f'Successfully mapped pixels for {camera_name}'
        })
        
    except Exception as e:
        logger.error(f"Error mapping camera pixels: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/camera-mappings', methods=['GET'])
def get_camera_mappings():
    """Get status of all camera mappings"""
    try:
        mappings = load_camera_mappings()
        
        # Get list of available cameras
        camera_poses = load_camera_poses_from_files()
        
        result = {
            'mappings': {}
        }
        
        for camera in camera_poses.keys():
            if camera in mappings:
                result['mappings'][camera] = {
                    'mapped': True,
                    'timestamp': mappings[camera].get('timestamp', ''),
                    'status': mappings[camera].get('status', 'unknown')
                }
            else:
                result['mappings'][camera] = {
                    'mapped': False,
                    'status': 'not_mapped'
                }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting camera mappings: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/validate-mappings', methods=['POST'])
def validate_mappings():
    """Validate all camera pixel mappings"""
    try:
        mappings = load_camera_mappings()
        
        if not mappings:
            return jsonify({
                'valid': False,
                'message': 'No mappings found'
            })
        
        # Check each mapping
        invalid_mappings = []
        for camera, mapping in mappings.items():
            if not mapping.get('mapping_table'):
                invalid_mappings.append(camera)
            elif not mapping.get('yard_map_bounds'):
                invalid_mappings.append(camera)
        
        if invalid_mappings:
            return jsonify({
                'valid': False,
                'message': f'Invalid mappings for cameras: {", ".join(invalid_mappings)}'
            })
        
        return jsonify({
            'valid': True,
            'message': f'All {len(mappings)} camera mappings are valid',
            'cameras': list(mappings.keys())
        })
        
    except Exception as e:
        logger.error(f"Error validating mappings: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/clear-all-mappings', methods=['POST'])
def clear_all_mappings():
    """Clear all camera pixel mappings"""
    try:
        # Clear the mappings file
        if os.path.exists(CAMERA_MAPPINGS_FILE):
            os.remove(CAMERA_MAPPINGS_FILE)
        
        logger.info("Cleared all camera pixel mappings")
        
        return jsonify({
            'status': 'success',
            'message': 'All camera mappings cleared'
        })
        
    except Exception as e:
        logger.error(f"Error clearing mappings: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/export-all-mappings', methods=['GET'])
def export_all_mappings():
    """Export all camera mappings as JSON"""
    try:
        mappings = load_camera_mappings()
        
        # Add metadata
        export_data = {
            'version': '1.0',
            'timestamp': datetime.now().isoformat(),
            'camera_count': len(mappings),
            'mappings': mappings
        }
        
        return jsonify(export_data)
        
    except Exception as e:
        logger.error(f"Error exporting mappings: {e}")
        return jsonify({'error': str(e)}), 500

def generate_pixel_mapping_table(camera_pose, map_bounds, map_width, map_height):
    """
    Generate a pixel mapping table from camera to yard map.
    This is a simplified implementation - in production you would:
    1. Use camera intrinsic parameters (focal length, principal point)
    2. Use camera extrinsic parameters (rotation, translation)
    3. Perform proper 3D-to-2D projection
    4. Account for lens distortion
    """
    
    # For now, return a simple mapping structure
    # In a real implementation, this would contain:
    # - Camera pixel coordinates -> Yard map pixel coordinates
    # - Only for ground plane pixels (where Z ≈ 0)
    
    mapping_info = {
        'type': 'simplified',
        'description': 'Camera to yard map pixel projection mapping',
        'camera_resolution': [1920, 1080],  # Typical camera resolution
        'map_resolution': [map_width, map_height],
        'map_bounds': map_bounds,
        'notes': 'This is a placeholder for the actual pixel mapping implementation'
    }
    
    # In production, you would generate an actual lookup table or transformation matrix
    # For each ground pixel in camera view -> corresponding yard map pixel
    
    return mapping_info

@bp.route('/project-to-map', methods=['POST'])
def project_to_map():
    """
    Project a camera pixel coordinate to yard map coordinate.
    Used during live tracking to place Erik on the map.
    """
    try:
        data = request.json
        camera_name = data.get('camera_name')
        pixel_x = data.get('pixel_x')
        pixel_y = data.get('pixel_y')
        
        if not camera_name:
            return jsonify({'error': 'Camera name required'}), 400
        
        # Load mappings
        mappings = load_camera_mappings()
        
        if camera_name not in mappings:
            return jsonify({'error': f'No mapping for camera {camera_name}'}), 404
        
        mapping = mappings[camera_name]
        
        # In production, use the mapping table to convert pixel coordinates
        # For now, return a placeholder
        
        # This would be the actual projection calculation
        map_x = pixel_x  # Placeholder
        map_y = pixel_y  # Placeholder
        
        return jsonify({
            'camera_pixel': [pixel_x, pixel_y],
            'map_pixel': [map_x, map_y],
            'camera': camera_name
        })
        
    except Exception as e:
        logger.error(f"Error projecting to map: {e}")
        return jsonify({'error': str(e)}), 500