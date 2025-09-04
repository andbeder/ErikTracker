#!/usr/bin/env python3
"""
Fast yard map generator with Z-filtering for large meshes.
Container-friendly version for Erik Image Manager.
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


def create_ground_surface_map(vertices, colors=None, projection='xy', grid_resolution=0.1, height_window=None):
    """Create ground surface map using cube projection with optimized height filtering.
    
    For each pixel, projects a cube from pixel edges and finds points within.
    If all points fit within height_window: simple average (fast)
    If points spread across heights: K-means clustering to separate ground from foliage
    """
    print(f"Creating ground surface with cube projection: {grid_resolution}m resolution, height_window: {height_window}m")
    
    if vertices.shape[1] < 3:
        return vertices, colors
    
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
        return vertices, colors
    
    # Create pixel grid bounds
    x_min, x_max = vertices_2d[:, 0].min(), vertices_2d[:, 0].max()
    y_min, y_max = vertices_2d[:, 1].min(), vertices_2d[:, 1].max()
    
    # Calculate grid dimensions
    x_pixels = int(np.ceil((x_max - x_min) / grid_resolution))
    y_pixels = int(np.ceil((y_max - y_min) / grid_resolution))
    
    print(f"Cube projection grid: {x_pixels}x{y_pixels} pixels, depth axis: {depth_name}, clustering window: {grid_resolution}m")
    
    ground_vertices = []
    ground_colors = [] if colors is not None else None
    
    # Project cube from each pixel
    for i in range(x_pixels):
        for j in range(y_pixels):
            # Calculate pixel edges (cube boundaries)
            pixel_x_min = x_min + i * grid_resolution
            pixel_x_max = x_min + (i + 1) * grid_resolution
            pixel_y_min = y_min + j * grid_resolution
            pixel_y_max = y_min + (j + 1) * grid_resolution
            
            # Find all points within the cube projection
            within_cube = ((vertices_2d[:, 0] >= pixel_x_min) & 
                          (vertices_2d[:, 0] <= pixel_x_max) &
                          (vertices_2d[:, 1] >= pixel_y_min) & 
                          (vertices_2d[:, 1] <= pixel_y_max))
            
            if not np.any(within_cube):
                # No points found in cube, find nearest point as fallback
                pixel_center_x = (pixel_x_min + pixel_x_max) / 2
                pixel_center_y = (pixel_y_min + pixel_y_max) / 2
                distances_2d = np.sqrt((vertices_2d[:, 0] - pixel_center_x)**2 + 
                                     (vertices_2d[:, 1] - pixel_center_y)**2)
                closest_idx = np.argmin(distances_2d)
                ground_vertices.append(vertices[closest_idx])
                if colors is not None:
                    ground_colors.append(colors[closest_idx])
                continue
            
            # Get points and depths within cube
            cube_indices = np.where(within_cube)[0]
            cube_depths = depth_values[within_cube]
            
            # Optimized height filtering: check if all points fit within height window
            depth_min, depth_max = cube_depths.min(), cube_depths.max()
            depth_range = depth_max - depth_min
            
            if height_window is not None and depth_range <= height_window:
                # All points within height window - simple average (fast path)
                best_cluster = cube_indices
            else:
                # Points spread across heights - use K-means to separate ground from foliage
                if len(cube_depths) >= 2:
                    try:
                        from sklearn.cluster import KMeans
                        # Use K-means with n=2 to separate ground and foliage
                        kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
                        cluster_labels = kmeans.fit_predict(cube_depths.reshape(-1, 1))
                        
                        # Find the cluster with the lower centroid (ground)
                        centroids = kmeans.cluster_centers_.flatten()
                        ground_cluster_label = np.argmin(centroids)
                        
                        # Select indices belonging to ground cluster
                        ground_mask = cluster_labels == ground_cluster_label
                        best_cluster = cube_indices[ground_mask]
                    except ImportError:
                        # Fallback to simple lowest point selection if sklearn not available
                        lowest_idx = np.argmin(cube_depths)
                        best_cluster = cube_indices[lowest_idx:lowest_idx+1]
                else:
                    # Single point or empty - use all points
                    best_cluster = cube_indices
            
            # Average position and color from best cluster
            if best_cluster is not None and len(best_cluster) > 0:
                # Average vertex position in the cluster
                cluster_vertices = vertices[best_cluster]
                avg_vertex = np.mean(cluster_vertices, axis=0)
                ground_vertices.append(avg_vertex)
                
                # Average colors in the cluster
                if colors is not None:
                    cluster_colors = colors[best_cluster]
                    avg_color = np.mean(cluster_colors, axis=0)
                    ground_colors.append(avg_color)
    
    ground_vertices = np.array(ground_vertices)
    if colors is not None:
        ground_colors = np.array(ground_colors)
    
    print(f"Ray-cast ground surface: {len(ground_vertices)} pixels from {len(vertices)} input points")
    
    return ground_vertices, ground_colors


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


def create_yard_map(vertices, colors=None, depth_min=None, depth_max=None, point_size=0.1, colormap='terrain', projection='xy', grid_resolution=0.1, height_window=None):
    """Create yard map using ground-up projection to show ground surface with true colors."""
    print(f"DEBUG: create_yard_map called with colormap='{colormap}', projection='{projection}'")
    print(f"DEBUG: colors is None: {colors is None}")
    
    # For true-color ground mapping, we want to show the ground surface
    # We'll project from ground up, so ground pixels override tree pixels
    
    # Project all vertices to 2D first
    vertices_2d = project_to_2d(vertices, projection)
    
    if len(vertices_2d) == 0:
        raise ValueError("No vertices to process!")
    
    # Create cube-projected ground surface: for each pixel, find ground points via height clustering
    # This naturally filters out trees and gives us the ground surface
    filtered_vertices, filtered_colors = create_ground_surface_map(vertices, colors, projection, grid_resolution, height_window)
    vertices_2d = project_to_2d(filtered_vertices, projection)
    
    # Extract coordinates
    x = vertices_2d[:, 0]
    y = vertices_2d[:, 1]
    
    print(f"Ground surface projection: {len(filtered_vertices)} points")
    print(f"Colors available: {filtered_colors is not None}")
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # For Erik's position tracking, we prioritize true colors from the mesh
    if filtered_colors is not None:
        # Use true colors from mesh - this is the primary goal
        print(f"Using true colors from ground surface")
        colors_normalized = filtered_colors / 255.0 if filtered_colors.max() > 1 else filtered_colors
        scatter = ax.scatter(x, y, c=colors_normalized, s=point_size, alpha=0.8)
        print("Applied true colors from mesh data")
    else:
        # Fallback to terrain-based coloring if no color data
        print("No color data available, using terrain-style coloring")
        if filtered_vertices.shape[1] > 2:
            if projection == 'xy':
                height_data = filtered_vertices[:, 2]
                height_label = 'Ground Height (Z meters)'
            elif projection == 'xz':
                height_data = filtered_vertices[:, 1] 
                height_label = 'Ground Depth (Y meters)'
            elif projection == 'yz':
                height_data = filtered_vertices[:, 0]
                height_label = 'Ground Depth (X meters)'
            
            scatter = ax.scatter(x, y, c=height_data, cmap='terrain', s=point_size, alpha=0.8)
            plt.colorbar(scatter, ax=ax, label=height_label)
        else:
            ax.scatter(x, y, s=point_size, alpha=0.8, color='brown')
    
    # Set equal aspect and limits
    ax.set_aspect('equal')
    
    # Labels based on projection
    projection_labels = {
        'xy': ('X (meters)', 'Y (meters)', 'Top-Down Ground View'),
        'xz': ('X (meters)', 'Z (meters)', 'Side Ground View'),
        'yz': ('Y (meters)', 'Z (meters)', 'Front Ground View')
    }
    
    xlabel, ylabel, title_suffix = projection_labels.get(projection, ('X', 'Y', 'Ground View'))
    
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(f'Erik\'s Yard Map - {title_suffix}')
    ax.grid(True, alpha=0.3)
    
    # Print ground surface stats
    print(f"Ground surface bounds:")
    if projection == 'xy':
        print(f"  X=[{x.min():.2f}, {x.max():.2f}], Y=[{y.min():.2f}, {y.max():.2f}] meters")
    elif projection == 'xz':
        print(f"  X=[{x.min():.2f}, {x.max():.2f}], Z=[{y.min():.2f}, {y.max():.2f}] meters")
    elif projection == 'yz':
        print(f"  Y=[{x.min():.2f}, {x.max():.2f}], Z=[{y.min():.2f}, {y.max():.2f}] meters")
    
    return fig, ax


def main():
    print("DEBUG: Starting main function", flush=True)
    parser = argparse.ArgumentParser(description='Generate true-color ground surface maps for Erik position tracking')
    parser.add_argument('input', help='Input PLY mesh file path')
    parser.add_argument('--output', '-o', default='yard_map.png', help='Output image path')
    parser.add_argument('--grid-resolution', type=float, default=0.1, help='Grid resolution in meters (default: 0.1m)')
    parser.add_argument('--height-window', type=float, help='Height window in meters - use simple average if all points within this range (default: use K-means)')
    parser.add_argument('--search-distance', type=float, help='DEPRECATED: Not used with cube projection')
    parser.add_argument('--max-points', type=int, default=100000, 
                       help='Maximum points to process for performance (default: 100000)')
    parser.add_argument('--point-size', type=float, default=0.1, help='Point size for rendering (default: 0.1)')
    parser.add_argument('--projection', '-p', choices=['xy', 'xz', 'yz'], 
                       default='xy', help='Projection plane: xy=top-down, xz=side, yz=front (default: xy)')
    parser.add_argument('--dpi', type=int, default=150, help='Output image DPI (default: 150)')
    # Keep old parameters for backward compatibility (but ignore them)
    parser.add_argument('--depth-max', type=float, help='DEPRECATED: Ground-up projection used instead')
    parser.add_argument('--depth-min', type=float, help='DEPRECATED: Ground-up projection used instead')
    parser.add_argument('--z-max', type=float, help='DEPRECATED: Ground-up projection used instead')
    parser.add_argument('--z-min', type=float, help='DEPRECATED: Ground-up projection used instead')
    parser.add_argument('--colormap', default='true_color', help='DEPRECATED: Always uses true colors when available')
    
    args = parser.parse_args()
    
    # Warn about deprecated parameters
    deprecated_params = []
    if args.depth_max is not None or args.depth_min is not None:
        deprecated_params.extend(['--depth-max', '--depth-min'])
    if args.z_max is not None or args.z_min is not None:
        deprecated_params.extend(['--z-max', '--z-min'])
    
    if deprecated_params:
        print(f"Note: {', '.join(deprecated_params)} parameters are deprecated.")
        print("      Ground-up projection is now used automatically for clean ground surface mapping.")
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        return 1
    
    print(f"Loading mesh for Erik's yard mapping: {args.input}")
    
    vertices, colors = load_mesh_vertices(args.input, args.max_points)
    if vertices is None:
        print("Failed to load mesh vertices")
        return 1
    
    print(f"Loaded {len(vertices)} vertices for ground surface extraction")
    if colors is not None:
        print(f"Found true color data: {colors.shape} - perfect for position tracking!")
    else:
        print("No color data found - will use terrain-style coloring")
        
    if vertices.shape[1] > 2:
        z_min, z_max = vertices[:, 2].min(), vertices[:, 2].max()
        print(f"Mesh height range: [{z_min:.2f}, {z_max:.2f}] meters")
    
    print(f"Generating cube-projected ground surface map...")
    print(f"  Projection: {args.projection}")
    print(f"  Grid resolution: {args.grid_resolution}m")
    print(f"  Point size: {args.point_size}")
    
    try:
        fig, ax = create_yard_map(vertices, colors, None, None, args.point_size, 'true_color', args.projection, args.grid_resolution, args.height_window)
        
        print(f"Saving to: {args.output}")
        plt.savefig(args.output, dpi=args.dpi, bbox_inches='tight', facecolor='white')
        plt.close()
        
        # Verify file was created and get size
        if os.path.exists(args.output):
            file_size = os.path.getsize(args.output) / 1024  # KB
            print(f"Generated map saved ({file_size:.1f} KB)")
        else:
            raise FileNotFoundError(f"Failed to save output file: {args.output}")
        
        print("Done!")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())