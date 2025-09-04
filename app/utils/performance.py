"""
Performance utilities and optimization helpers
"""

import time
import logging
import gc
import threading
from functools import wraps
from typing import Dict, Any, Optional
import psutil
import os

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Monitor application performance metrics"""
    
    def __init__(self):
        self.metrics = {}
        self.lock = threading.Lock()
    
    def track_operation(self, operation_name: str, duration: float, metadata: Dict[str, Any] = None):
        """Track performance of an operation
        
        Args:
            operation_name: Name of the operation
            duration: Duration in seconds
            metadata: Additional metadata
        """
        with self.lock:
            if operation_name not in self.metrics:
                self.metrics[operation_name] = {
                    'count': 0,
                    'total_time': 0,
                    'avg_time': 0,
                    'min_time': float('inf'),
                    'max_time': 0,
                    'last_run': None
                }
            
            stats = self.metrics[operation_name]
            stats['count'] += 1
            stats['total_time'] += duration
            stats['avg_time'] = stats['total_time'] / stats['count']
            stats['min_time'] = min(stats['min_time'], duration)
            stats['max_time'] = max(stats['max_time'], duration)
            stats['last_run'] = time.time()
            
            if metadata:
                stats['last_metadata'] = metadata
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all performance metrics"""
        with self.lock:
            return self.metrics.copy()
    
    def reset_metrics(self):
        """Reset all performance metrics"""
        with self.lock:
            self.metrics.clear()

# Global performance monitor
global_monitor = PerformanceMonitor()

def monitor_performance(operation_name: str = None):
    """Decorator to monitor function performance
    
    Args:
        operation_name: Custom operation name (uses function name if not provided)
    """
    def decorator(func):
        nonlocal operation_name
        if not operation_name:
            operation_name = f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Track successful operations
                global_monitor.track_operation(
                    operation_name, 
                    duration, 
                    {'status': 'success', 'args_count': len(args), 'kwargs_count': len(kwargs)}
                )
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                # Track failed operations
                global_monitor.track_operation(
                    f"{operation_name}_error", 
                    duration, 
                    {'status': 'error', 'error_type': type(e).__name__}
                )
                
                raise
        
        return wrapper
    return decorator

def get_system_metrics() -> Dict[str, Any]:
    """Get current system performance metrics"""
    try:
        process = psutil.Process()
        
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'memory_used_mb': psutil.virtual_memory().used / (1024 * 1024),
            'process_memory_mb': process.memory_info().rss / (1024 * 1024),
            'process_cpu_percent': process.cpu_percent(),
            'open_files': len(process.open_files()),
            'threads': process.num_threads(),
            'disk_usage_percent': psutil.disk_usage('/').percent
        }
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        return {'error': str(e)}

def optimize_imports():
    """Optimize Python imports by cleaning up unused modules"""
    import sys
    
    initial_count = len(sys.modules)
    
    # Get list of modules to potentially remove
    # Be conservative - only remove modules we know are safe to remove
    safe_to_remove = []
    
    for module_name in list(sys.modules.keys()):
        # Don't remove core modules or application modules
        if (module_name.startswith('app.') or 
            module_name in ['__main__', '__builtin__', 'sys', 'os'] or
            module_name.startswith('flask') or
            module_name.startswith('werkzeug')):
            continue
        
        # Check if module is unused (this is a simple heuristic)
        module = sys.modules.get(module_name)
        if module is None:
            safe_to_remove.append(module_name)
    
    # Remove safe modules
    for module_name in safe_to_remove:
        if module_name in sys.modules:
            del sys.modules[module_name]
    
    final_count = len(sys.modules)
    removed = initial_count - final_count
    
    if removed > 0:
        logger.info(f"Import optimization: removed {removed} unused modules")
        
        # Force garbage collection
        gc.collect()
    
    return removed

def memory_cleanup():
    """Perform memory cleanup operations"""
    logger.info("Performing memory cleanup")
    
    # Force garbage collection
    collected = gc.collect()
    
    # Clean up thread locals
    threading.local()
    
    # Get memory stats
    try:
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)
        logger.info(f"Memory cleanup complete. Current usage: {memory_mb:.1f}MB, collected {collected} objects")
        return memory_mb
    except Exception as e:
        logger.error(f"Error getting memory stats: {e}")
        return None

def profile_startup():
    """Profile application startup performance"""
    startup_times = {}
    
    # Time imports
    start = time.time()
    try:
        from app import create_app
        startup_times['app_import'] = time.time() - start
    except ImportError as e:
        startup_times['app_import_error'] = str(e)
        return startup_times
    
    # Time app creation
    start = time.time()
    try:
        app = create_app('testing')
        startup_times['app_creation'] = time.time() - start
    except Exception as e:
        startup_times['app_creation_error'] = str(e)
        return startup_times
    
    # Time service initialization
    start = time.time()
    try:
        with app.app_context():
            # Services are already initialized during app creation
            startup_times['service_init'] = time.time() - start
    except Exception as e:
        startup_times['service_init_error'] = str(e)
    
    return startup_times

def benchmark_operations():
    """Benchmark common application operations"""
    benchmarks = {}
    
    try:
        from app.utils import validate_file_upload, create_progress_session
        from app.services.file_service import FileService
        
        # Benchmark validation
        start = time.time()
        for _ in range(1000):
            validate_file_upload(None, {'jpg', 'png'})
        benchmarks['validation_1000_calls'] = time.time() - start
        
        # Benchmark progress session creation
        start = time.time()
        for _ in range(100):
            create_progress_session('benchmark')
        benchmarks['progress_session_100_calls'] = time.time() - start
        
        # Benchmark service instantiation
        config = {'UPLOAD_FOLDER': './test', 'MESH_FOLDER': './test'}
        start = time.time()
        for _ in range(100):
            FileService(config)
        benchmarks['service_instantiation_100_calls'] = time.time() - start
        
    except Exception as e:
        benchmarks['benchmark_error'] = str(e)
    
    return benchmarks

def cleanup_temp_files(app_config: Dict[str, Any]):
    """Clean up temporary files across the application"""
    cleaned_files = 0
    
    try:
        from app.utils.file_helpers import cleanup_temp_files
        
        # Clean up various temporary directories
        temp_dirs = [
            '/tmp',
            app_config.get('UPLOAD_FOLDER', './erik_images'),
            app_config.get('MESH_FOLDER', './meshes'),
        ]
        
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                cleaned = cleanup_temp_files(temp_dir, max_age_hours=24)
                cleaned_files += cleaned
        
        logger.info(f"Cleaned up {cleaned_files} temporary files")
        
    except Exception as e:
        logger.error(f"Error cleaning temporary files: {e}")
    
    return cleaned_files

def generate_performance_report() -> Dict[str, Any]:
    """Generate comprehensive performance report"""
    report = {
        'timestamp': time.time(),
        'system_metrics': get_system_metrics(),
        'performance_metrics': global_monitor.get_metrics(),
        'startup_profile': profile_startup(),
        'benchmarks': benchmark_operations()
    }
    
    return report