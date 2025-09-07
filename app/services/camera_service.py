"""
Camera Service for RTSP Streaming and Camera Management
Handles camera proxy setup and RTSP forwarding
"""

import os
import re
import json
import logging
import subprocess
import requests
import threading
import signal
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class CameraService:
    """Service for managing camera streams and RTSP forwarding"""
    
    def __init__(self, config=None):
        """Initialize camera service with configuration"""
        self.config = config or {}
        
        # Configuration
        self.external_ip = self.config.get('EXTERNAL_IP', '24.147.52.91')
        self.frigate_host = self.config.get('FRIGATE_HOST', 'localhost:5000')
        
        # Port forwarding state
        self.rtsp_forwarding_active = False
        self.forwarding_process = None
        self.forwarding_ports = {}
        
        # Snapshot process management - ensure only one per camera
        self.snapshot_processes = {}  # camera_id -> process
        self.snapshot_lock = threading.Lock()
    
    def setup_rtsp_forwarding(self, local_rtsp_url, external_port=5554):
        """Set up RTSP stream forwarding for external access
        
        Args:
            local_rtsp_url: Local RTSP URL to forward
            external_port: External port to use for forwarding
            
        Returns:
            Dictionary with forwarding information or error
        """
        try:
            # Parse the RTSP URL to get components
            import urllib.parse
            parsed = urllib.parse.urlparse(local_rtsp_url)
            
            if parsed.scheme != 'rtsp':
                return {'error': 'Invalid RTSP URL'}
            
            # Create forwarding command using ffmpeg
            forwarding_url = f"rtsp://0.0.0.0:{external_port}/stream"
            
            cmd = [
                'ffmpeg',
                '-rtsp_transport', 'tcp',
                '-i', local_rtsp_url,
                '-c', 'copy',
                '-f', 'rtsp',
                '-rtsp_transport', 'tcp',
                forwarding_url
            ]
            
            # Start forwarding process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Store forwarding information
            stream_id = f"stream_{external_port}"
            self.forwarding_ports[stream_id] = {
                'process': process,
                'local_url': local_rtsp_url,
                'external_port': external_port,
                'external_url': f"rtsp://{self.external_ip}:{external_port}/stream",
                'started_at': datetime.now().isoformat()
            }
            
            logger.info(f"Started RTSP forwarding on port {external_port}")
            
            return {
                'success': True,
                'stream_id': stream_id,
                'external_url': self.forwarding_ports[stream_id]['external_url'],
                'external_port': external_port
            }
            
        except Exception as e:
            logger.error(f"Error setting up RTSP forwarding: {e}")
            return {'error': str(e)}
    
    def stop_rtsp_forwarding(self, stream_id):
        """Stop RTSP stream forwarding
        
        Args:
            stream_id: Stream ID to stop
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if stream_id in self.forwarding_ports:
                process = self.forwarding_ports[stream_id]['process']
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
                
                del self.forwarding_ports[stream_id]
                logger.info(f"Stopped RTSP forwarding for {stream_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error stopping RTSP forwarding: {e}")
        
        return False
    
    def get_forwarding_status(self):
        """Get status of all RTSP forwarding streams
        
        Returns:
            Dictionary with forwarding status information
        """
        status = {
            'active_streams': [],
            'total_streams': len(self.forwarding_ports)
        }
        
        for stream_id, info in self.forwarding_ports.items():
            process = info['process']
            is_running = process and process.poll() is None
            
            status['active_streams'].append({
                'stream_id': stream_id,
                'local_url': info['local_url'],
                'external_url': info['external_url'],
                'external_port': info['external_port'],
                'is_running': is_running,
                'started_at': info['started_at']
            })
        
        return status
    
    def test_camera_connection(self, camera_url):
        """Test connection to a camera
        
        Args:
            camera_url: Camera URL to test (HTTP or RTSP)
            
        Returns:
            Dictionary with test results
        """
        try:
            if camera_url.startswith('http'):
                # Test HTTP camera
                response = requests.get(camera_url, timeout=5)
                return {
                    'success': response.status_code == 200,
                    'status_code': response.status_code,
                    'type': 'http'
                }
                
            elif camera_url.startswith('rtsp'):
                # Test RTSP stream using ffprobe
                cmd = [
                    'ffprobe',
                    '-v', 'error',
                    '-rtsp_transport', 'tcp',
                    '-i', camera_url,
                    '-show_entries', 'stream=codec_name,width,height',
                    '-of', 'json',
                    '-timeout', '5000000'  # 5 seconds in microseconds
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    stream_info = json.loads(result.stdout)
                    return {
                        'success': True,
                        'type': 'rtsp',
                        'streams': stream_info.get('streams', [])
                    }
                else:
                    return {
                        'success': False,
                        'type': 'rtsp',
                        'error': result.stderr
                    }
                    
        except requests.Timeout:
            return {'success': False, 'error': 'Connection timeout'}
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'RTSP connection timeout'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_camera_snapshot(self, rtsp_url):
        """Get a snapshot from an RTSP camera
        
        Args:
            rtsp_url: RTSP URL of the camera
            
        Returns:
            Image data (bytes) or None if failed
        """
        import tempfile
        
        # Extract camera identifier from URL for process tracking
        parsed = urlparse(rtsp_url)
        camera_id = f"{parsed.hostname}:{parsed.port or 554}{parsed.path}"
        
        with self.snapshot_lock:
            # Check if there's already a snapshot process for this camera
            if camera_id in self.snapshot_processes:
                old_process = self.snapshot_processes[camera_id]
                if old_process and old_process.poll() is None:
                    # Kill the old hung process
                    logger.warning(f"Killing hung snapshot process for camera {camera_id}")
                    try:
                        old_process.kill()
                        old_process.wait(timeout=2)
                    except:
                        pass
                del self.snapshot_processes[camera_id]
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                cmd = [
                    'ffmpeg',
                    '-rtsp_transport', 'tcp',
                    '-i', rtsp_url,
                    '-vframes', '1',
                    '-q:v', '2',
                    '-y',
                    tmp_file.name
                ]
                
                # Use Popen to track the process
                with self.snapshot_lock:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    self.snapshot_processes[camera_id] = process
                
                try:
                    # Wait for process with timeout
                    stdout, stderr = process.communicate(timeout=10)
                    returncode = process.returncode
                except subprocess.TimeoutExpired:
                    # Process hung - kill it
                    logger.error(f"Snapshot process timed out for camera {camera_id}")
                    process.kill()
                    process.wait()
                    returncode = -1
                finally:
                    # Clean up process tracking
                    with self.snapshot_lock:
                        if camera_id in self.snapshot_processes:
                            del self.snapshot_processes[camera_id]
                
                # Read image if successful
                if returncode == 0 and os.path.exists(tmp_file.name):
                    with open(tmp_file.name, 'rb') as f:
                        image_data = f.read()
                    
                    os.unlink(tmp_file.name)
                    return image_data
                else:
                    # Clean up temp file on failure
                    if os.path.exists(tmp_file.name):
                        os.unlink(tmp_file.name)
                    logger.error(f"FFmpeg failed for camera {camera_id}: {stderr if returncode != -1 else 'timeout'}")
                    
        except Exception as e:
            logger.error(f"Error getting camera snapshot from {camera_id}: {e}")
            # Ensure process is cleaned up on exception
            with self.snapshot_lock:
                if camera_id in self.snapshot_processes:
                    try:
                        self.snapshot_processes[camera_id].kill()
                    except:
                        pass
                    del self.snapshot_processes[camera_id]
        
        return None
    
    def cleanup_snapshot_processes(self):
        """Clean up any remaining snapshot processes
        
        This should be called on service shutdown or periodically
        to ensure no zombie processes remain.
        """
        with self.snapshot_lock:
            for camera_id, process in list(self.snapshot_processes.items()):
                if process and process.poll() is None:
                    logger.warning(f"Cleaning up snapshot process for camera {camera_id}")
                    try:
                        process.kill()
                        process.wait(timeout=2)
                    except:
                        pass
            self.snapshot_processes.clear()
    
    def __del__(self):
        """Cleanup on service destruction"""
        try:
            self.cleanup_snapshot_processes()
            # Also clean up any forwarding processes
            for stream_id in list(self.forwarding_ports.keys()):
                self.stop_rtsp_forwarding(stream_id)
        except:
            pass
    
    def discover_cameras(self, network_range='192.168.0.0/24'):
        """Discover cameras on the network
        
        Args:
            network_range: Network range to scan (CIDR notation)
            
        Returns:
            List of discovered camera information
        """
        discovered = []
        
        try:
            # Use nmap or similar for discovery (simplified version)
            # In production, would use proper ONVIF discovery
            
            # Common camera ports
            camera_ports = [80, 554, 8080, 8554]
            
            # This is a simplified example - real implementation would use ONVIF
            logger.info(f"Camera discovery not fully implemented yet")
            
        except Exception as e:
            logger.error(f"Error discovering cameras: {e}")
        
        return discovered
    
    def create_camera_proxy(self, camera_name, camera_ip, camera_port=80, proxy_port=None):
        """Create nginx proxy configuration for a camera
        
        Args:
            camera_name: Name for the camera
            camera_ip: Camera IP address
            camera_port: Camera web interface port
            proxy_port: Local proxy port (auto-assigned if None)
            
        Returns:
            Dictionary with proxy information or error
        """
        try:
            # Find available proxy port if not specified
            if not proxy_port:
                used_ports = self.get_used_proxy_ports()
                for port in range(8100, 8200):
                    if port not in used_ports:
                        proxy_port = port
                        break
            
            if not proxy_port:
                return {'error': 'No available proxy ports'}
            
            # Create nginx configuration
            nginx_config = f"""
    # Camera: {camera_name} ({camera_ip})
    server {{
        listen {proxy_port};
        server_name localhost;
        
        location / {{
            proxy_pass http://{camera_ip}:{camera_port};
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_buffering off;
            
            # WebSocket support for live view
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }}
    }}
"""
            
            # Add to nginx configuration (simplified - would need proper integration)
            logger.info(f"Created camera proxy for {camera_name} on port {proxy_port}")
            
            return {
                'success': True,
                'camera_name': camera_name,
                'camera_ip': camera_ip,
                'proxy_port': proxy_port,
                'proxy_url': f"http://localhost:{proxy_port}"
            }
            
        except Exception as e:
            logger.error(f"Error creating camera proxy: {e}")
            return {'error': str(e)}
    
    def get_used_proxy_ports(self):
        """Get list of used proxy ports from nginx configuration
        
        Returns:
            Set of used port numbers
        """
        used_ports = set()
        
        try:
            nginx_config_path = '/home/andrew/nvr/nginx/nginx.conf'
            if os.path.exists(nginx_config_path):
                with open(nginx_config_path, 'r') as f:
                    content = f.read()
                
                # Find all listen directives
                import re
                matches = re.findall(r'listen\s+(\d+);', content)
                used_ports = set(int(port) for port in matches)
                
        except Exception as e:
            logger.error(f"Error getting used proxy ports: {e}")
        
        return used_ports
    
    def get_camera_list(self):
        """Get list of available camera names from Frigate
        
        Returns:
            List of camera names
        """
        try:
            from app.services.frigate_service import FrigateService
            frigate_service = FrigateService()
            return frigate_service.get_camera_names()
        except Exception as e:
            logger.error(f"Error getting camera list: {e}")
            return []
    
    def capture_snapshot(self, camera_name):
        """Capture HD snapshot from camera using Frigate API
        
        Args:
            camera_name: Name of the camera to capture from
            
        Returns:
            Dictionary with success status and image data
        """
        try:
            import base64
            
            # Use Frigate's snapshot API - construct URL
            frigate_url = f"http://{self.frigate_host}/api/{camera_name}/latest.jpg"
            
            # Make request to Frigate
            response = requests.get(frigate_url, timeout=10)
            
            if response.status_code == 200:
                # Convert image to base64 for consistency with expected format
                image_base64 = base64.b64encode(response.content).decode('utf-8')
                
                logger.info(f"Successfully captured snapshot from {camera_name}")
                return {
                    'success': True,
                    'image_data': f'data:image/jpeg;base64,{image_base64}'
                }
            else:
                logger.error(f"Failed to capture snapshot from {camera_name}: HTTP {response.status_code}")
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code} from Frigate API'
                }
                
        except requests.Timeout:
            logger.error(f"Timeout capturing snapshot from {camera_name}")
            return {
                'success': False,
                'error': 'Timeout connecting to Frigate'
            }
        except Exception as e:
            logger.error(f"Error capturing snapshot from {camera_name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }