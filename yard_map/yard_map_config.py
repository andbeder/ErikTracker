#!/usr/bin/env python3
"""
Configurable mesh to yard map converter with Z-offset filtering.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
import argparse
import json
import os

try:
    import trimesh
    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False

try:
    from plyfile import PlyData
    PLYFILE_AVAILABLE = True
except ImportError:
    PLYFILE_AVAILABLE = False


class YardMapConfig:
    """Configuration class for yard map generation."""
    
    def __init__(self):
        self.z_max_filter = None  # Maximum Z height to include
        self.z_min_filter = None  # Minimum Z height to include
        self.projection = 'xy'    # Projection plane
        self.resolution = 1000    # Output resolution
        self.dpi = 150           # Output DPI
        self.colormap = 'terrain' # Color map for height visualization
        self.point_size = 0.5    # Point size for point cloud rendering
        self.alpha = 0.6         # Transparency
        self.grid = True         # Show grid
        self.equal_aspect = True # Equal aspect ratio
        self.output_format = 'png' # Output format
        
    def save(self, filepath):
        """Save configuration to JSON file."""
        config_dict = {
            'z_max_filter': self.z_max_filter,
            'z_min_filter': self.z_min_filter,
            'projection': self.projection,
            'resolution': self.resolution,
            'dpi': self.dpi,
            'colormap': self.colormap,
            'point_size': self.point_size,
            'alpha': self.alpha,
            'grid': self.grid,
            'equal_aspect': self.equal_aspect,
            'output_format': self.output_format
        }
        with open(filepath, 'w') as f:
            json.dump(config_dict, f, indent=2)
    
    def load(self, filepath):
        """Load configuration from JSON file."""
        with open(filepath, 'r') as f:
            config_dict = json.load(f)
        
        for key, value in config_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def interactive_setup(self, vertices=None):
        """Interactive configuration setup."""
        print("\n=== Yard Map Configuration ===")
        
        # Z-filtering setup
        if vertices is not None and vertices.shape[1] > 2:
            z_min, z_max = vertices[:, 2].min(), vertices[:, 2].max()
            print(f"\nMesh Z-range: [{z_min:.2f}, {z_max:.2f}] meters")
            
            # Z-max filter (remove high points like trees)
            response = input(f"Set maximum Z height to filter out trees/foliage? (current: {self.z_max_filter}, range: {z_min:.2f}-{z_max:.2f}): ").strip()
            if response:
                try:
                    self.z_max_filter = float(response)
                except ValueError:
                    print("Invalid value, keeping current setting")
            
            # Z-min filter (remove low points like underground)
            response = input(f"Set minimum Z height to filter out underground points? (current: {self.z_min_filter}): ").strip()
            if response:
                try:
                    self.z_min_filter = float(response)
                except ValueError:
                    print("Invalid value, keeping current setting")
        
        # Projection
        response = input(f"Projection plane (xy/xz/yz) [current: {self.projection}]: ").strip().lower()
        if response in ['xy', 'xz', 'yz']:
            self.projection = response
        
        # Colormap
        response = input(f"Color map (terrain/viridis/plasma/coolwarm/jet) [current: {self.colormap}]: ").strip().lower()
        if response:
            self.colormap = response
        
        # Point size
        response = input(f"Point size for rendering [current: {self.point_size}]: ").strip()
        if response:
            try:
                self.point_size = float(response)
            except ValueError:
                print("Invalid value, keeping current setting")
        
        # Alpha transparency
        response = input(f"Transparency (0.0-1.0) [current: {self.alpha}]: ").strip()
        if response:
            try:
                alpha = float(response)
                if 0.0 <= alpha <= 1.0:
                    self.alpha = alpha
                else:
                    print("Alpha must be between 0.0 and 1.0")
            except ValueError:
                print("Invalid value, keeping current setting")
        
        # DPI
        response = input(f"Output DPI [current: {self.dpi}]: ").strip()
        if response:
            try:
                self.dpi = int(response)
            except ValueError:
                print("Invalid value, keeping current setting")
        
        print(f"\nConfiguration complete!")
        self.print_summary()
    
    def print_summary(self):
        """Print current configuration."""
        print(f"""
Current Configuration:
  - Z-height filter: {self.z_min_filter} to {self.z_max_filter}
  - Projection: {self.projection}
  - Colormap: {self.colormap}
  - Point size: {self.point_size}
  - Transparency: {self.alpha}
  - DPI: {self.dpi}
        """)


def load_ply_with_plyfile(ply_path):
    """Load PLY file using plyfile library."""
    plydata = PlyData.read(ply_path)
    
    vertex_data = plydata['vertex']
    vertices = np.column_stack([
        vertex_data['x'],
        vertex_data['y'], 
        vertex_data['z']
    ])
    
    faces = None
    if 'face' in plydata:
        face_data = plydata['face']
        faces = np.array([list(face[0]) for face in face_data])
    
    return vertices, faces


def load_ply_with_trimesh(ply_path):
    """Load PLY file using trimesh library."""
    mesh = trimesh.load(ply_path)
    return mesh.vertices, mesh.faces


def load_ply_basic(ply_path):
    """Basic PLY loader that reads vertex coordinates."""
    vertices = []
    faces = []
    
    with open(ply_path, 'r') as f:
        lines = f.readlines()
    
    vertex_count = 0
    face_count = 0
    header_ended = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('element vertex'):
            vertex_count = int(line.split()[-1])
        elif line.startswith('element face'):
            face_count = int(line.split()[-1])
        elif line == 'end_header':
            header_ended = True
            data_start = i + 1
            break
    
    if not header_ended:
        raise ValueError("Could not find end_header in PLY file")
    
    # Read vertices
    for i in range(data_start, data_start + vertex_count):
        parts = lines[i].strip().split()
        x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
        vertices.append([x, y, z])
    
    # Read faces
    face_start = data_start + vertex_count
    for i in range(face_start, face_start + face_count):
        parts = lines[i].strip().split()
        if len(parts) >= 4:
            face_vertices = [int(parts[j]) for j in range(1, int(parts[0]) + 1)]
            faces.append(face_vertices)
    
    return np.array(vertices), np.array(faces) if faces else None


def filter_vertices_by_z(vertices, faces=None, z_min=None, z_max=None):
    """Filter vertices and faces by Z coordinate."""
    if vertices.shape[1] < 3:
        return vertices, faces
    
    # Create mask for Z filtering
    mask = np.ones(len(vertices), dtype=bool)
    
    if z_min is not None:
        mask &= (vertices[:, 2] >= z_min)
    
    if z_max is not None:
        mask &= (vertices[:, 2] <= z_max)
    
    # Filter vertices
    filtered_vertices = vertices[mask]
    
    # Filter faces if available
    filtered_faces = None
    if faces is not None and len(faces) > 0:
        # Create mapping from old indices to new indices
        old_to_new = {}
        new_idx = 0
        for old_idx, keep in enumerate(mask):
            if keep:
                old_to_new[old_idx] = new_idx
                new_idx += 1
        
        # Filter faces that have all vertices still valid
        valid_faces = []
        for face in faces:
            if all(v in old_to_new for v in face):
                new_face = [old_to_new[v] for v in face]
                valid_faces.append(new_face)
        
        if valid_faces:
            filtered_faces = np.array(valid_faces)
    
    print(f"Filtered from {len(vertices)} to {len(filtered_vertices)} vertices")
    if faces is not None:
        print(f"Filtered from {len(faces) if faces is not None else 0} to {len(filtered_faces) if filtered_faces is not None else 0} faces")
    
    return filtered_vertices, filtered_faces


def project_to_2d(vertices, projection='xy'):
    """Project 3D vertices to 2D plane."""
    if projection == 'xy':
        return vertices[:, [0, 1]]
    elif projection == 'xz':
        return vertices[:, [0, 2]]
    elif projection == 'yz':
        return vertices[:, [1, 2]]
    else:
        raise ValueError(f"Unknown projection: {projection}")


def create_yard_map(vertices, faces, config):
    """Create a 2D yard map from 3D mesh data using configuration."""
    
    # Filter vertices by Z if configured
    if config.z_min_filter is not None or config.z_max_filter is not None:
        vertices, faces = filter_vertices_by_z(vertices, faces, config.z_min_filter, config.z_max_filter)
    
    if len(vertices) == 0:
        raise ValueError("No vertices remaining after Z filtering!")
    
    # Project to 2D
    vertices_2d = project_to_2d(vertices, config.projection)
    
    # Get bounds
    x_min, y_min = vertices_2d.min(axis=0)
    x_max, y_max = vertices_2d.max(axis=0)
    
    print(f"Filtered mesh bounds: X=[{x_min:.2f}, {x_max:.2f}], Y=[{y_min:.2f}, {y_max:.2f}]")
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 12))
    
    if faces is not None and len(faces) > 0:
        # Render triangular faces
        patches = []
        face_colors = []
        
        for face in faces:
            if len(face) >= 3:
                face_vertices_2d = vertices_2d[face[:3]]
                patches.append(Polygon(face_vertices_2d, closed=True))
                
                if vertices.shape[1] > 2:
                    avg_z = np.mean(vertices[face[:3], 2])
                    face_colors.append(avg_z)
                else:
                    face_colors.append(0.5)
        
        if patches:
            p = PatchCollection(patches, alpha=config.alpha)
            if face_colors:
                p.set_array(np.array(face_colors))
                p.set_cmap(config.colormap)
            else:
                p.set_facecolor('green')
            
            ax.add_collection(p)
            
            if face_colors:
                plt.colorbar(p, ax=ax, label='Height (Z)')
    else:
        # Render as point cloud
        if vertices.shape[1] > 2:
            scatter = ax.scatter(vertices_2d[:, 0], vertices_2d[:, 1], 
                               c=vertices[:, 2], cmap=config.colormap, 
                               s=config.point_size, alpha=config.alpha)
            plt.colorbar(scatter, ax=ax, label='Height (Z)')
        else:
            ax.scatter(vertices_2d[:, 0], vertices_2d[:, 1], 
                      s=config.point_size, alpha=config.alpha, color='green')
    
    # Set aspect ratio and limits
    if config.equal_aspect:
        ax.set_aspect('equal')
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    
    # Labels and title
    projection_labels = {'xy': ('X (meters)', 'Y (meters)', 'Top-Down View'),
                        'xz': ('X (meters)', 'Z (meters)', 'Side View'),
                        'yz': ('Y (meters)', 'Z (meters)', 'Front View')}
    
    xlabel, ylabel, title_suffix = projection_labels.get(config.projection, ('X', 'Y', 'View'))
    
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(f'Yard Map - {title_suffix}')
    
    # Grid
    if config.grid:
        ax.grid(True, alpha=0.3)
    
    return fig, ax


def main():
    parser = argparse.ArgumentParser(description='Configurable mesh to yard map converter')
    parser.add_argument('input', help='Input PLY file path')
    parser.add_argument('--config', '-c', help='Configuration file path')
    parser.add_argument('--save-config', help='Save configuration to file')
    parser.add_argument('--output', '-o', help='Output image path')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Run interactive configuration')
    parser.add_argument('--z-max', type=float, help='Maximum Z height to include (filters out high points)')
    parser.add_argument('--z-min', type=float, help='Minimum Z height to include')
    parser.add_argument('--projection', '-p', choices=['xy', 'xz', 'yz'], 
                       default='xy', help='Projection plane')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        return 1
    
    # Load configuration
    config = YardMapConfig()
    if args.config and os.path.exists(args.config):
        print(f"Loading configuration from: {args.config}")
        config.load(args.config)
    
    # Override with command line arguments
    if args.z_max is not None:
        config.z_max_filter = args.z_max
    if args.z_min is not None:
        config.z_min_filter = args.z_min
    if args.projection:
        config.projection = args.projection
    
    print(f"Loading mesh from: {args.input}")
    
    # Load mesh
    vertices = faces = None
    
    if TRIMESH_AVAILABLE:
        try:
            vertices, faces = load_ply_with_trimesh(args.input)
            print(f"Loaded with trimesh: {len(vertices)} vertices, {len(faces) if faces is not None else 0} faces")
        except Exception as e:
            print(f"Trimesh failed: {e}")
    
    if vertices is None and PLYFILE_AVAILABLE:
        try:
            vertices, faces = load_ply_with_plyfile(args.input)
            print(f"Loaded with plyfile: {len(vertices)} vertices, {len(faces) if faces is not None else 0} faces")
        except Exception as e:
            print(f"Plyfile failed: {e}")
    
    if vertices is None:
        try:
            vertices, faces = load_ply_basic(args.input)
            print(f"Loaded with basic loader: {len(vertices)} vertices, {len(faces) if faces is not None else 0} faces")
        except Exception as e:
            print(f"All loaders failed: {e}")
            return 1
    
    # Interactive configuration
    if args.interactive:
        config.interactive_setup(vertices)
    
    # Save configuration if requested
    if args.save_config:
        config.save(args.save_config)
        print(f"Configuration saved to: {args.save_config}")
    
    # Generate output path
    output_path = args.output
    if not output_path:
        base_name = os.path.splitext(os.path.basename(args.input))[0]
        output_path = f"{base_name}_yard_map.{config.output_format}"
    
    print(f"Creating yard map...")
    config.print_summary()
    
    try:
        fig, ax = create_yard_map(vertices, faces, config)
        
        print(f"Saving yard map to: {output_path}")
        plt.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
        plt.close()
        
        print("Done!")
        return 0
        
    except Exception as e:
        print(f"Error creating yard map: {e}")
        return 1


if __name__ == '__main__':
    exit(main())