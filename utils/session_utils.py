"""
Session management utilities
"""

import uuid
import logging
from flask import session
from services.duckdb_service import duckdb_service

logger = logging.getLogger(__name__)

def get_session_id():
    """Get or create session ID for DuckDB operations"""
    if 'session_uuid' not in session:
        session['session_uuid'] = str(uuid.uuid4())
    return session['session_uuid']

def cleanup_user_session():
    """Clean up user session data including DuckDB temporary data"""
    try:
        session_id = get_session_id()
        template_id = session.get('template_id')
        
        # Cleanup DuckDB session data if exists
        if template_id:
            try:
                duckdb_service.cleanup_session_data(session_id, template_id)
                logger.info(f"Cleaned up DuckDB data for session {session_id}, template {template_id}")
            except Exception as e:
                logger.warning(f"Failed to cleanup DuckDB session data: {e}")
        
        # Clear specific session keys while preserving authentication
        session_keys_to_clear = [
            'df', 'header_row', 'headers', 'sheet_name', 'current_step',
            'selected_headers', 'validations', 'error_cell_locations',
            'data_rows', 'corrected_file_path', 'file_path', 'template_id',
            'has_existing_rules', 'is_large_file', 'processing_time',
            'duckdb_loaded', 'corrections', 'validation_results'
        ]
        
        for key in session_keys_to_clear:
            session.pop(key, None)
        
        logger.info(f"Session cleanup completed for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error during session cleanup: {e}")

def get_session_data():
    """Get current session data for debugging/monitoring"""
    return {
        'session_id': get_session_id(),
        'user_id': session.get('user_id'),
        'user_email': session.get('user_email'),
        'template_id': session.get('template_id'),
        'current_step': session.get('current_step'),
        'is_large_file': session.get('is_large_file', False),
        'has_existing_rules': session.get('has_existing_rules', False),
        'processing_time': session.get('processing_time'),
        'keys_count': len(session.keys())
    }

def validate_session_data(required_keys=None):
    """Validate that required session data exists"""
    if required_keys is None:
        required_keys = ['user_id', 'loggedin']
    
    missing_keys = []
    for key in required_keys:
        if key not in session:
            missing_keys.append(key)
    
    return {
        'valid': len(missing_keys) == 0,
        'missing_keys': missing_keys,
        'session_data': get_session_data()
    }

def store_validation_state(validation_data):
    """Store validation state in session"""
    try:
        session['validation_state'] = {
            'error_cell_locations': validation_data.get('error_cell_locations', {}),
            'data_rows': validation_data.get('data_rows', []),
            'processing_time': validation_data.get('processing_time_ms', 0),
            'processing_method': validation_data.get('processing_method', 'unknown'),
            'timestamp': validation_data.get('timestamp')
        }
        logger.info("Validation state stored in session")
    except Exception as e:
        logger.error(f"Failed to store validation state: {e}")

def get_validation_state():
    """Get validation state from session"""
    return session.get('validation_state', {})

def clear_validation_state():
    """Clear validation state from session"""
    session.pop('validation_state', None)
    logger.info("Validation state cleared from session")

def is_session_expired():
    """Check if session has expired"""
    import time
    from flask import current_app
    
    last_activity = session.get('last_activity')
    if not last_activity:
        return True
    
    session_lifetime = current_app.config.get('PERMANENT_SESSION_LIFETIME', 86400)
    return (time.time() - last_activity) > session_lifetime

def refresh_session():
    """Refresh session activity timestamp"""
    import time
    session['last_activity'] = time.time()
    session.permanent = True
