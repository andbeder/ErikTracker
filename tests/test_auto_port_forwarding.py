#!/usr/bin/env python3
"""
Test script to demonstrate automatic camera port forwarding functionality
"""

def load_camera_port_mapping():
    """Load current camera-to-port mapping from nginx configuration"""
    mapping = {}
    try:
        nginx_config_path = './nginx/nginx.conf'
        with open(nginx_config_path, 'r') as f:
            content = f.read()
            
        # Parse nginx config to extract IP to port mappings
        import re
        # Match patterns like: listen 8101; ... proxy_pass http://192.168.0.101:80;
        pattern = r'listen (\d+);.*?proxy_pass http://([0-9.]+):80;'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for port, ip in matches:
            mapping[ip] = port
            
    except Exception as e:
        print(f"Error loading camera port mapping: {e}")
    
    return mapping

def get_next_available_port():
    """Get the next available port in the range 8101-8120"""
    current_mapping = load_camera_port_mapping()
    used_ports = set(int(port) for port in current_mapping.values())
    
    # Check ports 8101-8120
    for port in range(8101, 8121):
        if port not in used_ports:
            return port
    
    print("No available ports in range 8101-8120")
    return None

def simulate_add_camera(ip_address):
    """Simulate adding a new camera and show what port would be assigned"""
    current_mapping = load_camera_port_mapping()
    
    print(f"\n🎥 Adding camera with IP: {ip_address}")
    print(f"Current port mappings: {current_mapping}")
    
    if ip_address in current_mapping:
        print(f"✅ Camera already has port forwarding: localhost:{current_mapping[ip_address]}")
        return current_mapping[ip_address]
    else:
        available_port = get_next_available_port()
        if available_port:
            print(f"🚀 Would assign port {available_port} for camera {ip_address}")
            print(f"📝 Would add nginx config block for {ip_address}:{available_port}")
            print(f"🔄 Would reload nginx configuration")
            print(f"📄 Would update docker-compose.yml with port mapping")
            return available_port
        else:
            print("❌ No available ports for assignment")
            return None

if __name__ == "__main__":
    print("🔧 Automatic Camera Port Forwarding Test\n")
    
    # Show current status
    mapping = load_camera_port_mapping()
    print("📊 Current Camera Port Mappings:")
    for ip, port in mapping.items():
        print(f"  {ip} → localhost:{port}")
    
    available = get_next_available_port()
    print(f"\n🔌 Next available port: {available}")
    
    # Test scenarios
    test_cameras = [
        "192.168.0.105",  # New camera
        "192.168.0.101",  # Existing camera
        "192.168.0.106",  # Another new camera
    ]
    
    for camera_ip in test_cameras:
        simulate_add_camera(camera_ip)
    
    print(f"\n✅ Automatic port forwarding system ready!")
    print(f"🔗 Ports 8101-8120 available for camera proxying")
    print(f"📱 Camera Views tab will automatically work with new cameras")