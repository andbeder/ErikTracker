"""
Camera Pose and Pixel Mapping API
Handles camera-to-yard-map pixel projection mappings
"""

import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, send_file
import logging
import numpy as np
from app.services.pixel_mapping_service import PixelMappingService

logger = logging.getLogger(__name__)

bp = Blueprint('pose', __name__, url_prefix='/api/pose')

# Initialize pixel mapping service
pixel_service = PixelMappingService()

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


# New ray-casting pixel mapping endpoints

@bp.route('/build-ground-height-map', methods=['POST'])
def build_ground_height_map():
    """Build ground height map from point cloud"""
    try:
        data = request.json
        point_cloud_path = data.get('point_cloud_path')
        percentile = data.get('percentile', 20)
        
        # Load yard map configuration
        yard_config_path = data.get('yard_config_path', 'config/yard_map_config.json')
        pixel_service.load_yard_map_config(yard_config_path)
        
        # Check if point cloud exists
        mesh_folder = os.environ.get('MESH_FOLDER', '/home/andrew/nvr/meshes')
        if not point_cloud_path:
            # Try to find the default reconstruction
            point_cloud_path = os.path.join(mesh_folder, 'yard_reconstruction.ply')
        
        if not os.path.exists(point_cloud_path):
            return jsonify({'error': f'Point cloud not found: {point_cloud_path}'}), 404
        
        # Build ground height map
        ground_heights = pixel_service.build_ground_height_map(point_cloud_path, percentile)
        
        # Save ground heights to file
        output_path = os.path.join('config', 'ground_heights.json')
        os.makedirs('config', exist_ok=True)
        
        # Convert tuple keys to strings for JSON serialization
        json_heights = {f"{k[0]},{k[1]}": v for k, v in ground_heights.items()}
        
        with open(output_path, 'w') as f:
            json.dump(json_heights, f)
        
        return jsonify({
            'success': True,
            'pixel_count': len(ground_heights),
            'output_path': output_path,
            'yard_map_config': pixel_service.yard_map_config
        })
        
    except Exception as e:
        logger.error(f"Error building ground height map: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/generate-pixel-mapping', methods=['POST'])
def generate_pixel_mapping_raycast():
    """Generate pixel mapping for a camera using ray-casting"""
    try:
        data = request.json
        camera_name = data.get('camera_name')
        sample_rate = data.get('sample_rate', 10)
        
        if not camera_name:
            return jsonify({'error': 'Camera name required'}), 400
        
        # Load camera pose
        camera_poses = load_camera_poses_from_files()
        if camera_name not in camera_poses:
            return jsonify({'error': f'No pose data for camera {camera_name}'}), 404
        
        camera_pose_data = camera_poses[camera_name]
        
        # Prepare camera configuration
        camera_config = {
            'transformation_matrix': camera_pose_data.get('transformation_matrix'),
            'image_width': data.get('image_width', 1920),
            'image_height': data.get('image_height', 1080),
            'focal_length': data.get('focal_length', 1000),
            'principal_point': data.get('principal_point', [960, 540])
        }
        
        # Load ground heights if not already loaded
        if not pixel_service.ground_heights:
            ground_heights_path = 'config/ground_heights.json'
            if os.path.exists(ground_heights_path):
                with open(ground_heights_path, 'r') as f:
                    json_heights = json.load(f)
                    # Convert string keys back to tuples
                    pixel_service.ground_heights = {
                        tuple(map(int, k.split(','))): v 
                        for k, v in json_heights.items()
                    }
            else:
                return jsonify({'error': 'Ground height map not built. Run build-ground-height-map first'}), 400
        
        # Load yard map config if not loaded
        if not pixel_service.yard_map_config:
            pixel_service.load_yard_map_config()
        
        # Generate pixel mapping
        mapping_result = pixel_service.generate_pixel_mapping(
            camera_name, 
            camera_config,
            sample_rate
        )
        
        # Save the mapping
        pixel_service.save_mapping(camera_name)
        
        # Also update the legacy mappings file for compatibility
        mappings = load_camera_mappings()
        mappings[camera_name] = {
            'camera_name': camera_name,
            'timestamp': datetime.now().isoformat(),
            'status': 'mapped',
            'yard_map_bounds': pixel_service.yard_map_config,
            'camera_pose': camera_pose_data,
            'mapping_table': {
                'type': 'ray_cast',
                'sample_rate': sample_rate,
                'valid_pixels': mapping_result['valid_pixel_count'],
                'total_sampled': mapping_result['total_sampled_pixels']
            }
        }
        save_camera_mappings(mappings)
        
        return jsonify({
            'success': True,
            'camera_name': camera_name,
            'valid_mappings': mapping_result['valid_pixel_count'],
            'total_sampled': mapping_result['total_sampled_pixels'],
            'sample_rate': sample_rate,
            'coverage_percentage': (mapping_result['valid_pixel_count'] / 
                                   mapping_result['total_sampled_pixels'] * 100)
                                  if mapping_result['total_sampled_pixels'] > 0 else 0
        })
        
    except Exception as e:
        logger.error(f"Error generating pixel mapping: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/query-pixel-mapping', methods=['POST'])
def query_pixel_mapping():
    """Query yard map coordinates for a camera pixel"""
    try:
        data = request.json
        camera_name = data.get('camera_name')
        pixel_x = data.get('pixel_x')
        pixel_y = data.get('pixel_y')
        
        if not camera_name or pixel_x is None or pixel_y is None:
            return jsonify({'error': 'camera_name, pixel_x, and pixel_y required'}), 400
        
        # Try to load existing mapping
        if camera_name not in pixel_service.pixel_mappings:
            mapping_path = f"config/pixel_mappings/{camera_name}_mapping.json"
            if not pixel_service.load_mapping(camera_name, mapping_path):
                return jsonify({'error': f'No mapping found for camera {camera_name}'}), 404
        
        # Get interpolated yard map coordinates
        result = pixel_service.interpolate_pixel(pixel_x, pixel_y, camera_name)
        
        if result:
            return jsonify({
                'success': True,
                'camera_pixel': {'x': pixel_x, 'y': pixel_y},
                'yard_map_pixel': {
                    'x': result['yard_map_x'],
                    'y': result['yard_map_y']
                },
                'confidence': result['confidence'],
                'interpolated': result.get('interpolated', False)
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No ground intersection found for this pixel'
            })
            
    except Exception as e:
        logger.error(f"Error querying pixel mapping: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/visualize-pixel-mapping/<camera_name>', methods=['GET'])
def visualize_pixel_mapping(camera_name):
    """Generate a visualization of the pixel mapping"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from io import BytesIO
        
        # Load mapping
        if camera_name not in pixel_service.pixel_mappings:
            mapping_path = f"config/pixel_mappings/{camera_name}_mapping.json"
            if not pixel_service.load_mapping(camera_name, mapping_path):
                return jsonify({'error': f'No mapping found for camera {camera_name}'}), 404
        
        mapping = pixel_service.pixel_mappings[camera_name]
        
        # Create visualization
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Plot camera view with mapped pixels
        camera_width = mapping['camera_resolution']['width']
        camera_height = mapping['camera_resolution']['height']
        sample_rate = mapping['sample_rate']
        
        # Camera view
        ax1.set_title(f'Camera View - {camera_name}')
        ax1.set_xlim(0, camera_width)
        ax1.set_ylim(camera_height, 0)
        ax1.set_xlabel('Pixel X')
        ax1.set_ylabel('Pixel Y')
        ax1.set_aspect('equal')
        
        # Yard map view
        yard_config = mapping['yard_map_config']
        ax2.set_title('Yard Map Coverage')
        ax2.set_xlim(0, yard_config['image_width'])
        ax2.set_ylim(yard_config['image_height'], 0)
        ax2.set_xlabel('Yard Map X')
        ax2.set_ylabel('Yard Map Y')
        ax2.set_aspect('equal')
        
        # Plot mappings
        for pixel_key, yard_coord in mapping['camera_to_yard_mapping'].items():
            cam_x, cam_y = map(int, pixel_key.split(','))
            yard_x = yard_coord['yard_map_x']
            yard_y = yard_coord['yard_map_y']
            confidence = yard_coord['confidence']
            
            # Color based on confidence
            color = plt.cm.viridis(confidence)
            
            # Plot on camera view
            ax1.plot(cam_x, cam_y, 'o', color=color, markersize=2, alpha=0.5)
            
            # Plot on yard map
            ax2.plot(yard_x, yard_y, 'o', color=color, markersize=1, alpha=0.3)
        
        # Add colorbars
        sm = plt.cm.ScalarMappable(cmap=plt.cm.viridis, norm=plt.Normalize(0, 1))
        sm.set_array([])
        fig.colorbar(sm, ax=ax1, label='Confidence')
        fig.colorbar(sm, ax=ax2, label='Confidence')
        
        plt.suptitle(f'Pixel Mapping Visualization - {camera_name}')
        plt.tight_layout()
        
        # Save to BytesIO
        img_buffer = BytesIO()
        plt.savefig(img_buffer, format='png', dpi=100)
        img_buffer.seek(0)
        plt.close()
        
        return send_file(img_buffer, mimetype='image/png')
        
    except ImportError:
        return jsonify({'error': 'Matplotlib not installed for visualization'}), 500
    except Exception as e:
        logger.error(f"Error visualizing pixel mapping: {e}")
        return jsonify({'error': str(e)}), 500