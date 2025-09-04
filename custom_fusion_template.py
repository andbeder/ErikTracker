#!/usr/bin/env python3
"""
Custom Fusion Script Template for COLMAP Dense Reconstruction

This script should read COLMAP's stereo depth maps and output a fused point cloud.
Modify this template with your own fusion algorithm.

Input: COLMAP dense workspace with stereo depth maps
Output: PLY file with fused point cloud

Usage:
    python3 custom_fusion.py --workspace /path/to/dense --output /path/to/fused.ply
"""

import argparse
import os
import numpy as np
from pathlib import Path
import struct
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def read_colmap_depth_map(path):
    """Read COLMAP depth map file (.dmb format)"""
    with open(path, 'rb') as f:
        # Read header
        width = struct.unpack('i', f.read(4))[0]
        height = struct.unpack('i', f.read(4))[0]
        channels = struct.unpack('i', f.read(4))[0]
        
        # Read depth values
        num_pixels = width * height * channels
        depth_data = struct.unpack('f' * num_pixels, f.read(4 * num_pixels))
        
        # Reshape to image
        depth_map = np.array(depth_data).reshape((height, width, channels))
        
    return depth_map

def read_colmap_normal_map(path):
    """Read COLMAP normal map file (.nmb format)"""
    # Similar structure to depth map
    return read_colmap_depth_map(path)

def write_ply(filename, points, colors=None, normals=None):
    """Write point cloud to PLY file"""
    
    num_points = len(points)
    
    # PLY header
    header = [
        "ply",
        "format ascii 1.0",
        f"element vertex {num_points}",
        "property float x",
        "property float y", 
        "property float z",
    ]
    
    if colors is not None:
        header.extend([
            "property uchar red",
            "property uchar green",
            "property uchar blue",
        ])
    
    if normals is not None:
        header.extend([
            "property float nx",
            "property float ny",
            "property float nz",
        ])
    
    header.append("end_header")
    
    # Write PLY file
    with open(filename, 'w') as f:
        f.write('\n'.join(header) + '\n')
        
        for i in range(num_points):
            line = f"{points[i, 0]} {points[i, 1]} {points[i, 2]}"
            
            if colors is not None:
                line += f" {int(colors[i, 0])} {int(colors[i, 1])} {int(colors[i, 2])}"
            
            if normals is not None:
                line += f" {normals[i, 0]} {normals[i, 1]} {normals[i, 2]}"
            
            f.write(line + '\n')
    
    logger.info(f"Wrote {num_points} points to {filename}")

def custom_fusion(workspace_path, output_path):
    """
    Your custom fusion implementation goes here.
    
    This template provides a basic fusion that:
    1. Reads COLMAP's depth maps from workspace/stereo/depth_maps
    2. Applies your custom fusion algorithm
    3. Outputs a PLY point cloud
    
    Modify this function with your own fusion logic.
    """
    
    stereo_dir = Path(workspace_path) / "stereo"
    depth_maps_dir = stereo_dir / "depth_maps"
    normal_maps_dir = stereo_dir / "normal_maps"
    
    if not depth_maps_dir.exists():
        raise FileNotFoundError(f"Depth maps directory not found: {depth_maps_dir}")
    
    # Collect all depth maps
    depth_files = sorted(depth_maps_dir.glob("*.dmb"))
    
    if not depth_files:
        raise FileNotFoundError("No depth map files found")
    
    logger.info(f"Found {len(depth_files)} depth maps")
    
    # =========================================
    # YOUR CUSTOM FUSION ALGORITHM STARTS HERE
    # =========================================
    
    all_points = []
    all_colors = []
    all_normals = []
    
    # Example: Simple concatenation of all depth maps
    # Replace this with your own fusion algorithm
    for depth_file in depth_files:
        logger.info(f"Processing {depth_file.name}")
        
        try:
            # Read depth map
            depth_map = read_colmap_depth_map(depth_file)
            
            # Read corresponding normal map if exists
            normal_file = normal_maps_dir / depth_file.name.replace('.dmb', '.nmb')
            if normal_file.exists():
                normal_map = read_colmap_normal_map(normal_file)
            else:
                normal_map = None
            
            # Convert depth map to 3D points
            # NOTE: This is a simplified example. You'll need proper camera calibration
            # and transformation matrices from COLMAP's cameras.bin and images.bin files
            
            height, width = depth_map.shape[:2]
            
            # Create mesh grid for pixel coordinates
            xx, yy = np.meshgrid(np.arange(width), np.arange(height))
            
            # Filter valid depth values (non-zero)
            valid_mask = depth_map[:, :, 0] > 0
            
            if np.sum(valid_mask) == 0:
                continue
            
            # Simple projection (you should use actual camera parameters)
            # This is just a placeholder - replace with your method
            points_3d = np.stack([
                xx[valid_mask],
                yy[valid_mask],
                depth_map[:, :, 0][valid_mask]
            ], axis=-1)
            
            all_points.append(points_3d)
            
            # Add dummy colors (replace with actual image colors)
            colors = np.ones((points_3d.shape[0], 3)) * 128
            all_colors.append(colors)
            
            # Add normals if available
            if normal_map is not None and normal_map.shape == depth_map.shape:
                normals_3d = normal_map[valid_mask]
                all_normals.append(normals_3d[:, :3])
            
        except Exception as e:
            logger.warning(f"Error processing {depth_file.name}: {e}")
            continue
    
    # =========================================
    # YOUR CUSTOM FUSION ALGORITHM ENDS HERE
    # =========================================
    
    if not all_points:
        raise ValueError("No valid points extracted from depth maps")
    
    # Combine all points
    final_points = np.vstack(all_points)
    final_colors = np.vstack(all_colors) if all_colors else None
    final_normals = np.vstack(all_normals) if all_normals else None
    
    logger.info(f"Total points after fusion: {len(final_points)}")
    
    # Write output PLY
    write_ply(output_path, final_points, final_colors, final_normals)
    
    return len(final_points)

def main():
    parser = argparse.ArgumentParser(description='Custom fusion for COLMAP dense reconstruction')
    parser.add_argument('--workspace', required=True, help='COLMAP dense workspace directory')
    parser.add_argument('--output', required=True, help='Output PLY file path')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        logger.info(f"Starting custom fusion...")
        logger.info(f"Workspace: {args.workspace}")
        logger.info(f"Output: {args.output}")
        
        num_points = custom_fusion(args.workspace, args.output)
        
        logger.info(f"Custom fusion completed successfully with {num_points} points")
        
    except Exception as e:
        logger.error(f"Custom fusion failed: {e}")
        raise

if __name__ == "__main__":
    main()