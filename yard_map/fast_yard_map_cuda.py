#!/usr/bin/env python3
"""
CUDA-accelerated yard map generator using GPU parallel processing.
Designed for maximum performance using CuPy and Numba CUDA kernels.
"""

import numpy as np
import argparse
import os
import sys
import time
from PIL import Image

# CUDA imports
try:
    import cupy as cp
    import numpy as np  # Make sure numpy is available for filtering
    import numba.cuda as cuda
    from numba import types
    CUDA_AVAILABLE = True
    print("CUDA acceleration available")
except ImportError:
    CUDA_AVAILABLE = False
    print("CUDA not available, falling back to CPU")

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
            
            # Calculate reasonable bounds using percentiles (but keep all points)
            print(f"Total points in dataset: {len(vertices):,}")
            x_percentiles = np.percentile(vertices[:, 0], [1, 99])
            y_percentiles = np.percentile(vertices[:, 1], [1, 99])
            z_percentiles = np.percentile(vertices[:, 2], [1, 99])
            
            print(f"Data range: X=[{vertices[:,0].min():.1f}, {vertices[:,0].max():.1f}], "
                  f"Y=[{vertices[:,1].min():.1f}, {vertices[:,1].max():.1f}], "
                  f"Z=[{vertices[:,2].min():.1f}, {vertices[:,2].max():.1f}]")
            print(f"99% bounds: X=[{x_percentiles[0]:.1f}, {x_percentiles[1]:.1f}], "
                  f"Y=[{y_percentiles[0]:.1f}, {y_percentiles[1]:.1f}], "
                  f"Z=[{z_percentiles[0]:.1f}, {z_percentiles[1]:.1f}]")
            
            # Store suggested bounds as metadata (but don't filter points)
            vertices.suggested_bounds = (x_percentiles, y_percentiles, z_percentiles)
            
            # Sample if too many points
            if len(vertices) > max_points:
                indices = np.random.choice(len(vertices), max_points, replace=False)
                vertices = vertices[indices]
                if colors is not None:
                    colors = colors[indices]
                print(f"Sampled {max_points} vertices from {len(mesh.vertices)} total points")
            
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


@cuda.jit
def cuda_build_spatial_grid(vertices_2d, grid_cells, grid_count,
                           x_min, y_min, cell_size, grid_width, grid_height):
    """Build spatial hash grid for fast point lookups."""
    idx = cuda.grid(1)
    if idx >= vertices_2d.shape[0]:
        return
    
    # Calculate grid cell for this point
    cell_x = int((vertices_2d[idx, 0] - x_min) / cell_size)
    cell_y = int((vertices_2d[idx, 1] - y_min) / cell_size)
    
    # Clamp to grid bounds
    if cell_x < 0: cell_x = 0
    if cell_x >= grid_width: cell_x = grid_width - 1
    if cell_y < 0: cell_y = 0 
    if cell_y >= grid_height: cell_y = grid_height - 1
    
    # Calculate linear cell index
    cell_idx = cell_y * grid_width + cell_x
    
    # Atomically increment count for this cell
    old_count = cuda.atomic.add(grid_count, cell_idx, 1)
    
    # Store point index in grid (if there's space)
    if old_count < 100:  # Max 100 points per cell
        grid_cells[cell_idx, old_count] = idx


@cuda.jit
def cuda_process_pixels_with_grid(vertices_2d, vertices_z, colors, 
                                 grid_cells, grid_count,
                                 x_min, y_min, y_max, pixel_size, cell_size,
                                 height_window, output_image, coloring_mode, 
                                 z_min, z_max, raster_width, raster_height,
                                 grid_width):
    """
    Optimized CUDA kernel using spatial grid for fast point lookups.
    Each thread processes one pixel of the 640x360 output image.
    """
    # Get pixel coordinates
    pixel_id = cuda.grid(1)
    if pixel_id >= raster_width * raster_height:
        return
    
    col = pixel_id % raster_width
    row = pixel_id // raster_width
    
    # Calculate pixel boundaries in world coordinates
    pixel_x_min = x_min + col * pixel_size
    pixel_x_max = x_min + (col + 1) * pixel_size
    pixel_y_min = y_max - (row + 1) * pixel_size  # Image Y is flipped
    pixel_y_max = y_max - row * pixel_size
    
    # Find which grid cells overlap with this pixel
    cell_x_min = int((pixel_x_min - x_min) / cell_size)
    cell_x_max = int((pixel_x_max - x_min) / cell_size) 
    cell_y_min = int((pixel_y_min - y_min) / cell_size)
    cell_y_max = int((pixel_y_max - y_min) / cell_size)
    
    # Clamp to grid bounds
    if cell_x_min < 0: cell_x_min = 0
    if cell_x_max >= grid_width: cell_x_max = grid_width - 1
    if cell_y_min < 0: cell_y_min = 0
    if cell_y_max >= grid_width: cell_y_max = grid_width - 1  # Assuming square grid
    
    # Arrays to store points in this pixel
    pixel_points = cuda.local.array(500, types.int32)  # Max 500 points per pixel
    pixel_count = 0
    
    # Check all overlapping grid cells
    for cell_y in range(cell_y_min, cell_y_max + 1):
        for cell_x in range(cell_x_min, cell_x_max + 1):
            cell_idx = cell_y * grid_width + cell_x
            cell_point_count = grid_count[cell_idx]
            
            # Check all points in this cell
            for i in range(min(cell_point_count, 100)):  # Max 100 points per cell
                point_idx = grid_cells[cell_idx, i]
                
                # Check if point is actually within pixel bounds
                if (vertices_2d[point_idx, 0] >= pixel_x_min and 
                    vertices_2d[point_idx, 0] <= pixel_x_max and
                    vertices_2d[point_idx, 1] >= pixel_y_min and 
                    vertices_2d[point_idx, 1] <= pixel_y_max):
                    
                    if pixel_count < 500:  # Avoid overflow
                        pixel_points[pixel_count] = point_idx
                        pixel_count += 1
    
    # If no points found, expand search area progressively
    expansion = 1
    while pixel_count == 0 and expansion <= 5:  # Max 5-pixel expansion
        # Expand pixel bounds by 'expansion' pixels on all sides
        expanded_pixel_size = pixel_size * expansion
        expanded_x_min = pixel_x_min - (expanded_pixel_size * (expansion - 1))
        expanded_x_max = pixel_x_max + (expanded_pixel_size * (expansion - 1))
        expanded_y_min = pixel_y_min - (expanded_pixel_size * (expansion - 1))
        expanded_y_max = pixel_y_max + (expanded_pixel_size * (expansion - 1))
        
        # Recalculate grid cells for expanded area
        exp_cell_x_min = int((expanded_x_min - x_min) / cell_size)
        exp_cell_x_max = int((expanded_x_max - x_min) / cell_size)
        exp_cell_y_min = int((expanded_y_min - y_min) / cell_size)
        exp_cell_y_max = int((expanded_y_max - y_min) / cell_size)
        
        # Clamp to grid bounds
        if exp_cell_x_min < 0: exp_cell_x_min = 0
        if exp_cell_x_max >= grid_width: exp_cell_x_max = grid_width - 1
        if exp_cell_y_min < 0: exp_cell_y_min = 0
        if exp_cell_y_max >= grid_width: exp_cell_y_max = grid_width - 1
        
        # Search in expanded area
        for cell_y in range(exp_cell_y_min, exp_cell_y_max + 1):
            for cell_x in range(exp_cell_x_min, exp_cell_x_max + 1):
                cell_idx = cell_y * grid_width + cell_x
                cell_point_count = grid_count[cell_idx]
                
                for i in range(min(cell_point_count, 100)):
                    point_idx = grid_cells[cell_idx, i]
                    
                    # Check if point is within expanded bounds
                    if (vertices_2d[point_idx, 0] >= expanded_x_min and 
                        vertices_2d[point_idx, 0] <= expanded_x_max and
                        vertices_2d[point_idx, 1] >= expanded_y_min and 
                        vertices_2d[point_idx, 1] <= expanded_y_max):
                        
                        if pixel_count < 500:
                            pixel_points[pixel_count] = point_idx
                            pixel_count += 1
        
        expansion += 1
    
    # Process pixel if we have points (original or from expansion)
    if pixel_count > 0:
        # Collect all heights in this pixel
        pixel_heights = cuda.local.array(500, types.float32)
        for j in range(pixel_count):
            pixel_heights[j] = vertices_z[pixel_points[j]]
        
        # Sort heights to find percentile (simple bubble sort for small arrays)
        for i in range(pixel_count - 1):
            for j in range(pixel_count - 1 - i):
                if pixel_heights[j] > pixel_heights[j + 1]:
                    temp = pixel_heights[j]
                    pixel_heights[j] = pixel_heights[j + 1]
                    pixel_heights[j + 1] = temp
        
        # Use percentile-based ground selection
        # Take lowest 40% of points, but at least 1 point
        percentile_count = max(1, int(pixel_count * 0.4))
        
        # Height threshold is the percentile height
        if percentile_count <= pixel_count:
            height_threshold = pixel_heights[percentile_count - 1]
        else:
            height_threshold = pixel_heights[pixel_count - 1]
        
        # Count valid points and accumulate colors
        valid_points = 0
        color_r = 0.0
        color_g = 0.0
        color_b = 0.0
        max_height = pixel_heights[0]  # minimum height
        
        for j in range(pixel_count):
            point_idx = pixel_points[j]
            point_height = vertices_z[point_idx]
            
            if point_height <= height_threshold:
                valid_points += 1
                
                if coloring_mode == 0:  # true_color
                    color_r += colors[point_idx, 0]
                    color_g += colors[point_idx, 1] 
                    color_b += colors[point_idx, 2]
                
                if point_height > max_height:
                    max_height = point_height
        
        # Set pixel color based on coloring mode
        if valid_points > 0:
            if coloring_mode == 0:  # true_color
                # Average colors
                avg_r = color_r / valid_points
                avg_g = color_g / valid_points  
                avg_b = color_b / valid_points
                
                # Ensure 0-255 range
                if avg_r <= 1.0:
                    avg_r *= 255
                if avg_g <= 1.0:
                    avg_g *= 255
                if avg_b <= 1.0:
                    avg_b *= 255
                
                output_image[row, col, 0] = int(avg_r)
                output_image[row, col, 1] = int(avg_g)
                output_image[row, col, 2] = int(avg_b)
                
            elif coloring_mode == 1:  # height gradient
                # Normalize height for gradient coloring
                height_range = z_max - z_min
                if height_range > 0:
                    normalized_height = (max_height - z_min) / height_range
                else:
                    normalized_height = 0.0
                
                # Apply terrain-like gradient
                if normalized_height < 0.25:
                    # Blue to cyan
                    t = normalized_height * 4
                    output_image[row, col, 0] = int((1-t) * 0 + t * 0)
                    output_image[row, col, 1] = int((1-t) * 100 + t * 255)
                    output_image[row, col, 2] = int((1-t) * 255 + t * 255)
                elif normalized_height < 0.5:
                    # Cyan to green  
                    t = (normalized_height - 0.25) * 4
                    output_image[row, col, 0] = int((1-t) * 0 + t * 0)
                    output_image[row, col, 1] = int((1-t) * 255 + t * 255)
                    output_image[row, col, 2] = int((1-t) * 255 + t * 0)
                elif normalized_height < 0.75:
                    # Green to yellow
                    t = (normalized_height - 0.5) * 4
                    output_image[row, col, 0] = int((1-t) * 0 + t * 255)
                    output_image[row, col, 1] = int((1-t) * 255 + t * 255)
                    output_image[row, col, 2] = int((1-t) * 0 + t * 0)
                else:
                    # Yellow to red
                    t = (normalized_height - 0.75) * 4
                    output_image[row, col, 0] = int((1-t) * 255 + t * 255)
                    output_image[row, col, 1] = int((1-t) * 255 + t * 0)
                    output_image[row, col, 2] = int((1-t) * 0 + t * 0)
                    
            elif coloring_mode == 2:  # path visualization  
                # Green if we selected most points (ground-like pixel)
                # Red if we filtered out many points (mixed ground/tree pixel)
                selection_ratio = float(valid_points) / float(pixel_count)
                if selection_ratio >= 0.7:  # Selected 70%+ of points - mostly ground
                    output_image[row, col, 0] = 0
                    output_image[row, col, 1] = 255
                    output_image[row, col, 2] = 0
                else:  # Filtered out significant points - mixed ground/trees
                    output_image[row, col, 0] = 255
                    output_image[row, col, 1] = 0
                    output_image[row, col, 2] = 0
        else:
            # No valid points - gray
            output_image[row, col, 0] = 50
            output_image[row, col, 1] = 50
            output_image[row, col, 2] = 50
    else:
        # No points found - gray
        output_image[row, col, 0] = 50
        output_image[row, col, 1] = 50
        output_image[row, col, 2] = 50


@cuda.jit
def cuda_simple_average_pixels(vertices_2d, vertices_z, colors, 
                               grid_cells, grid_count,
                               x_min, y_min, y_max, pixel_size, cell_size,
                               output_image, coloring_mode, 
                               z_min, z_max, raster_width, raster_height,
                               grid_width):
    """
    CUDA kernel for true simple averaging - averages ALL points in each pixel.
    No percentile filtering, no height thresholds - just average everything.
    """
    # Get pixel coordinates
    pixel_id = cuda.grid(1)
    if pixel_id >= raster_width * raster_height:
        return
    
    col = pixel_id % raster_width
    row = pixel_id // raster_width
    
    # Calculate pixel boundaries in world coordinates
    pixel_x_min = x_min + col * pixel_size
    pixel_x_max = x_min + (col + 1) * pixel_size
    pixel_y_min = y_max - (row + 1) * pixel_size  # Image Y is flipped
    pixel_y_max = y_max - row * pixel_size
    
    # Find which grid cells overlap with this pixel
    cell_x_min = int((pixel_x_min - x_min) / cell_size)
    cell_x_max = int((pixel_x_max - x_min) / cell_size) 
    cell_y_min = int((pixel_y_min - y_min) / cell_size)
    cell_y_max = int((pixel_y_max - y_min) / cell_size)
    
    # Clamp to grid bounds
    if cell_x_min < 0: cell_x_min = 0
    if cell_x_max >= grid_width: cell_x_max = grid_width - 1
    if cell_y_min < 0: cell_y_min = 0
    if cell_y_max >= grid_width: cell_y_max = grid_width - 1
    
    # Arrays to store points in this pixel
    pixel_points = cuda.local.array(500, types.int32)  # Max 500 points per pixel
    pixel_count = 0
    
    # Check all overlapping grid cells
    for cell_y in range(cell_y_min, cell_y_max + 1):
        for cell_x in range(cell_x_min, cell_x_max + 1):
            cell_idx = cell_y * grid_width + cell_x
            cell_point_count = grid_count[cell_idx]
            
            # Check all points in this cell
            for i in range(min(cell_point_count, 100)):  # Max 100 points per cell
                point_idx = grid_cells[cell_idx, i]
                
                # Check if point is actually within pixel bounds
                if (vertices_2d[point_idx, 0] >= pixel_x_min and 
                    vertices_2d[point_idx, 0] <= pixel_x_max and
                    vertices_2d[point_idx, 1] >= pixel_y_min and 
                    vertices_2d[point_idx, 1] <= pixel_y_max):
                    
                    if pixel_count < 500:  # Avoid overflow
                        pixel_points[pixel_count] = point_idx
                        pixel_count += 1
    
    # If no points found, expand search area progressively
    expansion = 1
    while pixel_count == 0 and expansion <= 5:  # Max 5-pixel expansion
        # Expand pixel bounds by 'expansion' pixels on all sides
        expanded_pixel_size = pixel_size * expansion
        expanded_x_min = pixel_x_min - (expanded_pixel_size * (expansion - 1))
        expanded_x_max = pixel_x_max + (expanded_pixel_size * (expansion - 1))
        expanded_y_min = pixel_y_min - (expanded_pixel_size * (expansion - 1))
        expanded_y_max = pixel_y_max + (expanded_pixel_size * (expansion - 1))
        
        # Recalculate grid cells for expanded area
        exp_cell_x_min = int((expanded_x_min - x_min) / cell_size)
        exp_cell_x_max = int((expanded_x_max - x_min) / cell_size)
        exp_cell_y_min = int((expanded_y_min - y_min) / cell_size)
        exp_cell_y_max = int((expanded_y_max - y_min) / cell_size)
        
        # Clamp to grid bounds
        if exp_cell_x_min < 0: exp_cell_x_min = 0
        if exp_cell_x_max >= grid_width: exp_cell_x_max = grid_width - 1
        if exp_cell_y_min < 0: exp_cell_y_min = 0
        if exp_cell_y_max >= grid_width: exp_cell_y_max = grid_width - 1
        
        # Search in expanded area
        for cell_y in range(exp_cell_y_min, exp_cell_y_max + 1):
            for cell_x in range(exp_cell_x_min, exp_cell_x_max + 1):
                cell_idx = cell_y * grid_width + cell_x
                cell_point_count = grid_count[cell_idx]
                
                for i in range(min(cell_point_count, 100)):
                    point_idx = grid_cells[cell_idx, i]
                    
                    # Check if point is within expanded bounds
                    if (vertices_2d[point_idx, 0] >= expanded_x_min and 
                        vertices_2d[point_idx, 0] <= expanded_x_max and
                        vertices_2d[point_idx, 1] >= expanded_y_min and 
                        vertices_2d[point_idx, 1] <= expanded_y_max):
                        
                        if pixel_count < 500:
                            pixel_points[pixel_count] = point_idx
                            pixel_count += 1
        
        expansion += 1
    
    # Process pixel with simple averaging of ALL points (no filtering)
    if pixel_count > 0:
        # Simple average of ALL points - no percentile filtering
        color_r = 0.0
        color_g = 0.0
        color_b = 0.0
        height_sum = 0.0
        
        for j in range(pixel_count):
            point_idx = pixel_points[j]
            
            if coloring_mode == 0:  # true_color
                color_r += colors[point_idx, 0]
                color_g += colors[point_idx, 1] 
                color_b += colors[point_idx, 2]
            
            height_sum += vertices_z[point_idx]
        
        # Set pixel color based on coloring mode
        if coloring_mode == 0:  # true_color
            # Simple average of ALL colors
            avg_r = color_r / pixel_count
            avg_g = color_g / pixel_count  
            avg_b = color_b / pixel_count
            
            # Ensure 0-255 range
            if avg_r <= 1.0:
                avg_r *= 255
            if avg_g <= 1.0:
                avg_g *= 255
            if avg_b <= 1.0:
                avg_b *= 255
            
            output_image[row, col, 0] = int(avg_r)
            output_image[row, col, 1] = int(avg_g)
            output_image[row, col, 2] = int(avg_b)
            
        elif coloring_mode == 1:  # height gradient
            # Average height for gradient coloring
            avg_height = height_sum / pixel_count
            height_range = z_max - z_min
            if height_range > 0:
                normalized_height = (avg_height - z_min) / height_range
            else:
                normalized_height = 0.0
                
            # Simple terrain gradient: blue (low) -> green (mid) -> brown (high)
            if normalized_height <= 0.33:
                # Blue to green
                t = normalized_height * 3
                output_image[row, col, 0] = int((1-t) * 100 + t * 34)
                output_image[row, col, 1] = int((1-t) * 150 + t * 139) 
                output_image[row, col, 2] = int((1-t) * 255 + t * 34)
            elif normalized_height <= 0.67:
                # Green to brown
                t = (normalized_height - 0.33) * 3
                output_image[row, col, 0] = int((1-t) * 34 + t * 139)
                output_image[row, col, 1] = int((1-t) * 139 + t * 90)
                output_image[row, col, 2] = int((1-t) * 34 + t * 45)
            else:
                # Brown to white
                t = (normalized_height - 0.67) * 3
                output_image[row, col, 0] = int((1-t) * 139 + t * 255)
                output_image[row, col, 1] = int((1-t) * 90 + t * 255)
                output_image[row, col, 2] = int((1-t) * 45 + t * 255)
                
        else:  # coloring_mode == 2: simple average visualization
            # Show uniform green for simple average (no filtering applied)
            output_image[row, col, 0] = 34   # Forest green
            output_image[row, col, 1] = 139
            output_image[row, col, 2] = 34
    else:
        # No points found - gray
        output_image[row, col, 0] = 128
        output_image[row, col, 1] = 128
        output_image[row, col, 2] = 128


def create_cuda_raster_map(vertices, colors=None, projection='xy', grid_resolution=0.1, 
                          height_window=0.5, custom_bounds=None, coloring='true_color', 
                          output_width=1280, output_height=720, rotation=0, algorithm='bottom_percentile'):
    """Create ultra-fast CUDA-accelerated yard map with dynamic resolution.
    
    Args:
        algorithm: 'bottom_percentile' (default) or 'simple_average'
    """
    
    if not CUDA_AVAILABLE:
        raise RuntimeError("CUDA not available - cannot use GPU acceleration")
    
    print(f"Creating CUDA-accelerated raster map: {output_width}x{output_height} pixels")
    print(f"Using GPU: {cp.cuda.Device()}")
    
    start_time = time.time()
    
    # Get 2D projection coordinates and depths
    vertices_2d = project_to_2d(vertices, projection)
    
    # Apply rotation if specified
    if rotation != 0:
        print(f"Applying rotation: {rotation}°")
        angle_rad = np.radians(rotation)
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)
        
        # Rotate around the centroid
        center_x = vertices_2d[:, 0].mean()
        center_y = vertices_2d[:, 1].mean()
        
        # Translate to origin
        x_centered = vertices_2d[:, 0] - center_x
        y_centered = vertices_2d[:, 1] - center_y
        
        # Apply rotation matrix
        x_rotated = x_centered * cos_a - y_centered * sin_a
        y_rotated = x_centered * sin_a + y_centered * cos_a
        
        # Translate back
        vertices_2d[:, 0] = x_rotated + center_x
        vertices_2d[:, 1] = y_rotated + center_y
    
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
    
    # Use custom bounds if provided, otherwise use percentile bounds for initial view
    # IMPORTANT: Bounds are ONLY for setting the view window, NOT for filtering points!
    if custom_bounds:
        x_min, x_max, y_min, y_max = custom_bounds
        print(f"Using custom bounds for view window: X=[{x_min:.2f}, {x_max:.2f}], Y=[{y_min:.2f}, {y_max:.2f}] meters")
        
        # Count how many points are in the view (for information only)
        in_view = ((vertices_2d[:, 0] >= x_min) & 
                   (vertices_2d[:, 0] <= x_max) &
                   (vertices_2d[:, 1] >= y_min) & 
                   (vertices_2d[:, 1] <= y_max))
        print(f"Points visible in view window: {np.sum(in_view)}/{len(vertices)} ({np.sum(in_view)/len(vertices)*100:.1f}%)")
        print(f"Processing ALL {len(vertices_2d)} points (no filtering)")
    else:
        # Use percentile bounds to exclude outliers from initial view
        # This gives a reasonable default view while keeping all data for zooming
        x_percentiles = np.percentile(vertices_2d[:, 0], [1, 99])
        y_percentiles = np.percentile(vertices_2d[:, 1], [1, 99])
        
        x_min, x_max = x_percentiles[0], x_percentiles[1]
        y_min, y_max = y_percentiles[0], y_percentiles[1]
        
        print(f"Full data range: X=[{vertices_2d[:, 0].min():.2f}, {vertices_2d[:, 0].max():.2f}], Y=[{vertices_2d[:, 1].min():.2f}, {vertices_2d[:, 1].max():.2f}]")
        print(f"Using 99% bounds: X=[{x_min:.2f}, {x_max:.2f}], Y=[{y_min:.2f}, {y_max:.2f}] meters")
    
    # Fixed raster dimensions
    RASTER_WIDTH = output_width
    RASTER_HEIGHT = output_height
    
    # Calculate uniform pixel size for 1:1 sampling (16:9 aspect ratio)
    data_width = x_max - x_min
    data_height = y_max - y_min
    data_aspect = data_width / data_height
    target_aspect = RASTER_WIDTH / RASTER_HEIGHT  # 16:9 = 1.777...
    
    if data_aspect > target_aspect:
        # Data is wider - fit to width, expand height
        pixel_size = data_width / RASTER_WIDTH
        adjusted_height = RASTER_HEIGHT * pixel_size
        height_padding = (adjusted_height - data_height) / 2
        x_min_adjusted, x_max_adjusted = x_min, x_max
        y_min_adjusted = y_min - height_padding
        y_max_adjusted = y_max + height_padding
    else:
        # Data is taller - fit to height, expand width  
        pixel_size = data_height / RASTER_HEIGHT
        adjusted_width = RASTER_WIDTH * pixel_size
        width_padding = (adjusted_width - data_width) / 2
        x_min_adjusted = x_min - width_padding
        x_max_adjusted = x_max + width_padding
        y_min_adjusted, y_max_adjusted = y_min, y_max
    
    print(f"1:1 Pixel size: {pixel_size:.4f}m x {pixel_size:.4f}m")
    print(f"Adjusted bounds: X=[{x_min_adjusted:.2f}, {x_max_adjusted:.2f}], Y=[{y_min_adjusted:.2f}, {y_max_adjusted:.2f}]")
    
    # Convert coloring mode to integer for CUDA kernel
    coloring_map = {'true_color': 0, 'height': 1, 'path': 2}
    coloring_mode = coloring_map.get(coloring, 0)
    
    # Move data to GPU
    print("Transferring data to GPU...")
    gpu_vertices_2d = cp.asarray(vertices_2d, dtype=cp.float32)
    gpu_vertices_z = cp.asarray(depth_values, dtype=cp.float32) 
    
    if colors is not None:
        gpu_colors = cp.asarray(colors, dtype=cp.float32)
    else:
        # Create dummy color data for height/path modes
        gpu_colors = cp.zeros((len(vertices), 3), dtype=cp.float32)
    
    # Create output image on GPU
    gpu_output = cp.zeros((RASTER_HEIGHT, RASTER_WIDTH, 3), dtype=cp.uint8)
    
    # Get height range for gradient coloring
    z_min = float(depth_values.min())
    z_max = float(depth_values.max())
    
    print("Building spatial acceleration grid...")
    
    # Create spatial grid for fast point lookups
    # Use cells that are roughly pixel-sized for optimal performance
    cell_size = pixel_size  # Each cell = 1 pixel
    grid_width = int((x_max_adjusted - x_min_adjusted) / cell_size) + 1
    grid_height = int((y_max_adjusted - y_min_adjusted) / cell_size) + 1
    max_points_per_cell = 100
    
    print(f"Spatial grid: {grid_width}x{grid_height} cells, cell size: {cell_size:.4f}m")
    
    # Allocate grid data structures on GPU
    gpu_grid_cells = cp.zeros((grid_width * grid_height, max_points_per_cell), dtype=cp.int32)
    gpu_grid_count = cp.zeros(grid_width * grid_height, dtype=cp.int32)
    
    # Build spatial grid
    num_points = len(vertices)
    threads_per_block = 256
    blocks_for_points = (num_points + threads_per_block - 1) // threads_per_block
    
    cuda_build_spatial_grid[blocks_for_points, threads_per_block](
        gpu_vertices_2d, gpu_grid_cells, gpu_grid_count,
        x_min_adjusted, y_min_adjusted, cell_size, grid_width, grid_height
    )
    
    cp.cuda.Stream.null.synchronize()
    print("Spatial grid built successfully")
    
    print("Launching optimized CUDA pixel processing kernels...")
    
    # Configure CUDA launch parameters for pixel processing
    total_pixels = RASTER_WIDTH * RASTER_HEIGHT
    blocks_per_grid = (total_pixels + threads_per_block - 1) // threads_per_block
    
    print(f"CUDA config: {blocks_per_grid} blocks x {threads_per_block} threads = {blocks_per_grid * threads_per_block} total threads")
    print(f"Using algorithm: {algorithm}")
    
    # Choose CUDA kernel based on algorithm
    if algorithm == 'simple_average':
        print("Launching simple average CUDA kernel...")
        cuda_simple_average_pixels[blocks_per_grid, threads_per_block](
            gpu_vertices_2d, gpu_vertices_z, gpu_colors,
            gpu_grid_cells, gpu_grid_count,
            x_min_adjusted, y_min_adjusted, y_max_adjusted, pixel_size, cell_size,
            gpu_output, coloring_mode, z_min, z_max,
            RASTER_WIDTH, RASTER_HEIGHT, grid_width
        )
    else:  # bottom_percentile (default)
        print("Launching bottom percentile CUDA kernel...")
        cuda_process_pixels_with_grid[blocks_per_grid, threads_per_block](
            gpu_vertices_2d, gpu_vertices_z, gpu_colors,
            gpu_grid_cells, gpu_grid_count,
            x_min_adjusted, y_min_adjusted, y_max_adjusted, pixel_size, cell_size,
            height_window, gpu_output, coloring_mode, z_min, z_max,
            RASTER_WIDTH, RASTER_HEIGHT, grid_width
        )
    
    # Wait for GPU computation to complete
    cp.cuda.Stream.null.synchronize()
    
    # Transfer result back to CPU
    print("Transferring result from GPU...")
    cpu_output = cp.asnumpy(gpu_output)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"CUDA rasterization complete!")
    print(f"Total time: {total_time:.3f} seconds")
    print(f"Pixels per second: {total_pixels / total_time:.0f}")
    print(f"GPU Memory used: {cp.get_default_memory_pool().used_bytes() / 1024 / 1024:.1f} MB")
    
    return cpu_output


def create_yard_map(vertices, colors=None, projection='xy', grid_resolution=0.1, 
                   height_window=0.5, custom_bounds=None, coloring='true_color',
                   output_width=1280, output_height=720, rotation=0, algorithm='bottom_percentile'):
    """Create rasterized yard map using CUDA acceleration with dynamic resolution."""
    print(f"Creating CUDA-accelerated yard map:")
    print(f"  Output: {output_width}x{output_height} raster image")
    print(f"  Projection: {projection}")
    print(f"  Height window: {height_window}m")
    print(f"  Coloring: {coloring}")
    print(f"  Colors available: {colors is not None}")
    if custom_bounds:
        print(f"  Custom bounds: X=[{custom_bounds[0]:.2f}, {custom_bounds[1]:.2f}], Y=[{custom_bounds[2]:.2f}, {custom_bounds[3]:.2f}]")
    
    if len(vertices) == 0:
        raise ValueError("No vertices to process!")
    
    # Create CUDA-accelerated rasterized image
    raster_image = create_cuda_raster_map(
        vertices, colors, projection, grid_resolution, height_window, custom_bounds, coloring,
        output_width, output_height, rotation, algorithm
    )
    
    # Convert numpy array to PIL Image
    img = Image.fromarray(raster_image, mode='RGB')
    
    return img


def main():
    print("CUDA-Accelerated Yard Map Generator", flush=True)
    
    if not CUDA_AVAILABLE:
        print("ERROR: CUDA not available. Please install CuPy and Numba with CUDA support.")
        return 1
    
    parser = argparse.ArgumentParser(description='Generate yard maps with CUDA GPU acceleration')
    parser.add_argument('input', help='Input PLY mesh file path')
    parser.add_argument('--output', '-o', default='yard_map_cuda.png', help='Output image path')
    parser.add_argument('--grid-resolution', type=float, default=0.1, help='Grid resolution in meters (default: 0.1m)')
    parser.add_argument('--height-window', type=float, default=0.5, help='Height window in meters (default: 0.5m)')
    parser.add_argument('--coloring', choices=['true_color', 'height', 'path'], default='true_color', 
                       help='Coloring mode: true_color=mesh colors, height=elevation gradient, path=algorithm visualization')
    parser.add_argument('--bounds', type=str, help='Custom bounds as x_min,x_max,y_min,y_max for focused rendering')
    parser.add_argument('--x-min', type=float, help='Minimum X coordinate')
    parser.add_argument('--x-max', type=float, help='Maximum X coordinate') 
    parser.add_argument('--y-min', type=float, help='Minimum Y coordinate')
    parser.add_argument('--y-max', type=float, help='Maximum Y coordinate')
    parser.add_argument('--max-points', type=int, default=20000000, 
                       help='Maximum points to process for performance (default: 20000000)')
    parser.add_argument('--output-width', type=int, default=1280, 
                        help='Output image width (default: 1280)')
    parser.add_argument('--output-height', type=int, default=720, 
                        help='Output image height (default: 720)')
    parser.add_argument('--projection', '-p', choices=['xy', 'xz', 'yz'], 
                       default='xy', help='Projection plane: xy=top-down, xz=side, yz=front (default: xy)')
    parser.add_argument('--rotation', type=float, default=0, 
                       help='Rotation angle in degrees (default: 0)')
    parser.add_argument('--algorithm', choices=['bottom_percentile', 'simple_average'], default='bottom_percentile',
                       help='Algorithm: bottom_percentile=lowest 40%% points, simple_average=all points (default: bottom_percentile)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        return 1
    
    print(f"Loading mesh for CUDA processing: {args.input}")
    
    vertices, colors = load_mesh_vertices(args.input, args.max_points)
    if vertices is None:
        print("Failed to load mesh vertices")
        return 1
    
    print(f"Loaded {len(vertices)} vertices for CUDA processing")
    if colors is not None:
        print(f"Found true color data: {colors.shape} - will use for pixel colors")
    else:
        print("No color data found - will use height-based coloring")
        
    if vertices.shape[1] > 2:
        z_min, z_max = vertices[:, 2].min(), vertices[:, 2].max()
        print(f"Mesh height range: [{z_min:.2f}, {z_max:.2f}] meters")
    
    try:
        # Parse custom bounds if provided
        custom_bounds = None
        if args.x_min is not None and args.x_max is not None and args.y_min is not None and args.y_max is not None:
            # Use separate parameters
            custom_bounds = [args.x_min, args.x_max, args.y_min, args.y_max]
            print(f"Using custom bounds: X=[{custom_bounds[0]:.2f}, {custom_bounds[1]:.2f}], Y=[{custom_bounds[2]:.2f}, {custom_bounds[3]:.2f}]")
        elif args.bounds:
            # Fall back to comma-separated string
            try:
                bounds_values = [float(x.strip()) for x in args.bounds.split(',')]
                if len(bounds_values) == 4:
                    custom_bounds = bounds_values
                    print(f"Using custom bounds: X=[{custom_bounds[0]:.2f}, {custom_bounds[1]:.2f}], Y=[{custom_bounds[2]:.2f}, {custom_bounds[3]:.2f}]")
                else:
                    print("Warning: Invalid bounds format, using full data bounds")
            except Exception as e:
                print(f"Warning: Could not parse bounds '{args.bounds}': {e}")
        
        img = create_yard_map(
            vertices, colors, args.projection, args.grid_resolution, args.height_window, custom_bounds, args.coloring,
            args.output_width, args.output_height, args.rotation, args.algorithm
        )
        
        print(f"Saving {args.output_width}x{args.output_height} CUDA raster to: {args.output}")
        img.save(args.output)
        
        # Verify file was created and get size
        if os.path.exists(args.output):
            file_size = os.path.getsize(args.output) / 1024  # KB
            print(f"Generated {args.output_width}x{args.output_height} CUDA raster map saved ({file_size:.1f} KB)")
        else:
            raise FileNotFoundError(f"Failed to save output file: {args.output}")
        
        print("CUDA acceleration complete!")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())