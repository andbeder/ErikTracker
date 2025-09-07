#!/usr/bin/env python3
"""
Camera Optics Analyzer
Analyzes camera images to determine optical characteristics including:
- Field of view (FOV)
- Lens distortion (barrel/pincushion)
- Focal length estimation
- Lens type detection
"""

import cv2
import numpy as np
import json
import sys
import os
from pathlib import Path
import matplotlib.pyplot as plt
from scipy import optimize
import requests
from datetime import datetime

def detect_lens_distortion(image_path):
    """Detect barrel or pincushion distortion in image"""
    img = cv2.imread(image_path)
    if img is None:
        return None, "Could not load image"
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    
    # Detect edges for line analysis
    edges = cv2.Canny(gray, 50, 150)
    
    # Detect lines using Hough transform
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, 
                            minLineLength=min(w,h)//4, maxLineGap=10)
    
    if lines is None:
        return {"distortion_type": "unknown", "severity": 0}, "No lines detected"
    
    # Analyze line curvature
    curvatures = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        # Calculate distance from image center
        cx, cy = w/2, h/2
        dist_from_center = np.sqrt(((x1+x2)/2 - cx)**2 + ((y1+y2)/2 - cy)**2)
        
        # Sample points along the line
        num_samples = 10
        x_samples = np.linspace(x1, x2, num_samples)
        y_samples = np.linspace(y1, y2, num_samples)
        
        # Check for curvature by fitting polynomial
        if abs(x2 - x1) > abs(y2 - y1):  # More horizontal
            coeffs = np.polyfit(x_samples, y_samples, 2)
            curvature = abs(coeffs[0])
        else:  # More vertical
            coeffs = np.polyfit(y_samples, x_samples, 2)
            curvature = abs(coeffs[0])
        
        if dist_from_center > min(w, h) * 0.3:  # Only consider lines away from center
            curvatures.append(curvature)
    
    if curvatures:
        avg_curvature = np.mean(curvatures)
        if avg_curvature > 0.001:
            return {
                "distortion_type": "barrel",
                "severity": min(avg_curvature * 1000, 10),
                "curvature": avg_curvature
            }, "Barrel distortion detected"
        elif avg_curvature < -0.001:
            return {
                "distortion_type": "pincushion", 
                "severity": min(abs(avg_curvature) * 1000, 10),
                "curvature": avg_curvature
            }, "Pincushion distortion detected"
    
    return {"distortion_type": "minimal", "severity": 0}, "Minimal distortion"

def estimate_fov(image_path, known_object_size=None):
    """Estimate field of view from image"""
    img = cv2.imread(image_path)
    if img is None:
        return None, "Could not load image"
    
    h, w, _ = img.shape
    
    # Common sensor sizes and crop factors
    # Assuming typical security camera sensor (1/2.8" or 1/3")
    sensor_diagonal_mm = 6.5  # 1/2.8" sensor
    
    # Estimate based on image aspect ratio and typical focal lengths
    aspect_ratio = w / h
    
    # Common focal lengths for security cameras (mm)
    common_focal_lengths = [2.8, 3.6, 4.0, 6.0, 8.0, 12.0]
    
    # Calculate horizontal FOV for each focal length
    fov_estimates = {}
    for focal_length in common_focal_lengths:
        # Horizontal sensor size (assuming 16:9 or 4:3)
        if abs(aspect_ratio - 16/9) < 0.1:
            sensor_width = sensor_diagonal_mm * 0.87  # 16:9
        else:
            sensor_width = sensor_diagonal_mm * 0.8   # 4:3
        
        # FOV = 2 * arctan(sensor_size / (2 * focal_length))
        hfov = 2 * np.degrees(np.arctan(sensor_width / (2 * focal_length)))
        vfov = 2 * np.degrees(np.arctan(sensor_width / aspect_ratio / (2 * focal_length)))
        
        fov_estimates[f"{focal_length}mm"] = {
            "horizontal_fov": round(hfov, 1),
            "vertical_fov": round(vfov, 1),
            "diagonal_fov": round(np.sqrt(hfov**2 + vfov**2), 1)
        }
    
    # Try to detect vanishing points for better estimation
    vanishing_points = detect_vanishing_points(img)
    
    # Analyze edge density at corners vs center (wide angle lenses show more distortion)
    edge_ratio = analyze_edge_distribution(img)
    
    # Estimate most likely focal length based on edge distribution
    if edge_ratio > 1.5:  # More edges at periphery
        likely_focal = 2.8  # Wide angle
        lens_type = "wide-angle"
    elif edge_ratio > 1.2:
        likely_focal = 3.6
        lens_type = "wide"
    elif edge_ratio > 0.9:
        likely_focal = 4.0
        lens_type = "normal"
    else:
        likely_focal = 6.0
        lens_type = "mild-telephoto"
    
    result = {
        "most_likely": fov_estimates[f"{likely_focal}mm"],
        "likely_focal_length_mm": likely_focal,
        "lens_type": lens_type,
        "all_estimates": fov_estimates,
        "edge_ratio": round(edge_ratio, 2),
        "image_dimensions": {"width": w, "height": h},
        "aspect_ratio": round(aspect_ratio, 2)
    }
    
    return result, f"Likely {lens_type} lens (~{likely_focal}mm)"

def detect_vanishing_points(img):
    """Detect vanishing points in the image"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50,
                            minLineLength=100, maxLineGap=10)
    
    if lines is None or len(lines) < 10:
        return []
    
    # Group lines by angle
    horizontal = []
    vertical = []
    diagonal = []
    
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2-y1, x2-x1))
        
        if abs(angle) < 20 or abs(angle) > 160:
            horizontal.append(line[0])
        elif 70 < abs(angle) < 110:
            vertical.append(line[0])
        else:
            diagonal.append(line[0])
    
    return {
        "horizontal_lines": len(horizontal),
        "vertical_lines": len(vertical),
        "diagonal_lines": len(diagonal)
    }

def analyze_edge_distribution(img):
    """Analyze edge distribution to detect wide-angle characteristics"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    
    # Divide image into center and periphery
    center_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(center_mask, 
                  (w//4, h//4), 
                  (3*w//4, 3*h//4), 
                  255, -1)
    
    periphery_mask = 255 - center_mask
    
    # Detect edges
    edges = cv2.Canny(gray, 50, 150)
    
    # Count edges in each region
    center_edges = cv2.countNonZero(cv2.bitwise_and(edges, edges, mask=center_mask))
    periphery_edges = cv2.countNonZero(cv2.bitwise_and(edges, edges, mask=periphery_mask))
    
    # Normalize by area
    center_area = cv2.countNonZero(center_mask)
    periphery_area = cv2.countNonZero(periphery_mask)
    
    center_density = center_edges / center_area if center_area > 0 else 0
    periphery_density = periphery_edges / periphery_area if periphery_area > 0 else 0
    
    # Ratio > 1 means more edges at periphery (wide angle characteristic)
    ratio = periphery_density / center_density if center_density > 0 else 1
    
    return ratio

def analyze_chromatic_aberration(image_path):
    """Detect chromatic aberration (color fringing)"""
    img = cv2.imread(image_path)
    if img is None:
        return None, "Could not load image"
    
    # Convert to float
    img_float = img.astype(np.float32) / 255.0
    b, g, r = cv2.split(img_float)
    
    # Find high contrast edges
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    
    # Dilate edges to get regions around edges
    kernel = np.ones((5,5), np.uint8)
    edge_regions = cv2.dilate(edges, kernel, iterations=1)
    
    # Calculate color channel misalignment at edges
    edge_pixels = edge_regions > 0
    
    if np.sum(edge_pixels) > 0:
        # Calculate standard deviation of color channels at edges
        r_std = np.std(r[edge_pixels])
        g_std = np.std(g[edge_pixels])
        b_std = np.std(b[edge_pixels])
        
        # Color fringing score
        fringing_score = np.std([r_std, g_std, b_std]) * 100
        
        if fringing_score > 5:
            severity = "high"
        elif fringing_score > 2:
            severity = "moderate"
        elif fringing_score > 0.5:
            severity = "low"
        else:
            severity = "minimal"
        
        return {
            "chromatic_aberration": severity,
            "fringing_score": round(fringing_score, 2),
            "channel_stds": {
                "red": round(r_std, 4),
                "green": round(g_std, 4),
                "blue": round(b_std, 4)
            }
        }, f"Chromatic aberration: {severity}"
    
    return {"chromatic_aberration": "unknown"}, "Could not analyze chromatic aberration"

def get_camera_snapshot(camera_name):
    """Get snapshot from live camera"""
    try:
        # Try to get snapshot from the running server
        response = requests.get(f'http://localhost:9001/api/cameras/{camera_name}/snapshot', timeout=5)
        if response.status_code == 200:
            # Save snapshot temporarily
            snapshot_path = f'/tmp/{camera_name}_snapshot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg'
            with open(snapshot_path, 'wb') as f:
                f.write(response.content)
            return snapshot_path
    except:
        pass
    
    # Check for existing snapshots
    snapshot_dirs = [
        '/home/andrew/nvr/erik_images',
        '/tmp'
    ]
    
    for dir_path in snapshot_dirs:
        if os.path.exists(dir_path):
            # Look for recent camera images
            for file in Path(dir_path).glob(f'*{camera_name}*.jpg'):
                return str(file)
    
    return None

def main():
    print("=" * 60)
    print("CAMERA OPTICS ANALYZER")
    print("=" * 60)
    
    # Get camera name from arguments or use default
    camera_name = sys.argv[1] if len(sys.argv) > 1 else "backyard"
    
    # Get image path
    if len(sys.argv) > 2:
        image_path = sys.argv[2]
    else:
        print(f"\nLooking for {camera_name} camera snapshot...")
        image_path = get_camera_snapshot(camera_name)
    
    if not image_path or not os.path.exists(image_path):
        print(f"Error: Could not find image for camera '{camera_name}'")
        print("\nUsage: python analyze_camera_optics.py [camera_name] [image_path]")
        return
    
    print(f"Analyzing image: {image_path}")
    print("-" * 60)
    
    # Load and display basic info
    img = cv2.imread(image_path)
    if img is None:
        print("Error: Could not load image")
        return
    
    h, w, _ = img.shape
    print(f"\n📷 IMAGE PROPERTIES:")
    print(f"  Resolution: {w} x {h} pixels")
    print(f"  Aspect Ratio: {w/h:.2f}:1 (~{w//np.gcd(w,h)}:{h//np.gcd(w,h)})")
    
    # Analyze FOV
    print(f"\n🎯 FIELD OF VIEW ANALYSIS:")
    fov_result, fov_msg = estimate_fov(image_path)
    if fov_result:
        print(f"  {fov_msg}")
        print(f"  Most Likely FOV:")
        print(f"    - Horizontal: {fov_result['most_likely']['horizontal_fov']}°")
        print(f"    - Vertical: {fov_result['most_likely']['vertical_fov']}°")
        print(f"    - Diagonal: {fov_result['most_likely']['diagonal_fov']}°")
        print(f"  Estimated Focal Length: {fov_result['likely_focal_length_mm']}mm")
        print(f"  Edge Distribution Ratio: {fov_result['edge_ratio']}")
    
    # Analyze distortion
    print(f"\n📐 LENS DISTORTION ANALYSIS:")
    distortion_result, distortion_msg = detect_lens_distortion(image_path)
    if distortion_result:
        print(f"  {distortion_msg}")
        print(f"  Type: {distortion_result['distortion_type']}")
        print(f"  Severity: {distortion_result['severity']:.1f}/10")
    
    # Analyze chromatic aberration
    print(f"\n🌈 CHROMATIC ABERRATION:")
    chroma_result, chroma_msg = analyze_chromatic_aberration(image_path)
    if chroma_result:
        print(f"  {chroma_msg}")
        if 'fringing_score' in chroma_result:
            print(f"  Fringing Score: {chroma_result['fringing_score']}")
    
    # Summary and recommendations
    print(f"\n📊 SUMMARY:")
    print(f"  Camera Type: Security/Surveillance Camera")
    if fov_result:
        lens_type = fov_result['lens_type']
        focal = fov_result['likely_focal_length_mm']
        print(f"  Lens Type: {lens_type.title()} (~{focal}mm)")
        
        if focal <= 3.6:
            print(f"  Suitable for: Wide area coverage, room monitoring")
        elif focal <= 6:
            print(f"  Suitable for: General surveillance, entrances")
        else:
            print(f"  Suitable for: Focused monitoring, long-range detail")
    
    print("\n" + "=" * 60)
    
    # Save analysis results
    results = {
        "camera_name": camera_name,
        "image_path": image_path,
        "timestamp": datetime.now().isoformat(),
        "image_properties": {
            "width": w,
            "height": h,
            "aspect_ratio": round(w/h, 2)
        },
        "fov_analysis": fov_result,
        "distortion_analysis": distortion_result,
        "chromatic_aberration": chroma_result
    }
    
    output_path = f'/tmp/{camera_name}_optics_analysis.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nAnalysis saved to: {output_path}")

if __name__ == "__main__":
    main()