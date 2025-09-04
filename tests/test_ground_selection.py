#!/usr/bin/env python3
"""
Test different ground selection strategies to compare results.
"""

import numpy as np
import trimesh
from PIL import Image

def test_ground_strategies():
    """Test different strategies for ground point selection."""
    
    # Load COLMAP data
    mesh = trimesh.load('meshes/yard-colmap-fused.ply')
    vertices = mesh.vertices[:100000]  # Sample for testing
    colors = mesh.visual.vertex_colors[:100000, :3] if hasattr(mesh.visual, 'vertex_colors') else None
    
    # Project to 2D 
    vertices_2d = vertices[:, [0, 1]]
    heights = vertices[:, 2]
    
    print(f"Overall height statistics:")
    print(f"  Min: {heights.min():.2f}m")
    print(f"  Max: {heights.max():.2f}m") 
    print(f"  25th percentile: {np.percentile(heights, 25):.2f}m")
    print(f"  50th percentile: {np.percentile(heights, 50):.2f}m")
    print(f"  75th percentile: {np.percentile(heights, 75):.2f}m")
    
    # Find bounds
    x_min, x_max = vertices_2d[:, 0].min(), vertices_2d[:, 0].max()
    y_min, y_max = vertices_2d[:, 1].min(), vertices_2d[:, 1].max()
    
    # Test a grid of pixels
    pixel_size = 0.1
    test_results = []
    
    print(f"\nTesting ground selection strategies on sample pixels...")
    
    for i in range(10):  # Test 10 pixels
        test_x = x_min + (x_max - x_min) * (i / 9)
        test_y = (y_min + y_max) / 2
        
        # Find points in pixel
        in_pixel = ((vertices_2d[:, 0] >= test_x - pixel_size/2) & 
                   (vertices_2d[:, 0] <= test_x + pixel_size/2) &
                   (vertices_2d[:, 1] >= test_y - pixel_size/2) & 
                   (vertices_2d[:, 1] <= test_y + pixel_size/2))
        
        pixel_indices = np.where(in_pixel)[0]
        
        if len(pixel_indices) < 5:  # Skip sparse pixels
            continue
            
        pixel_heights = heights[pixel_indices]
        pixel_colors = colors[pixel_indices] if colors is not None else None
        
        height_range = pixel_heights.max() - pixel_heights.min()
        
        if height_range < 0.5:  # Skip pixels with little variation
            continue
            
        print(f"\nPixel {len(test_results)+1}: ({test_x:.1f}, {test_y:.1f})")
        print(f"  Points: {len(pixel_indices)}, Height range: {height_range:.2f}m")
        
        # Strategy 1: Current (min_height + window)
        height_window = 1.0
        min_height = pixel_heights.min()
        threshold = min_height + height_window
        ground_mask = pixel_heights <= threshold
        ground_count_1 = np.sum(ground_mask)
        if pixel_colors is not None and ground_count_1 > 0:
            avg_color_1 = np.mean(pixel_colors[ground_mask], axis=0)
            print(f"  Strategy 1 (min+window): {ground_count_1}/{len(pixel_indices)} points, color RGB({avg_color_1[0]:.0f},{avg_color_1[1]:.0f},{avg_color_1[2]:.0f})")
        
        # Strategy 2: Lowest percentile  
        percentile_30 = np.percentile(pixel_heights, 30)
        ground_mask_2 = pixel_heights <= percentile_30
        ground_count_2 = np.sum(ground_mask_2)
        if pixel_colors is not None and ground_count_2 > 0:
            avg_color_2 = np.mean(pixel_colors[ground_mask_2], axis=0)
            print(f"  Strategy 2 (lowest 30%): {ground_count_2}/{len(pixel_indices)} points, color RGB({avg_color_2[0]:.0f},{avg_color_2[1]:.0f},{avg_color_2[2]:.0f})")
            
        # Strategy 3: Global ground threshold (based on overall data)
        global_ground_threshold = np.percentile(heights, 25)  # Bottom 25% of all points
        ground_mask_3 = pixel_heights <= global_ground_threshold
        ground_count_3 = np.sum(ground_mask_3)
        if pixel_colors is not None and ground_count_3 > 0:
            avg_color_3 = np.mean(pixel_colors[ground_mask_3], axis=0)
            print(f"  Strategy 3 (global threshold): {ground_count_3}/{len(pixel_indices)} points, color RGB({avg_color_3[0]:.0f},{avg_color_3[1]:.0f},{avg_color_3[2]:.0f})")
        
        test_results.append({
            'location': (test_x, test_y),
            'height_range': height_range,
            'strategy_1_count': ground_count_1,
            'strategy_2_count': ground_count_2, 
            'strategy_3_count': ground_count_3
        })
        
        if len(test_results) >= 5:  # Test 5 good pixels
            break
    
    print(f"\n=== Summary ===")
    print(f"Tested {len(test_results)} pixels with good height variation")
    
    if len(test_results) > 0:
        avg_s1 = np.mean([r['strategy_1_count'] for r in test_results])
        avg_s2 = np.mean([r['strategy_2_count'] for r in test_results]) 
        avg_s3 = np.mean([r['strategy_3_count'] for r in test_results])
        
        print(f"Average ground points selected:")
        print(f"  Strategy 1 (current): {avg_s1:.1f} points")
        print(f"  Strategy 2 (percentile): {avg_s2:.1f} points")
        print(f"  Strategy 3 (global threshold): {avg_s3:.1f} points")

if __name__ == '__main__':
    test_ground_strategies()