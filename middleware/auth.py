"""
Authentication middleware and utilities
"""

import logging
from functools import wraps
from flask import session, request, jsonify, g
from services.fabric_service import fabric_service

logger = logging.getLogger(__name__)

def auth_middleware(app):
    """Register authentication middleware"""
    
    @app.before_request
    def load_logged_in_user():
        """Load user information if logged in"""
        user_id = session.get('user_id')
        
        if user_id is None:
            g.user = None
        else:
            try:
                users = fabric_service.execute_query(
                    "SELECT id, email, first_name, last_name FROM login_details WHERE id = ?",
                    (user_id,)
                )
                g.user = users[0] if users else None
                
                if g.user is None:
                    # User not found, clear session
                    session.clear()
                    
            except Exception as e:
                logger.error(f"Error loading user: {e}")
                g.user = None

def login_required(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session or 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('loggedin') or session.get('user_id') != 1:
            return jsonify({'success': False, 'message': 'Admin privileges required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def validate_session():
    """Validate current session"""
    try:
        if 'loggedin' in session and 'user_id' in session:
            user_data = fabric_service.execute_query(
                "SELECT email, first_name FROM login_details WHERE id = ?",
                (session['user_id'],)
            )
            
            if user_data:
                return {
                    'valid': True,
                    'user': {
                        'email': user_data[0]['email'],
                        'id': session['user_id'],
                        'first_name': user_data[0]['first_name']
                    }
                }
            else:
                session.clear()
                return {'valid': False, 'message': 'User not found'}
        
        return {'valid': False, 'message': 'Not logged in'}
        
    except Exception as e:
        logger.error(f"Session validation error: {e}")
        return {'valid': False, 'message': 'Session validation failed'}

def create_session(user_data):
    """Create user session"""
    try:
        session.clear()
        session['loggedin'] = True
        session['user_id'] = user_data['id']
        session['user_email'] = user_data['email']
        session.permanent = True
        
        logger.info(f"Session created for user: {user_data['email']}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        return False

def destroy_session():
    """Destroy user session"""
    try:
        user_email = session.get('user_email', 'unknown')
        session.clear()
        logger.info(f"Session destroyed for user: {user_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to destroy session: {e}")
        return False
