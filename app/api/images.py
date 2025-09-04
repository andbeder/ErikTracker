"""
Image Management API Blueprint
Handles image upload, download, and management operations
"""

import os
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, render_template, jsonify, redirect, url_for, flash, current_app, send_from_directory
from werkzeug.utils import secure_filename

bp = Blueprint('images', __name__)

@bp.route('/')
def index():
    """Main page showing Erik images and matches"""
    file_service = current_app.file_service
    mqtt_service = current_app.mqtt_service
    frigate_service = current_app.frigate_service
    yard_service = current_app.yard_service
    
    # Get images using file service
    images = file_service.list_files('image')
    total_size_mb = sum(img.get('size', 0) for img in images) / (1024 * 1024)
    
    # Get recent matches from MQTT service
    recent_matches = mqtt_service.get_detection_matches()[:20]
    
    # Load Frigate config for display
    frigate_config = frigate_service.load_config()
    
    # Extract camera web URLs for interface links
    camera_urls = {}
    if frigate_config and 'cameras' in frigate_config:
        for camera_name, camera_config in frigate_config['cameras'].items():
            camera_url = frigate_service.extract_camera_ip(camera_config)
            if camera_url:
                camera_urls[camera_name] = camera_url
    
    # Get mesh files for yard mapping
    mesh_files = yard_service.list_meshes()
    
    return render_template('index.html', 
                         images=images, 
                         total_images=len(images),
                         total_size_mb=round(total_size_mb, 2),
                         matches=recent_matches,
                         total_matches=mqtt_service.get_match_count(),
                         frigate_config=frigate_config,
                         camera_urls=camera_urls,
                         mesh_files=mesh_files)

@bp.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('images.index'))
    
    file_service = current_app.file_service
    files = request.files.getlist('file')
    uploaded_count = 0
    errors = []
    
    for file in files:
        if file.filename == '':
            continue
            
        result = file_service.save_upload(file, 'image')
        if 'error' in result:
            errors.append(f"{file.filename}: {result['error']}")
        else:
            uploaded_count += 1
    
    if uploaded_count > 0:
        flash(f'Successfully uploaded {uploaded_count} image(s)', 'success')
    
    for error in errors:
        flash(error, 'error')
    
    return redirect(url_for('images.index'))

@bp.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    """Delete a specific image"""
    file_service = current_app.file_service
    
    if file_service.delete_file(filename, 'image'):
        flash(f'Deleted {filename}', 'success')
    else:
        flash(f'Error deleting {filename}', 'error')
    
    return redirect(url_for('images.index'))

@bp.route('/delete_all', methods=['POST'])
def delete_all():
    """Delete all images"""
    file_service = current_app.file_service
    
    deleted_count = file_service.delete_all_files('image')
    flash(f'Deleted {deleted_count} images', 'success')
    
    return redirect(url_for('images.index'))

@bp.route('/download/<filename>')
def download_file(filename):
    """Download a specific image"""
    try:
        secure_name = secure_filename(filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        return send_from_directory(upload_folder, secure_name, as_attachment=True)
    except Exception as e:
        flash(f'Error downloading {filename}: {str(e)}', 'error')
        return redirect(url_for('images.index'))

@bp.route('/<filename>')
def serve_image(filename):
    """Serve an image file directly (not as download)"""
    try:
        # Check if file has a valid image extension
        allowed_extensions = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp'}
        if not any(filename.lower().endswith(f'.{ext}') for ext in allowed_extensions):
            return '', 404
            
        secure_name = secure_filename(filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        
        # Convert relative path to absolute if needed
        if not os.path.isabs(upload_folder):
            upload_folder = os.path.abspath(upload_folder)
        
        return send_from_directory(upload_folder, secure_name)
    except Exception as e:
        # Return 404 for missing images
        return '', 404

@bp.route('/api/images')
def api_images():
    """API endpoint to get image list as JSON"""
    file_service = current_app.file_service
    images = file_service.list_files('image')
    
    return jsonify({
        'images': images,
        'total_count': len(images),
        'total_size_mb': round(sum(img.get('size', 0) for img in images) / (1024 * 1024), 2)
    })

@bp.route('/api/matches')
def api_matches():
    """API endpoint to get detection matches as JSON"""
    mqtt_service = current_app.mqtt_service
    matches = mqtt_service.get_detection_matches()[:50]  # Last 50 matches
    
    return jsonify({
        'matches': matches,
        'total_count': mqtt_service.get_match_count()
    })

@bp.route('/api/matches/clear', methods=['POST'])
def clear_matches():
    """Clear all detection matches"""
    mqtt_service = current_app.mqtt_service
    mqtt_service.clear_detection_matches()
    
    flash('Cleared all detection matches', 'success')
    return jsonify({'status': 'success'})

@bp.route('/api/status')
def api_status():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'upload_folder': current_app.config['UPLOAD_FOLDER'],
        'timestamp': datetime.now().isoformat()
    })

@bp.route('/api/storage-stats')
def storage_stats():
    """Get storage statistics"""
    file_service = current_app.file_service
    stats = file_service.get_storage_stats()
    return jsonify(stats)