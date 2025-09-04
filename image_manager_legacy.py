#!/usr/bin/env python3
"""
Erik Image Manager Web Interface
A Flask web app for managing Erik's reference images in the hybrid tracker
Runs on port 9000 with upload, delete, and preview functionality
"""

from flask import Flask, request, render_template, jsonify, send_from_directory, redirect, url_for, flash, session
import os
import sys
import logging
from pathlib import Path
from werkzeug.utils import secure_filename
from PIL import Image
import io
import base64
from datetime import datetime
import shutil
import paho.mqtt.client as mqtt
import json
import threading
import queue
import time
import yaml
from copy import deepcopy
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import subprocess
import tempfile
import requests
import uuid
import re
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'erik-image-manager-secret-key-change-in-production'

# Configuration
UPLOAD_FOLDER = os.getenv('ERIK_IMAGES_FOLDER', '/app/erik_images')
MESH_FOLDER = os.getenv('MESH_FOLDER', '/home/andrew/nvr/meshes')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp'}
MESH_EXTENSIONS = {'ply', 'obj', 'stl'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
THUMBNAIL_SIZE = (200, 200)
MATCH_THUMBNAIL_SIZE = (150, 150)

# External IP for camera access (with port forwarding 5000 -> 192.168.68.54:5000)
EXTERNAL_IP = os.getenv('EXTERNAL_IP', '24.147.52.91')  # Cable modem external IP

# Frigate Configuration
FRIGATE_CONFIG_PATH = os.getenv('FRIGATE_CONFIG_PATH', '/home/andrew/nvr/frigate/config/config.yaml')
FRIGATE_CONFIG_BACKUP_PATH = os.getenv('FRIGATE_CONFIG_BACKUP_PATH', '/home/andrew/nvr/frigate/config/backup_config.yaml')

# MQTT Configuration
MQTT_HOST = os.getenv('MQTT_HOST', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))

# Ensure upload folder exists
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
Path(MESH_FOLDER).mkdir(parents=True, exist_ok=True)

# Global storage for detection matches
detection_matches = []
matches_lock = threading.Lock()

# Global storage for COLMAP progress tracking
colmap_progress_sessions = {}
progress_lock = threading.Lock()

# Global progress state (visible to all clients)
global_progress_state = {
    'active': False,
    'current_phase': None,
    'progress': {},
    'completed': False,
    'project_dir': None,
    'session_id': None,
    'start_time': None,
    'last_updated': None
}
global_progress_lock = threading.Lock()

class MQTTDetectionListener:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.running = False
        
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT connected for detection monitoring")
            client.subscribe("yard/erik/detected/+")
        else:
            logger.error(f"MQTT connection failed: {rc}")
    
    def _on_message(self, client, userdata, msg):
        try:
            detection_data = json.loads(msg.payload.decode())
            camera = msg.topic.split('/')[-1]
            
            # Add camera name and timestamp
            detection_data['camera'] = camera
            detection_data['received_time'] = datetime.now().isoformat()
            
            with matches_lock:
                # Add to matches list (keep last 50)
                detection_matches.insert(0, detection_data)
                if len(detection_matches) > 50:
                    detection_matches.pop()
                    
            logger.info(f"Received Erik detection on {camera}: {detection_data.get('confidence', 0):.3f}")
            
        except Exception as e:
            logger.error(f"Error processing detection message: {e}")
    
    def start(self):
        try:
            self.client.connect(MQTT_HOST, MQTT_PORT, 60)
            self.running = True
            self.client.loop_start()
            logger.info(f"MQTT listener started on {MQTT_HOST}:{MQTT_PORT}")
        except Exception as e:
            logger.error(f"Failed to start MQTT listener: {e}")
    
    def stop(self):
        if self.running:
            self.client.loop_stop()
            self.client.disconnect()
            self.running = False

# Start MQTT listener
mqtt_listener = MQTTDetectionListener()
mqtt_listener.start()

class COLMAPProgressTracker:
    """Tracks COLMAP progress by parsing log output"""
    def __init__(self, session_id):
        self.session_id = session_id
        self.current_phase = None
        self.progress = {
            'feature_extraction': {'current': 0, 'total': 0, 'percent': 0},
            'feature_matching': {'current': 0, 'total': 0, 'percent': 0},
            'sparse_reconstruction': {'current': 0, 'total': 0, 'percent': 0},
            'dense_reconstruction': {'current': 0, 'total': 0, 'percent': 0}
        }
        self.process = None
        self.completed = False
        
    def parse_log_line(self, line_type, line_content):
        """Parse COLMAP log line and update progress"""
        if not line_content:
            return
            
        try:
            # COLMAP uses structured logging with timestamps like: I20250902 17:00:41.258980    25 timer.cc:91]
            # Feature extraction progress - look for actual COLMAP patterns
            if 'feature_extraction.cc' in line_content or 'sift.cc' in line_content:
                # COLMAP feature extraction patterns
                patterns = [
                    r'Processed file \[(\d+)/(\d+)\]',  # Main COLMAP pattern: "Processed file [1/33]"
                    r'Processed (\d+)/(\d+) images',
                    r'Extracting features \[(\d+)/(\d+)\]',
                    r'Features \[(\d+)/(\d+)\]',
                    r'Image (\d+) of (\d+)',
                    # Extract from thread-based processing
                    r'\] Creating SIFT.*extractor.*(\d+)',
                    r'\] (\d+) images.*processed',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, line_content)
                    if match:
                        if len(match.groups()) == 2:
                            # Pattern with current/total
                            current, total = int(match.group(1)), int(match.group(2))
                            self.progress['feature_extraction']['current'] = current
                            self.progress['feature_extraction']['total'] = total
                            self.progress['feature_extraction']['percent'] = min(100, int((current / total) * 100))
                        else:
                            # Pattern with just current
                            current = int(match.group(1))
                            self.progress['feature_extraction']['current'] = current
                            if self.progress['feature_extraction']['total'] > 0:
                                self.progress['feature_extraction']['percent'] = min(100, int(
                                    (current / self.progress['feature_extraction']['total']) * 100
                                ))
                        break
            
            # Also check for general processing indicators in COLMAP logs
            elif 'timer.cc' in line_content and 'Elapsed time' in line_content:
                # This indicates a phase completed - mark as 100% if we have any progress
                if self.current_phase == 'feature_extraction' and self.progress['feature_extraction']['current'] > 0:
                    self.progress['feature_extraction']['percent'] = 100
                        
            # Feature matching progress - COLMAP sequential matcher patterns
            elif ('pairing.cc' in line_content or 'feature_matching.cc' in line_content or 
                  'matcher.cc' in line_content or 'matching' in line_content.lower()):
                patterns = [
                    r'Matching image \[(\d+)/(\d+)\]',  # Main COLMAP pattern: "Matching image [1/126]"
                    r'Matched (\d+)/(\d+) image pairs',
                    r'Matching \[(\d+)/(\d+)\]',
                    r'Processed (\d+)/(\d+) pairs',
                    r'Sequential matching.*(\d+)/(\d+)',
                    r'Loop closure.*(\d+)/(\d+)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, line_content)
                    if match:
                        if len(match.groups()) == 2:
                            current, total = int(match.group(1)), int(match.group(2))
                            self.progress['feature_matching']['current'] = current
                            self.progress['feature_matching']['total'] = total
                            self.progress['feature_matching']['percent'] = min(100, int((current / total) * 100))
                        break
                        
            # Sparse reconstruction progress (incremental_pipeline.cc patterns)
            elif ('incremental_pipeline.cc' in line_content or 'Registering' in line_content or 
                  'Registered' in line_content or 'triangulat' in line_content.lower()):
                patterns = [
                    r'Registering image #(\d+) \(num_reg_frames=(\d+)\)',  # Current COLMAP output
                    r'Registered image #(\d+)',
                    r'Registered (\d+) images',
                    r'Triangulating (\d+)',
                    r'Images: (\d+)',
                    r'=> Registered images: (\d+)',
                    r'=> Added (\d+) observations',
                    r'=> Merged (\d+) observations',
                    r'=> Completed (\d+) observations',
                    r'Bundle adjustment converged'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, line_content)
                    if match:
                        if pattern == r'Bundle adjustment converged':
                            # Mark sparse reconstruction as nearly complete
                            self.progress['sparse_reconstruction']['percent'] = 95
                        elif pattern == r'Registering image #(\d+) \(num_reg_frames=(\d+)\)':
                            # Use num_reg_frames (second capture group) for current count
                            current = int(match.group(2))
                            self.progress['sparse_reconstruction']['current'] = current
                            if self.progress['sparse_reconstruction']['total'] > 0:
                                self.progress['sparse_reconstruction']['percent'] = min(100, int(
                                    (current / self.progress['sparse_reconstruction']['total']) * 100
                                ))
                        elif match.groups():
                            current = int(match.group(1))
                            self.progress['sparse_reconstruction']['current'] = current
                            if self.progress['sparse_reconstruction']['total'] > 0:
                                self.progress['sparse_reconstruction']['percent'] = min(100, int(
                                    (current / self.progress['sparse_reconstruction']['total']) * 100
                                ))
                        break
                        
            # Dense reconstruction progress (image_undistorter.cc, stereo patterns)
            elif ('image_undistorter.cc' in line_content or 'patch_match.cc' in line_content or 
                  'Depth' in line_content or 'Undistorting' in line_content or 'Stereo' in line_content):
                patterns = [
                    r'Depth map (\d+)/(\d+)',
                    r'Undistorting image (\d+)/(\d+)',
                    r'Processing (\d+)/(\d+)',
                    r'\[(\d+)/(\d+)\]',
                    r'=> Processed (\d+)/(\d+) images',
                    r'=> Undistorted (\d+)/(\d+) images',
                    r'=> Computed stereo for (\d+)/(\d+)',
                    r'=> Depth maps: (\d+)/(\d+)',
                    r'=> Normal maps: (\d+)/(\d+)'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, line_content)
                    if match:
                        if len(match.groups()) == 2:
                            current, total = int(match.group(1)), int(match.group(2))
                            self.progress['dense_reconstruction']['current'] = current
                            self.progress['dense_reconstruction']['total'] = total
                            self.progress['dense_reconstruction']['percent'] = min(100, int((current / total) * 100))
                        break
                        
            # Stereo fusion progress (final dense reconstruction phase)
            elif 'stereo_fusion.cc' in line_content or 'Fusing' in line_content:
                patterns = [
                    r'Fusing (\d+)/(\d+)',
                    r'=> Fused (\d+) points',
                    r'=> Filtered (\d+) points',
                    r'Processing depth map (\d+)/(\d+)',
                    r'Fusion completed'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, line_content)
                    if match:
                        if pattern == r'Fusion completed':
                            # Mark dense reconstruction as complete
                            self.progress['dense_reconstruction']['percent'] = 100
                        elif match.groups():
                            if len(match.groups()) == 2:
                                current, total = int(match.group(1)), int(match.group(2))
                                self.progress['dense_reconstruction']['current'] = current
                                self.progress['dense_reconstruction']['total'] = total
                                self.progress['dense_reconstruction']['percent'] = min(100, int((current / total) * 100))
                        break
                    
            # Extract total counts from initialization messages
            elif 'images' in line_content:
                patterns = [
                    r'Found (\d+) images',
                    r'Loading (\d+) images',
                    r'(\d+) images loaded',
                    r'Total images: (\d+)'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, line_content)
                    if match:
                        total_images = int(match.group(1))
                        if self.progress['feature_extraction']['total'] == 0:
                            self.progress['feature_extraction']['total'] = total_images
                        if self.progress['sparse_reconstruction']['total'] == 0:
                            self.progress['sparse_reconstruction']['total'] = total_images
                        break
                        
        except Exception as e:
            logger.error(f"Error parsing log line: {e}")

def update_global_progress(session_id=None):
    """Update global progress state from session tracker"""
    global global_progress_state
    try:
        with global_progress_lock:
            if session_id and session_id in colmap_progress_sessions:
                tracker = colmap_progress_sessions[session_id]
                global_progress_state.update({
                    'active': True,
                    'current_phase': tracker.current_phase,
                    'progress': tracker.progress.copy(),
                    'completed': tracker.completed,
                    'session_id': session_id,
                    'last_updated': time.time()
                })
            elif not session_id:
                # Clear global progress
                global_progress_state.update({
                    'active': False,
                    'current_phase': None,
                    'progress': {},
                    'completed': False,
                    'session_id': None,
                    'project_dir': None,
                    'last_updated': time.time()
                })
    except Exception as e:
        logger.error(f"Error updating global progress: {e}")

def get_global_progress():
    """Get current global progress state"""
    with global_progress_lock:
        return global_progress_state.copy()

def run_colmap_with_progress(cmd, session_id):
    """Run COLMAP command with progress tracking"""
    with progress_lock:
        if session_id not in colmap_progress_sessions:
            return None
            
        tracker = colmap_progress_sessions[session_id]
    
    def read_output_stream(process, tracker):
        """Read and parse subprocess output in real-time"""
        try:
            # Use select to read from both stdout and stderr simultaneously
            import select
            
            while process.poll() is None:
                # Check if data is available to read
                ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)
                
                for stream in ready:
                    line = stream.readline()
                    if line:
                        stream_name = 'stdout' if stream == process.stdout else 'stderr'
                        tracker.parse_log_line(stream_name, line.strip())
                        # Update global progress after parsing
                        update_global_progress(session_id)
                        logger.info(f"COLMAP {stream_name}: {line.strip()}")
            
            # Read any remaining output
            remaining_stdout = process.stdout.read()
            remaining_stderr = process.stderr.read()
            
            if remaining_stdout:
                for line in remaining_stdout.split('\n'):
                    if line.strip():
                        tracker.parse_log_line('stdout', line.strip())
                        logger.info(f"COLMAP stdout: {line.strip()}")
                        
            if remaining_stderr:
                for line in remaining_stderr.split('\n'):
                    if line.strip():
                        tracker.parse_log_line('stderr', line.strip())
                        logger.info(f"COLMAP stderr: {line.strip()}")
                        
        except Exception as e:
            logger.error(f"Error reading COLMAP output: {e}")
    
    try:
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        tracker.process = process
        
        # Start thread to read output
        output_thread = threading.Thread(
            target=read_output_stream, 
            args=(process, tracker), 
            daemon=True
        )
        output_thread.start()
        
        # Wait for process to complete
        return_code = process.wait()
        
        # Mark as completed
        tracker.completed = True
        
        return return_code == 0
        
    except Exception as e:
        logger.error(f"Error running COLMAP with progress: {e}")
        tracker.completed = True
        return False

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_image_info(filepath):
    """Get image information including size and thumbnail"""
    try:
        with Image.open(filepath) as img:
            # Create thumbnail
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            
            # Convert to base64 for web display
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG')
            thumbnail_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            # Get file stats
            stats = os.stat(filepath)
            
            return {
                'filename': os.path.basename(filepath),
                'size': stats.st_size,
                'size_mb': round(stats.st_size / (1024 * 1024), 2),
                'modified': datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'thumbnail': f"data:image/jpeg;base64,{thumbnail_base64}",
                'dimensions': f"{img.width}x{img.height}" if hasattr(img, 'width') else "Unknown"
            }
    except Exception as e:
        logger.error(f"Error processing image {filepath}: {e}")
        return None

def get_all_images():
    """Get information about all images in the upload folder"""
    images = []
    image_extensions = [f'*.{ext}' for ext in ALLOWED_EXTENSIONS]
    
    for ext in image_extensions:
        for image_path in Path(UPLOAD_FOLDER).glob(ext):
            if image_path.is_file():
                info = get_image_info(str(image_path))
                if info:
                    images.append(info)
    
    # Sort by modification date (newest first)
    images.sort(key=lambda x: x['modified'], reverse=True)
    return images

def load_frigate_config():
    """Load Frigate configuration from YAML file"""
    try:
        with open(FRIGATE_CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading Frigate config: {e}")
        return None

def save_frigate_config(config_data):
    """Save Frigate configuration to YAML file with backup"""
    try:
        # Create backup first
        if os.path.exists(FRIGATE_CONFIG_PATH):
            shutil.copy2(FRIGATE_CONFIG_PATH, FRIGATE_CONFIG_BACKUP_PATH)
            logger.info("Created backup of Frigate config")
        
        # Save new config
        with open(FRIGATE_CONFIG_PATH, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False, indent=2)
        logger.info("Saved Frigate configuration")
        return True
    except Exception as e:
        logger.error(f"Error saving Frigate config: {e}")
        return False

def validate_camera_config(camera_data):
    """Validate camera configuration data"""
    required_fields = ['ffmpeg', 'detect']
    for field in required_fields:
        if field not in camera_data:
            return False, f"Missing required field: {field}"
    
    if 'inputs' not in camera_data['ffmpeg']:
        return False, "Missing ffmpeg inputs"
    
    return True, "Valid configuration"

def extract_camera_ip(camera_config):
    """Extract IP address from camera RTSP URL and map to forwarded port"""
    try:
        if 'ffmpeg' in camera_config and 'inputs' in camera_config['ffmpeg']:
            for input_stream in camera_config['ffmpeg']['inputs']:
                if 'path' in input_stream:
                    rtsp_url = input_stream['path']
                    # Parse RTSP URL like: rtsp://admin:hiver300@192.168.0.101:554/path
                    import re
                    ip_match = re.search(r'@([0-9.]+):', rtsp_url)
                    if ip_match:
                        ip_address = ip_match.group(1)
                        return get_camera_web_url(ip_address)
    except Exception as e:
        logger.error(f"Error extracting camera IP: {e}")
    return None

def get_camera_web_url(ip_address):
    """Map camera IP addresses to forwarded port URLs with automatic port assignment"""
    # Load current port mapping from nginx config
    camera_port_mapping = load_camera_port_mapping()
    
    if ip_address in camera_port_mapping:
        port = camera_port_mapping[ip_address]
        return f"http://localhost:{port}"
    
    # If not in mapping, try to auto-assign port
    assigned_port = auto_assign_camera_port(ip_address)
    if assigned_port:
        return f"http://localhost:{assigned_port}"
    
    # Fallback to direct IP if auto-assignment fails
    return f"http://{ip_address}"

def load_camera_port_mapping():
    """Load current camera-to-port mapping from nginx configuration"""
    mapping = {}
    try:
        nginx_config_path = '/home/andrew/nvr/nginx/nginx.conf'
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
        logger.error(f"Error loading camera port mapping: {e}")
        # Return default mapping as fallback
        mapping = {
            '192.168.0.101': '8101',  # Front Door
            '192.168.0.102': '8102',  # Backyard  
            '192.168.0.103': '8103',  # Side Yard
            '192.168.0.104': '8104',  # Garage
        }
    
    return mapping

def get_next_available_port():
    """Get the next available port in the range 8101-8120"""
    current_mapping = load_camera_port_mapping()
    used_ports = set(int(port) for port in current_mapping.values())
    
    # Check ports 8101-8120
    for port in range(8101, 8121):
        if port not in used_ports:
            return port
    
    logger.warning("No available ports in range 8101-8120")
    return None

def auto_assign_camera_port(ip_address):
    """Automatically assign a port for a new camera and update nginx config"""
    try:
        available_port = get_next_available_port()
        if not available_port:
            logger.error(f"Cannot assign port for {ip_address}: no ports available")
            return None
            
        # Add to nginx configuration
        success = add_camera_to_nginx_config(ip_address, available_port)
        if success:
            # Reload nginx to apply changes
            reload_nginx_config()
            logger.info(f"Auto-assigned port {available_port} for camera {ip_address}")
            return available_port
        else:
            logger.error(f"Failed to update nginx config for {ip_address}:{available_port}")
            return None
            
    except Exception as e:
        logger.error(f"Error auto-assigning port for {ip_address}: {e}")
        return None

def add_camera_to_nginx_config(ip_address, port):
    """Add a new camera proxy configuration to nginx.conf"""
    try:
        nginx_config_path = '/home/andrew/nvr/nginx/nginx.conf'
        
        # Create the new server block
        server_block = f"""
    # Camera {ip_address} -> localhost:{port}
    server {{
        listen {port};
        server_name localhost;
        
        location / {{
            proxy_pass http://{ip_address}:80;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 10s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }}
    }}"""
        
        # Read current config
        with open(nginx_config_path, 'r') as f:
            config_content = f.read()
        
        # Insert the new server block before the closing brace
        insertion_point = config_content.rfind('}')
        if insertion_point != -1:
            new_config = (config_content[:insertion_point] + 
                          server_block + '\n' + 
                          config_content[insertion_point:])
            
            # Write updated config
            with open(nginx_config_path, 'w') as f:
                f.write(new_config)
            
            logger.info(f"Added nginx proxy config for {ip_address}:{port}")
            return True
        else:
            logger.error("Could not find insertion point in nginx config")
            return False
            
    except Exception as e:
        logger.error(f"Error adding camera to nginx config: {e}")
        return False

def reload_nginx_config():
    """Reload nginx configuration in the camera-proxy container"""
    try:
        # Send SIGHUP to nginx in the container to reload config
        result = subprocess.run([
            'docker', 'exec', 'camera-proxy', 'nginx', '-s', 'reload'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("Nginx configuration reloaded successfully")
            return True
        else:
            logger.error(f"Failed to reload nginx: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error reloading nginx config: {e}")
        return False

def update_docker_compose_ports(ip_address, port):
    """Update docker-compose.yml to expose the new camera port"""
    try:
        compose_path = '/home/andrew/nvr/docker-compose.yml'
        
        # Read current docker-compose.yml
        with open(compose_path, 'r') as f:
            compose_content = f.read()
        
        # Find the camera-proxy service ports section
        import re
        
        # Look for the camera-proxy ports section
        ports_pattern = r'(camera-proxy:.*?ports:\s*\n)((?:\s*-\s*"810\d:810\d".*\n)*)'
        match = re.search(ports_pattern, compose_content, re.DOTALL)
        
        if match:
            ports_section_start = match.group(1)
            existing_ports = match.group(2)
            new_port_line = f'      - "{port}:{port}"  # Camera {ip_address}\n'
            
            # Insert new port mapping
            new_ports_section = ports_section_start + existing_ports + new_port_line
            updated_content = compose_content.replace(match.group(0), new_ports_section)
            
            # Write updated docker-compose.yml
            with open(compose_path, 'w') as f:
                f.write(updated_content)
                
            logger.info(f"Added port mapping {port}:{port} to docker-compose.yml")
            return True
        else:
            logger.error("Could not find camera-proxy ports section in docker-compose.yml")
            return False
            
    except Exception as e:
        logger.error(f"Error updating docker-compose.yml: {e}")
        return False

def get_mesh_files():
    """Get list of available mesh files"""
    mesh_files = []
    for ext in MESH_EXTENSIONS:
        for mesh_path in Path(MESH_FOLDER).glob(f'*.{ext}'):
            if mesh_path.is_file():
                stats = os.stat(mesh_path)
                mesh_files.append({
                    'filename': mesh_path.name,
                    'path': str(mesh_path),
                    'size': stats.st_size,
                    'size_mb': round(stats.st_size / (1024 * 1024), 2),
                    'modified': datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
    
    # Sort by modification date (newest first)
    mesh_files.sort(key=lambda x: x['modified'], reverse=True)
    return mesh_files

def generate_yard_map(mesh_path, grid_resolution=0.1, max_points=50000, point_size=0.1, projection='xy'):
    """Generate yard map from mesh file"""
    try:
        # Determine script path and Python executable - works in both container and development
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, 'fast_yard_map.py')
        
        # Use the current Python executable (works with venv)
        python_executable = sys.executable
        
        cmd = [
            python_executable, script_path, mesh_path,
            '--max-points', str(max_points),
            '--point-size', str(point_size),
            '--grid-resolution', str(grid_resolution),
            '--projection', projection
        ]
            
        # Create temporary output file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            cmd.extend(['--output', tmp_file.name])
            
            logger.info(f"Running yard map generation: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                # Read the generated image
                with open(tmp_file.name, 'rb') as f:
                    image_data = f.read()
                
                # Clean up temp file
                os.unlink(tmp_file.name)
                
                return image_data, result.stdout
            else:
                logger.error(f"Yard map generation failed: {result.stderr}")
                return None, result.stderr
                
    except subprocess.TimeoutExpired:
        logger.error("Yard map generation timed out")
        return None, "Generation timed out after 2 minutes"
    except Exception as e:
        logger.error(f"Error generating yard map: {e}")
        return None, str(e)

def generate_raster_yard_map(mesh_path, grid_resolution=0.1, max_points=20000000, projection='xy', height_window=0.5, custom_bounds=None, coloring='true_color', output_width=1280, output_height=720, rotation=0):
    """Generate rasterized yard map using height-optimized algorithm with rotation support"""
    try:
        # Determine script path and Python executable  
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Try CUDA version first, fall back to CPU if not available
        cuda_script_path = os.path.join(script_dir, 'fast_yard_map_cuda.py')
        cpu_script_path = os.path.join(script_dir, 'fast_yard_map_height_optimized.py')
        
        # Check if CUDA version is available and working
        script_path = cpu_script_path  # Default to CPU
        try:
            import cupy as cp
            import numba.cuda as cuda
            if cuda.is_available() and os.path.exists(cuda_script_path):
                script_path = cuda_script_path
                logger.info("Using CUDA-accelerated yard map generation")
            else:
                logger.info("CUDA not available, using CPU version")
        except ImportError:
            logger.info("CUDA libraries not installed, using CPU version")
        
        python_executable = sys.executable
        
        cmd = [
            python_executable, script_path, mesh_path,
            '--max-points', str(max_points),
            '--grid-resolution', str(grid_resolution),
            '--height-window', str(height_window),
            '--coloring', coloring,
            '--projection', projection,
            '--output-width', str(output_width),
            '--output-height', str(output_height)
        ]
        
        # Add custom bounds if provided
        if custom_bounds:
            bounds_str = f"{custom_bounds[0]},{custom_bounds[1]},{custom_bounds[2]},{custom_bounds[3]}"
            cmd.append(f'--bounds={bounds_str}')
        
        # Add rotation if specified
        if rotation != 0:
            cmd.append(f'--rotation={rotation}')
            
        # Create temporary output file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            cmd.extend(['--output', tmp_file.name])
            
            logger.info(f"Running rasterized yard map generation: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)  # 3 minutes for rasterization
            
            if result.returncode == 0:
                # Read the generated image (already 640x360)
                with open(tmp_file.name, 'rb') as f:
                    image_data = f.read()
                
                # Clean up temp file
                os.unlink(tmp_file.name)
                
                return image_data, result.stdout
            else:
                logger.error(f"Rasterized yard map generation failed: {result.stderr}")
                return None, result.stderr
                
    except subprocess.TimeoutExpired:
        logger.error("Rasterized yard map generation timed out")
        return None, "Generation timed out after 3 minutes"
    except Exception as e:
        logger.error(f"Error generating rasterized yard map: {e}")
        return None, str(e)

@app.route('/')
def index():
    """Main page showing Erik images and matches"""
    images = get_all_images()
    total_size_mb = sum(img['size'] for img in images) / (1024 * 1024)
    
    # Get recent matches
    with matches_lock:
        recent_matches = detection_matches[:20]  # Last 20 matches
    
    # Load Frigate config for display
    frigate_config = load_frigate_config()
    
    # Extract camera web URLs for interface links (via port forwarding)
    camera_urls = {}
    if frigate_config and 'cameras' in frigate_config:
        for camera_name, camera_config in frigate_config['cameras'].items():
            camera_url = extract_camera_ip(camera_config)
            if camera_url:
                camera_urls[camera_name] = camera_url
    
    # Get mesh files for yard mapping
    mesh_files = get_mesh_files()
    
    return render_template('index.html', 
                         images=images, 
                         total_images=len(images),
                         total_size_mb=round(total_size_mb, 2),
                         matches=recent_matches,
                         total_matches=len(detection_matches),
                         frigate_config=frigate_config,
                         camera_urls=camera_urls,
                         mesh_files=mesh_files)

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('index'))
    
    files = request.files.getlist('file')
    uploaded_count = 0
    errors = []
    
    for file in files:
        if file.filename == '':
            continue
            
        if file and allowed_file(file.filename):
            try:
                # Secure the filename
                filename = secure_filename(file.filename)
                
                # Add timestamp if file exists
                filepath = Path(UPLOAD_FOLDER) / filename
                if filepath.exists():
                    name, ext = os.path.splitext(filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{name}_{timestamp}{ext}"
                    filepath = Path(UPLOAD_FOLDER) / filename
                
                # Check file size
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > MAX_FILE_SIZE:
                    errors.append(f"{file.filename}: File too large (max 16MB)")
                    continue
                
                # Save file
                file.save(str(filepath))
                
                # Validate it's actually an image
                try:
                    with Image.open(str(filepath)) as img:
                        img.verify()
                    uploaded_count += 1
                    logger.info(f"Uploaded image: {filename}")
                except Exception as e:
                    os.remove(str(filepath))  # Remove invalid image
                    errors.append(f"{file.filename}: Not a valid image file")
                    
            except Exception as e:
                errors.append(f"{file.filename}: Upload failed - {str(e)}")
        else:
            errors.append(f"{file.filename}: Invalid file type")
    
    if uploaded_count > 0:
        flash(f'Successfully uploaded {uploaded_count} image(s)', 'success')
    
    for error in errors:
        flash(error, 'error')
    
    return redirect(url_for('index'))

@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    """Delete a specific image"""
    try:
        # Secure the filename
        secure_name = secure_filename(filename)
        filepath = Path(UPLOAD_FOLDER) / secure_name
        
        if filepath.exists() and filepath.is_file():
            os.remove(str(filepath))
            flash(f'Deleted {filename}', 'success')
            logger.info(f"Deleted image: {filename}")
        else:
            flash(f'File {filename} not found', 'error')
            
    except Exception as e:
        flash(f'Error deleting {filename}: {str(e)}', 'error')
        logger.error(f"Error deleting {filename}: {e}")
    
    return redirect(url_for('index'))

@app.route('/delete_all', methods=['POST'])
def delete_all():
    """Delete all images"""
    try:
        images = get_all_images()
        deleted_count = 0
        
        for image in images:
            filepath = Path(UPLOAD_FOLDER) / image['filename']
            if filepath.exists():
                os.remove(str(filepath))
                deleted_count += 1
        
        flash(f'Deleted {deleted_count} images', 'success')
        logger.info(f"Deleted all images: {deleted_count} files")
        
    except Exception as e:
        flash(f'Error deleting images: {str(e)}', 'error')
        logger.error(f"Error deleting all images: {e}")
    
    return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_file(filename):
    """Download a specific image"""
    try:
        secure_name = secure_filename(filename)
        return send_from_directory(UPLOAD_FOLDER, secure_name, as_attachment=True)
    except Exception as e:
        flash(f'Error downloading {filename}: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/images')
def api_images():
    """API endpoint to get image list as JSON"""
    images = get_all_images()
    return jsonify({
        'images': images,
        'total_count': len(images),
        'total_size_mb': round(sum(img['size'] for img in images) / (1024 * 1024), 2)
    })

@app.route('/api/matches')
def api_matches():
    """API endpoint to get detection matches as JSON"""
    with matches_lock:
        matches = detection_matches[:50]  # Last 50 matches
    
    return jsonify({
        'matches': matches,
        'total_count': len(detection_matches)
    })

@app.route('/api/matches/clear', methods=['POST'])
def clear_matches():
    """Clear all detection matches"""
    with matches_lock:
        detection_matches.clear()
    
    flash('Cleared all detection matches', 'success')
    return jsonify({'status': 'success'})

@app.route('/api/status')
def api_status():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'upload_folder': UPLOAD_FOLDER,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/frigate/config')
def frigate_config():
    """API endpoint to get Frigate configuration"""
    config = load_frigate_config()
    if config:
        return jsonify(config)
    else:
        return jsonify({'error': 'Could not load configuration'}), 500

@app.route('/frigate/config/camera/<camera_name>')
def get_camera_config(camera_name):
    """Get configuration for a specific camera"""
    config = load_frigate_config()
    if not config or 'cameras' not in config:
        return jsonify({'error': 'Configuration not found'}), 404
    
    if camera_name not in config['cameras']:
        return jsonify({'error': f'Camera {camera_name} not found'}), 404
    
    return jsonify(config['cameras'][camera_name])

@app.route('/frigate/config/camera/<camera_name>', methods=['POST'])
def update_camera_config(camera_name):
    """Update configuration for a specific camera"""
    try:
        camera_data = request.json
        if not camera_data:
            flash('No configuration data provided', 'error')
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate camera configuration
        is_valid, message = validate_camera_config(camera_data)
        if not is_valid:
            flash(f'Invalid configuration: {message}', 'error')
            return jsonify({'error': message}), 400
        
        # Load current config
        config = load_frigate_config()
        if not config:
            flash('Could not load current configuration', 'error')
            return jsonify({'error': 'Could not load configuration'}), 500
        
        # Update camera config
        if 'cameras' not in config:
            config['cameras'] = {}
        
        config['cameras'][camera_name] = camera_data
        
        # Save updated config
        if save_frigate_config(config):
            flash(f'Updated camera {camera_name} configuration', 'success')
            return jsonify({'status': 'success', 'message': f'Camera {camera_name} updated'})
        else:
            flash('Failed to save configuration', 'error')
            return jsonify({'error': 'Failed to save configuration'}), 500
            
    except Exception as e:
        logger.error(f"Error updating camera config: {e}")
        flash(f'Error updating camera: {str(e)}', 'error')
        return jsonify({'error': str(e)}), 500

@app.route('/frigate/config/global', methods=['POST'])
def update_global_config():
    """Update global Frigate configuration settings"""
    try:
        global_data = request.json
        if not global_data:
            flash('No configuration data provided', 'error')
            return jsonify({'error': 'No data provided'}), 400
        
        # Load current config
        config = load_frigate_config()
        if not config:
            flash('Could not load current configuration', 'error')
            return jsonify({'error': 'Could not load configuration'}), 500
        
        # Update global settings (preserve cameras and other sections)
        allowed_global_keys = ['mqtt', 'detectors', 'model', 'record', 'snapshots', 'objects', 'live', 'birdseye', 'logger', 'detect']
        
        for key, value in global_data.items():
            if key in allowed_global_keys:
                config[key] = value
        
        # Save updated config
        if save_frigate_config(config):
            flash('Updated global configuration', 'success')
            return jsonify({'status': 'success', 'message': 'Global configuration updated'})
        else:
            flash('Failed to save configuration', 'error')
            return jsonify({'error': 'Failed to save configuration'}), 500
            
    except Exception as e:
        logger.error(f"Error updating global config: {e}")
        flash(f'Error updating global configuration: {str(e)}', 'error')
        return jsonify({'error': str(e)}), 500

@app.route('/frigate/config/backup', methods=['POST'])
def create_backup():
    """Create manual backup of current Frigate configuration"""
    try:
        if not os.path.exists(FRIGATE_CONFIG_PATH):
            flash('No configuration file found to backup', 'error')
            return redirect(url_for('index'))
        
        # Create timestamped backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        timestamped_backup = f"{FRIGATE_CONFIG_BACKUP_PATH}_{timestamp}"
        
        # Copy current config to both locations
        shutil.copy2(FRIGATE_CONFIG_PATH, FRIGATE_CONFIG_BACKUP_PATH)
        shutil.copy2(FRIGATE_CONFIG_PATH, timestamped_backup)
        
        flash(f'Configuration backup created successfully', 'success')
        logger.info(f"Created Frigate config backup: {timestamped_backup}")
        
        return redirect(url_for('index'))
        
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        flash(f'Error creating backup: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/frigate/config/backup/restore')
def restore_backup():
    """Restore Frigate configuration from backup"""
    try:
        if not os.path.exists(FRIGATE_CONFIG_BACKUP_PATH):
            flash('No backup file found', 'error')
            return redirect(url_for('index'))
        
        # Copy backup to main config
        shutil.copy2(FRIGATE_CONFIG_BACKUP_PATH, FRIGATE_CONFIG_PATH)
        flash('Configuration restored from backup', 'success')
        logger.info("Restored Frigate config from backup")
        
        return redirect(url_for('index'))
        
    except Exception as e:
        logger.error(f"Error restoring backup: {e}")
        flash(f'Error restoring backup: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/frigate/config/camera', methods=['POST'])
def add_camera():
    """Add a new camera to Frigate configuration"""
    try:
        data = request.json
        camera_name = data.get('camera_name', '').strip()
        camera_config = data.get('camera_config', {})
        
        if not camera_name:
            flash('Camera name is required', 'error')
            return jsonify({'error': 'Camera name is required'}), 400
            
        # Validate camera configuration
        is_valid, message = validate_camera_config(camera_config)
        if not is_valid:
            flash(f'Invalid camera configuration: {message}', 'error')
            return jsonify({'error': message}), 400
        
        # Load current config
        config = load_frigate_config()
        if not config:
            flash('Could not load current configuration', 'error')
            return jsonify({'error': 'Could not load configuration'}), 500
        
        # Check if camera already exists
        if 'cameras' not in config:
            config['cameras'] = {}
            
        if camera_name in config['cameras']:
            flash(f'Camera {camera_name} already exists', 'error')
            return jsonify({'error': f'Camera {camera_name} already exists'}), 400
        
        # Add new camera
        config['cameras'][camera_name] = camera_config
        
        # Save updated config
        if save_frigate_config(config):
            # Try to set up automatic port forwarding for the new camera
            try:
                camera_ip = extract_camera_ip(camera_config)
                if camera_ip and camera_ip != f"http://{camera_ip}":  # Avoid infinite recursion
                    ip_match = camera_ip.replace('http://', '').replace('https://', '')
                    # Extract just the IP address
                    import re
                    ip_search = re.search(r'([0-9.]+)', ip_match)
                    if ip_search:
                        ip_addr = ip_search.group(1)
                        assigned_port = auto_assign_camera_port(ip_addr)
                        if assigned_port:
                            # Also update docker-compose.yml for persistent port mapping
                            update_docker_compose_ports(ip_addr, assigned_port)
                            flash(f'Added camera {camera_name} with port forwarding on port {assigned_port}', 'success')
                        else:
                            flash(f'Added camera {camera_name} (port forwarding setup failed)', 'warning')
                    else:
                        flash(f'Added camera {camera_name} (could not extract IP for port forwarding)', 'success')
                else:
                    flash(f'Added camera {camera_name} successfully', 'success')
            except Exception as e:
                logger.warning(f"Could not set up port forwarding for {camera_name}: {e}")
                flash(f'Added camera {camera_name} (port forwarding setup failed)', 'warning')
            
            logger.info(f"Added new camera: {camera_name}")
            return jsonify({'status': 'success', 'message': f'Camera {camera_name} added'})
        else:
            flash('Failed to save configuration', 'error')
            return jsonify({'error': 'Failed to save configuration'}), 500
            
    except Exception as e:
        logger.error(f"Error adding camera: {e}")
        flash(f'Error adding camera: {str(e)}', 'error')
        return jsonify({'error': str(e)}), 500

@app.route('/frigate/config/camera/<camera_name>', methods=['DELETE'])
def remove_camera(camera_name):
    """Remove a camera from Frigate configuration"""
    try:
        # Load current config
        config = load_frigate_config()
        if not config or 'cameras' not in config:
            flash('Configuration not found', 'error')
            return jsonify({'error': 'Configuration not found'}), 404
        
        if camera_name not in config['cameras']:
            flash(f'Camera {camera_name} not found', 'error')
            return jsonify({'error': f'Camera {camera_name} not found'}), 404
        
        # Remove camera from config
        del config['cameras'][camera_name]
        
        # Also remove from go2rtc streams if present
        if 'go2rtc' in config and 'streams' in config['go2rtc']:
            streams_to_remove = []
            for stream_name in config['go2rtc']['streams']:
                if stream_name.startswith(f"{camera_name}_"):
                    streams_to_remove.append(stream_name)
            
            for stream_name in streams_to_remove:
                del config['go2rtc']['streams'][stream_name]
        
        # Save updated config
        if save_frigate_config(config):
            flash(f'Removed camera {camera_name} successfully', 'success')
            logger.info(f"Removed camera: {camera_name}")
            return jsonify({'status': 'success', 'message': f'Camera {camera_name} removed'})
        else:
            flash('Failed to save configuration', 'error')
            return jsonify({'error': 'Failed to save configuration'}), 500
            
    except Exception as e:
        logger.error(f"Error removing camera: {e}")
        flash(f'Error removing camera: {str(e)}', 'error')
        return jsonify({'error': str(e)}), 500

@app.route('/api/yard-map/scan-bounds', methods=['POST'])
def scan_mesh_bounds():
    """Scan mesh file to get 2-98 percentile boundaries for the selected projection"""
    try:
        data = request.json
        mesh_file = data.get('mesh_file')
        projection = data.get('projection', 'xy')  # Get projection from request
        
        if not mesh_file:
            return jsonify({'success': False, 'error': 'No mesh file specified'}), 400
        
        # Handle mesh file paths - could be in MESH_FOLDER or COLMAP project directory
        if mesh_file.startswith('current_reconstruction/'):
            # Mesh from COLMAP reconstruction
            mesh_path = os.path.join(COLMAP_PROJECT_DIR, mesh_file)
        else:
            # Traditional mesh file
            mesh_path = os.path.join(MESH_FOLDER, mesh_file)
            
        if not os.path.exists(mesh_path):
            return jsonify({'success': False, 'error': f'Mesh file not found: {mesh_path}'}), 404
        
        # Import trimesh for loading the mesh
        try:
            import trimesh
            import numpy as np
        except ImportError:
            return jsonify({'success': False, 'error': 'Trimesh library not available'}), 500
        
        # Load mesh and get vertices
        logger.info(f"Scanning boundaries for mesh: {mesh_file} with projection: {projection}")
        mesh = trimesh.load(mesh_path)
        vertices = mesh.vertices
        
        # Calculate 2-98 percentile bounds for all axes
        x_bounds = np.percentile(vertices[:, 0], [2, 98])
        y_bounds = np.percentile(vertices[:, 1], [2, 98])
        z_bounds = np.percentile(vertices[:, 2], [2, 98])
        
        # Select bounds based on projection
        if projection == 'xy':
            axis1_bounds = x_bounds
            axis2_bounds = y_bounds
            axis1_label = 'X'
            axis2_label = 'Y'
            logger.info(f"Scanned bounds: X=[{axis1_bounds[0]:.2f}, {axis1_bounds[1]:.2f}], Y=[{axis2_bounds[0]:.2f}, {axis2_bounds[1]:.2f}]")
        elif projection == 'xz':
            axis1_bounds = x_bounds
            axis2_bounds = z_bounds
            axis1_label = 'X'
            axis2_label = 'Z'
            logger.info(f"Scanned bounds: X=[{axis1_bounds[0]:.2f}, {axis1_bounds[1]:.2f}], Z=[{axis2_bounds[0]:.2f}, {axis2_bounds[1]:.2f}]")
        elif projection == 'yz':
            axis1_bounds = y_bounds
            axis2_bounds = z_bounds
            axis1_label = 'Y'
            axis2_label = 'Z'
            logger.info(f"Scanned bounds: Y=[{axis1_bounds[0]:.2f}, {axis1_bounds[1]:.2f}], Z=[{axis2_bounds[0]:.2f}, {axis2_bounds[1]:.2f}]")
        else:
            return jsonify({'success': False, 'error': f'Invalid projection: {projection}'}), 400
        
        # Return the bounds with axis labels
        bounds = {
            'axis1_min': float(axis1_bounds[0]),
            'axis1_max': float(axis1_bounds[1]),
            'axis2_min': float(axis2_bounds[0]),
            'axis2_max': float(axis2_bounds[1]),
            'axis1_label': axis1_label,
            'axis2_label': axis2_label,
            # Keep legacy fields for compatibility
            'x_min': float(axis1_bounds[0]),
            'x_max': float(axis1_bounds[1]),
            'y_min': float(axis2_bounds[0]),
            'y_max': float(axis2_bounds[1]),
            'z_min': float(z_bounds[0]),
            'z_max': float(z_bounds[1])
        }
        
        return jsonify({
            'success': True,
            'bounds': bounds,
            'total_points': len(vertices),
            'percentile': '2-98',
            'projection': projection
        })
        
    except Exception as e:
        logger.error(f"Error scanning mesh bounds: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/yard-map/generate', methods=['POST'])
def generate_yard_map_api():
    """Generate height-optimized yard map from mesh file"""
    try:
        data = request.json
        mesh_file = data.get('mesh_file')
        grid_resolution = data.get('grid_resolution', 0.1)
        max_points = data.get('max_points', 50000)
        height_window = data.get('height_window', 0.5)
        coloring = data.get('coloring', 'true_color')
        projection = data.get('projection', 'xy')
        custom_bounds = data.get('custom_bounds')  # [x_min, x_max, y_min, y_max]
        rotation = data.get('rotation', 0)  # Rotation angle in degrees
        
        if not mesh_file:
            return jsonify({'error': 'No mesh file specified'}), 400
        
        # Handle mesh file paths - could be in MESH_FOLDER or COLMAP project directory
        if mesh_file.startswith('current_reconstruction/'):
            # Mesh from COLMAP reconstruction
            mesh_path = Path(COLMAP_PROJECT_DIR) / mesh_file
        else:
            # Traditional mesh file
            mesh_path = Path(MESH_FOLDER) / mesh_file
            
        if not mesh_path.exists() or not mesh_path.is_file():
            return jsonify({'error': 'Mesh file not found'}), 404
        
        # Generate height-optimized yard map
        image_data, output = generate_raster_yard_map(
            str(mesh_path), grid_resolution, max_points, projection, height_window, custom_bounds, coloring,
            1280, 720, rotation
        )
        
        if image_data:
            # Convert to base64 for JSON response
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            return jsonify({
                'status': 'success',
                'image': f'data:image/png;base64,{image_b64}',
                'log': output
            })
        else:
            return jsonify({'error': output}), 500
            
    except Exception as e:
        logger.error(f"Error in rasterized yard map API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/yard-map/download', methods=['POST'])
def download_yard_map():
    """Download height-optimized yard map as PNG"""
    try:
        data = request.json
        mesh_file = data.get('mesh_file')
        grid_resolution = data.get('grid_resolution', 0.1)
        max_points = data.get('max_points', 50000)
        height_window = data.get('height_window', 0.5)
        coloring = data.get('coloring', 'true_color')
        projection = data.get('projection', 'xy')
        custom_bounds = data.get('custom_bounds')  # [x_min, x_max, y_min, y_max]
        rotation = data.get('rotation', 0)  # Rotation angle in degrees
        
        if not mesh_file:
            return jsonify({'error': 'No mesh file specified'}), 400
        
        # Handle mesh file paths - could be in MESH_FOLDER or COLMAP project directory
        if mesh_file.startswith('current_reconstruction/'):
            # Mesh from COLMAP reconstruction
            mesh_path = Path(COLMAP_PROJECT_DIR) / mesh_file
        else:
            # Traditional mesh file
            mesh_path = Path(MESH_FOLDER) / mesh_file
            
        if not mesh_path.exists() or not mesh_path.is_file():
            return jsonify({'error': 'Mesh file not found'}), 404
        
        # Generate height-optimized yard map
        image_data, output = generate_raster_yard_map(
            str(mesh_path), grid_resolution, max_points, projection, height_window, custom_bounds, coloring,
            1280, 720, rotation
        )
        
        if image_data:
            # Create filename with parameters 
            grid_suffix = f"_grid{grid_resolution}m" if grid_resolution != 0.1 else ""
            view_suffix = f"_{projection}" if projection != 'xy' else ""
            filename = f"erik_yard_{Path(mesh_file).stem}{grid_suffix}{view_suffix}.png"
            
            # Return as file download
            response = app.response_class(
                image_data,
                mimetype='image/png',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
            return response
        else:
            return jsonify({'error': output}), 500
            
    except Exception as e:
        logger.error(f"Error in yard map download: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/yard-map/use', methods=['POST'])
def use_yard_map():
    """Save the generated rasterized map as the active yard map for tracking"""
    try:
        data = request.json
        mesh_file = data.get('mesh_file')
        grid_resolution = data.get('grid_resolution', 0.1)
        max_points = data.get('max_points', 50000)
        projection = data.get('projection', 'xy')
        rotation = data.get('rotation', 0)
        
        if not mesh_file:
            return jsonify({'error': 'No mesh file specified'}), 400
        
        # Handle mesh file paths - could be in MESH_FOLDER or COLMAP project directory
        if mesh_file.startswith('current_reconstruction/'):
            # Mesh from COLMAP reconstruction
            mesh_path = Path(COLMAP_PROJECT_DIR) / mesh_file
        else:
            # Traditional mesh file
            mesh_path = Path(MESH_FOLDER) / mesh_file
            
        if not mesh_path.exists() or not mesh_path.is_file():
            return jsonify({'error': 'Mesh file not found'}), 404
        
        # Generate the rasterized map
        image_data, output = generate_raster_yard_map(
            str(mesh_path), grid_resolution, max_points, projection, 0.5, None, 'true_color', 1280, 720, rotation
        )
        
        if not image_data:
            return jsonify({'error': 'Failed to generate map: ' + output}), 500
        
        # Define the active map location (used by yard-map application)
        active_map_dir = Path('/home/andrew/nvr/yard-map')
        active_map_dir.mkdir(parents=True, exist_ok=True)
        
        active_map_path = active_map_dir / 'active_yard_map.png'
        active_config_path = active_map_dir / 'active_yard_map.json'
        
        # Save the map image
        with open(active_map_path, 'wb') as f:
            f.write(image_data)
        
        # Save the configuration
        config = {
            'mesh_file': mesh_file,
            'grid_resolution': grid_resolution,
            'max_points': max_points,
            'projection': projection,
            'width': 640,
            'height': 360,
            'algorithm': 'rasterized_cube_projection',
            'generated_at': datetime.now().isoformat(),
            'generated_by': 'Erik Image Manager'
        }
        
        with open(active_config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Saved active yard map: {active_map_path}")
        logger.info(f"Map config: {config}")
        
        return jsonify({
            'status': 'success',
            'message': 'Map saved as active yard map',
            'path': str(active_map_path),
            'config': config
        })
        
    except Exception as e:
        logger.error(f"Error saving yard map: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/mesh-files')
def api_mesh_files():
    """API endpoint to get mesh file list"""
    mesh_files = get_mesh_files()
    return jsonify({
        'mesh_files': mesh_files,
        'total_count': len(mesh_files)
    })

# Settings storage
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), 'global_settings.json')

def load_global_settings():
    """Load global settings from JSON file"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {
        'track_erik': True,
        'track_others': False,
        'track_animals': False,
        'pushover_enabled': False,
        'pushover_user_key': '',
        'pushover_app_token': ''
    }

def save_global_settings(settings):
    """Save global settings to JSON file"""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

@app.route('/api/config/external-ip', methods=['GET'])
def get_external_ip():
    """Get the external IP for camera URLs"""
    return jsonify({'external_ip': EXTERNAL_IP})

@app.route('/mobile')
def mobile_view():
    """Mobile-optimized camera view"""
    return render_template('mobile.html', external_ip=EXTERNAL_IP)

@app.route('/api/settings/global', methods=['GET'])
def get_global_settings():
    """Get global tracking settings"""
    try:
        settings = load_global_settings()
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        logger.error(f"Error loading settings: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/settings/global', methods=['POST'])
def save_settings():
    """Save global tracking settings and restart services if needed"""
    try:
        data = request.get_json()
        
        # Load current settings to check for changes
        old_settings = load_global_settings()
        
        # Update settings
        new_settings = {
            'track_erik': data.get('track_erik', True),
            'track_others': data.get('track_others', False),
            'track_animals': data.get('track_animals', False),
            'pushover_enabled': data.get('pushover_enabled', False),
            'pushover_user_key': data.get('pushover_user_key', ''),
            'pushover_app_token': data.get('pushover_app_token', '')
        }
        
        # Save settings
        save_global_settings(new_settings)
        
        # Check if tracking settings changed (would require service restart)
        tracking_changed = (
            old_settings.get('track_erik') != new_settings['track_erik'] or
            old_settings.get('track_others') != new_settings['track_others']
        )
        
        services_restarted = False
        if tracking_changed:
            # Restart the hybrid tracker service if it exists
            try:
                # Check if the service exists and restart it
                result = subprocess.run(['systemctl', 'status', 'hybrid-erik-tracker'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    subprocess.run(['sudo', 'systemctl', 'restart', 'hybrid-erik-tracker'], 
                                 capture_output=True, text=True)
                    services_restarted = True
                    logger.info("Restarted hybrid-erik-tracker service")
            except Exception as e:
                logger.warning(f"Could not restart service: {str(e)}")
        
        return jsonify({
            'success': True, 
            'message': 'Settings saved successfully',
            'services_restarted': services_restarted
        })
        
    except Exception as e:
        logger.error(f"Error saving settings: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# COLMAP Reconstruction API Endpoints
COLMAP_PROJECT_DIR = os.path.join(os.path.dirname(__file__), 'colmap_projects')
os.makedirs(COLMAP_PROJECT_DIR, exist_ok=True)

# Video upload directory - shared across all sessions
VIDEO_UPLOAD_DIR = os.path.join(COLMAP_PROJECT_DIR, 'uploaded_videos', 'shared')
os.makedirs(VIDEO_UPLOAD_DIR, exist_ok=True)

# File to store video metadata
VIDEO_METADATA_FILE = os.path.join(VIDEO_UPLOAD_DIR, 'videos.json')

def load_video_metadata():
    """Load video metadata from JSON file"""
    if os.path.exists(VIDEO_METADATA_FILE):
        try:
            with open(VIDEO_METADATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_video_metadata(videos):
    """Save video metadata to JSON file"""
    with open(VIDEO_METADATA_FILE, 'w') as f:
        json.dump(videos, f, indent=2)

@app.route('/api/colmap/upload-video', methods=['POST'])
def upload_video():
    """Upload and persist video files on the server (shared storage)"""
    try:
        if 'video' not in request.files:
            return jsonify({'success': False, 'error': 'No video file provided'})
        
        video_file = request.files['video']
        if video_file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        # Save video with unique filename to avoid conflicts
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        original_name = secure_filename(video_file.filename)
        if not original_name:
            original_name = "video.mov"
        
        # Create unique filename
        name_parts = original_name.rsplit('.', 1)
        if len(name_parts) == 2:
            filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
        else:
            filename = f"{original_name}_{timestamp}"
        
        video_path = os.path.join(VIDEO_UPLOAD_DIR, filename)
        video_file.save(video_path)
        
        # Get file info
        file_size = os.path.getsize(video_path)
        
        # Load existing videos
        videos = load_video_metadata()
        
        video_info = {
            'id': str(uuid.uuid4()),
            'name': filename,
            'original_name': video_file.filename,
            'size': file_size,
            'path': video_path,
            'uploaded_at': datetime.now().isoformat()
        }
        
        # Add to shared storage
        videos.append(video_info)
        save_video_metadata(videos)
        
        return jsonify({
            'success': True,
            'video': video_info,
            'message': f'Video {filename} uploaded successfully'
        })
        
    except Exception as e:
        logger.error(f"Video upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/delete-video/<video_id>', methods=['DELETE'])
def delete_video(video_id):
    """Delete an uploaded video from the server (shared storage)"""
    try:
        # Load videos from shared storage
        videos = load_video_metadata()
        
        # Find video to delete
        video_to_delete = None
        for video in videos:
            if video['id'] == video_id:
                video_to_delete = video
                break
        
        if not video_to_delete:
            return jsonify({'success': False, 'error': 'Video not found'})
        
        # Delete file from disk
        if os.path.exists(video_to_delete['path']):
            os.remove(video_to_delete['path'])
        
        # Remove from metadata
        videos = [v for v in videos if v['id'] != video_id]
        save_video_metadata(videos)
        
        return jsonify({'success': True, 'message': 'Video deleted successfully'})
        
    except Exception as e:
        logger.error(f"Video deletion error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/list-videos', methods=['GET'])
def list_videos():
    """List all uploaded videos from shared storage"""
    try:
        # Load videos from shared storage
        videos = load_video_metadata()
        
        # Verify files still exist and clean up metadata
        valid_videos = []
        for video in videos:
            if os.path.exists(video['path']):
                valid_videos.append(video)
        
        # Update metadata if any videos were removed
        if len(valid_videos) != len(videos):
            save_video_metadata(valid_videos)
        
        return jsonify({
            'success': True,
            'videos': valid_videos
        })
        
    except Exception as e:
        logger.error(f"Video listing error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/reset-project', methods=['POST'])
def reset_project():
    """Reset the COLMAP project by deleting all files"""
    try:
        project_name = "current_reconstruction"
        project_dir = os.path.join(COLMAP_PROJECT_DIR, project_name)
        
        if os.path.exists(project_dir):
            try:
                # Try regular removal first
                shutil.rmtree(project_dir)
            except PermissionError:
                try:
                    # If permission denied, try to change ownership first
                    subprocess.run(['sudo', 'chown', '-R', f'{os.getuid()}:{os.getgid()}', project_dir], 
                                  capture_output=True, text=True, timeout=10)
                    # Then try regular removal again
                    shutil.rmtree(project_dir, ignore_errors=True)
                except Exception:
                    # Last resort - force removal with sudo (may require password)
                    logger.warning(f"Could not remove {project_dir} - permission issues")
                    # Create a script to handle this more gracefully
                    pass
        
        # Clear session project reference
        if 'current_colmap_project' in session:
            del session['current_colmap_project']
            session.modified = True
        
        return jsonify({'success': True, 'message': 'Project reset successfully'})
    except Exception as e:
        logger.error(f"Project reset error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/extract-frames', methods=['POST'])
def extract_frames():
    try:
        import tempfile
        import subprocess
        
        # Use single COLMAP project directory - clean it first
        project_name = "current_reconstruction"
        project_dir = os.path.join(COLMAP_PROJECT_DIR, project_name)
        
        # Clean up existing project if it exists (handle permission issues)
        if os.path.exists(project_dir):
            try:
                # Try sudo removal first for files with permission issues
                result = subprocess.run(['sudo', 'rm', '-rf', project_dir], 
                                      capture_output=True, text=True)
                if result.returncode != 0:
                    shutil.rmtree(project_dir, ignore_errors=True)
            except:
                shutil.rmtree(project_dir, ignore_errors=True)
        
        # Create fresh project directory
        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(os.path.join(project_dir, 'images'), exist_ok=True)
        
        # Get videos from shared storage instead of uploaded files
        videos = load_video_metadata()
        if not videos:
            return jsonify({'success': False, 'error': 'No videos found. Please upload videos first.'})
        
        # Get frame interval parameter (default to 60)
        data = request.get_json() if request.is_json else request.form
        frame_interval = data.get('frame_interval', '60')
        try:
            frame_interval = int(frame_interval)
            if frame_interval <= 0:
                frame_interval = 60
        except (ValueError, TypeError):
            frame_interval = 60
        
        frame_count = 0
        
        for video_info in videos:
            video_path = video_info['path']
            
            # Check if video file exists
            if not os.path.exists(video_path):
                return jsonify({'success': False, 'error': f'Video file not found: {video_info["name"]}'})
            
            # Extract frames using ffmpeg in Docker
            video_name = os.path.splitext(video_info['name'])[0]
            output_pattern = os.path.join(project_dir, 'images', f'{video_name}_%06d.jpg')
            
            docker_cmd = [
                'docker', 'run', '--rm',
                '-v', f'{project_dir}:/workspace',
                '-v', f'{video_path}:/input.mov:ro',
                'jrottenberg/ffmpeg:4.4-alpine',
                '-i', '/input.mov',
                '-vf', f'select=not(mod(n\\,{frame_interval}))',  # Every Nth frame
                '-vsync', 'vfr',
                '-q:v', '2',  # High quality
                f'/workspace/images/{video_name}_%06d.jpg'
            ]
            
            result = subprocess.run(docker_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return jsonify({'success': False, 'error': f'FFmpeg error: {result.stderr}'})
        
        # Count extracted frames
        image_files = [f for f in os.listdir(os.path.join(project_dir, 'images')) if f.endswith('.jpg')]
        frame_count = len(image_files)
        
        # Also copy frames to the erik_tracker COLMAP project directory for testing
        erik_tracker_dir = os.path.expanduser('~/colmap/projects/erik_tracker/images')
        try:
            # Create erik_tracker directory if it doesn't exist
            os.makedirs(erik_tracker_dir, exist_ok=True)
            
            # Clear existing images in erik_tracker directory
            for existing_file in os.listdir(erik_tracker_dir):
                if existing_file.endswith(('.jpg', '.jpeg', '.png')):
                    os.remove(os.path.join(erik_tracker_dir, existing_file))
            
            # Copy all extracted frames to erik_tracker directory
            for image_file in image_files:
                src_path = os.path.join(project_dir, 'images', image_file)
                dst_path = os.path.join(erik_tracker_dir, image_file)
                shutil.copy2(src_path, dst_path)
            
            logger.info(f"Copied {frame_count} frames to erik_tracker directory: {erik_tracker_dir}")
            
        except Exception as copy_error:
            logger.warning(f"Failed to copy frames to erik_tracker directory: {copy_error}")
            # Don't fail the whole operation if erik_tracker copy fails
        
        # Store project info in session
        session['current_colmap_project'] = project_dir
        
        return jsonify({
            'success': True, 
            'frame_count': frame_count, 
            'project_dir': project_dir,
            'erik_tracker_dir': erik_tracker_dir,
            'copied_to_erik_tracker': True
        })
        
    except Exception as e:
        logger.error(f"Frame extraction error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/feature-extraction', methods=['POST'])
def feature_extraction():
    try:
        project_dir = session.get('current_colmap_project')
        if not project_dir or not os.path.exists(project_dir):
            return jsonify({'success': False, 'error': 'No active project found'})
        
        # Create database
        database_path = os.path.join(project_dir, 'database.db')
        images_path = os.path.join(project_dir, 'images')
        
        # COLMAP feature extraction using Docker with GPU acceleration (fallback to CPU on error)
        def try_feature_extraction_with_fallback():
            # Try GPU first
            docker_cmd_gpu = [
                'docker', 'run', '--rm', '--gpus', 'all',
                '-v', f'{project_dir}:/workspace',
                'colmap/colmap:latest',
                'colmap', 'feature_extractor',
                '--database_path', '/workspace/database.db',
                '--image_path', '/workspace/images',
                '--ImageReader.camera_model', 'OPENCV',
                '--SiftExtraction.max_image_size', '3200',
                '--SiftExtraction.use_gpu', '1'
            ]
            
            result = subprocess.run(docker_cmd_gpu, capture_output=True, text=True)
            
            # If GPU fails, try CPU fallback
            if result.returncode != 0 and ('CUDA' in result.stderr or 'GPU' in result.stderr):
                logger.warning(f"GPU feature extraction failed, falling back to CPU: {result.stderr}")
                docker_cmd_cpu = [
                    'docker', 'run', '--rm',
                    '-v', f'{project_dir}:/workspace',
                    'colmap/colmap:latest',
                    'colmap', 'feature_extractor',
                    '--database_path', '/workspace/database.db',
                    '--image_path', '/workspace/images',
                    '--ImageReader.camera_model', 'OPENCV',
                    '--SiftExtraction.max_image_size', '3200',
                    '--SiftExtraction.use_gpu', '0'
                ]
                result = subprocess.run(docker_cmd_cpu, capture_output=True, text=True)
            
            return result
        
        result = try_feature_extraction_with_fallback()
        
        if result.returncode != 0:
            return jsonify({'success': False, 'error': f'Feature extraction failed: {result.stderr}'})
        
        # Sequential feature matching with loop closure detection
        def try_feature_matching_with_fallback():
            # Step 1: Sequential matching for temporal continuity
            docker_cmd_sequential = [
                'docker', 'run', '--rm', '--gpus', 'all',
                '-v', f'{project_dir}:/workspace',
                'colmap/colmap:latest',
                'colmap', 'sequential_matcher',
                '--database_path', '/workspace/database.db',
                '--SiftMatching.use_gpu', '1',
                '--SequentialMatching.overlap', '10',  # Match with 10 previous images
                '--SequentialMatching.loop_detection', '1',  # Enable loop detection
                '--SequentialMatching.loop_detection_period', '10',  # Check every 10 images
                '--SequentialMatching.loop_detection_num_images', '50'  # Use last 50 images for loop detection
            ]
            
            result = subprocess.run(docker_cmd_sequential, capture_output=True, text=True)
            
            # If GPU fails, try CPU fallback
            if result.returncode != 0 and ('CUDA' in result.stderr or 'GPU' in result.stderr):
                logger.warning(f"GPU sequential matching failed, falling back to CPU: {result.stderr}")
                docker_cmd_cpu = [
                    'docker', 'run', '--rm',
                    '-v', f'{project_dir}:/workspace',
                    'colmap/colmap:latest',
                    'colmap', 'sequential_matcher',
                    '--database_path', '/workspace/database.db',
                    '--SiftMatching.use_gpu', '0',
                    '--SequentialMatching.overlap', '10',
                    '--SequentialMatching.loop_detection', '1',
                    '--SequentialMatching.loop_detection_period', '10',
                    '--SequentialMatching.loop_detection_num_images', '50'
                ]
                result = subprocess.run(docker_cmd_cpu, capture_output=True, text=True)
            
            return result
        
        result = try_feature_matching_with_fallback()
        
        if result.returncode != 0:
            return jsonify({'success': False, 'error': f'Feature matching failed: {result.stderr}'})
        
        # Count images processed
        image_files = [f for f in os.listdir(images_path) if f.endswith('.jpg')]
        
        return jsonify({'success': True, 'image_count': len(image_files)})
        
    except Exception as e:
        logger.error(f"Feature extraction error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/sparse-reconstruction', methods=['POST'])
def sparse_reconstruction():
    try:
        project_dir = session.get('current_colmap_project')
        if not project_dir or not os.path.exists(project_dir):
            return jsonify({'success': False, 'error': 'No active project found'})
        
        # Create sparse reconstruction directory
        sparse_dir = os.path.join(project_dir, 'sparse')
        os.makedirs(sparse_dir, exist_ok=True)
        
        # COLMAP mapper with GPU acceleration
        docker_cmd = [
            'docker', 'run', '--rm', '--gpus', 'all',
            '-v', f'{project_dir}:/workspace',
            'colmap/colmap:latest',
            'colmap', 'mapper',
            '--database_path', '/workspace/database.db',
            '--image_path', '/workspace/images',
            '--output_path', '/workspace/sparse'
        ]
        
        result = subprocess.run(docker_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({'success': False, 'error': f'Sparse reconstruction failed: {result.stderr}'})
        
        # Count points in reconstruction
        point_count = 0
        # Look for reconstruction folders (0, 1, 2, etc.)
        for item in os.listdir(sparse_dir):
            model_dir = os.path.join(sparse_dir, item)
            if os.path.isdir(model_dir):
                points_file = os.path.join(model_dir, 'points3D.txt')
                if os.path.exists(points_file):
                    with open(points_file, 'r') as f:
                        lines = [line for line in f if not line.startswith('#')]
                        point_count = len(lines)
                    break
        
        return jsonify({'success': True, 'point_count': point_count})
        
    except Exception as e:
        logger.error(f"Sparse reconstruction error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/analyze-models', methods=['GET'])
def analyze_sparse_models():
    """Analyze all available sparse reconstruction models"""
    try:
        project_dir = session.get('current_colmap_project')
        if not project_dir or not os.path.exists(project_dir):
            return jsonify({'success': False, 'error': 'No active project found'})
        
        sparse_dir = os.path.join(project_dir, 'sparse')
        if not os.path.exists(sparse_dir):
            return jsonify({'success': False, 'error': 'No sparse reconstruction found'})
        
        models = []
        
        # Analyze each model directory
        for item in sorted(os.listdir(sparse_dir)):
            model_path = os.path.join(sparse_dir, item)
            if os.path.isdir(model_path) and os.path.exists(os.path.join(model_path, 'cameras.bin')):
                try:
                    # Run COLMAP model analyzer
                    docker_cmd = [
                        'docker', 'run', '--rm',
                        '-v', f'{project_dir}:/workspace',
                        'colmap/colmap:latest',
                        'colmap', 'model_analyzer',
                        '--path', f'/workspace/sparse/{item}'
                    ]
                    
                    result = subprocess.run(docker_cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        # Parse the model analyzer output
                        output = result.stderr  # COLMAP logs to stderr
                        model_info = {
                            'model_id': item,
                            'path': f'sparse/{item}',
                            'cameras': 0,
                            'images': 0,
                            'registered_images': 0,
                            'points': 0,
                            'observations': 0,
                            'mean_track_length': 0.0,
                            'mean_observations_per_image': 0.0,
                            'mean_reprojection_error': 0.0,
                            'quality': 'unknown'
                        }
                        
                        # Extract metrics from output using regex
                        patterns = {
                            'cameras': r'Cameras: (\d+)',
                            'images': r'Images: (\d+)',
                            'registered_images': r'Registered images: (\d+)',
                            'points': r'Points: (\d+)',
                            'observations': r'Observations: (\d+)',
                            'mean_track_length': r'Mean track length: ([\d.]+)',
                            'mean_observations_per_image': r'Mean observations per image: ([\d.]+)',
                            'mean_reprojection_error': r'Mean reprojection error: ([\d.]+)px'
                        }
                        
                        for key, pattern in patterns.items():
                            match = re.search(pattern, output)
                            if match:
                                value = match.group(1)
                                if key in ['mean_track_length', 'mean_observations_per_image', 'mean_reprojection_error']:
                                    model_info[key] = float(value)
                                else:
                                    model_info[key] = int(value)
                        
                        # Determine quality based on metrics
                        if model_info['mean_reprojection_error'] < 0.6:
                            if model_info['registered_images'] > 50:
                                model_info['quality'] = 'excellent'
                            elif model_info['registered_images'] > 20:
                                model_info['quality'] = 'good'
                            else:
                                model_info['quality'] = 'fair'
                        elif model_info['mean_reprojection_error'] < 1.0:
                            if model_info['registered_images'] > 20:
                                model_info['quality'] = 'good'
                            else:
                                model_info['quality'] = 'fair'
                        else:
                            model_info['quality'] = 'poor'
                        
                        models.append(model_info)
                        
                except Exception as e:
                    logger.warning(f"Failed to analyze model {item}: {e}")
                    continue
        
        # Sort models by quality (excellent, good, fair, poor) and then by points count
        quality_order = {'excellent': 0, 'good': 1, 'fair': 2, 'poor': 3, 'unknown': 4}
        models.sort(key=lambda x: (quality_order.get(x['quality'], 4), -x['points']))
        
        return jsonify({
            'success': True, 
            'models': models,
            'total_models': len(models),
            'best_model': models[0]['model_id'] if models else None
        })
        
    except Exception as e:
        logger.error(f"Model analysis error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/select-model', methods=['POST'])
def select_sparse_model():
    """Select a specific sparse model for dense reconstruction"""
    try:
        data = request.get_json()
        model_id = data.get('model_id')
        
        # Handle clearing the selection (model_id = null)
        if model_id is None:
            if 'selected_sparse_model' in session:
                del session['selected_sparse_model']
                session.modified = True
            return jsonify({
                'success': True, 
                'selected_model': None,
                'message': 'Model selection cleared'
            })
        
        if not model_id:
            return jsonify({'success': False, 'error': 'No model ID provided'})
        
        project_dir = session.get('current_colmap_project')
        if not project_dir or not os.path.exists(project_dir):
            return jsonify({'success': False, 'error': 'No active project found'})
        
        model_path = os.path.join(project_dir, 'sparse', model_id)
        if not os.path.exists(model_path):
            return jsonify({'success': False, 'error': f'Model {model_id} not found'})
        
        # Store selected model in session
        session['selected_sparse_model'] = model_id
        session.permanent = True  # Make session persistent
        
        logger.info(f"📌 Model {model_id} stored in session for dense reconstruction")
        
        return jsonify({
            'success': True, 
            'selected_model': model_id,
            'message': f'Model {model_id} selected for dense reconstruction'
        })
        
    except Exception as e:
        logger.error(f"Model selection error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/current-model', methods=['GET'])
def get_current_model():
    """Debug endpoint to check currently selected model"""
    try:
        project_dir = session.get('current_colmap_project')
        selected_model_id = session.get('selected_sparse_model')
        
        return jsonify({
            'success': True,
            'project_dir': project_dir,
            'selected_model_id': selected_model_id,
            'session_id': session.get('session_id', 'unknown')
        })
        
    except Exception as e:
        logger.error(f"Get current model error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/dense-reconstruction', methods=['POST'])
def dense_reconstruction():
    try:
        project_dir = session.get('current_colmap_project')
        if not project_dir or not os.path.exists(project_dir):
            return jsonify({'success': False, 'error': 'No active project found'})
        
        sparse_dir = os.path.join(project_dir, 'sparse')
        dense_dir = os.path.join(project_dir, 'dense')
        os.makedirs(dense_dir, exist_ok=True)
        
        # Use selected model or default to best available model
        selected_model_id = session.get('selected_sparse_model')
        model_dir = None
        
        logger.info(f"Dense reconstruction - looking for selected model: {selected_model_id}")
        logger.info(f"Sparse directory: {sparse_dir}")
        logger.info(f"Available directories: {os.listdir(sparse_dir) if os.path.exists(sparse_dir) else 'Directory not found'}")
        
        if selected_model_id:
            potential_model = os.path.join(sparse_dir, selected_model_id)
            logger.info(f"Checking model path: {potential_model}")
            logger.info(f"Path exists: {os.path.exists(potential_model)}")
            logger.info(f"Is directory: {os.path.isdir(potential_model) if os.path.exists(potential_model) else False}")
            
            cameras_path = os.path.join(potential_model, 'cameras.bin')
            logger.info(f"Cameras.bin exists: {os.path.exists(cameras_path)}")
            
            if os.path.isdir(potential_model) and os.path.exists(os.path.join(potential_model, 'cameras.bin')):
                model_dir = potential_model
                logger.info(f"✅ Using selected sparse model: {selected_model_id} at {model_dir}")
            else:
                logger.warning(f"❌ Selected model {selected_model_id} not found or invalid at {potential_model}")
        
        # Fall back to finding the model with most images (best quality)
        if not model_dir:
            logger.info("No valid selected model, finding best model by image count...")
            best_model = None
            max_images = 0
            
            for item in os.listdir(sparse_dir):
                potential_model = os.path.join(sparse_dir, item)
                if os.path.isdir(potential_model) and os.path.exists(os.path.join(potential_model, 'cameras.bin')):
                    try:
                        # Count images in this model
                        images_bin = os.path.join(potential_model, 'images.bin')
                        if os.path.exists(images_bin):
                            # Quick estimate of image count from file size
                            file_size = os.path.getsize(images_bin)
                            estimated_images = max(1, file_size // 100)  # Rough estimate
                            
                            logger.info(f"Model {item}: estimated ~{estimated_images} images")
                            
                            if estimated_images > max_images:
                                max_images = estimated_images
                                best_model = item
                                model_dir = potential_model
                    except Exception as e:
                        logger.warning(f"Could not analyze model {item}: {e}")
                        # Fallback to first valid model
                        if not model_dir:
                            model_dir = potential_model
                            best_model = item
            
            if best_model:
                logger.info(f"✅ Using best available model: {best_model} (~{max_images} images)")
            else:
                logger.error("❌ No valid sparse models found!")
        
        if not model_dir:
            return jsonify({'success': False, 'error': 'No sparse reconstruction found'})
        
        # Image undistortion with GPU acceleration
        docker_cmd = [
            'docker', 'run', '--rm', '--gpus', 'all',
            '-v', f'{project_dir}:/workspace',
            'colmap/colmap:latest',
            'colmap', 'image_undistorter',
            '--image_path', '/workspace/images',
            '--input_path', f'/workspace/sparse/{os.path.basename(model_dir)}',
            '--output_path', '/workspace/dense',
            '--output_type', 'COLMAP'
        ]
        
        result = subprocess.run(docker_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({'success': False, 'error': f'Image undistortion failed: {result.stderr}'})
        
        # Patch match stereo with GPU acceleration (most GPU-intensive step)
        docker_cmd = [
            'docker', 'run', '--rm', '--gpus', 'all',
            '-v', f'{project_dir}:/workspace',
            'colmap/colmap:latest',
            'colmap', 'patch_match_stereo',
            '--workspace_path', '/workspace/dense',
            '--PatchMatchStereo.gpu_index', '0'  # Use GPU 0 for stereo matching
        ]
        
        result = subprocess.run(docker_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({'success': False, 'error': f'Stereo matching failed: {result.stderr}'})
        
        # Stereo fusion with GPU acceleration
        docker_cmd = [
            'docker', 'run', '--rm', '--gpus', 'all',
            '-v', f'{project_dir}:/workspace',
            'colmap/colmap:latest',
            'colmap', 'stereo_fusion',
            '--workspace_path', '/workspace/dense',
            '--output_path', '/workspace/dense/fused.ply'
        ]
        
        result = subprocess.run(docker_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({'success': False, 'error': f'Stereo fusion failed: {result.stderr}'})
        
        # Try to count points in the PLY file
        ply_file = os.path.join(dense_dir, 'fused.ply')
        point_count = 0
        
        if os.path.exists(ply_file):
            try:
                with open(ply_file, 'r') as f:
                    for line in f:
                        if line.startswith('element vertex'):
                            point_count = int(line.split()[-1])
                            break
            except:
                point_count = 0
        
        return jsonify({'success': True, 'point_count': point_count})
        
    except Exception as e:
        logger.error(f"Dense reconstruction error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/custom-fusion', methods=['POST'])
def custom_fusion():
    """Run custom fusion script instead of COLMAP's stereo_fusion"""
    try:
        project_dir = session.get('current_colmap_project')
        if not project_dir or not os.path.exists(project_dir):
            return jsonify({'success': False, 'error': 'No active project found'})
        
        dense_dir = os.path.join(project_dir, 'dense')
        
        # Check if patch_match_stereo has been run (depth maps exist)
        stereo_dir = os.path.join(dense_dir, 'stereo')
        if not os.path.exists(stereo_dir):
            return jsonify({'success': False, 'error': 'No stereo depth maps found. Run dense reconstruction first (up to stereo matching).'})
        
        # Check if custom fusion script exists
        custom_fusion_script = os.path.join(os.path.dirname(__file__), 'custom_fusion.py')
        if not os.path.exists(custom_fusion_script):
            return jsonify({'success': False, 'error': 'custom_fusion.py not found. Please add your fusion script to the project directory.'})
        
        # Run custom fusion script
        # The script should read from dense/stereo and output to dense/fused.ply
        result = subprocess.run([
            'python3', custom_fusion_script,
            '--workspace', dense_dir,
            '--output', os.path.join(dense_dir, 'fused.ply')
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({'success': False, 'error': f'Custom fusion failed: {result.stderr}'})
        
        # Check if output was created
        ply_file = os.path.join(dense_dir, 'fused.ply')
        if not os.path.exists(ply_file):
            return jsonify({'success': False, 'error': 'Custom fusion did not produce output file'})
        
        # Count points in the PLY file
        point_count = 0
        try:
            with open(ply_file, 'r') as f:
                for line in f:
                    if line.startswith('element vertex'):
                        point_count = int(line.split()[-1])
                        break
        except:
            point_count = 0
        
        return jsonify({
            'success': True, 
            'point_count': point_count,
            'message': 'Custom fusion completed successfully'
        })
        
    except Exception as e:
        logger.error(f"Custom fusion error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/dense-reconstruction-stereo-only', methods=['POST'])
def dense_reconstruction_stereo_only():
    """Run dense reconstruction up to stereo matching (without fusion) for custom fusion later"""
    try:
        project_dir = session.get('current_colmap_project')
        if not project_dir or not os.path.exists(project_dir):
            return jsonify({'success': False, 'error': 'No active project found'})
        
        sparse_dir = os.path.join(project_dir, 'sparse')
        dense_dir = os.path.join(project_dir, 'dense')
        os.makedirs(dense_dir, exist_ok=True)
        
        # Use selected model or default to best available model
        selected_model_id = session.get('selected_sparse_model')
        model_dir = None
        
        logger.info(f"Stereo-only - looking for selected model: {selected_model_id}")
        logger.info(f"Available models: {os.listdir(sparse_dir) if os.path.exists(sparse_dir) else 'Directory not found'}")
        
        if selected_model_id:
            potential_model = os.path.join(sparse_dir, selected_model_id)
            logger.info(f"Checking stereo model path: {potential_model}")
            
            if os.path.isdir(potential_model) and os.path.exists(os.path.join(potential_model, 'cameras.bin')):
                model_dir = potential_model
                logger.info(f"✅ Using selected sparse model for stereo: {selected_model_id} at {model_dir}")
            else:
                logger.warning(f"❌ Selected stereo model {selected_model_id} not found or invalid")
        
        # Fall back to finding the model with most images (best quality)
        if not model_dir:
            logger.info("No valid selected stereo model, finding best model by image count...")
            best_model = None
            max_images = 0
            
            for item in os.listdir(sparse_dir):
                potential_model = os.path.join(sparse_dir, item)
                if os.path.isdir(potential_model) and os.path.exists(os.path.join(potential_model, 'cameras.bin')):
                    try:
                        # Count images in this model
                        images_bin = os.path.join(potential_model, 'images.bin')
                        if os.path.exists(images_bin):
                            # Quick estimate of image count from file size
                            file_size = os.path.getsize(images_bin)
                            estimated_images = max(1, file_size // 100)  # Rough estimate
                            
                            logger.info(f"Stereo model {item}: estimated ~{estimated_images} images")
                            
                            if estimated_images > max_images:
                                max_images = estimated_images
                                best_model = item
                                model_dir = potential_model
                    except Exception as e:
                        logger.warning(f"Could not analyze stereo model {item}: {e}")
                        # Fallback to first valid model
                        if not model_dir:
                            model_dir = potential_model
                            best_model = item
            
            if best_model:
                logger.info(f"✅ Using best available stereo model: {best_model} (~{max_images} images)")
            else:
                logger.error("❌ No valid sparse models found for stereo!")
        
        if not model_dir:
            return jsonify({'success': False, 'error': 'No sparse reconstruction found'})
        
        # Image undistortion with GPU acceleration
        docker_cmd = [
            'docker', 'run', '--rm', '--gpus', 'all',
            '-v', f'{project_dir}:/workspace',
            'colmap/colmap:latest',
            'colmap', 'image_undistorter',
            '--image_path', '/workspace/images',
            '--input_path', f'/workspace/sparse/{os.path.basename(model_dir)}',
            '--output_path', '/workspace/dense',
            '--output_type', 'COLMAP'
        ]
        
        result = subprocess.run(docker_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({'success': False, 'error': f'Image undistortion failed: {result.stderr}'})
        
        # Patch match stereo with GPU acceleration (most GPU-intensive step)
        docker_cmd = [
            'docker', 'run', '--rm', '--gpus', 'all',
            '-v', f'{project_dir}:/workspace',
            'colmap/colmap:latest',
            'colmap', 'patch_match_stereo',
            '--workspace_path', '/workspace/dense',
            '--PatchMatchStereo.gpu_index', '0'
        ]
        
        result = subprocess.run(docker_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({'success': False, 'error': f'Stereo matching failed: {result.stderr}'})
        
        return jsonify({
            'success': True,
            'message': 'Stereo matching completed. Ready for custom fusion.'
        })
        
    except Exception as e:
        logger.error(f"Dense reconstruction (stereo only) error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/enable-point-cloud', methods=['POST'])
def enable_point_cloud():
    try:
        project_dir = session.get('current_colmap_project')
        if not project_dir or not os.path.exists(project_dir):
            return jsonify({'success': False, 'error': 'No active project found'})
        
        # Look for the PLY file
        ply_file = os.path.join(project_dir, 'dense', 'fused.ply')
        if not os.path.exists(ply_file):
            return jsonify({'success': False, 'error': 'No dense reconstruction found'})
        
        # Copy the PLY file to meshes directory for the Yard Map tab
        mesh_name = f"colmap_reconstruction_{int(time.time())}.ply"
        dest_path = os.path.join(MESH_FOLDER, mesh_name)
        
        import shutil
        shutil.copy2(ply_file, dest_path)
        
        logger.info(f"Enabled point cloud: {mesh_name}")
        
        return jsonify({'success': True, 'mesh_file': mesh_name})
        
    except Exception as e:
        logger.error(f"Enable point cloud error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/capture-camera-snapshot', methods=['POST'])
def capture_camera_snapshot():
    """Capture high-quality snapshot from Frigate camera for pose estimation"""
    try:
        data = request.get_json()
        camera_name = data.get('camera')
        
        if not camera_name:
            return jsonify({'success': False, 'error': 'Camera name is required'})
        
        project_dir = session.get('current_colmap_project')
        if not project_dir or not os.path.exists(project_dir):
            return jsonify({'success': False, 'error': 'No active COLMAP project found'})
        
        # Create camera snapshots directory
        snapshots_dir = os.path.join(project_dir, 'camera_snapshots')
        os.makedirs(snapshots_dir, exist_ok=True)
        
        # Capture snapshot from Frigate
        frigate_url = f"http://localhost:5000/api/{camera_name}/latest.jpg?h=720"
        
        import requests
        response = requests.get(frigate_url, timeout=10)
        response.raise_for_status()
        
        # Save snapshot with timestamp
        timestamp = int(time.time())
        snapshot_filename = f"{camera_name}_{timestamp}.jpg"
        snapshot_path = os.path.join(snapshots_dir, snapshot_filename)
        
        with open(snapshot_path, 'wb') as f:
            f.write(response.content)
        
        # Verify image was saved and is valid
        from PIL import Image
        try:
            with Image.open(snapshot_path) as img:
                width, height = img.size
                if width == 0 or height == 0:
                    raise ValueError("Invalid image dimensions")
        except Exception as e:
            return jsonify({'success': False, 'error': f'Invalid image captured: {str(e)}'})
        
        logger.info(f"Captured camera snapshot: {snapshot_filename} ({width}x{height})")
        
        return jsonify({
            'success': True, 
            'snapshot_path': snapshot_path,
            'snapshot_filename': snapshot_filename,
            'image_size': [width, height]
        })
        
    except Exception as e:
        logger.error(f"Camera snapshot capture error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/estimate-camera-pose', methods=['POST'])
def estimate_camera_pose():
    """Estimate camera pose using COLMAP image registration"""
    try:
        data = request.get_json()
        camera_name = data.get('camera')
        snapshot_path = data.get('snapshot_path')
        
        if not camera_name or not snapshot_path:
            return jsonify({'success': False, 'error': 'Camera name and snapshot path are required'})
        
        project_dir = session.get('current_colmap_project')
        if not project_dir or not os.path.exists(project_dir):
            return jsonify({'success': False, 'error': 'No active COLMAP project found'})
        
        start_time = time.time()
        
        # Check if we have a valid sparse reconstruction
        sparse_dir = os.path.join(project_dir, 'sparse', '0')
        if not os.path.exists(sparse_dir):
            return jsonify({'success': False, 'error': 'No sparse reconstruction found. Run COLMAP reconstruction first.'})
        
        database_path = os.path.join(project_dir, 'database.db')
        if not os.path.exists(database_path):
            return jsonify({'success': False, 'error': 'COLMAP database not found. Run COLMAP reconstruction first.'})
        
        # Create pose estimation directory
        pose_dir = os.path.join(project_dir, 'camera_poses', camera_name)
        os.makedirs(pose_dir, exist_ok=True)
        
        # Copy snapshot to temporary images directory for COLMAP
        temp_images_dir = os.path.join(pose_dir, 'images')
        os.makedirs(temp_images_dir, exist_ok=True)
        
        import shutil
        temp_snapshot_path = os.path.join(temp_images_dir, os.path.basename(snapshot_path))
        shutil.copy2(snapshot_path, temp_snapshot_path)
        
        # Run COLMAP image registration pipeline
        success, error_msg, results = run_colmap_pose_estimation(
            database_path, temp_images_dir, sparse_dir, pose_dir
        )
        
        if not success:
            return jsonify({'success': False, 'error': error_msg})
        
        processing_time = time.time() - start_time
        
        # Parse camera pose from results
        pose_data = parse_camera_pose_results(pose_dir, camera_name)
        pose_data['processing_time'] = round(processing_time, 2)
        pose_data['camera'] = camera_name
        
        # Save pose data for later use
        pose_file = os.path.join(pose_dir, 'pose_data.json')
        with open(pose_file, 'w') as f:
            json.dump(pose_data, f, indent=2)
        
        logger.info(f"Camera pose estimation completed for {camera_name} in {processing_time:.2f}s")
        
        return jsonify({
            'success': True,
            **pose_data
        })
        
    except Exception as e:
        logger.error(f"Camera pose estimation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

def run_colmap_pose_estimation(database_path, images_dir, sparse_input_dir, output_dir):
    """Run COLMAP image registration pipeline"""
    try:
        # Step 1: Extract features for new image
        cmd_features = [
            'docker', 'run', '--rm', '--gpus', 'all', '-v', f'{os.path.dirname(database_path)}:/workspace',
            'colmap/colmap:latest', 'colmap', 'feature_extractor',
            '--database_path', '/workspace/' + os.path.basename(database_path),
            '--image_path', f'/workspace/{os.path.relpath(images_dir, os.path.dirname(database_path))}',
            '--ImageReader.single_camera', '1',
            '--SiftExtraction.use_gpu', '1'
        ]
        
        logger.info("Running COLMAP feature extraction for camera pose...")
        result = subprocess.run(cmd_features, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            return False, f"Feature extraction failed: {result.stderr}", None
        
        # Step 2: Match features with existing model
        cmd_match = [
            'docker', 'run', '--rm', '--gpus', 'all', '-v', f'{os.path.dirname(database_path)}:/workspace',
            'colmap/colmap:latest', 'colmap', 'exhaustive_matcher',
            '--database_path', '/workspace/' + os.path.basename(database_path),
            '--SiftMatching.use_gpu', '1'
        ]
        
        logger.info("Running COLMAP feature matching...")
        result = subprocess.run(cmd_match, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            return False, f"Feature matching failed: {result.stderr}", None
        
        # Step 3: Register camera image
        cmd_register = [
            'docker', 'run', '--rm', '-v', f'{os.path.dirname(database_path)}:/workspace',
            'colmap/colmap:latest', 'colmap', 'image_registrator',
            '--database_path', '/workspace/' + os.path.basename(database_path),
            '--input_path', f'/workspace/{os.path.relpath(sparse_input_dir, os.path.dirname(database_path))}',
            '--output_path', f'/workspace/{os.path.relpath(output_dir, os.path.dirname(database_path))}'
        ]
        
        logger.info("Running COLMAP image registration...")
        result = subprocess.run(cmd_register, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            return False, f"Image registration failed: {result.stderr}", None
        
        return True, None, result.stdout
        
    except subprocess.TimeoutExpired:
        return False, "COLMAP processing timeout", None
    except Exception as e:
        return False, str(e), None

def parse_camera_pose_results(pose_dir, camera_name):
    """Parse camera pose from COLMAP output"""
    try:
        # Look for images.bin file in the pose directory
        images_bin_path = os.path.join(pose_dir, 'images.bin')
        if not os.path.exists(images_bin_path):
            return {'error': 'No pose results found'}
        
        # For now, return placeholder data
        # TODO: Implement proper COLMAP binary file parsing
        return {
            'success': True,
            'confidence': 0.85,
            'num_matches': 150,
            'transformation_matrix': [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0], 
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0]
            ],
            'translation': [0.0, 0.0, 0.0],
            'rotation': [1.0, 0.0, 0.0, 0.0]  # quaternion
        }
        
    except Exception as e:
        return {'error': f'Failed to parse pose results: {str(e)}'}

@app.route('/api/colmap/camera-poses', methods=['GET'])
def get_camera_poses():
    """Get all estimated camera poses"""
    try:
        project_dir = session.get('current_colmap_project')
        if not project_dir:
            return jsonify({'success': False, 'error': 'No active COLMAP project'})
        
        poses_base_dir = os.path.join(project_dir, 'camera_poses')
        if not os.path.exists(poses_base_dir):
            return jsonify({'success': True, 'poses': {}})
        
        poses = {}
        for camera_name in os.listdir(poses_base_dir):
            pose_file = os.path.join(poses_base_dir, camera_name, 'pose_data.json')
            if os.path.exists(pose_file):
                with open(pose_file, 'r') as f:
                    poses[camera_name] = json.load(f)
        
        return jsonify({'success': True, 'poses': poses})
        
    except Exception as e:
        logger.error(f"Get camera poses error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/upload-reconstruction', methods=['POST'])
def upload_reconstruction():
    """Upload COLMAP reconstruction files (sparse model or dense PLY)"""
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': 'No files provided'})
        
        files = request.files.getlist('files')
        reconstruction_type = request.form.get('type', 'sparse')  # 'sparse' or 'dense'
        project_name = request.form.get('project_name', f'uploaded_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        
        # Create project directory
        project_dir = os.path.join('/home/andrew/nvr/colmap_projects', project_name)
        os.makedirs(project_dir, exist_ok=True)
        
        uploaded_files = []
        
        if reconstruction_type == 'sparse':
            # Handle sparse reconstruction files (cameras.bin, images.bin, points3D.bin)
            sparse_dir = os.path.join(project_dir, 'sparse', '0')
            os.makedirs(sparse_dir, exist_ok=True)
            
            required_files = set()
            for file in files:
                if file.filename in ['cameras.bin', 'images.bin', 'points3D.bin',
                                    'cameras.txt', 'images.txt', 'points3D.txt']:
                    file_path = os.path.join(sparse_dir, file.filename)
                    file.save(file_path)
                    uploaded_files.append(file.filename)
                    if file.filename.endswith('.bin'):
                        required_files.add(file.filename.replace('.bin', ''))
            
            # Check if we have all required sparse files
            if not {'cameras', 'images', 'points3D'}.issubset(required_files):
                missing = {'cameras', 'images', 'points3D'} - required_files
                return jsonify({
                    'success': False, 
                    'error': f'Missing required sparse files: {", ".join(f"{m}.bin" for m in missing)}'
                })
            
            # Store in session for camera pose estimation
            session['current_colmap_project'] = project_dir
            
        elif reconstruction_type == 'dense':
            # Handle dense reconstruction (PLY files)
            dense_dir = os.path.join(project_dir, 'dense')
            os.makedirs(dense_dir, exist_ok=True)
            
            for file in files:
                if file.filename.endswith('.ply'):
                    # Save to both dense dir and meshes dir
                    dense_path = os.path.join(dense_dir, 'fused.ply')
                    file.save(dense_path)
                    
                    # Also copy to meshes folder for yard map generation
                    mesh_name = f"{project_name}_{file.filename}"
                    mesh_path = os.path.join(MESH_FOLDER, mesh_name)
                    shutil.copy2(dense_path, mesh_path)
                    
                    uploaded_files.append(file.filename)
            
            if not uploaded_files:
                return jsonify({'success': False, 'error': 'No PLY files found in upload'})
        
        else:
            return jsonify({'success': False, 'error': 'Invalid reconstruction type'})
        
        return jsonify({
            'success': True,
            'message': f'Successfully uploaded {len(uploaded_files)} files',
            'project_name': project_name,
            'project_dir': project_dir,
            'type': reconstruction_type,
            'uploaded_files': uploaded_files
        })
        
    except Exception as e:
        logger.error(f"Upload reconstruction error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/upload-complete-project', methods=['POST'])
def upload_complete_project():
    """Upload a complete COLMAP project (ZIP file containing all reconstruction data)"""
    try:
        if 'project_zip' not in request.files:
            return jsonify({'success': False, 'error': 'No ZIP file provided'})
        
        zip_file = request.files['project_zip']
        if not zip_file.filename.endswith('.zip'):
            return jsonify({'success': False, 'error': 'File must be a ZIP archive'})
        
        # Create temporary directory for extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, 'project.zip')
            zip_file.save(zip_path)
            
            # Extract ZIP
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Find project structure
            extracted_items = os.listdir(temp_dir)
            extracted_items.remove('project.zip')
            
            # Determine project root (might be nested in a folder)
            project_root = temp_dir
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_dir, extracted_items[0])):
                project_root = os.path.join(temp_dir, extracted_items[0])
            
            # Validate project structure
            has_sparse = os.path.exists(os.path.join(project_root, 'sparse'))
            has_dense = os.path.exists(os.path.join(project_root, 'dense'))
            has_images = os.path.exists(os.path.join(project_root, 'images'))
            
            if not (has_sparse or has_dense):
                return jsonify({
                    'success': False,
                    'error': 'Invalid project structure. Must contain sparse/ or dense/ directory'
                })
            
            # Copy to colmap_projects
            project_name = f'uploaded_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            project_dir = os.path.join('/home/andrew/nvr/colmap_projects', project_name)
            shutil.copytree(project_root, project_dir)
            
            # If there's a dense reconstruction, also copy PLY to meshes
            dense_ply = os.path.join(project_dir, 'dense', 'fused.ply')
            if os.path.exists(dense_ply):
                mesh_path = os.path.join(MESH_FOLDER, f'{project_name}_dense.ply')
                shutil.copy2(dense_ply, mesh_path)
            
            # Store in session
            session['current_colmap_project'] = project_dir
            
            return jsonify({
                'success': True,
                'message': 'Project uploaded successfully',
                'project_name': project_name,
                'project_dir': project_dir,
                'has_sparse': has_sparse,
                'has_dense': has_dense,
                'has_images': has_images
            })
            
    except Exception as e:
        logger.error(f"Upload complete project error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# Progress tracking API endpoints
@app.route('/api/colmap/start-with-progress/<phase>', methods=['POST'])
def start_colmap_phase_with_progress(phase):
    """Start COLMAP phase with progress tracking"""
    try:
        session_id = str(uuid.uuid4())
        
        # Initialize progress tracker
        tracker = COLMAPProgressTracker(session_id)
        tracker.current_phase = phase
        
        # Get project directory from session while still in request context
        project_dir = session.get('current_colmap_project')
        if not project_dir:
            return jsonify({'success': False, 'error': 'No active COLMAP project found'})
        
        with progress_lock:
            colmap_progress_sessions[session_id] = tracker
        
        # Initialize global progress state
        with global_progress_lock:
            global_progress_state.update({
                'active': True,
                'current_phase': phase,
                'progress': tracker.progress.copy(),
                'completed': False,
                'session_id': session_id,
                'project_dir': project_dir,
                'start_time': time.time(),
                'last_updated': time.time()
            })
        
        # Start COLMAP process in background thread
        def run_phase():
            try:
                success = False
                if phase == 'feature_extraction':
                    success = run_feature_extraction_with_progress(tracker, project_dir)
                elif phase == 'sparse_reconstruction':
                    success = run_sparse_reconstruction_with_progress(tracker, project_dir)
                elif phase == 'dense_reconstruction':
                    success = run_dense_reconstruction_with_progress(tracker, project_dir)
                
                # Mark progress as 100% when completed
                if success and phase in tracker.progress:
                    tracker.progress[phase]['percent'] = 100
                
                # Update global progress state
                tracker.completed = True
                update_global_progress(session_id)
                    
            except Exception as e:
                logger.error(f"Error running COLMAP phase {phase}: {e}")
                tracker.completed = True
                update_global_progress(session_id)
        
        threading.Thread(target=run_phase, daemon=True).start()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'phase': phase
        })
        
    except Exception as e:
        logger.error(f"Error starting COLMAP phase with progress: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/set-project', methods=['POST'])
def set_current_project():
    """Set the current COLMAP project for debugging"""
    try:
        project_name = "current_reconstruction"
        project_dir = os.path.join(COLMAP_PROJECT_DIR, project_name)
        
        if not os.path.exists(project_dir):
            return jsonify({'success': False, 'error': 'Project directory does not exist'})
        
        session['current_colmap_project'] = project_dir
        logger.info(f"Set current COLMAP project to: {project_dir}")
        
        return jsonify({'success': True, 'project_dir': project_dir})
        
    except Exception as e:
        logger.error(f"Error setting current project: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/progress/<session_id>', methods=['GET'])
def get_colmap_progress(session_id):
    """Get current COLMAP progress for a session"""
    try:
        with progress_lock:
            if session_id in colmap_progress_sessions:
                tracker = colmap_progress_sessions[session_id]
                return jsonify({
                    'success': True,
                    'current_phase': tracker.current_phase,
                    'progress': tracker.progress,
                    'completed': tracker.completed,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return jsonify({
                    'success': False, 
                    'error': 'Session not found'
                })
        
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/global-progress', methods=['GET'])
def get_global_colmap_progress():
    """Get current global COLMAP progress (visible to all clients)"""
    try:
        progress_data = get_global_progress()
        
        # If no active progress, check if there are any running sessions
        if not progress_data['active']:
            with progress_lock:
                if colmap_progress_sessions:
                    # Find the most recent session
                    latest_session = max(colmap_progress_sessions.keys())
                    update_global_progress(latest_session)
                    progress_data = get_global_progress()
        
        return jsonify({
            'success': True,
            'active': progress_data['active'],
            'current_phase': progress_data['current_phase'],
            'progress': progress_data['progress'],
            'completed': progress_data['completed'],
            'last_updated': progress_data['last_updated'],
            'timestamp': time.time()
        })
        
    except Exception as e:
        logger.error(f"Error getting global progress: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/stereo-progress', methods=['GET'])
def get_stereo_progress():
    """Get stereo matching progress by counting depth maps"""
    try:
        # Use current_reconstruction as the default project directory
        project_dir = session.get('current_colmap_project')
        if not project_dir or not os.path.exists(project_dir):
            project_dir = '/home/andrew/nvr/colmap_projects/current_reconstruction'
            if not os.path.exists(project_dir):
                return jsonify({'success': False, 'error': 'No active project found'})
        
        depth_maps_dir = os.path.join(project_dir, 'dense', 'stereo', 'depth_maps')
        normal_maps_dir = os.path.join(project_dir, 'dense', 'stereo', 'normal_maps')
        
        # Count generated depth maps
        depth_count = 0
        normal_count = 0
        
        if os.path.exists(depth_maps_dir):
            depth_count = len([f for f in os.listdir(depth_maps_dir) if f.endswith('.photometric.bin')])
        
        if os.path.exists(normal_maps_dir):
            normal_count = len([f for f in os.listdir(normal_maps_dir) if f.endswith('.geometric.bin')])
        
        # Get total number of images from undistorted images directory
        # This is more accurate than estimating from binary files
        undistorted_images_dir = os.path.join(project_dir, 'dense', 'images')
        total_images = 0
        
        if os.path.exists(undistorted_images_dir):
            total_images = len([f for f in os.listdir(undistorted_images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
        
        # Fallback to sparse reconstruction estimation if undistorted images not found
        if total_images == 0:
            sparse_dir = os.path.join(project_dir, 'sparse')
            for item in os.listdir(sparse_dir):
                potential_model = os.path.join(sparse_dir, item)
                if os.path.isdir(potential_model) and os.path.exists(os.path.join(potential_model, 'images.bin')):
                    try:
                        images_bin = os.path.join(potential_model, 'images.bin')
                        file_size = os.path.getsize(images_bin)
                        # More realistic estimation: assume ~300 bytes per image on average
                        estimated_images = max(1, file_size // 300)
                        if estimated_images > total_images:
                            total_images = estimated_images
                    except:
                        pass
        
        # Calculate progress
        progress_percent = 0
        if total_images > 0:
            progress_percent = min(100, int((depth_count / total_images) * 100))
        
        # Determine status
        is_completed = depth_count > 0 and depth_count >= total_images * 0.8  # Consider complete if 80%+ done
        is_active = depth_count > 0 and not is_completed
        
        return jsonify({
            'success': True,
            'active': is_active,
            'completed': is_completed,
            'depth_maps_generated': depth_count,
            'normal_maps_generated': normal_count,
            'total_images': total_images,
            'progress_percent': progress_percent,
            'status': 'completed' if is_completed else ('active' if is_active else 'pending')
        })
        
    except Exception as e:
        logger.error(f"Error getting stereo progress: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/colmap/fusion-progress', methods=['GET'])
def get_fusion_progress():
    """Get fusion progress by checking PLY file status"""
    try:
        # Use current_reconstruction as the default project directory
        project_dir = session.get('current_colmap_project')
        if not project_dir or not os.path.exists(project_dir):
            project_dir = '/home/andrew/nvr/colmap_projects/current_reconstruction'
            if not os.path.exists(project_dir):
                return jsonify({'success': False, 'error': 'No active project found'})
        
        ply_file = os.path.join(project_dir, 'dense', 'fused.ply')
        
        # Check if PLY exists and has content
        ply_exists = os.path.exists(ply_file)
        ply_size = 0
        point_count = 0
        
        if ply_exists:
            ply_size = os.path.getsize(ply_file)
            
            # Try to count vertices in PLY file
            try:
                with open(ply_file, 'r') as f:
                    for line in f:
                        if line.startswith('element vertex'):
                            point_count = int(line.split()[-1])
                            break
            except:
                pass
        
        # Determine status
        is_completed = ply_exists and point_count > 0
        is_active = ply_exists and point_count == 0  # PLY exists but empty (fusion running)
        
        return jsonify({
            'success': True,
            'active': is_active,
            'completed': is_completed,
            'ply_exists': ply_exists,
            'ply_size_bytes': ply_size,
            'point_count': point_count,
            'status': 'completed' if is_completed else ('active' if is_active else 'pending')
        })
        
    except Exception as e:
        logger.error(f"Error getting fusion progress: {e}")
        return jsonify({'success': False, 'error': str(e)})

def run_feature_extraction_with_progress(tracker, project_dir):
    """Run feature extraction and sequential matching with progress tracking"""
    try:
        if not project_dir:
            logger.error("No project directory provided")
            return False
            
        images_dir = os.path.join(project_dir, 'images')
        database_path = os.path.join(project_dir, 'database.db')
        
        # Estimate total images for progress tracking
        if os.path.exists(images_dir):
            image_files = [f for f in os.listdir(images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            tracker.progress['feature_extraction']['total'] = len(image_files)
        
        # Step 1: Feature extraction (CPU-only for testing)
        cmd_features = [
            'docker', 'run', '--rm',
            '-v', f'{project_dir}:/workspace',
            'colmap/colmap:latest',
            'colmap', 'feature_extractor',
            '--database_path', '/workspace/database.db',
            '--image_path', '/workspace/images',
            '--ImageReader.camera_model', 'OPENCV',
            '--SiftExtraction.max_image_size', '3200',
            '--SiftExtraction.use_gpu', '0'
        ]
        
        logger.info(f"Starting feature extraction with progress for session {tracker.session_id}")
        logger.info(f"Command: {' '.join(cmd_features)}")
        
        if not run_colmap_with_progress(cmd_features, tracker.session_id):
            logger.error("Feature extraction failed")
            return False
            
        logger.info("Feature extraction completed successfully")
        
        # Step 2: Sequential matching with loop closure
        cmd_matching = [
            'docker', 'run', '--rm',
            '-v', f'{project_dir}:/workspace',
            'colmap/colmap:latest',
            'colmap', 'sequential_matcher',
            '--database_path', '/workspace/database.db',
            '--SiftMatching.use_gpu', '0',  # CPU-only matching
            '--SequentialMatching.overlap', '10',  # Match with 10 previous images
            '--SequentialMatching.loop_detection', '0',  # Disable loop detection for now
        ]
        
        return run_colmap_with_progress(cmd_matching, tracker.session_id)
        
    except Exception as e:
        logger.error(f"Feature extraction with progress error: {e}")
        return False

def run_sparse_reconstruction_with_progress(tracker, project_dir):
    """Run sparse reconstruction with progress tracking"""
    try:
        if not project_dir:
            logger.error("No project directory provided")
            return False
            
        database_path = os.path.join(project_dir, 'database.db')
        images_dir = os.path.join(project_dir, 'images')
        sparse_dir = os.path.join(project_dir, 'sparse')
        
        # Estimate total images for progress tracking
        if os.path.exists(images_dir):
            image_files = [f for f in os.listdir(images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            tracker.progress['sparse_reconstruction']['total'] = len(image_files)
        
        os.makedirs(sparse_dir, exist_ok=True)
        
        cmd = [
            'docker', 'run', '--rm',
            '-v', f'{project_dir}:/workspace',
            'colmap/colmap:latest',
            'colmap', 'mapper',
            '--database_path', '/workspace/database.db',
            '--image_path', '/workspace/images',
            '--output_path', '/workspace/sparse'
        ]
        
        return run_colmap_with_progress(cmd, tracker.session_id)
        
    except Exception as e:
        logger.error(f"Sparse reconstruction with progress error: {e}")
        return False

def run_dense_reconstruction_with_progress(tracker, project_dir):
    """Run dense reconstruction with progress tracking"""
    try:
        if not project_dir:
            logger.error("No project directory provided")
            return False
            
        sparse_dir = os.path.join(project_dir, 'sparse')
        dense_dir = os.path.join(project_dir, 'dense')
        
        os.makedirs(dense_dir, exist_ok=True)
        
        # Get selected model (this needs to access session, which is tricky in background thread)
        # For now, find the best model by image count
        model_id = "0"  # default fallback
        best_model = None
        max_images = 0
        
        logger.info("Progress tracker: Finding best model for dense reconstruction...")
        
        try:
            for item in os.listdir(sparse_dir):
                potential_model = os.path.join(sparse_dir, item)
                if os.path.isdir(potential_model) and os.path.exists(os.path.join(potential_model, 'cameras.bin')):
                    try:
                        # Count images in this model
                        images_bin = os.path.join(potential_model, 'images.bin')
                        if os.path.exists(images_bin):
                            file_size = os.path.getsize(images_bin)
                            estimated_images = max(1, file_size // 100)
                            
                            logger.info(f"Progress tracker model {item}: estimated ~{estimated_images} images")
                            
                            if estimated_images > max_images:
                                max_images = estimated_images
                                best_model = item
                                model_id = item
                    except Exception as e:
                        logger.warning(f"Could not analyze progress model {item}: {e}")
            
            if best_model:
                logger.info(f"✅ Progress tracker using best model: {best_model} (~{max_images} images)")
            else:
                logger.warning("❌ Progress tracker: No valid models found, using default")
                
        except Exception as e:
            logger.error(f"Error finding best model for progress tracker: {e}")
        
        # Run undistorter first
        cmd1 = [
            'docker', 'run', '--rm',
            '-v', f'{project_dir}:/workspace',
            'colmap/colmap:latest',
            'colmap', 'image_undistorter',
            '--image_path', '/workspace/images',
            '--input_path', f'/workspace/sparse/{model_id}',
            '--output_path', '/workspace/dense',
            '--output_type', 'COLMAP'
        ]
        
        if not run_colmap_with_progress(cmd1, tracker.session_id):
            return False
        
        # Run stereo
        cmd2 = [
            'docker', 'run', '--rm',
            '-v', f'{project_dir}:/workspace',
            'colmap/colmap:latest',
            'colmap', 'patch_match_stereo',
            '--workspace_path', '/workspace/dense',
            '--workspace_format', 'COLMAP'
        ]
        
        return run_colmap_with_progress(cmd2, tracker.session_id)
        
    except Exception as e:
        logger.error(f"Dense reconstruction with progress error: {e}")
        return False

@app.route('/api/camera-proxy/setup-all', methods=['POST'])
def setup_all_camera_proxies():
    """Set up port forwarding for all configured cameras"""
    try:
        config = load_frigate_config()
        if not config or 'cameras' not in config:
            return jsonify({'success': False, 'error': 'No cameras configured'})
        
        results = {}
        for camera_name, camera_config in config['cameras'].items():
            try:
                # Extract IP from camera configuration
                camera_ip = extract_camera_ip(camera_config)
                if camera_ip:
                    ip_match = camera_ip.replace('http://', '').replace('https://', '')
                    import re
                    ip_search = re.search(r'([0-9.]+)', ip_match)
                    if ip_search:
                        ip_addr = ip_search.group(1)
                        
                        # Check if already has port forwarding
                        current_mapping = load_camera_port_mapping()
                        if ip_addr in current_mapping:
                            results[camera_name] = {
                                'status': 'exists',
                                'ip': ip_addr,
                                'port': current_mapping[ip_addr],
                                'message': f'Already forwarded on port {current_mapping[ip_addr]}'
                            }
                        else:
                            # Set up new port forwarding
                            assigned_port = auto_assign_camera_port(ip_addr)
                            if assigned_port:
                                update_docker_compose_ports(ip_addr, assigned_port)
                                results[camera_name] = {
                                    'status': 'success',
                                    'ip': ip_addr,
                                    'port': assigned_port,
                                    'message': f'Port forwarding set up on port {assigned_port}'
                                }
                            else:
                                results[camera_name] = {
                                    'status': 'failed',
                                    'ip': ip_addr,
                                    'message': 'Failed to assign port'
                                }
                    else:
                        results[camera_name] = {
                            'status': 'failed',
                            'message': 'Could not extract IP address'
                        }
                else:
                    results[camera_name] = {
                        'status': 'failed', 
                        'message': 'No camera IP found in configuration'
                    }
            except Exception as e:
                results[camera_name] = {
                    'status': 'error',
                    'message': str(e)
                }
        
        return jsonify({'success': True, 'results': results})
        
    except Exception as e:
        logger.error(f"Setup camera proxies error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/camera-proxy/status', methods=['GET'])
def get_camera_proxy_status():
    """Get current camera proxy port mappings and status"""
    try:
        config = load_frigate_config()
        camera_mapping = load_camera_port_mapping()
        
        status = {
            'proxy_mappings': camera_mapping,
            'available_ports': [],
            'camera_urls': {}
        }
        
        # Get available ports
        used_ports = set(int(port) for port in camera_mapping.values())
        for port in range(8101, 8121):
            if port not in used_ports:
                status['available_ports'].append(port)
        
        # Get camera URLs for web interface
        if config and 'cameras' in config:
            for camera_name, camera_config in config['cameras'].items():
                camera_url = extract_camera_ip(camera_config)
                if camera_url:
                    status['camera_urls'][camera_name] = camera_url
        
        return jsonify({'success': True, **status})
        
    except Exception as e:
        logger.error(f"Get camera proxy status error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/erik/map-config', methods=['GET'])
def get_map_config():
    """Get active yard map configuration and availability"""
    try:
        # Check for active yard map
        active_map_path = '/home/andrew/nvr/active_yard_map.png'
        active_config_path = '/home/andrew/nvr/active_yard_map.json'
        
        map_available = os.path.exists(active_map_path)
        config_data = {}
        
        if os.path.exists(active_config_path):
            with open(active_config_path, 'r') as f:
                config_data = json.load(f)
        
        return jsonify({
            'success': True,
            'map_available': map_available,
            'map_url': '/static/active_yard_map.png' if map_available else None,
            'boundaries': config_data.get('boundaries', {}),
            'coordinate_system': config_data.get('coordinate_system', 'unknown'),
            'timestamp': config_data.get('timestamp', None)
        })
        
    except Exception as e:
        logger.error(f"Get map config error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/erik/live-position', methods=['GET'])
def get_erik_live_position():
    """Get Erik's current live position for map display"""
    try:
        # For Phase 1, return placeholder data
        # This will be fully implemented in Phase 2 & 3
        
        # Get the most recent detection from our matches
        with matches_lock:
            if detection_matches:
                latest_detection = detection_matches[0]
                
                # Calculate time since last detection
                if 'received_time' in latest_detection:
                    received_time = datetime.fromisoformat(latest_detection['received_time'])
                    time_diff = (datetime.now() - received_time).total_seconds()
                    
                    # Only show position if detection is recent (< 10 seconds)
                    if time_diff < 10:
                        return jsonify({
                            'success': True,
                            'position': {
                                'pixel_x': 640,  # Placeholder - center of 1280px map
                                'pixel_y': 360,  # Placeholder - center of 720px map
                                'world_x': 0.0,  # Placeholder world coordinates
                                'world_y': 0.0   # Will be calculated in Phase 2
                            },
                            'detection_info': {
                                'camera': latest_detection.get('camera', 'unknown'),
                                'confidence': latest_detection.get('confidence', 0.0),
                                'timestamp': latest_detection.get('received_time')
                            },
                            'last_detection': {
                                'timestamp': latest_detection.get('received_time'),
                                'camera': latest_detection.get('camera')
                            }
                        })
        
        # No recent detection found
        return jsonify({
            'success': False,
            'position': None,
            'detection_info': None,
            'last_detection': None,
            'message': 'No recent Erik detections'
        })
        
    except Exception as e:
        logger.error(f"Get Erik live position error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/camera/<camera_name>/rtsp-stream')
def get_camera_rtsp_stream(camera_name):
    """Proxy RTSP stream as HTTP stream for browser compatibility"""
    try:
        # Camera RTSP configuration mapping
        camera_rtsp_map = {
            'front_door': 'rtsp://admin:hiver300@192.168.0.101:554/h264Preview_01_main',
            'backyard': 'rtsp://admin:hiver300@192.168.0.102:554/h264Preview_01_main',
            'side_yard': 'rtsp://admin:hiver300@192.168.0.103:554/h264Preview_01_main',
            'garage': 'rtsp://admin:hiver300@192.168.0.104:554/h264Preview_01_main'
        }
        
        if camera_name not in camera_rtsp_map:
            return jsonify({'error': 'Camera not found'}), 404
            
        rtsp_url = camera_rtsp_map[camera_name]
        
        # For now, return the direct RTSP URL that will be handled by port forwarding
        # The frontend will connect directly to the forwarded port
        camera_ip_map = {
            'front_door': {'ip': '192.168.0.101', 'port': 7101},
            'backyard': {'ip': '192.168.0.102', 'port': 7102},
            'side_yard': {'ip': '192.168.0.103', 'port': 7103},
            'garage': {'ip': '192.168.0.104', 'port': 7104}
        }
        
        config = camera_ip_map[camera_name]
        
        return jsonify({
            'success': True,
            'rtsp_url': rtsp_url,
            'http_stream_url': f"http://{request.host.split(':')[0]}:{config['port']}",
            'camera_ip': config['ip'],
            'forwarded_port': config['port']
        })
        
    except Exception as e:
        logger.error(f"RTSP stream error for {camera_name}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rtsp-forwarding/setup', methods=['POST'])
def setup_rtsp_forwarding():
    """Setup RTSP to HTTP forwarding using FFmpeg"""
    try:
        # Camera configuration
        cameras_config = [
            {'name': 'front_door', 'ip': '192.168.0.101', 'port': 7101},
            {'name': 'backyard', 'ip': '192.168.0.102', 'port': 7102},
            {'name': 'side_yard', 'ip': '192.168.0.103', 'port': 7103},
            {'name': 'garage', 'ip': '192.168.0.104', 'port': 7104}
        ]
        
        forwarding_info = []
        
        for camera in cameras_config:
            rtsp_url = f"rtsp://admin:hiver300@{camera['ip']}:554/h264Preview_01_main"
            http_port = camera['port']
            
            forwarding_info.append({
                'camera': camera['name'],
                'ip': camera['ip'],
                'rtsp_url': rtsp_url,
                'http_port': http_port,
                'setup_command': f"ffmpeg -i {rtsp_url} -c copy -f flv rtmp://localhost:{http_port}/live",
                'router_forwarding': f"Forward external port {http_port} to internal {request.host.split(':')[0]}:{http_port}"
            })
        
        return jsonify({
            'success': True,
            'message': 'RTSP forwarding configuration generated',
            'cameras': forwarding_info,
            'instructions': {
                'router_setup': 'Forward these ports on your router:',
                'ports_to_forward': [c['port'] for c in cameras_config],
                'pattern': 'IP ending in 101 -> port 7101, IP ending in 102 -> port 7102, etc.'
            }
        })
        
    except Exception as e:
        logger.error(f"RTSP forwarding setup error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/static/active_yard_map.png')
def serve_active_yard_map():
    """Serve the active yard map image"""
    try:
        active_map_path = '/home/andrew/nvr/active_yard_map.png'
        if os.path.exists(active_map_path):
            return send_from_directory('/home/andrew/nvr', 'active_yard_map.png')
        else:
            # Return a placeholder image or 404
            return jsonify({'error': 'No active yard map available'}), 404
    except Exception as e:
        logger.error(f"Serve active yard map error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(413)
def too_large(e):
    flash('File too large (max 16MB)', 'error')
    return redirect(url_for('index'))

if __name__ == '__main__':
    import argparse
    import sys
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Erik Image Manager')
    parser.add_argument('--dev', action='store_true', help='Run in development mode')
    parser.add_argument('--port', type=int, default=9000, help='Port to run on')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    args = parser.parse_args()
    
    if args.dev:
        logger.info(f"🚀 Starting Erik Image Manager in DEVELOPMENT mode")
        logger.info(f"   URL: http://localhost:{args.port}")
        logger.info(f"   Upload folder: {UPLOAD_FOLDER}")
        logger.info(f"   Mesh folder: {MESH_FOLDER}")
        logger.info(f"   Frigate config: {FRIGATE_CONFIG_PATH}")
        app.run(host=args.host, port=args.port, debug=True)
    else:
        logger.info(f"Starting Erik Image Manager on port {args.port}")
        logger.info(f"Upload folder: {UPLOAD_FOLDER}")
        app.run(host=args.host, port=args.port, debug=False)