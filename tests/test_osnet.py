#!/usr/bin/env python3

import torch
import torchreid

def test_osnet_availability():
    """Test if OSNet models are available and can be loaded"""
    
    print("TorchReID version:", torchreid.__version__)
    print("PyTorch version:", torch.__version__)
    print()
    
    # Check available models - try different approaches
    print("Available models in TorchReID:")
    
    # Try to load OSNet models directly
    osnet_models = ['osnet_x1_0', 'osnet_x0_75', 'osnet_x0_5', 'osnet_x0_25']
    print(f"Testing OSNet models: {osnet_models}")
    print()
    
    success = False
    for model_name in osnet_models:
        print(f"Testing model: {model_name}")
        try:
            model = torchreid.models.build_model(
                name=model_name,
                num_classes=1000,  # placeholder
                pretrained=True
            )
            
            print(f"✓ Successfully loaded {model_name}")
            print(f"Model type: {type(model)}")
            
            # Test with dummy input
            model.eval()
            dummy_input = torch.randn(1, 3, 256, 128)  # Standard ReID input size
            with torch.no_grad():
                features = model(dummy_input)
            
            print(f"✓ Model forward pass successful")
            print(f"Feature shape: {features.shape}")
            
            success = True
            break  # Exit on first successful model
            
        except Exception as e:
            print(f"✗ Error loading {model_name}: {e}")
            continue
    
    if not success:
        print("✗ No OSNet models could be loaded")
        
    return success

if __name__ == "__main__":
    test_osnet_availability()