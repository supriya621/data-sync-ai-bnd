"""
Configuration History Routes - File Configuration History Management
Tracks when users configure files with validation rules
"""

import json
import logging
from flask import Blueprint, request, jsonify, session
from backend.services.fabric_service import fabric_service
from file_configuration_history import (
    get_user_configuration_history, 
    delete_configuration_history,
    save_file_configuration_history
)

# Create blueprint
config_history_bp = Blueprint('config_history', __name__)

# Setup logging
logger = logging.getLogger(__name__)

# Import Redis service if available
try:
    from backend.services.redis_service import redis_service
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

def monitor_api_performance(operation_name):
    """Decorator to monitor API performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"[PERF] {operation_name}: {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"[PERF] {operation_name} failed: {duration:.3f}s - {str(e)}")
                raise
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

def check_login():
    """Check if user is logged in"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Authentication required'}), 401
    return None

# Configuration History Routes
@config_history_bp.route('', methods=['GET'])
@monitor_api_performance("get_configuration_history")
def get_configuration_history():
    """Get file configuration history for the current user"""
    try:
        # Check authentication
        auth_check = check_login()
        if auth_check:
            return auth_check
            
        # Get pagination parameters
        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Validate pagination parameters
        limit = min(max(limit, 1), 100)  # Between 1 and 100
        offset = max(offset, 0)  # Non-negative
        
        # Get configuration history using helper function
        history_data = get_user_configuration_history(
            user_id=session['user_id'],
            limit=limit,
            offset=offset
        )
        
        if not history_data['success']:
            return jsonify({
                'success': False, 
                'message': history_data.get('message', 'Failed to get configuration history')
            }), 500
        
        # Add performance metrics
        response_data = {
            'success': True,
            'history': history_data['history'],
            'pagination': history_data['pagination'],
            'performance': {
                'cache_enabled': REDIS_AVAILABLE,
                'records_found': len(history_data['history']),
                'total_records': history_data['pagination']['total']
            }
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error getting configuration history: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to get configuration history',
            'error_details': str(e)
        }), 500

@config_history_bp.route('/<int:history_id>', methods=['DELETE'])
@monitor_api_performance("delete_configuration_history")
def delete_configuration_history_route(history_id):
    """Delete configuration history record (soft delete)"""
    try:
        # Check authentication
        auth_check = check_login()
        if auth_check:
            return auth_check
        
        # Delete using helper function
        success = delete_configuration_history(history_id, session['user_id'])
        
        if not success:
            return jsonify({
                'success': False, 
                'message': 'Configuration history not found or access denied'
            }), 404
        
        return jsonify({
            'success': True, 
            'message': 'Configuration history deleted successfully',
            'performance': {
                'cache_enabled': REDIS_AVAILABLE
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting configuration history {history_id}: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to delete configuration history'
        }), 500

@config_history_bp.route('/<int:history_id>/details', methods=['GET'])
@monitor_api_performance("get_configuration_details")
def get_configuration_details(history_id):
    """Get detailed configuration information for a specific history record"""
    try:
        # Check authentication
        auth_check = check_login()
        if auth_check:
            return auth_check
        
        # Get detailed configuration
        details_query = """
        SELECT 
            history_id,
            file_name,
            original_file_name,
            sheet_name,
            file_headers,
            configured_rules,
            total_rules_configured,
            configured_columns_count,
            configuration_summary,
            file_size_mb,
            total_rows,
            validation_status,
            created_at,
            updated_at
        FROM rule_configuration_history
        WHERE history_id = ? AND user_id = ? AND is_active = 1
        """
        
        details = fabric_service.execute_query(details_query, (history_id, session['user_id']))
        
        if not details:
            return jsonify({
                'success': False, 
                'message': 'Configuration history not found'
            }), 404
        
        record = details[0]
        
        # Parse JSON fields
        try:
            headers = json.loads(record['file_headers']) if record['file_headers'] else []
            configured_rules = json.loads(record['configured_rules']) if record['configured_rules'] else {}
        except json.JSONDecodeError:
            headers = []
            configured_rules = {}
            logger.warning(f"Failed to parse JSON for history {history_id}")
        
        # Format detailed response
        detailed_config = {
            'history_id': record['history_id'],
            'file_name': record['original_file_name'],
            'internal_file_name': record['file_name'],
            'sheet_name': record['sheet_name'],
            'file_headers': headers,
            'configured_rules': configured_rules,
            'statistics': {
                'total_rules': record['total_rules_configured'],
                'configured_columns': record['configured_columns_count'],
                'total_headers': len(headers),
                'file_size_mb': float(record['file_size_mb']) if record['file_size_mb'] else 0,
                'total_rows': record['total_rows'] or 0
            },
            'configuration_summary': record['configuration_summary'],
            'validation_status': record['validation_status'],
            'timestamps': {
                'configured_date': record['created_at'].strftime('%Y-%m-%d %H:%M:%S') if record['created_at'] else '',
                'last_updated': record['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if record['updated_at'] else ''
            }
        }
        
        return jsonify({
            'success': True,
            'configuration': detailed_config
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting configuration details for {history_id}: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to get configuration details'
        }), 500

# Helper function for other parts of the application to save configuration history
def save_configuration_history(user_id, file_name, original_file_name, file_headers, 
                              configured_rules, sheet_name=None, file_size_mb=None, 
                              total_rows=None):
    """
    Public function to save file configuration history from other parts of the application
    This is the main integration point for your file upload/configuration workflow
    """
    return save_file_configuration_history(
        user_id=user_id,
        file_name=file_name,
        original_file_name=original_file_name,
        file_headers=file_headers,
        configured_rules=configured_rules,
        sheet_name=sheet_name,
        file_size_mb=file_size_mb,
        total_rows=total_rows
    )

# Stats endpoint for dashboard
@config_history_bp.route('/stats', methods=['GET'])
@monitor_api_performance("get_configuration_stats")
def get_configuration_stats():
    """Get configuration statistics for the current user"""
    try:
        # Check authentication
        auth_check = check_login()
        if auth_check:
            return auth_check
        
        # Get user statistics
        stats_query = """
        SELECT 
            COUNT(*) as total_configurations,
            SUM(total_rules_configured) as total_rules_created,
            AVG(configured_columns_count) as avg_columns_configured,
            SUM(file_size_mb) as total_file_size_processed,
            SUM(total_rows) as total_rows_processed,
            MAX(created_at) as last_configuration_date,
            COUNT(CASE WHEN validation_status = 'VALIDATED' THEN 1 END) as validated_files,
            COUNT(CASE WHEN validation_status = 'CONFIGURED' THEN 1 END) as pending_validation
        FROM rule_configuration_history
        WHERE user_id = ? AND is_active = 1
        """
        
        stats_result = fabric_service.execute_query(stats_query, (session['user_id'],))
        
        if not stats_result:
            # Return zero stats if no records
            stats = {
                'total_configurations': 0,
                'total_rules_created': 0,
                'avg_columns_configured': 0,
                'total_file_size_processed': 0,
                'total_rows_processed': 0,
                'last_configuration_date': None,
                'validated_files': 0,
                'pending_validation': 0
            }
        else:
            stats = stats_result[0]
        
        # Format the response
        formatted_stats = {
            'total_configurations': stats['total_configurations'] or 0,
            'total_rules_created': stats['total_rules_created'] or 0,
            'avg_columns_configured': round(float(stats['avg_columns_configured'] or 0), 1),
            'total_file_size_mb': round(float(stats['total_file_size_processed'] or 0), 2),
            'total_rows_processed': stats['total_rows_processed'] or 0,
            'last_configuration': stats['last_configuration_date'].strftime('%Y-%m-%d %H:%M') if stats['last_configuration_date'] else 'Never',
            'validation_progress': {
                'validated_files': stats['validated_files'] or 0,
                'pending_validation': stats['pending_validation'] or 0,
                'validation_rate': round((stats['validated_files'] or 0) / max(stats['total_configurations'] or 1, 1) * 100, 1)
            }
        }
        
        return jsonify({
            'success': True,
            'stats': formatted_stats,
            'performance': {
                'cache_enabled': REDIS_AVAILABLE
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting configuration stats: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to get configuration statistics'
        }), 500
