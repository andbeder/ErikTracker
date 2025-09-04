#!/usr/bin/env python3
"""
Simple Compatibility Test - Image Analysis
Tests visual similarity between Erik and Matthew images without OSNet
"""

import os
import sys
from pathlib import Path
from PIL import Image, ImageStat
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import cv2

class SimpleCompatibilityTester:
    def __init__(self):
        """Initialize simple feature extractor using basic image features"""
        pass
        
    def extract_basic_features(self, image_path):
        """Extract basic visual features from image"""
        try:
            # Load image
            img = cv2.imread(str(image_path))
            if img is None:
                return None
                
            # Resize to standard size
            img_resized = cv2.resize(img, (224, 224))
            
            # Extract basic features
            features = []
            
            # Color histogram features
            for i in range(3):  # BGR channels
                hist = cv2.calcHist([img_resized], [i], None, [32], [0, 256])
                features.extend(hist.flatten())
            
            # Texture features (LBP-like)
            gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
            
            # Simple edge features
            edges = cv2.Canny(gray, 100, 200)
            edge_density = np.mean(edges) / 255.0
            features.append(edge_density)
            
            # Brightness and contrast
            brightness = np.mean(gray)
            contrast = np.std(gray)
            features.extend([brightness, contrast])
            
            return np.array(features)
            
        except Exception as e:
            print(f"Error processing {image_path}: {e}")
            return None
    
    def extract_features_folder(self, folder_path):
        """Extract features from all images in folder"""
        features = []
        filenames = []
        
        folder = Path(folder_path)
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        
        for ext in image_extensions:
            for image_path in folder.glob(f'*{ext}'):
                feature_vector = self.extract_basic_features(image_path)
                if feature_vector is not None:
                    features.append(feature_vector)
                    filenames.append(image_path.name)
                    print(f"✓ Processed {image_path.name}")
        
        return np.array(features), filenames
    
    def run_compatibility_test(self, erik_folder, matthew_folder):
        """Run compatibility test using basic image features"""
        
        print("🧪 Simple Erik vs Matthew Compatibility Test")
        print("=" * 50)
        print("Note: Using basic image features (not OSNet)")
        print("=" * 50)
        
        # Extract features
        print(f"\n📸 Processing Erik images from {erik_folder}...")
        erik_features, erik_files = self.extract_features_folder(erik_folder)
        
        print(f"\n📸 Processing Matthew images from {matthew_folder}...")
        matthew_features, matthew_files = self.extract_features_folder(matthew_folder)
        
        print(f"\n📊 Dataset Summary:")
        print(f"   Erik images: {len(erik_features)}")
        print(f"   Matthew images: {len(matthew_features)}")
        
        if len(erik_features) == 0 or len(matthew_features) == 0:
            print("❌ Error: No valid images found")
            return
        
        # Calculate similarities
        print(f"\n🔍 Analyzing image similarities...")
        
        # Normalize features
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        
        all_features = np.vstack([erik_features, matthew_features])
        all_features_scaled = scaler.fit_transform(all_features)
        
        erik_scaled = all_features_scaled[:len(erik_features)]
        matthew_scaled = all_features_scaled[len(erik_features):]
        
        # Calculate similarity matrices
        erik_internal = cosine_similarity(erik_scaled, erik_scaled)
        matthew_internal = cosine_similarity(matthew_scaled, matthew_scaled)
        erik_vs_matthew = cosine_similarity(erik_scaled, matthew_scaled)
        
        # Statistics
        erik_internal_upper = erik_internal[np.triu_indices_from(erik_internal, k=1)]
        matthew_internal_upper = matthew_internal[np.triu_indices_from(matthew_internal, k=1)]
        
        erik_internal_mean = np.mean(erik_internal_upper)
        matthew_internal_mean = np.mean(matthew_internal_upper)
        cross_similarity_mean = np.mean(erik_vs_matthew)
        cross_similarity_max = np.max(erik_vs_matthew)
        
        print(f"\n📈 Basic Similarity Analysis:")
        print(f"=" * 35)
        print(f"Erik internal similarity:    {erik_internal_mean:.3f}")
        print(f"Matthew internal similarity: {matthew_internal_mean:.3f}")
        print(f"Cross-person similarity:     {cross_similarity_mean:.3f}")
        print(f"Max cross-person similarity: {cross_similarity_max:.3f}")
        
        # Visual difference analysis
        erik_avg_brightness = np.mean([np.mean(f[-2]) for f in erik_features])
        matthew_avg_brightness = np.mean([np.mean(f[-2]) for f in matthew_features])
        brightness_diff = abs(erik_avg_brightness - matthew_avg_brightness)
        
        print(f"\n🎨 Visual Characteristics:")
        print(f"=" * 30)
        print(f"Erik avg brightness:   {erik_avg_brightness:.1f}")
        print(f"Matthew avg brightness: {matthew_avg_brightness:.1f}")
        print(f"Brightness difference: {brightness_diff:.1f}")
        
        # Simple assessment
        separation_quality = min(erik_internal_mean, matthew_internal_mean) - cross_similarity_max
        
        print(f"\n🎯 Basic Compatibility Assessment:")
        print(f"=" * 40)
        print(f"Separation quality: {separation_quality:.3f}")
        
        if separation_quality > 0.15:
            recommendation = "✅ GOOD separation - OSNet likely to work well"
            risk = "Low"
        elif separation_quality > 0.05:
            recommendation = "⚠️  MODERATE separation - test with OSNet"
            risk = "Medium"
        else:
            recommendation = "❌ POOR separation - high confusion risk"
            risk = "High"
        
        print(f"Risk level: {risk}")
        print(f"Recommendation: {recommendation}")
        
        # Age/similarity hints
        if cross_similarity_mean > 0.8:
            print("\n💡 Hints:")
            print("   • Very high cross-similarity suggests similar appearance")
            print("   • Consider age difference and distinctive features")
            print("   • OSNet may still distinguish better than basic features")
        elif cross_similarity_mean < 0.6:
            print("\n💡 Hints:")
            print("   • Good visual separation detected")
            print("   • Different clothing, lighting, or poses")
            print("   • OSNet should handle this well")
            
        print(f"\n⚠️  Important Notes:")
        print(f"   • This is a simplified test using basic image features")
        print(f"   • OSNet uses much more sophisticated person re-identification")
        print(f"   • Final decision should be based on full OSNet testing")
        
        if separation_quality > 0.05:
            print(f"\n✅ Next Step: Set up OSNet for definitive testing")
        else:
            print(f"\n❌ Recommendation: Stick with Erik-only tracking for now")
            
        return {
            'erik_internal_mean': erik_internal_mean,
            'matthew_internal_mean': matthew_internal_mean,
            'cross_similarity_mean': cross_similarity_mean,
            'separation_quality': separation_quality,
            'recommendation': recommendation
        }

if __name__ == "__main__":
    erik_folder = "/home/andrew/nvr/erik_images"
    matthew_folder = "/home/andrew/nvr/matthew_images"
    
    if not os.path.exists(erik_folder):
        print(f"❌ Erik folder not found: {erik_folder}")
        sys.exit(1)
        
    if not os.path.exists(matthew_folder):
        print(f"❌ Matthew folder not found: {matthew_folder}")
        sys.exit(1)
    
    tester = SimpleCompatibilityTester()
    results = tester.run_compatibility_test(erik_folder, matthew_folder)