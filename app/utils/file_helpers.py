"""
File operation helper utilities
Common file operations used across the application
"""

import os
import io
import base64
import shutil
from pathlib import Path
from datetime import datetime
from PIL import Image
import logging

logger = logging.getLogger(__name__)

def allowed_file(filename, allowed_extensions=None):
    """Check if file extension is allowed
    
    Args:
        filename: Name of the file to check
        allowed_extensions: Set of allowed extensions (default: common image types)
        
    Returns:
        True if allowed, False otherwise
    """
    if not allowed_extensions:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp'}
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_image_info(filepath, thumbnail_size=(200, 200)):
    """Get image information including size and thumbnail
    
    Args:
        filepath: Path to the image file
        thumbnail_size: Size tuple for thumbnail generation
        
    Returns:
        Dictionary with image information
    """
    try:
        with Image.open(filepath) as img:
            # Create thumbnail
            img.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
            
            # Convert to base64 for web display
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG')
            thumbnail_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            # Get file stats
            stats = os.stat(filepath)
            
            return {
                'filename': os.path.basename(filepath),
                'size': stats.st_size,
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'modified': datetime.fromtimestamp(stats.st_mtime).isoformat(),
                'thumbnail': thumbnail_base64
            }
    except Exception as e:
        logger.error(f"Error getting image info for {filepath}: {e}")
        return None

def get_all_images(upload_folder, allowed_extensions=None):
    """Get information about all images in upload folder
    
    Args:
        upload_folder: Path to upload directory
        allowed_extensions: Set of allowed file extensions
        
    Returns:
        List of image information dictionaries
    """
    if not allowed_extensions:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp'}
    
    images = []
    try:
        upload_path = Path(upload_folder)
        if not upload_path.exists():
            return images
        
        for file_path in upload_path.glob('*'):
            if file_path.is_file() and file_path.suffix[1:].lower() in allowed_extensions:
                image_info = get_image_info(str(file_path))
                if image_info:
                    images.append(image_info)
        
        # Sort by modification time (newest first)
        images.sort(key=lambda x: x['modified'], reverse=True)
        
    except Exception as e:
        logger.error(f"Error listing images: {e}")
    
    return images

def safe_filename(filename, timestamp=True):
    """Create a safe filename with optional timestamp
    
    Args:
        filename: Original filename
        timestamp: Whether to add timestamp if file exists
        
    Returns:
        Safe filename string
    """
    from werkzeug.utils import secure_filename
    
    safe_name = secure_filename(filename)
    
    if timestamp:
        name, ext = os.path.splitext(safe_name)
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = f"{name}_{timestamp_str}{ext}"
    
    return safe_name

def ensure_directory(directory_path):
    """Ensure directory exists, create if it doesn't
    
    Args:
        directory_path: Path to directory
        
    Returns:
        True if directory exists or was created, False otherwise
    """
    try:
        Path(directory_path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating directory {directory_path}: {e}")
        return False

def get_file_size_mb(file_path):
    """Get file size in megabytes
    
    Args:
        file_path: Path to file
        
    Returns:
        File size in MB as float
    """
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except Exception as e:
        logger.error(f"Error getting file size for {file_path}: {e}")
        return 0.0

def backup_file(file_path, backup_suffix='_backup'):
    """Create a backup copy of a file
    
    Args:
        file_path: Path to original file
        backup_suffix: Suffix to add to backup filename
        
    Returns:
        Path to backup file if successful, None otherwise
    """
    try:
        if not os.path.exists(file_path):
            return None
        
        file_path = Path(file_path)
        backup_path = file_path.with_name(f"{file_path.stem}{backup_suffix}{file_path.suffix}")
        
        shutil.copy2(file_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
        return str(backup_path)
        
    except Exception as e:
        logger.error(f"Error creating backup of {file_path}: {e}")
        return None

def cleanup_temp_files(temp_dir, max_age_hours=24):
    """Clean up temporary files older than specified age
    
    Args:
        temp_dir: Directory containing temporary files
        max_age_hours: Maximum age in hours before cleanup
        
    Returns:
        Number of files cleaned up
    """
    cleaned_count = 0
    try:
        temp_path = Path(temp_dir)
        if not temp_path.exists():
            return 0
        
        max_age_seconds = max_age_hours * 3600
        current_time = datetime.now().timestamp()
        
        for file_path in temp_path.iterdir():
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    file_path.unlink()
                    cleaned_count += 1
        
        logger.info(f"Cleaned up {cleaned_count} temporary files")
        
    except Exception as e:
        logger.error(f"Error cleaning temporary files: {e}")
    
    return cleaned_count

def get_directory_size(directory_path):
    """Get total size of all files in a directory
    
    Args:
        directory_path: Path to directory
        
    Returns:
        Total size in bytes
    """
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(directory_path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
    except Exception as e:
        logger.error(f"Error calculating directory size: {e}")
    
    return total_size

def create_thumbnail(image_path, size=(150, 150), output_format='JPEG'):
    """Create thumbnail from image
    
    Args:
        image_path: Path to source image
        size: Thumbnail size tuple
        output_format: Output image format
        
    Returns:
        Base64 encoded thumbnail or None if failed
    """
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format=output_format)
            return base64.b64encode(buffer.getvalue()).decode()
            
    except Exception as e:
        logger.error(f"Error creating thumbnail: {e}")
        return None