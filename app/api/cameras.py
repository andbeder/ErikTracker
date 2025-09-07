"""
Camera Management API Blueprint
Handles RTSP streaming, camera proxies, and camera operations
"""

import os
import json
import base64
import logging
from flask import Blueprint, request, jsonify, current_app, Response

logger = logging.getLogger(__name__)

bp = Blueprint('cameras', __name__, url_prefix='/api')

@bp.route('/camera-proxy/setup-all', methods=['POST'])
def setup_all_camera_proxies():
    """Set up nginx proxies for all configured cameras"""
    try:
        frigate_service = current_app.frigate_service
        camera_service = current_app.camera_service
        
        # Get all cameras from Frigate config
        camera_names = frigate_service.get_camera_names()
        
        if not camera_names:
            return jsonify({'error': 'No cameras configured in Frigate'}), 400
        
        results = []
        success_count = 0
        
        for camera_name in camera_names:
            try:
                camera_config = frigate_service.get_camera_config(camera_name)
                if not camera_config:
                    results.append({
                        'camera': camera_name,
                        'status': 'error',
                        'message': 'Camera config not found'
                    })
                    continue
                
                # Extract camera IP from RTSP URL
                camera_ip = None
                if 'ffmpeg' in camera_config and 'inputs' in camera_config['ffmpeg']:
                    for input_stream in camera_config['ffmpeg']['inputs']:
                        if 'path' in input_stream:
                            import re
                            ip_match = re.search(r'@([0-9.]+):', input_stream['path'])
                            if ip_match:
                                camera_ip = ip_match.group(1)
                                break
                
                if not camera_ip:
                    results.append({
                        'camera': camera_name,
                        'status': 'error',
                        'message': 'Could not extract IP from RTSP URL'
                    })
                    continue
                
                # Create proxy configuration
                proxy_result = camera_service.create_camera_proxy(camera_name, camera_ip)
                
                if 'error' in proxy_result:
                    results.append({
                        'camera': camera_name,
                        'status': 'error',
                        'message': proxy_result['error']
                    })
                else:
                    results.append({
                        'camera': camera_name,
                        'status': 'success',
                        'proxy_port': proxy_result['proxy_port'],
                        'proxy_url': proxy_result['proxy_url']
                    })
                    success_count += 1
                    
            except Exception as e:
                results.append({
                    'camera': camera_name,
                    'status': 'error',
                    'message': str(e)
                })
        
        return jsonify({
            'status': 'completed',
            'total_cameras': len(camera_names),
            'successful_setups': success_count,
            'results': results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/camera-proxy/status', methods=['GET'])
def get_camera_proxy_status():
    """Get status of all camera proxies"""
    try:
        camera_service = current_app.camera_service
        
        # Get used proxy ports
        used_ports = camera_service.get_used_proxy_ports()
        
        # Get camera information from Frigate
        frigate_service = current_app.frigate_service
        camera_names = frigate_service.get_camera_names()
        
        proxies = []
        for camera_name in camera_names:
            camera_config = frigate_service.get_camera_config(camera_name)
            if camera_config:
                web_url = frigate_service.extract_camera_ip(camera_config)
                if web_url and 'localhost:' in web_url:
                    port = web_url.split(':')[-1]
                    proxies.append({
                        'camera': camera_name,
                        'port': port,
                        'url': web_url,
                        'status': 'active' if int(port) in used_ports else 'inactive'
                    })
        
        return jsonify({
            'proxies': proxies,
            'total_proxies': len(proxies),
            'used_ports': list(used_ports)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/camera/<camera_name>/rtsp-stream')
def get_rtsp_stream_info(camera_name):
    """Get RTSP stream information for a camera"""
    try:
        frigate_service = current_app.frigate_service
        camera_config = frigate_service.get_camera_config(camera_name)
        
        if not camera_config:
            return jsonify({'error': f'Camera {camera_name} not found'}), 404
        
        # Extract RTSP streams from camera config
        streams = []
        if 'ffmpeg' in camera_config and 'inputs' in camera_config['ffmpeg']:
            for i, input_stream in enumerate(camera_config['ffmpeg']['inputs']):
                if 'path' in input_stream:
                    streams.append({
                        'stream_id': i,
                        'rtsp_url': input_stream['path'],
                        'roles': input_stream.get('roles', [])
                    })
        
        return jsonify({
            'camera': camera_name,
            'streams': streams,
            'total_streams': len(streams)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/rtsp-forwarding/setup', methods=['POST'])
def setup_rtsp_forwarding():
    """Set up RTSP stream forwarding for external access"""
    try:
        data = request.json
        camera_name = data.get('camera_name')
        stream_id = data.get('stream_id', 0)
        external_port = data.get('external_port', 5554)
        
        if not camera_name:
            return jsonify({'error': 'Camera name required'}), 400
        
        frigate_service = current_app.frigate_service
        camera_service = current_app.camera_service
        
        # Get camera configuration
        camera_config = frigate_service.get_camera_config(camera_name)
        if not camera_config:
            return jsonify({'error': f'Camera {camera_name} not found'}), 404
        
        # Get RTSP URL for specified stream
        rtsp_url = None
        if 'ffmpeg' in camera_config and 'inputs' in camera_config['ffmpeg']:
            inputs = camera_config['ffmpeg']['inputs']
            if stream_id < len(inputs) and 'path' in inputs[stream_id]:
                rtsp_url = inputs[stream_id]['path']
        
        if not rtsp_url:
            return jsonify({'error': f'Stream {stream_id} not found for camera {camera_name}'}), 404
        
        # Set up forwarding
        result = camera_service.setup_rtsp_forwarding(rtsp_url, external_port)
        
        if 'error' in result:
            return jsonify({'error': result['error']}), 500
        
        return jsonify({
            'status': 'success',
            'camera': camera_name,
            'stream_id': stream_id,
            'forwarding_info': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/rtsp-forwarding/status', methods=['GET'])
def get_rtsp_forwarding_status():
    """Get status of RTSP stream forwarding"""
    camera_service = current_app.camera_service
    status = camera_service.get_forwarding_status()
    return jsonify(status)

@bp.route('/rtsp-forwarding/stop/<stream_id>', methods=['POST'])
def stop_rtsp_forwarding(stream_id):
    """Stop RTSP stream forwarding"""
    camera_service = current_app.camera_service
    
    if camera_service.stop_rtsp_forwarding(stream_id):
        return jsonify({
            'status': 'success',
            'message': f'Stopped forwarding for stream {stream_id}'
        })
    else:
        return jsonify({'error': 'Failed to stop forwarding'}), 500

@bp.route('/camera/<camera_name>/test-connection', methods=['POST'])
def test_camera_connection(camera_name):
    """Test connection to a camera"""
    try:
        frigate_service = current_app.frigate_service
        camera_service = current_app.camera_service
        
        # Get camera configuration
        camera_config = frigate_service.get_camera_config(camera_name)
        if not camera_config:
            return jsonify({'error': f'Camera {camera_name} not found'}), 404
        
        # Test both web interface and RTSP stream
        results = {
            'camera': camera_name,
            'tests': []
        }
        
        # Test web interface
        web_url = frigate_service.extract_camera_ip(camera_config)
        if web_url:
            web_result = camera_service.test_camera_connection(web_url)
            results['tests'].append({
                'type': 'web_interface',
                'url': web_url,
                'result': web_result
            })
        
        # Test RTSP streams
        if 'ffmpeg' in camera_config and 'inputs' in camera_config['ffmpeg']:
            for i, input_stream in enumerate(camera_config['ffmpeg']['inputs']):
                if 'path' in input_stream:
                    rtsp_url = input_stream['path']
                    rtsp_result = camera_service.test_camera_connection(rtsp_url)
                    results['tests'].append({
                        'type': 'rtsp_stream',
                        'stream_id': i,
                        'url': rtsp_url,
                        'result': rtsp_result
                    })
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/camera/<camera_name>/snapshot', methods=['POST'])
def capture_camera_snapshot(camera_name):
    """Capture snapshot from camera"""
    try:
        frigate_service = current_app.frigate_service
        camera_service = current_app.camera_service
        
        # Get camera RTSP URL
        camera_config = frigate_service.get_camera_config(camera_name)
        if not camera_config:
            return jsonify({'error': f'Camera {camera_name} not found'}), 404
        
        # Get first RTSP stream
        rtsp_url = None
        if 'ffmpeg' in camera_config and 'inputs' in camera_config['ffmpeg']:
            for input_stream in camera_config['ffmpeg']['inputs']:
                if 'path' in input_stream:
                    rtsp_url = input_stream['path']
                    break
        
        if not rtsp_url:
            return jsonify({'error': 'No RTSP stream found for camera'}), 404
        
        # Capture snapshot
        image_data = camera_service.get_camera_snapshot(rtsp_url)
        
        if image_data:
            # Return as base64 encoded image
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            return jsonify({
                'status': 'success',
                'camera': camera_name,
                'image_data': image_base64,
                'image_format': 'jpeg'
            })
        else:
            return jsonify({'error': 'Failed to capture snapshot'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/cameras/discover', methods=['POST'])
def discover_cameras():
    """Discover cameras on the network"""
    try:
        data = request.json or {}
        network_range = data.get('network_range', '192.168.0.0/24')
        
        camera_service = current_app.camera_service
        discovered = camera_service.discover_cameras(network_range)
        
        return jsonify({
            'discovered_cameras': discovered,
            'total_found': len(discovered)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config/external-ip', methods=['GET'])
def get_external_ip():
    """Get external IP configuration"""
    external_ip = current_app.config.get('EXTERNAL_IP', '24.147.52.91')
    
    return jsonify({
        'external_ip': external_ip,
        'source': 'configuration'
    })

@bp.route('/<camera_name>/latest.jpg', methods=['GET'])
def get_camera_latest_image(camera_name):
    """Get latest image from camera for live feeds"""
    try:
        import requests
        from flask import Response
        
        # Try to get image from Frigate first
        frigate_url = f"http://localhost:5000/api/{camera_name}/latest.jpg"
        
        try:
            # Add query parameters if provided (like timestamp, height)
            params = dict(request.args)
            
            response = requests.get(frigate_url, params=params, timeout=5)
            if response.status_code == 200:
                return Response(
                    response.content,
                    mimetype='image/jpeg',
                    headers={
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Pragma': 'no-cache',
                        'Expires': '0'
                    }
                )
        except requests.RequestException:
            pass
        
        # Fallback: Try to use camera service to get snapshot
        camera_service = current_app.camera_service
        frigate_service = current_app.frigate_service
        
        # Get camera configuration from Frigate
        config = frigate_service.load_config()
        if config and 'cameras' in config and camera_name in config['cameras']:
            camera_config = config['cameras'][camera_name]
            
            # Extract RTSP URL from camera config
            if 'ffmpeg' in camera_config and 'inputs' in camera_config['ffmpeg']:
                inputs = camera_config['ffmpeg']['inputs']
                if inputs and len(inputs) > 0:
                    rtsp_url = inputs[0].get('path')
                    if rtsp_url:
                        # Get snapshot from camera service
                        snapshot_data = camera_service.get_camera_snapshot(rtsp_url)
                        if snapshot_data:
                            return Response(
                                snapshot_data,
                                mimetype='image/jpeg',
                                headers={
                                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                                    'Pragma': 'no-cache',
                                    'Expires': '0'
                                }
                            )
        
        # If all else fails, return a placeholder image with 503 status
        placeholder_img = generate_placeholder_image(camera_name)
        if placeholder_img:
            return Response(
                placeholder_img,
                mimetype='image/jpeg',
                headers={
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            ), 503
        else:
            return jsonify({'error': f'Camera {camera_name} not available'}), 503
        
    except Exception as e:
        logger.error(f"Error getting camera image for {camera_name}: {e}")
        return Response(
            generate_placeholder_image(camera_name, error=True),
            mimetype='image/jpeg'
        ), 500

def generate_placeholder_image(camera_name, error=False):
    """Generate a placeholder image for camera when unavailable"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        
        # Create a simple placeholder image
        width, height = 640, 480
        
        if error:
            color = (200, 100, 100)  # Light red for error
            text = f"❌ {camera_name.replace('_', ' ').title()}\nCamera Error"
        else:
            color = (100, 100, 100)  # Gray for offline
            text = f"📷 {camera_name.replace('_', ' ').title()}\nCamera Offline"
        
        img = Image.new('RGB', (width, height), color=color)
        draw = ImageDraw.Draw(img)
        
        # Add text
        try:
            # Try to use a default font
            font = ImageFont.load_default()
        except:
            font = None
        
        bbox = draw.textbbox((0, 0), text, font=font) if font else (0, 0, 100, 40)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        draw.text((x, y), text, fill=(255, 255, 255), font=font, align='center')
        
        # Save to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        return buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating placeholder image: {e}")
        # Return minimal response
        return b''

@bp.route('/<camera_name>/stream.m3u8', methods=['GET'])
def get_camera_hls_stream(camera_name):
    """Proxy HLS stream from Frigate to avoid CORS issues"""
    try:
        import requests
        
        # Proxy request to Frigate HLS endpoint
        frigate_url = f"http://localhost:5000/live/hls/{camera_name}/index.m3u8"
        
        try:
            # Forward any query parameters
            params = dict(request.args)
            
            response = requests.get(frigate_url, params=params, timeout=10)
            if response.status_code == 200:
                return Response(
                    response.content,
                    mimetype='application/x-mpegURL',
                    headers={
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'GET, OPTIONS',
                        'Access-Control-Allow-Headers': 'Content-Type',
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Pragma': 'no-cache',
                        'Expires': '0'
                    }
                )
            else:
                return jsonify({'error': f'Frigate returned {response.status_code}'}), response.status_code
                
        except requests.RequestException as e:
            return jsonify({'error': f'Failed to connect to Frigate: {str(e)}'}), 503
        
    except Exception as e:
        logger.error(f"Error proxying HLS stream for {camera_name}: {e}")
        return jsonify({'error': 'Stream proxy error'}), 500

@bp.route('/<camera_name>/segments/<path:segment_path>', methods=['GET'])  
def get_camera_hls_segment(camera_name, segment_path):
    """Proxy HLS segments from Frigate"""
    try:
        import requests
        
        # Proxy request to Frigate HLS segment
        frigate_url = f"http://localhost:5000/live/hls/{camera_name}/{segment_path}"
        
        try:
            response = requests.get(frigate_url, timeout=10, stream=True)
            if response.status_code == 200:
                return Response(
                    response.iter_content(chunk_size=8192),
                    mimetype='video/mp2t',
                    headers={
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'GET, OPTIONS',
                        'Access-Control-Allow-Headers': 'Content-Type',
                        'Cache-Control': 'no-cache'
                    }
                )
            else:
                return jsonify({'error': f'Segment not found'}), response.status_code
                
        except requests.RequestException as e:
            return jsonify({'error': f'Failed to get segment: {str(e)}'}), 503
        
    except Exception as e:
        logger.error(f"Error proxying HLS segment {segment_path} for {camera_name}: {e}")
        return jsonify({'error': 'Segment proxy error'}), 500

@bp.route('/<camera_name>/mjpeg', methods=['GET'])
def get_camera_mjpeg_stream(camera_name):
    """Provide MJPEG stream for camera"""
    try:
        frigate_service = current_app.frigate_service
        
        def generate_mjpeg():
            import time
            import requests
            
            while True:
                try:
                    # Get latest frame from Frigate
                    frigate_url = f"http://localhost:5000/api/{camera_name}/latest.jpg"
                    response = requests.get(frigate_url, timeout=5)
                    
                    if response.status_code == 200:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + 
                               response.content + b'\r\n')
                    else:
                        # If Frigate fails, try local snapshot
                        local_url = f"http://localhost:9001/api/{camera_name}/latest.jpg"
                        local_response = requests.get(local_url, timeout=5)
                        if local_response.status_code == 200:
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + 
                                   local_response.content + b'\r\n')
                    
                    time.sleep(0.1)  # 10 FPS
                    
                except Exception as e:
                    logger.warning(f"MJPEG frame error for {camera_name}: {e}")
                    time.sleep(1)  # Wait longer on error
        
        return Response(
            generate_mjpeg(),
            mimetype='multipart/x-mixed-replace; boundary=frame',
            headers={
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache'
            }
        )
        
    except Exception as e:
        logger.error(f"Error creating MJPEG stream for {camera_name}: {e}")
        return jsonify({'error': 'MJPEG stream error'}), 500

@bp.route('/<camera_name>/direct-stream.m3u8', methods=['GET'])
def get_direct_rtsp_hls_stream(camera_name):
    """Convert camera RTSP stream directly to HLS"""
    try:
        import subprocess
        import threading
        import time
        import tempfile
        
        frigate_service = current_app.frigate_service
        
        # Get camera RTSP URL from Frigate config
        camera_config = frigate_service.get_camera_config(camera_name)
        if not camera_config:
            return jsonify({'error': f'Camera {camera_name} not found'}), 404
        
        rtsp_url = None
        if 'ffmpeg' in camera_config and 'inputs' in camera_config['ffmpeg']:
            for input_stream in camera_config['ffmpeg']['inputs']:
                if 'path' in input_stream and input_stream['path'].startswith('rtsp://'):
                    rtsp_url = input_stream['path']
                    break
        
        if not rtsp_url:
            return jsonify({'error': f'No RTSP URL found for camera {camera_name}'}), 404
        
        logger.info(f"Starting direct HLS conversion for {camera_name} from {rtsp_url}")
        
        # Create temporary directory for HLS segments
        hls_dir = f"/tmp/hls_streams/{camera_name}"
        os.makedirs(hls_dir, exist_ok=True)
        
        playlist_path = os.path.join(hls_dir, 'playlist.m3u8')
        
        # Start FFmpeg process to convert RTSP to HLS
        def start_hls_conversion():
            try:
                cmd = [
                    'ffmpeg',
                    '-i', rtsp_url,
                    '-c:v', 'libx264',           # Video codec
                    '-preset', 'ultrafast',      # Fast encoding
                    '-tune', 'zerolatency',      # Low latency
                    '-g', '30',                  # GOP size
                    '-sc_threshold', '0',        # Disable scene detection
                    '-f', 'hls',                 # HLS format
                    '-hls_time', '2',            # 2 second segments
                    '-hls_list_size', '5',       # Keep 5 segments
                    '-hls_flags', 'delete_segments+append_list', # Clean up old segments
                    '-hls_segment_filename', os.path.join(hls_dir, 'segment_%03d.ts'),
                    playlist_path,
                    '-y'  # Overwrite output
                ]
                
                logger.info(f"Starting FFmpeg command for {camera_name}")
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Store process for cleanup
                if not hasattr(current_app, 'hls_processes'):
                    current_app.hls_processes = {}
                current_app.hls_processes[camera_name] = process
                
                # Monitor process
                for i in range(30):  # Wait up to 30 seconds for playlist
                    if os.path.exists(playlist_path):
                        logger.info(f"HLS playlist created for {camera_name}")
                        break
                    time.sleep(1)
                else:
                    logger.warning(f"HLS playlist not created within timeout for {camera_name}")
                
            except Exception as e:
                logger.error(f"FFmpeg conversion error for {camera_name}: {e}")
        
        # Start conversion in background thread
        if not os.path.exists(playlist_path):
            conversion_thread = threading.Thread(target=start_hls_conversion, daemon=True)
            conversion_thread.start()
            
            # Wait briefly for playlist to be created
            for i in range(10):
                if os.path.exists(playlist_path):
                    break
                time.sleep(0.5)
        
        # If playlist exists, serve it with corrected URLs
        if os.path.exists(playlist_path):
            with open(playlist_path, 'r') as f:
                playlist_content = f.read()
            
            # Replace segment references with proper URLs
            lines = playlist_content.split('\n')
            corrected_lines = []
            for line in lines:
                if line.endswith('.ts'):
                    # Convert segment filename to full URL
                    corrected_lines.append(f'/api/{camera_name}/hls-segments/{line}')
                else:
                    corrected_lines.append(line)
            
            corrected_playlist = '\n'.join(corrected_lines)
            
            return Response(
                corrected_playlist,
                mimetype='application/x-mpegURL',
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache'
                }
            )
        else:
            return jsonify({'error': 'HLS conversion still starting, please try again in a few seconds'}), 202
        
    except Exception as e:
        logger.error(f"Error creating direct HLS stream for {camera_name}: {e}")
        return jsonify({'error': f'Direct stream error: {str(e)}'}), 500

@bp.route('/<camera_name>/hls-segments/<path:segment_name>', methods=['GET'])
def get_hls_segment(camera_name, segment_name):
    """Serve HLS segments for direct RTSP conversion"""
    try:
        hls_dir = f"/tmp/hls_streams/{camera_name}"
        segment_path = os.path.join(hls_dir, segment_name)
        
        if not os.path.exists(segment_path):
            return jsonify({'error': 'Segment not found'}), 404
        
        with open(segment_path, 'rb') as f:
            segment_data = f.read()
        
        return Response(
            segment_data,
            mimetype='video/mp2t',
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Cache-Control': 'max-age=10'
            }
        )
        
    except Exception as e:
        logger.error(f"Error serving HLS segment {segment_name} for {camera_name}: {e}")
        return jsonify({'error': 'Segment error'}), 500

@bp.route('/<camera_name>/rtsp-info', methods=['GET'])
def get_camera_rtsp_info(camera_name):
    """Get RTSP URL and info for direct camera connection"""
    try:
        frigate_service = current_app.frigate_service
        
        # Get camera RTSP URL from Frigate config
        camera_config = frigate_service.get_camera_config(camera_name)
        if not camera_config:
            return jsonify({'error': f'Camera {camera_name} not found'}), 404
        
        rtsp_streams = []
        if 'ffmpeg' in camera_config and 'inputs' in camera_config['ffmpeg']:
            for i, input_stream in enumerate(camera_config['ffmpeg']['inputs']):
                if 'path' in input_stream and input_stream['path'].startswith('rtsp://'):
                    rtsp_streams.append({
                        'stream_id': i,
                        'rtsp_url': input_stream['path'],
                        'roles': input_stream.get('roles', [])
                    })
        
        if not rtsp_streams:
            return jsonify({'error': f'No RTSP URLs found for camera {camera_name}'}), 404
        
        return jsonify({
            'camera_name': camera_name,
            'rtsp_streams': rtsp_streams,
            'hls_endpoint': f'/api/{camera_name}/direct-stream.m3u8',
            'mjpeg_endpoint': f'/api/{camera_name}/mjpeg'
        })
        
    except Exception as e:
        logger.error(f"Error getting RTSP info for {camera_name}: {e}")
        return jsonify({'error': f'RTSP info error: {str(e)}'}), 500

@bp.route('/<camera_name>/direct-rtsp-hls', methods=['GET'])
def get_direct_rtsp_hls(camera_name):
    """Convert direct RTSP feed to HLS using forwarded ports"""
    try:
        import subprocess
        import threading
        import time
        import tempfile
        
        # Map camera names to forwarded RTSP ports
        rtsp_port_map = {
            'front_door': 5101,
            'backyard': 5102,
            'side_yard': 5103,
            'garage': 5104
        }
        
        if camera_name not in rtsp_port_map:
            return jsonify({'error': f'No direct RTSP port configured for {camera_name}'}), 404
        
        rtsp_port = rtsp_port_map[camera_name]
        # Include authentication credentials for camera access
        rtsp_url = f"rtsp://admin:hiver300@localhost:{rtsp_port}/h264Preview_01_main"
        
        logger.info(f"Starting direct RTSP HLS conversion for {camera_name} from port {rtsp_port}")
        
        # Create temporary directory for HLS segments
        hls_dir = f"/tmp/direct_hls/{camera_name}"
        os.makedirs(hls_dir, exist_ok=True)
        
        playlist_path = os.path.join(hls_dir, 'playlist.m3u8')
        
        # Start FFmpeg process to convert RTSP to HLS
        def start_direct_hls_conversion():
            try:
                cmd = [
                    'ffmpeg',
                    '-f', 'rtsp',
                    '-rtsp_transport', 'tcp',
                    '-i', rtsp_url,
                    '-c:v', 'copy',              # Copy video codec (faster)
                    '-an',                       # No audio for now (avoids codec issues)
                    '-f', 'hls',                # HLS format
                    '-hls_time', '2',           # 2 second segments
                    '-hls_list_size', '3',      # Keep 3 segments
                    '-hls_flags', 'delete_segments+append_list',
                    '-hls_segment_filename', os.path.join(hls_dir, 'segment_%03d.ts'),
                    playlist_path
                ]
                
                logger.info(f"Starting FFmpeg for {camera_name}: {' '.join(cmd)}")
                
                # Start FFmpeg process
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Wait a moment for FFmpeg to create initial segments
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"Error starting HLS conversion for {camera_name}: {e}")
        
        # Start conversion in background thread with app context
        with current_app.app_context():
            conversion_thread = threading.Thread(target=start_direct_hls_conversion)
            conversion_thread.daemon = True
            conversion_thread.start()
        
        # Wait for playlist to be created
        max_wait = 10  # seconds
        wait_count = 0
        while not os.path.exists(playlist_path) and wait_count < max_wait:
            time.sleep(1)
            wait_count += 1
        
        if not os.path.exists(playlist_path):
            return jsonify({'error': 'Failed to create HLS playlist'}), 500
        
        # Read and serve the playlist
        with open(playlist_path, 'r') as f:
            playlist_content = f.read()
        
        # Update segment paths to point to our API endpoint
        lines = playlist_content.split('\n')
        corrected_lines = []
        for line in lines:
            if line.endswith('.ts'):
                corrected_lines.append(f'/api/{camera_name}/direct-hls-segments/{line}')
            else:
                corrected_lines.append(line)
        
        return '\n'.join(corrected_lines), 200, {
            'Content-Type': 'application/vnd.apple.mpegurl',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'Access-Control-Allow-Origin': '*'
        }
        
    except Exception as e:
        logger.error(f"Direct RTSP HLS error for {camera_name}: {str(e)}")
        return jsonify({'error': f'Direct RTSP HLS error: {str(e)}'}), 500

@bp.route('/<camera_name>/direct-hls-segments/<path:segment_name>', methods=['GET'])
def get_direct_hls_segment(camera_name, segment_name):
    """Serve HLS segments for direct RTSP conversion"""
    try:
        hls_dir = f"/tmp/direct_hls/{camera_name}"
        segment_path = os.path.join(hls_dir, segment_name)
        
        if not os.path.exists(segment_path):
            return jsonify({'error': 'Segment not found'}), 404
        
        with open(segment_path, 'rb') as f:
            segment_data = f.read()
        
        return segment_data, 200, {
            'Content-Type': 'video/mp2t',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'Access-Control-Allow-Origin': '*'
        }
        
    except Exception as e:
        logger.error(f"Direct HLS segment error: {str(e)}")
        return jsonify({'error': 'Segment error'}), 500