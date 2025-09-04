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

try:
    import trimesh
    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False


def load_mesh_vertices(ply_path, max_points=100000):
    """Load mesh vertices, sampling if too large."""
    if TRIMESH_AVAILABLE:
        try:
            mesh = trimesh.load(ply_path)
            vertices = mesh.vertices
            
            # Sample if too many points
            if len(vertices) > max_points:
                indices = np.random.choice(len(vertices), max_points, replace=False)
                vertices = vertices[indices]
                print(f"Sampled {max_points} vertices from {len(mesh.vertices)} total")
            
            return vertices
        except Exception as e:
            print(f"Trimesh failed: {e}")
    
    return None


def filter_by_height(vertices, z_min=None, z_max=None):
    """Filter vertices by Z coordinate."""
    if vertices.shape[1] < 3:
        return vertices
    
    mask = np.ones(len(vertices), dtype=bool)
    
    if z_min is not None:
        mask &= (vertices[:, 2] >= z_min)
        print(f"Filtering Z >= {z_min}")
    
    if z_max is not None:
        mask &= (vertices[:, 2] <= z_max)
        print(f"Filtering Z <= {z_max}")
    
    filtered = vertices[mask]
    print(f"Kept {len(filtered)}/{len(vertices)} vertices after Z filtering")
    
    return filtered


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


def create_yard_map(vertices, z_min=None, z_max=None, point_size=0.1, colormap='terrain', projection='xy'):
    """Create yard map with height filtering and configurable projection."""
    
    # Filter by height
    filtered_vertices = filter_by_height(vertices, z_min, z_max)
    
    if len(filtered_vertices) == 0:
        raise ValueError("No vertices remaining after filtering!")
    
    # Project to 2D
    vertices_2d = project_to_2d(filtered_vertices, projection)
    
    # Extract coordinates
    x = vertices_2d[:, 0]
    y = vertices_2d[:, 1]
    z = filtered_vertices[:, 2] if filtered_vertices.shape[1] > 2 else None
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 12))
    
    if z is not None:
        # Color by height
        scatter = ax.scatter(x, y, c=z, cmap=colormap, s=point_size, alpha=0.6)
        plt.colorbar(scatter, ax=ax, label='Height (Z meters)')
    else:
        ax.scatter(x, y, s=point_size, alpha=0.6, color='green')
    
    # Set equal aspect and limits
    ax.set_aspect('equal')
    
    # Labels based on projection
    projection_labels = {
        'xy': ('X (meters)', 'Y (meters)', 'Top-Down View'),
        'xz': ('X (meters)', 'Z (meters)', 'Side View'),
        'yz': ('Y (meters)', 'Z (meters)', 'Front View')
    }
    
    xlabel, ylabel, title_suffix = projection_labels.get(projection, ('X', 'Y', 'View'))
    
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(f'Yard Map - {title_suffix} (Height Filtered)')
    ax.grid(True, alpha=0.3)
    
    # Print stats
    if z is not None:
        print(f"Height range in map: {z.min():.2f} to {z.max():.2f} meters")
    print(f"Area bounds: X=[{x.min():.2f}, {x.max():.2f}], Y=[{y.min():.2f}, {y.max():.2f}]")
    
    return fig, ax


def main():
    parser = argparse.ArgumentParser(description='Fast yard map generator with height filtering')
    parser.add_argument('input', help='Input PLY file path')
    parser.add_argument('--output', '-o', default='yard_map.png', help='Output image path')
    parser.add_argument('--z-max', type=float, help='Maximum Z height (filter out trees/foliage)')
    parser.add_argument('--z-min', type=float, help='Minimum Z height (filter out underground)')
    parser.add_argument('--max-points', type=int, default=100000, 
                       help='Maximum points to process (for performance)')
    parser.add_argument('--point-size', type=float, default=0.1, help='Point size for rendering')
    parser.add_argument('--colormap', default='terrain', help='Color map name')
    parser.add_argument('--projection', '-p', choices=['xy', 'xz', 'yz'], 
                       default='xy', help='Projection plane (default: xy for top-down)')
    parser.add_argument('--dpi', type=int, default=150, help='Output DPI')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        return 1
    
    print(f"Loading mesh from: {args.input}")
    
    vertices = load_mesh_vertices(args.input, args.max_points)
    if vertices is None:
        print("Failed to load mesh vertices")
        return 1
    
    print(f"Loaded {len(vertices)} vertices")
    if vertices.shape[1] > 2:
        z_min, z_max = vertices[:, 2].min(), vertices[:, 2].max()
        print(f"Original Z-range: [{z_min:.2f}, {z_max:.2f}] meters")
        
        # Suggest filtering values
        if args.z_max is None and args.z_min is None:
            print(f"\nSuggested Z-max for filtering trees: {z_max * 0.3:.1f} to {z_max * 0.7:.1f}")
            print(f"Use --z-max to filter out high points like trees")
    
    print(f"Creating yard map with {args.projection} projection...")
    print(f"Configuration: max_points={args.max_points}, point_size={args.point_size}, colormap={args.colormap}")
    
    try:
        fig, ax = create_yard_map(vertices, args.z_min, args.z_max, args.point_size, args.colormap, args.projection)
        
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