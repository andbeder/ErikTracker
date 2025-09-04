"""
Logging helper utilities
Common logging patterns and utilities for the application
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from functools import wraps

def setup_logging(
    log_level: str = 'INFO',
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
    enable_console: bool = True,
    max_log_size_mb: int = 10,
    backup_count: int = 5
) -> logging.Logger:
    """Set up application logging with file and console handlers
    
    Args:
        log_level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        log_file: Path to log file (optional)
        log_format: Custom log format (optional)
        enable_console: Whether to enable console logging
        max_log_size_mb: Maximum log file size in MB before rotation
        backup_count: Number of backup log files to keep
        
    Returns:
        Configured logger
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set default format
    if not log_format:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    formatter = logging.Formatter(log_format)
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler with rotation
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_log_size_mb * 1024 * 1024,
            backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger

def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Get a logger with optional level override
    
    Args:
        name: Logger name (typically __name__)
        level: Optional logging level override
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    
    if level:
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    return logger

def log_function_call(include_args: bool = False, include_result: bool = False):
    """Decorator to log function calls
    
    Args:
        include_args: Whether to log function arguments
        include_result: Whether to log function result
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            
            # Log function entry
            if include_args:
                logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
            else:
                logger.debug(f"Calling {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                
                # Log successful completion
                if include_result:
                    logger.debug(f"{func.__name__} completed successfully, result: {result}")
                else:
                    logger.debug(f"{func.__name__} completed successfully")
                
                return result
                
            except Exception as e:
                logger.error(f"{func.__name__} failed with error: {str(e)}")
                raise
        
        return wrapper
    return decorator

def log_execution_time(log_level: str = 'INFO'):
    """Decorator to log function execution time
    
    Args:
        log_level: Level at which to log execution time
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            
            logger = get_logger(func.__module__)
            log_func = getattr(logger, log_level.lower(), logger.info)
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                log_func(f"{func.__name__} executed in {execution_time:.3f} seconds")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"{func.__name__} failed after {execution_time:.3f} seconds: {str(e)}")
                raise
        
        return wrapper
    return decorator

def create_operation_logger(operation_name: str, log_file: Optional[str] = None) -> logging.Logger:
    """Create a dedicated logger for a specific operation
    
    Args:
        operation_name: Name of the operation (e.g., 'colmap', 'mesh_processing')
        log_file: Optional dedicated log file for this operation
        
    Returns:
        Dedicated logger
    """
    logger_name = f"erik.{operation_name}"
    logger = logging.getLogger(logger_name)
    
    # Prevent propagation to root logger if we have a dedicated file
    if log_file:
        logger.propagate = False
        
        # Check if handler already exists
        if not logger.handlers:
            handler = logging.FileHandler(log_file)
            formatter = logging.Formatter(
                f'%(asctime)s - {operation_name.upper()} - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
    
    return logger

def log_with_context(logger: logging.Logger, level: str, message: str, **context):
    """Log message with additional context information
    
    Args:
        logger: Logger instance
        level: Log level ('debug', 'info', 'warning', 'error')
        message: Log message
        **context: Additional context to include
    """
    log_func = getattr(logger, level.lower(), logger.info)
    
    if context:
        context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        full_message = f"{message} [{context_str}]"
    else:
        full_message = message
    
    log_func(full_message)

def log_api_request(logger: logging.Logger, request, response_status: int, execution_time: float):
    """Log API request details
    
    Args:
        logger: Logger instance
        request: Flask request object
        response_status: HTTP response status code
        execution_time: Request execution time in seconds
    """
    log_with_context(
        logger, 'info',
        f"{request.method} {request.path}",
        status=response_status,
        time=f"{execution_time:.3f}s",
        remote_addr=request.remote_addr,
        user_agent=request.headers.get('User-Agent', 'Unknown')[:100]  # Truncate long user agents
    )

def create_structured_log_entry(
    action: str,
    status: str,
    details: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """Create structured log entry for JSON logging
    
    Args:
        action: Action being performed
        status: Status of the action ('started', 'completed', 'failed')
        details: Additional details dictionary
        timestamp: Optional timestamp (uses current time if not provided)
        
    Returns:
        Structured log entry dictionary
    """
    entry = {
        'timestamp': timestamp or datetime.now().isoformat(),
        'action': action,
        'status': status
    }
    
    if details:
        entry.update(details)
    
    return entry

def setup_service_logging(service_name: str, log_dir: str = './logs') -> logging.Logger:
    """Set up dedicated logging for a service
    
    Args:
        service_name: Name of the service
        log_dir: Directory for log files
        
    Returns:
        Service logger
    """
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir_path / f"{service_name.lower()}.log"
    
    return create_operation_logger(service_name, str(log_file))

def log_system_info(logger: logging.Logger):
    """Log system information for debugging
    
    Args:
        logger: Logger instance
    """
    try:
        import platform
        import psutil
        
        system_info = {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': f"{psutil.virtual_memory().total / (1024**3):.1f}GB",
            'disk_usage': f"{psutil.disk_usage('/').percent:.1f}%"
        }
        
        log_with_context(logger, 'info', "System information", **system_info)
        
    except ImportError:
        logger.warning("psutil not available for system info logging")
    except Exception as e:
        logger.error(f"Error logging system info: {e}")

def configure_werkzeug_logging(log_level: str = 'WARNING'):
    """Configure Werkzeug (Flask) logging level
    
    Args:
        log_level: Logging level for Werkzeug
    """
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(getattr(logging, log_level.upper(), logging.WARNING))