#!/usr/bin/env python3
"""
Test OSNet with Erik's images - Step 1
This script helps you test OSNet functionality with actual images of Erik
"""

import torch
import torchreid
import cv2
import numpy as np
import os
from typing import List, Tuple, Dict
import matplotlib.pyplot as plt
from pathlib import Path

class ErikOSNetTester:
    def __init__(self):
        print("Loading OSNet model...")
        self.model = torchreid.models.build_model(
            name='osnet_x1_0',
            num_classes=1000,
            pretrained=True
        )
        self.model.eval()
        print("✓ OSNet model loaded successfully")
        
    def preprocess_image(self, image_path: str) -> Tuple[torch.Tensor, np.ndarray]:
        """Load and preprocess image for OSNet"""
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        original = image.copy()
        
        # Resize to OSNet input size (128x256)
        image = cv2.resize(image, (128, 256))
        
        # Convert BGR to RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Normalize using ImageNet stats
        image = image.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        image = (image - mean) / std
        
        # Convert to tensor and add batch dimension
        tensor = torch.tensor(image, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)
        
        return tensor, original
    
    def extract_features(self, image_path: str) -> torch.Tensor:
        """Extract OSNet features from image"""
        tensor, _ = self.preprocess_image(image_path)
        
        with torch.no_grad():
            features = self.model(tensor)
        
        # L2 normalize features
        features = torch.nn.functional.normalize(features, p=2, dim=1)
        return features
    
    def compute_similarity(self, features1: torch.Tensor, features2: torch.Tensor) -> float:
        """Compute cosine similarity between two feature vectors"""
        similarity = torch.cosine_similarity(features1, features2, dim=1).item()
        return similarity
    
    def test_single_image(self, image_path: str):
        """Test feature extraction on a single image"""
        print(f"\n📸 Testing image: {image_path}")
        
        if not os.path.exists(image_path):
            print(f"❌ Image not found: {image_path}")
            return None
        
        try:
            features = self.extract_features(image_path)
            print(f"✓ Features extracted successfully")
            print(f"  Feature shape: {features.shape}")
            print(f"  Feature norm: {torch.norm(features).item():.3f}")
            return features
        except Exception as e:
            print(f"❌ Error processing image: {e}")
            return None
    
    def test_image_similarity(self, image_paths: List[str]):
        """Test similarity between multiple images"""
        print(f"\n🔍 Testing similarity between {len(image_paths)} images...")
        
        # Extract features for all images
        features_dict = {}
        for i, path in enumerate(image_paths):
            features = self.test_single_image(path)
            if features is not None:
                features_dict[f"Image_{i+1}_{Path(path).name}"] = features
        
        if len(features_dict) < 2:
            print("❌ Need at least 2 valid images for similarity testing")
            return None, None
        
        # Compare all pairs
        print(f"\n📊 Similarity Matrix:")
        print(f"{'':20} ", end="")
        for name in features_dict.keys():
            print(f"{name[:15]:>15}", end="")
        print()
        
        similarities = []
        for name1, feat1 in features_dict.items():
            print(f"{name1[:20]:20} ", end="")
            row_similarities = []
            for name2, feat2 in features_dict.items():
                sim = self.compute_similarity(feat1, feat2)
                row_similarities.append(sim)
                similarities.append(sim)
                print(f"{sim:15.3f}", end="")
            print()
        
        # Statistics
        similarities = np.array(similarities)
        non_self_similarities = similarities[similarities < 0.99]  # Exclude self-similarity
        
        print(f"\n📈 Statistics:")
        print(f"  Average similarity: {np.mean(non_self_similarities):.3f}")
        print(f"  Min similarity: {np.min(non_self_similarities):.3f}")
        print(f"  Max similarity: {np.max(non_self_similarities):.3f}")
        print(f"  Std deviation: {np.std(non_self_similarities):.3f}")
        
        return features_dict, non_self_similarities
    
    def recommend_threshold(self, similarities: np.ndarray):
        """Recommend similarity threshold based on test results"""
        mean_sim = np.mean(similarities)
        std_sim = np.std(similarities)
        
        print(f"\n🎯 Threshold Recommendations:")
        print(f"  Conservative (mean - 1*std): {mean_sim - std_sim:.3f}")
        print(f"  Moderate (mean - 0.5*std): {mean_sim - 0.5*std_sim:.3f}")
        print(f"  Aggressive (mean): {mean_sim:.3f}")
        print(f"  Very Aggressive (mean + 0.5*std): {mean_sim + 0.5*std_sim:.3f}")
        
        recommended = mean_sim - 0.5*std_sim
        print(f"  🎯 Recommended threshold: {recommended:.3f}")
        
        return recommended

def main():
    print("🚀 Erik OSNet Testing Tool")
    print("=" * 50)
    
    tester = ErikOSNetTester()
    
    # Instructions for user
    print("\n📋 Instructions:")
    print("1. Place Erik's images in a folder (e.g., ~/nvr/erik_images/)")
    print("2. Update the image_folder path below")
    print("3. Run this script to test OSNet with Erik's images")
    print()
    
    # Configuration - UPDATE THIS PATH
    image_folder = "/home/andrew/nvr/erik_images"  # Update this path!
    
    print(f"📁 Looking for images in: {image_folder}")
    
    if not os.path.exists(image_folder):
        print(f"❌ Folder not found: {image_folder}")
        print("\n🔧 To test OSNet:")
        print(f"1. Create folder: mkdir -p {image_folder}")
        print(f"2. Add Erik's images to: {image_folder}")
        print("3. Run this script again")
        
        # Test with sample images if available
        print("\n🧪 Testing with sample/demo images...")
        
        # Look for any images in current directory
        current_images = []
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
            current_images.extend(Path('.').glob(ext))
        
        if current_images:
            print(f"Found {len(current_images)} images in current directory")
            image_paths = [str(img) for img in current_images[:5]]  # Test first 5
        else:
            print("No test images available")
            return
    else:
        # Get all image files from the folder
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        image_paths = []
        
        for ext in image_extensions:
            image_paths.extend([str(p) for p in Path(image_folder).glob(f'*{ext}')])
            image_paths.extend([str(p) for p in Path(image_folder).glob(f'*{ext.upper()}')])
        
        if not image_paths:
            print(f"❌ No images found in {image_folder}")
            print(f"   Supported formats: {', '.join(image_extensions)}")
            return
        
        print(f"✓ Found {len(image_paths)} images")
    
    # Test images
    if len(image_paths) == 1:
        print("🔍 Testing single image...")
        tester.test_single_image(image_paths[0])
        
    elif len(image_paths) > 1:
        print(f"🔍 Testing similarity between {len(image_paths)} images...")
        result = tester.test_image_similarity(image_paths)
        
        if result is not None:
            features_dict, similarities = result
            if len(similarities) > 0:
                recommended_threshold = tester.recommend_threshold(similarities)
                
                print(f"\n✅ Testing complete!")
                print(f"📝 Next steps:")
                print(f"   1. Use threshold: {recommended_threshold:.3f}")
                print(f"   2. Add more Erik images if similarities are low")
                print(f"   3. Test with non-Erik images to verify discrimination")
        else:
            print("❌ Could not process images - check image formats and content")
    
    print(f"\n🎉 OSNet testing finished!")

if __name__ == "__main__":
    main()