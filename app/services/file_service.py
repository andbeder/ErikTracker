"""
File Service for Upload, Download and Image Management
Handles file operations and image processing
"""

import os
import io
import base64
import shutil
import logging
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image

logger = logging.getLogger(__name__)

class FileService:
    """Service for managing file uploads, downloads, and image operations"""
    
    def __init__(self, config=None):
        """Initialize file service with configuration"""
        self.config = config or {}
        
        # Configuration
        self.upload_folder = self.config.get('UPLOAD_FOLDER', './erik_images')
        self.mesh_folder = self.config.get('MESH_FOLDER', './meshes')
        self.video_folder = self.config.get('VIDEO_FOLDER', './uploaded_videos')
        self.allowed_extensions = self.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp'})
        self.mesh_extensions = self.config.get('MESH_EXTENSIONS', {'ply', 'obj', 'stl'})
        self.video_extensions = self.config.get('VIDEO_EXTENSIONS', {'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv'})
        self.max_file_size = self.config.get('MAX_FILE_SIZE', 16 * 1024 * 1024)  # 16MB for images/meshes
        self.max_video_size = self.config.get('MAX_VIDEO_SIZE', 500 * 1024 * 1024)  # 500MB for videos
        self.thumbnail_size = self.config.get('THUMBNAIL_SIZE', (200, 200))
        self.match_thumbnail_size = self.config.get('MATCH_THUMBNAIL_SIZE', (150, 150))
        
        # Ensure directories exist
        Path(self.upload_folder).mkdir(parents=True, exist_ok=True)
        Path(self.mesh_folder).mkdir(parents=True, exist_ok=True)
        Path(self.video_folder).mkdir(parents=True, exist_ok=True)
    
    def allowed_file(self, filename, file_type='image'):
        """Check if file extension is allowed
        
        Args:
            filename: Name of the file
            file_type: Type of file ('image', 'mesh', or 'video')
            
        Returns:
            True if allowed, False otherwise
        """
        if '.' not in filename:
            return False
        
        extension = filename.rsplit('.', 1)[1].lower()
        
        if file_type == 'mesh':
            return extension in self.mesh_extensions
        elif file_type == 'video':
            return extension in self.video_extensions
        else:
            return extension in self.allowed_extensions
    
    def save_upload(self, file_storage, file_type='image'):
        """Save uploaded file
        
        Args:
            file_storage: Flask FileStorage object
            file_type: Type of file ('image', 'mesh', or 'video')
            
        Returns:
            Dictionary with file information or error
        """
        try:
            if not file_storage or file_storage.filename == '':
                return {'error': 'No file provided'}
            
            filename = secure_filename(file_storage.filename)
            
            if not self.allowed_file(filename, file_type):
                return {'error': 'File type not allowed'}
            
            # Check file size based on type
            file_storage.seek(0, os.SEEK_END)
            file_size = file_storage.tell()
            file_storage.seek(0)
            
            max_size = self.max_video_size if file_type == 'video' else self.max_file_size
            max_size_mb = max_size / (1024*1024)
            
            if file_size > max_size:
                return {'error': f'File too large. Maximum size for {file_type} files is {max_size_mb:.0f}MB'}
            
            # Generate unique filename if exists
            if file_type == 'mesh':
                base_folder = self.mesh_folder
            elif file_type == 'video':
                base_folder = self.video_folder
            else:
                base_folder = self.upload_folder
                
            filepath = Path(base_folder) / filename
            
            if filepath.exists():
                base_name = filepath.stem
                extension = filepath.suffix
                counter = 1
                while filepath.exists():
                    filename = f"{base_name}_{counter}{extension}"
                    filepath = Path(base_folder) / filename
                    counter += 1
            
            # Save file
            file_storage.save(str(filepath))
            
            # Get file information
            file_info = self.get_file_info(str(filepath), file_type)
            file_info['uploaded_at'] = datetime.now().isoformat()
            
            logger.info(f"Saved uploaded file: {filename}")
            return file_info
            
        except Exception as e:
            logger.error(f"Error saving upload: {e}")
            return {'error': str(e)}
    
    def get_file_info(self, filepath, file_type='image'):
        """Get file information including metadata
        
        Args:
            filepath: Path to the file
            file_type: Type of file ('image' or 'mesh')
            
        Returns:
            Dictionary with file information
        """
        try:
            path = Path(filepath)
            stats = path.stat()
            
            # Format modified date for template
            modified_dt = datetime.fromtimestamp(stats.st_mtime)
            formatted_modified = modified_dt.strftime("%Y-%m-%d %H:%M")
            
            info = {
                'name': path.name,
                'filename': path.name,  # Add filename field for template
                'path': str(path),
                'size': stats.st_size,
                'size_mb': round(stats.st_size / (1024 * 1024), 2),  # Size in MB for template
                'modified': formatted_modified,  # Formatted date for template
                'type': file_type
            }
            
            if file_type == 'image':
                # Get image-specific information
                with Image.open(filepath) as img:
                    info['width'] = img.width
                    info['height'] = img.height
                    info['format'] = img.format
                    info['dimensions'] = f"{img.width}x{img.height}"  # Formatted dimensions for template
                    
                    # Set thumbnail URL for template to use
                    info['thumbnail'] = path.name  # Template will construct full URL
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return {'name': Path(filepath).name, 'error': str(e)}
    
    def list_files(self, file_type='image'):
        """List files in the appropriate folder
        
        Args:
            file_type: Type of files to list ('image', 'mesh', or 'video')
            
        Returns:
            List of file information dictionaries
        """
        files = []
        
        try:
            if file_type == 'mesh':
                folder = self.mesh_folder
                extensions = self.mesh_extensions
            elif file_type == 'video':
                folder = self.video_folder
                extensions = self.video_extensions
            else:
                folder = self.upload_folder
                extensions = self.allowed_extensions
                
            folder_path = Path(folder)
            
            if not folder_path.exists():
                return files
            
            for file_path in folder_path.iterdir():
                if file_path.is_file() and file_path.suffix[1:].lower() in extensions:
                    file_info = self.get_file_info(str(file_path), file_type)
                    files.append(file_info)
            
            # Sort by modification time (newest first)
            files.sort(key=lambda x: x.get('modified', ''), reverse=True)
            
        except Exception as e:
            logger.error(f"Error listing files: {e}")
        
        return files
    
    def delete_file(self, filename, file_type='image'):
        """Delete a file
        
        Args:
            filename: Name of the file to delete
            file_type: Type of file ('image', 'mesh', or 'video')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if file_type == 'mesh':
                folder = self.mesh_folder
            elif file_type == 'video':
                folder = self.video_folder
            else:
                folder = self.upload_folder
                
            filepath = Path(folder) / secure_filename(filename)
            
            if filepath.exists() and filepath.is_file():
                filepath.unlink()
                logger.info(f"Deleted file: {filename}")
                return True
            else:
                logger.warning(f"File not found: {filename}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False
    
    def delete_all_files(self, file_type='image'):
        """Delete all files of a specific type
        
        Args:
            file_type: Type of files to delete ('image', 'mesh', or 'video')
            
        Returns:
            Number of files deleted
        """
        count = 0
        
        try:
            if file_type == 'mesh':
                folder = self.mesh_folder
                extensions = self.mesh_extensions
            elif file_type == 'video':
                folder = self.video_folder
                extensions = self.video_extensions
            else:
                folder = self.upload_folder
                extensions = self.allowed_extensions
                
            folder_path = Path(folder)
            
            if not folder_path.exists():
                return 0
            
            for file_path in folder_path.iterdir():
                if file_path.is_file() and file_path.suffix[1:].lower() in extensions:
                    file_path.unlink()
                    count += 1
            
            logger.info(f"Deleted {count} {file_type} files")
            
        except Exception as e:
            logger.error(f"Error deleting all files: {e}")
        
        return count
    
    def create_thumbnail(self, image_path, size=None):
        """Create thumbnail from image file
        
        Args:
            image_path: Path to the image file
            size: Thumbnail size tuple (width, height)
            
        Returns:
            Base64 encoded thumbnail or None if failed
        """
        try:
            size = size or self.thumbnail_size
            
            with Image.open(image_path) as img:
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG')
                return base64.b64encode(buffer.getvalue()).decode()
                
        except Exception as e:
            logger.error(f"Error creating thumbnail: {e}")
            return None
    
    def process_image(self, image_path, operations):
        """Process image with specified operations
        
        Args:
            image_path: Path to the image file
            operations: Dictionary of operations to perform
                - resize: {'width': int, 'height': int}
                - rotate: {'angle': int}
                - crop: {'x': int, 'y': int, 'width': int, 'height': int}
                - format: 'JPEG' or 'PNG'
                
        Returns:
            Processed image data or None if failed
        """
        try:
            with Image.open(image_path) as img:
                # Apply operations
                if 'resize' in operations:
                    size = (operations['resize']['width'], operations['resize']['height'])
                    img = img.resize(size, Image.Resampling.LANCZOS)
                
                if 'rotate' in operations:
                    img = img.rotate(operations['rotate']['angle'], expand=True)
                
                if 'crop' in operations:
                    crop_data = operations['crop']
                    box = (crop_data['x'], crop_data['y'], 
                          crop_data['x'] + crop_data['width'], 
                          crop_data['y'] + crop_data['height'])
                    img = img.crop(box)
                
                # Save to buffer
                buffer = io.BytesIO()
                format_type = operations.get('format', 'JPEG')
                img.save(buffer, format=format_type)
                
                return buffer.getvalue()
                
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return None
    
    def get_storage_stats(self):
        """Get storage statistics for uploaded files
        
        Returns:
            Dictionary with storage statistics
        """
        stats = {
            'images': {'count': 0, 'total_size': 0, 'folder': self.upload_folder},
            'meshes': {'count': 0, 'total_size': 0, 'folder': self.mesh_folder}
        }
        
        try:
            # Calculate image stats
            image_path = Path(self.upload_folder)
            if image_path.exists():
                for file_path in image_path.iterdir():
                    if file_path.is_file() and file_path.suffix[1:].lower() in self.allowed_extensions:
                        stats['images']['count'] += 1
                        stats['images']['total_size'] += file_path.stat().st_size
            
            # Calculate mesh stats
            mesh_path = Path(self.mesh_folder)
            if mesh_path.exists():
                for file_path in mesh_path.iterdir():
                    if file_path.is_file() and file_path.suffix[1:].lower() in self.mesh_extensions:
                        stats['meshes']['count'] += 1
                        stats['meshes']['total_size'] += file_path.stat().st_size
            
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
        
        return stats