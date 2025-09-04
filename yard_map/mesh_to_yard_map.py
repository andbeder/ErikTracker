#!/usr/bin/env python3
"""
Convert a Poisson mesh to a top-down yard map image.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
import argparse
import os

try:
    import trimesh
    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False
    print("Warning: trimesh not available. Install with: pip install trimesh")

try:
    from plyfile import PlyData
    PLYFILE_AVAILABLE = True
except ImportError:
    PLYFILE_AVAILABLE = False
    print("Warning: plyfile not available. Install with: pip install plyfile")


def load_ply_with_plyfile(ply_path):
    """Load PLY file using plyfile library."""
    plydata = PlyData.read(ply_path)
    
    # Extract vertices
    vertex_data = plydata['vertex']
    vertices = np.column_stack([
        vertex_data['x'],
        vertex_data['y'], 
        vertex_data['z']
    ])
    
    # Extract faces if available
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
    
    # Find header info
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
        if len(parts) >= 4:  # At least: count + 3 vertices
            face_vertices = [int(parts[j]) for j in range(1, int(parts[0]) + 1)]
            faces.append(face_vertices)
    
    return np.array(vertices), np.array(faces) if faces else None


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


def create_yard_map(vertices, faces=None, resolution=1000, projection='xy'):
    """Create a 2D yard map from 3D mesh data."""
    
    # Project to 2D
    vertices_2d = project_to_2d(vertices, projection)
    
    # Get bounds
    x_min, y_min = vertices_2d.min(axis=0)
    x_max, y_max = vertices_2d.max(axis=0)
    
    print(f"Mesh bounds: X=[{x_min:.2f}, {x_max:.2f}], Y=[{y_min:.2f}, {y_max:.2f}]")
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 12))
    
    if faces is not None and len(faces) > 0:
        # Render triangular faces
        patches = []
        face_colors = []
        
        for face in faces:
            if len(face) >= 3:
                # Get the 2D coordinates of the face vertices
                face_vertices_2d = vertices_2d[face[:3]]  # Use first 3 vertices for triangle
                patches.append(Polygon(face_vertices_2d, closed=True))
                
                # Color by average Z (height) if available
                if vertices.shape[1] > 2:
                    avg_z = np.mean(vertices[face[:3], 2])
                    face_colors.append(avg_z)
                else:
                    face_colors.append(0.5)
        
        if patches:
            p = PatchCollection(patches, alpha=0.7)
            if face_colors:
                p.set_array(np.array(face_colors))
                p.set_cmap('terrain')
            else:
                p.set_facecolor('green')
                p.set_alpha(0.5)
            
            ax.add_collection(p)
            
            if face_colors:
                plt.colorbar(p, ax=ax, label='Height (Z)')
    else:
        # Render as point cloud with height coloring
        if vertices.shape[1] > 2:
            scatter = ax.scatter(vertices_2d[:, 0], vertices_2d[:, 1], 
                               c=vertices[:, 2], cmap='terrain', s=0.5, alpha=0.6)
            plt.colorbar(scatter, ax=ax, label='Height (Z)')
        else:
            ax.scatter(vertices_2d[:, 0], vertices_2d[:, 1], s=0.5, alpha=0.6, color='green')
    
    # Set equal aspect ratio and limits
    ax.set_aspect('equal')
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    
    # Labels and title
    ax.set_xlabel('X (meters)')
    ax.set_ylabel('Y (meters)')
    ax.set_title('Yard Map - Top-Down View')
    
    # Grid
    ax.grid(True, alpha=0.3)
    
    return fig, ax


def main():
    parser = argparse.ArgumentParser(description='Convert Poisson mesh to yard map')
    parser.add_argument('input', help='Input PLY file path')
    parser.add_argument('--output', '-o', help='Output image path (default: yard_map.png)')
    parser.add_argument('--resolution', '-r', type=int, default=1000,
                       help='Output resolution (default: 1000)')
    parser.add_argument('--projection', '-p', choices=['xy', 'xz', 'yz'], 
                       default='xy', help='Projection plane (default: xy for top-down)')
    parser.add_argument('--dpi', type=int, default=150, 
                       help='Output DPI (default: 150)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        return 1
    
    output_path = args.output or 'yard_map.png'
    
    print(f"Loading mesh from: {args.input}")
    
    # Try different loading methods
    vertices = faces = None
    
    if TRIMESH_AVAILABLE:
        try:
            print("Trying trimesh loader...")
            vertices, faces = load_ply_with_trimesh(args.input)
            print(f"Loaded with trimesh: {len(vertices)} vertices, {len(faces) if faces is not None else 0} faces")
        except Exception as e:
            print(f"Trimesh failed: {e}")
    
    if vertices is None and PLYFILE_AVAILABLE:
        try:
            print("Trying plyfile loader...")
            vertices, faces = load_ply_with_plyfile(args.input)
            print(f"Loaded with plyfile: {len(vertices)} vertices, {len(faces) if faces is not None else 0} faces")
        except Exception as e:
            print(f"Plyfile failed: {e}")
    
    if vertices is None:
        try:
            print("Trying basic PLY loader...")
            vertices, faces = load_ply_basic(args.input)
            print(f"Loaded with basic loader: {len(vertices)} vertices, {len(faces) if faces is not None else 0} faces")
        except Exception as e:
            print(f"Basic loader failed: {e}")
            return 1
    
    if vertices is None or len(vertices) == 0:
        print("Error: Could not load vertices from PLY file")
        return 1
    
    print(f"Creating yard map with {args.projection} projection...")
    fig, ax = create_yard_map(vertices, faces, args.resolution, args.projection)
    
    print(f"Saving yard map to: {output_path}")
    plt.savefig(output_path, dpi=args.dpi, bbox_inches='tight')
    plt.close()
    
    print("Done!")
    return 0


if __name__ == '__main__':
    exit(main())