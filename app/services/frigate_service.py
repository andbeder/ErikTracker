"""
Frigate Service for Camera Configuration Management
Handles Frigate config load/save and camera configuration
"""

import os
import re
import yaml
import shutil
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class FrigateService:
    """Service for managing Frigate configuration and cameras"""
    
    def __init__(self, config=None):
        """Initialize Frigate service with configuration"""
        self.config = config or {}
        
        # Configuration paths
        self.config_path = self.config.get('FRIGATE_CONFIG_PATH', '/home/andrew/nvr/frigate/config/config.yaml')
        self.backup_path = self.config.get('FRIGATE_CONFIG_BACKUP_PATH', '/home/andrew/nvr/frigate/config/backup_config.yaml')
        self.nginx_config_path = self.config.get('NGINX_CONFIG_PATH', '/home/andrew/nvr/nginx/nginx.conf')
        
        # Camera port mapping
        self.camera_port_mapping = {}
        self.load_camera_port_mapping()
    
    def load_config(self):
        """Load Frigate configuration from YAML file
        
        Returns:
            Configuration dictionary or None if error
        """
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading Frigate config: {e}")
            return None
    
    def save_config(self, config_data):
        """Save Frigate configuration to YAML file with backup
        
        Args:
            config_data: Configuration dictionary to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create backup first
            if os.path.exists(self.config_path):
                shutil.copy2(self.config_path, self.backup_path)
                logger.info("Created backup of Frigate config")
            
            # Save new config
            with open(self.config_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False, indent=2)
            logger.info("Saved Frigate configuration")
            return True
        except Exception as e:
            logger.error(f"Error saving Frigate config: {e}")
            return False
    
    def validate_camera_config(self, camera_data):
        """Validate camera configuration data
        
        Args:
            camera_data: Camera configuration dictionary
            
        Returns:
            Tuple of (is_valid, message)
        """
        required_fields = ['ffmpeg', 'detect']
        for field in required_fields:
            if field not in camera_data:
                return False, f"Missing required field: {field}"
        
        if 'inputs' not in camera_data['ffmpeg']:
            return False, "Missing ffmpeg inputs"
        
        return True, "Valid configuration"
    
    def extract_camera_ip(self, camera_config):
        """Extract IP address from camera RTSP URL
        
        Args:
            camera_config: Camera configuration dictionary
            
        Returns:
            Camera web URL or None if not found
        """
        try:
            if 'ffmpeg' in camera_config and 'inputs' in camera_config['ffmpeg']:
                for input_stream in camera_config['ffmpeg']['inputs']:
                    if 'path' in input_stream:
                        rtsp_url = input_stream['path']
                        # Parse RTSP URL like: rtsp://admin:hiver300@192.168.0.101:554/path
                        ip_match = re.search(r'@([0-9.]+):', rtsp_url)
                        if ip_match:
                            ip_address = ip_match.group(1)
                            return self.get_camera_web_url(ip_address)
        except Exception as e:
            logger.error(f"Error extracting camera IP: {e}")
        return None
    
    def get_camera_web_url(self, ip_address):
        """Map camera IP addresses to forwarded port URLs
        
        Args:
            ip_address: Camera IP address
            
        Returns:
            Web URL for camera access
        """
        if ip_address in self.camera_port_mapping:
            port = self.camera_port_mapping[ip_address]
            return f"http://localhost:{port}"
        
        # If not in mapping, try to auto-assign port
        assigned_port = self.auto_assign_camera_port(ip_address)
        if assigned_port:
            return f"http://localhost:{assigned_port}"
        
        # Fallback to direct IP
        return f"http://{ip_address}"
    
    def load_camera_port_mapping(self):
        """Load current camera-to-port mapping from nginx configuration"""
        mapping = {}
        try:
            with open(self.nginx_config_path, 'r') as f:
                content = f.read()
                
            # Parse nginx config to extract IP to port mappings
            # Match patterns like: listen 8101; ... proxy_pass http://192.168.0.101:80;
            pattern = r'listen (\d+);.*?proxy_pass http://([0-9.]+):80;'
            matches = re.findall(pattern, content, re.DOTALL)
            
            for port, ip in matches:
                mapping[ip] = port
                
        except Exception as e:
            logger.error(f"Error loading camera port mapping: {e}")
            # Return default mapping as fallback
            mapping = {
                '192.168.0.101': '8101',  # Front Door
                '192.168.0.102': '8102',  # Backyard  
                '192.168.0.103': '8103',  # Side Yard
                '192.168.0.104': '8104',  # Garage
            }
        
        self.camera_port_mapping = mapping
        return mapping
    
    def auto_assign_camera_port(self, ip_address):
        """Auto-assign a port for a camera IP address
        
        Args:
            ip_address: Camera IP address
            
        Returns:
            Assigned port number or None if failed
        """
        try:
            # Get list of used ports
            used_ports = set(int(port) for port in self.camera_port_mapping.values())
            
            # Find next available port in range 8100-8199
            for port in range(8100, 8200):
                if port not in used_ports:
                    # Add nginx configuration for this camera
                    if self.add_nginx_camera_proxy(ip_address, port):
                        self.camera_port_mapping[ip_address] = str(port)
                        logger.info(f"Auto-assigned port {port} to camera {ip_address}")
                        return port
                    
        except Exception as e:
            logger.error(f"Error auto-assigning camera port: {e}")
        
        return None
    
    def add_nginx_camera_proxy(self, ip_address, port):
        """Add nginx proxy configuration for a camera
        
        Args:
            ip_address: Camera IP address
            port: Port to use for proxy
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Read current nginx config
            with open(self.nginx_config_path, 'r') as f:
                content = f.read()
            
            # Check if configuration already exists
            if f"listen {port};" in content:
                logger.warning(f"Port {port} already configured in nginx")
                return False
            
            # Create new server block for camera
            new_server_block = f"""
    # Camera: {ip_address}
    server {{
        listen {port};
        location / {{
            proxy_pass http://{ip_address}:80;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_buffering off;
        }}
    }}
"""
            
            # Insert new server block before the last closing brace
            insert_pos = content.rfind('}')
            if insert_pos > 0:
                new_content = content[:insert_pos] + new_server_block + content[insert_pos:]
                
                # Backup and save
                backup_path = self.nginx_config_path + '.backup'
                shutil.copy2(self.nginx_config_path, backup_path)
                
                with open(self.nginx_config_path, 'w') as f:
                    f.write(new_content)
                
                # Reload nginx
                self.reload_nginx()
                logger.info(f"Added nginx proxy for {ip_address} on port {port}")
                return True
                
        except Exception as e:
            logger.error(f"Error adding nginx camera proxy: {e}")
        
        return False
    
    def reload_nginx(self):
        """Reload nginx configuration"""
        try:
            result = subprocess.run(
                ['docker', 'exec', 'nginx', 'nginx', '-s', 'reload'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info("Nginx configuration reloaded successfully")
                return True
            else:
                logger.error(f"Failed to reload nginx: {result.stderr}")
        except Exception as e:
            logger.error(f"Error reloading nginx: {e}")
        
        return False
    
    def get_camera_names(self):
        """Get list of configured camera names
        
        Returns:
            List of camera names
        """
        config = self.load_config()
        if config and 'cameras' in config:
            return list(config['cameras'].keys())
        return []
    
    def get_camera_config(self, camera_name):
        """Get configuration for a specific camera
        
        Args:
            camera_name: Name of the camera
            
        Returns:
            Camera configuration dictionary or None if not found
        """
        config = self.load_config()
        if config and 'cameras' in config:
            return config['cameras'].get(camera_name)
        return None
    
    def update_camera_config(self, camera_name, camera_data):
        """Update configuration for a specific camera
        
        Args:
            camera_name: Name of the camera
            camera_data: New camera configuration
            
        Returns:
            True if successful, False otherwise
        """
        config = self.load_config()
        if not config:
            return False
        
        if 'cameras' not in config:
            config['cameras'] = {}
        
        config['cameras'][camera_name] = camera_data
        return self.save_config(config)
    
    def delete_camera_config(self, camera_name):
        """Delete configuration for a specific camera
        
        Args:
            camera_name: Name of the camera to delete
            
        Returns:
            True if successful, False otherwise
        """
        config = self.load_config()
        if not config or 'cameras' not in config:
            return False
        
        if camera_name in config['cameras']:
            del config['cameras'][camera_name]
            return self.save_config(config)
        
        return False
    
    def restart_frigate(self):
        """Restart Frigate container
        
        Returns:
            True if successful, False otherwise
        """
        try:
            result = subprocess.run(
                ['docker', 'restart', 'frigate'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                logger.info("Frigate restarted successfully")
                return True
            else:
                logger.error(f"Failed to restart Frigate: {result.stderr}")
        except Exception as e:
            logger.error(f"Error restarting Frigate: {e}")
        
        return False