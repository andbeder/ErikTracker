#!/usr/bin/env python3
"""
Test script for color detection functionality
"""

import cv2
import numpy as np
from pathlib import Path
import sys
import os

# Import the tracker to test color functions
sys.path.append('/home/andrew/nvr')
from hybrid_erik_tracker import HybridErikTracker

def create_test_config():
    """Create a minimal config for testing"""
    return {
        'enable_color_tracking': True,
        'color_weight': 0.2,
        'color_confidence_threshold': 0.6,
        'color_tolerance': 15,
        'osnet_threshold': 0.484,
        'osnet_weight': 0.5,
        'face_weight': 0.3,
        'enable_face_recognition': False,  # Disable for this test
        'erik_images_folder': '/home/andrew/nvr/erik_images'
    }

def create_test_image_with_color(color_bgr, width=256, height=384):
    """Create a test person-shaped image with a specific color"""
    image = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Create a person-like shape (rectangle for torso)
    torso_top = height // 4
    torso_bottom = int(height * 0.75)
    torso_left = int(width * 0.2)
    torso_right = int(width * 0.8)
    
    # Fill torso area with the test color
    image[torso_top:torso_bottom, torso_left:torso_right] = color_bgr
    
    # Add some background noise
    image[:torso_top, :] = [50, 50, 50]  # Dark background
    image[torso_bottom:, :] = [40, 40, 40]  # Dark background
    
    return image

def test_color_detection():
    """Test the color detection functionality"""
    print("Testing Enhanced Color Detection System")
    print("=" * 50)
    
    # Create tracker instance
    config = create_test_config()
    tracker = HybridErikTracker(config)
    
    # Test colors (BGR format)
    test_colors = {
        'red_shirt': [30, 30, 200],      # Red shirt
        'blue_shirt': [200, 30, 30],     # Blue shirt  
        'green_shirt': [30, 200, 30],    # Green shirt
        'black_shirt': [20, 20, 20],     # Black shirt
        'white_shirt': [240, 240, 240],  # White shirt
    }
    
    # Test 1: Learn Erik's color profile from red shirt
    print("\n1. Learning Erik's color profile from red shirt...")
    red_image = create_test_image_with_color(test_colors['red_shirt'])
    
    # Simulate high confidence face recognition to trigger color learning
    tracker._update_erik_color_profile(red_image, 0.95)
    
    if tracker.erik_shirt_color is not None:
        print(f"✓ Learned Erik's shirt color: hue={tracker.erik_shirt_color:.1f}")
        print(f"  Color range: {tracker.erik_color_range}")
    else:
        print("✗ Failed to learn color profile")
        return
    
    # Test 2: Test color similarity with same color
    print("\n2. Testing similarity with same red shirt...")
    red_similarity = tracker._compute_color_similarity(red_image)
    print(f"  Red shirt similarity: {red_similarity:.3f}")
    
    # Test 3: Test with different colors
    print("\n3. Testing with different colored shirts...")
    for color_name, color_bgr in test_colors.items():
        if color_name == 'red_shirt':
            continue  # Already tested
            
        test_image = create_test_image_with_color(color_bgr)
        similarity = tracker._compute_color_similarity(test_image)
        detected = similarity >= tracker.color_confidence_threshold
        
        print(f"  {color_name}: {similarity:.3f} {'✓' if detected else '✗'}")
    
    # Test 4: Test hue extraction
    print("\n4. Testing hue extraction...")
    for color_name, color_bgr in test_colors.items():
        test_image = create_test_image_with_color(color_bgr)
        torso_region = tracker._extract_torso_region(test_image)
        hue = tracker._get_dominant_hue(torso_region)
        
        if hue is not None:
            print(f"  {color_name}: hue={hue:.1f}°")
        else:
            print(f"  {color_name}: no dominant hue detected")
    
    # Test 5: Test scoring fusion
    print("\n5. Testing confidence score fusion...")
    
    # Simulate detection scores
    test_scenarios = [
        ("All methods agree", 0.8, 0.9, 0.7, True, True, True),
        ("Face + Color only", 0.3, 0.9, 0.8, False, True, True),
        ("OSNet + Color only", 0.8, 0.4, 0.7, True, False, True),
        ("Color only", 0.3, 0.4, 0.9, False, False, True),
        ("No detection", 0.2, 0.3, 0.3, False, False, False),
    ]
    
    for scenario_name, osnet_score, face_score, color_score, osnet_det, face_det, color_det in test_scenarios:
        is_erik, combined, details = tracker._fuse_confidence_scores(
            osnet_score, face_score, color_score, osnet_det, face_det, color_det
        )
        
        print(f"  {scenario_name}:")
        print(f"    Combined: {combined:.3f}, Detected: {'✓' if is_erik else '✗'}")
        print(f"    Method: {details['method']}")
    
    print("\n" + "=" * 50)
    print("Color detection test completed!")

if __name__ == "__main__":
    test_color_detection()