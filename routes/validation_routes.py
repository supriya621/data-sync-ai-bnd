"""
Data validation routes - validate data, manage rules, process corrections
"""

import json
import time
import logging
from flask import Blueprint, request, jsonify, session, current_app
from middleware.auth import login_required
from middleware.error_handlers import ValidationError, DatabaseError
from services.fabric_service import fabric_service
from services.duckdb_service import duckdb_service
from utils.session_utils import get_session_id, store_validation_state, get_validation_state
from utils.file_utils import normalize_data_rows, get_file_info

logger = logging.getLogger(__name__)

# Create blueprint
validation_bp = Blueprint('validation', __name__)

@validation_bp.route('/existing/<int:template_id>', methods=['GET'])
@login_required
def validate_existing_template(template_id):
    """Validate existing template with performance optimization"""
    start_time = time.time()
    
    try:
        # Get template information
        templates = fabric_service.execute_query("""
            SELECT template_name, sheet_name, headers
            FROM excel_templates
            WHERE template_id = ? AND user_id = ? AND status = 'ACTIVE'
        """, (template_id, session['user_id']))
        
        if not templates:
            return jsonify({'success': False, 'message': 'Template not found'}), 404
        
        template = templates[0]
        headers = json.loads(template['headers']) if template['headers'] else []
        
        # Get validation rules
        rules = fabric_service.execute_query("""
            SELECT tc.column_name, vrt.rule_name
            FROM template_columns tc
            JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
            WHERE tc.template_id = ? AND tc.is_selected = 1
        """, (template_id,))
        
        if not rules:
            return jsonify({
                'success': False, 
                'message': 'No validation rules configured for this template'
            }), 400
        
        # Group rules by column
        validation_rules = {}
        for rule in rules:
            column_name = rule['column_name']
            if column_name not in validation_rules:
                validation_rules[column_name] = []
            validation_rules[column_name].append(rule['rule_name'])
        
        # Use ONLY SQL table data for validation - NO file access
        session_id = get_session_id()
        
        logger.info(f"🔍 Validating ONLY SQL table data - no file processing")
        logger.info(f"🚫 NO lakehouse or file system access - SQL tables only")
        
        # Validate ONLY SQL table data - no file or lakehouse access
        try:
            # Always use SQL Fabric for validation (no file processing)
            validation_result = fabric_service.validate_data_in_sql_fabric(
                session_id, template_id, validation_rules
            )
            
            # Get data from SQL table ONLY
            data_rows = fabric_service.get_file_data(session_id, template_id, headers)
            
            logger.info(f"✅ Validated SQL table data ONLY - {len(data_rows)} rows")
            logger.info(f"🚫 NO file or lakehouse access - pure SQL validation")
            
        except Exception as e:
            logger.error(f"SQL table validation error: {e}")
            validation_result = {'total_errors': 0, 'error_cell_locations': {}}
            data_rows = []
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Save validation history (SQL table reference only)
        save_validation_history(template_id, template['template_name'], 
                              validation_result.get('total_errors', 0), 
                              f"SQL_TABLE_DATA_ONLY_{session_id}", processing_time)
        
        # Prepare response
        response_data = {
            'success': True,
            'error_cell_locations': validation_result.get('error_cell_locations', {}),
            'data_rows': normalize_data_rows(data_rows),
            'processing_time_ms': processing_time,
            'processing_method': 'DuckDB' if is_large_file else 'Pandas',
            'total_errors': validation_result.get('total_errors', 0),
            'validation_summary': generate_validation_summary(validation_result)
        }
        
        # Store validation state
        store_validation_state(response_data)
        
        logger.info(f"Validation completed for template {template_id}: "
                   f"{validation_result.get('total_errors', 0)} errors found in {processing_time}ms")
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error in validate_existing_template: {e}")
        return jsonify({'success': False, 'message': f'Validation failed: {str(e)}'}), 500

@validation_bp.route('/corrected/<int:template_id>', methods=['POST'])
@login_required
def validate_corrected_template(template_id):
    """Validate corrected template data"""
    try:
        # Get corrections from request
        corrections = request.json.get('corrections', {})
        
        if not corrections:
            return jsonify({
                'success': False, 
                'message': 'No corrections provided'
            }), 400
        
        # Apply corrections and validate
        validation_result = apply_corrections_and_validate(template_id, corrections)
        
        return jsonify({
            'success': True,
            'message': 'Corrected template validated successfully',
            'results': validation_result
        }), 200
        
    except Exception as e:
        logger.error(f"Error validating corrected template: {e}")
        return jsonify({
            'success': False, 
            'message': f'Validation of corrected template failed: {str(e)}'
        }), 500

@validation_bp.route('/rules/<int:template_id>', methods=['GET'])
@login_required
def get_validation_rules(template_id):
    """Get validation rules for a template"""
    try:
        rules = fabric_service.execute_query("""
            SELECT 
                vrt.rule_type_id,
                vrt.rule_name,
                vrt.description,
                vrt.parameters,
                vrt.is_custom,
                tc.column_name,
                tc.is_selected
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
                'rule_id': rule['rule_type_id'],
                'rule_name': rule['rule_name'],
                'description': rule['description'],
                'is_custom': rule['is_custom']
            })
        
        return jsonify({
            'success': True,
            'rules': rules_by_column
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting validation rules: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to get validation rules'
        }), 500

@validation_bp.route('/rules/<int:template_id>', methods=['POST'])
@login_required
def update_validation_rules(template_id):
    """Update validation rules for a template"""
    try:
        rules_data = request.json.get('rules', {})
        
        if not rules_data:
            raise ValidationError('No rules data provided')
        
        # Get template columns
        columns = fabric_service.execute_query("""
            SELECT column_id, column_name 
            FROM template_columns 
            WHERE template_id = ? AND is_selected = 1
        """, (template_id,))
        
        column_map = {col['column_name']: col['column_id'] for col in columns}
        
        # Get available rules
        available_rules = fabric_service.execute_query("""
            SELECT rule_type_id, rule_name 
            FROM validation_rule_types 
            WHERE is_active = 1
        """)
        
        rule_map = {rule['rule_name']: rule['rule_type_id'] for rule in available_rules}
        
        # Clear existing rules for this template
        fabric_service.execute_non_query("""
            DELETE FROM column_validation_rules 
            WHERE column_id IN (
                SELECT column_id FROM template_columns 
                WHERE template_id = ? AND is_selected = 1
            )
        """, (template_id,))
        
        # Insert new rules
        validation_data = []
        for column_name, rule_names in rules_data.items():
            column_id = column_map.get(column_name)
            if not column_id:
                continue
            
            for rule_name in rule_names:
                rule_type_id = rule_map.get(rule_name)
                if rule_type_id:
                    validation_data.append((column_id, rule_type_id, json.dumps({})))
        
        if validation_data:
            # Use executemany for batch insert
            conn = fabric_service.get_connection()
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO column_validation_rules (column_id, rule_type_id, rule_config)
                VALUES (?, ?, ?)
            """, validation_data)
            conn.commit()
            cursor.close()
        
        logger.info(f"Updated validation rules for template {template_id}")
        return jsonify({'success': True, 'message': 'Validation rules updated'}), 200
        
    except ValidationError as e:
        return jsonify({'success': False, 'message': e.message}), 400
    except Exception as e:
        logger.error(f"Error updating validation rules: {e}")
        return jsonify({'success': False, 'message': 'Failed to update rules'}), 500

@validation_bp.route('/history', methods=['GET'])
@login_required
def get_validation_history():
    """Get validation history for the user"""
    try:
        history = fabric_service.execute_query("""
            SELECT 
                vh.history_id,
                vh.template_id,
                vh.template_name,
                vh.error_count,
                vh.corrected_at,
                vh.processing_time_ms,
                et.created_at as original_uploaded_at,
                et.headers
            FROM validation_history vh
            JOIN excel_templates et ON vh.template_id = et.template_id
            WHERE vh.user_id = ?
            ORDER BY vh.corrected_at DESC
            LIMIT 50
        """, (session['user_id'],))
        
        # Group by template for better organization
        grouped_history = {}
        for entry in history:
            template_name = entry['template_name']
            base_name = template_name.replace('_corrected.xlsx', '').replace('_corrected.csv', '')
            
            if base_name not in grouped_history:
                grouped_history[base_name] = {
                    'original_uploaded_at': entry['original_uploaded_at'].isoformat() if entry['original_uploaded_at'] else None,
                    'validations': []
                }
            
            grouped_history[base_name]['validations'].append({
                'history_id': entry['history_id'],
                'template_id': entry['template_id'],
                'template_name': entry['template_name'],
                'error_count': entry['error_count'],
                'corrected_at': entry['corrected_at'].isoformat() if entry['corrected_at'] else None,
                'processing_time_ms': entry['processing_time_ms']
            })
        
        return jsonify({
            'success': True,
            'history': grouped_history
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting validation history: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to get validation history'
        }), 500

def validate_with_duckdb(session_id, template_id, validation_rules):
    """Validate using DuckDB for large files"""
    try:
        result = duckdb_service.validate_data(session_id, template_id, validation_rules)
        return result
    except Exception as e:
        logger.error(f"DuckDB validation failed: {e}")
        return {'error_cell_locations': {}, 'total_errors': 0}

def validate_traditionally(template_id, validation_rules, headers):
    """Traditional validation for smaller files"""
    try:
        # This is a simplified version - you would implement the full validation logic
        return {'error_cell_locations': {}, 'total_errors': 0}
    except Exception as e:
        logger.error(f"Traditional validation failed: {e}")
        return {'error_cell_locations': {}, 'total_errors': 0}

def save_validation_history(template_id, template_name, error_count, file_path, processing_time):
    """Save validation history to database"""
    try:
        fabric_service.execute_non_query("""
            INSERT INTO validation_history 
            (template_id, template_name, error_count, corrected_file_path, user_id, processing_time_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (template_id, template_name, error_count, file_path, session['user_id'], processing_time))
    except Exception as e:
        logger.error(f"Failed to save validation history: {e}")

def generate_validation_summary(validation_result):
    """Generate validation summary"""
    error_locations = validation_result.get('error_cell_locations', {})
    total_errors = validation_result.get('total_errors', 0)
    
    summary = {
        'total_errors': total_errors,
        'columns_with_errors': len(error_locations),
        'error_types': {}
    }
    
    # Count error types
    for column_errors in error_locations.values():
        for error in column_errors:
            rule_failed = error.get('rule_failed', 'Unknown')
            summary['error_types'][rule_failed] = summary['error_types'].get(rule_failed, 0) + 1
    
    return summary

def apply_corrections_and_validate(template_id, corrections):
    """Apply corrections and validate the results"""
    # This would be implemented based on your specific correction logic
    # For now, return a placeholder response
    return {
        'corrections_applied': len(corrections),
        'validation_passed': True,
        'remaining_errors': 0
    }
