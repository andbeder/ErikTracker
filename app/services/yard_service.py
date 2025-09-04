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
        self.fast_yard_map_script = os.path.join(self.script_dir, 'fast_yard_map.py')
        self.raster_yard_map_script = os.path.join(self.script_dir, 'fast_yard_map_raster.py')
        
        # Python executable (works with venv)
        self.python_executable = sys.executable
    
    def generate_yard_map(self, mesh_path, grid_resolution=0.1, max_points=50000, 
                         point_size=0.1, projection='xy'):
        """Generate yard map from mesh file
        
        Args:
            mesh_path: Path to the mesh file
            grid_resolution: Grid resolution for sampling
            max_points: Maximum number of points to process
            point_size: Size of points in the visualization
            projection: Projection plane ('xy', 'xz', 'yz')
            
        Returns:
            Tuple of (image_data, output_log) or (None, error_message) if failed
        """
        try:
            cmd = [
                self.python_executable, self.fast_yard_map_script, mesh_path,
                '--max-points', str(max_points),
                '--point-size', str(point_size),
                '--grid-resolution', str(grid_resolution),
                '--projection', projection
            ]
                
            # Create temporary output file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                cmd.extend(['--output', tmp_file.name])
                
                logger.info(f"Running yard map generation: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
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
            return None, "Generation timed out after 2 minutes"
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
                '--projection', projection,
                '--height-window', str(height_window),
                '--coloring', coloring,
                '--output-width', str(output_width),
                '--output-height', str(output_height),
                '--rotation', str(rotation)
            ]
            
            # Add custom bounds if provided
            if custom_bounds:
                cmd.extend([
                    '--xmin', str(custom_bounds['xmin']),
                    '--xmax', str(custom_bounds['xmax']),
                    '--ymin', str(custom_bounds['ymin']),
                    '--ymax', str(custom_bounds['ymax'])
                ])
                
            # Create temporary output file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                cmd.extend(['--output', tmp_file.name])
                
                logger.info(f"Running raster yard map generation")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                
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
            return None, "Generation timed out after 3 minutes"
        except Exception as e:
            logger.error(f"Error generating raster yard map: {e}")
            return None, str(e)
    
    def scan_bounds(self, mesh_path, grid_resolution=0.5, projection='xy'):
        """Scan mesh bounds for yard map generation
        
        Args:
            mesh_path: Path to the mesh file
            grid_resolution: Grid resolution for sampling
            projection: Projection plane
            
        Returns:
            Bounds dictionary or None if failed
        """
        try:
            cmd = [
                self.python_executable, self.fast_yard_map_script, mesh_path,
                '--scan-bounds-only',
                '--grid-resolution', str(grid_resolution),
                '--projection', projection
            ]
            
            logger.info(f"Scanning bounds for: {mesh_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Parse bounds from output
                for line in result.stdout.split('\n'):
                    if line.startswith('BOUNDS_JSON:'):
                        bounds_str = line.replace('BOUNDS_JSON:', '').strip()
                        return json.loads(bounds_str)
                        
                logger.error("Bounds not found in output")
                return None
            else:
                logger.error(f"Bounds scanning failed: {result.stderr}")
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
                metadata['saved_at'] = datetime.now().isoformat()
                metadata['image_path'] = self.active_yard_map_path
                
                with open(self.active_yard_map_json, 'w') as f:
                    json.dump(metadata, f, indent=2)
            
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