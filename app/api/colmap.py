"""
COLMAP API Blueprint  
Handles all COLMAP 3D reconstruction operations and endpoints
"""

import os
import json
import logging
import math
import shutil
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify, flash, current_app, send_from_directory, send_file
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

bp = Blueprint('colmap', __name__, url_prefix='/api/colmap')

@bp.route('/upload-video', methods=['POST'])
def upload_video():
    """Upload video for frame extraction"""
    print(f"DEBUG: Upload request files: {list(request.files.keys())}")
    print(f"DEBUG: Content-Type: {request.content_type}")
    print(f"DEBUG: Content-Length: {request.content_length}")
    
    if 'file' not in request.files:
        print("DEBUG: 'file' not in request.files")
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    print(f"DEBUG: File object: {file}, filename: '{file.filename}', content_type: {file.content_type}")
    
    if file.filename == '':
        print("DEBUG: filename is empty")
        return jsonify({'error': 'No file selected'}), 400
    
    # Use file service for upload handling
    file_service = current_app.file_service
    result = file_service.save_upload(file, 'video')
    
    if 'error' in result:
        return jsonify({'error': result['error']}), 400
    
    return jsonify({
        'status': 'success',
        'video_id': result['name'],
        'filename': result['name'],
        'size': result['size']
    })

@bp.route('/delete-video/<video_id>', methods=['DELETE'])
def delete_video(video_id):
    """Delete uploaded video"""
    file_service = current_app.file_service
    
    if file_service.delete_file(video_id, 'video'):
        return jsonify({'status': 'success'})
    else:
        return jsonify({'error': 'Video not found'}), 404

@bp.route('/list-videos', methods=['GET'])
def list_videos():
    """List uploaded videos"""
    file_service = current_app.file_service
    videos = file_service.list_files('video')
    return jsonify({'videos': videos})

@bp.route('/reset-project', methods=['POST'])
def reset_project():
    """Reset/clear COLMAP project"""
    try:
        # Handle case where no JSON body is sent
        request_data = request.json or {}
        project_dir = request_data.get('project_dir')
        
        # Use default project directory if none specified
        if not project_dir:
            project_dir = '/home/andrew/nvr/colmap_projects/current_reconstruction'
        
        # Clear project directory safely with proper error handling
        if os.path.exists(project_dir):
            errors = []
            successful_deletions = []
            
            for item in os.listdir(project_dir):
                item_path = os.path.join(project_dir, item)
                try:
                    if os.path.isfile(item_path):
                        os.unlink(item_path)
                        successful_deletions.append(item)
                    elif os.path.isdir(item_path):
                        # Try regular deletion first
                        try:
                            shutil.rmtree(item_path)
                            successful_deletions.append(item)
                        except PermissionError:
                            # If permission denied, try with sudo
                            import subprocess
                            result = subprocess.run(
                                ['sudo', 'rm', '-rf', item_path],
                                capture_output=True,
                                text=True
                            )
                            if result.returncode == 0:
                                successful_deletions.append(f"{item} (with sudo)")
                            else:
                                errors.append(f"{item}: {result.stderr.strip()}")
                except Exception as e:
                    errors.append(f"{item}: {str(e)}")
            
            if errors:
                # Partial success - some files couldn't be deleted
                logger.warning(f"Reset partially successful. Errors: {errors}")
                return jsonify({
                    'status': 'partial_success',
                    'message': f'Project partially reset. {len(successful_deletions)} items deleted.',
                    'successful_deletions': successful_deletions,
                    'errors': errors
                })
            else:
                return jsonify({
                    'status': 'success', 
                    'message': f'Project reset successfully. {len(successful_deletions)} items deleted.',
                    'deleted_items': successful_deletions
                })
        else:
            return jsonify({'status': 'success', 'message': 'Project directory does not exist'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/list-frames', methods=['GET'])
def list_frames():
    """Check for existing frames in the current reconstruction project"""
    try:
        # Get COLMAP project directory from config
        colmap_project_dir = current_app.config.get('COLMAP_PROJECT_DIR', '/home/andrew/nvr/colmap_projects')
        project_name = "current_reconstruction"
        project_dir = os.path.join(colmap_project_dir, project_name)
        images_dir = os.path.join(project_dir, 'images')
        
        if not os.path.exists(images_dir):
            return jsonify({
                'success': True,
                'frame_count': 0,
                'frames': [],
                'project_dir': project_dir,
                'message': 'No frames directory found'
            })
        
        # Count image files
        image_extensions = ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']
        image_files = []
        
        for filename in os.listdir(images_dir):
            if any(filename.lower().endswith(ext) for ext in image_extensions):
                image_files.append(filename)
        
        frame_count = len(image_files)
        
        # Get a sample of frame names (first 10) for display
        sample_frames = sorted(image_files)[:10]
        
        return jsonify({
            'success': True,
            'frame_count': frame_count,
            'frames': sample_frames,
            'total_frames': frame_count,
            'project_dir': project_dir,
            'images_dir': images_dir,
            'message': f'Found {frame_count} extracted frames'
        })
        
    except Exception as e:
        current_app.logger.error(f"List frames error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/extract-frames', methods=['POST'])
def extract_frames():
    """Extract frames from video for COLMAP"""
    try:
        data = request.json
        video_file = data.get('video_file')
        project_dir = data.get('project_dir')
        fps = float(data.get('fps', 1))  # Convert to float to handle both int and decimal values
        
        if not video_file or not project_dir:
            return jsonify({'error': 'Missing required parameters'}), 400
        
        # Create project structure
        os.makedirs(project_dir, exist_ok=True)
        images_dir = os.path.join(project_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        # Extract frames using ffmpeg
        # If fps is <= 1, treat as fps rate (e.g., 0.5 = every 2 seconds)
        # If fps is > 1, treat as frame interval (e.g., 20 = every 20th frame)
        if fps <= 1:
            # Use fps filter for sub-1 fps rates
            vf_filter = f'fps={fps}'
        else:
            # Use select filter for frame intervals (every Nth frame)
            vf_filter = f'select=not(mod(n\\,{int(fps)}))'
        
        cmd = [
            'ffmpeg', '-i', video_file,
            '-vf', vf_filter,
            '-vsync', 'vfr',  # Variable frame rate to work with select filter
            '-q:v', '2',
            os.path.join(images_dir, 'frame_%04d.jpg')
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 minutes for large videos
        
        if result.returncode == 0:
            # Count extracted frames
            frame_count = len([f for f in os.listdir(images_dir) if f.endswith('.jpg')])
            return jsonify({
                'status': 'success',
                'frames_extracted': frame_count,
                'project_dir': project_dir
            })
        else:
            return jsonify({'error': f'Frame extraction failed: {result.stderr}'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/feature-extraction', methods=['POST'])
def feature_extraction():
    """Run COLMAP feature extraction"""
    try:
        data = request.json
        project_dir = data.get('project_dir')
        
        if not project_dir:
            return jsonify({'error': 'Project directory not specified'}), 400
        
        colmap_service = current_app.colmap_service
        session_id = colmap_service.create_session()
        
        # Run feature extraction in background
        success = colmap_service.run_feature_extraction(project_dir, session_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'session_id': session_id,
                'message': 'Feature extraction completed'
            })
        else:
            return jsonify({'error': 'Feature extraction failed'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/sparse-reconstruction', methods=['POST'])
def sparse_reconstruction():
    """Run COLMAP sparse reconstruction"""
    try:
        data = request.json
        project_dir = data.get('project_dir')
        
        if not project_dir:
            return jsonify({'error': 'Project directory not specified'}), 400
        
        colmap_service = current_app.colmap_service
        session_id = colmap_service.create_session()
        
        # Run feature matching first, then reconstruction
        if colmap_service.run_feature_matching(project_dir, session_id):
            success = colmap_service.run_sparse_reconstruction(project_dir, session_id)
            
            if success:
                return jsonify({
                    'status': 'success',
                    'session_id': session_id,
                    'message': 'Sparse reconstruction completed'
                })
            else:
                return jsonify({'error': 'Sparse reconstruction failed'}), 500
        else:
            return jsonify({'error': 'Feature matching failed'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/analyze-models', methods=['GET'])
def analyze_models():
    """Analyze COLMAP models in sparse directory with detailed statistics"""
    try:
        project_dir = request.args.get('project_dir')
        if not project_dir:
            return jsonify({'error': 'Project directory not specified'}), 400
        
        sparse_dir = os.path.join(project_dir, 'sparse')
        if not os.path.exists(sparse_dir):
            return jsonify({
                'success': True,
                'models': [],
                'message': 'No sparse reconstruction found'
            })
        
        models = []
        
        # Analyze each model directory
        for item in sorted(os.listdir(sparse_dir)):
            model_path = os.path.join(sparse_dir, item)
            if os.path.isdir(model_path) and os.path.exists(os.path.join(model_path, 'cameras.bin')):
                try:
                    # Run COLMAP model analyzer
                    cmd = [
                        'colmap', 'model_analyzer',
                        '--path', model_path
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
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
                        
                        import re
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
                    current_app.logger.warning(f"Failed to analyze model {item}: {e}")
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
        return jsonify({'error': str(e)}), 500

@bp.route('/check-file', methods=['GET'])
def check_file():
    """Check if a file or directory exists in the project"""
    try:
        project_dir = request.args.get('project_dir')
        file_name = request.args.get('file')
        
        if not project_dir or not file_name:
            return jsonify({'error': 'Missing project_dir or file parameter'}), 400
        
        file_path = os.path.join(project_dir, file_name)
        exists = os.path.exists(file_path)
        
        result = {
            'exists': exists,
            'path': file_path
        }
        
        # If it's a directory, count files in it
        if exists and os.path.isdir(file_path):
            try:
                files = [f for f in os.listdir(file_path) if os.path.isfile(os.path.join(file_path, f))]
                result['count'] = len(files)
                result['is_directory'] = True
            except:
                result['count'] = 0
                result['is_directory'] = True
        elif exists and os.path.isfile(file_path):
            result['is_directory'] = False
            result['size'] = os.path.getsize(file_path)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/select-model', methods=['POST'])
def select_model():
    """Select a specific COLMAP model for dense reconstruction"""
    try:
        data = request.json
        project_dir = data.get('project_dir')
        model_id = data.get('model_id')
        
        if not project_dir or not model_id:
            return jsonify({'error': 'Missing required parameters'}), 400
        
        # Store selected model info (could be in database or config file)
        selected_model_path = os.path.join(project_dir, 'sparse', model_id)
        
        if os.path.exists(selected_model_path):
            return jsonify({
                'status': 'success',
                'selected_model': model_id,
                'model_path': selected_model_path
            })
        else:
            return jsonify({'error': 'Selected model not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/current-model', methods=['GET'])
def current_model():
    """Get currently selected model"""
    # This would typically be stored in a database or config
    # For now, return a simple response
    return jsonify({
        'current_model': None,
        'message': 'No model currently selected'
    })

@bp.route('/dense-reconstruction', methods=['POST'])
def dense_reconstruction():
    """Run COLMAP dense reconstruction with full 3-step pipeline"""
    try:
        data = request.json or {}
        project_dir = data.get('project_dir')
        selected_model_id = data.get('model_id')
        
        if not project_dir:
            return jsonify({'error': 'Project directory not specified'}), 400
        
        if not os.path.exists(project_dir):
            return jsonify({'error': 'Project directory not found'}), 404
        
        sparse_dir = os.path.join(project_dir, 'sparse')
        dense_dir = os.path.join(project_dir, 'dense')
        images_dir = os.path.join(project_dir, 'images')
        
        # Validate required directories exist
        if not os.path.exists(sparse_dir):
            return jsonify({'error': 'No sparse reconstruction found'}), 400
        if not os.path.exists(images_dir):
            return jsonify({'error': 'No images directory found'}), 400
        
        os.makedirs(dense_dir, exist_ok=True)
        
        # Find best sparse model to use
        model_dir = None
        
        logger.info(f"Dense reconstruction - looking for model: {selected_model_id}")
        logger.info(f"Available models: {os.listdir(sparse_dir) if os.path.exists(sparse_dir) else 'None'}")
        
        if selected_model_id:
            potential_model = os.path.join(sparse_dir, selected_model_id)
            if os.path.isdir(potential_model) and os.path.exists(os.path.join(potential_model, 'cameras.bin')):
                model_dir = potential_model
                logger.info(f"✅ Using selected sparse model: {selected_model_id}")
        
        # Fall back to finding the best available model
        if not model_dir:
            logger.info("Finding best model by image count...")
            best_model = None
            max_images = 0
            
            for item in sorted(os.listdir(sparse_dir)):
                potential_model = os.path.join(sparse_dir, item)
                if os.path.isdir(potential_model) and os.path.exists(os.path.join(potential_model, 'cameras.bin')):
                    try:
                        # Estimate image count from images.bin file size
                        images_bin = os.path.join(potential_model, 'images.bin')
                        if os.path.exists(images_bin):
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
        
        if not model_dir:
            return jsonify({'error': 'No valid sparse reconstruction found'}), 400
        
        model_name = os.path.basename(model_dir)
        
        # Step 1: Image undistortion
        logger.info("🔄 Step 1/3: Image undistortion...")
        docker_cmd = [
            'docker', 'run', '--rm', '--gpus', 'all',
            '-v', f'{project_dir}:/workspace',
            'colmap/colmap:latest',
            'colmap', 'image_undistorter',
            '--image_path', '/workspace/images',
            '--input_path', f'/workspace/sparse/{model_name}',
            '--output_path', '/workspace/dense',
            '--output_type', 'COLMAP'
        ]
        
        result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=1800)  # 30 min timeout
        
        if result.returncode != 0:
            logger.error(f"Image undistortion failed: {result.stderr}")
            return jsonify({'error': f'Image undistortion failed: {result.stderr}'}), 500
        
        logger.info("✅ Step 1/3: Image undistortion completed")
        
        # Step 2: Patch match stereo (most GPU-intensive step)
        logger.info("🔄 Step 2/3: Patch match stereo (GPU-intensive)...")
        docker_cmd = [
            'docker', 'run', '--rm', '--gpus', 'all',
            '-v', f'{project_dir}:/workspace',
            'colmap/colmap:latest',
            'colmap', 'patch_match_stereo',
            '--workspace_path', '/workspace/dense',
            '--PatchMatchStereo.gpu_index', '0'  # Use GPU 0
        ]
        
        result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=3600)  # 60 min timeout
        
        if result.returncode != 0:
            logger.error(f"Stereo matching failed: {result.stderr}")
            return jsonify({'error': f'Stereo matching failed: {result.stderr}'}), 500
        
        logger.info("✅ Step 2/3: Patch match stereo completed")
        
        # Step 3: Stereo fusion
        logger.info("🔄 Step 3/3: Stereo fusion...")
        docker_cmd = [
            'docker', 'run', '--rm', '--gpus', 'all',
            '-v', f'{project_dir}:/workspace',
            'colmap/colmap:latest',
            'colmap', 'stereo_fusion',
            '--workspace_path', '/workspace/dense',
            '--output_path', '/workspace/dense/fused.ply'
        ]
        
        result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=1800)  # 30 min timeout
        
        if result.returncode != 0:
            logger.error(f"Stereo fusion failed: {result.stderr}")
            return jsonify({'error': f'Stereo fusion failed: {result.stderr}'}), 500
        
        logger.info("✅ Step 3/3: Stereo fusion completed")
        
        # Count points in the resulting PLY file
        ply_file = os.path.join(dense_dir, 'fused.ply')
        point_count = 0
        
        if os.path.exists(ply_file):
            try:
                with open(ply_file, 'r') as f:
                    for line in f:
                        if line.startswith('element vertex'):
                            point_count = int(line.split()[-1])
                            break
            except Exception as e:
                logger.warning(f"Could not count points in PLY file: {e}")
                point_count = 0
        
        logger.info(f"✅ Dense reconstruction completed successfully! Point count: {point_count}")
        
        return jsonify({
            'status': 'success',
            'point_count': point_count,
            'model_used': model_name,
            'ply_file': ply_file,
            'message': f'Dense reconstruction completed with {point_count} points'
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Dense reconstruction timed out'}), 500
    except Exception as e:
        logger.error(f"Dense reconstruction error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/dense-reconstruction-status', methods=['GET'])
def dense_reconstruction_status():
    """Check if dense reconstruction is currently running"""
    try:
        import subprocess
        
        # Check for running COLMAP Docker containers
        result = subprocess.run(['docker', 'ps', '--format', '{{.Image}}'], 
                              capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            running_images = result.stdout.strip().split('\n')
            colmap_running = any('colmap' in image.lower() for image in running_images if image)
            
            if colmap_running:
                # Get container details
                result = subprocess.run(['docker', 'ps', '--filter', 'ancestor=colmap/colmap:latest', 
                                       '--format', '{{.Names}}\t{{.Status}}'], 
                                      capture_output=True, text=True, timeout=5)
                
                container_info = result.stdout.strip()
                
                return jsonify({
                    'running': True,
                    'status': 'Dense reconstruction is currently running',
                    'container_info': container_info,
                    'message': 'COLMAP dense reconstruction pipeline in progress (30-90 minutes)'
                })
            else:
                return jsonify({
                    'running': False,
                    'status': 'No dense reconstruction running',
                    'message': 'Ready to start dense reconstruction'
                })
        else:
            return jsonify({
                'running': False,
                'status': 'Could not check Docker status',
                'message': 'Docker status check failed'
            })
            
    except Exception as e:
        logger.error(f"Error checking dense reconstruction status: {str(e)}")
        return jsonify({
            'running': False,
            'status': 'Error checking status',
            'error': str(e)
        }), 500

@bp.route('/dense-reconstruction-progress', methods=['GET'])
def dense_reconstruction_progress():
    """Get detailed progress of dense reconstruction"""
    try:
        data = request.args
        project_dir = data.get('project_dir', '/home/andrew/nvr/colmap_projects/current_reconstruction')
        
        if not os.path.exists(project_dir):
            return jsonify({'error': 'Project directory not found'}), 404
        
        dense_dir = os.path.join(project_dir, 'dense')
        images_dir = os.path.join(project_dir, 'images')
        
        # Count total images
        total_images = 0
        if os.path.exists(images_dir):
            total_images = len([f for f in os.listdir(images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
        
        progress_info = {
            'total_images': total_images,
            'phase': 'not_started',
            'progress_percent': 0,
            'current_count': 0,
            'phase_name': 'Not Started',
            'details': 'Dense reconstruction not started',
            'estimated_time_remaining': 'Unknown'
        }
        
        if not os.path.exists(dense_dir):
            return jsonify(progress_info)
        
        # Phase 1: Image undistortion (check for undistorted images)
        undistorted_images_dir = os.path.join(dense_dir, 'images')
        if os.path.exists(undistorted_images_dir):
            undistorted_count = len([f for f in os.listdir(undistorted_images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
            
            if undistorted_count < total_images:
                # Still undistorting images
                progress_info.update({
                    'phase': 'undistortion',
                    'phase_name': 'Image Undistortion',
                    'current_count': undistorted_count,
                    'progress_percent': int((undistorted_count / total_images) * 25) if total_images > 0 else 0,
                    'details': f'Undistorting images: {undistorted_count}/{total_images}',
                    'estimated_time_remaining': '5-15 minutes'
                })
            else:
                # Phase 2: Stereo matching (check for depth maps)
                stereo_dir = os.path.join(dense_dir, 'stereo', 'depth_maps')
                if os.path.exists(stereo_dir):
                    depth_maps = [f for f in os.listdir(stereo_dir) if f.endswith('.bin')]
                    depth_count = len(depth_maps)
                    
                    # Stereo creates multiple files per image, so estimate based on file count
                    estimated_stereo_files = total_images * 2  # rough estimate
                    
                    if depth_count < estimated_stereo_files:
                        # Still doing stereo matching
                        stereo_progress = min(70, 25 + int((depth_count / estimated_stereo_files) * 45))
                        progress_info.update({
                            'phase': 'stereo_matching',
                            'phase_name': 'Stereo Matching (GPU-Intensive)',
                            'current_count': depth_count,
                            'progress_percent': stereo_progress,
                            'details': f'Computing depth maps: {depth_count} files created (~{int(depth_count/2)} images processed)',
                            'estimated_time_remaining': f'{max(1, int((estimated_stereo_files - depth_count) / 10))} minutes'
                        })
                    else:
                        # Phase 3: Check for final PLY file
                        ply_file = os.path.join(dense_dir, 'fused.ply')
                        if os.path.exists(ply_file):
                            # Count points in PLY file
                            point_count = 0
                            try:
                                with open(ply_file, 'r') as f:
                                    for line in f:
                                        if line.startswith('element vertex'):
                                            point_count = int(line.split()[-1])
                                            break
                            except:
                                point_count = 0
                                
                            progress_info.update({
                                'phase': 'completed',
                                'phase_name': 'Completed',
                                'current_count': point_count,
                                'progress_percent': 100,
                                'details': f'Dense reconstruction complete! {point_count:,} points generated',
                                'estimated_time_remaining': 'Complete'
                            })
                        else:
                            # Fusion phase
                            progress_info.update({
                                'phase': 'fusion',
                                'phase_name': 'Stereo Fusion',
                                'current_count': 0,
                                'progress_percent': 85,
                                'details': 'Fusing depth maps into point cloud...',
                                'estimated_time_remaining': '5-10 minutes'
                            })
                else:
                    # Stereo directory doesn't exist yet
                    progress_info.update({
                        'phase': 'preparing_stereo',
                        'phase_name': 'Preparing Stereo Matching',
                        'current_count': 0,
                        'progress_percent': 25,
                        'details': 'Setting up stereo matching pipeline...',
                        'estimated_time_remaining': '2-5 minutes'
                    })
        
        return jsonify(progress_info)
        
    except Exception as e:
        logger.error(f"Error getting dense reconstruction progress: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/progress/<session_id>', methods=['GET'])
def get_progress(session_id):
    """Get progress for a specific COLMAP session"""
    colmap_service = current_app.colmap_service
    progress = colmap_service.get_progress(session_id)
    
    if progress:
        return jsonify(progress)
    else:
        return jsonify({'error': 'Session not found'}), 404

@bp.route('/global-progress', methods=['GET'])
def get_global_progress():
    """Get global COLMAP progress state"""
    colmap_service = current_app.colmap_service
    progress = colmap_service.get_global_progress()
    return jsonify(progress)

@bp.route('/start-with-progress/<phase>', methods=['POST'])
def start_colmap_phase_with_progress(phase):
    """Start a COLMAP phase with progress tracking"""
    try:
        data = request.json or {}
        project_dir = data.get('project_dir')
        
        if not project_dir:
            return jsonify({'error': 'Project directory not specified'}), 400
        
        colmap_service = current_app.colmap_service
        session_id = colmap_service.create_session()
        
        # Start the appropriate phase asynchronously
        if phase == 'feature_extraction':
            session_id = colmap_service.run_feature_extraction_async(project_dir, session_id)
            return jsonify({
                'status': 'success',
                'session_id': session_id,
                'phase': phase
            })
        elif phase == 'feature_matching':
            success = colmap_service.run_feature_matching(project_dir, session_id)
        elif phase == 'sparse_reconstruction':
            session_id = colmap_service.run_sparse_reconstruction_async(project_dir, session_id)
            return jsonify({
                'status': 'success',
                'session_id': session_id,
                'phase': phase
            })
        else:
            return jsonify({'error': f'Unknown phase: {phase}'}), 400
        
        if success:
            return jsonify({
                'status': 'success',
                'session_id': session_id,
                'phase': phase
            })
        else:
            return jsonify({'error': f'{phase} failed'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/set-project', methods=['POST'])
def set_project():
    """Set the active COLMAP project directory"""
    try:
        data = request.json
        project_dir = data.get('project_dir')
        
        if not project_dir:
            return jsonify({'error': 'Project directory not specified'}), 400
        
        # Validate project directory exists
        if not os.path.exists(project_dir):
            os.makedirs(project_dir, exist_ok=True)
        
        # Store in global state (could be in database)
        return jsonify({
            'status': 'success',
            'project_dir': project_dir
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/upload-reconstruction', methods=['POST'])
def upload_reconstruction():
    """Upload pre-computed COLMAP reconstruction"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        project_dir = request.form.get('project_dir')
        
        if not project_dir:
            return jsonify({'error': 'Project directory not specified'}), 400
        
        # Handle reconstruction upload
        # This would extract and process the uploaded reconstruction
        
        return jsonify({
            'status': 'success',
            'message': 'Reconstruction uploaded'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500





@bp.route('/enable-point-cloud', methods=['POST'])
def enable_point_cloud():
    """Enable point cloud for yard map generation by copying dense reconstruction to meshes folder"""
    try:
        data = request.json or {}
        project_dir = data.get('project_dir')
        
        if not project_dir:
            return jsonify({'error': 'Project directory not specified'}), 400
        
        if not os.path.exists(project_dir):
            return jsonify({'error': 'Project directory not found'}), 404
        
        # Look for the PLY file from dense reconstruction
        ply_file = os.path.join(project_dir, 'dense', 'fused.ply')
        if not os.path.exists(ply_file):
            return jsonify({'error': 'No dense reconstruction found. Run dense reconstruction first.'}), 400
        
        # Get mesh folder from environment variable
        mesh_folder = os.getenv('MESH_FOLDER', '/home/andrew/nvr/meshes')
        
        # Create mesh folder if it doesn't exist
        os.makedirs(mesh_folder, exist_ok=True)
        
        # Use standardized filename and clean up old files
        mesh_name = "yard_reconstruction.ply"
        dest_path = os.path.join(mesh_folder, mesh_name)
        
        # Remove old mesh files to keep only one
        for old_file in os.listdir(mesh_folder):
            if old_file.endswith('.ply'):
                old_path = os.path.join(mesh_folder, old_file)
                try:
                    os.remove(old_path)
                    logger.info(f"Removed old mesh file: {old_file}")
                except Exception as e:
                    logger.warning(f"Could not remove old mesh file {old_file}: {e}")
        
        # Copy the PLY file to meshes directory
        import shutil
        shutil.copy2(ply_file, dest_path)
        
        logger.info(f"Enabled point cloud: {mesh_name}")
        
        return jsonify({
            'status': 'success',
            'mesh_file': mesh_name,
            'mesh_path': dest_path,
            'message': 'Point cloud enabled for yard map generation'
        })
        
    except Exception as e:
        logger.error(f"Enable point cloud error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/upload-byo-model', methods=['POST'])
def upload_byo_model():
    """Upload BYO model files (cameras.bin, images.bin, points3D.bin, fusion.ply)"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        file_type = request.form.get('file_type')  # 'cameras', 'images', 'points3d', 'fusion'
        
        if not file.filename:
            return jsonify({'error': 'No file selected'}), 400
        
        if not file_type:
            return jsonify({'error': 'File type not specified'}), 400
        
        # Check file size for BYO model files
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        max_byo_size = current_app.config.get('MAX_BYO_MODEL_SIZE', 2 * 1024 * 1024 * 1024)  # 2GB
        if file_size > max_byo_size:
            size_mb = file_size / (1024 * 1024)
            max_mb = max_byo_size / (1024 * 1024)
            return jsonify({'error': f'File too large ({size_mb:.1f}MB). Maximum size for BYO model files is {max_mb:.0f}MB.'}), 400
        
        if file_size == 0:
            return jsonify({'error': 'File is empty. Please select a valid BYO model file.'}), 400
        
        # Validate file type and extension
        valid_files = {
            'cameras': ('cameras.bin', ['.bin']),
            'images': ('images.bin', ['.bin']),  
            'points3d': ('points3D.bin', ['.bin']),
            'fusion': ('fusion.ply', ['.ply'])
        }
        
        if file_type not in valid_files:
            return jsonify({'error': f'Invalid file type: {file_type}'}), 400
        
        expected_name, valid_extensions = valid_files[file_type]
        
        # Check file extension
        if not any(file.filename.lower().endswith(ext) for ext in valid_extensions):
            return jsonify({'error': f'Invalid file extension. Expected: {valid_extensions}'}), 400
        
        # Set up BYO model directory
        byo_dir = '/home/andrew/nvr/colmap_projects/byo_model'
        os.makedirs(byo_dir, exist_ok=True)
        
        # For sparse model files, create sparse subdirectory
        if file_type in ['cameras', 'images', 'points3d']:
            sparse_dir = os.path.join(byo_dir, 'sparse', '0')
            os.makedirs(sparse_dir, exist_ok=True)
            save_path = os.path.join(sparse_dir, expected_name)
        else:  # fusion.ply goes in dense directory
            dense_dir = os.path.join(byo_dir, 'dense')
            os.makedirs(dense_dir, exist_ok=True)
            save_path = os.path.join(dense_dir, expected_name)
        
        # Save file
        file.save(save_path)
        file_size = os.path.getsize(save_path)
        
        logger.info(f"Uploaded BYO model file: {expected_name} ({file_size} bytes)")
        
        return jsonify({
            'status': 'success',
            'file_type': file_type,
            'filename': expected_name,
            'size': file_size,
            'path': save_path,
            'message': f'{expected_name} uploaded successfully'
        })
        
    except Exception as e:
        logger.error(f"BYO model upload error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/list-byo-model', methods=['GET'])
def list_byo_model():
    """List uploaded BYO model files"""
    try:
        byo_dir = '/home/andrew/nvr/colmap_projects/byo_model'
        
        # Check which files exist
        files_status = {
            'cameras': False,
            'images': False,
            'points3d': False,
            'fusion': False
        }
        
        file_info = {}
        
        # Check sparse model files
        sparse_dir = os.path.join(byo_dir, 'sparse', '0')
        if os.path.exists(sparse_dir):
            for file_key, filename in [('cameras', 'cameras.bin'), ('images', 'images.bin'), ('points3d', 'points3D.bin')]:
                file_path = os.path.join(sparse_dir, filename)
                if os.path.exists(file_path):
                    files_status[file_key] = True
                    file_info[file_key] = {
                        'filename': filename,
                        'size': os.path.getsize(file_path),
                        'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                        'path': file_path
                    }
        
        # Check fusion.ply
        dense_dir = os.path.join(byo_dir, 'dense')
        fusion_path = os.path.join(dense_dir, 'fusion.ply')
        if os.path.exists(fusion_path):
            files_status['fusion'] = True
            file_info['fusion'] = {
                'filename': 'fusion.ply',
                'size': os.path.getsize(fusion_path),
                'modified': datetime.fromtimestamp(os.path.getmtime(fusion_path)).isoformat(),
                'path': fusion_path
            }
        
        # Calculate completion
        uploaded_count = sum(files_status.values())
        all_files_uploaded = uploaded_count == 4
        
        return jsonify({
            'status': 'success',
            'files_status': files_status,
            'file_info': file_info,
            'uploaded_count': uploaded_count,
            'total_required': 4,
            'complete': all_files_uploaded,
            'byo_dir': byo_dir
        })
        
    except Exception as e:
        logger.error(f"List BYO model error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/delete-byo-model/<file_type>', methods=['DELETE'])
def delete_byo_model(file_type):
    """Delete a BYO model file"""
    try:
        valid_files = {
            'cameras': ('cameras.bin', 'sparse/0/cameras.bin'),
            'images': ('images.bin', 'sparse/0/images.bin'),
            'points3d': ('points3D.bin', 'sparse/0/points3D.bin'),
            'fusion': ('fusion.ply', 'dense/fusion.ply')
        }
        
        if file_type not in valid_files:
            return jsonify({'error': f'Invalid file type: {file_type}'}), 400
        
        byo_dir = '/home/andrew/nvr/colmap_projects/byo_model'
        filename, rel_path = valid_files[file_type]
        file_path = os.path.join(byo_dir, rel_path)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted BYO model file: {filename}")
            return jsonify({
                'status': 'success',
                'message': f'{filename} deleted successfully'
            })
        else:
            return jsonify({'error': f'{filename} not found'}), 404
        
    except Exception as e:
        logger.error(f"Delete BYO model error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/enable-byo-point-cloud', methods=['POST'])  
def enable_byo_point_cloud():
    """Enable point cloud from BYO model by copying fusion.ply to meshes folder"""
    try:
        byo_dir = '/home/andrew/nvr/colmap_projects/byo_model'
        fusion_path = os.path.join(byo_dir, 'dense', 'fusion.ply')
        
        if not os.path.exists(fusion_path):
            return jsonify({'error': 'fusion.ply not found. Please upload fusion.ply first.'}), 400
        
        # Get mesh folder from environment variable
        mesh_folder = os.getenv('MESH_FOLDER', '/home/andrew/nvr/meshes')
        
        # Create mesh folder if it doesn't exist
        os.makedirs(mesh_folder, exist_ok=True)
        
        # Use standardized filename and clean up old files
        mesh_name = "yard_reconstruction.ply"
        dest_path = os.path.join(mesh_folder, mesh_name)
        
        # Remove old mesh files to keep only one
        for old_file in os.listdir(mesh_folder):
            if old_file.endswith('.ply'):
                old_path = os.path.join(mesh_folder, old_file)
                try:
                    os.remove(old_path)
                    logger.info(f"Removed old mesh file: {old_file}")
                except Exception as e:
                    logger.warning(f"Could not remove old mesh file {old_file}: {e}")
        
        # Copy the PLY file to meshes directory
        shutil.copy2(fusion_path, dest_path)
        
        logger.info(f"Enabled BYO point cloud: {mesh_name}")
        
        return jsonify({
            'status': 'success',
            'mesh_file': mesh_name,
            'mesh_path': dest_path,
            'message': 'BYO point cloud enabled for yard map generation'
        })
        
    except Exception as e:
        logger.error(f"Enable BYO point cloud error: {str(e)}")
        return jsonify({'error': str(e)}), 500





