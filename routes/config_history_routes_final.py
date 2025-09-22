"""
Configuration History Routes - Using Your Existing Excel Templates Table
Shows user's configured templates as configuration history
"""

import json
import logging
from flask import Blueprint, request, jsonify, session
from backend.services.fabric_service import fabric_service

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

# Configuration History Routes - Using Your Excel Templates Table
@config_history_bp.route('', methods=['GET'])
@monitor_api_performance("get_configuration_history")
def get_configuration_history():
    """Get user's excel templates as configuration history"""
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
        
        # Get user's excel templates as configuration history
        # Using your exact table structure and column names
        history_query = """
        SELECT 
            template_id,
            template_name,
            created_at,
            updated_at,
            sheet_name,
            headers,
            status,
            is_corrected
        FROM excel_templates
        WHERE user_id = ? AND status = 'ACTIVE'
        ORDER BY created_at DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
        
        history_records = fabric_service.execute_query(history_query, (session['user_id'], offset, limit))
        
        # Get total count for this user
        count_query = """
        SELECT COUNT(*) as total 
        FROM excel_templates 
        WHERE user_id = ? AND status = 'ACTIVE'
        """
        total_result = fabric_service.execute_query(count_query, (session['user_id'],))
        total_count = total_result[0]['total'] if total_result else 0
        
        # Format records for configuration history display
        formatted_history = []
        for record in history_records:
            try:
                # Parse headers JSON - your format: '["name", "email", "date", "num"]'
                headers = []
                if record['headers']:
                    try:
                        headers = json.loads(record['headers'])
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse headers for template {record['template_id']}")
                        headers = []
                
                # Get validation rules count for this template
                rules_query = """
                SELECT COUNT(*) as rule_count
                FROM template_columns tc
                LEFT JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
                WHERE tc.template_id = ?
                """
                
                try:
                    rules_result = fabric_service.execute_query(rules_query, (record['template_id'],))
                    total_rules = rules_result[0]['rule_count'] if rules_result else 0
                except:
                    total_rules = 0
                
                # Get configured columns count
                columns_query = """
                SELECT COUNT(DISTINCT tc.column_id) as column_count
                FROM template_columns tc
                WHERE tc.template_id = ?
                """
                
                try:
                    columns_result = fabric_service.execute_query(columns_query, (record['template_id'],))
                    configured_columns = columns_result[0]['column_count'] if columns_result else 0
                except:
                    configured_columns = len(headers)  # Fallback to headers count
                
                # Create configuration summary
                if configured_columns > 0 and total_rules > 0:
                    configuration_summary = f"{configured_columns} columns configured with {total_rules} validation rules"
                elif configured_columns > 0:
                    configuration_summary = f"{configured_columns} columns configured (no validation rules yet)"
                else:
                    configuration_summary = "Template created, configuration pending"
                
                # Clean up template name for display (remove UUID parts if present)
                display_name = record['template_name']
                if '_' in display_name and len(display_name) > 50:  # Looks like it has UUID
                    # Extract original filename from your naming pattern: user_uuid_filename.xlsx
                    parts = display_name.split('_', 2)
                    if len(parts) >= 3:
                        display_name = parts[2]  # Get the filename part
                
                # Format for history display using your exact data structure
                formatted_record = {
                    'history_id': record['template_id'],  # Use template_id as history_id
                    'template_id': record['template_id'],
                    'file_name': display_name,  # Clean display name
                    'original_file_name': record['template_name'],  # Full original name
                    'sheet_name': record['sheet_name'] or 'Sheet1',
                    'headers': headers,
                    'headers_count': len(headers),
                    'total_rules': total_rules,
                    'configured_columns': configured_columns,
                    'configuration_summary': configuration_summary,
                    'status': 'VALIDATED' if record['is_corrected'] else 'CONFIGURED',
                    'configured_date': record['created_at'].strftime('%Y-%m-%d %H:%M') if record['created_at'] else '',
                    'last_updated': record['updated_at'].strftime('%Y-%m-%d %H:%M') if record['updated_at'] else '',
                    'can_revalidate': total_rules > 0,
                    'can_reconfigure': True,
                    'template_exists': True,
                    'is_corrected': bool(record['is_corrected']) if record['is_corrected'] is not None else False
                }
                
                formatted_history.append(formatted_record)
                
            except Exception as parse_error:
                logger.warning(f"Error parsing template record {record['template_id']}: {parse_error}")
                # Add basic record even if parsing fails
                formatted_record = {
                    'history_id': record['template_id'],
                    'template_id': record['template_id'],
                    'file_name': record['template_name'],
                    'sheet_name': record['sheet_name'] or 'Sheet1',
                    'headers': [],
                    'headers_count': 0,
                    'total_rules': 0,
                    'configured_columns': 0,
                    'configuration_summary': 'Configuration error',
                    'status': 'ERROR',
                    'configured_date': record['created_at'].strftime('%Y-%m-%d %H:%M') if record['created_at'] else '',
                    'can_revalidate': False,
                    'template_exists': True
                }
                formatted_history.append(formatted_record)
        
        # Response
        response_data = {
            'success': True,
            'history': formatted_history,
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + limit) < total_count
            },
            'performance': {
                'cache_enabled': REDIS_AVAILABLE,
                'records_found': len(formatted_history),
                'total_templates': total_count
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

@config_history_bp.route('/<int:template_id>', methods=['DELETE'])
@monitor_api_performance("delete_template_configuration")
def delete_template_configuration(template_id):
    """Delete template configuration"""
    try:
        # Check authentication
        auth_check = check_login()
        if auth_check:
            return auth_check
        
        # Check if template exists and belongs to user
        template_query = """
        SELECT template_id, template_name 
        FROM excel_templates 
        WHERE template_id = ? AND user_id = ? AND status = 'ACTIVE'
        """
        template_result = fabric_service.execute_query(template_query, (template_id, session['user_id']))
        
        if not template_result:
            return jsonify({
                'success': False, 
                'message': 'Template configuration not found or access denied'
            }), 404
        
        template_name = template_result[0]['template_name']
        
        # Soft delete by changing status (preserve data)
        delete_query = """
        UPDATE excel_templates 
        SET status = 'DELETED', updated_at = GETDATE()
        WHERE template_id = ? AND user_id = ?
        """
        
        fabric_service.execute_non_query(delete_query, (template_id, session['user_id']))
        
        logger.info(f"Deleted template configuration {template_id}: {template_name} for user {session['user_id']}")
        
        return jsonify({
            'success': True, 
            'message': f'Configuration "{template_name}" deleted successfully',
            'performance': {
                'cache_enabled': REDIS_AVAILABLE
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting template configuration {template_id}: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to delete template configuration'
        }), 500

@config_history_bp.route('/<int:template_id>/details', methods=['GET'])
@monitor_api_performance("get_template_configuration_details")
def get_template_configuration_details(template_id):
    """Get detailed configuration for a specific template"""
    try:
        # Check authentication
        auth_check = check_login()
        if auth_check:
            return auth_check
        
        # Get template details using your exact table structure
        template_query = """
        SELECT 
            template_id,
            template_name,
            created_at,
            updated_at,
            sheet_name,
            headers,
            status,
            is_corrected
        FROM excel_templates
        WHERE template_id = ? AND user_id = ? AND status = 'ACTIVE'
        """
        
        template_result = fabric_service.execute_query(template_query, (template_id, session['user_id']))
        
        if not template_result:
            return jsonify({
                'success': False, 
                'message': 'Template configuration not found or access denied'
            }), 404
        
        template = template_result[0]
        
        # Parse headers JSON
        headers = []
        if template['headers']:
            try:
                headers = json.loads(template['headers'])
            except json.JSONDecodeError:
                logger.warning(f"Could not parse headers for template {template_id}")
                headers = []
        
        # Get column details with validation rules
        columns_query = """
        SELECT 
            tc.column_id,
            tc.column_name,
            tc.data_type,
            tc.is_required,
            tc.column_order,
            vrt.rule_name
        FROM template_columns tc
        LEFT JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
        LEFT JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
        WHERE tc.template_id = ?
        ORDER BY tc.column_order, tc.column_name
        """
        
        try:
            columns_raw = fabric_service.execute_query(columns_query, (template_id,))
            
            # Group validation rules by column
            columns_dict = {}
            for row in columns_raw:
                col_id = row['column_id']
                if col_id not in columns_dict:
                    columns_dict[col_id] = {
                        'column_id': col_id,
                        'column_name': row['column_name'],
                        'data_type': row['data_type'],
                        'is_required': bool(row['is_required']) if row['is_required'] is not None else False,
                        'column_order': row['column_order'],
                        'validation_rules': []
                    }
                
                if row['rule_name']:
                    columns_dict[col_id]['validation_rules'].append(row['rule_name'])
            
            columns = list(columns_dict.values())
            
        except Exception as col_error:
            logger.warning(f"Error getting column details for template {template_id}: {col_error}")
            # Fallback to headers only
            columns = [
                {
                    'column_name': header,
                    'data_type': 'text',
                    'is_required': False,
                    'validation_rules': []
                }
                for header in headers
            ]
        
        # Clean up template name for display
        display_name = template['template_name']
        if '_' in display_name and len(display_name) > 50:
            parts = display_name.split('_', 2)
            if len(parts) >= 3:
                display_name = parts[2]
        
        # Format detailed response using your data structure
        detailed_config = {
            'template_id': template['template_id'],
            'template_name': display_name,
            'full_template_name': template['template_name'],
            'created_date': template['created_at'].strftime('%Y-%m-%d %H:%M:%S') if template['created_at'] else '',
            'last_updated': template['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if template['updated_at'] else '',
            'file_info': {
                'sheet_name': template['sheet_name'] or 'Sheet1',
                'headers': headers,
                'headers_count': len(headers)
            },
            'columns': columns,
            'statistics': {
                'total_headers': len(headers),
                'configured_columns': len(columns),
                'total_rules': sum(len(col.get('validation_rules', [])) for col in columns)
            },
            'status': template['status'],
            'is_corrected': bool(template['is_corrected']) if template['is_corrected'] is not None else False
        }
        
        return jsonify({
            'success': True,
            'configuration': detailed_config
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting template configuration details for {template_id}: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to get template configuration details'
        }), 500

# Stats endpoint using your excel_templates table
@config_history_bp.route('/stats', methods=['GET'])
@monitor_api_performance("get_template_stats")
def get_template_configuration_stats():
    """Get template configuration statistics for the current user"""
    try:
        # Check authentication
        auth_check = check_login()
        if auth_check:
            return auth_check
        
        # Get user's template statistics using your exact table structure
        stats_query = """
        SELECT 
            COUNT(*) as total_templates,
            MAX(created_at) as last_template_date,
            COUNT(CASE WHEN is_corrected = 1 THEN 1 END) as corrected_templates,
            COUNT(CASE WHEN is_corrected = 0 OR is_corrected IS NULL THEN 1 END) as pending_templates
        FROM excel_templates
        WHERE user_id = ? AND status = 'ACTIVE'
        """
        
        stats_result = fabric_service.execute_query(stats_query, (session['user_id'],))
        
        if not stats_result:
            stats = {
                'total_templates': 0,
                'last_template_date': None,
                'corrected_templates': 0,
                'pending_templates': 0
            }
        else:
            stats = stats_result[0]
        
        # Get total rules count for this user
        rules_query = """
        SELECT COUNT(*) as total_rules
        FROM column_validation_rules cvr
        INNER JOIN template_columns tc ON cvr.column_id = tc.column_id
        INNER JOIN excel_templates et ON tc.template_id = et.template_id
        WHERE et.user_id = ? AND et.status = 'ACTIVE'
        """
        
        try:
            rules_result = fabric_service.execute_query(rules_query, (session['user_id'],))
            total_rules = rules_result[0]['total_rules'] if rules_result else 0
        except:
            total_rules = 0
        
        # Format response
        formatted_stats = {
            'total_configurations': stats['total_templates'] or 0,
            'total_rules_created': total_rules or 0,
            'corrected_files': stats['corrected_templates'] or 0,
            'pending_validation': stats['pending_templates'] or 0,
            'last_configuration': stats['last_template_date'].strftime('%Y-%m-%d %H:%M') if stats['last_template_date'] else 'Never',
            'validation_progress': {
                'corrected': stats['corrected_templates'] or 0,
                'pending': stats['pending_templates'] or 0,
                'correction_rate': round((stats['corrected_templates'] or 0) / max(stats['total_templates'] or 1, 1) * 100, 1)
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
        logger.error(f"Error getting template configuration stats: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to get configuration statistics'
        }), 500

# Helper function for compatibility (if needed elsewhere in your app)
def save_configuration_history(*args, **kwargs):
    """
    Compatibility function - your configurations are already saved in excel_templates
    This function exists for compatibility with any existing code
    """
    logger.info("Configuration already saved in excel_templates table")
    return True
