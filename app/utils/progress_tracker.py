"""
Progress tracking utilities
Common progress tracking and session management utilities
"""

import uuid
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ProgressSession:
    """Generic progress tracking session"""
    
    def __init__(self, session_id: str = None, session_type: str = "generic"):
        self.session_id = session_id or str(uuid.uuid4())
        self.session_type = session_type
        self.start_time = datetime.now()
        self.last_updated = datetime.now()
        self.completed = False
        self.progress = {}
        self.status = "initialized"
        self.error_message = None
        self.metadata = {}
    
    def update_progress(self, phase: str, current: int, total: int = None):
        """Update progress for a specific phase
        
        Args:
            phase: Name of the current phase
            current: Current progress value
            total: Total expected value (optional)
        """
        if phase not in self.progress:
            self.progress[phase] = {}
        
        self.progress[phase]['current'] = current
        if total is not None:
            self.progress[phase]['total'] = total
            self.progress[phase]['percent'] = min(100, int((current / total) * 100)) if total > 0 else 0
        
        self.last_updated = datetime.now()
        logger.debug(f"Session {self.session_id} progress updated: {phase} = {current}/{total}")
    
    def set_status(self, status: str, error_message: str = None):
        """Set session status
        
        Args:
            status: Status string
            error_message: Optional error message
        """
        self.status = status
        self.error_message = error_message
        self.last_updated = datetime.now()
        
        if status in ['completed', 'failed', 'cancelled']:
            self.completed = True
    
    def add_metadata(self, key: str, value: Any):
        """Add metadata to the session
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
        self.last_updated = datetime.now()
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time since session start in seconds"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        return {
            'session_id': self.session_id,
            'session_type': self.session_type,
            'status': self.status,
            'progress': self.progress,
            'completed': self.completed,
            'start_time': self.start_time.isoformat(),
            'last_updated': self.last_updated.isoformat(),
            'elapsed_time': self.get_elapsed_time(),
            'error_message': self.error_message,
            'metadata': self.metadata
        }

class ProgressTracker:
    """Thread-safe progress tracker for managing multiple sessions"""
    
    def __init__(self):
        self._sessions: Dict[str, ProgressSession] = {}
        self._lock = threading.Lock()
        self._global_state = {
            'active_sessions': 0,
            'last_activity': None
        }
    
    def create_session(self, session_id: str = None, session_type: str = "generic") -> str:
        """Create a new progress tracking session
        
        Args:
            session_id: Optional session ID (generates if not provided)
            session_type: Type of session
            
        Returns:
            Session ID
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        session = ProgressSession(session_id, session_type)
        
        with self._lock:
            self._sessions[session_id] = session
            self._global_state['active_sessions'] = len([s for s in self._sessions.values() if not s.completed])
            self._global_state['last_activity'] = datetime.now().isoformat()
        
        logger.info(f"Created progress session: {session_id} (type: {session_type})")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[ProgressSession]:
        """Get a progress session by ID
        
        Args:
            session_id: Session ID
            
        Returns:
            ProgressSession or None if not found
        """
        with self._lock:
            return self._sessions.get(session_id)
    
    def update_session_progress(self, session_id: str, phase: str, current: int, total: int = None):
        """Update progress for a session
        
        Args:
            session_id: Session ID
            phase: Progress phase name
            current: Current progress value
            total: Total expected value
        """
        session = self.get_session(session_id)
        if session:
            session.update_progress(phase, current, total)
            
            with self._lock:
                self._global_state['last_activity'] = datetime.now().isoformat()
    
    def set_session_status(self, session_id: str, status: str, error_message: str = None):
        """Set status for a session
        
        Args:
            session_id: Session ID
            status: Status string
            error_message: Optional error message
        """
        session = self.get_session(session_id)
        if session:
            session.set_status(status, error_message)
            
            with self._lock:
                self._global_state['active_sessions'] = len([s for s in self._sessions.values() if not s.completed])
                self._global_state['last_activity'] = datetime.now().isoformat()
    
    def add_session_metadata(self, session_id: str, key: str, value: Any):
        """Add metadata to a session
        
        Args:
            session_id: Session ID
            key: Metadata key
            value: Metadata value
        """
        session = self.get_session(session_id)
        if session:
            session.add_metadata(key, value)
    
    def get_session_dict(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session as dictionary
        
        Args:
            session_id: Session ID
            
        Returns:
            Session dictionary or None if not found
        """
        session = self.get_session(session_id)
        return session.to_dict() if session else None
    
    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get all active (non-completed) sessions
        
        Returns:
            Dictionary of active sessions
        """
        active = {}
        with self._lock:
            for session_id, session in self._sessions.items():
                if not session.completed:
                    active[session_id] = session.to_dict()
        
        return active
    
    def get_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get all sessions
        
        Returns:
            Dictionary of all sessions
        """
        all_sessions = {}
        with self._lock:
            for session_id, session in self._sessions.items():
                all_sessions[session_id] = session.to_dict()
        
        return all_sessions
    
    def cleanup_completed_sessions(self, max_completed: int = 10):
        """Clean up completed sessions, keeping only the most recent
        
        Args:
            max_completed: Maximum number of completed sessions to keep
        """
        with self._lock:
            completed_sessions = [(sid, s) for sid, s in self._sessions.items() if s.completed]
            
            if len(completed_sessions) > max_completed:
                # Sort by last updated time and keep most recent
                completed_sessions.sort(key=lambda x: x[1].last_updated, reverse=True)
                
                # Remove oldest sessions
                for session_id, _ in completed_sessions[max_completed:]:
                    del self._sessions[session_id]
                    logger.debug(f"Cleaned up completed session: {session_id}")
    
    def get_global_state(self) -> Dict[str, Any]:
        """Get global tracker state
        
        Returns:
            Global state dictionary
        """
        with self._lock:
            state = self._global_state.copy()
            state['total_sessions'] = len(self._sessions)
            
            # Find most recent active session
            active_sessions = [s for s in self._sessions.values() if not s.completed]
            if active_sessions:
                most_recent = max(active_sessions, key=lambda s: s.last_updated)
                state['most_recent_session'] = {
                    'session_id': most_recent.session_id,
                    'session_type': most_recent.session_type,
                    'status': most_recent.status,
                    'last_updated': most_recent.last_updated.isoformat()
                }
            
            return state

# Global progress tracker instance
global_progress_tracker = ProgressTracker()

def create_progress_session(session_type: str = "generic") -> str:
    """Create a new progress session using global tracker
    
    Args:
        session_type: Type of session
        
    Returns:
        Session ID
    """
    return global_progress_tracker.create_session(session_type=session_type)

def update_progress(session_id: str, phase: str, current: int, total: int = None):
    """Update progress using global tracker
    
    Args:
        session_id: Session ID
        phase: Progress phase name
        current: Current progress value
        total: Total expected value
    """
    global_progress_tracker.update_session_progress(session_id, phase, current, total)

def set_progress_status(session_id: str, status: str, error_message: str = None):
    """Set progress status using global tracker
    
    Args:
        session_id: Session ID
        status: Status string
        error_message: Optional error message
    """
    global_progress_tracker.set_session_status(session_id, status, error_message)

def get_progress_info(session_id: str) -> Optional[Dict[str, Any]]:
    """Get progress information using global tracker
    
    Args:
        session_id: Session ID
        
    Returns:
        Progress information dictionary or None
    """
    return global_progress_tracker.get_session_dict(session_id)