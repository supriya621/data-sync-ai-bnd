"""
File management routes - upload, download, processing
"""

import os
import time
import json
import logging
from flask import Blueprint, request, jsonify, session, send_file, current_app
from werkzeug.utils import secure_filename
from middleware.auth import login_required
from middleware.error_handlers import ValidationError, FileProcessingError
from services.fabric_service import fabric_service
from services.duckdb_service import duckdb_service
from utils.file_utils import (
    is_allowed_file, is_large_file, read_file_optimized,
    find_header_row, get_file_info
)
from utils.session_utils import get_session_id

logger = logging.getLogger(__name__)

# Create blueprint
file_bp = Blueprint('files', __name__)

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv', 'txt', 'dat'}
MAX_FILENAME_LENGTH = 255

@file_bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """File upload endpoint with large file optimization"""
    try:
        # Check if file is provided
        if 'file' not in request.files:
            raise ValidationError('No file provided')
        
        file = request.files['file']
        if file.filename == '':
            raise ValidationError('No file selected')
        
        # Validate file
        if not is_allowed_file(file.filename):
            raise ValidationError(f'File type not allowed. Supported: {", ".join(ALLOWED_EXTENSIONS)}')
        
        # Secure filename
        filename = secure_filename(file.filename)
        if len(filename) > MAX_FILENAME_LENGTH:
            raise ValidationError('Filename too long')
        
        # Save file
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        start_time = time.time()
        
        try:
            file.save(file_path)
            logger.info(f"File saved: {filename}")
        except Exception as e:
            raise FileProcessingError(f'Failed to save file: {str(e)}', filename)
        
        # Process file with optimization
        try:
            sheets, is_large_file_processing = read_file_optimized(file_path)
            processing_time = int((time.time() - start_time) * 1000)
            
            logger.info(f"File processed in {processing_time}ms using {'DuckDB' if is_large_file_processing else 'traditional'} method")
            
        except Exception as e:
            # Clean up saved file on processing error
            try:
                os.remove(file_path)
            except:
                pass
            raise FileProcessingError(f'Failed to process file: {str(e)}', filename)
        
        # Extract sheet information
        sheet_names = list(sheets.keys())
        if not sheet_names:
            raise FileProcessingError('No sheets found in the file', filename)
        
        sheet_name = sheet_names[0]
        
        # Get headers based on processing method
        if is_large_file_processing:
            headers = sheets[sheet_name]['headers']
            header_row = sheets[sheet_name]['header_row']
        else:
            df = sheets[sheet_name]
            header_row = find_header_row(df)
            if header_row == -1:
                raise FileProcessingError('Could not detect header row', filename)
            headers = df.iloc[header_row].tolist()
        
        # Check for existing template
        template_id, has_existing_rules = check_existing_template(filename, headers, sheet_name)
        
        # Create new template if needed
        if template_id is None:
            template_id = create_new_template(filename, headers, sheet_name)
        
        # Store session data
        session_data = {
            'file_path': file_path,
            'template_id': template_id,
            'header_row': header_row,
            'headers': headers,
            'sheet_name': sheet_name,
            'current_step': 3 if has_existing_rules else 1,
            'has_existing_rules': has_existing_rules,
            'is_large_file': is_large_file_processing,
            'processing_time': processing_time
        }
        
        for key, value in session_data.items():
            session[key] = value
        
        # Store DataFrame for traditional processing
        if not is_large_file_processing and 'df' not in session:
            df = sheets[sheet_name]
            df.columns = headers
            df = df.iloc[header_row + 1:].reset_index(drop=True)
            session['df'] = df.to_json()
        
        # Get file statistics
        file_info = get_file_info(file_path)
        
        response_data = {
            'success': True,
            'sheets': {sheet_name: {'headers': headers}},
            'file_name': filename,
            'template_id': template_id,
            'has_existing_rules': has_existing_rules,
            'sheet_name': sheet_name,
            'skip_to_step_3': has_existing_rules,
            'processing_method': 'DuckDB' if is_large_file_processing else 'Pandas',
            'processing_time_ms': processing_time,
            'file_info': file_info
        }
        
        logger.info(f"Upload successful: {filename} (Template ID: {template_id})")
        return jsonify(response_data), 200
        
    except ValidationError as e:
        return jsonify({'success': False, 'error': e.message}), 400
    except FileProcessingError as e:
        logger.error(f"File processing error: {e.message} - {e.filename}")
        return jsonify({'success': False, 'error': e.message}), 400
    except Exception as e:
        logger.error(f"Unexpected error during upload: {e}")
        return jsonify({'success': False, 'error': 'Upload failed'}), 500

@file_bp.route('/download/<path:filename>')
@login_required
def download_file(filename):
    """Download file endpoint"""
    try:
        # Security: ensure filename is safe
        clean_filename = secure_filename(filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], clean_filename)
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Verify user has access to this file (basic security check)
        # You might want to implement more sophisticated access control
        
        try:
            # Ensure download filename has _corrected suffix if appropriate
            base_name, ext = os.path.splitext(clean_filename)
            if not base_name.endswith('_corrected'):
                download_name = f"{base_name}_corrected{ext}"
            else:
                download_name = clean_filename
            
            logger.info(f"File download: {clean_filename} as {download_name}")
            return send_file(file_path, as_attachment=True, download_name=download_name)
            
        except Exception as e:
            logger.error(f"Error sending file {file_path}: {e}")
            return jsonify({'success': False, 'error': 'Download failed'}), 500
            
    except Exception as e:
        logger.error(f"Error in download endpoint: {e}")
        return jsonify({'success': False, 'error': 'Download failed'}), 500

@file_bp.route('/info/<int:template_id>')
@login_required
def get_file_info(template_id):
    """Get file information for a template"""
    try:
        # Get template information
        templates = fabric_service.execute_query("""
            SELECT template_name, sheet_name, headers, created_at, updated_at
            FROM excel_templates
            WHERE template_id = ? AND user_id = ? AND status = 'ACTIVE'
        """, (template_id, session['user_id']))
        
        if not templates:
            return jsonify({'success': False, 'error': 'Template not found'}), 404
        
        template = templates[0]
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], template['template_name'])
        
        # Get file system info
        file_info = get_file_info(file_path) if os.path.exists(file_path) else None
        
        # Get validation rules count
        rules_count = fabric_service.execute_query("""
            SELECT COUNT(*) as count
            FROM template_columns tc
            JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            WHERE tc.template_id = ? AND tc.is_selected = 1
        """, (template_id,))
        
        response_data = {
            'success': True,
            'template': {
                'id': template_id,
                'name': template['template_name'],
                'sheet_name': template['sheet_name'],
                'headers': json.loads(template['headers']) if template['headers'] else [],
                'created_at': template['created_at'].isoformat() if template['created_at'] else None,
                'updated_at': template['updated_at'].isoformat() if template['updated_at'] else None,
                'rules_count': rules_count[0]['count'] if rules_count else 0
            },
            'file_info': file_info
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error getting file info for template {template_id}: {e}")
        return jsonify({'success': False, 'error': 'Failed to get file information'}), 500

def check_existing_template(filename, headers, sheet_name):
    """Check if template already exists with same structure"""
    try:
        templates = fabric_service.execute_query("""
            SELECT template_id, headers, sheet_name
            FROM excel_templates
            WHERE template_name = ? AND user_id = ? AND status = 'ACTIVE'
            ORDER BY created_at DESC
        """, (filename, session['user_id']))
        
        # Find matching template
        for template in templates:
            stored_headers = json.loads(template['headers']) if template['headers'] else []
            if stored_headers == headers and template['sheet_name'] == sheet_name:
                template_id = template['template_id']
                
                # Check for existing rules
                rules = fabric_service.execute_query("""
                    SELECT COUNT(*) as count
                    FROM template_columns tc
                    JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
                    WHERE tc.template_id = ? AND tc.is_selected = 1
                """, (template_id,))
                
                has_rules = rules[0]['count'] > 0 if rules else False
                return template_id, has_rules
        
        return None, False
        
    except Exception as e:
        logger.error(f"Error checking existing template: {e}")
        return None, False

def create_new_template(filename, headers, sheet_name):
    """Create new template in database"""
    try:
        # Insert template
        template_id = fabric_service.execute_non_query("""
            INSERT INTO excel_templates (template_name, user_id, sheet_name, headers, is_corrected)
            OUTPUT INSERTED.template_id
            VALUES (?, ?, ?, ?, 0)
        """, (filename, session['user_id'], sheet_name, json.dumps(headers)))
        
        # Get the inserted template_id
        result = fabric_service.execute_query("SELECT SCOPE_IDENTITY() as id")
        template_id = result[0]['id'] if result else None
        
        if not template_id:
            raise Exception("Failed to get template ID after insertion")
        
        # Create template columns
        for i, header in enumerate(headers):
            fabric_service.execute_non_query("""
                INSERT INTO template_columns (template_id, column_name, column_position, is_selected)
                VALUES (?, ?, ?, 0)
            """, (template_id, header, i + 1))
        
        logger.info(f"Created new template: {filename} (ID: {template_id})")
        return template_id
        
    except Exception as e:
        logger.error(f"Error creating new template: {e}")
        raise FileProcessingError(f"Failed to create template: {str(e)}")
