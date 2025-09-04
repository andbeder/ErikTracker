"""
MQTT Service for Erik Detection Monitoring
Handles MQTT connections and detection message processing
"""

import json
import logging
import threading
from datetime import datetime
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

class MQTTDetectionListener:
    """Manages MQTT connections for detection monitoring"""
    
    def __init__(self, host='localhost', port=1883):
        """Initialize MQTT listener
        
        Args:
            host: MQTT broker host
            port: MQTT broker port
        """
        self.host = host
        self.port = port
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.running = False
        
        # Storage for detection matches
        self.detection_matches = []
        self.matches_lock = threading.Lock()
        self.max_matches = 50
        
    def _on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection events"""
        if rc == 0:
            logger.info("MQTT connected for detection monitoring")
            client.subscribe("yard/erik/detected/+")
        else:
            logger.error(f"MQTT connection failed: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Process incoming MQTT messages"""
        try:
            detection_data = json.loads(msg.payload.decode())
            camera = msg.topic.split('/')[-1]
            
            # Add camera name and timestamp
            detection_data['camera'] = camera
            detection_data['received_time'] = datetime.now().isoformat()
            
            with self.matches_lock:
                # Add to matches list (keep last N matches)
                self.detection_matches.insert(0, detection_data)
                if len(self.detection_matches) > self.max_matches:
                    self.detection_matches.pop()
                    
            logger.info(f"Received Erik detection on {camera}: {detection_data.get('confidence', 0):.3f}")
            
        except Exception as e:
            logger.error(f"Error processing detection message: {e}")
    
    def start(self):
        """Start MQTT listener"""
        try:
            self.client.connect(self.host, self.port, 60)
            self.running = True
            self.client.loop_start()
            logger.info(f"MQTT listener started on {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start MQTT listener: {e}")
            return False
    
    def stop(self):
        """Stop MQTT listener"""
        if self.running:
            self.client.loop_stop()
            self.client.disconnect()
            self.running = False
            logger.info("MQTT listener stopped")
    
    def get_matches(self):
        """Get current detection matches
        
        Returns:
            List of detection matches
        """
        with self.matches_lock:
            return self.detection_matches.copy()
    
    def clear_matches(self):
        """Clear all detection matches"""
        with self.matches_lock:
            self.detection_matches.clear()
            logger.info("Cleared all detection matches")
    
    def get_match_count(self):
        """Get count of current matches
        
        Returns:
            Number of matches
        """
        with self.matches_lock:
            return len(self.detection_matches)

class MQTTService:
    """Service class for managing MQTT operations"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure only one MQTT service"""
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config=None):
        """Initialize MQTT service with configuration"""
        if not hasattr(self, 'initialized'):
            self.config = config or {}
            self.listener = None
            self.initialized = True
    
    def start_listener(self, host=None, port=None):
        """Start the MQTT detection listener
        
        Args:
            host: MQTT broker host (uses config default if not provided)
            port: MQTT broker port (uses config default if not provided)
            
        Returns:
            True if started successfully, False otherwise
        """
        if self.listener and self.listener.running:
            logger.warning("MQTT listener already running")
            return True
        
        mqtt_host = host or self.config.get('MQTT_HOST', 'localhost')
        mqtt_port = port or self.config.get('MQTT_PORT', 1883)
        
        self.listener = MQTTDetectionListener(mqtt_host, mqtt_port)
        return self.listener.start()
    
    def stop_listener(self):
        """Stop the MQTT detection listener"""
        if self.listener:
            self.listener.stop()
            self.listener = None
    
    def get_detection_matches(self):
        """Get current detection matches from listener
        
        Returns:
            List of detection matches or empty list if listener not running
        """
        if self.listener:
            return self.listener.get_matches()
        return []
    
    def clear_detection_matches(self):
        """Clear all detection matches"""
        if self.listener:
            self.listener.clear_matches()
    
    def get_match_count(self):
        """Get count of current matches
        
        Returns:
            Number of matches or 0 if listener not running
        """
        if self.listener:
            return self.listener.get_match_count()
        return 0
    
    def is_running(self):
        """Check if MQTT listener is running
        
        Returns:
            True if running, False otherwise
        """
        return self.listener and self.listener.running