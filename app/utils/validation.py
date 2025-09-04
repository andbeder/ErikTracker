"""
Validation utilities
Common validation functions used across the application
"""

import re
import os
import logging
from typing import Dict, Any, List, Tuple, Union
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def validate_file_upload(file, allowed_extensions: set, max_size_mb: float = 16.0) -> Tuple[bool, str]:
    """Validate uploaded file
    
    Args:
        file: File object from request
        allowed_extensions: Set of allowed file extensions
        max_size_mb: Maximum file size in megabytes
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file or file.filename == '':
        return False, "No file provided"
    
    # Check file extension
    if '.' not in file.filename:
        return False, "File has no extension"
    
    extension = file.filename.rsplit('.', 1)[1].lower()
    if extension not in allowed_extensions:
        return False, f"File type '.{extension}' not allowed. Allowed types: {', '.join(sorted(allowed_extensions))}"
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer
    
    max_size_bytes = max_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
        return False, f"File too large ({file_size / (1024*1024):.1f}MB). Maximum size: {max_size_mb}MB"
    
    if file_size == 0:
        return False, "File is empty"
    
    return True, "File is valid"

def validate_ip_address(ip_address: str) -> Tuple[bool, str]:
    """Validate IP address format
    
    Args:
        ip_address: IP address string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not ip_address:
        return False, "IP address cannot be empty"
    
    # IPv4 pattern
    ipv4_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    
    if re.match(ipv4_pattern, ip_address):
        return True, "Valid IPv4 address"
    
    # Check for localhost
    if ip_address.lower() in ['localhost', '127.0.0.1']:
        return True, "Valid localhost address"
    
    return False, f"Invalid IP address format: {ip_address}"

def validate_port(port: Union[str, int]) -> Tuple[bool, str]:
    """Validate port number
    
    Args:
        port: Port number to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        port_num = int(port)
        
        if port_num < 1 or port_num > 65535:
            return False, f"Port must be between 1 and 65535, got {port_num}"
        
        # Check for common restricted ports
        restricted_ports = {22, 23, 25, 53, 80, 110, 143, 443, 993, 995}
        if port_num in restricted_ports:
            logger.warning(f"Port {port_num} is a commonly restricted system port")
        
        return True, f"Valid port number: {port_num}"
        
    except (ValueError, TypeError):
        return False, f"Invalid port format: {port}"

def validate_url(url: str, allowed_schemes: set = None) -> Tuple[bool, str]:
    """Validate URL format
    
    Args:
        url: URL string to validate
        allowed_schemes: Set of allowed URL schemes (default: http, https, rtsp)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "URL cannot be empty"
    
    if not allowed_schemes:
        allowed_schemes = {'http', 'https', 'rtsp'}
    
    try:
        parsed = urlparse(url)
        
        if not parsed.scheme:
            return False, "URL missing scheme (e.g., http://)"
        
        if parsed.scheme.lower() not in allowed_schemes:
            return False, f"URL scheme '{parsed.scheme}' not allowed. Allowed: {', '.join(sorted(allowed_schemes))}"
        
        if not parsed.netloc:
            return False, "URL missing host/domain"
        
        return True, f"Valid {parsed.scheme.upper()} URL"
        
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"

def validate_rtsp_url(rtsp_url: str) -> Tuple[bool, str]:
    """Validate RTSP URL format
    
    Args:
        rtsp_url: RTSP URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    is_valid_url, url_message = validate_url(rtsp_url, {'rtsp'})
    if not is_valid_url:
        return False, url_message
    
    # Additional RTSP-specific validation
    parsed = urlparse(rtsp_url)
    
    # Check for credentials in URL
    if '@' in parsed.netloc:
        # URL contains credentials
        if not re.match(r'.+:.+@.+', parsed.netloc):
            return False, "Invalid RTSP URL credentials format"
    
    # Check port if specified
    if parsed.port:
        is_valid_port, port_message = validate_port(parsed.port)
        if not is_valid_port:
            return False, f"RTSP URL has invalid port: {port_message}"
    
    return True, "Valid RTSP URL"

def validate_camera_config(camera_config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate camera configuration
    
    Args:
        camera_config: Camera configuration dictionary
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Check required fields
    required_fields = ['ffmpeg', 'detect']
    for field in required_fields:
        if field not in camera_config:
            errors.append(f"Missing required field: {field}")
    
    # Validate ffmpeg configuration
    if 'ffmpeg' in camera_config:
        ffmpeg_config = camera_config['ffmpeg']
        
        if 'inputs' not in ffmpeg_config:
            errors.append("Missing ffmpeg.inputs configuration")
        else:
            inputs = ffmpeg_config['inputs']
            if not isinstance(inputs, list) or len(inputs) == 0:
                errors.append("ffmpeg.inputs must be a non-empty list")
            else:
                for i, input_config in enumerate(inputs):
                    if 'path' not in input_config:
                        errors.append(f"ffmpeg.inputs[{i}] missing 'path' field")
                    else:
                        # Validate RTSP URL if it looks like one
                        path = input_config['path']
                        if path.startswith('rtsp://'):
                            is_valid, error = validate_rtsp_url(path)
                            if not is_valid:
                                errors.append(f"ffmpeg.inputs[{i}].path: {error}")
    
    # Validate detect configuration
    if 'detect' in camera_config:
        detect_config = camera_config['detect']
        if 'width' in detect_config and 'height' in detect_config:
            try:
                width = int(detect_config['width'])
                height = int(detect_config['height'])
                if width <= 0 or height <= 0:
                    errors.append("detect width and height must be positive integers")
                if width > 4000 or height > 4000:
                    logger.warning(f"Detect resolution {width}x{height} is very high")
            except (ValueError, TypeError):
                errors.append("detect width and height must be valid integers")
    
    return len(errors) == 0, errors

def validate_mesh_generation_params(params: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate mesh generation parameters
    
    Args:
        params: Mesh generation parameters
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Validate grid resolution
    if 'grid_resolution' in params:
        try:
            resolution = float(params['grid_resolution'])
            if resolution <= 0:
                errors.append("grid_resolution must be positive")
            if resolution > 10.0:
                errors.append("grid_resolution too large (max 10.0)")
        except (ValueError, TypeError):
            errors.append("grid_resolution must be a valid number")
    
    # Validate max points
    if 'max_points' in params:
        try:
            max_points = int(params['max_points'])
            if max_points <= 0:
                errors.append("max_points must be positive")
            if max_points > 100000000:  # 100M points
                errors.append("max_points too large (max 100M)")
        except (ValueError, TypeError):
            errors.append("max_points must be a valid integer")
    
    # Validate projection
    if 'projection' in params:
        valid_projections = {'xy', 'xz', 'yz'}
        if params['projection'] not in valid_projections:
            errors.append(f"projection must be one of: {', '.join(valid_projections)}")
    
    # Validate output dimensions
    for dim in ['output_width', 'output_height']:
        if dim in params:
            try:
                value = int(params[dim])
                if value <= 0:
                    errors.append(f"{dim} must be positive")
                if value > 8192:
                    errors.append(f"{dim} too large (max 8192)")
            except (ValueError, TypeError):
                errors.append(f"{dim} must be a valid integer")
    
    return len(errors) == 0, errors

def validate_json_structure(data: Any, required_keys: List[str], optional_keys: List[str] = None) -> Tuple[bool, List[str]]:
    """Validate JSON data structure
    
    Args:
        data: Data to validate
        required_keys: List of required keys
        optional_keys: List of optional keys
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    if not isinstance(data, dict):
        return False, ["Data must be a JSON object/dictionary"]
    
    # Check required keys
    for key in required_keys:
        if key not in data:
            errors.append(f"Missing required field: {key}")
    
    # Check for unknown keys if optional_keys is provided
    if optional_keys is not None:
        allowed_keys = set(required_keys + optional_keys)
        extra_keys = set(data.keys()) - allowed_keys
        if extra_keys:
            errors.append(f"Unknown fields: {', '.join(sorted(extra_keys))}")
    
    return len(errors) == 0, errors

def validate_session_id(session_id: str) -> Tuple[bool, str]:
    """Validate session ID format
    
    Args:
        session_id: Session ID to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not session_id:
        return False, "Session ID cannot be empty"
    
    if not isinstance(session_id, str):
        return False, "Session ID must be a string"
    
    # Check UUID format
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if re.match(uuid_pattern, session_id.lower()):
        return True, "Valid UUID session ID"
    
    # Allow simple alphanumeric session IDs
    if re.match(r'^[a-zA-Z0-9_-]+$', session_id) and len(session_id) >= 4:
        return True, "Valid session ID"
    
    return False, "Invalid session ID format (must be UUID or alphanumeric)"

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    if not filename:
        return "unnamed_file"
    
    # Remove dangerous characters
    sanitized = re.sub(r'[^\w\s.-]', '', filename)
    
    # Replace spaces with underscores
    sanitized = re.sub(r'\s+', '_', sanitized)
    
    # Limit length
    if len(sanitized) > 100:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:100-len(ext)] + ext
    
    return sanitized or "unnamed_file"