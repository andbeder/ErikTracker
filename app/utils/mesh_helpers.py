"""
Mesh processing helper utilities
Common mesh operations and 3D model utilities
"""

import os
import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

def get_mesh_files(mesh_folder, mesh_extensions=None):
    """Get list of mesh files in directory
    
    Args:
        mesh_folder: Path to mesh directory
        mesh_extensions: Set of allowed mesh file extensions
        
    Returns:
        List of mesh file information dictionaries
    """
    if not mesh_extensions:
        mesh_extensions = {'ply', 'obj', 'stl'}
    
    meshes = []
    try:
        mesh_path = Path(mesh_folder)
        if mesh_path.exists():
            for file in mesh_path.glob('*'):
                if file.suffix.lower() in {f'.{ext}' for ext in mesh_extensions}:
                    stats = file.stat()
                    meshes.append({
                        'name': file.name,
                        'path': str(file),
                        'size': stats.st_size,
                        'size_mb': stats.st_size / (1024 * 1024),
                        'modified': datetime.fromtimestamp(stats.st_mtime).isoformat(),
                        'type': file.suffix[1:].upper()
                    })
        
        # Sort by modification time (newest first)
        meshes.sort(key=lambda x: x['modified'], reverse=True)
        
    except Exception as e:
        logger.error(f"Error listing mesh files: {e}")
    
    return meshes

def validate_mesh_file(mesh_path):
    """Validate that a mesh file exists and is readable
    
    Args:
        mesh_path: Path to mesh file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        if not os.path.exists(mesh_path):
            return False, f"Mesh file not found: {mesh_path}"
        
        if not os.path.isfile(mesh_path):
            return False, f"Path is not a file: {mesh_path}"
        
        # Check file size
        file_size = os.path.getsize(mesh_path)
        if file_size == 0:
            return False, "Mesh file is empty"
        
        # Check file extension
        file_ext = Path(mesh_path).suffix.lower()
        if file_ext not in {'.ply', '.obj', '.stl'}:
            return False, f"Unsupported mesh format: {file_ext}"
        
        # Basic file header check for PLY files
        if file_ext == '.ply':
            with open(mesh_path, 'r') as f:
                first_line = f.readline().strip()
                if not first_line.startswith('ply'):
                    return False, "Invalid PLY file format"
        
        return True, "Valid mesh file"
        
    except Exception as e:
        return False, f"Error validating mesh file: {str(e)}"

def get_mesh_info(mesh_path):
    """Get detailed information about a mesh file
    
    Args:
        mesh_path: Path to mesh file
        
    Returns:
        Dictionary with mesh information or None if failed
    """
    try:
        is_valid, error_msg = validate_mesh_file(mesh_path)
        if not is_valid:
            return {'error': error_msg}
        
        stats = os.stat(mesh_path)
        file_path = Path(mesh_path)
        
        info = {
            'name': file_path.name,
            'path': str(file_path),
            'size': stats.st_size,
            'size_mb': stats.st_size / (1024 * 1024),
            'modified': datetime.fromtimestamp(stats.st_mtime).isoformat(),
            'format': file_path.suffix[1:].upper(),
            'valid': True
        }
        
        # Try to get additional mesh statistics
        if file_path.suffix.lower() == '.ply':
            ply_info = _get_ply_info(mesh_path)
            if ply_info:
                info.update(ply_info)
        
        return info
        
    except Exception as e:
        logger.error(f"Error getting mesh info: {e}")
        return {'error': str(e)}

def _get_ply_info(ply_path):
    """Get information from PLY file header
    
    Args:
        ply_path: Path to PLY file
        
    Returns:
        Dictionary with PLY file information
    """
    try:
        info = {
            'vertices': 0,
            'faces': 0,
            'format': 'unknown'
        }
        
        with open(ply_path, 'r') as f:
            in_header = True
            while in_header:
                line = f.readline().strip()
                
                if line.startswith('format'):
                    info['format'] = line.split()[1]
                elif line.startswith('element vertex'):
                    info['vertices'] = int(line.split()[2])
                elif line.startswith('element face'):
                    info['faces'] = int(line.split()[2])
                elif line == 'end_header':
                    in_header = False
        
        return info
        
    except Exception as e:
        logger.error(f"Error reading PLY header: {e}")
        return None

def calculate_mesh_bounds(mesh_path, grid_resolution=0.5):
    """Calculate mesh bounding box
    
    Args:
        mesh_path: Path to mesh file
        grid_resolution: Grid resolution for sampling
        
    Returns:
        Dictionary with mesh bounds or None if failed
    """
    try:
        # This would typically use a 3D processing library
        # For now, return placeholder bounds that could be calculated
        # In a real implementation, you'd use libraries like Open3D or trimesh
        
        logger.info(f"Calculating bounds for mesh: {mesh_path}")
        
        # Placeholder bounds - in real implementation would calculate from mesh
        bounds = {
            'xmin': -10.0,
            'xmax': 10.0,
            'ymin': -10.0,
            'ymax': 10.0,
            'zmin': -2.0,
            'zmax': 2.0,
            'grid_resolution': grid_resolution
        }
        
        return bounds
        
    except Exception as e:
        logger.error(f"Error calculating mesh bounds: {e}")
        return None

def mesh_to_point_cloud(mesh_path, output_path, max_points=50000):
    """Convert mesh to point cloud
    
    Args:
        mesh_path: Path to input mesh file
        output_path: Path for output point cloud
        max_points: Maximum number of points to sample
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # This would typically use a 3D processing library
        # For now, return True as placeholder
        logger.info(f"Converting mesh to point cloud: {mesh_path} -> {output_path}")
        
        # In real implementation, would use libraries to:
        # 1. Load mesh
        # 2. Sample points from surface
        # 3. Save as point cloud format
        
        return True
        
    except Exception as e:
        logger.error(f"Error converting mesh to point cloud: {e}")
        return False

def optimize_mesh(mesh_path, output_path=None, reduction_ratio=0.5):
    """Optimize mesh by reducing polygon count
    
    Args:
        mesh_path: Path to input mesh file
        output_path: Path for optimized mesh (optional)
        reduction_ratio: Ratio of polygons to keep (0.0-1.0)
        
    Returns:
        Path to optimized mesh if successful, None otherwise
    """
    try:
        if not output_path:
            path = Path(mesh_path)
            output_path = str(path.with_name(f"{path.stem}_optimized{path.suffix}"))
        
        logger.info(f"Optimizing mesh: {mesh_path} -> {output_path}")
        
        # This would typically use mesh processing tools
        # For now, copy the original file as placeholder
        import shutil
        shutil.copy2(mesh_path, output_path)
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error optimizing mesh: {e}")
        return None

def mesh_statistics(mesh_path):
    """Get comprehensive mesh statistics
    
    Args:
        mesh_path: Path to mesh file
        
    Returns:
        Dictionary with mesh statistics
    """
    try:
        base_info = get_mesh_info(mesh_path)
        if 'error' in base_info:
            return base_info
        
        stats = {
            **base_info,
            'quality': 'unknown',
            'density': 'unknown',
            'manifold': 'unknown',
            'watertight': 'unknown'
        }
        
        # In real implementation, would calculate:
        # - Mesh quality metrics
        # - Vertex density
        # - Manifold properties
        # - Watertight analysis
        
        return stats
        
    except Exception as e:
        logger.error(f"Error calculating mesh statistics: {e}")
        return {'error': str(e)}

def cleanup_mesh_cache(cache_dir, max_age_hours=24):
    """Clean up temporary mesh processing files
    
    Args:
        cache_dir: Directory containing cached mesh files
        max_age_hours: Maximum age in hours before cleanup
        
    Returns:
        Number of files cleaned up
    """
    try:
        from .file_helpers import cleanup_temp_files
        return cleanup_temp_files(cache_dir, max_age_hours)
    except Exception as e:
        logger.error(f"Error cleaning mesh cache: {e}")
        return 0