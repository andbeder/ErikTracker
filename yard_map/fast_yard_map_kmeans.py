#!/usr/bin/env python3
"""
K-means based yard map generator using height clustering to separate ground from foliage.
Creates a fixed 640x360 pixel image with complete coverage.
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
import time
from scipy.spatial import cKDTree
from sklearn.cluster import KMeans

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


def create_kmeans_raster_map(vertices, colors=None, projection='xy', grid_resolution=0.1):
    """Create a rasterized 640x360 yard map using K-means height clustering.
    
    For each pixel:
    1. Find all points in the pixel cube
    2. Use K-means (N=2) on height values to separate ground from foliage/sky
    3. Select the cluster with lower mean height (ground)
    4. Average colors of ground points
    """
    print(f"Creating K-means rasterized map: 640x360 pixels, grid resolution: {grid_resolution}m")
    
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
    print(f"Depth axis: {depth_name}, K-means clustering on heights")
    
    # Fixed raster dimensions
    RASTER_WIDTH = 640
    RASTER_HEIGHT = 360
    
    # Calculate pixel size in world units
    pixel_width = (x_max - x_min) / RASTER_WIDTH
    pixel_height = (y_max - y_min) / RASTER_HEIGHT
    
    print(f"Pixel size: {pixel_width:.4f}m x {pixel_height:.4f}m")
    
    # Build spatial index for fast nearest neighbor queries
    print("Building spatial index...")
    start_index_time = time.time()
    tree = cKDTree(vertices_2d)
    print(f"Spatial index built in {time.time() - start_index_time:.2f} seconds")
    
    # Initialize output image
    raster_image = np.zeros((RASTER_HEIGHT, RASTER_WIDTH, 3), dtype=np.uint8)
    
    print("Processing pixels with K-means clustering...")
    start_time = time.time()
    
    pixels_processed = 0
    total_pixels = RASTER_HEIGHT * RASTER_WIDTH
    max_points_in_pixel = 0
    total_points_found = 0
    successful_kmeans = 0
    
    for row in range(RASTER_HEIGHT):
        for col in range(RASTER_WIDTH):
            # Calculate pixel boundaries in world coordinates
            pixel_x_min = x_min + col * pixel_width
            pixel_x_max = x_min + (col + 1) * pixel_width
            pixel_y_min = y_max - (row + 1) * pixel_height  # Image Y is flipped
            pixel_y_max = y_max - row * pixel_height
            
            # Find points within the pixel cube (start with cube, expand if needed)
            within_cube = ((vertices_2d[:, 0] >= pixel_x_min) & 
                          (vertices_2d[:, 0] <= pixel_x_max) &
                          (vertices_2d[:, 1] >= pixel_y_min) & 
                          (vertices_2d[:, 1] <= pixel_y_max))
            
            cube_indices = np.where(within_cube)[0]
            
            # If no points in cube, expand search using spatial index
            if len(cube_indices) == 0:
                pixel_center = [(pixel_x_min + pixel_x_max) / 2, (pixel_y_min + pixel_y_max) / 2]
                # Start with pixel diagonal distance
                search_radius = np.sqrt(pixel_width**2 + pixel_height**2) / 2
                
                for expansion in range(5):  # Max 5 expansions
                    cube_indices = tree.query_ball_point(pixel_center, search_radius)
                    if len(cube_indices) > 0:
                        break
                    search_radius *= 2
            
            if len(cube_indices) > 0:
                # Get heights for K-means clustering
                cube_heights = depth_values[cube_indices]
                
                # Track statistics
                num_points = len(cube_indices)
                total_points_found += num_points
                max_points_in_pixel = max(max_points_in_pixel, num_points)
                
                # Ground selection using K-means on height
                if num_points >= 2:  # Need at least 2 points for K-means
                    try:
                        # Reshape heights for sklearn
                        heights_2d = cube_heights.reshape(-1, 1)
                        
                        # K-means with N=2 clusters
                        kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
                        cluster_labels = kmeans.fit_predict(heights_2d)
                        cluster_centers = kmeans.cluster_centers_.flatten()
                        
                        # Select cluster with lower mean height (ground)
                        ground_cluster_id = np.argmin(cluster_centers)
                        ground_mask = cluster_labels == ground_cluster_id
                        ground_indices = np.array(cube_indices)[ground_mask]
                        
                        successful_kmeans += 1
                        
                    except Exception:
                        # Fallback: use all points if K-means fails
                        ground_indices = cube_indices
                else:
                    # Use the single point we have
                    ground_indices = cube_indices
                
                # Set pixel color by averaging ground points
                if len(ground_indices) > 0:
                    if colors is not None:
                        # Average colors of ground points
                        ground_colors = colors[ground_indices]
                        avg_color = np.mean(ground_colors, axis=0)
                        # Ensure color values are in 0-255 range
                        if avg_color.max() <= 1.0:
                            avg_color *= 255
                        raster_image[row, col] = avg_color.astype(np.uint8)
                    else:
                        # Use height-based coloring if no colors available
                        avg_height = np.mean(depth_values[ground_indices])
                        normalized_height = (avg_height - depth_values.min()) / (depth_values.max() - depth_values.min())
                        color_val = int(normalized_height * 255)
                        raster_image[row, col] = [color_val, color_val // 2, 100]  # Brown-ish terrain
                else:
                    # No ground points - use fallback
                    raster_image[row, col] = [50, 50, 50]  # Dark gray
            else:
                # No points found - use fallback color
                raster_image[row, col] = [50, 50, 50]  # Dark gray
            
            pixels_processed += 1
            
            # Progress update every 5000 pixels
            if pixels_processed % 5000 == 0:
                progress = (pixels_processed / total_pixels) * 100
                elapsed = time.time() - start_time
                pixels_per_sec = pixels_processed / elapsed if elapsed > 0 else 0
                eta_seconds = (total_pixels - pixels_processed) / pixels_per_sec if pixels_per_sec > 0 else 0
                print(f"K-means rasterizing: {progress:.1f}% complete, {pixels_per_sec:.0f} pixels/sec, ETA: {eta_seconds:.0f}s")
    
    end_time = time.time()
    total_time = end_time - start_time
    avg_points_per_pixel = total_points_found / pixels_processed if pixels_processed > 0 else 0
    kmeans_success_rate = (successful_kmeans / pixels_processed) * 100
    
    print(f"K-means rasterization complete!")
    print(f"Total time: {total_time:.1f} seconds")
    print(f"Pixels per second: {pixels_processed / total_time:.0f}")
    print(f"Average points per pixel: {avg_points_per_pixel:.1f}")
    print(f"Maximum points in a single pixel: {max_points_in_pixel}")
    print(f"K-means clustering success rate: {kmeans_success_rate:.1f}%")
    
    return raster_image


def main():
    print("Starting K-means rasterized yard map generation", flush=True)
    parser = argparse.ArgumentParser(description='Generate K-means rasterized yard maps (640x360) with height clustering')
    parser.add_argument('input', help='Input PLY mesh file path')
    parser.add_argument('--output', '-o', default='yard_map_kmeans.png', help='Output image path')
    parser.add_argument('--grid-resolution', type=float, default=0.1, help='Grid resolution in meters (default: 0.1m)')
    parser.add_argument('--max-points', type=int, default=100000, 
                       help='Maximum points to process for performance (default: 100000)')
    parser.add_argument('--projection', '-p', choices=['xy', 'xz', 'yz'], 
                       default='xy', help='Projection plane: xy=top-down, xz=side, yz=front (default: xy)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        return 1
    
    print(f"Loading mesh for K-means rasterization: {args.input}")
    
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
    
    print(f"Generating K-means rasterized yard map...")
    print(f"  Output size: 640x360 pixels")
    print(f"  Projection: {args.projection}")
    print(f"  Grid resolution: {args.grid_resolution}m")
    print(f"  K-means clusters: N=2 (ground vs foliage/sky)")
    
    try:
        raster_image = create_kmeans_raster_map(vertices, colors, args.projection, args.grid_resolution)
        
        # Save as PNG using PIL
        pil_image = Image.fromarray(raster_image, 'RGB')
        pil_image.save(args.output, 'PNG')
        
        # Verify file was created and get size
        if os.path.exists(args.output):
            file_size = os.path.getsize(args.output) / 1024  # KB
            print(f"K-means rasterized map saved: {args.output} ({file_size:.1f} KB)")
        else:
            raise FileNotFoundError(f"Failed to save output file: {args.output}")
        
        print("Done!")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())