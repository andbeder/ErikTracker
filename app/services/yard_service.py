"""
Yard Mapping Service for Mesh Processing and Map Generation
Handles yard map generation from 3D meshes
"""

import os
import sys
import json
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class YardMappingService:
    """Service for generating yard maps from 3D mesh data"""
    
    def __init__(self, config=None):
        """Initialize yard mapping service with configuration"""
        self.config = config or {}
        
        # Configuration
        self.mesh_folder = self.config.get('MESH_FOLDER', './meshes')
        self.yard_map_path = self.config.get('YARD_MAP_PATH', './yard_map.png')
        self.active_yard_map_path = self.config.get('ACTIVE_YARD_MAP_PATH', './active_yard_map.png')
        self.active_yard_map_json = self.config.get('ACTIVE_YARD_MAP_JSON', './active_yard_map.json')
        
        # Yard map generation scripts
        self.script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.yard_map_dir = os.path.join(self.script_dir, 'yard_map')
        self.fast_yard_map_script = os.path.join(self.yard_map_dir, 'fast_yard_map.py')
        self.raster_yard_map_script = os.path.join(self.yard_map_dir, 'fast_yard_map_raster.py')
        
        # Python executable (use dev-venv for packages)
        venv_python = os.path.join(self.script_dir, 'dev-venv', 'bin', 'python3')
        self.python_executable = venv_python if os.path.exists(venv_python) else sys.executable
    
    def generate_yard_map(self, mesh_path, grid_resolution=0.1, max_points=50000, 
                         point_size=0.1, projection='xy', algorithm='kmeans', custom_bounds=None, height_window=0.5, rotation=0):
        """Generate yard map from mesh file
        
        Args:
            mesh_path: Path to the mesh file
            grid_resolution: Grid resolution for sampling
            max_points: Maximum number of points to process
            point_size: Size of points in the visualization
            projection: Projection plane ('xy', 'xz', 'yz')
            algorithm: Algorithm for processing points ('kmeans', 'simple_average')
            custom_bounds: [x_min, x_max, y_min, y_max] for fixed view area and scale
            height_window: Height window for K-means optimization (default: 0.5m)
            rotation: Rotation angle in degrees (default: 0)
            
        Returns:
            Tuple of (image_data, output_log) or (None, error_message) if failed
        """
        try:
            logger.info(f"Generating yard map with algorithm: {algorithm}, custom_bounds: {custom_bounds}")
            
            # Use CUDA script for bottom_percentile and simple_average, regular script for kmeans
            if algorithm in ['simple_average', 'bottom_percentile']:
                script_to_use = os.path.join(self.yard_map_dir, 'fast_yard_map_cuda.py')
                # Use much higher point limit for CUDA algorithms since they can handle it efficiently
                cuda_max_points = 20000000  # Use full dataset for CUDA algorithms
                cmd = [
                    self.python_executable, script_to_use, mesh_path,
                    '--max-points', str(cuda_max_points),
                    '--grid-resolution', str(grid_resolution),
                    '--projection', projection,
                    '--algorithm', algorithm,
                    '--rotation', str(rotation)
                ]
                logger.info(f"Using CUDA algorithm with {cuda_max_points:,} max points")
                
                # CUDA script uses separate parameters for bounds
                if custom_bounds is not None and len(custom_bounds) == 4 and all(isinstance(x, (int, float)) and x is not None for x in custom_bounds):
                    cmd.extend(['--x-min', str(custom_bounds[0])])
                    cmd.extend(['--x-max', str(custom_bounds[1])])
                    cmd.extend(['--y-min', str(custom_bounds[2])])
                    cmd.extend(['--y-max', str(custom_bounds[3])])
                    logger.info(f"Added bounds parameters: x=[{custom_bounds[0]}, {custom_bounds[1]}], y=[{custom_bounds[2]}, {custom_bounds[3]}]")
                elif custom_bounds is not None:
                    logger.warning(f"Invalid custom_bounds ignored: {custom_bounds} (type: {type(custom_bounds)}, len: {len(custom_bounds) if hasattr(custom_bounds, '__len__') else 'N/A'})")
                    
            else:  # kmeans - use regular script
                cmd = [
                    self.python_executable, self.fast_yard_map_script, mesh_path,
                    '--max-points', str(max_points),
                    '--point-size', str(point_size),
                    '--grid-resolution', str(grid_resolution),
                    '--projection', projection,
                    '--algorithm', algorithm,
                    '--height-window', str(height_window)
                ]
                
                # Add custom bounds if provided
                if custom_bounds is not None:
                    cmd.extend(['--custom-bounds'] + [str(bound) for bound in custom_bounds])
                
            # Create temporary output file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                cmd.extend(['--output', tmp_file.name])
                
                logger.info(f"Running yard map generation command: {cmd}")
                logger.info(f"Command as string: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                
                if result.returncode == 0:
                    # Read the generated image
                    with open(tmp_file.name, 'rb') as f:
                        image_data = f.read()
                    
                    # Clean up temp file
                    os.unlink(tmp_file.name)
                    
                    return image_data, result.stdout
                else:
                    logger.error(f"Yard map generation failed: {result.stderr}")
                    return None, result.stderr
                    
        except subprocess.TimeoutExpired:
            logger.error("Yard map generation timed out")
            return None, "Generation timed out after 10 minutes"
        except Exception as e:
            logger.error(f"Error generating yard map: {e}")
            return None, str(e)
    
    def generate_raster_yard_map(self, mesh_path, grid_resolution=0.1, max_points=20000000, 
                                 projection='xy', height_window=0.5, custom_bounds=None, 
                                 coloring='true_color', output_width=1280, output_height=720, 
                                 rotation=0):
        """Generate rasterized yard map from mesh file
        
        Args:
            mesh_path: Path to the mesh file
            grid_resolution: Grid resolution for sampling
            max_points: Maximum number of points to process
            projection: Projection plane ('xy', 'xz', 'yz')
            height_window: Height window for filtering
            custom_bounds: Custom bounds dictionary
            coloring: Coloring mode ('true_color', 'terrain', 'shadow')
            output_width: Output image width
            output_height: Output image height
            rotation: Rotation angle in degrees
            
        Returns:
            Tuple of (image_data, output_log) or (None, error_message) if failed
        """
        try:
            # Check if raster script exists, fallback to regular if not
            if not os.path.exists(self.raster_yard_map_script):
                logger.warning(f"Raster script not found, using regular yard map generation")
                return self.generate_yard_map(mesh_path, grid_resolution, max_points, 0.1, projection)
            
            cmd = [
                self.python_executable, self.raster_yard_map_script, mesh_path,
                '--max-points', str(max_points),
                '--grid-resolution', str(grid_resolution),
                '--projection', projection
            ]
            
            # Note: custom bounds not supported by raster script
                
            # Create temporary output file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                cmd.extend(['--output', tmp_file.name])
                
                logger.info(f"Running raster yard map generation")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                
                if result.returncode == 0:
                    # Read the generated image
                    with open(tmp_file.name, 'rb') as f:
                        image_data = f.read()
                    
                    # Clean up temp file
                    os.unlink(tmp_file.name)
                    
                    return image_data, result.stdout
                else:
                    logger.error(f"Raster yard map generation failed: {result.stderr}")
                    return None, result.stderr
                    
        except subprocess.TimeoutExpired:
            logger.error("Raster yard map generation timed out")
            return None, "Generation timed out after 10 minutes"
        except Exception as e:
            logger.error(f"Error generating raster yard map: {e}")
            return None, str(e)
    
    def scan_bounds(self, mesh_path, grid_resolution=0.5, projection='xy'):
        """Scan mesh bounds for yard map generation
        
        Args:
            mesh_path: Path to the mesh file
            grid_resolution: Grid resolution for sampling (not used in direct calculation)
            projection: Projection plane ('xy', 'xz', 'yz')
            
        Returns:
            Bounds dictionary or None if failed
        """
        try:
            import trimesh
            import numpy as np
            
            logger.info(f"Scanning bounds for: {mesh_path} with projection: {projection}")
            
            # Load mesh and get vertices
            mesh = trimesh.load(mesh_path)
            vertices = mesh.vertices
            
            # Calculate 2-98 percentile bounds for all axes
            x_bounds = np.percentile(vertices[:, 0], [2, 98])
            y_bounds = np.percentile(vertices[:, 1], [2, 98])
            z_bounds = np.percentile(vertices[:, 2], [2, 98])
            
            # Select bounds based on projection
            if projection == 'xy':
                axis1_bounds = x_bounds
                axis2_bounds = y_bounds
                axis1_label = 'X'
                axis2_label = 'Y'
            elif projection == 'xz':
                axis1_bounds = x_bounds
                axis2_bounds = z_bounds
                axis1_label = 'X'
                axis2_label = 'Z'
            elif projection == 'yz':
                axis1_bounds = y_bounds
                axis2_bounds = z_bounds
                axis1_label = 'Y'
                axis2_label = 'Z'
            else:
                logger.error(f"Invalid projection: {projection}")
                return None
            
            logger.info(f"Scanned bounds: {axis1_label}=[{axis1_bounds[0]:.2f}, {axis1_bounds[1]:.2f}], {axis2_label}=[{axis2_bounds[0]:.2f}, {axis2_bounds[1]:.2f}]")
            
            # Return the bounds with axis labels
            bounds = {
                'axis1_min': float(axis1_bounds[0]),
                'axis1_max': float(axis1_bounds[1]),
                'axis2_min': float(axis2_bounds[0]),
                'axis2_max': float(axis2_bounds[1]),
                'axis1_label': axis1_label,
                'axis2_label': axis2_label,
                # Keep legacy fields for compatibility
                'x_min': float(axis1_bounds[0]),
                'x_max': float(axis1_bounds[1]),
                'y_min': float(axis2_bounds[0]),
                'y_max': float(axis2_bounds[1]),
                'z_min': float(z_bounds[0]),
                'z_max': float(z_bounds[1]),
                'total_points': len(vertices)
            }
            
            return bounds
                
        except ImportError as e:
            logger.error(f"Missing required library: {e}")
            return None
        except Exception as e:
            logger.error(f"Error scanning bounds: {e}")
            return None
    
    def list_meshes(self):
        """List available mesh files
        
        Returns:
            List of mesh file information dictionaries
        """
        meshes = []
        try:
            mesh_path = Path(self.mesh_folder)
            if mesh_path.exists():
                for file in mesh_path.glob('*'):
                    if file.suffix.lower() in {'.ply', '.obj', '.stl'}:
                        stats = file.stat()
                        meshes.append({
                            'name': file.name,
                            'path': str(file),
                            'size': stats.st_size,
                            'modified': datetime.fromtimestamp(stats.st_mtime).isoformat(),
                            'type': file.suffix[1:].upper()
                        })
        except Exception as e:
            logger.error(f"Error listing meshes: {e}")
        
        return sorted(meshes, key=lambda x: x['modified'], reverse=True)
    
    def save_active_map(self, image_data, metadata=None):
        """Save yard map as the active map
        
        Args:
            image_data: PNG image data
            metadata: Optional metadata dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Save the image
            with open(self.active_yard_map_path, 'wb') as f:
                f.write(image_data)
            
            # Save metadata if provided
            if metadata:
                # Enhanced metadata for Erik positioning
                enhanced_metadata = {
                    'saved_at': datetime.now().isoformat(),
                    'image_path': self.active_yard_map_path,
                    'source': metadata.get('source', 'generated'),
                    'parameters': metadata.get('parameters', {}),
                    
                    # Map positioning data for Erik
                    'map_bounds': {
                        'x_min': metadata.get('map_bounds', {}).get('x_min'),
                        'x_max': metadata.get('map_bounds', {}).get('x_max'),
                        'y_min': metadata.get('map_bounds', {}).get('y_min'),
                        'y_max': metadata.get('map_bounds', {}).get('y_max'),
                        'center_x': metadata.get('map_bounds', {}).get('center_x'),
                        'center_y': metadata.get('map_bounds', {}).get('center_y'),
                        'scale_meters_per_pixel': metadata.get('map_bounds', {}).get('scale_meters_per_pixel'),
                        'rotation_degrees': metadata.get('map_bounds', {}).get('rotation_degrees', 0),
                        'projection': metadata.get('map_bounds', {}).get('projection', 'xy')
                    },
                    
                    # Image dimensions
                    'image_width': metadata.get('image_width'),
                    'image_height': metadata.get('image_height'),
                    
                    # Generation metadata
                    'algorithm': metadata.get('parameters', {}).get('algorithm'),
                    'grid_resolution': metadata.get('parameters', {}).get('grid_resolution'),
                    'mesh_file': metadata.get('parameters', {}).get('mesh_file')
                }
                
                with open(self.active_yard_map_json, 'w') as f:
                    json.dump(enhanced_metadata, f, indent=2)
                    
                logger.info(f"Saved active yard map with enhanced metadata: bounds={enhanced_metadata['map_bounds']}")
            
            logger.info(f"Saved active yard map to {self.active_yard_map_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving active map: {e}")
            return False
    
    def get_active_map_info(self):
        """Get information about the active yard map
        
        Returns:
            Dictionary with active map information or None if not found
        """
        try:
            if os.path.exists(self.active_yard_map_json):
                with open(self.active_yard_map_json, 'r') as f:
                    return json.load(f)
            elif os.path.exists(self.active_yard_map_path):
                # Return basic info if JSON doesn't exist
                stats = os.stat(self.active_yard_map_path)
                return {
                    'image_path': self.active_yard_map_path,
                    'size': stats.st_size,
                    'modified': datetime.fromtimestamp(stats.st_mtime).isoformat()
                }
        except Exception as e:
            logger.error(f"Error getting active map info: {e}")
        
        return None
    
    def delete_mesh(self, mesh_name):
        """Delete a mesh file
        
        Args:
            mesh_name: Name of the mesh file to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            mesh_path = Path(self.mesh_folder) / mesh_name
            if mesh_path.exists() and mesh_path.is_file():
                mesh_path.unlink()
                logger.info(f"Deleted mesh: {mesh_name}")
                return True
            else:
                logger.warning(f"Mesh not found: {mesh_name}")
                return False
        except Exception as e:
            logger.error(f"Error deleting mesh: {e}")
            return False