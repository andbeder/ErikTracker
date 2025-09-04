#!/usr/bin/env python3
"""
Hybrid Erik Tracker - Combines OSNet person re-identification with face recognition
Integrates with Frigate via MQTT for real-time person detection and tracking
"""

import torch
import torchreid
import cv2
import numpy as np
import paho.mqtt.client as mqtt
import json
import requests
import base64
import logging
from typing import Dict, List, Optional, Tuple, Any
from io import BytesIO
from PIL import Image
import time
from pathlib import Path
import os
from datetime import datetime
import threading
import queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HybridErikTracker:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.mqtt_client = None
        self.processing_queue = queue.Queue(maxsize=100)
        
        # OSNet setup
        logger.info("Loading OSNet model...")
        self.osnet_model = torchreid.models.build_model(
            name='osnet_x1_0',
            num_classes=1000,
            pretrained=True
        )
        self.osnet_model.eval()
        
        # Erik's reference features
        self.erik_features: Optional[torch.Tensor] = None
        self.osnet_threshold = config.get('osnet_threshold', 0.484)
        
        # Face recognition setup
        self.face_recognition_enabled = config.get('enable_face_recognition', True)
        self.face_threshold = config.get('face_threshold', 0.75)
        
        # Frigate integration
        self.frigate_url = config.get('frigate_url', 'http://localhost:5000')
        
        # Confidence fusion weights
        self.osnet_weight = config.get('osnet_weight', 0.5)
        self.face_weight = config.get('face_weight', 0.3)
        self.color_weight = config.get('color_weight', 0.2)
        
        # Color tracking
        self.erik_shirt_color = None  # HSV hue value (0-179)
        self.erik_color_range = None  # (lower_hue, upper_hue) tolerance range
        self.color_confidence_threshold = config.get('color_confidence_threshold', 0.6)
        self.color_tolerance = config.get('color_tolerance', 15)  # degrees in HSV hue
        self.color_enabled = config.get('enable_color_tracking', True)
        
        # Recent detections cache (prevent spam)
        self.recent_detections = {}
        self.detection_cooldown = config.get('detection_cooldown', 5)  # seconds
        
        # Daily shirt color notification flag
        self.daily_color_notified = False
        self.last_notification_date = None
        
        logger.info("Hybrid Erik Tracker initialized")
        
    def load_erik_references(self, image_folder: str):
        """Load Erik's reference images and compute average OSNet features"""
        image_paths = []
        for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
            image_paths.extend(Path(image_folder).glob(f'*{ext}'))
            image_paths.extend(Path(image_folder).glob(f'*{ext.upper()}'))
            
        if not image_paths:
            logger.error(f"No Erik reference images found in {image_folder}")
            return False
            
        erik_features = []
        valid_images = 0
        
        for image_path in image_paths:
            try:
                features = self._extract_osnet_features_from_file(str(image_path))
                if features is not None:
                    erik_features.append(features)
                    valid_images += 1
            except Exception as e:
                logger.warning(f"Could not process {image_path}: {e}")
                
        if erik_features:
            self.erik_features = torch.mean(torch.cat(erik_features), dim=0, keepdim=True)
            logger.info(f"Loaded Erik reference features from {valid_images} images")
            return True
        else:
            logger.error("No valid Erik reference images processed")
            return False
            
    def _extract_osnet_features_from_file(self, image_path: str) -> Optional[torch.Tensor]:
        """Extract OSNet features from image file"""
        image = cv2.imread(image_path)
        if image is None:
            return None
        return self._extract_osnet_features(image)
        
    def _extract_osnet_features(self, image: np.ndarray) -> Optional[torch.Tensor]:
        """Extract OSNet features from image array"""
        try:
            # Resize to OSNet input size
            image = cv2.resize(image, (128, 256))
            
            # Convert BGR to RGB and normalize
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            image = image.astype(np.float32) / 255.0
            
            # ImageNet normalization
            mean = np.array([0.485, 0.456, 0.406])
            std = np.array([0.229, 0.224, 0.225])
            image = (image - mean) / std
            
            # Convert to tensor
            tensor = torch.tensor(image, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)
            
            with torch.no_grad():
                features = self.osnet_model(tensor)
            
            # L2 normalize
            features = torch.nn.functional.normalize(features, p=2, dim=1)
            return features
            
        except Exception as e:
            logger.error(f"OSNet feature extraction failed: {e}")
            return None
            
    def _compute_osnet_similarity(self, features: torch.Tensor) -> float:
        """Compute OSNet similarity with Erik's reference features"""
        if self.erik_features is None:
            return 0.0
        
        similarity = torch.cosine_similarity(
            self.erik_features, features, dim=1
        ).item()
        return similarity
    
    def _hue_to_color_name(self, hue: float) -> str:
        """Convert HSV hue value to human-readable color name"""
        if hue is None:
            return "unknown"
            
        # HSV hue ranges (0-179 in OpenCV)
        # Red: 0-10, 160-179
        # Orange: 11-25  
        # Yellow: 26-35
        # Green: 36-85
        # Cyan: 86-95
        # Blue: 96-125
        # Purple: 126-150
        # Pink: 151-159
        
        hue = int(hue)
        
        if hue <= 10 or hue >= 160:
            return "red"
        elif 11 <= hue <= 25:
            return "orange"
        elif 26 <= hue <= 35:
            return "yellow"
        elif 36 <= hue <= 85:
            return "green"
        elif 86 <= hue <= 95:
            return "cyan"
        elif 96 <= hue <= 125:
            return "blue"
        elif 126 <= hue <= 150:
            return "purple"
        elif 151 <= hue <= 159:
            return "pink"
        else:
            return f"color-{hue}"  # Fallback with numeric value
        
    def _extract_torso_region(self, person_image: np.ndarray) -> np.ndarray:
        """Extract torso region from person image (middle third of height)"""
        h, w = person_image.shape[:2]
        
        # Define torso region (middle third vertically, central 70% horizontally)
        torso_top = h // 4
        torso_bottom = int(h * 0.75)
        torso_left = int(w * 0.15)
        torso_right = int(w * 0.85)
        
        torso_region = person_image[torso_top:torso_bottom, torso_left:torso_right]
        return torso_region
        
    def _get_dominant_hue(self, image_region: np.ndarray) -> Optional[float]:
        """Extract dominant hue from image region using HSV color space"""
        if image_region.size == 0:
            return None
            
        try:
            # Convert BGR to HSV
            hsv = cv2.cvtColor(image_region, cv2.COLOR_BGR2HSV)
            
            # Create mask to exclude very dark or very light pixels (shadows/highlights)
            # S > 30 (not too gray), V > 30 and V < 230 (not too dark/bright)
            mask = cv2.inRange(hsv, (0, 30, 30), (179, 255, 230))
            
            if cv2.countNonZero(mask) < 10:  # Not enough valid pixels
                return None
            
            # Get hue values from masked region
            hue_values = hsv[:, :, 0][mask > 0]
            
            if len(hue_values) == 0:
                return None
                
            # Calculate histogram of hue values
            hist = cv2.calcHist([hue_values], [0], None, [180], [0, 180])
            
            # Find the dominant hue (mode)
            dominant_hue = np.argmax(hist)
            
            # Calculate confidence based on how concentrated the hue distribution is
            total_pixels = len(hue_values)
            dominant_count = hist[dominant_hue][0]
            confidence = dominant_count / total_pixels
            
            if confidence < 0.1:  # Too dispersed, no clear dominant color
                return None
                
            return float(dominant_hue)
            
        except Exception as e:
            logger.error(f"Error extracting dominant hue: {e}")
            return None
            
    def _update_erik_color_profile(self, person_image: np.ndarray, face_confidence: float):
        """Update Erik's color profile when we have high confidence face recognition"""
        if not self.color_enabled:
            return
            
        # Only update color profile with high confidence face matches
        if face_confidence < 0.9:
            return
            
        torso_region = self._extract_torso_region(person_image)
        dominant_hue = self._get_dominant_hue(torso_region)
        
        if dominant_hue is not None:
            # Check if this is the first color identification of the day
            current_date = datetime.now().date()
            is_first_color_of_day = (
                self.erik_shirt_color is None or 
                self.last_notification_date != current_date or
                not self.daily_color_notified
            )
            
            # Update Erik's shirt color
            self.erik_shirt_color = dominant_hue
            
            # Calculate tolerance range
            lower_hue = max(0, dominant_hue - self.color_tolerance)
            upper_hue = min(179, dominant_hue + self.color_tolerance)
            
            # Handle hue wraparound (red is at 0 and 179)
            if dominant_hue < self.color_tolerance:
                # Red hue near 0, also include high values near 179
                self.erik_color_range = (max(0, dominant_hue - self.color_tolerance),
                                       min(179, dominant_hue + self.color_tolerance),
                                       max(0, 179 - (self.color_tolerance - dominant_hue)),
                                       179)
            elif dominant_hue > (179 - self.color_tolerance):
                # Red hue near 179, also include low values near 0
                self.erik_color_range = (0,
                                       min(179, self.color_tolerance - (179 - dominant_hue)),
                                       max(0, dominant_hue - self.color_tolerance),
                                       179)
            else:
                # Normal case, no wraparound
                self.erik_color_range = (lower_hue, upper_hue)
            
            color_name = self._hue_to_color_name(dominant_hue)
            
            logger.info(f"Updated Erik's shirt color profile: {color_name} (hue={dominant_hue:.1f}), "
                       f"range={self.erik_color_range}")
            
            # Send push notification for first color identification of the day
            if is_first_color_of_day:
                self._send_daily_color_notification(color_name, dominant_hue, face_confidence)
                self.daily_color_notified = True
                self.last_notification_date = current_date
    
    def _send_daily_color_notification(self, color_name: str, hue: float, confidence: float):
        """Send iPhone push notification for Erik's daily shirt color"""
        try:
            current_time = datetime.now().strftime("%I:%M %p")
            
            # Create notification data
            notification_data = {
                "color_detected": color_name,
                "hue_value": round(hue, 1),
                "face_confidence": round(confidence, 2),
                "timestamp": datetime.now().isoformat(),
                "notification_type": "daily_color_identification"
            }
            
            # Publish to MQTT for Home Assistant automation
            self.mqtt_client.publish(
                "yard/erik/daily_color",
                json.dumps(notification_data)
            )
            
            logger.info(f"🎨 Daily color notification sent: Erik is wearing a {color_name} shirt today!")
            
            # Also publish to general notifications topic
            notification_message = {
                "title": "👕 Erik's Shirt Color Today",
                "message": f"Erik is wearing a {color_name} shirt (detected at {current_time})",
                "priority": "normal",
                "sound": "magic",  # Pushover sound
                "color_name": color_name,
                "hue": hue,
                "confidence": confidence,
                "timestamp": notification_data["timestamp"]
            }
            
            self.mqtt_client.publish(
                "notifications/erik/color",
                json.dumps(notification_message)
            )
            
        except Exception as e:
            logger.error(f"Failed to send daily color notification: {e}")
                       
    def _compute_color_similarity(self, person_image: np.ndarray) -> float:
        """Compute color similarity with Erik's current shirt color"""
        if not self.color_enabled or self.erik_shirt_color is None:
            return 0.0
            
        torso_region = self._extract_torso_region(person_image)
        current_hue = self._get_dominant_hue(torso_region)
        
        if current_hue is None:
            return 0.0
            
        try:
            # Calculate similarity based on hue distance
            if len(self.erik_color_range) == 2:
                # Simple range (no wraparound)
                lower, upper = self.erik_color_range
                if lower <= current_hue <= upper:
                    # Within range - calculate proximity to center
                    center_distance = abs(current_hue - self.erik_shirt_color)
                    similarity = 1.0 - (center_distance / self.color_tolerance)
                    return max(0.0, similarity)
                else:
                    return 0.0
            else:
                # Wraparound case (red hue)
                low1, high1, low2, high2 = self.erik_color_range
                in_range = (low1 <= current_hue <= high1) or (low2 <= current_hue <= high2)
                
                if in_range:
                    # Calculate distance considering wraparound
                    dist1 = abs(current_hue - self.erik_shirt_color)
                    dist2 = 180 - dist1  # Wraparound distance
                    min_distance = min(dist1, dist2)
                    similarity = 1.0 - (min_distance / self.color_tolerance)
                    return max(0.0, similarity)
                else:
                    return 0.0
                    
        except Exception as e:
            logger.error(f"Error computing color similarity: {e}")
            return 0.0
        
    def _get_person_crop_from_frigate(self, camera: str, detection: Dict) -> Optional[np.ndarray]:
        """Get person crop from Frigate detection"""
        try:
            # Get the detection ID or timestamp to fetch the image
            detection_id = detection.get('id')
            if not detection_id:
                return None
                
            # Fetch image from Frigate API
            crop_url = f"{self.frigate_url}/api/{camera}/latest.jpg"
            response = requests.get(crop_url, timeout=5)
            
            if response.status_code == 200:
                # Convert to OpenCV image
                image_array = np.frombuffer(response.content, np.uint8)
                full_image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                
                # Extract bounding box
                bbox = detection.get('box', detection.get('bbox'))
                if bbox and len(bbox) >= 4:
                    x, y, w, h = bbox[:4]
                    # Ensure coordinates are within image bounds
                    h_img, w_img = full_image.shape[:2]
                    x = max(0, min(int(x), w_img))
                    y = max(0, min(int(y), h_img))
                    w = max(1, min(int(w), w_img - x))
                    h = max(1, min(int(h), h_img - y))
                    
                    # Crop the person
                    person_crop = full_image[y:y+h, x:x+w]
                    
                    if person_crop.size > 0:
                        return person_crop
                        
        except Exception as e:
            logger.error(f"Failed to get person crop from Frigate: {e}")
            
        return None
        
    def _query_face_recognition(self, image: np.ndarray) -> Tuple[bool, float]:
        """Query face recognition system (Double Take or CompreFace)"""
        if not self.face_recognition_enabled:
            return False, 0.0
            
        try:
            # Encode image as base64
            _, buffer = cv2.imencode('.jpg', image)
            image_b64 = base64.b64encode(buffer).decode('utf-8')
            
            # Query Double Take or CompreFace API
            # This is a placeholder - implement based on your face recognition setup
            face_api_url = self.config.get('face_api_url', 'http://localhost:3000/api/recognize')
            
            payload = {
                'image': image_b64,
                'target': 'erik'  # or however your system identifies Erik
            }
            
            response = requests.post(face_api_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                # Parse response based on your face recognition system
                confidence = result.get('confidence', 0.0)
                is_erik = confidence >= self.face_threshold
                return is_erik, confidence
                
        except Exception as e:
            logger.error(f"Face recognition query failed: {e}")
            
        return False, 0.0
        
    def _fuse_confidence_scores(self, osnet_score: float, face_score: float, color_score: float,
                               osnet_detected: bool, face_detected: bool, color_detected: bool) -> Tuple[bool, float, Dict]:
        """Fuse OSNet, face recognition, and color confidence scores"""
        
        # Normalize weights to ensure they sum to 1.0
        total_weight = self.osnet_weight + self.face_weight + self.color_weight
        norm_osnet_weight = self.osnet_weight / total_weight
        norm_face_weight = self.face_weight / total_weight
        norm_color_weight = self.color_weight / total_weight
        
        # Count how many methods detected Erik
        detection_count = sum([osnet_detected, face_detected, color_detected])
        
        # Base weighted combination
        combined_score = (
            norm_osnet_weight * osnet_score +
            norm_face_weight * face_score +
            norm_color_weight * color_score
        )
        
        # Determine method and apply confidence boosters
        if detection_count >= 2:
            # Multiple methods agree - boost confidence
            method_parts = []
            if osnet_detected:
                method_parts.append("osnet")
            if face_detected:
                method_parts.append("face")
            if color_detected:
                method_parts.append("color")
            method = "hybrid_" + "_".join(method_parts)
            
            # Apply consensus bonus (small boost for agreement)
            consensus_bonus = 0.1 * (detection_count - 1)
            combined_score = min(1.0, combined_score + consensus_bonus)
            
        elif detection_count == 1:
            # Single method detection
            if osnet_detected:
                method = "osnet_only"
            elif face_detected:
                method = "face_only"
            elif color_detected:
                method = "color_only"
        else:
            # No detection
            combined_score = 0.0
            method = "none"
            
        # Adaptive decision threshold based on color profile availability
        if self.erik_shirt_color is not None:
            # We have a color profile, can be slightly more permissive
            decision_threshold = 0.35
        else:
            # No color profile yet, require higher confidence
            decision_threshold = 0.4
            
        is_erik = combined_score >= decision_threshold
        
        details = {
            "osnet_score": osnet_score,
            "face_score": face_score,
            "color_score": color_score,
            "osnet_detected": osnet_detected,
            "face_detected": face_detected,
            "color_detected": color_detected,
            "combined_score": combined_score,
            "method": method,
            "threshold": decision_threshold,
            "detection_count": detection_count,
            "erik_shirt_color": self.erik_shirt_color,
            "weights": {
                "osnet": norm_osnet_weight,
                "face": norm_face_weight,
                "color": norm_color_weight
            }
        }
        
        return is_erik, combined_score, details
        
    def _is_recent_detection(self, camera: str) -> bool:
        """Check if we recently detected Erik on this camera"""
        key = f"{camera}_erik"
        last_detection = self.recent_detections.get(key, 0)
        return (time.time() - last_detection) < self.detection_cooldown
        
    def _mark_recent_detection(self, camera: str):
        """Mark Erik as recently detected on this camera"""
        key = f"{camera}_erik"
        self.recent_detections[key] = time.time()
        
    def _process_person_detection(self, camera: str, detection: Dict):
        """Process person detection with hybrid approach"""
        try:
            # Skip if we recently detected Erik on this camera
            if self._is_recent_detection(camera):
                return
                
            # Get person crop from Frigate
            person_crop = self._get_person_crop_from_frigate(camera, detection)
            if person_crop is None:
                logger.warning(f"Could not get person crop for {camera}")
                return
                
            # OSNet analysis
            osnet_features = self._extract_osnet_features(person_crop)
            osnet_score = 0.0
            osnet_detected = False
            
            if osnet_features is not None:
                osnet_score = self._compute_osnet_similarity(osnet_features)
                osnet_detected = osnet_score >= self.osnet_threshold
                
            # Face recognition analysis
            face_detected, face_score = self._query_face_recognition(person_crop)
            
            # Color analysis
            color_score = self._compute_color_similarity(person_crop)
            color_detected = color_score >= self.color_confidence_threshold
            
            # Update Erik's color profile if we have high confidence face match
            if face_detected and face_score >= 0.9:
                self._update_erik_color_profile(person_crop, face_score)
            
            # Fuse confidence scores
            is_erik, combined_confidence, details = self._fuse_confidence_scores(
                osnet_score, face_score, color_score, osnet_detected, face_detected, color_detected
            )
            
            if is_erik:
                # Mark recent detection to prevent spam
                self._mark_recent_detection(camera)
                
                # Publish Erik detection
                erik_data = {
                    "camera": camera,
                    "timestamp": datetime.now().isoformat(),
                    "confidence": combined_confidence,
                    "details": details,
                    "bbox": detection.get('box', detection.get('bbox')),
                    "detection_id": detection.get('id'),
                    "method": "hybrid_tracker"
                }
                
                self.mqtt_client.publish(
                    f"yard/erik/detected/{camera}",
                    json.dumps(erik_data)
                )
                
                logger.info(
                    f"Erik detected on {camera} - Combined: {combined_confidence:.3f} "
                    f"(OSNet: {osnet_score:.3f}, Face: {face_score:.3f}, Color: {color_score:.3f}) "
                    f"[{details['method']}] Color: {self.erik_shirt_color}"
                )
                
                # Also publish to general Erik topic
                self.mqtt_client.publish("yard/erik/status", json.dumps({
                    "detected": True,
                    "camera": camera,
                    "confidence": combined_confidence,
                    "timestamp": erik_data["timestamp"]
                }))
                
        except Exception as e:
            logger.error(f"Error processing person detection: {e}")
            
    def _worker_thread(self):
        """Worker thread to process detections"""
        while True:
            try:
                camera, detection = self.processing_queue.get(timeout=1)
                self._process_person_detection(camera, detection)
                self.processing_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker thread error: {e}")
                
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            # Subscribe to Frigate person events
            client.subscribe("frigate/+/person")
            client.subscribe("frigate/events")
        else:
            logger.error(f"MQTT connection failed with code {rc}")
            
    def _on_mqtt_message(self, client, userdata, msg):
        """MQTT message callback"""
        try:
            topic_parts = msg.topic.split('/')
            
            if len(topic_parts) >= 3 and topic_parts[2] == "person":
                # Person detection on specific camera
                camera = topic_parts[1]
                data = json.loads(msg.payload.decode())
                
                # Add to processing queue (non-blocking)
                try:
                    self.processing_queue.put_nowait((camera, data))
                except queue.Full:
                    logger.warning("Processing queue full, dropping detection")
                    
            elif msg.topic == "frigate/events":
                # General Frigate events
                data = json.loads(msg.payload.decode())
                if data.get('type') == 'new' and 'person' in data.get('label', ''):
                    camera = data.get('camera')
                    if camera:
                        try:
                            self.processing_queue.put_nowait((camera, data))
                        except queue.Full:
                            logger.warning("Processing queue full, dropping event")
                            
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
            
    def start(self):
        """Start the hybrid tracker"""
        logger.info("Starting Hybrid Erik Tracker...")
        
        # Load Erik's reference images
        erik_images_folder = self.config.get('erik_images_folder', '/app/erik_images')
        if not self.load_erik_references(erik_images_folder):
            logger.error("Failed to load Erik reference images")
            return False
            
        # Start worker thread
        worker = threading.Thread(target=self._worker_thread, daemon=True)
        worker.start()
        
        # Setup MQTT
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        
        mqtt_host = self.config.get('mqtt_host', 'localhost')
        mqtt_port = self.config.get('mqtt_port', 1883)
        
        try:
            self.mqtt_client.connect(mqtt_host, mqtt_port, 60)
            logger.info(f"Starting MQTT loop on {mqtt_host}:{mqtt_port}")
            self.mqtt_client.loop_forever()
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            return False
            
def load_config():
    """Load configuration from file or environment"""
    config = {
        # MQTT settings
        'mqtt_host': os.getenv('MQTT_HOST', 'localhost'),
        'mqtt_port': int(os.getenv('MQTT_PORT', '1883')),
        
        # Frigate settings
        'frigate_url': os.getenv('FRIGATE_URL', 'http://localhost:5000'),
        
        # OSNet settings
        'osnet_threshold': float(os.getenv('OSNET_THRESHOLD', '0.484')),
        'osnet_weight': float(os.getenv('OSNET_WEIGHT', '0.5')),
        
        # Face recognition settings
        'enable_face_recognition': os.getenv('ENABLE_FACE_RECOGNITION', 'true').lower() == 'true',
        'face_api_url': os.getenv('FACE_API_URL', 'http://double-take:3000/api/recognize'),
        'face_threshold': float(os.getenv('FACE_THRESHOLD', '0.75')),
        'face_weight': float(os.getenv('FACE_WEIGHT', '0.3')),
        
        # Color tracking settings
        'enable_color_tracking': os.getenv('ENABLE_COLOR_TRACKING', 'true').lower() == 'true',
        'color_weight': float(os.getenv('COLOR_WEIGHT', '0.2')),
        'color_confidence_threshold': float(os.getenv('COLOR_CONFIDENCE_THRESHOLD', '0.6')),
        'color_tolerance': float(os.getenv('COLOR_TOLERANCE', '15')),
        
        # Erik reference images
        'erik_images_folder': os.getenv('ERIK_IMAGES_FOLDER', '/app/erik_images'),
        
        # Detection settings
        'detection_cooldown': int(os.getenv('DETECTION_COOLDOWN', '5')),
    }
    
    return config

def main():
    """Main entry point"""
    logger.info("=== Hybrid Erik Tracker Starting ===")
    
    config = load_config()
    
    # Log configuration (without sensitive data)
    logger.info("Configuration:")
    for key, value in config.items():
        if 'password' not in key.lower() and 'secret' not in key.lower():
            logger.info(f"  {key}: {value}")
    
    tracker = HybridErikTracker(config)
    
    try:
        tracker.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Tracker failed: {e}")
        
if __name__ == "__main__":
    main()