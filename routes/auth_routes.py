"""
Authentication routes - login, register, logout, session management
"""

import logging
import bcrypt
from flask import Blueprint, request, jsonify, session
from services.fabric_service import fabric_service
from middleware.auth import validate_session, create_session, destroy_session, login_required
from middleware.error_handlers import ValidationError, DatabaseError

logger = logging.getLogger(__name__)

# Create blueprint
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/check', methods=['GET'])
def check_auth():
    """Check current authentication status"""
    try:
        session_data = validate_session()
        
        if session_data['valid']:
            return jsonify({
                'success': True,
                'user': session_data['user']
            }), 200
        else:
            return jsonify({
                'success': False, 
                'message': session_data['message']
            }), 401
            
    except Exception as e:
        logger.error(f"Error checking authentication: {e}")
        return jsonify({
            'success': False, 
            'message': 'Authentication check failed'
        }), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        # Get login data
        data = request.get_json() if request.is_json else request.form
        email = data.get('username') or data.get('email')
        password = data.get('password')
        
        if not email or not password:
            raise ValidationError('Email and password are required')
        
        logger.info(f"Login attempt for: {email}")
        
        # Admin shortcut for development
        if email == "admin" and password == "admin":
            session_data = {
                'id': 1,
                'email': 'admin@example.com',
                'first_name': 'Admin'
            }
            
            if create_session(session_data):
                return jsonify({
                    'success': True,
                    'message': 'Login successful',
                    'user': session_data
                }), 200
        
        # Regular user authentication
        user = fabric_service.get_user_by_email(email.lower())
        
        if not user:
            logger.warning(f"Login failed - user not found: {email}")
            return jsonify({
                'success': False, 
                'message': 'Invalid credentials'
            }), 401
        
        # Verify password
        if not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            logger.warning(f"Login failed - invalid password: {email}")
            return jsonify({
                'success': False, 
                'message': 'Invalid credentials'
            }), 401
        
        # Create session
        session_data = {
            'id': user['id'],
            'email': user['email'],
            'first_name': user['first_name']
        }
        
        if create_session(session_data):
            logger.info(f"Login successful: {email}")
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user': session_data
            }), 200
        else:
            raise DatabaseError('Failed to create session')
            
    except ValidationError as e:
        return jsonify({'success': False, 'message': e.message}), 400
    except DatabaseError as e:
        logger.error(f"Database error during login: {e}")
        return jsonify({'success': False, 'message': 'Login failed'}), 500
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}")
        return jsonify({'success': False, 'message': 'Login failed'}), 500

@auth_bp.route('/register', methods=['POST'])
def register():
    """User registration endpoint"""
    try:
        # Get registration data
        data = request.get_json() if request.is_json else request.form
        
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        email = data.get('email')
        mobile = data.get('mobile')
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        
        # Validate required fields
        required_fields = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'mobile': mobile,
            'password': password,
            'confirm_password': confirm_password
        }
        
        missing_fields = [field for field, value in required_fields.items() if not value]
        if missing_fields:
            raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Validate password confirmation
        if password != confirm_password:
            raise ValidationError('Passwords do not match')
        
        # Validate email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValidationError('Invalid email format')
        
        # Check if user already exists
        existing_user = fabric_service.get_user_by_email(email.lower())
        if existing_user:
            return jsonify({
                'success': False, 
                'message': 'User already exists with this email'
            }), 409
        
        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Create user
        user_data = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email.lower(),
            'mobile': mobile,
            'password': hashed_password
        }
        
        user_id = fabric_service.create_user(user_data)
        
        # Create session for new user
        session_data = {
            'id': user_id,
            'email': email.lower(),
            'first_name': first_name
        }
        
        if create_session(session_data):
            logger.info(f"User registered successfully: {email}")
            return jsonify({
                'success': True,
                'message': 'Registration successful',
                'user': session_data
            }), 201
        else:
            raise DatabaseError('Failed to create session after registration')
            
    except ValidationError as e:
        return jsonify({'success': False, 'message': e.message}), 400
    except DatabaseError as e:
        logger.error(f"Database error during registration: {e}")
        return jsonify({'success': False, 'message': 'Registration failed'}), 500
    except Exception as e:
        logger.error(f"Unexpected error during registration: {e}")
        return jsonify({'success': False, 'message': 'Registration failed'}), 500

@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """User logout endpoint"""
    try:
        user_email = session.get('user_email', 'unknown')
        
        # Clean up any session data
        from utils.session_utils import cleanup_user_session
        cleanup_user_session()
        
        # Destroy session
        destroy_session()
        
        logger.info(f"User logged out: {user_email}")
        return jsonify({
            'success': True, 
            'message': 'Logged out successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        return jsonify({
            'success': False, 
            'message': 'Logout failed'
        }), 500

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Password reset endpoint"""
    try:
        data = request.get_json() if request.is_json else request.form
        
        email = data.get('email')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not all([email, new_password, confirm_password]):
            raise ValidationError('All fields are required')
        
        if new_password != confirm_password:
            raise ValidationError('Passwords do not match')
        
        # Check if user exists
        user = fabric_service.get_user_by_email(email.lower())
        if not user:
            # Don't reveal if email exists or not for security
            return jsonify({
                'success': True, 
                'message': 'If the email exists, password reset instructions have been sent'
            }), 200
        
        # Hash new password
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Update password
        fabric_service.execute_non_query(
            "UPDATE login_details SET password = ? WHERE email = ?",
            (hashed_password, email.lower())
        )
        
        logger.info(f"Password reset successful for: {email}")
        return jsonify({
            'success': True, 
            'message': 'Password reset successful'
        }), 200
        
    except ValidationError as e:
        return jsonify({'success': False, 'message': e.message}), 400
    except Exception as e:
        logger.error(f"Error during password reset: {e}")
        return jsonify({'success': False, 'message': 'Password reset failed'}), 500
