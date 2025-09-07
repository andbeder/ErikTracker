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