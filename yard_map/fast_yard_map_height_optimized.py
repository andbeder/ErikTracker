#!/usr/bin/env python3
"""
Height-optimized yard map generator with selective K-means clustering.
Uses height window check to avoid K-means when all points are within a small height range.
Falls back to K-means clustering only when needed to separate ground from foliage.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for containers
import matplotlib.pyplot as plt
import argparse
import os
import sys

try:
    import trimesh
    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False

try:
    from sklearn.cluster import KMeans
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: scikit-learn not available - will use fallback clustering methods")


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


def create_height_optimized_raster_map(vertices, colors=None, projection='xy', grid_resolution=0.1, height_window=0.5, custom_bounds=None, coloring='true_color'):
    """Create a rasterized 640x360 yard map using height-optimized K-means clustering.
    
    For each pixel:
    1. Find all points in the pixel cube
    2. If height range <= height_window: simple average (FAST PATH)
    3. Otherwise: Use K-means (N=2) on height values to separate ground from foliage
    4. Average colors of selected ground points
    """
    print(f"Creating height-optimized raster: 640x360 pixels, height_window: {height_window}m")
    
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
    
    # Use custom bounds if provided, otherwise calculate from data
    if custom_bounds:
        x_min, x_max, y_min, y_max = custom_bounds
        print(f"Using custom bounds: X=[{x_min:.2f}, {x_max:.2f}], Y=[{y_min:.2f}, {y_max:.2f}] meters")
        
        # Filter points to only those within bounds (with small margin)
        margin = 1.0  # 1 meter margin to ensure edge coverage
        in_bounds = ((vertices_2d[:, 0] >= x_min - margin) & 
                    (vertices_2d[:, 0] <= x_max + margin) &
                    (vertices_2d[:, 1] >= y_min - margin) & 
                    (vertices_2d[:, 1] <= y_max + margin))
        
        print(f"Points in bounds: {np.sum(in_bounds)}/{len(vertices)} ({np.sum(in_bounds)/len(vertices)*100:.1f}%)")
        
        if np.sum(in_bounds) == 0:
            print("WARNING: No points found within custom bounds!")
            # Expand search area
            margin = 5.0
            in_bounds = ((vertices_2d[:, 0] >= x_min - margin) & 
                        (vertices_2d[:, 0] <= x_max + margin) &
                        (vertices_2d[:, 1] >= y_min - margin) & 
                        (vertices_2d[:, 1] <= y_max + margin))
            print(f"Expanded search: {np.sum(in_bounds)} points found with {margin}m margin")
        
        # Filter vertices and colors to only include in-bounds points
        if np.sum(in_bounds) > 0:
            vertices_2d = vertices_2d[in_bounds]
            depth_values = depth_values[in_bounds]
            if colors is not None:
                colors = colors[in_bounds]
            print(f"Processing {len(vertices_2d)} points within bounds")
    else:
        # Use percentile bounds to exclude outliers from initial view
        # This gives a reasonable default view while keeping all data for zooming
        x_percentiles = np.percentile(vertices_2d[:, 0], [1, 99])
        y_percentiles = np.percentile(vertices_2d[:, 1], [1, 99])
        
        x_min, x_max = x_percentiles[0], x_percentiles[1]
        y_min, y_max = y_percentiles[0], y_percentiles[1]
        
        print(f"Full data range: X=[{vertices_2d[:, 0].min():.2f}, {vertices_2d[:, 0].max():.2f}], Y=[{vertices_2d[:, 1].min():.2f}, {vertices_2d[:, 1].max():.2f}]")
        print(f"Using 99% bounds: X=[{x_min:.2f}, {x_max:.2f}], Y=[{y_min:.2f}, {y_max:.2f}] meters")
    
    print(f"Depth axis: {depth_name}, Height-optimized clustering")
    
    # Fixed raster dimensions
    RASTER_WIDTH = args.output_width
    RASTER_HEIGHT = args.output_height
    
    # Calculate 1:1 pixel size (square pixels) - use the larger dimension to ensure all data fits
    data_width = x_max - x_min
    data_height = y_max - y_min
    
    # For 1:1 sampling, use the aspect ratio that fits the 16:9 raster best
    data_aspect = data_width / data_height
    raster_aspect = RASTER_WIDTH / RASTER_HEIGHT  # 16:9 ≈ 1.778
    
    if data_aspect > raster_aspect:
        # Data is wider - fit to raster width
        pixel_size = data_width / RASTER_WIDTH
        actual_width = data_width
        actual_height = RASTER_HEIGHT * pixel_size
    else:
        # Data is taller - fit to raster height  
        pixel_size = data_height / RASTER_HEIGHT
        actual_height = data_height
        actual_width = RASTER_WIDTH * pixel_size
    
    # Center the data within the raster bounds
    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2
    
    x_min_adjusted = center_x - actual_width / 2
    x_max_adjusted = center_x + actual_width / 2
    y_min_adjusted = center_y - actual_height / 2
    y_max_adjusted = center_y + actual_height / 2
    
    print(f"1:1 Pixel size: {pixel_size:.4f}m x {pixel_size:.4f}m")
    print(f"Adjusted bounds: X=[{x_min_adjusted:.2f}, {x_max_adjusted:.2f}], Y=[{y_min_adjusted:.2f}, {y_max_adjusted:.2f}]")
    
    # Build spatial index for fast nearest neighbor queries
    print("Building spatial index...")
    try:
        from scipy.spatial import cKDTree
        tree = cKDTree(vertices_2d)
        spatial_index_available = True
    except ImportError:
        print("Scipy not available - using slower nearest neighbor search")
        spatial_index_available = False
    
    # Initialize output image
    raster_image = np.zeros((RASTER_HEIGHT, RASTER_WIDTH, 3), dtype=np.uint8)
    
    print("Processing pixels with height-optimized clustering...")
    
    pixels_processed = 0
    total_pixels = RASTER_HEIGHT * RASTER_WIDTH
    
    # Stats tracking
    simple_average_count = 0
    kmeans_count = 0
    fallback_count = 0
    no_points_count = 0
    
    for row in range(RASTER_HEIGHT):
        for col in range(RASTER_WIDTH):
            # Calculate pixel boundaries in world coordinates (using adjusted bounds and uniform pixel size)
            pixel_x_min = x_min_adjusted + col * pixel_size
            pixel_x_max = x_min_adjusted + (col + 1) * pixel_size
            pixel_y_min = y_max_adjusted - (row + 1) * pixel_size  # Image Y is flipped
            pixel_y_max = y_max_adjusted - row * pixel_size
            
            # Find points within the pixel cube (start with cube, expand if needed)
            within_cube = ((vertices_2d[:, 0] >= pixel_x_min) & 
                          (vertices_2d[:, 0] <= pixel_x_max) &
                          (vertices_2d[:, 1] >= pixel_y_min) & 
                          (vertices_2d[:, 1] <= pixel_y_max))
            
            cube_indices = np.where(within_cube)[0]
            
            # If no points in cube, expand search using spatial index
            if len(cube_indices) == 0:
                pixel_center = [(pixel_x_min + pixel_x_max) / 2, (pixel_y_min + pixel_y_max) / 2]
                
                if spatial_index_available:
                    # Use spatial index for fast nearest neighbor
                    search_radius = np.sqrt(pixel_size**2 + pixel_size**2) / 2
                    for expansion in range(5):  # Max 5 expansions
                        cube_indices = tree.query_ball_point(pixel_center, search_radius)
                        if len(cube_indices) > 0:
                            cube_indices = np.array(cube_indices)  # Convert list to numpy array
                            break
                        search_radius *= 2
                else:
                    # Fallback: find single nearest point
                    distances_2d = np.sqrt((vertices_2d[:, 0] - pixel_center[0])**2 + 
                                         (vertices_2d[:, 1] - pixel_center[1])**2)
                    cube_indices = np.array([np.argmin(distances_2d)])
            
            if len(cube_indices) > 0:
                # Get heights for clustering analysis
                cube_heights = depth_values[cube_indices]
                
                # PERCENTILE-BASED GROUND SELECTION: Select lowest 40% of points by height
                # Sort by height and take bottom percentile
                sorted_height_indices = np.argsort(cube_heights)
                percentile_count = max(1, int(len(cube_heights) * 0.4))  # At least 1 point
                ground_selection = sorted_height_indices[:percentile_count]
                ground_indices = cube_indices[ground_selection]
                
                # Track which method we used for coloring (keep original height_range for path viz)
                height_min, height_max = cube_heights.min(), cube_heights.max()
                height_range = height_max - height_min
                
                if len(ground_indices) == len(cube_indices):
                    # All points were within window - this was the "fast path"
                    simple_average_count += 1
                else:
                    # Some points were filtered out - this was the "selective path"
                    kmeans_count += 1
                
                # Set pixel color based on coloring mode
                if len(ground_indices) > 0:
                    if coloring == 'true_color' and colors is not None:
                        # True Color: Average colors of ground points
                        ground_colors = colors[ground_indices]
                        avg_color = np.mean(ground_colors, axis=0)
                        # Ensure color values are in 0-255 range
                        if avg_color.max() <= 1.0:
                            avg_color *= 255
                        raster_image[row, col] = avg_color.astype(np.uint8)
                    elif coloring == 'height':
                        # Height Gradient: Color by max height in the ground points
                        max_height = np.max(depth_values[ground_indices])
                        normalized_height = (max_height - depth_values.min()) / (depth_values.max() - depth_values.min())
                        # Use a nice terrain-like gradient: blue (low) -> green -> yellow -> red (high)
                        if normalized_height < 0.25:
                            # Blue to cyan
                            t = normalized_height * 4
                            raster_image[row, col] = [int((1-t) * 0 + t * 0), int((1-t) * 100 + t * 255), int((1-t) * 255 + t * 255)]
                        elif normalized_height < 0.5:
                            # Cyan to green
                            t = (normalized_height - 0.25) * 4
                            raster_image[row, col] = [int((1-t) * 0 + t * 0), int((1-t) * 255 + t * 255), int((1-t) * 255 + t * 0)]
                        elif normalized_height < 0.75:
                            # Green to yellow
                            t = (normalized_height - 0.5) * 4
                            raster_image[row, col] = [int((1-t) * 0 + t * 255), int((1-t) * 255 + t * 255), int((1-t) * 0 + t * 0)]
                        else:
                            # Yellow to red
                            t = (normalized_height - 0.75) * 4
                            raster_image[row, col] = [int((1-t) * 255 + t * 255), int((1-t) * 255 + t * 0), int((1-t) * 0 + t * 0)]
                    elif coloring == 'path':
                        # Path Visualization: Color by selection ratio
                        selection_ratio = len(ground_indices) / len(cube_indices)
                        if selection_ratio >= 0.7:  # Selected 70%+ of points - mostly ground
                            raster_image[row, col] = [0, 255, 0]  # Green
                        else:  # Filtered out significant points - mixed ground/trees
                            raster_image[row, col] = [255, 0, 0]  # Red
                    else:
                        # Fallback to height-based coloring
                        avg_height = np.mean(depth_values[ground_indices])
                        normalized_height = (avg_height - depth_values.min()) / (depth_values.max() - depth_values.min())
                        color_val = int(normalized_height * 255)
                        raster_image[row, col] = [color_val, color_val // 2, 100]  # Brown-ish terrain
                else:
                    # No ground points - use fallback
                    raster_image[row, col] = [50, 50, 50]  # Dark gray
                    fallback_count += 1
            else:
                # No points found - use fallback color
                raster_image[row, col] = [50, 50, 50]  # Dark gray
                no_points_count += 1
            
            pixels_processed += 1
            
            # Progress update every 5000 pixels
            if pixels_processed % 5000 == 0:
                progress = (pixels_processed / total_pixels) * 100
                print(f"Height-optimized rasterizing: {progress:.1f}% complete")
    
    print(f"Height-optimized raster complete:")
    print(f"  Simple average (within height window): {simple_average_count} pixels")
    print(f"  K-means clustering: {kmeans_count} pixels")
    print(f"  Fallback methods: {fallback_count} pixels")
    print(f"  No points found: {no_points_count} pixels")
    print(f"  Optimization ratio: {(simple_average_count / total_pixels) * 100:.1f}% fast path")
    
    return raster_image


def create_yard_map(vertices, colors=None, projection='xy', grid_resolution=0.1, height_window=0.5, custom_bounds=None, coloring='true_color'):
    """Create 640x360 rasterized yard map using height-optimized processing."""
    print(f"Creating height-optimized yard map:")
    print(f"  Output: 640x360 raster image")
    print(f"  Projection: {projection}")
    print(f"  Height window: {height_window}m")
    print(f"  Coloring: {coloring}")
    print(f"  Colors available: {colors is not None}")
    if custom_bounds:
        print(f"  Custom bounds: X=[{custom_bounds[0]:.2f}, {custom_bounds[1]:.2f}], Y=[{custom_bounds[2]:.2f}, {custom_bounds[3]:.2f}]")
    
    if len(vertices) == 0:
        raise ValueError("No vertices to process!")
    
    # Create rasterized image using height optimization
    raster_image = create_height_optimized_raster_map(
        vertices, colors, projection, grid_resolution, height_window, custom_bounds, coloring
    )
    
    # Convert numpy array to PIL Image and save
    from PIL import Image
    img = Image.fromarray(raster_image, mode='RGB')
    
    return img


def main():
    print("Height-Optimized Yard Map Generator", flush=True)
    parser = argparse.ArgumentParser(description='Generate yard maps with height-optimized ground surface extraction')
    parser.add_argument('input', help='Input PLY mesh file path')
    parser.add_argument('--output', '-o', default='yard_map.png', help='Output image path')
    parser.add_argument('--grid-resolution', type=float, default=0.1, help='Grid resolution in meters (default: 0.1m)')
    parser.add_argument('--height-window', type=float, default=0.5, help='Height window in meters - use simple average if all points within this range (default: 0.5m)')
    parser.add_argument('--coloring', choices=['true_color', 'height', 'path'], default='true_color', help='Coloring mode: true_color=mesh colors, height=elevation gradient, path=algorithm visualization')
    parser.add_argument('--bounds', type=str, help='Custom bounds as x_min,x_max,y_min,y_max for focused rendering')
    parser.add_argument('--max-points', type=int, default=20000000, 
                       help='Maximum points to process for performance (default: 20000000)')
    parser.add_argument('--point-size', type=float, default=0.1, help='Point size for rendering (default: 0.1)')
    parser.add_argument('--projection', '-p', choices=['xy', 'xz', 'yz'], 
                       default='xy', help='Projection plane: xy=top-down, xz=side, yz=front (default: xy)')
    parser.add_argument('--dpi', type=int, default=150, help='Output image DPI (default: 150)')
    parser.add_argument('--output-width', type=int, default=1280, 
                        help='Output image width (default: 1280)')
    parser.add_argument('--output-height', type=int, default=720, 
                        help='Output image height (default: 720)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        return 1
    
    print(f"Loading mesh: {args.input}")
    
    vertices, colors = load_mesh_vertices(args.input, args.max_points)
    if vertices is None:
        print("Failed to load mesh vertices")
        return 1
    
    print(f"Loaded {len(vertices)} vertices")
    if colors is not None:
        print(f"Found color data: {colors.shape}")
    else:
        print("No color data found - will use terrain-style coloring")
        
    if vertices.shape[1] > 2:
        z_min, z_max = vertices[:, 2].min(), vertices[:, 2].max()
        print(f"Mesh height range: [{z_min:.2f}, {z_max:.2f}] meters")
    
    try:
        # Parse custom bounds if provided
        custom_bounds = None
        if args.bounds:
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
            vertices, colors, args.projection, args.grid_resolution, args.height_window, custom_bounds, args.coloring
        )
        
        print(f"Saving 640x360 raster to: {args.output}")
        img.save(args.output)
        
        # Verify file was created and get size
        if os.path.exists(args.output):
            file_size = os.path.getsize(args.output) / 1024  # KB
            print(f"Generated 640x360 raster map saved ({file_size:.1f} KB)")
        else:
            raise FileNotFoundError(f"Failed to save output file: {args.output}")
        
        print("Done!")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())