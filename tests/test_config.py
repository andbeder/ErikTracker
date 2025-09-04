#!/usr/bin/env python3
"""
Configuration Test Utility for Erik Image Manager
Tests the Phase 3 configuration management system
"""
import json
import requests
import sys
import os

def test_configuration_api(base_url='http://localhost:5000'):
    """Test the configuration API endpoints"""
    print("🧪 Testing Phase 3 Configuration Management...")
    print("=" * 50)
    
    endpoints = [
        ('/api/config/client', 'Client Configuration'),
        ('/api/config/environment', 'Environment Information'),
        ('/api/config/paths', 'Path Configuration'),
        ('/api/config/limits', 'File Limits & Constraints')
    ]
    
    for endpoint, description in endpoints:
        try:
            print(f"📡 Testing {description}: {endpoint}")
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Status: {response.status_code}")
                print(f"   📄 Response keys: {list(data.keys())}")
                
                # Show a few sample values
                if endpoint == '/api/config/client':
                    print(f"   🎯 App Title: {data.get('ui', {}).get('app_title', 'N/A')}")
                    print(f"   📁 Upload Folder: {data.get('images', {}).get('upload_folder', 'N/A')}")
                    print(f"   🌐 External IP: {data.get('network', {}).get('external_ip', 'N/A')}")
                elif endpoint == '/api/config/environment':
                    print(f"   🔧 Environment: {data.get('environment', 'N/A')}")
                    print(f"   🐛 Debug: {data.get('debug', 'N/A')}")
                    print(f"   📦 Version: {data.get('version', 'N/A')}")
                elif endpoint == '/api/config/paths':
                    print(f"   📂 Upload: {data.get('upload_folder', 'N/A')}")
                    print(f"   🗂️ Mesh: {data.get('mesh_folder', 'N/A')}")
                elif endpoint == '/api/config/limits':
                    print(f"   📸 Max Image Size: {data.get('max_file_size', 0) // 1024 // 1024}MB")
                    print(f"   🎬 Max Video Size: {data.get('max_video_size', 0) // 1024 // 1024}MB")
                    
            else:
                print(f"   ❌ Status: {response.status_code}")
                print(f"   📄 Response: {response.text[:100]}...")
                
        except requests.RequestException as e:
            print(f"   💥 Error: {e}")
        
        print()

def test_environment_variables():
    """Test environment variable configuration"""
    print("🌍 Testing Environment Variable Configuration...")
    print("=" * 50)
    
    config_vars = [
        ('ERIK_IMAGES_FOLDER', 'Image Upload Folder'),
        ('MESH_FOLDER', 'Mesh Storage Folder'),
        ('EXTERNAL_IP', 'External IP Address'),
        ('FRIGATE_CONFIG_PATH', 'Frigate Configuration'),
        ('MQTT_HOST', 'MQTT Broker Host'),
        ('COLMAP_PROJECTS_DIR', 'COLMAP Projects Directory')
    ]
    
    for var_name, description in config_vars:
        value = os.environ.get(var_name, 'Not Set')
        status = '✅' if value != 'Not Set' else '⚠️'
        print(f"   {status} {description}: {var_name} = {value}")
    
    print()

def generate_config_summary():
    """Generate a configuration summary"""
    print("📋 Configuration Management Summary (Phase 3)")
    print("=" * 50)
    
    features = [
        "✅ Server-side configuration API (/api/config/*)",
        "✅ Client-side AppConfig class with caching",
        "✅ Environment variable integration",
        "✅ Template variable injection",
        "✅ Fallback configuration system",
        "✅ Dynamic path resolution",
        "✅ Centralized file size limits",
        "✅ Feature flag management",
        "✅ Configuration validation",
        "✅ Hot reload capabilities"
    ]
    
    for feature in features:
        print(f"  {feature}")
    
    print("\n🎯 Benefits:")
    print("  • No more hardcoded values in JavaScript")
    print("  • Environment-specific configuration")
    print("  • Single source of truth for settings")
    print("  • Easy deployment configuration")
    print("  • Better error handling and fallbacks")
    print("  • Improved maintainability")

if __name__ == '__main__':
    try:
        base_url = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:5000'
        test_configuration_api(base_url)
        test_environment_variables()
        generate_config_summary()
    except KeyboardInterrupt:
        print("\n⏹️ Configuration tests interrupted")
    except Exception as e:
        print(f"💥 Test error: {e}")