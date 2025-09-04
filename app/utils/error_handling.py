"""
Error handling utilities
Common error handling patterns and utilities
"""

import logging
import traceback
from typing import Dict, Any, Optional, Tuple
from functools import wraps
from flask import jsonify, current_app

logger = logging.getLogger(__name__)

class APIError(Exception):
    """Custom API error with status code and message"""
    
    def __init__(self, message: str, status_code: int = 400, payload: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for JSON response"""
        error_dict = {'error': self.message}
        error_dict.update(self.payload)
        return error_dict

def handle_api_error(error: APIError):
    """Handle APIError and return JSON response"""
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

def api_error_handler(f):
    """Decorator to handle API errors and return consistent JSON responses"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except APIError as e:
            logger.error(f"API Error in {f.__name__}: {e.message}")
            return handle_api_error(e)
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Return generic error in production, detailed in debug
            if current_app and current_app.debug:
                error_response = {
                    'error': f'Internal server error: {str(e)}',
                    'traceback': traceback.format_exc()
                }
            else:
                error_response = {'error': 'Internal server error'}
            
            response = jsonify(error_response)
            response.status_code = 500
            return response
    
    return decorated_function

def safe_execute(func, *args, default_return=None, log_errors=True, **kwargs):
    """Safely execute a function and return default on error
    
    Args:
        func: Function to execute
        *args: Function arguments
        default_return: Value to return on error
        log_errors: Whether to log errors
        **kwargs: Function keyword arguments
        
    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            logger.error(f"Error in safe_execute({func.__name__}): {str(e)}")
        return default_return

def validate_and_execute(validation_func, execution_func, *args, **kwargs):
    """Validate input then execute function
    
    Args:
        validation_func: Function to validate inputs (should return (is_valid, error_message))
        execution_func: Function to execute if validation passes
        *args: Arguments for both functions
        **kwargs: Keyword arguments for both functions
        
    Returns:
        Execution result or raises APIError if validation fails
    """
    is_valid, error_message = validation_func(*args, **kwargs)
    if not is_valid:
        raise APIError(error_message, 400)
    
    return execution_func(*args, **kwargs)

def log_and_return_error(message: str, status_code: int = 400, log_level: str = 'error') -> Tuple[Dict[str, str], int]:
    """Log error and return JSON error response
    
    Args:
        message: Error message
        status_code: HTTP status code
        log_level: Logging level ('error', 'warning', 'info')
        
    Returns:
        Tuple of (error_dict, status_code)
    """
    log_func = getattr(logger, log_level, logger.error)
    log_func(message)
    
    return {'error': message}, status_code

def create_success_response(data: Any = None, message: str = None) -> Dict[str, Any]:
    """Create consistent success response
    
    Args:
        data: Response data
        message: Success message
        
    Returns:
        Success response dictionary
    """
    response = {'status': 'success'}
    
    if message:
        response['message'] = message
    
    if data is not None:
        if isinstance(data, dict):
            response.update(data)
        else:
            response['data'] = data
    
    return response

def create_error_response(message: str, error_code: str = None, details: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create consistent error response
    
    Args:
        message: Error message
        error_code: Optional error code
        details: Optional additional error details
        
    Returns:
        Error response dictionary
    """
    response = {
        'status': 'error',
        'error': message
    }
    
    if error_code:
        response['error_code'] = error_code
    
    if details:
        response['details'] = details
    
    return response

def handle_file_operation_error(operation: str, filename: str, error: Exception) -> APIError:
    """Handle file operation errors consistently
    
    Args:
        operation: Type of operation (e.g., 'upload', 'delete', 'read')
        filename: Name of the file
        error: The exception that occurred
        
    Returns:
        APIError with appropriate message and status code
    """
    error_str = str(error)
    
    if 'Permission denied' in error_str:
        return APIError(f"Permission denied for {operation} operation on '{filename}'", 403)
    elif 'No such file' in error_str or 'not found' in error_str.lower():
        return APIError(f"File '{filename}' not found", 404)
    elif 'No space left' in error_str:
        return APIError(f"Insufficient disk space for {operation} operation", 507)
    elif 'File exists' in error_str and operation == 'create':
        return APIError(f"File '{filename}' already exists", 409)
    else:
        return APIError(f"Failed to {operation} file '{filename}': {error_str}", 500)

def handle_service_error(service_name: str, operation: str, error: Exception) -> APIError:
    """Handle service operation errors consistently
    
    Args:
        service_name: Name of the service (e.g., 'MQTT', 'COLMAP')
        operation: Operation being performed
        error: The exception that occurred
        
    Returns:
        APIError with appropriate message and status code
    """
    error_str = str(error)
    
    if 'connection' in error_str.lower() or 'timeout' in error_str.lower():
        return APIError(f"{service_name} service connection error during {operation}", 503)
    elif 'not found' in error_str.lower() or 'does not exist' in error_str.lower():
        return APIError(f"Resource not found in {service_name} service for {operation}", 404)
    elif 'permission' in error_str.lower() or 'unauthorized' in error_str.lower():
        return APIError(f"Permission denied for {service_name} {operation}", 403)
    else:
        return APIError(f"{service_name} service error during {operation}: {error_str}", 500)

def retry_on_failure(max_retries: int = 3, delay: float = 1.0, exponential_backoff: bool = True):
    """Decorator to retry function on failure
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        exponential_backoff: Whether to use exponential backoff
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. Retrying in {current_delay}s...")
                        
                        import time
                        time.sleep(current_delay)
                        
                        if exponential_backoff:
                            current_delay *= 2
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
            
            # Re-raise the last exception if all retries failed
            raise last_exception
        
        return wrapper
    return decorator