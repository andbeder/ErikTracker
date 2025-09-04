#!/usr/bin/env python3
"""
Rasterized yard map generator using cube projection with expanding search.
Creates a fixed 1280x720 pixel image with complete coverage.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for containers
import matplotlib.pyplot as plt
import argparse
import os
import sys
from PIL import Image
import io

try:
    import trimesh
    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False


def load_mesh_vertices(ply_path, max_points=100000):
    """Load mesh vertices and colors, sampling if too large."""
    if TRIMESH_AVAILABLE:
        try:
            mesh = trimesh.load(ply_path)
            vertices = mesh.vertices
            colors = None
            
            # Check if mesh has color data
            if hasattr(mesh.visual, 'vertex_colors') and mesh.visual.vertex_colors is not None:
                colors = mesh.visual.vertex_colors[:, :3]  # RGB only, drop alpha if present
                print(f"Found color data: {colors.shape}", flush=True)
            elif hasattr(mesh.visual, 'face_colors') and mesh.visual.face_colors is not None:
                print("Found face colors but no vertex colors")
            else:
                print("No color data found in mesh")
            
            # Sample if too many points
            if len(vertices) > max_points:
                indices = np.random.choice(len(vertices), max_points, replace=False)
                vertices = vertices[indices]
                if colors is not None:
                    colors = colors[indices]
                print(f"Sampled {max_points} vertices from {len(mesh.vertices)} total")
            
            return vertices, colors
        except Exception as e:
            print(f"Trimesh failed: {e}")
    
    return None, None


def project_to_2d(vertices, projection='xy'):
    """Project 3D vertices to 2D plane."""
    if projection == 'xy':
        return vertices[:, [0, 1]]  # Top-down view
    elif projection == 'xz':
        return vertices[:, [0, 2]]  # Side view
    elif projection == 'yz':
        return vertices[:, [1, 2]]  # Front view
    else:
        raise ValueError(f"Unknown projection: {projection}")


def create_raster_map(vertices, colors=None, projection='xy', grid_resolution=0.1):
    """Create a rasterized 1280x720 yard map using cube projection with expanding search.
    
    For each pixel in the 1280x720 image:
    1. Project a cube from pixel edges into 3D space
    2. Find all points within the cube
    3. If no points found, expand cube by 1 pixel and repeat
    4. Cluster points by height using grid_resolution as window
    5. Select lowest cluster (ground)
    6. Average colors within cluster
    """
    print(f"Creating rasterized map: 640x360 pixels, grid resolution: {grid_resolution}m")
    
    if vertices.shape[1] < 3:
        raise ValueError("Need 3D vertices for rasterization")
    
    # Get 2D projection coordinates (the plane we're viewing)
    vertices_2d = project_to_2d(vertices, projection)
    
    # Determine the depth axis (perpendicular to projection plane)
    if projection == 'xy':
        depth_values = vertices[:, 2]  # Z axis for XY projection
        depth_name = 'Z'
    elif projection == 'xz':
        depth_values = vertices[:, 1]  # Y axis for XZ projection  
        depth_name = 'Y'
    elif projection == 'yz':
        depth_values = vertices[:, 0]  # X axis for YZ projection
        depth_name = 'X'
    else:
        raise ValueError(f"Unknown projection: {projection}")
    
    # Calculate bounds of 3D data
    x_min, x_max = vertices_2d[:, 0].min(), vertices_2d[:, 0].max()
    y_min, y_max = vertices_2d[:, 1].min(), vertices_2d[:, 1].max()
    
    print(f"Data bounds: X=[{x_min:.2f}, {x_max:.2f}], Y=[{y_min:.2f}, {y_max:.2f}] meters")
    print(f"Depth axis: {depth_name}, clustering window: {grid_resolution}m")
    
    # Fixed raster dimensions
    RASTER_WIDTH = 640
    RASTER_HEIGHT = 360
    
    # Calculate pixel size in world units
    pixel_width = (x_max - x_min) / RASTER_WIDTH
    pixel_height = (y_max - y_min) / RASTER_HEIGHT
    
    print(f"Pixel size: {pixel_width:.4f}m x {pixel_height:.4f}m")
    
    # Initialize output image
    raster_image = np.zeros((RASTER_HEIGHT, RASTER_WIDTH, 3), dtype=np.uint8)
    
    # Process each pixel
    pixels_processed = 0
    expansions_needed = 0
    max_expansion = 0
    total_points_found = 0
    max_points_in_pixel = 0
    
    import time
    start_time = time.time()
    
    for row in range(RASTER_HEIGHT):
        for col in range(RASTER_WIDTH):
            # Calculate world coordinates for this pixel
            pixel_x_min = x_min + col * pixel_width
            pixel_x_max = x_min + (col + 1) * pixel_width
            pixel_y_min = y_max - (row + 1) * pixel_height  # Image Y is flipped
            pixel_y_max = y_max - row * pixel_height
            
            # Start with 1-pixel cube
            expansion = 0
            found_points = False
            
            while not found_points and expansion <= 10:  # Max 10 pixel expansion
                # Calculate expanded cube bounds
                expanded_x_min = pixel_x_min - expansion * pixel_width
                expanded_x_max = pixel_x_max + expansion * pixel_width
                expanded_y_min = pixel_y_min - expansion * pixel_height
                expanded_y_max = pixel_y_max + expansion * pixel_height
                
                # Find points within expanded cube
                within_cube = ((vertices_2d[:, 0] >= expanded_x_min) & 
                              (vertices_2d[:, 0] <= expanded_x_max) &
                              (vertices_2d[:, 1] >= expanded_y_min) & 
                              (vertices_2d[:, 1] <= expanded_y_max))
                
                if np.any(within_cube):
                    found_points = True
                    if expansion > 0:
                        expansions_needed += 1
                        max_expansion = max(max_expansion, expansion)
                else:
                    expansion += 1
            
            if found_points:
                # Get points and depths within cube
                cube_indices = np.where(within_cube)[0]
                cube_depths = depth_values[within_cube]
                
                # Track statistics
                num_points = len(cube_indices)
                total_points_found += num_points
                max_points_in_pixel = max(max_points_in_pixel, num_points)
                
                # Cluster points by height windows using grid_resolution
                depth_min, depth_max = cube_depths.min(), cube_depths.max()
                if depth_max - depth_min <= grid_resolution:
                    # All points in single cluster
                    clusters = [cube_indices]
                else:
                    # Create overlapping windows with grid_resolution as window size
                    clusters = []
                    window_start = depth_min
                    while window_start <= depth_max:
                        window_end = window_start + grid_resolution
                        in_window = (cube_depths >= window_start) & (cube_depths <= window_end)
                        if np.any(in_window):
                            clusters.append(cube_indices[in_window])
                        window_start += grid_resolution / 2  # 50% overlap for better coverage
                
                # Select cluster with lowest minimum height (ground)
                best_cluster = None
                best_min_depth = float('inf')
                
                for cluster_indices in clusters:
                    cluster_depths = depth_values[cluster_indices]
                    cluster_min = cluster_depths.min()
                    if cluster_min < best_min_depth:
                        best_min_depth = cluster_min
                        best_cluster = cluster_indices
                
                # Set pixel color from best cluster
                if best_cluster is not None and len(best_cluster) > 0:
                    if colors is not None:
                        # Average colors in the cluster
                        cluster_colors = colors[best_cluster]
                        avg_color = np.mean(cluster_colors, axis=0)
                        # Ensure color values are in 0-255 range
                        if avg_color.max() <= 1.0:
                            avg_color *= 255
                        raster_image[row, col] = avg_color.astype(np.uint8)
                    else:
                        # Use height-based coloring if no colors available
                        normalized_height = (best_min_depth - depth_values.min()) / (depth_values.max() - depth_values.min())
                        color_val = int(normalized_height * 255)
                        raster_image[row, col] = [color_val, color_val // 2, 100]  # Brown-ish terrain
            else:
                # No points found even with expansion - use fallback color
                raster_image[row, col] = [50, 50, 50]  # Dark gray
            
            pixels_processed += 1
            
            # Progress update every 5000 pixels with timing info
            if pixels_processed % 5000 == 0:
                progress = (pixels_processed / (RASTER_WIDTH * RASTER_HEIGHT)) * 100
                elapsed = time.time() - start_time
                pixels_per_sec = pixels_processed / elapsed if elapsed > 0 else 0
                eta_seconds = (RASTER_WIDTH * RASTER_HEIGHT - pixels_processed) / pixels_per_sec if pixels_per_sec > 0 else 0
                print(f"Rasterizing: {progress:.1f}% complete, {pixels_per_sec:.0f} pixels/sec, ETA: {eta_seconds:.0f}s")
    
    end_time = time.time()
    total_time = end_time - start_time
    avg_points_per_pixel = total_points_found / pixels_processed if pixels_processed > 0 else 0
    
    print(f"Rasterization complete!")
    print(f"Total time: {total_time:.1f} seconds")
    print(f"Pixels per second: {pixels_processed / total_time:.0f}")
    print(f"Pixels requiring expansion: {expansions_needed}")
    print(f"Maximum expansion needed: {max_expansion} pixels")
    print(f"Average points per pixel: {avg_points_per_pixel:.1f}")
    print(f"Maximum points in a single pixel: {max_points_in_pixel}")
    print(f"Total point-pixel intersections: {total_points_found}")
    
    return raster_image


def main():
    print("Starting rasterized yard map generation", flush=True)
    parser = argparse.ArgumentParser(description='Generate rasterized yard maps (640x360) with cube projection')
    parser.add_argument('input', help='Input PLY mesh file path')
    parser.add_argument('--output', '-o', default='yard_map_raster.png', help='Output image path')
    parser.add_argument('--grid-resolution', type=float, default=0.1, help='Grid resolution in meters (default: 0.1m)')
    parser.add_argument('--max-points', type=int, default=100000, 
                       help='Maximum points to process for performance (default: 100000)')
    parser.add_argument('--projection', '-p', choices=['xy', 'xz', 'yz'], 
                       default='xy', help='Projection plane: xy=top-down, xz=side, yz=front (default: xy)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        return 1
    
    print(f"Loading mesh for rasterization: {args.input}")
    
    vertices, colors = load_mesh_vertices(args.input, args.max_points)
    if vertices is None:
        print("Failed to load mesh vertices")
        return 1
    
    print(f"Loaded {len(vertices)} vertices for rasterization")
    if colors is not None:
        print(f"Found true color data: {colors.shape} - will use for pixel colors")
    else:
        print("No color data found - will use height-based coloring")
        
    if vertices.shape[1] > 2:
        z_min, z_max = vertices[:, 2].min(), vertices[:, 2].max()
        print(f"Mesh height range: [{z_min:.2f}, {z_max:.2f}] meters")
    
    print(f"Generating rasterized yard map...")
    print(f"  Output size: 640x360 pixels")
    print(f"  Projection: {args.projection}")
    print(f"  Grid resolution: {args.grid_resolution}m")
    
    try:
        raster_image = create_raster_map(vertices, colors, args.projection, args.grid_resolution)
        
        # Save as PNG using PIL
        pil_image = Image.fromarray(raster_image, 'RGB')
        pil_image.save(args.output, 'PNG')
        
        # Verify file was created and get size
        if os.path.exists(args.output):
            file_size = os.path.getsize(args.output) / 1024  # KB
            print(f"Rasterized map saved: {args.output} ({file_size:.1f} KB)")
        else:
            raise FileNotFoundError(f"Failed to save output file: {args.output}")
        
        print("Done!")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())