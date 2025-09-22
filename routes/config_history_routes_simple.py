"""
Configuration History Routes - Using Existing Excel Templates Table
Show user's configured templates in the configuration history section
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

# Configuration History Routes - Using Excel Templates
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
        # Note: Add user_id to excel_templates table if not exists
        history_query = """
        SELECT 
            id as template_id,
            name as template_name,
            description,
            created_date,
            template_config,
            (SELECT COUNT(*) FROM template_columns tc WHERE tc.template_id = et.id) as configured_columns_count
        FROM excel_templates et
        ORDER BY created_date DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
        
        # If you have user_id in excel_templates, add WHERE clause:
        # WHERE user_id = ?  and use (session['user_id'], offset, limit)
        
        history_records = fabric_service.execute_query(history_query, (offset, limit))
        
        # Get total count
        count_query = "SELECT COUNT(*) as total FROM excel_templates"
        total_result = fabric_service.execute_query(count_query)
        total_count = total_result[0]['total'] if total_result else 0
        
        # Format records for configuration history display
        formatted_history = []
        for record in history_records:
            try:
                # Parse template config JSON
                template_config = {}
                if record['template_config']:
                    try:
                        template_config = json.loads(record['template_config'])
                    except json.JSONDecodeError:
                        template_config = {}
                
                # Get additional details from template_columns if needed
                columns_query = """
                SELECT 
                    tc.column_name,
                    COUNT(cvr.rule_type_id) as rule_count
                FROM template_columns tc
                LEFT JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
                WHERE tc.template_id = ?
                GROUP BY tc.column_name
                """
                
                try:
                    column_details = fabric_service.execute_query(columns_query, (record['template_id'],))
                    
                    # Build configuration summary
                    column_summaries = []
                    total_rules = 0
                    for col in column_details:
                        if col['rule_count'] > 0:
                            column_summaries.append(f"{col['column_name']} ({col['rule_count']} rules)")
                            total_rules += col['rule_count']
                    
                    configuration_summary = "; ".join(column_summaries[:5])  # Limit to 5 columns
                    if len(column_summaries) > 5:
                        configuration_summary += f" ... (+{len(column_summaries) - 5} more)"
                    
                    headers = [col['column_name'] for col in column_details]
                    
                except Exception as col_error:
                    logger.warning(f"Error getting column details for template {record['template_id']}: {col_error}")
                    configuration_summary = record['description'] or 'Template configured'
                    total_rules = 0
                    headers = []
                
                # Format for history display
                formatted_record = {
                    'history_id': record['template_id'],  # Use template_id as history_id
                    'template_id': record['template_id'],
                    'file_name': record['template_name'],  # Template name as file name
                    'sheet_name': template_config.get('sheet_name', 'Sheet1'),
                    'headers': headers,
                    'total_rules': total_rules,
                    'configured_columns': record['configured_columns_count'] or 0,
                    'configuration_summary': configuration_summary,
                    'file_size_mb': template_config.get('file_size_mb', 0),
                    'total_rows': template_config.get('total_rows', 0),
                    'status': 'CONFIGURED',
                    'configured_date': record['created_date'].strftime('%Y-%m-%d %H:%M') if record['created_date'] else '',
                    'last_updated': record['created_date'].strftime('%Y-%m-%d %H:%M') if record['created_date'] else '',
                    'can_revalidate': total_rules > 0,
                    'can_reconfigure': True,
                    'template_exists': True,
                    'description': record['description'] or ''
                }
                
                formatted_history.append(formatted_record)
                
            except Exception as parse_error:
                logger.warning(f"Error parsing template record {record['template_id']}: {parse_error}")
                # Add basic record even if parsing fails
                formatted_record = {
                    'history_id': record['template_id'],
                    'template_id': record['template_id'],
                    'file_name': record['template_name'],
                    'sheet_name': 'Sheet1',
                    'headers': [],
                    'total_rules': 0,
                    'configured_columns': 0,
                    'configuration_summary': record['description'] or 'Configuration error',
                    'status': 'ERROR',
                    'configured_date': record['created_date'].strftime('%Y-%m-%d %H:%M') if record['created_date'] else '',
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
    """Delete template configuration (delete from excel_templates)"""
    try:
        # Check authentication
        auth_check = check_login()
        if auth_check:
            return auth_check
        
        # Check if template exists
        # If you have user_id in excel_templates, add user ownership check
        template_query = "SELECT id, name FROM excel_templates WHERE id = ?"
        template_result = fabric_service.execute_query(template_query, (template_id,))
        
        if not template_result:
            return jsonify({
                'success': False, 
                'message': 'Template configuration not found'
            }), 404
        
        template_name = template_result[0]['name']
        
        # Delete related records first (if needed)
        try:
            # Delete column validation rules
            fabric_service.execute_non_query("""
                DELETE cvr FROM column_validation_rules cvr
                INNER JOIN template_columns tc ON cvr.column_id = tc.column_id
                WHERE tc.template_id = ?
            """, (template_id,))
            
            # Delete template columns
            fabric_service.execute_non_query("DELETE FROM template_columns WHERE template_id = ?", (template_id,))
            
            # Delete template
            fabric_service.execute_non_query("DELETE FROM excel_templates WHERE id = ?", (template_id,))
            
        except Exception as delete_error:
            logger.error(f"Error during cascade delete for template {template_id}: {delete_error}")
            # Try simple delete if cascade fails
            fabric_service.execute_non_query("DELETE FROM excel_templates WHERE id = ?", (template_id,))
        
        logger.info(f"Deleted template configuration {template_id}: {template_name}")
        
        return jsonify({
            'success': True, 
            'message': f'Template "{template_name}" deleted successfully',
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
        
        # Get template details
        template_query = """
        SELECT 
            id,
            name,
            description,
            created_date,
            template_config
        FROM excel_templates
        WHERE id = ?
        """
        
        template_result = fabric_service.execute_query(template_query, (template_id,))
        
        if not template_result:
            return jsonify({
                'success': False, 
                'message': 'Template configuration not found'
            }), 404
        
        template = template_result[0]
        
        # Parse template config
        try:
            template_config = json.loads(template['template_config']) if template['template_config'] else {}
        except json.JSONDecodeError:
            template_config = {}
        
        # Get column details with rules
        columns_query = """
        SELECT 
            tc.column_id,
            tc.column_name,
            tc.data_type,
            tc.is_required,
            tc.column_order,
            STRING_AGG(vrt.name, ', ') as validation_rules
        FROM template_columns tc
        LEFT JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
        LEFT JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.id
        WHERE tc.template_id = ?
        GROUP BY tc.column_id, tc.column_name, tc.data_type, tc.is_required, tc.column_order
        ORDER BY tc.column_order
        """
        
        columns = fabric_service.execute_query(columns_query, (template_id,))
        
        # Format detailed response
        detailed_config = {
            'template_id': template['id'],
            'template_name': template['name'],
            'description': template['description'],
            'created_date': template['created_date'].strftime('%Y-%m-%d %H:%M:%S') if template['created_date'] else '',
            'file_info': {
                'sheet_name': template_config.get('sheet_name', 'Sheet1'),
                'file_size_mb': template_config.get('file_size_mb', 0),
                'total_rows': template_config.get('total_rows', 0),
                'original_filename': template_config.get('original_filename', template['name'])
            },
            'columns': [
                {
                    'column_id': col['column_id'],
                    'column_name': col['column_name'],
                    'data_type': col['data_type'],
                    'is_required': bool(col['is_required']),
                    'column_order': col['column_order'],
                    'validation_rules': col['validation_rules'].split(', ') if col['validation_rules'] else []
                }
                for col in columns
            ],
            'statistics': {
                'total_columns': len(columns),
                'configured_columns': len([col for col in columns if col['validation_rules']]),
                'total_rules': sum(len(col['validation_rules'].split(', ')) if col['validation_rules'] else 0 for col in columns)
            },
            'template_config': template_config
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

# Stats endpoint using excel_templates
@config_history_bp.route('/stats', methods=['GET'])
@monitor_api_performance("get_template_stats")
def get_template_configuration_stats():
    """Get template configuration statistics"""
    try:
        # Check authentication
        auth_check = check_login()
        if auth_check:
            return auth_check
        
        # Get template statistics
        stats_query = """
        SELECT 
            COUNT(*) as total_templates,
            MAX(created_date) as last_template_date,
            AVG(CAST((SELECT COUNT(*) FROM template_columns tc WHERE tc.template_id = et.id) AS FLOAT)) as avg_columns_per_template
        FROM excel_templates et
        """
        
        # If you have user_id, add: WHERE user_id = ? and use (session['user_id'],)
        stats_result = fabric_service.execute_query(stats_query)
        
        if not stats_result:
            stats = {
                'total_templates': 0,
                'last_template_date': None,
                'avg_columns_per_template': 0
            }
        else:
            stats = stats_result[0]
        
        # Get total rules count
        rules_query = """
        SELECT COUNT(*) as total_rules
        FROM column_validation_rules cvr
        INNER JOIN template_columns tc ON cvr.column_id = tc.column_id
        INNER JOIN excel_templates et ON tc.template_id = et.id
        """
        
        rules_result = fabric_service.execute_query(rules_query)
        total_rules = rules_result[0]['total_rules'] if rules_result else 0
        
        # Format response
        formatted_stats = {
            'total_configurations': stats['total_templates'] or 0,
            'total_rules_created': total_rules or 0,
            'avg_columns_configured': round(float(stats['avg_columns_per_template'] or 0), 1),
            'last_configuration': stats['last_template_date'].strftime('%Y-%m-%d %H:%M') if stats['last_template_date'] else 'Never',
            'templates_ready': stats['total_templates'] or 0
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

# Helper function for saving template configurations (if needed elsewhere)
def save_configuration_history(template_name, template_description, template_config):
    """
    Save template configuration (wrapper around existing template save)
    This maintains compatibility with any existing code that expects this function
    """
    try:
        template_data = {
            'name': template_name,
            'description': template_description,
            'config': template_config
        }
        
        return fabric_service.save_template(template_data)
        
    except Exception as e:
        logger.error(f"Error saving template configuration: {e}")
        return None
