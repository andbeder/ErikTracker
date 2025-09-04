"""
Response helper utilities
Common response formatting and HTTP utilities
"""

from typing import Any, Dict, List, Optional, Union
from flask import jsonify, make_response, request
import json
import logging

logger = logging.getLogger(__name__)

def json_response(
    data: Any = None,
    status_code: int = 200,
    message: str = None,
    error: str = None,
    headers: Dict[str, str] = None
) -> tuple:
    """Create consistent JSON response
    
    Args:
        data: Response data
        status_code: HTTP status code
        message: Success message
        error: Error message
        headers: Additional headers
        
    Returns:
        Tuple of (response, status_code)
    """
    response_body = {}
    
    if error:
        response_body['status'] = 'error'
        response_body['error'] = error
    else:
        response_body['status'] = 'success'
        
        if message:
            response_body['message'] = message
        
        if data is not None:
            if isinstance(data, dict) and 'status' not in data:
                # Merge data into response
                response_body.update(data)
            else:
                response_body['data'] = data
    
    response = make_response(jsonify(response_body), status_code)
    
    if headers:
        for key, value in headers.items():
            response.headers[key] = value
    
    return response

def success_response(
    data: Any = None,
    message: str = None,
    status_code: int = 200,
    headers: Dict[str, str] = None
) -> tuple:
    """Create success JSON response
    
    Args:
        data: Response data
        message: Success message
        status_code: HTTP status code
        headers: Additional headers
        
    Returns:
        Tuple of (response, status_code)
    """
    return json_response(
        data=data,
        status_code=status_code,
        message=message,
        headers=headers
    )

def error_response(
    error: str,
    status_code: int = 400,
    details: Dict[str, Any] = None,
    headers: Dict[str, str] = None
) -> tuple:
    """Create error JSON response
    
    Args:
        error: Error message
        status_code: HTTP status code
        details: Additional error details
        headers: Additional headers
        
    Returns:
        Tuple of (response, status_code)
    """
    data = details if details else None
    return json_response(
        data=data,
        status_code=status_code,
        error=error,
        headers=headers
    )

def validation_error_response(errors: Union[str, List[str]]) -> tuple:
    """Create validation error response
    
    Args:
        errors: Validation error(s)
        
    Returns:
        Tuple of (response, status_code)
    """
    if isinstance(errors, str):
        error_message = errors
        error_details = None
    else:
        error_message = "Validation failed"
        error_details = {'validation_errors': errors}
    
    return error_response(
        error=error_message,
        status_code=422,
        details=error_details
    )

def not_found_response(resource: str = "Resource") -> tuple:
    """Create not found error response
    
    Args:
        resource: Name of the resource not found
        
    Returns:
        Tuple of (response, status_code)
    """
    return error_response(
        error=f"{resource} not found",
        status_code=404
    )

def unauthorized_response(message: str = "Authentication required") -> tuple:
    """Create unauthorized error response
    
    Args:
        message: Authentication error message
        
    Returns:
        Tuple of (response, status_code)
    """
    return error_response(
        error=message,
        status_code=401,
        headers={'WWW-Authenticate': 'Bearer'}
    )

def forbidden_response(message: str = "Insufficient permissions") -> tuple:
    """Create forbidden error response
    
    Args:
        message: Authorization error message
        
    Returns:
        Tuple of (response, status_code)
    """
    return error_response(
        error=message,
        status_code=403
    )

def conflict_response(message: str = "Resource conflict") -> tuple:
    """Create conflict error response
    
    Args:
        message: Conflict error message
        
    Returns:
        Tuple of (response, status_code)
    """
    return error_response(
        error=message,
        status_code=409
    )

def server_error_response(message: str = "Internal server error") -> tuple:
    """Create server error response
    
    Args:
        message: Server error message
        
    Returns:
        Tuple of (response, status_code)
    """
    return error_response(
        error=message,
        status_code=500
    )

def service_unavailable_response(message: str = "Service temporarily unavailable") -> tuple:
    """Create service unavailable response
    
    Args:
        message: Service unavailable message
        
    Returns:
        Tuple of (response, status_code)
    """
    return error_response(
        error=message,
        status_code=503
    )

def paginated_response(
    items: List[Any],
    page: int,
    per_page: int,
    total: int,
    endpoint: str = None
) -> Dict[str, Any]:
    """Create paginated response data
    
    Args:
        items: List of items for current page
        page: Current page number
        per_page: Items per page
        total: Total number of items
        endpoint: API endpoint for pagination links
        
    Returns:
        Paginated response data
    """
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    pagination_data = {
        'items': items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    }
    
    # Add pagination links if endpoint provided
    if endpoint:
        base_url = request.url_root.rstrip('/') + endpoint
        pagination_data['pagination']['links'] = {}
        
        if page > 1:
            pagination_data['pagination']['links']['prev'] = f"{base_url}?page={page-1}&per_page={per_page}"
        
        if page < total_pages:
            pagination_data['pagination']['links']['next'] = f"{base_url}?page={page+1}&per_page={per_page}"
        
        pagination_data['pagination']['links']['first'] = f"{base_url}?page=1&per_page={per_page}"
        pagination_data['pagination']['links']['last'] = f"{base_url}?page={total_pages}&per_page={per_page}"
    
    return pagination_data

def file_response(
    file_data: bytes,
    filename: str,
    mimetype: str = 'application/octet-stream',
    as_attachment: bool = True
) -> Any:
    """Create file download response
    
    Args:
        file_data: File content as bytes
        filename: Name for downloaded file
        mimetype: MIME type of the file
        as_attachment: Whether to force download or display inline
        
    Returns:
        Flask response for file download
    """
    response = make_response(file_data)
    response.headers['Content-Type'] = mimetype
    
    if as_attachment:
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    else:
        response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
    
    return response

def streaming_response(generator, mimetype: str = 'text/plain'):
    """Create streaming response
    
    Args:
        generator: Generator function that yields response chunks
        mimetype: MIME type of the response
        
    Returns:
        Flask streaming response
    """
    from flask import Response
    
    return Response(generator, mimetype=mimetype)

def cors_response(response, origins: str = '*', methods: str = 'GET,POST,PUT,DELETE', headers: str = '*'):
    """Add CORS headers to response
    
    Args:
        response: Flask response object
        origins: Allowed origins
        methods: Allowed methods
        headers: Allowed headers
        
    Returns:
        Response with CORS headers
    """
    response.headers['Access-Control-Allow-Origin'] = origins
    response.headers['Access-Control-Allow-Methods'] = methods
    response.headers['Access-Control-Allow-Headers'] = headers
    return response

def cache_response(response, max_age: int = 3600, public: bool = True):
    """Add cache headers to response
    
    Args:
        response: Flask response object
        max_age: Cache max age in seconds
        public: Whether cache can be public
        
    Returns:
        Response with cache headers
    """
    cache_control = f"{'public' if public else 'private'}, max-age={max_age}"
    response.headers['Cache-Control'] = cache_control
    return response

def no_cache_response(response):
    """Add no-cache headers to response
    
    Args:
        response: Flask response object
        
    Returns:
        Response with no-cache headers
    """
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

def get_pagination_params(default_page: int = 1, default_per_page: int = 20, max_per_page: int = 100) -> tuple:
    """Get pagination parameters from request
    
    Args:
        default_page: Default page number
        default_per_page: Default items per page
        max_per_page: Maximum allowed items per page
        
    Returns:
        Tuple of (page, per_page)
    """
    try:
        page = int(request.args.get('page', default_page))
        per_page = int(request.args.get('per_page', default_per_page))
        
        # Validate values
        page = max(1, page)
        per_page = max(1, min(per_page, max_per_page))
        
        return page, per_page
        
    except (ValueError, TypeError):
        return default_page, default_per_page