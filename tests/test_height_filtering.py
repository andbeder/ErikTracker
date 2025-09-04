#!/usr/bin/env python3
"""
Test height filtering approaches to determine which gives ground vs foliage.
"""

import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

def analyze_pixel_heights():
    """Analyze a sample pixel to understand height distribution."""
    
    # Load sample data
    mesh = trimesh.load('meshes/yard-colmap-fused.ply')
    vertices = mesh.vertices[:50000]  # Sample for testing
    colors = mesh.visual.vertex_colors[:50000, :3] if hasattr(mesh.visual, 'vertex_colors') else None
    
    # Project to 2D (top-down view)
    vertices_2d = vertices[:, [0, 1]]
    heights = vertices[:, 2]
    
    # Find data bounds
    x_min, x_max = vertices_2d[:, 0].min(), vertices_2d[:, 0].max()
    y_min, y_max = vertices_2d[:, 1].min(), vertices_2d[:, 1].max()
    
    # Find a pixel with large height variation (ground to trees)
    pixel_size = 0.2  # Larger pixels to capture more variation
    
    best_pixel = None
    best_variation = 0
    
    # Test several pixel locations to find one with good height variation
    for i in range(20):
        test_x = x_min + (x_max - x_min) * (i / 19)  
        test_y = y_min + (y_max - y_min) * 0.5  # Middle Y
        
        in_pixel = ((vertices_2d[:, 0] >= test_x - pixel_size/2) & 
                   (vertices_2d[:, 0] <= test_x + pixel_size/2) &
                   (vertices_2d[:, 1] >= test_y - pixel_size/2) & 
                   (vertices_2d[:, 1] <= test_y + pixel_size/2))
        
        pixel_indices = np.where(in_pixel)[0]
        
        if len(pixel_indices) > 10:  # Need enough points
            pixel_heights = heights[pixel_indices]
            height_variation = pixel_heights.max() - pixel_heights.min()
            
            if height_variation > best_variation:
                best_variation = height_variation
                best_pixel = (test_x, test_y, pixel_indices)
    
    if best_pixel is None:
        print("No suitable test pixel found")
        return
    
    test_x, test_y, pixel_indices = best_pixel
    pixel_heights = heights[pixel_indices]
    pixel_colors = colors[pixel_indices] if colors is not None else None
    
    print(f"\n=== Test Pixel Analysis ===")
    print(f"Pixel location: ({test_x:.2f}, {test_y:.2f})")
    print(f"Points in pixel: {len(pixel_indices)}")
    print(f"Height range: {pixel_heights.min():.2f}m to {pixel_heights.max():.2f}m")
    print(f"Height variation: {best_variation:.2f}m")
    
    # Test both approaches
    height_window = 1.0
    
    # Approach 1: min_height + window (current)
    min_height = pixel_heights.min()
    threshold_1 = min_height + height_window
    ground_mask_1 = pixel_heights <= threshold_1
    ground_indices_1 = pixel_indices[ground_mask_1]
    
    print(f"\n--- Approach 1: min_height + window ---")
    print(f"Min height: {min_height:.2f}m")
    print(f"Threshold: {threshold_1:.2f}m") 
    print(f"Ground points: {len(ground_indices_1)}/{len(pixel_indices)} ({len(ground_indices_1)/len(pixel_indices)*100:.1f}%)")
    if pixel_colors is not None:
        avg_color_1 = np.mean(colors[ground_indices_1], axis=0)
        print(f"Average color: RGB({avg_color_1[0]:.0f}, {avg_color_1[1]:.0f}, {avg_color_1[2]:.0f})")
    
    # Approach 2: max_height - window (alternative)
    max_height = pixel_heights.max()
    threshold_2 = max_height - height_window
    ground_mask_2 = pixel_heights >= threshold_2
    ground_indices_2 = pixel_indices[ground_mask_2]
    
    print(f"\n--- Approach 2: max_height - window ---")
    print(f"Max height: {max_height:.2f}m")
    print(f"Threshold: {threshold_2:.2f}m")
    print(f"Ground points: {len(ground_indices_2)}/{len(pixel_indices)} ({len(ground_indices_2)/len(pixel_indices)*100:.1f}%)")
    if pixel_colors is not None:
        avg_color_2 = np.mean(colors[ground_indices_2], axis=0)
        print(f"Average color: RGB({avg_color_2[0]:.0f}, {avg_color_2[1]:.0f}, {avg_color_2[2]:.0f})")
    
    # Approach 3: Lowest 30% by height (for comparison)
    sorted_indices = np.argsort(pixel_heights)
    lowest_30_percent = int(len(sorted_indices) * 0.3)
    ground_indices_3 = pixel_indices[sorted_indices[:lowest_30_percent]]
    
    print(f"\n--- Approach 3: Lowest 30% by height ---")
    print(f"Ground points: {len(ground_indices_3)}/{len(pixel_indices)} ({len(ground_indices_3)/len(pixel_indices)*100:.1f}%)")
    if pixel_colors is not None:
        avg_color_3 = np.mean(colors[ground_indices_3], axis=0)
        print(f"Average color: RGB({avg_color_3[0]:.0f}, {avg_color_3[1]:.0f}, {avg_color_3[2]:.0f})")
    
    # Show which heights are selected by each approach
    if len(pixel_indices) > 5:
        print(f"\n--- Height distribution ---")
        print(f"All heights: {sorted(pixel_heights)[:10]}")  # Show first 10 heights
        print(f"Approach 1 selects: {sorted(pixel_heights[ground_mask_1])[:5]}")
        print(f"Approach 2 selects: {sorted(pixel_heights[ground_mask_2])[:5]}")

if __name__ == '__main__':
    analyze_pixel_heights()