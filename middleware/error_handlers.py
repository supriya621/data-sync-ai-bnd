"""
Error handlers and exception management
"""

import logging
from flask import jsonify, request
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

def register_error_handlers(app):
    """Register global error handlers"""
    
    @app.errorhandler(400)
    def bad_request(error):
        """Handle bad request errors"""
        logger.warning(f"Bad request: {request.url} - {error}")
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': 'Invalid request data'
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        """Handle unauthorized errors"""
        logger.warning(f"Unauthorized access: {request.url}")
        return jsonify({
            'success': False,
            'error': 'Unauthorized',
            'message': 'Authentication required'
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        """Handle forbidden errors"""
        logger.warning(f"Forbidden access: {request.url}")
        return jsonify({
            'success': False,
            'error': 'Forbidden',
            'message': 'Insufficient permissions'
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle not found errors"""
        logger.warning(f"Resource not found: {request.url}")
        return jsonify({
            'success': False,
            'error': 'Not Found',
            'message': 'Resource not found'
        }), 404
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        """Handle file too large errors"""
        logger.warning(f"File too large: {request.url}")
        return jsonify({
            'success': False,
            'error': 'File Too Large',
            'message': f'File size exceeds {app.config.get("MAX_CONTENT_LENGTH", 0) // (1024*1024)}MB limit'
        }), 413
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle internal server errors"""
        logger.error(f"Internal server error: {request.url} - {error}")
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle all other unexpected errors"""
        logger.error(f"Unexpected error: {request.url} - {str(error)}", exc_info=True)
        
        # Don't expose internal error details in production
        from config.config import config
        if config.DEBUG:
            message = str(error)
        else:
            message = 'An unexpected error occurred'
        
        return jsonify({
            'success': False,
            'error': 'Unexpected Error',
            'message': message
        }), 500

class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(self.message)

class FileProcessingError(Exception):
    """Custom file processing error"""
    def __init__(self, message, filename=None):
        self.message = message
        self.filename = filename
        super().__init__(self.message)

class DatabaseError(Exception):
    """Custom database error"""
    def __init__(self, message, operation=None):
        self.message = message
        self.operation = operation
        super().__init__(self.message)
