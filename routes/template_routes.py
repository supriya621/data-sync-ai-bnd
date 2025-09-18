"""
Template management routes - CRUD operations for templates
"""

import json
import os
import logging
from flask import Blueprint, request, jsonify, session, current_app
from middleware.auth import login_required
from middleware.error_handlers import ValidationError, DatabaseError
from services.fabric_service import fabric_service
from utils.file_utils import get_file_info

logger = logging.getLogger(__name__)

# Create blueprint
template_bp = Blueprint('templates', __name__)

@template_bp.route('/', methods=['GET'])
@login_required
def get_templates():
    """Get all templates for the current user"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        status = request.args.get('status', 'ACTIVE')
        
        templates = fabric_service.execute_query("""
            SELECT 
                template_id, 
                template_name, 
                created_at, 
                updated_at,
                status, 
                is_corrected,
                sheet_name,
                headers,
                validation_frequency
            FROM excel_templates
            WHERE user_id = ? AND status = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (session['user_id'], status, limit, offset))
        
        # Enrich with additional information
        enriched_templates = []
        for template in templates:
            # Get rule count
            rule_count = fabric_service.execute_query("""
                SELECT COUNT(*) as count
                FROM template_columns tc
                JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
                WHERE tc.template_id = ? AND tc.is_selected = 1
            """, (template['template_id'],))
            
            # Get file info if exists
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], template['template_name'])
            file_info = get_file_info(file_path) if os.path.exists(file_path) else None
            
            enriched_template = {
                'template_id': template['template_id'],
                'template_name': template['template_name'],
                'created_at': template['created_at'].isoformat() if template['created_at'] else None,
                'updated_at': template['updated_at'].isoformat() if template['updated_at'] else None,
                'status': template['status'],
                'is_corrected': bool(template['is_corrected']),
                'sheet_name': template['sheet_name'],
                'headers': json.loads(template['headers']) if template['headers'] else [],
                'validation_frequency': template['validation_frequency'],
                'rule_count': rule_count[0]['count'] if rule_count else 0,
                'file_info': file_info
            }
            enriched_templates.append(enriched_template)
        
        return jsonify({
            'success': True,
            'templates': enriched_templates,
            'pagination': {
                'limit': limit,
                'offset': offset,
                'count': len(enriched_templates)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to get templates'
        }), 500

@template_bp.route('/<int:template_id>', methods=['GET'])
@login_required
def get_template(template_id):
    """Get specific template details"""
    try:
        templates = fabric_service.execute_query("""
            SELECT 
                template_id,
                template_name, 
                created_at, 
                updated_at,
                status, 
                is_corrected,
                sheet_name,
                headers,
                validation_frequency,
                remote_file_path
            FROM excel_templates
            WHERE template_id = ? AND user_id = ? AND status = 'ACTIVE'
        """, (template_id, session['user_id']))
        
        if not templates:
            return jsonify({
                'success': False, 
                'message': 'Template not found'
            }), 404
        
        template = templates[0]
        
        # Get columns with rules
        columns = fabric_service.execute_query("""
            SELECT 
                tc.column_id,
                tc.column_name,
                tc.column_position,
                tc.is_selected,
                tc.is_validation_enabled,
                COUNT(cvr.column_validation_id) as rule_count
            FROM template_columns tc
            LEFT JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            WHERE tc.template_id = ?
            GROUP BY tc.column_id, tc.column_name, tc.column_position, tc.is_selected, tc.is_validation_enabled
            ORDER BY tc.column_position
        """, (template_id,))
        
        # Get validation rules details
        rules = fabric_service.execute_query("""
            SELECT 
                vrt.rule_name,
                vrt.description,
                vrt.is_custom,
                tc.column_name
            FROM validation_rule_types vrt
            JOIN column_validation_rules cvr ON vrt.rule_type_id = cvr.rule_type_id
            JOIN template_columns tc ON cvr.column_id = tc.column_id
            WHERE tc.template_id = ? AND tc.is_selected = 1
        """, (template_id,))
        
        # Group rules by column
        rules_by_column = {}
        for rule in rules:
            column_name = rule['column_name']
            if column_name not in rules_by_column:
                rules_by_column[column_name] = []
            rules_by_column[column_name].append({
                'rule_name': rule['rule_name'],
                'description': rule['description'],
                'is_custom': bool(rule['is_custom'])
            })
        
        # Get file info
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], template['template_name'])
        file_info = get_file_info(file_path) if os.path.exists(file_path) else None
        
        response_data = {
            'success': True,
            'template': {
                'template_id': template['template_id'],
                'template_name': template['template_name'],
                'created_at': template['created_at'].isoformat() if template['created_at'] else None,
                'updated_at': template['updated_at'].isoformat() if template['updated_at'] else None,
                'status': template['status'],
                'is_corrected': bool(template['is_corrected']),
                'sheet_name': template['sheet_name'],
                'headers': json.loads(template['headers']) if template['headers'] else [],
                'validation_frequency': template['validation_frequency'],
                'remote_file_path': template['remote_file_path'],
                'columns': columns,
                'rules_by_column': rules_by_column,
                'file_info': file_info
            }
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to get template details'
        }), 500

@template_bp.route('/<int:template_id>', methods=['PUT'])
@login_required
def update_template(template_id):
    """Update template metadata"""
    try:
        data = request.get_json()
        
        if not data:
            raise ValidationError('No update data provided')
        
        # Verify ownership
        templates = fabric_service.execute_query("""
            SELECT template_id FROM excel_templates
            WHERE template_id = ? AND user_id = ?
        """, (template_id, session['user_id']))
        
        if not templates:
            return jsonify({
                'success': False, 
                'message': 'Template not found'
            }), 404
        
        # Prepare update fields
        update_fields = []
        params = []
        
        if 'template_name' in data:
            update_fields.append("template_name = ?")
            params.append(data['template_name'])
        
        if 'validation_frequency' in data:
            if data['validation_frequency'] in ['WEEKLY', 'MONTHLY', 'YEARLY', None]:
                update_fields.append("validation_frequency = ?")
                params.append(data['validation_frequency'])
            else:
                raise ValidationError('Invalid validation frequency')
        
        if 'status' in data:
            if data['status'] in ['ACTIVE', 'INACTIVE']:
                update_fields.append("status = ?")
                params.append(data['status'])
            else:
                raise ValidationError('Invalid status')
        
        if not update_fields:
            raise ValidationError('No valid update fields provided')
        
        # Add updated_at and template_id to params
        update_fields.append("updated_at = GETDATE()")
        params.append(template_id)
        
        # Execute update
        query = f"UPDATE excel_templates SET {', '.join(update_fields)} WHERE template_id = ?"
        fabric_service.execute_non_query(query, tuple(params))
        
        logger.info(f"Template {template_id} updated successfully")
        return jsonify({
            'success': True, 
            'message': 'Template updated successfully'
        }), 200
        
    except ValidationError as e:
        return jsonify({'success': False, 'message': e.message}), 400
    except Exception as e:
        logger.error(f"Error updating template {template_id}: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to update template'
        }), 500

@template_bp.route('/<int:template_id>', methods=['DELETE'])
@login_required
def delete_template(template_id):
    """Delete template and associated data"""
    try:
        # Verify ownership and get template info
        templates = fabric_service.execute_query("""
            SELECT template_name FROM excel_templates
            WHERE template_id = ? AND user_id = ?
        """, (template_id, session['user_id']))
        
        if not templates:
            return jsonify({
                'success': False, 
                'message': 'Template not found'
            }), 404
        
        template_name = templates[0]['template_name']
        
        # Delete associated file if exists
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], template_name)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete file {file_path}: {e}")
        
        # Delete from database (cascading deletes will handle related records)
        fabric_service.execute_non_query("""
            DELETE FROM excel_templates
            WHERE template_id = ? AND user_id = ?
        """, (template_id, session['user_id']))
        
        logger.info(f"Template {template_id} deleted successfully")
        return jsonify({
            'success': True, 
            'message': 'Template deleted successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting template {template_id}: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to delete template'
        }), 500

@template_bp.route('/<int:template_id>/columns', methods=['POST'])
@login_required
def update_template_columns(template_id):
    """Update which columns are selected for validation"""
    try:
        data = request.get_json()
        selected_columns = data.get('selected_columns', [])
        
        if not isinstance(selected_columns, list):
            raise ValidationError('selected_columns must be a list')
        
        # Verify template ownership
        templates = fabric_service.execute_query("""
            SELECT template_id FROM excel_templates
            WHERE template_id = ? AND user_id = ?
        """, (template_id, session['user_id']))
        
        if not templates:
            return jsonify({
                'success': False, 
                'message': 'Template not found'
            }), 404
        
        # Update all columns to not selected first
        fabric_service.execute_non_query("""
            UPDATE template_columns 
            SET is_selected = 0, is_validation_enabled = 0
            WHERE template_id = ?
        """, (template_id,))
        
        # Update selected columns
        if selected_columns:
            placeholders = ', '.join(['?' for _ in selected_columns])
            query = f"""
                UPDATE template_columns 
                SET is_selected = 1, is_validation_enabled = 1
                WHERE template_id = ? AND column_name IN ({placeholders})
            """
            fabric_service.execute_non_query(query, (template_id, *selected_columns))
        
        logger.info(f"Updated column selection for template {template_id}")
        return jsonify({
            'success': True, 
            'message': 'Column selection updated'
        }), 200
        
    except ValidationError as e:
        return jsonify({'success': False, 'message': e.message}), 400
    except Exception as e:
        logger.error(f"Error updating template columns: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to update column selection'
        }), 500

@template_bp.route('/with-rules', methods=['GET'])
@login_required
def get_templates_with_rules():
    """Get templates that have validation rules configured"""
    try:
        templates = fabric_service.execute_query("""
            SELECT DISTINCT
                et.template_id,
                et.template_name,
                et.created_at,
                et.sheet_name,
                COUNT(cvr.column_validation_id) as rule_count
            FROM excel_templates et
            JOIN template_columns tc ON et.template_id = tc.template_id
            JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            WHERE et.user_id = ? AND et.status = 'ACTIVE' AND et.is_corrected = 0
            GROUP BY et.template_id, et.template_name, et.created_at, et.sheet_name
            HAVING COUNT(cvr.column_validation_id) > 0
            ORDER BY et.created_at DESC
        """, (session['user_id'],))
        
        enriched_templates = []
        for template in templates:
            enriched_templates.append({
                'template_id': template['template_id'],
                'template_name': template['template_name'],
                'created_at': template['created_at'].isoformat() if template['created_at'] else None,
                'sheet_name': template['sheet_name'],
                'rule_count': template['rule_count']
            })
        
        return jsonify({
            'success': True,
            'templates': enriched_templates
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting templates with rules: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to get templates with rules'
        }), 500
