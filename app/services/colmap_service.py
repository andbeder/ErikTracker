"""
COLMAP Service for 3D Reconstruction
Handles COLMAP operations and progress tracking
"""

import os
import re
import json
import logging
import threading
import subprocess
import select
import uuid
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

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
        self.start_time = datetime.now()
        self.last_updated = datetime.now()
        
    def parse_log_line(self, line_type, line_content):
        """Parse COLMAP log line and update progress - Enhanced with legacy patterns"""
        if not line_content:
            return
            
        try:
            # Update last updated time
            self.last_updated = datetime.now()
            
            # Feature extraction progress - enhanced patterns from legacy
            if 'feature_extraction.cc' in line_content or 'sift.cc' in line_content:
                patterns = [
                    r'Processed file \[(\d+)/(\d+)\]',  # Main COLMAP pattern
                    r'Processed (\d+)/(\d+) images',
                    r'Extracting features \[(\d+)/(\d+)\]',
                    r'Features \[(\d+)/(\d+)\]',
                    r'Image (\d+) of (\d+)',
                    r'\] Creating SIFT.*extractor.*(\d+)',  # Thread-based processing
                    r'\] (\d+) images.*processed',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, line_content)
                    if match:
                        if len(match.groups()) == 2:
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
            
            # Check for general processing indicators in COLMAP logs
            elif 'timer.cc' in line_content and 'Elapsed time' in line_content:
                # This indicates a phase completed - mark as 100% if we have any progress
                if self.current_phase == 'feature_extraction' and self.progress['feature_extraction']['current'] > 0:
                    self.progress['feature_extraction']['percent'] = 100
            
            # Feature matching progress - enhanced patterns from legacy
            elif ('pairing.cc' in line_content or 'feature_matching.cc' in line_content or 
                  'matcher.cc' in line_content or 'matching' in line_content.lower()):
                patterns = [
                    r'Matching image \[(\d+)/(\d+)\]',  # Main COLMAP pattern
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
            
            # Sparse reconstruction progress - enhanced patterns from legacy
            elif ('mapper.cc' in line_content or 'incremental_mapper.cc' in line_content or 
                  'reconstruction.cc' in line_content):
                patterns = [
                    r'Registering image \[(\d+)/(\d+)\]',  # Main COLMAP pattern
                    r'Registered images: (\d+)/(\d+)',
                    r'=> Registered images: (\d+)',
                    r'Triangulating (\d+)/(\d+)',
                    r'=> Triangulated (\d+) points',
                    r'Bundle adjustment.*(\d+)/(\d+)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, line_content)
                    if match:
                        if 'Triangulated.*points' in pattern or 'Registered images:' in pattern:
                            if len(match.groups()) == 1:
                                current = int(match.group(1))
                                self.progress['sparse_reconstruction']['current'] = current
                        else:
                            current, total = int(match.group(1)), int(match.group(2))
                            self.progress['sparse_reconstruction']['current'] = current
                            self.progress['sparse_reconstruction']['total'] = total
                            if total > 0:
                                self.progress['sparse_reconstruction']['percent'] = min(100, int(
                                    (current / total) * 100
                                ))
                        break
            
            # Dense reconstruction progress - enhanced patterns from legacy
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
                        total = int(match.group(1))
                        # Set total for feature extraction if not already set
                        if self.progress['feature_extraction']['total'] == 0:
                            self.progress['feature_extraction']['total'] = total
                        break
                    
        except Exception as e:
            logger.error(f"Error parsing COLMAP log line: {e}")
            logger.debug(f"Line content: {line_content}")
                        
        except Exception as e:
            logger.error(f"Error parsing COLMAP log: {e}")
    
    def get_elapsed_time(self):
        """Get elapsed time since start"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def to_dict(self):
        """Convert progress to dictionary"""
        return {
            'session_id': self.session_id,
            'current_phase': self.current_phase,
            'progress': self.progress,
            'completed': self.completed,
            'elapsed_time': self.get_elapsed_time(),
            'last_updated': self.last_updated.isoformat()
        }

class COLMAPService:
    """Service for managing COLMAP 3D reconstruction operations"""
    
    def __init__(self, config=None):
        """Initialize COLMAP service with configuration"""
        self.config = config or {}
        self.progress_sessions = {}
        self.progress_lock = threading.Lock()
        
        # Global progress state
        self.global_progress_state = {
            'active': False,
            'current_phase': None,
            'progress': {},
            'completed': False,
            'project_dir': None,
            'session_id': None,
            'start_time': None,
            'last_updated': None
        }
        self.global_progress_lock = threading.Lock()
        
        # Configuration
        self.projects_dir = self.config.get('COLMAP_PROJECTS_DIR', '/home/andrew/colmap/projects')
        self.docker_image = self.config.get('COLMAP_DOCKER_IMAGE', 'colmap/colmap:latest')
    
    def create_session(self, session_id=None):
        """Create a new COLMAP progress session
        
        Args:
            session_id: Optional session ID, generates one if not provided
            
        Returns:
            Session ID
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        with self.progress_lock:
            self.progress_sessions[session_id] = COLMAPProgressTracker(session_id)
        
        return session_id
    
    def get_session(self, session_id):
        """Get a COLMAP progress session
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            COLMAPProgressTracker or None if not found
        """
        with self.progress_lock:
            return self.progress_sessions.get(session_id)
    
    def update_global_progress(self, session_id):
        """Update global progress state from a session"""
        with self.progress_lock:
            tracker = self.progress_sessions.get(session_id)
            if not tracker:
                return
            
            with self.global_progress_lock:
                self.global_progress_state['active'] = not tracker.completed
                self.global_progress_state['current_phase'] = tracker.current_phase
                self.global_progress_state['progress'] = tracker.progress.copy()
                self.global_progress_state['completed'] = tracker.completed
                self.global_progress_state['session_id'] = session_id
                self.global_progress_state['last_updated'] = datetime.now().isoformat()
    
    def run_colmap_with_progress(self, cmd, session_id):
        """Run COLMAP command with progress tracking
        
        Args:
            cmd: Command to run (list of arguments)
            session_id: Session ID for progress tracking
            
        Returns:
            True if successful, False otherwise
        """
        tracker = self.get_session(session_id)
        if not tracker:
            logger.error(f"Session {session_id} not found")
            return False
        
        def read_output_stream(process, tracker):
            """Read and parse subprocess output in real-time"""
            try:
                while process.poll() is None:
                    ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)
                    
                    for stream in ready:
                        line = stream.readline()
                        if line:
                            stream_name = 'stdout' if stream == process.stdout else 'stderr'
                            tracker.parse_log_line(stream_name, line.strip())
                            self.update_global_progress(session_id)
                            logger.debug(f"COLMAP {stream_name}: {line.strip()}")
                
                # Read any remaining output
                remaining_stdout = process.stdout.read()
                remaining_stderr = process.stderr.read()
                
                if remaining_stdout:
                    for line in remaining_stdout.split('\n'):
                        if line.strip():
                            tracker.parse_log_line('stdout', line.strip())
                            
                if remaining_stderr:
                    for line in remaining_stderr.split('\n'):
                        if line.strip():
                            tracker.parse_log_line('stderr', line.strip())
                            
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
            self.update_global_progress(session_id)
            
            return return_code == 0
            
        except Exception as e:
            logger.error(f"Error running COLMAP with progress: {e}")
            tracker.completed = True
            return False
    
    def run_feature_extraction(self, project_dir, session_id=None):
        """Run COLMAP feature extraction
        
        Args:
            project_dir: Project directory path
            session_id: Optional session ID for progress tracking
            
        Returns:
            True if successful, False otherwise
        """
        if not session_id:
            session_id = self.create_session()
        
        tracker = self.get_session(session_id)
        if tracker:
            tracker.current_phase = 'feature_extraction'
        
        database_path = os.path.join(project_dir, 'database.db')
        images_dir = os.path.join(project_dir, 'images')
        
        cmd = [
            'colmap', 'feature_extractor',
            '--database_path', database_path,
            '--image_path', images_dir,
            '--FeatureExtraction.use_gpu', '1'
        ]
        
        logger.info(f"Starting feature extraction for project: {project_dir}")
        return self.run_colmap_with_progress(cmd, session_id)
    
    def run_feature_extraction_async(self, project_dir, session_id=None):
        """Run COLMAP feature extraction asynchronously in background thread
        
        Args:
            project_dir: Project directory path
            session_id: Optional session ID for progress tracking
            
        Returns:
            Session ID for progress tracking
        """
        if not session_id:
            session_id = self.create_session()
        
        tracker = self.get_session(session_id)
        if tracker:
            tracker.current_phase = 'feature_extraction'
        
        def run_in_background():
            """Background thread function"""
            database_path = os.path.join(project_dir, 'database.db')
            images_dir = os.path.join(project_dir, 'images')
            
            cmd = [
                'colmap', 'feature_extractor',
                '--database_path', database_path,
                '--image_path', images_dir,
                '--FeatureExtraction.use_gpu', '1'
            ]
            
            logger.info(f"Starting feature extraction for project: {project_dir}")
            success = self.run_colmap_with_progress(cmd, session_id)
            
            # Update completion status
            tracker = self.get_session(session_id)
            if tracker:
                tracker.completed = True
                self.update_global_progress(session_id)
        
        # Start background thread
        thread = threading.Thread(target=run_in_background, daemon=True)
        thread.start()
        
        return session_id
    
    def run_feature_matching(self, project_dir, session_id=None):
        """Run COLMAP feature matching
        
        Args:
            project_dir: Project directory path
            session_id: Optional session ID for progress tracking
            
        Returns:
            True if successful, False otherwise
        """
        if not session_id:
            session_id = self.create_session()
        
        tracker = self.get_session(session_id)
        if tracker:
            tracker.current_phase = 'feature_matching'
        
        database_path = os.path.join(project_dir, 'database.db')
        
        cmd = [
            'colmap', 'sequential_matcher',
            '--database_path', database_path,
            '--FeatureMatching.use_gpu', '1'
        ]
        
        logger.info(f"Starting feature matching for project: {project_dir}")
        return self.run_colmap_with_progress(cmd, session_id)
    
    def run_sparse_reconstruction(self, project_dir, session_id=None):
        """Run COLMAP sparse reconstruction
        
        Args:
            project_dir: Project directory path
            session_id: Optional session ID for progress tracking
            
        Returns:
            True if successful, False otherwise
        """
        if not session_id:
            session_id = self.create_session()
        
        tracker = self.get_session(session_id)
        if tracker:
            tracker.current_phase = 'sparse_reconstruction'
        
        database_path = os.path.join(project_dir, 'database.db')
        images_dir = os.path.join(project_dir, 'images')
        sparse_dir = os.path.join(project_dir, 'sparse')
        
        # Create sparse directory if it doesn't exist
        Path(sparse_dir).mkdir(parents=True, exist_ok=True)
        
        cmd = [
            'colmap', 'mapper',
            '--database_path', database_path,
            '--image_path', images_dir,
            '--output_path', sparse_dir
        ]
        
        logger.info(f"Starting sparse reconstruction for project: {project_dir}")
        return self.run_colmap_with_progress(cmd, session_id)
    
    def run_sparse_reconstruction_async(self, project_dir, session_id=None):
        """Run COLMAP sparse reconstruction asynchronously in background thread
        
        Args:
            project_dir: Project directory path
            session_id: Optional session ID for progress tracking
            
        Returns:
            Session ID for progress tracking
        """
        if not session_id:
            session_id = self.create_session()
        
        tracker = self.get_session(session_id)
        if tracker:
            tracker.current_phase = 'sparse_reconstruction'
        
        def run_in_background():
            """Background thread function"""
            database_path = os.path.join(project_dir, 'database.db')
            images_dir = os.path.join(project_dir, 'images')
            sparse_dir = os.path.join(project_dir, 'sparse')
            
            # Create sparse directory if it doesn't exist
            Path(sparse_dir).mkdir(parents=True, exist_ok=True)
            
            # First run feature matching if not already done
            matching_cmd = [
                'colmap', 'sequential_matcher',
                '--database_path', database_path,
                '--FeatureMatching.use_gpu', '1'
            ]
            
            logger.info(f"Starting feature matching for project: {project_dir}")
            matching_success = self.run_colmap_with_progress(matching_cmd, session_id)
            
            if matching_success:
                # Then run sparse reconstruction
                sparse_cmd = [
                    'colmap', 'mapper',
                    '--database_path', database_path,
                    '--image_path', images_dir,
                    '--output_path', sparse_dir
                ]
                
                logger.info(f"Starting sparse reconstruction for project: {project_dir}")
                sparse_success = self.run_colmap_with_progress(sparse_cmd, session_id)
            else:
                sparse_success = False
            
            # Update completion status
            tracker = self.get_session(session_id)
            if tracker:
                tracker.completed = True
                self.update_global_progress(session_id)
            
            return sparse_success
        
        # Start background thread
        thread = threading.Thread(target=run_in_background, daemon=True)
        thread.start()
        
        return session_id
    
    def get_progress(self, session_id):
        """Get progress for a specific session
        
        Args:
            session_id: Session ID
            
        Returns:
            Progress dictionary or None if not found
        """
        tracker = self.get_session(session_id)
        if tracker:
            return tracker.to_dict()
        return None
    
    def get_global_progress(self):
        """Get global progress state
        
        Returns:
            Global progress dictionary
        """
        with self.global_progress_lock:
            return self.global_progress_state.copy()
    
    def cleanup_session(self, session_id):
        """Clean up a completed session
        
        Args:
            session_id: Session ID to clean up
        """
        with self.progress_lock:
            if session_id in self.progress_sessions:
                del self.progress_sessions[session_id]
                logger.info(f"Cleaned up session: {session_id}")