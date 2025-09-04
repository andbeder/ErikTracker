#!/usr/bin/env python3
"""
Ultra-fast yard map generator using vectorized operations and simple height thresholding.
Designed for speed - processes all pixels simultaneously using numpy vectorization.
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


def create_ultra_fast_raster_map(vertices, colors=None, projection='xy', grid_resolution=0.1, height_window=None):
    """Create ultra-fast rasterized 640x360 yard map using vectorized operations.
    
    Strategy:
    1. Pre-compute all pixel assignments for all points
    2. Use vectorized operations to process all pixels at once
    3. If height_window specified: simple average if points within window, else lowest point
    4. If no height_window: simple height thresholding 
    """
    print(f"Creating ultra-fast rasterized map: 640x360 pixels, grid resolution: {grid_resolution}m")
    
    if vertices.shape[1] < 3:
        raise ValueError("Need 3D vertices for rasterization")
    
    start_time = time.time()
    
    # Get 2D projection coordinates and depths
    vertices_2d = project_to_2d(vertices, projection)
    
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
    
    # Calculate bounds
    x_min, x_max = vertices_2d[:, 0].min(), vertices_2d[:, 0].max()
    y_min, y_max = vertices_2d[:, 1].min(), vertices_2d[:, 1].max()
    
    print(f"Data bounds: X=[{x_min:.2f}, {x_max:.2f}], Y=[{y_min:.2f}, {y_max:.2f}] meters")
    print(f"Depth axis: {depth_name}, height range: [{depth_values.min():.2f}, {depth_values.max():.2f}]")
    
    # Fixed raster dimensions
    RASTER_WIDTH = 640
    RASTER_HEIGHT = 360
    
    # Calculate pixel size
    pixel_width = (x_max - x_min) / RASTER_WIDTH
    pixel_height = (y_max - y_min) / RASTER_HEIGHT
    
    print(f"Pixel size: {pixel_width:.4f}m x {pixel_height:.4f}m")
    print("Computing pixel assignments for all points...")
    
    # Vectorized pixel assignment for ALL points at once
    pixel_x = np.floor((vertices_2d[:, 0] - x_min) / pixel_width).astype(np.int32)
    pixel_y = np.floor((y_max - vertices_2d[:, 1]) / pixel_height).astype(np.int32)
    
    # Clamp to valid pixel ranges
    pixel_x = np.clip(pixel_x, 0, RASTER_WIDTH - 1)
    pixel_y = np.clip(pixel_y, 0, RASTER_HEIGHT - 1)
    
    # Convert to linear indices
    pixel_indices = pixel_y * RASTER_WIDTH + pixel_x
    
    print("Processing pixels with vectorized operations...")
    
    # Initialize output image
    raster_image = np.zeros((RASTER_HEIGHT * RASTER_WIDTH, 3), dtype=np.float32)
    pixel_counts = np.zeros(RASTER_HEIGHT * RASTER_WIDTH, dtype=np.int32)
    
    # Group points by pixel and compute statistics
    unique_pixels, inverse_indices = np.unique(pixel_indices, return_inverse=True)
    
    print(f"Found {len(unique_pixels)} non-empty pixels out of {RASTER_HEIGHT * RASTER_WIDTH} total pixels")
    
    for i, pixel_idx in enumerate(unique_pixels):
        # Get all points in this pixel
        point_mask = inverse_indices == i
        pixel_depths = depth_values[point_mask]
        
        # Simple ground selection: take bottom 30% by height
        if len(pixel_depths) > 3:
            # Sort depths and take bottom 30%
            sorted_depths = np.sort(pixel_depths)
            ground_threshold = sorted_depths[int(len(sorted_depths) * 0.3)]
            ground_mask = pixel_depths <= ground_threshold
            
            # Get indices of ground points
            ground_point_indices = np.where(point_mask)[0][ground_mask]
        else:
            # Use all points if we have few
            ground_point_indices = np.where(point_mask)[0]
        
        # Compute average color for ground points
        if len(ground_point_indices) > 0:
            if colors is not None:
                avg_color = np.mean(colors[ground_point_indices], axis=0)
                if avg_color.max() <= 1.0:
                    avg_color *= 255
                raster_image[pixel_idx] = avg_color
            else:
                # Height-based coloring
                avg_height = np.mean(depth_values[ground_point_indices])
                normalized = (avg_height - depth_values.min()) / (depth_values.max() - depth_values.min())
                color_val = int(normalized * 255)
                raster_image[pixel_idx] = [color_val, color_val * 0.7, color_val * 0.5]
            
            pixel_counts[pixel_idx] = len(ground_point_indices)
    
    # Fill empty pixels with nearest neighbor
    empty_pixels = pixel_counts == 0
    if np.any(empty_pixels):
        print(f"Filling {np.sum(empty_pixels)} empty pixels with nearest neighbors...")
        
        # Create coordinate grids
        y_coords, x_coords = np.mgrid[0:RASTER_HEIGHT, 0:RASTER_WIDTH]
        empty_coords = np.column_stack([y_coords[empty_pixels], x_coords[empty_pixels]])
        filled_coords = np.column_stack([y_coords[~empty_pixels], x_coords[~empty_pixels]])
        
        if len(filled_coords) > 0:
            # Simple nearest neighbor assignment
            from scipy.spatial.distance import cdist
            distances = cdist(empty_coords, filled_coords)
            nearest_indices = np.argmin(distances, axis=1)
            
            empty_linear = np.where(empty_pixels)[0]
            filled_linear = np.where(~empty_pixels)[0]
            
            for i, empty_idx in enumerate(empty_linear):
                nearest_filled_idx = filled_linear[nearest_indices[i]]
                raster_image[empty_idx] = raster_image[nearest_filled_idx]
    
    # Reshape back to 2D image
    raster_image = raster_image.reshape(RASTER_HEIGHT, RASTER_WIDTH, 3)
    
    end_time = time.time()
    total_time = end_time - start_time
    total_pixels = RASTER_HEIGHT * RASTER_WIDTH
    
    print(f"Ultra-fast rasterization complete!")
    print(f"Total time: {total_time:.2f} seconds")
    print(f"Pixels per second: {total_pixels / total_time:.0f}")
    print(f"Non-empty pixels: {len(unique_pixels)} ({len(unique_pixels)/total_pixels*100:.1f}%)")
    
    return raster_image.astype(np.uint8)


def main():
    print("Starting ultra-fast rasterized yard map generation", flush=True)
    parser = argparse.ArgumentParser(description='Generate ultra-fast rasterized yard maps (640x360)')
    parser.add_argument('input', help='Input PLY mesh file path')
    parser.add_argument('--output', '-o', default='yard_map_ultra.png', help='Output image path')
    parser.add_argument('--grid-resolution', type=float, default=0.1, help='Grid resolution in meters (default: 0.1m)')
    parser.add_argument('--max-points', type=int, default=50000, 
                       help='Maximum points to process for performance (default: 50000)')
    parser.add_argument('--projection', '-p', choices=['xy', 'xz', 'yz'], 
                       default='xy', help='Projection plane: xy=top-down, xz=side, yz=front (default: xy)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        return 1
    
    print(f"Loading mesh for ultra-fast rasterization: {args.input}")
    
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
    
    print(f"Generating ultra-fast rasterized yard map...")
    print(f"  Output size: 640x360 pixels")
    print(f"  Projection: {args.projection}")
    print(f"  Ground selection: bottom 30% by height")
    
    try:
        raster_image = create_ultra_fast_raster_map(vertices, colors, args.projection, args.grid_resolution)
        
        # Save as PNG using PIL
        pil_image = Image.fromarray(raster_image, 'RGB')
        pil_image.save(args.output, 'PNG')
        
        # Verify file was created and get size
        if os.path.exists(args.output):
            file_size = os.path.getsize(args.output) / 1024  # KB
            print(f"Ultra-fast rasterized map saved: {args.output} ({file_size:.1f} KB)")
        else:
            raise FileNotFoundError(f"Failed to save output file: {args.output}")
        
        print("Done!")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())