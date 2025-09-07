"""
Pixel Mapping Service
Handles ray-casting from camera pixels to ground terrain for accurate yard map positioning
"""

import os
import json
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import logging
from pathlib import Path
import struct

logger = logging.getLogger(__name__)


class PixelMappingService:
    """Service for mapping camera pixels to yard map coordinates via ray-casting"""
    
    def __init__(self):
        self.camera_configs = {}
        self.yard_map_config = None
        self.ground_heights = {}
        self.pixel_mappings = {}
        
        # Default camera intrinsics (can be overridden per camera)
        self.default_camera_params = {
            'image_width': 1920,
            'image_height': 1080,
            'focal_length': 1000,  # In pixels, typical for ~60 degree FOV
            'principal_point': (960, 540)  # Image center
        }
    
    def load_yard_map_config(self, config_path: str = 'config/yard_map_config.json') -> Dict:
        """Load yard map configuration from file"""
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    self.yard_map_config = json.load(f)
                    logger.info(f"Loaded yard map config: {self.yard_map_config}")
            else:
                # Default configuration
                self.yard_map_config = {
                    'image_width': 1280,
                    'image_height': 720,
                    'center_x': 0.0,
                    'center_y': 0.0,
                    'projection': 'xz',
                    'rotation_degrees': 0,
                    'scale_meters_per_pixel': 0.01
                }
                logger.warning(f"Using default yard map config")
            
            return self.yard_map_config
        except Exception as e:
            logger.error(f"Error loading yard map config: {e}")
            return None
    
    def world_to_yard_map_pixel(self, world_point: np.ndarray, config: Dict = None) -> Dict[str, float]:
        """
        Transform 3D world coordinates to 2D yard map pixel coordinates
        
        Args:
            world_point: 3D point in world coordinates [x, y, z]
            config: Yard map configuration (uses self.yard_map_config if None)
        
        Returns:
            Dictionary with 'x' and 'y' pixel coordinates
        """
        if config is None:
            config = self.yard_map_config
        
        if config is None:
            raise ValueError("Yard map configuration not loaded")
        
        # Extract projection plane coordinates
        if config['projection'] == 'xz':
            world_x = world_point[0]
            world_y = world_point[2]  # Z becomes Y in 2D
        elif config['projection'] == 'xy':
            world_x = world_point[0]
            world_y = world_point[1]
        else:
            raise ValueError(f"Unknown projection: {config['projection']}")
        
        # Apply rotation around center
        angle_rad = np.radians(config.get('rotation_degrees', 0))
        dx = world_x - config.get('center_x', 0)
        dy = world_y - config.get('center_y', 0)
        
        rotated_x = dx * np.cos(angle_rad) - dy * np.sin(angle_rad)
        rotated_y = dx * np.sin(angle_rad) + dy * np.cos(angle_rad)
        
        # Convert to pixel coordinates
        pixel_x = (rotated_x / config['scale_meters_per_pixel']) + (config['image_width'] / 2)
        pixel_y = (config['image_height'] / 2) - (rotated_y / config['scale_meters_per_pixel'])
        
        return {'x': pixel_x, 'y': pixel_y}
    
    def yard_map_pixel_to_world(self, pixel_x: float, pixel_y: float, height: float = 0.0) -> np.ndarray:
        """
        Transform 2D yard map pixel to 3D world coordinates
        
        Args:
            pixel_x: X pixel coordinate in yard map
            pixel_y: Y pixel coordinate in yard map
            height: Height (Y) value in world coordinates
        
        Returns:
            3D point in world coordinates [x, y, z]
        """
        config = self.yard_map_config
        if config is None:
            raise ValueError("Yard map configuration not loaded")
        
        # Convert pixel to relative coordinates
        rel_x = (pixel_x - config['image_width'] / 2) * config['scale_meters_per_pixel']
        rel_y = (config['image_height'] / 2 - pixel_y) * config['scale_meters_per_pixel']
        
        # Apply inverse rotation
        angle_rad = -np.radians(config.get('rotation_degrees', 0))
        world_x = rel_x * np.cos(angle_rad) - rel_y * np.sin(angle_rad)
        world_y = rel_x * np.sin(angle_rad) + rel_y * np.cos(angle_rad)
        
        # Add center offset
        world_x += config.get('center_x', 0)
        world_y += config.get('center_y', 0)
        
        # Create 3D point based on projection
        if config['projection'] == 'xz':
            return np.array([world_x, height, world_y])
        elif config['projection'] == 'xy':
            return np.array([world_x, world_y, height])
        else:
            raise ValueError(f"Unknown projection: {config['projection']}")
    
    def build_ground_height_map(self, point_cloud_path: str, percentile: float = 20) -> Dict:
        """
        Build a height map of the ground from point cloud data
        
        Args:
            point_cloud_path: Path to point cloud file (PLY format)
            percentile: Percentile to use for ground height (default 20 for lowest 20%)
        
        Returns:
            Dictionary mapping yard map pixels to ground heights
        """
        try:
            logger.info(f"Building ground height map from {point_cloud_path}")
            
            # Load point cloud
            points = self.load_point_cloud(point_cloud_path)
            if points is None or len(points) == 0:
                logger.error("No points loaded from point cloud")
                return {}
            
            # Group points by yard map pixel
            height_map = {}
            for point in points:
                # Transform to yard map pixel
                pixel = self.world_to_yard_map_pixel(point)
                pixel_key = (int(pixel['x']), int(pixel['y']))
                
                # Check if pixel is within map bounds
                if (0 <= pixel_key[0] < self.yard_map_config['image_width'] and
                    0 <= pixel_key[1] < self.yard_map_config['image_height']):
                    
                    if pixel_key not in height_map:
                        height_map[pixel_key] = []
                    height_map[pixel_key].append(point[1])  # Y is height
            
            # Calculate ground height for each pixel
            ground_heights = {}
            for pixel_key, heights in height_map.items():
                if heights:
                    # Use percentile to find ground level
                    ground_height = np.percentile(heights, percentile)
                    ground_heights[pixel_key] = ground_height
            
            logger.info(f"Built ground height map with {len(ground_heights)} pixels")
            self.ground_heights = ground_heights
            return ground_heights
            
        except Exception as e:
            logger.error(f"Error building ground height map: {e}")
            return {}
    
    def load_point_cloud(self, file_path: str) -> np.ndarray:
        """Load point cloud from PLY file (binary or ASCII)"""
        try:
            points = []
            with open(file_path, 'rb') as f:
                # Read PLY header
                line = f.readline().decode('utf-8').strip()
                if line != 'ply':
                    logger.error("Not a valid PLY file")
                    return None
                
                # Parse header
                vertex_count = 0
                header_end = False
                properties = []
                format_type = None
                
                while not header_end:
                    line = f.readline().decode('utf-8').strip()
                    if line.startswith('format'):
                        format_type = line.split()[1]
                    elif line.startswith('element vertex'):
                        vertex_count = int(line.split()[2])
                    elif line.startswith('property'):
                        parts = line.split()
                        prop_type = parts[1]
                        prop_name = parts[2] if len(parts) > 2 else parts[-1]
                        properties.append((prop_type, prop_name))
                    elif line == 'end_header':
                        header_end = True
                
                logger.info(f"Loading PLY with {vertex_count} vertices, format: {format_type}")
                
                # Read vertices based on format
                if format_type and 'binary' in format_type:
                    # Binary format
                    import struct
                    
                    # Determine byte order
                    if 'little' in format_type:
                        endian = '<'
                    else:
                        endian = '>'
                    
                    # Build format string for struct.unpack
                    format_str = endian
                    for prop_type, prop_name in properties:
                        if prop_type == 'float':
                            format_str += 'f'
                        elif prop_type == 'double':
                            format_str += 'd'
                        elif prop_type == 'uchar':
                            format_str += 'B'
                        elif prop_type == 'char':
                            format_str += 'b'
                        elif prop_type == 'ushort':
                            format_str += 'H'
                        elif prop_type == 'short':
                            format_str += 'h'
                        elif prop_type == 'uint':
                            format_str += 'I'
                        elif prop_type == 'int':
                            format_str += 'i'
                    
                    bytes_per_vertex = struct.calcsize(format_str)
                    
                    # Read vertices (sample for large files)
                    sample_rate = max(1, vertex_count // 100000)  # Sample to get ~100k points max
                    sampled_count = 0
                    
                    for i in range(vertex_count):
                        vertex_bytes = f.read(bytes_per_vertex)
                        if len(vertex_bytes) < bytes_per_vertex:
                            break
                        
                        # Sample points to reduce memory usage
                        if i % sample_rate == 0:
                            vertex_data = struct.unpack(format_str, vertex_bytes)
                            # Get x, y, z (first 3 floats)
                            if len(vertex_data) >= 3:
                                x, y, z = vertex_data[0:3]
                                points.append(np.array([x, y, z]))
                                sampled_count += 1
                    
                    logger.info(f"Loaded {sampled_count} points (sampled every {sample_rate} vertices)")
                    
                else:
                    # ASCII format
                    for i in range(min(vertex_count, 100000)):  # Limit to 100k points
                        line = f.readline().decode('utf-8').strip()
                        if not line:
                            break
                        vertex_data = line.split()
                        if len(vertex_data) >= 3:
                            x = float(vertex_data[0])
                            y = float(vertex_data[1])
                            z = float(vertex_data[2])
                            points.append(np.array([x, y, z]))
            
            return np.array(points) if points else None
            
        except Exception as e:
            logger.error(f"Error loading point cloud: {e}")
            return None
    
    def generate_camera_ray(self, u: int, v: int, camera_config: Dict) -> Dict:
        """
        Generate a ray from camera origin through a pixel
        
        Args:
            u: Pixel column (x)
            v: Pixel row (y)
            camera_config: Camera configuration including pose and intrinsics
        
        Returns:
            Dictionary with 'origin' and 'direction' as numpy arrays
        """
        # Get camera intrinsics
        fx = camera_config.get('focal_length', self.default_camera_params['focal_length'])
        fy = fx  # Assume square pixels
        cx = camera_config.get('principal_point', self.default_camera_params['principal_point'])[0]
        cy = camera_config.get('principal_point', self.default_camera_params['principal_point'])[1]
        
        # Convert pixel to normalized camera coordinates
        x_cam = (u - cx) / fx
        y_cam = (v - cy) / fy
        z_cam = 1.0
        
        # Ray in camera space
        ray_camera = np.array([x_cam, y_cam, z_cam])
        ray_camera = ray_camera / np.linalg.norm(ray_camera)
        
        # Get camera transformation matrix
        transform = np.array(camera_config['transformation_matrix'])
        rotation = transform[:3, :3]
        position = transform[:3, 3]
        
        # Transform ray to world space
        ray_world = rotation @ ray_camera
        ray_world = ray_world / np.linalg.norm(ray_world)
        
        return {
            'origin': position,
            'direction': ray_world
        }
    
    def find_ground_intersection(self, ray_origin: np.ndarray, ray_direction: np.ndarray,
                                ground_heights: Dict = None) -> Optional[Dict]:
        """
        Find intersection of ray with ground terrain
        
        Args:
            ray_origin: Ray starting point in world coordinates
            ray_direction: Ray direction vector (normalized)
            ground_heights: Ground height map (uses self.ground_heights if None)
        
        Returns:
            Dictionary with intersection details or None if no intersection
        """
        if ground_heights is None:
            ground_heights = self.ground_heights
        
        if not ground_heights:
            logger.warning("No ground height data available")
            return None
        
        # Ray marching parameters
        step_size = 0.02  # meters
        max_distance = 50.0  # meters
        
        for t in np.arange(step_size, max_distance, step_size):
            # Current point along ray
            world_point = ray_origin + t * ray_direction
            
            # Convert to yard map pixel
            try:
                map_pixel = self.world_to_yard_map_pixel(world_point)
                pixel_key = (int(map_pixel['x']), int(map_pixel['y']))
                
                # Check if we have ground height for this pixel
                if pixel_key in ground_heights:
                    ground_height = ground_heights[pixel_key]
                    
                    # Check if ray has hit ground (with small tolerance)
                    if world_point[1] <= ground_height + 0.01:
                        return {
                            'world_point': world_point,
                            'yard_map_pixel': map_pixel,
                            'ground_height': ground_height,
                            'distance': t,
                            'confidence': self.calculate_confidence(t, world_point[1] - ground_height)
                        }
                
                # Also check neighboring pixels for better coverage
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        neighbor_key = (pixel_key[0] + dx, pixel_key[1] + dy)
                        if neighbor_key in ground_heights:
                            ground_height = ground_heights[neighbor_key]
                            if world_point[1] <= ground_height + 0.01:
                                return {
                                    'world_point': world_point,
                                    'yard_map_pixel': map_pixel,
                                    'ground_height': ground_height,
                                    'distance': t,
                                    'confidence': self.calculate_confidence(t, world_point[1] - ground_height)
                                }
                
            except Exception as e:
                logger.debug(f"Error processing ray at t={t}: {e}")
                continue
        
        return None
    
    def calculate_confidence(self, distance: float, height_diff: float) -> float:
        """
        Calculate confidence score for a pixel mapping
        
        Args:
            distance: Distance from camera to intersection
            height_diff: Difference between ray height and ground height
        
        Returns:
            Confidence score between 0 and 1
        """
        # Confidence decreases with distance
        distance_factor = max(0, 1 - (distance / 30.0))  # 30m max confidence range
        
        # Confidence decreases with height uncertainty
        height_factor = max(0, 1 - abs(height_diff) * 10)  # 0.1m tolerance
        
        return distance_factor * height_factor
    
    def generate_pixel_mapping(self, camera_name: str, camera_config: Dict,
                              sample_rate: int = 10) -> Dict:
        """
        Generate complete pixel mapping for a camera
        
        Args:
            camera_name: Name of the camera
            camera_config: Camera configuration including pose and intrinsics
            sample_rate: Sample every Nth pixel for faster processing (default 10)
        
        Returns:
            Dictionary with pixel mapping data
        """
        logger.info(f"Generating pixel mapping for camera {camera_name} with sample rate {sample_rate}")
        
        # Get camera resolution
        width = camera_config.get('image_width', self.default_camera_params['image_width'])
        height = camera_config.get('image_height', self.default_camera_params['image_height'])
        
        pixel_mapping = {}
        valid_mappings = 0
        
        # Debug: test center pixel
        if sample_rate > 0:
            center_ray = self.generate_camera_ray(width//2, height//2, camera_config)
            logger.debug(f"Center pixel ray - origin: {center_ray['origin']}, direction: {center_ray['direction']}")
            
            # Check ground heights
            if self.ground_heights:
                sample_heights = list(self.ground_heights.values())[:10]
                logger.debug(f"Sample ground heights: {sample_heights}")
                logger.debug(f"Total ground height pixels: {len(self.ground_heights)}")
        
        # Sample pixels across the image
        for v in range(0, height, sample_rate):
            for u in range(0, width, sample_rate):
                # Generate ray for this pixel
                ray = self.generate_camera_ray(u, v, camera_config)
                
                # Find ground intersection
                intersection = self.find_ground_intersection(
                    ray['origin'],
                    ray['direction']
                )
                
                if intersection:
                    pixel_key = f"{u},{v}"
                    pixel_mapping[pixel_key] = {
                        'yard_map_x': int(intersection['yard_map_pixel']['x']),
                        'yard_map_y': int(intersection['yard_map_pixel']['y']),
                        'confidence': intersection['confidence'],
                        'distance': intersection['distance']
                    }
                    valid_mappings += 1
                    
                    # Debug first valid mapping
                    if valid_mappings == 1:
                        logger.debug(f"First valid mapping at pixel ({u},{v}): {pixel_mapping[pixel_key]}")
            
            # Progress update
            if v % 100 == 0:
                logger.debug(f"Processed row {v}/{height}, valid mappings: {valid_mappings}")
        
        # Store the mapping
        self.pixel_mappings[camera_name] = {
            'camera_name': camera_name,
            'yard_map_config': self.yard_map_config,
            'camera_resolution': {'width': width, 'height': height},
            'sample_rate': sample_rate,
            'camera_to_yard_mapping': pixel_mapping,
            'valid_pixel_count': valid_mappings,
            'total_sampled_pixels': (width // sample_rate) * (height // sample_rate)
        }
        
        logger.info(f"Generated {valid_mappings} valid pixel mappings for {camera_name}")
        return self.pixel_mappings[camera_name]
    
    def interpolate_pixel(self, u: float, v: float, camera_name: str) -> Optional[Dict]:
        """
        Get yard map coordinates for a pixel using interpolation
        
        Args:
            u: Pixel column
            v: Pixel row
            camera_name: Camera name
        
        Returns:
            Interpolated yard map coordinates or None
        """
        if camera_name not in self.pixel_mappings:
            logger.error(f"No pixel mapping for camera {camera_name}")
            return None
        
        mapping = self.pixel_mappings[camera_name]
        sample_rate = mapping['sample_rate']
        
        # Find nearest sampled pixels
        u_base = (int(u) // sample_rate) * sample_rate
        v_base = (int(v) // sample_rate) * sample_rate
        
        # Get the four surrounding sample points
        corners = []
        for du in [0, sample_rate]:
            for dv in [0, sample_rate]:
                key = f"{u_base + du},{v_base + dv}"
                if key in mapping['camera_to_yard_mapping']:
                    corners.append(mapping['camera_to_yard_mapping'][key])
        
        if len(corners) < 4:
            # Fall back to nearest neighbor
            key = f"{u_base},{v_base}"
            if key in mapping['camera_to_yard_mapping']:
                return mapping['camera_to_yard_mapping'][key]
            return None
        
        # Bilinear interpolation
        fx = (u - u_base) / sample_rate
        fy = (v - v_base) / sample_rate
        
        # Interpolate X coordinate
        x_top = corners[0]['yard_map_x'] * (1 - fx) + corners[1]['yard_map_x'] * fx
        x_bottom = corners[2]['yard_map_x'] * (1 - fx) + corners[3]['yard_map_x'] * fx
        x_final = x_top * (1 - fy) + x_bottom * fy
        
        # Interpolate Y coordinate
        y_top = corners[0]['yard_map_y'] * (1 - fx) + corners[1]['yard_map_y'] * fx
        y_bottom = corners[2]['yard_map_y'] * (1 - fx) + corners[3]['yard_map_y'] * fx
        y_final = y_top * (1 - fy) + y_bottom * fy
        
        # Average confidence
        avg_confidence = sum(c['confidence'] for c in corners) / len(corners)
        
        return {
            'yard_map_x': int(x_final),
            'yard_map_y': int(y_final),
            'confidence': avg_confidence,
            'interpolated': True
        }
    
    def save_mapping(self, camera_name: str, output_path: str = None) -> bool:
        """Save pixel mapping to file"""
        try:
            if camera_name not in self.pixel_mappings:
                logger.error(f"No mapping for camera {camera_name}")
                return False
            
            if output_path is None:
                output_path = f"config/pixel_mappings/{camera_name}_mapping.json"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(self.pixel_mappings[camera_name], f, indent=2)
            
            logger.info(f"Saved pixel mapping to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving pixel mapping: {e}")
            return False
    
    def load_mapping(self, camera_name: str, input_path: str = None) -> bool:
        """Load pixel mapping from file"""
        try:
            if input_path is None:
                input_path = f"config/pixel_mappings/{camera_name}_mapping.json"
            
            if not os.path.exists(input_path):
                logger.error(f"Mapping file not found: {input_path}")
                return False
            
            with open(input_path, 'r') as f:
                self.pixel_mappings[camera_name] = json.load(f)
            
            logger.info(f"Loaded pixel mapping from {input_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading pixel mapping: {e}")
            return False