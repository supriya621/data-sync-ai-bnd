"""
Data Sync AI - Pure SQL Fabric Application
All data storage and processing in Microsoft Fabric SQL Server
"""

import os
import sys
import logging
from flask import Flask, request, jsonify, session, send_file
from flask_session import Session
from flask_cors import CORS
from dotenv import load_dotenv
import bcrypt
import json
import pandas as pd
from datetime import datetime
import uuid
import time
import tempfile

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# Load environment variables
load_dotenv()

# Import configuration and services
from backend.config.config import config
from backend.services.fabric_service import fabric_service

# Initialize Flask app
app = Flask(__name__, static_folder='../data-sync-ai-fnd/dist', static_url_path='')
app.secret_key = config.SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = config.SESSION_FILE_DIR
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = config.MAX_FILE_SIZE_MB * 1024 * 1024

# Initialize extensions
Session(app)
CORS(app, supports_credentials=True, origins=config.ALLOWED_ORIGINS)

# Ensure directories exist
os.makedirs(config.SESSION_FILE_DIR, exist_ok=True)
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

# Setup logging
config.setup_logging()
logger = logging.getLogger(__name__)

# Comprehensive Generic validation rules
GENERIC_RULES = {
    'Required': {
        'name': 'Required',
        'description': 'Ensures the field is not null',
        'parameters': '{"allow_null": false}'
    },
    'Int': {
        'name': 'Int',
        'description': 'Validates integer format',
        'parameters': '{"format": "integer"}'
    },
    'Float': {
        'name': 'Float',
        'description': 'Validates number format (integer or decimal)',
        'parameters': '{"format": "float"}'
    },
    'Text': {
        'name': 'Text',
        'description': 'Allows text with quotes and parentheses',
        'parameters': '{"allow_special": false}'
    },
    'Email': {
        'name': 'Email',
        'description': 'Validates email format',
        'parameters': '{"regex": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\\\.[a-zA-Z0-9-.]+$"}'
    },
    'Date': {
        'name': 'Date',
        'description': 'Validates date format',
        'parameters': '{"format": "%d-%m-%Y"}'
    },
    'Boolean': {
        'name': 'Boolean',
        'description': 'Validates boolean format (true/false or 0/1)',
        'parameters': '{"format": "boolean"}'
    },
    'Alphanumeric': {
        'name': 'Alphanumeric',
        'description': 'Validates alphanumeric format',
        'parameters': '{"format": "alphanumeric"}'
    }
}

# Authentication decorators
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def admin_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
        
        # Get user from SQL Fabric
        user = fabric_service.get_user_by_email(session.get('user_email', ''))
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 403
            
        # Check if user has admin role (first user is admin)
        if user['id'] != 1:
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# Helper functions
def get_session_id():
    """Generate or get session ID for SQL Fabric operations"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

# Initialize database and create default admin user
def init_application():
    """Initialize SQL Fabric database and create default admin user"""
    try:
        # Initialize Fabric SQL database
        fabric_service.init_database()
        logger.info("SQL Fabric database initialized successfully")
        
        # Create default admin user if not exists
        admin_user = fabric_service.get_user_by_email('admin@example.com')
        if not admin_user:
            admin_data = {
                'first_name': 'Admin',
                'last_name': 'User', 
                'email': 'admin@example.com',
                'mobile': '1234567890',
                'password': bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
                'is_approved': True
            }
            fabric_service.create_user(admin_data)
            logger.info("Default admin user created in SQL Fabric")
        
        # Create default validation rules in SQL Fabric
        fabric_service.create_default_rules()
        logger.info("Application initialized with SQL Fabric database")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise

# Authentication Routes
@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    """Check current authentication status"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Not authenticated'}), 401
        
        user = fabric_service.get_user_by_email(session.get('user_email', ''))  
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 401
            
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'first_name': user['first_name'],
                'last_name': user['last_name'],
                'role': 'admin' if user['id'] == 1 else 'user'
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking authentication: {e}")
        return jsonify({'success': False, 'message': 'Authentication check failed'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json() if request.is_json else request.form
        email = data.get('username') or data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required'}), 400
        
        logger.info(f"Login attempt for: {email}")
        
        # Get user from SQL Fabric
        user = fabric_service.get_user_by_email(email.lower())
        
        if not user:
            logger.warning(f"Login failed - user not found: {email}")
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        # Verify password
        if not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            logger.warning(f"Login failed - invalid password: {email}")
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        # Check if user is approved (except for admin)
        if user['id'] != 1 and not user.get('is_approved', False):
            return jsonify({'success': False, 'message': 'Account pending approval'}), 403
        
        # Create session
        session['user_id'] = user['id']
        session['user_email'] = user['email']
        
        logger.info(f"Login successful: {email}")
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'email': user['email'],
                'first_name': user['first_name'],
                'last_name': user['last_name'],
                'role': 'admin' if user['id'] == 1 else 'user'
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'Login failed'}), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration endpoint"""
    try:
        data = request.get_json() if request.is_json else request.form
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'email', 'mobile', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field.title()} is required'}), 400
        
        email = data['email'].lower().strip()
        
        # Check if user already exists in SQL Fabric
        existing_user = fabric_service.get_user_by_email(email)
        if existing_user:
            return jsonify({'success': False, 'message': 'User already exists'}), 409
        
        # Hash password
        password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Create user data
        user_data = {
            'first_name': data['first_name'].strip(),
            'last_name': data['last_name'].strip(),
            'email': email,
            'mobile': data['mobile'].strip(),
            'password': password_hash,
            'is_approved': False
        }
        
        # Create user in SQL Fabric
        new_user_id = fabric_service.create_user(user_data)
        
        logger.info(f"User registered successfully in SQL Fabric: {email}")
        return jsonify({
            'success': True,
            'message': 'Registration successful. Please wait for admin approval.',
            'user_id': new_user_id
        }), 201
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'success': False, 'message': 'Registration failed'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """User logout endpoint"""
    try:
        session.clear()
        return jsonify({'success': True, 'message': 'Logout successful'}), 200
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({'success': False, 'message': 'Logout failed'}), 500

# Admin Routes
@app.route('/api/admin/users', methods=['GET'])
@admin_required
def get_users():
    """Get all users from SQL Fabric (admin only)"""
    try:
        users = fabric_service.execute_query("""
            SELECT id, first_name, last_name, email, mobile, is_approved, created_at
            FROM login_details
            WHERE id > 1
            ORDER BY created_at DESC
        """)
        return jsonify({'success': True, 'users': users}), 200
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({'success': False, 'message': 'Failed to get users'}), 500

@app.route('/api/admin/users/<int:user_id>/approve', methods=['POST'])
@admin_required  
def approve_user_endpoint(user_id):
    """Approve user in SQL Fabric (admin only)"""
    try:
        fabric_service.execute_non_query("""
            UPDATE login_details SET is_approved = 1 WHERE id = ?
        """, (user_id,))
        
        return jsonify({'success': True, 'message': 'User approved successfully'}), 200
    except Exception as e:
        logger.error(f"Error approving user: {e}")
        return jsonify({'success': False, 'message': 'Failed to approve user'}), 500

@app.route('/api/admin/users/<int:user_id>/reject', methods=['POST'])
@admin_required
def reject_user_endpoint(user_id):
    """Reject user in SQL Fabric (admin only)"""
    try:
        fabric_service.execute_non_query("""
            UPDATE login_details SET is_approved = 0 WHERE id = ?
        """, (user_id,))
        
        return jsonify({'success': True, 'message': 'User rejected successfully'}), 200
    except Exception as e:
        logger.error(f"Error rejecting user: {e}")
        return jsonify({'success': False, 'message': 'Failed to reject user'}), 500

# File Upload Route - SQL Fabric Only
@app.route('/api/files/upload', methods=['POST'])
@login_required
def upload_file():
    """Upload file for SQL Fabric processing - ALL data stored in SQL Server"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        # Save file temporarily
        filename = f"{session['user_id']}_{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Read file to get info and load into SQL Fabric
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        elif filepath.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(filepath)
        else:
            return jsonify({'success': False, 'message': 'Unsupported file format'}), 400
        
        # Create template in SQL Fabric
        template_data = {
            'template_name': filename,
            'user_id': session['user_id'],
            'sheet_name': 'Sheet1',
            'headers': json.dumps(df.columns.tolist()),
            'status': 'ACTIVE'
        }
        
        template_id = fabric_service.create_template(template_data)
        
        # Store file data in SQL Fabric using bulk insert
        session_id = get_session_id()
        fabric_service.bulk_insert_file_data(df, session_id, template_id)
        
        # Store in session
        session['current_file'] = {
            'filename': filename,
            'filepath': filepath,
            'headers': df.columns.tolist(),
            'row_count': len(df),
            'preview': df.head(5).to_dict('records'),
            'template_id': template_id,
            'processing_engine': 'SQL Fabric'
        }
        
        session['current_template_id'] = template_id
        
        logger.info(f"File loaded into SQL Fabric: {len(df)} rows")
        
        return jsonify({
            'success': True,
            'file_info': session['current_file'],
            'message': f'File loaded successfully using SQL Fabric ({len(df)} rows)'
        }), 200
        
    except Exception as e:
        logger.error(f"File upload error: {e}")
        return jsonify({'success': False, 'message': 'File upload failed'}), 500

# Validation Configuration Routes
@app.route('/api/validation/configure-headers', methods=['POST'])
@login_required
def configure_headers():
    """Configure headers for validation in SQL Fabric"""
    try:
        data = request.get_json()
        selected_headers = data.get('selected_headers', [])
        
        if not session.get('current_file'):
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        template_id = session['current_template_id']
        
        # Store column configuration in SQL Fabric
        fabric_service.execute_non_query("""
            DELETE FROM template_columns WHERE template_id = ?
        """, (template_id,))
        
        for i, header in enumerate(selected_headers):
            try:
                fabric_service.execute_non_query("""
                    INSERT INTO template_columns (template_id, column_name, column_position, is_selected)
                    VALUES (?, ?, ?, 1)
                """, (template_id, header, i))
            except Exception as e:
                logger.warning(f"Error inserting column {header}: {e}")
        
        session['selected_headers'] = selected_headers
        
        return jsonify({
            'success': True,
            'message': 'Headers configured successfully in SQL Fabric',
            'selected_headers': selected_headers,
            'available_rules': list(GENERIC_RULES.keys())
        }), 200
        
    except Exception as e:
        logger.error(f"Configure headers error: {e}")
        return jsonify({'success': False, 'message': 'Header configuration failed'}), 500

@app.route('/api/validation/configure-rules', methods=['POST'])
@login_required
def configure_rules():
    """Configure validation rules in SQL Fabric"""
    try:
        data = request.get_json()
        rules_config = data.get('rules_config', {})
        
        if not session.get('selected_headers'):
            return jsonify({'success': False, 'message': 'Headers not configured'}), 400
        
        session['rules_config'] = rules_config
        
        return jsonify({
            'success': True,
            'message': 'Rules configured successfully in SQL Fabric',
            'rules_config': rules_config
        }), 200
        
    except Exception as e:
        logger.error(f"Configure rules error: {e}")
        return jsonify({'success': False, 'message': 'Rule configuration failed'}), 500

@app.route('/api/validation/validate', methods=['POST'])
@login_required
def validate_data():
    """Validate data using SQL Fabric processing"""
    try:
        if not session.get('current_file') or not session.get('selected_headers'):
            return jsonify({'success': False, 'message': 'Configuration incomplete'}), 400
        
        current_file = session['current_file']
        template_id = session['current_template_id']
        session_id = get_session_id()
        
        # Get validation rules from request or session - handle both JSON and form data
        try:
            data = request.get_json() if request.is_json else {}
            rules_config = data.get('rules_config', session.get('rules_config', {}))
        except Exception:
            # If JSON parsing fails, use rules from session
            rules_config = session.get('rules_config', {})
        
        start_time = time.time()
        
        # Process validation in SQL Fabric
        logger.info(f"Starting SQL Fabric validation for {current_file['row_count']} rows...")
        validation_result = fabric_service.validate_data_in_sql_fabric(session_id, template_id, rules_config)
        
        # Get sample data for display
        sample_data = fabric_service.get_file_data(session_id, template_id, session['selected_headers'])[:100]
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Save validation history to SQL Fabric
        history_data = {
            'template_id': template_id,
            'template_name': current_file['filename'],
            'error_count': validation_result['total_errors'],
            'user_id': session['user_id'],
            'processing_time_ms': processing_time,
            'file_size_mb': round(current_file['row_count'] * len(session['selected_headers']) / 1000000, 2)
        }
        
        fabric_service.store_validation_history(history_data)
        
        session['validation_errors'] = validation_result['error_cell_locations']
        
        logger.info(f"SQL Fabric validation completed: {validation_result['total_errors']} errors found")
        
        return jsonify({
            'success': True,
            'errors': convert_errors_to_list(validation_result['error_cell_locations']),
            'total_errors': validation_result['total_errors'],
            'data': sample_data,
            'processing_time_ms': processing_time,
            'processing_method': 'SQL Fabric',
            'file_rows': current_file['row_count']
        }), 200
        
    except Exception as e:
        logger.error(f"SQL Fabric validation error: {e}")
        return jsonify({'success': False, 'message': f'Validation failed: {str(e)}'}), 500

def convert_errors_to_list(error_dict):
    """Convert error dictionary to list format for frontend"""
    errors_list = []
    for column_name, column_errors in error_dict.items():
        for error in column_errors:
            errors_list.append({
                'row': error['row'],
                'column': column_name,
                'value': error['value'],
                'rule_failed': error['rule_failed'],
                'description': error.get('reason', GENERIC_RULES.get(error['rule_failed'], {}).get('description', ''))
            })
    return errors_list

@app.route('/api/files/download-corrected', methods=['GET'])
@login_required
def download_corrected():
    """Download corrected file - processed by SQL Fabric"""
    try:
        current_file = session.get('current_file')
        if not current_file:
            return jsonify({'success': False, 'message': 'No file data available'}), 400
        
        session_id = get_session_id()
        template_id = session['current_template_id']
        headers = session.get('selected_headers', [])
        
        # Get corrected data from SQL Fabric
        corrected_data = fabric_service.export_corrected_data(session_id, template_id, headers)
        
        if corrected_data.empty:
            return jsonify({'success': False, 'message': 'No corrected data available'}), 400
        
        original_filename = current_file['filename']
        
        # Generate corrected filename
        base_name, ext = os.path.splitext(original_filename)
        corrected_filename = f"{base_name}_corrected_sql_fabric{ext}"
        corrected_filepath = os.path.join(app.config['UPLOAD_FOLDER'], corrected_filename)
        
        # Save corrected file
        if ext.lower() == '.csv':
            corrected_data.to_csv(corrected_filepath, index=False)
        else:
            corrected_data.to_excel(corrected_filepath, index=False)
        
        logger.info(f"Generated corrected file using SQL Fabric data: {corrected_filename}")
        
        return send_file(corrected_filepath, as_attachment=True, download_name=corrected_filename)
        
    except Exception as e:
        logger.error(f"SQL Fabric download error: {e}")
        return jsonify({'success': False, 'message': f'Download failed: {str(e)}'}), 500

# Available rules endpoint
@app.route('/api/validation/rules', methods=['GET'])
@login_required
def get_available_rules():
    """Get available generic rules from SQL Fabric"""
    try:
        rules = fabric_service.get_validation_rules()
        rules_info = {}
        for rule in rules:
            rules_info[rule['rule_name']] = {
                'name': rule['rule_name'],
                'description': rule['description']
            }
        
        return jsonify({
            'success': True,
            'rules': rules_info,
            'processing_engine': 'SQL Fabric'
        }), 200
    except Exception as e:
        logger.error(f"Error getting validation rules: {e}")
        return jsonify({'success': False, 'message': 'Failed to get validation rules'}), 500

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check with SQL Fabric database status"""
    try:
        # Test SQL Fabric connection
        fabric_status = fabric_service.test_connection()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'sql_fabric': fabric_status
            },
            'processing_engine': 'SQL Fabric (All data)',
            'database': 'Microsoft Fabric SQL Server'
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# Static file serving (for frontend)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_static(path):
    """Serve static files from frontend build"""
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return app.send_static_file(path)
    return app.send_static_file('index.html')

if __name__ == '__main__':
    try:
        # Validate configuration
        config.validate_config()
        
        # Initialize application with SQL Fabric only
        init_application()
        
        logger.info("Starting Data Sync AI with SQL Fabric as PRIMARY database...")
        logger.info("ALL data (users, files, processing, results) stored in SQL Fabric")
        logger.info(f"Environment: {config.FLASK_ENV}")
        logger.info(f"SQL Fabric Server: {config.FABRIC_SERVER}")
        logger.info(f"SQL Fabric Database: {config.FABRIC_DATABASE}")
        
        port = int(os.environ.get('PORT', config.PORT))
        app.run(debug=config.DEBUG, host='0.0.0.0', port=port)
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
