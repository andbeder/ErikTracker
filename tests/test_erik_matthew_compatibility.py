#!/usr/bin/env python3
"""
Erik vs Matthew Compatibility Test
Tests whether the hybrid tracker can reliably distinguish between Erik and Matthew
"""

import os
import sys
import torch
import numpy as np
from pathlib import Path
from PIL import Image
import logging
from sklearn.metrics.pairwise import cosine_similarity
import matplotlib.pyplot as plt
import seaborn as sns

# Add the path for OSNet
sys.path.append('/home/andrew/nvr/osnet_venv/lib/python3.11/site-packages')

try:
    import torchreid
    from torchreid.reid.utils import FeatureExtractor
except ImportError as e:
    print(f"Error importing torchreid: {e}")
    print("Make sure you're running in the OSNet virtual environment")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PersonCompatibilityTester:
    def __init__(self):
        """Initialize OSNet feature extractor"""
        self.extractor = FeatureExtractor(
            model_name='osnet_x1_0',
            model_path='/home/andrew/nvr/osnet_x1_0_imagenet.pth',
            device='cpu'
        )
        logger.info("OSNet feature extractor initialized")
        
    def extract_features(self, image_folder):
        """Extract features from all images in a folder"""
        features = []
        image_files = []
        
        folder = Path(image_folder)
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        
        for ext in image_extensions:
            for image_path in folder.glob(f'*{ext}'):
                try:
                    # Extract features using file path directly
                    feature = self.extractor(str(image_path))
                    features.append(feature[0])  # Get the first (and only) feature vector
                    image_files.append(image_path.name)
                    
                    logger.info(f"Extracted features from {image_path.name}")
                    
                except Exception as e:
                    logger.error(f"Error processing {image_path}: {e}")
                    
        return np.array(features), image_files
    
    def run_compatibility_test(self, erik_folder, matthew_folder):
        """Run comprehensive compatibility test between Erik and Matthew"""
        
        print("🧪 Starting Erik vs Matthew Compatibility Test...")
        print("=" * 60)
        
        # Extract features for both persons
        print(f"📸 Extracting Erik features from {erik_folder}...")
        erik_features, erik_files = self.extract_features(erik_folder)
        
        print(f"📸 Extracting Matthew features from {matthew_folder}...")
        matthew_features, matthew_files = self.extract_features(matthew_folder)
        
        print(f"\n📊 Dataset Summary:")
        print(f"   Erik images: {len(erik_features)}")
        print(f"   Matthew images: {len(matthew_features)}")
        
        if len(erik_features) == 0 or len(matthew_features) == 0:
            print("❌ Error: No valid images found in one or both folders")
            return
        
        # Calculate similarity matrices
        print(f"\n🔍 Calculating similarity matrices...")
        
        # Within-person similarities (should be high)
        erik_internal = cosine_similarity(erik_features, erik_features)
        matthew_internal = cosine_similarity(matthew_features, matthew_features)
        
        # Cross-person similarities (should be low) 
        erik_vs_matthew = cosine_similarity(erik_features, matthew_features)
        
        # Calculate statistics
        erik_internal_mean = np.mean(erik_internal[np.triu_indices_from(erik_internal, k=1)])
        erik_internal_std = np.std(erik_internal[np.triu_indices_from(erik_internal, k=1)])
        
        matthew_internal_mean = np.mean(matthew_internal[np.triu_indices_from(matthew_internal, k=1)])
        matthew_internal_std = np.std(matthew_internal[np.triu_indices_from(matthew_internal, k=1)])
        
        cross_similarity_mean = np.mean(erik_vs_matthew)
        cross_similarity_max = np.max(erik_vs_matthew)
        cross_similarity_std = np.std(erik_vs_matthew)
        
        # Results
        print(f"\n📈 Similarity Analysis Results:")
        print(f"=" * 40)
        print(f"Erik internal similarity:    {erik_internal_mean:.3f} ± {erik_internal_std:.3f}")
        print(f"Matthew internal similarity: {matthew_internal_mean:.3f} ± {matthew_internal_std:.3f}")
        print(f"Cross-person similarity:     {cross_similarity_mean:.3f} ± {cross_similarity_std:.3f}")
        print(f"Max cross-person similarity: {cross_similarity_max:.3f}")
        
        # Separation analysis
        separation_quality = min(erik_internal_mean, matthew_internal_mean) - cross_similarity_max
        
        print(f"\n🎯 Compatibility Assessment:")
        print(f"=" * 40)
        print(f"Separation quality: {separation_quality:.3f}")
        
        if separation_quality > 0.2:
            recommendation = "✅ EXCELLENT - Multi-person tracking recommended"
            risk_level = "Very Low"
        elif separation_quality > 0.1:
            recommendation = "✅ GOOD - Multi-person tracking likely safe"
            risk_level = "Low"
        elif separation_quality > 0.0:
            recommendation = "⚠️  MARGINAL - Proceed with caution"
            risk_level = "Medium"
        else:
            recommendation = "❌ POOR - High risk of confusion"
            risk_level = "High"
            
        print(f"Risk Level: {risk_level}")
        print(f"Recommendation: {recommendation}")
        
        # Threshold analysis
        current_threshold = 0.484
        print(f"\n🔧 Threshold Analysis (current: {current_threshold}):")
        print(f"=" * 50)
        
        erik_above_threshold = np.sum(erik_internal > current_threshold) / erik_internal.size * 100
        matthew_above_threshold = np.sum(matthew_internal > current_threshold) / matthew_internal.size * 100
        cross_above_threshold = np.sum(erik_vs_matthew > current_threshold) / erik_vs_matthew.size * 100
        
        print(f"Erik matches above threshold:    {erik_above_threshold:.1f}%")
        print(f"Matthew matches above threshold: {matthew_above_threshold:.1f}%")
        print(f"Cross matches above threshold:   {cross_above_threshold:.1f}% (should be ~0%)")
        
        if cross_above_threshold > 10:
            print("⚠️  WARNING: High cross-person confusion risk!")
        elif cross_above_threshold > 5:
            print("⚠️  CAUTION: Some cross-person confusion possible")
        else:
            print("✅ Good threshold separation")
            
        # Suggested thresholds
        erik_suggested = np.percentile(erik_internal[np.triu_indices_from(erik_internal, k=1)], 15)
        matthew_suggested = np.percentile(matthew_internal[np.triu_indices_from(matthew_internal, k=1)], 15)
        
        print(f"\n💡 Suggested individual thresholds:")
        print(f"   Erik threshold:    {erik_suggested:.3f}")
        print(f"   Matthew threshold: {matthew_suggested:.3f}")
        
        # Final recommendation
        print(f"\n🎯 FINAL RECOMMENDATION:")
        print(f"=" * 30)
        if separation_quality > 0.1 and cross_above_threshold < 10:
            print("✅ PROCEED with multi-person tracking")
            print("   • Good feature separation detected")
            print("   • Low confusion risk")
            print("   • Should improve overall system accuracy")
        elif separation_quality > 0.0:
            print("⚠️  PROCEED WITH CAUTION")
            print("   • Moderate separation - tune thresholds carefully")
            print("   • Monitor for false positives")
            print("   • Consider person-specific thresholds")
        else:
            print("❌ DO NOT PROCEED - stick with Erik-only")
            print("   • High confusion risk")
            print("   • May degrade Erik tracking accuracy")
            print("   • Consider waiting until subjects are more distinct")
            
        return {
            'erik_internal_mean': erik_internal_mean,
            'matthew_internal_mean': matthew_internal_mean,
            'cross_similarity_mean': cross_similarity_mean,
            'cross_similarity_max': cross_similarity_max,
            'separation_quality': separation_quality,
            'recommendation': recommendation,
            'risk_level': risk_level
        }

if __name__ == "__main__":
    # Paths to image folders
    erik_folder = "/home/andrew/nvr/erik_images"
    matthew_folder = "/home/andrew/nvr/matthew_images"
    
    # Check if folders exist
    if not os.path.exists(erik_folder):
        print(f"❌ Error: Erik folder not found: {erik_folder}")
        sys.exit(1)
        
    if not os.path.exists(matthew_folder):
        print(f"❌ Error: Matthew folder not found: {matthew_folder}")
        sys.exit(1)
    
    # Run the test
    tester = PersonCompatibilityTester()
    results = tester.run_compatibility_test(erik_folder, matthew_folder)