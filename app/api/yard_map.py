"""
Yard Mapping API Blueprint
Handles mesh processing and yard map generation
"""

import os
import json
import base64
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, send_from_directory, Response

bp = Blueprint('yard_map', __name__, url_prefix='/api/yard-map')

@bp.route('/scan-bounds', methods=['POST'])
def scan_bounds():
    """Scan mesh bounds for yard map generation"""
    try:
        data = request.json
        mesh_file = data.get('mesh_file')
        grid_resolution = data.get('grid_resolution', 0.5)
        projection = data.get('projection', 'xy')
        
        if not mesh_file:
            return jsonify({'error': 'Mesh file not specified'}), 400
        
        yard_service = current_app.yard_service
        
        # Get full path to mesh file
        mesh_files = yard_service.list_meshes()
        mesh_path = None
        for mesh in mesh_files:
            if mesh['name'] == mesh_file:
                mesh_path = mesh['path']
                break
        
        if not mesh_path or not os.path.exists(mesh_path):
            return jsonify({'error': 'Mesh file not found'}), 404
        
        # Scan bounds
        bounds = yard_service.scan_bounds(mesh_path, grid_resolution, projection)
        
        if bounds:
            return jsonify({
                'status': 'success',
                'bounds': bounds,
                'mesh_file': mesh_file
            })
        else:
            return jsonify({'error': 'Failed to scan mesh bounds'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/generate', methods=['POST'])
def generate_yard_map():
    """Generate yard map from mesh file"""
    try:
        data = request.json
        mesh_file = data.get('mesh_file')
        generation_type = data.get('type', 'standard')  # 'standard' or 'raster'
        
        # Common parameters
        grid_resolution = data.get('grid_resolution', 0.1)
        projection = data.get('projection', 'xy')
        
        if not mesh_file:
            return jsonify({'error': 'Mesh file not specified'}), 400
        
        yard_service = current_app.yard_service
        
        # Get full path to mesh file
        mesh_files = yard_service.list_meshes()
        mesh_path = None
        for mesh in mesh_files:
            if mesh['name'] == mesh_file:
                mesh_path = mesh['path']
                break
        
        if not mesh_path or not os.path.exists(mesh_path):
            return jsonify({'error': 'Mesh file not found'}), 404
        
        # Generate yard map based on type
        if generation_type == 'raster':
            # Raster-specific parameters
            max_points = data.get('max_points', 20000000)
            height_window = data.get('height_window', 0.5)
            custom_bounds = data.get('custom_bounds')
            coloring = data.get('coloring', 'true_color')
            output_width = data.get('output_width', 1280)
            output_height = data.get('output_height', 720)
            rotation = data.get('rotation', 0)
            
            image_data, log_output = yard_service.generate_raster_yard_map(
                mesh_path, grid_resolution, max_points, projection,
                height_window, custom_bounds, coloring, 
                output_width, output_height, rotation
            )
        else:
            # Standard yard map parameters
            max_points = data.get('max_points', 50000)
            point_size = data.get('point_size', 0.1)
            algorithm = data.get('algorithm', 'kmeans')
            custom_bounds = data.get('custom_bounds')
            height_window = data.get('height_window', 0.5)
            rotation = data.get('rotation', 0)
            
            image_data, log_output = yard_service.generate_yard_map(
                mesh_path, grid_resolution, max_points, point_size, projection, algorithm, custom_bounds, height_window, rotation
            )
        
        if image_data:
            # Encode image as base64 for JSON response
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            return jsonify({
                'status': 'success',
                'image_data': image_base64,
                'log_output': log_output,
                'parameters': {
                    'mesh_file': mesh_file,
                    'type': generation_type,
                    'grid_resolution': grid_resolution,
                    'projection': projection
                }
            })
        else:
            return jsonify({
                'status': 'error',
                'error': log_output or 'Yard map generation failed'
            }), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/download', methods=['POST'])
def download_yard_map():
    """Download generated yard map"""
    try:
        data = request.json
        image_data_base64 = data.get('image_data')
        filename = data.get('filename', 'yard_map.png')
        
        if not image_data_base64:
            return jsonify({'error': 'No image data provided'}), 400
        
        # Decode base64 image data
        image_data = base64.b64decode(image_data_base64)
        
        # Return as file download
        response = Response(
            image_data,
            mimetype='image/png',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/use', methods=['POST'])
def use_yard_map():
    """Set generated yard map as the active map"""
    try:
        data = request.json
        image_data_base64 = data.get('image_data')
        parameters = data.get('parameters', {})
        
        if not image_data_base64:
            return jsonify({'error': 'No image data provided'}), 400
        
        yard_service = current_app.yard_service
        
        # Decode base64 image data
        image_data = base64.b64decode(image_data_base64)
        
        # Create metadata for the active map
        metadata = {
            'source': 'generated',
            'parameters': parameters,
            'generated_at': datetime.now().isoformat(),
            
            # Extract map bounds from parameters for Erik positioning
            'map_bounds': {
                'x_min': parameters.get('custom_bounds', [None]*4)[0] if parameters.get('custom_bounds') and len(parameters.get('custom_bounds', [])) >= 4 else None,
                'x_max': parameters.get('custom_bounds', [None]*4)[1] if parameters.get('custom_bounds') and len(parameters.get('custom_bounds', [])) >= 4 else None,
                'y_min': parameters.get('custom_bounds', [None]*4)[2] if parameters.get('custom_bounds') and len(parameters.get('custom_bounds', [])) >= 4 else None,
                'y_max': parameters.get('custom_bounds', [None]*4)[3] if parameters.get('custom_bounds') and len(parameters.get('custom_bounds', [])) >= 4 else None,
                'center_x': parameters.get('center_x'),
                'center_y': parameters.get('center_y'),
                'scale_meters_per_pixel': parameters.get('scale_meters_per_pixel'),
                'rotation_degrees': parameters.get('rotation', 0),
                'projection': parameters.get('projection', 'xy')
            },
            
            # Image dimensions (standard for yard maps)
            'image_width': 1280,
            'image_height': 720
        }
        
        # Save as active map
        if yard_service.save_active_map(image_data, metadata):
            return jsonify({
                'status': 'success',
                'message': 'Yard map set as active map'
            })
        else:
            return jsonify({'error': 'Failed to save active map'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/mesh-files')
def list_mesh_files():
    """Get list of available mesh files"""
    yard_service = current_app.yard_service
    mesh_files = yard_service.list_meshes()
    
    return jsonify({
        'mesh_files': mesh_files,
        'total_count': len(mesh_files)
    })

@bp.route('/mesh-files/<filename>', methods=['DELETE'])
def delete_mesh_file(filename):
    """Delete a mesh file"""
    try:
        yard_service = current_app.yard_service
        
        if yard_service.delete_mesh(filename):
            return jsonify({
                'status': 'success',
                'message': f'Deleted mesh file: {filename}'
            })
        else:
            return jsonify({'error': 'Failed to delete mesh file'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/active-map/info')
def get_active_map_info():
    """Get information about the active yard map"""
    yard_service = current_app.yard_service
    info = yard_service.get_active_map_info()
    
    if info:
        return jsonify(info)
    else:
        return jsonify({'message': 'No active yard map'}), 404

@bp.route('/active-map/image')
def get_active_map_image():
    """Serve the active yard map image"""
    try:
        yard_service = current_app.yard_service
        
        # Get absolute path to the active yard map
        active_map_path = os.path.abspath(yard_service.active_yard_map_path)
        
        # Check if active map exists
        if os.path.exists(active_map_path):
            return send_from_directory(
                os.path.dirname(active_map_path),
                os.path.basename(active_map_path),
                mimetype='image/png'
            )
        else:
            return jsonify({'error': f'No active yard map found at {active_map_path}'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/presets')
def get_generation_presets():
    """Get predefined yard map generation presets"""
    presets = {
        'quick_preview': {
            'name': 'Quick Preview',
            'description': 'Fast generation for preview',
            'type': 'standard',
            'grid_resolution': 0.5,
            'max_points': 10000,
            'point_size': 0.2
        },
        'standard_quality': {
            'name': 'Standard Quality',
            'description': 'Balanced quality and speed',
            'type': 'standard',
            'grid_resolution': 0.1,
            'max_points': 50000,
            'point_size': 0.1
        },
        'high_quality': {
            'name': 'High Quality',
            'description': 'Best quality, slower generation',
            'type': 'raster',
            'grid_resolution': 0.05,
            'max_points': 20000000,
            'height_window': 0.3,
            'coloring': 'true_color',
            'output_width': 1920,
            'output_height': 1080
        },
        'terrain_view': {
            'name': 'Terrain View',
            'description': 'Emphasizes terrain features',
            'type': 'raster',
            'grid_resolution': 0.1,
            'max_points': 10000000,
            'height_window': 0.5,
            'coloring': 'terrain',
            'output_width': 1280,
            'output_height': 720
        }
    }
    
    return jsonify({
        'presets': presets,
        'total_count': len(presets)
    })