#!/usr/bin/env python3
"""
Test script to simulate Erik's shirt color detection and iPhone notification
"""

import json
import paho.mqtt.client as mqtt
from datetime import datetime
import time

def test_color_notification():
    """Send a test color notification via MQTT"""
    
    # MQTT setup (same as hybrid tracker)
    client = mqtt.Client()
    
    try:
        # Connect to MQTT broker
        client.connect("localhost", 1883, 60)
        client.loop_start()
        
        print("🧪 Testing Erik's Daily Shirt Color Notification System")
        print("=" * 60)
        
        # Test notification data
        test_color = "blue"
        test_hue = 110.0
        current_time = datetime.now().strftime("%I:%M %p")
        
        notification_message = {
            "title": "👕 Erik's Shirt Color Today",
            "message": f"Erik is wearing a {test_color} shirt (detected at {current_time})",
            "priority": "normal",
            "sound": "magic",  # Pushover sound
            "color_name": test_color,
            "hue": test_hue,
            "confidence": 0.95,
            "timestamp": datetime.now().isoformat()
        }
        
        daily_color_data = {
            "color_detected": test_color,
            "hue_value": test_hue,
            "face_confidence": 0.95,
            "timestamp": datetime.now().isoformat(),
            "notification_type": "daily_color_identification"
        }
        
        print(f"📱 Sending test notification for '{test_color}' shirt...")
        
        # Send notification to iPhone via MQTT
        result1 = client.publish("notifications/erik/color", json.dumps(notification_message))
        print(f"   Notification MQTT publish result: {result1.rc}")
        
        # Send data for Home Assistant logging
        result2 = client.publish("yard/erik/daily_color", json.dumps(daily_color_data))
        print(f"   Data logging MQTT publish result: {result2.rc}")
        
        print(f"\n✅ Test messages sent!")
        print(f"   Color: {test_color}")
        print(f"   Time: {current_time}")
        print(f"   Confidence: 95%")
        print(f"\n📲 Check your iPhone for push notification!")
        print(f"🏠 Check Home Assistant for automation trigger")
        
        # Wait a moment for message delivery
        time.sleep(2)
        
        # Test different colors
        test_colors = ["red", "green", "yellow", "purple"]
        
        print(f"\n🎨 Testing multiple colors (should only get ONE notification per day)...")
        for i, color in enumerate(test_colors):
            test_message = {
                "title": "👕 Erik's Shirt Color Today",
                "message": f"TEST: Erik is wearing a {color} shirt (test #{i+2})",
                "priority": "normal",
                "sound": "magic",
                "color_name": color,
                "hue": 30.0 + (i * 40),  # Different hues
                "confidence": 0.90 + (i * 0.02),
                "timestamp": datetime.now().isoformat()
            }
            
            client.publish("notifications/erik/color", json.dumps(test_message))
            print(f"   Sent test for {color} shirt")
            time.sleep(1)
        
        print(f"\n⚠️ Note: Real system only sends ONE notification per day")
        print(f"   (These are just test messages)")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    test_color_notification()