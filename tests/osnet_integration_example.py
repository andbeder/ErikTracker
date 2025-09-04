#!/usr/bin/env python3
"""
OSNet integration example for Erik tracking
This shows how to integrate OSNet with your existing Frigate/MQTT setup
"""

import torch
import torchreid
import cv2
import numpy as np
import paho.mqtt.client as mqtt
import json
from typing import Dict, List, Optional, Tuple
import base64
from io import BytesIO
from PIL import Image

class ErikTracker:
    def __init__(self, 
                 mqtt_host: str = "localhost",
                 mqtt_port: int = 1883,
                 similarity_threshold: float = 0.7):
        
        # Load OSNet model
        self.model = torchreid.models.build_model(
            name='osnet_x1_0',
            num_classes=1000,  # placeholder
            pretrained=True
        )
        self.model.eval()
        
        # Store Erik's reference features (to be populated)
        self.erik_features: Optional[torch.Tensor] = None
        self.similarity_threshold = similarity_threshold
        
        # MQTT setup
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        self.mqtt_client.connect(mqtt_host, mqtt_port, 60)
        
        print("Erik Tracker initialized with OSNet")
        
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Subscribe to Frigate person detection events"""
        print(f"MQTT connected with result code {rc}")
        # Subscribe to Frigate person detection events
        client.subscribe("frigate/+/person")
        client.subscribe("frigate/+/events")
        
    def _on_mqtt_message(self, client, userdata, msg):
        """Process incoming Frigate detection messages"""
        try:
            topic_parts = msg.topic.split('/')
            camera = topic_parts[1]
            
            if "person" in msg.topic:
                data = json.loads(msg.payload.decode())
                self._process_person_detection(camera, data)
                
        except Exception as e:
            print(f"Error processing MQTT message: {e}")
    
    def preprocess_image(self, image: np.ndarray) -> torch.Tensor:
        """Preprocess image for OSNet (resize to 256x128, normalize)"""
        # Resize to OSNet input size
        image = cv2.resize(image, (128, 256))
        
        # Convert BGR to RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Normalize
        image = image.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        image = (image - mean) / std
        
        # Convert to tensor and add batch dimension
        image = torch.tensor(image).permute(2, 0, 1).unsqueeze(0)
        return image
    
    def extract_features(self, image: np.ndarray) -> torch.Tensor:
        """Extract OSNet features from person crop"""
        processed_image = self.preprocess_image(image)
        
        with torch.no_grad():
            features = self.model(processed_image)
        
        # Normalize features
        features = torch.nn.functional.normalize(features, p=2, dim=1)
        return features
    
    def register_erik(self, image_paths: List[str]):
        """Register Erik's reference images and compute average features"""
        erik_feature_list = []
        
        for image_path in image_paths:
            image = cv2.imread(image_path)
            if image is None:
                print(f"Warning: Could not load {image_path}")
                continue
                
            features = self.extract_features(image)
            erik_feature_list.append(features)
        
        if erik_feature_list:
            # Average all Erik features
            self.erik_features = torch.mean(torch.cat(erik_feature_list), dim=0, keepdim=True)
            print(f"Registered Erik with {len(erik_feature_list)} reference images")
        else:
            print("Error: No valid Erik images found")
    
    def is_erik(self, image: np.ndarray) -> Tuple[bool, float]:
        """Check if detected person is Erik"""
        if self.erik_features is None:
            print("Warning: Erik not registered yet")
            return False, 0.0
        
        # Extract features from detected person
        person_features = self.extract_features(image)
        
        # Compute cosine similarity
        similarity = torch.cosine_similarity(
            self.erik_features, person_features, dim=1
        ).item()
        
        is_match = similarity >= self.similarity_threshold
        return is_match, similarity
    
    def _process_person_detection(self, camera: str, detection_data: Dict):
        """Process person detection from Frigate"""
        try:
            # Extract person crop from detection (you'll need to implement this
            # based on your Frigate setup - this might involve getting the image
            # from Frigate's API and cropping based on bounding box coordinates)
            
            # Placeholder for getting person crop
            person_crop = self._get_person_crop_from_frigate(camera, detection_data)
            
            if person_crop is not None:
                is_erik, confidence = self.is_erik(person_crop)
                
                if is_erik:
                    # Publish Erik detection to MQTT
                    erik_data = {
                        "camera": camera,
                        "confidence": confidence,
                        "timestamp": detection_data.get("timestamp"),
                        "bbox": detection_data.get("bbox"),
                        "method": "osnet"
                    }
                    
                    self.mqtt_client.publish(
                        f"yard/erik/detected/{camera}", 
                        json.dumps(erik_data)
                    )
                    
                    print(f"Erik detected on {camera} with confidence {confidence:.3f}")
                    
        except Exception as e:
            print(f"Error processing person detection: {e}")
    
    def _get_person_crop_from_frigate(self, camera: str, detection_data: Dict) -> Optional[np.ndarray]:
        """
        Get person crop from Frigate detection
        This is a placeholder - you'll need to implement based on your Frigate setup
        """
        # This would typically involve:
        # 1. Getting the full frame from Frigate API
        # 2. Cropping based on bounding box coordinates
        # 3. Returning the cropped person image
        
        # For now, return None - implement based on your Frigate integration
        return None
    
    def run(self):
        """Start the tracker"""
        print("Starting Erik Tracker...")
        self.mqtt_client.loop_forever()

def main():
    # Initialize tracker
    tracker = ErikTracker(
        mqtt_host="localhost",  # Your MQTT broker
        similarity_threshold=0.7  # Adjust based on testing
    )
    
    # Register Erik's reference images
    erik_images = [
        "/path/to/erik_image1.jpg",
        "/path/to/erik_image2.jpg",
        "/path/to/erik_image3.jpg",
    ]
    tracker.register_erik(erik_images)
    
    # Start tracking
    tracker.run()

if __name__ == "__main__":
    main()