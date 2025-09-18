"""
Data Sync AI - Simplified Application with DuckDB for ALL File Processing
Core functionality: Authentication, Admin approval, User workflow using DuckDB for all data processing
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

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# Load environment variables
load_dotenv()

# Import configuration and services
from backend.config.config import config
from backend.services.fabric_service import fabric_service
from backend.services.duckdb_service import duckdb_service

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

# Comprehensive Generic validation rules (as requested)
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
        
        # Use unified function to get user
        user = get_user_by_email(session.get('user_email', ''))
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 403
            
        # Check if user has admin role (first user is admin for simplicity)
        if user['id'] != 1:
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# Helper functions
def get_session_id():
    """Generate or get session ID for DuckDB operations"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

# Unified authentication functions that work with both SQL Fabric and DuckDB
def get_user_by_email(email):
    """Get user by email from available database"""
    global SQL_FABRIC_AVAILABLE
    
    try:
        if SQL_FABRIC_AVAILABLE:
            return fabric_service.get_user_by_email(email)
        else:
            # Use DuckDB
            conn = duckdb_service.connection
            result = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchall()
            if result:
                row = result[0]
                return {
                    'id': row[0],
                    'email': row[1], 
                    'password': row[2],
                    'first_name': row[3],
                    'last_name': row[4],
                    'mobile': row[5],
                    'is_approved': row[6],
                    'created_at': row[7]
                }
            return None
    except Exception as e:
        logger.error(f"Error getting user by email: {e}")
        return None

def create_user(user_data):
    """Create user in available database"""
    global SQL_FABRIC_AVAILABLE
    
    try:
        if SQL_FABRIC_AVAILABLE:
            return fabric_service.create_user(user_data)
        else:
            # Use DuckDB - ID will be auto-generated by sequence
            conn = duckdb_service.connection
            conn.execute("""
                INSERT INTO users (email, password, first_name, last_name, mobile, is_approved)
                VALUES (?, ?, ?, ?, ?, FALSE)
            """, (
                user_data['email'],
                user_data['password'],
                user_data['first_name'],
                user_data['last_name'],
                user_data['mobile']
            ))
            
            # Get the created user
            return get_user_by_email(user_data['email'])
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise

def get_all_users():
    """Get all users from available database"""
    global SQL_FABRIC_AVAILABLE
    
    try:
        if SQL_FABRIC_AVAILABLE:
            return fabric_service.execute_query("SELECT * FROM login_details ORDER BY created_at DESC")
        else:
            # Use DuckDB
            conn = duckdb_service.connection
            result = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
            users = []
            for row in result:
                users.append({
                    'id': row[0],
                    'email': row[1],
                    'first_name': row[3],
                    'last_name': row[4],
                    'mobile': row[5],
                    'is_approved': row[6],
                    'created_at': row[7]
                })
            return users
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        return []

def approve_user(user_id):
    """Approve user in available database"""
    global SQL_FABRIC_AVAILABLE
    
    try:
        if SQL_FABRIC_AVAILABLE:
            return fabric_service.execute_query(
                "UPDATE login_details SET is_approved = TRUE WHERE id = ?", 
                (user_id,)
            )
        else:
            # Use DuckDB
            conn = duckdb_service.connection
            conn.execute("UPDATE users SET is_approved = TRUE WHERE id = ?", (user_id,))
            return True
    except Exception as e:
        logger.error(f"Error approving user: {e}")
        return False

def reject_user(user_id):
    """Reject user in available database"""
    global SQL_FABRIC_AVAILABLE
    
    try:
        if SQL_FABRIC_AVAILABLE:
            return fabric_service.execute_query(
                "UPDATE login_details SET is_approved = FALSE WHERE id = ?", 
                (user_id,)
            )
        else:
            # Use DuckDB
            conn = duckdb_service.connection
            conn.execute("UPDATE users SET is_approved = FALSE WHERE id = ?", (user_id,))
            return True
    except Exception as e:
        logger.error(f"Error rejecting user: {e}")
        return False

# Global flag to track SQL Fabric availability
SQL_FABRIC_AVAILABLE = False

# Initialize database and rules on startup
def init_application():
    """Initialize database and create default rules with fallback support"""
    global SQL_FABRIC_AVAILABLE
    
    try:
        # Try to initialize Fabric SQL database
        fabric_service.init_database()
        SQL_FABRIC_AVAILABLE = True
        logger.info("SQL Fabric connection established successfully")
        
        # Create default admin user if not exists
        admin_user = fabric_service.get_user_by_email('admin@example.com')
        if not admin_user:
            admin_data = {
                'first_name': 'Admin',
                'last_name': 'User', 
                'email': 'admin@example.com',
                'mobile': '1234567890',
                'password': bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            }
            fabric_service.create_user(admin_data)
            logger.info("Default admin user created in SQL Fabric")
        
        # Create default validation rules in SQL Fabric
        fabric_service.create_default_rules()
        logger.info("Application initialized with SQL Fabric + DuckDB processing")
        
    except Exception as fabric_error:
        logger.warning(f"SQL Fabric connection failed: {str(fabric_error)}")
        logger.info("Falling back to DuckDB-only mode...")
        SQL_FABRIC_AVAILABLE = False
        
        try:
            # Initialize DuckDB-only mode with in-memory user management
            init_duckdb_fallback_mode()
            logger.info("Application initialized in DuckDB-only mode (fallback)")
            
        except Exception as duckdb_error:
            logger.error(f"DuckDB fallback initialization failed: {str(duckdb_error)}")
            raise Exception("Failed to initialize both SQL Fabric and DuckDB fallback modes")

def init_duckdb_fallback_mode():
    """Initialize application in DuckDB-only mode with in-memory user management"""
    # DuckDB service is already initialized when imported, just add user management tables
    conn = duckdb_service.connection
    
    # Drop existing users table if it exists to recreate with proper schema
    conn.execute("DROP TABLE IF EXISTS users")
    conn.execute("DROP SEQUENCE IF EXISTS user_id_seq")
    
    # Create user management tables in DuckDB with simpler auto-increment
    conn.execute("""
        CREATE SEQUENCE user_id_seq START 1
    """)
    
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY DEFAULT nextval('user_id_seq'),
            email VARCHAR UNIQUE,
            password VARCHAR,
            first_name VARCHAR,
            last_name VARCHAR,
            mobile VARCHAR,
            is_approved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create default admin user in DuckDB - will get ID 1 from sequence
    admin_password = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    conn.execute("""
        INSERT INTO users (email, password, first_name, last_name, mobile, is_approved)
        VALUES ('admin@example.com', ?, 'Admin', 'User', '1234567890', TRUE)
    """, (admin_password,))
    
    logger.info("Default admin user created in DuckDB with ID 1")
    logger.info("DuckDB fallback mode initialized successfully")

# Authentication Routes
@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    """Check current authentication status"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Not authenticated'}), 401
        
        user = get_user_by_email(session.get('user_email', ''))  
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
        
        # Get user from available database
        user = get_user_by_email(email.lower())
        
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
        
        # Check if user already exists
        existing_user = get_user_by_email(email)
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
            'password': password_hash
        }
        
        # Create user in available database
        new_user = create_user(user_data)
        
        logger.info(f"User registered successfully: {email}")
        return jsonify({
            'success': True,
            'message': 'Registration successful. Please wait for admin approval.',
            'user_id': new_user['id']
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
    """Get all users (admin only)"""
    try:
        users = get_all_users()
        return jsonify({'success': True, 'users': users}), 200
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({'success': False, 'message': 'Failed to get users'}), 500

@app.route('/api/admin/users/<int:user_id>/approve', methods=['POST'])
@admin_required  
def approve_user_endpoint(user_id):
    """Approve user (admin only)"""
    try:
        success = approve_user(user_id)
        if success:
            return jsonify({'success': True, 'message': 'User approved successfully'}), 200
        else:
            return jsonify({'success': False, 'message': 'Failed to approve user'}), 500
    except Exception as e:
        logger.error(f"Error approving user: {e}")
        return jsonify({'success': False, 'message': 'Failed to approve user'}), 500

@app.route('/api/admin/users/<int:user_id>/reject', methods=['POST'])
@admin_required
def reject_user_endpoint(user_id):
    """Reject user (admin only)"""
    try:
        success = reject_user(user_id)
        if success:
            return jsonify({'success': True, 'message': 'User rejected successfully'}), 200
        else:
            return jsonify({'success': False, 'message': 'Failed to reject user'}), 500
    except Exception as e:
        logger.error(f"Error rejecting user: {e}")
        return jsonify({'success': False, 'message': 'Failed to reject user'}), 500

# File Upload Route - ALWAYS uses DuckDB
@app.route('/api/files/upload', methods=['POST'])
@login_required
def upload_file():
    """Upload file for DuckDB processing - ALL files processed with DuckDB"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        # Save file
        filename = f"{session['user_id']}_{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Read file to get basic info for preview only
        if filepath.endswith('.csv'):
            df_sample = pd.read_csv(filepath, nrows=5)  # Just for preview
            total_rows = sum(1 for line in open(filepath, 'r', encoding='utf-8')) - 1
        elif filepath.endswith(('.xlsx', '.xls')):
            df_sample = pd.read_excel(filepath, nrows=5)
            df_full = pd.read_excel(filepath)
            total_rows = len(df_full)
        else:
            return jsonify({'success': False, 'message': 'Unsupported file format'}), 400
        
        # Create template in Fabric SQL
        template_result = fabric_service.execute_query("""
            INSERT INTO excel_templates (template_name, user_id, headers, sheet_name)
            OUTPUT INSERTED.template_id
            VALUES (?, ?, ?, ?)
        """, (filename, session['user_id'], json.dumps(df_sample.columns.tolist()), 'Sheet1'))
        
        template_id = template_result[0]['template_id']
        
        # Store in session
        session['current_file'] = {
            'filename': filename,
            'filepath': filepath,
            'headers': df_sample.columns.tolist(),
            'row_count': total_rows,
            'preview': df_sample.to_dict('records'),
            'template_id': template_id,
            'processing_engine': 'DuckDB'  # Always DuckDB
        }
        
        session['current_template_id'] = template_id
        
        # ALWAYS load into DuckDB for processing regardless of file size
        session_id = get_session_id()
        duckdb_result = duckdb_service.load_file_data(filepath, session_id, template_id)
        logger.info(f"File loaded into DuckDB: {total_rows} rows, processing method: DuckDB")
        
        return jsonify({
            'success': True,
            'file_info': session['current_file'],
            'message': f'File loaded successfully using DuckDB ({total_rows} rows)'
        }), 200
        
    except Exception as e:
        logger.error(f"File upload error: {e}")
        return jsonify({'success': False, 'message': 'File upload failed'}), 500

# Rule Configuration Routes (Steps 1-3)
@app.route('/api/validation/configure-headers', methods=['POST'])
@login_required
def configure_headers():
    """Step 1: Select headers for validation"""
    try:
        data = request.get_json()
        selected_headers = data.get('selected_headers', [])
        
        if not session.get('current_file'):
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        template_id = session['current_template_id']
        
        # Clear existing columns for this template
        fabric_service.execute_non_query("""
            DELETE FROM template_columns WHERE template_id = ?
        """, (template_id,))
        
        # Create template columns in Fabric SQL
        for i, header in enumerate(selected_headers):
            fabric_service.execute_non_query("""
                INSERT INTO template_columns (template_id, column_name, column_position, is_selected)
                VALUES (?, ?, ?, 1)
            """, (template_id, header, i))
        
        session['selected_headers'] = selected_headers
        
        return jsonify({
            'success': True,
            'message': 'Headers configured successfully (DuckDB ready)',
            'selected_headers': selected_headers,
            'available_rules': list(GENERIC_RULES.keys()),
            'processing_engine': 'DuckDB'
        }), 200
        
    except Exception as e:
        logger.error(f"Configure headers error: {e}")
        return jsonify({'success': False, 'message': 'Header configuration failed'}), 500

@app.route('/api/validation/configure-rules', methods=['POST'])
@login_required
def configure_rules():
    """Step 2: Configure generic rules for selected headers"""
    try:
        data = request.get_json()
        rules_config = data.get('rules_config', {})
        
        if not session.get('selected_headers'):
            return jsonify({'success': False, 'message': 'Headers not configured'}), 400
        
        template_id = session['current_template_id']
        
        # Get column IDs
        columns = fabric_service.execute_query("""
            SELECT column_id, column_name 
            FROM template_columns 
            WHERE template_id = ? AND is_selected = 1
        """, (template_id,))
        
        column_map = {col['column_name']: col['column_id'] for col in columns}
        
        # Get rule IDs from Fabric SQL
        rules = fabric_service.execute_query("""
            SELECT rule_type_id, rule_name 
            FROM validation_rule_types 
            WHERE is_active = 1 AND is_custom = 0
        """)
        
        rule_map = {rule['rule_name']: rule['rule_type_id'] for rule in rules}
        
        # Clear existing rules for this template
        fabric_service.execute_non_query("""
            DELETE FROM column_validation_rules 
            WHERE column_id IN (
                SELECT column_id FROM template_columns 
                WHERE template_id = ?
            )
        """, (template_id,))
        
        # Save column validation rules
        for column_name, rule_names in rules_config.items():
            column_id = column_map.get(column_name)
            if not column_id:
                continue
            
            for rule_name in rule_names:
                rule_type_id = rule_map.get(rule_name)
                if rule_type_id:
                    rule_config = GENERIC_RULES[rule_name]['parameters']
                    fabric_service.execute_non_query("""
                        INSERT INTO column_validation_rules (column_id, rule_type_id, rule_config)
                        VALUES (?, ?, ?)
                    """, (column_id, rule_type_id, rule_config))
        
        session['rules_config'] = rules_config
        
        return jsonify({
            'success': True,
            'message': 'Rules configured successfully (DuckDB ready for validation)',
            'rules_config': rules_config,
            'processing_engine': 'DuckDB'
        }), 200
        
    except Exception as e:
        logger.error(f"Configure rules error: {e}")
        return jsonify({'success': False, 'message': 'Rule configuration failed'}), 500

@app.route('/api/validation/review-config', methods=['GET'])
@login_required
def review_configuration():
    """Step 3: Review all configured rules"""
    try:
        if not session.get('current_file') or not session.get('rules_config'):
            return jsonify({'success': False, 'message': 'Configuration incomplete'}), 400
        
        config_summary = {
            'file_info': session['current_file'],
            'selected_headers': session.get('selected_headers', []),
            'rules_config': session.get('rules_config', {}),
            'rules_details': {rule: GENERIC_RULES[rule]['description'] for rule in GENERIC_RULES},
            'processing_engine': 'DuckDB',
            'ready_for_validation': True
        }
        
        return jsonify({
            'success': True,
            'configuration': config_summary
        }), 200
        
    except Exception as e:
        logger.error(f"Review configuration error: {e}")
        return jsonify({'success': False, 'message': 'Configuration review failed'}), 500

# Data Validation Routes (Steps 4-6) - ALL using DuckDB
@app.route('/api/validation/validate', methods=['POST'])
@login_required
def validate_data():
    """Step 4: Validate data using DuckDB for ALL files"""
    try:
        if not session.get('current_file') or not session.get('rules_config'):
            return jsonify({'success': False, 'message': 'Configuration incomplete'}), 400
        
        current_file = session['current_file']
        rules_config = session['rules_config']
        template_id = session['current_template_id']
        session_id = get_session_id()
        
        start_time = time.time()
        
        # ALWAYS use DuckDB for validation regardless of file size
        logger.info(f"Starting DuckDB validation for {current_file['row_count']} rows...")
        validation_result = duckdb_service.validate_data(session_id, template_id, rules_config)
        
        # Get sample data for display (first 100 rows for performance)
        sample_data = duckdb_service.get_data_rows(session_id, template_id, 
                                                 session['selected_headers'])[:100]
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Save validation history to Fabric SQL
        fabric_service.execute_non_query("""
            INSERT INTO validation_history 
            (template_id, template_name, error_count, corrected_file_path, user_id, processing_time_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (template_id, current_file['filename'], validation_result['total_errors'], 
              current_file['filepath'], session['user_id'], processing_time))
        
        session['validation_errors'] = validation_result['error_cell_locations']
        session['processing_method'] = 'DuckDB'  # Always DuckDB
        
        logger.info(f"DuckDB validation completed: {validation_result['total_errors']} errors found in {processing_time}ms")
        
        return jsonify({
            'success': True,
            'errors': convert_errors_to_list(validation_result['error_cell_locations']),
            'total_errors': validation_result['total_errors'],
            'data': sample_data,
            'processing_time_ms': processing_time,
            'processing_method': 'DuckDB',
            'file_rows': current_file['row_count']
        }), 200
        
    except Exception as e:
        logger.error(f"DuckDB validation error: {e}")
        return jsonify({'success': False, 'message': f'DuckDB validation failed: {str(e)}'}), 500

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

@app.route('/api/validation/correct', methods=['POST'])
@login_required
def correct_errors():
    """Step 5: Apply corrections using DuckDB"""
    try:
        data = request.get_json()
        corrections = data.get('corrections', {})
        
        if not corrections:
            return jsonify({'success': False, 'message': 'No corrections provided'}), 400
        
        current_file = session.get('current_file')
        if not current_file:
            return jsonify({'success': False, 'message': 'No file data available'}), 400
        
        session_id = get_session_id()
        template_id = session['current_template_id']
        
        # Apply corrections using DuckDB
        corrected_count = apply_corrections_with_duckdb(corrections, session_id, template_id)
        
        session['corrections'] = corrections
        session['corrected_count'] = corrected_count
        
        logger.info(f"Applied {corrected_count} corrections using DuckDB")
        
        return jsonify({
            'success': True,
            'message': f'Corrections applied successfully using DuckDB',
            'corrected_rows': corrected_count,
            'processing_engine': 'DuckDB'
        }), 200
        
    except Exception as e:
        logger.error(f"DuckDB error correction failed: {e}")
        return jsonify({'success': False, 'message': f'DuckDB error correction failed: {str(e)}'}), 500

def apply_corrections_with_duckdb(corrections, session_id, template_id):
    """Apply corrections using DuckDB operations"""
    try:
        conn = duckdb_service.connection
        corrected_count = 0
        
        for correction_key, new_value in corrections.items():
            # Parse correction key (format: "row_column")
            parts = correction_key.split('_', 1)
            if len(parts) == 2:
                row_num, column_name = int(parts[0]) - 2, parts[1]  # Convert to 0-based index
                
                # Update the value in DuckDB
                conn.execute("""
                    UPDATE file_data 
                    SET column_value = ?
                    WHERE session_id = ? AND template_id = ? 
                    AND row_index = ? AND column_name = ?
                """, (new_value, session_id, template_id, row_num, column_name))
                
                corrected_count += 1
        
        logger.info(f"Applied {corrected_count} corrections in DuckDB")
        return corrected_count
        
    except Exception as e:
        logger.error(f"Error applying corrections in DuckDB: {e}")
        raise

@app.route('/api/validation/review-changes', methods=['GET'])
@login_required
def review_changes():
    """Step 6: Review changes and prepare for download"""
    try:
        corrections = session.get('corrections', {})
        corrected_count = session.get('corrected_count', 0)
        
        if not corrections:
            return jsonify({
                'success': True,
                'changes': [],
                'total_changes': 0,
                'message': 'No changes to review'
            }), 200
        
        # Convert corrections to changes format
        changes = []
        for correction_key, new_value in corrections.items():
            parts = correction_key.split('_', 1)
            if len(parts) == 2:
                row_num, column = parts[0], parts[1]
                changes.append({
                    'row': int(row_num),
                    'column': column,
                    'original_value': 'Error Value',  # Could fetch from DuckDB if needed
                    'corrected_value': new_value
                })
        
        return jsonify({
            'success': True,
            'changes': changes,
            'total_changes': corrected_count,
            'processing_engine': 'DuckDB',
            'ready_for_download': True
        }), 200
        
    except Exception as e:
        logger.error(f"Review changes error: {e}")
        return jsonify({'success': False, 'message': 'Review changes failed'}), 500

@app.route('/api/files/download-corrected', methods=['GET'])
@login_required
def download_corrected():
    """Download corrected file - data processed by DuckDB"""
    try:
        current_file = session.get('current_file')
        if not current_file:
            return jsonify({'success': False, 'message': 'No file data available'}), 400
        
        session_id = get_session_id()
        template_id = session['current_template_id']
        headers = session.get('selected_headers', [])
        
        # Get corrected data from DuckDB
        corrected_data = duckdb_service.get_data_rows(session_id, template_id, headers)
        
        if not corrected_data:
            return jsonify({'success': False, 'message': 'No corrected data available'}), 400
        
        # Create DataFrame from DuckDB data
        df = pd.DataFrame(corrected_data)
        original_filename = current_file['filename']
        
        # Generate corrected filename
        base_name, ext = os.path.splitext(original_filename)
        corrected_filename = f"{base_name}_corrected_duckdb{ext}"
        corrected_filepath = os.path.join(app.config['UPLOAD_FOLDER'], corrected_filename)
        
        # Save corrected file
        if ext.lower() == '.csv':
            df.to_csv(corrected_filepath, index=False)
        else:
            df.to_excel(corrected_filepath, index=False)
        
        logger.info(f"Generated corrected file using DuckDB data: {corrected_filename}")
        
        return send_file(corrected_filepath, as_attachment=True, download_name=corrected_filename)
        
    except Exception as e:
        logger.error(f"DuckDB download error: {e}")
        return jsonify({'success': False, 'message': f'Download failed: {str(e)}'}), 500

# Available rules endpoint
@app.route('/api/validation/rules', methods=['GET'])
@login_required
def get_available_rules():
    """Get available generic rules"""
    rules_info = {}
    for rule_id, rule_data in GENERIC_RULES.items():
        rules_info[rule_id] = {
            'name': rule_data['name'],
            'description': rule_data['description']
        }
    
    return jsonify({
        'success': True,
        'rules': rules_info,
        'processing_engine': 'DuckDB'
    }), 200

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check with database status"""
    try:
        # Test Fabric SQL connection
        fabric_status = fabric_service.test_connection()
        
        # Test DuckDB connection
        duckdb_status = {"status": "success", "message": "DuckDB operational"}
        try:
            duckdb_service.connection.execute("SELECT 1")
        except Exception as e:
            duckdb_status = {"status": "error", "message": f"DuckDB error: {str(e)}"}
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'fabric_sql': fabric_status,
                'duckdb': duckdb_status
            },
            'processing_engine': 'DuckDB (All files)',
            'configuration': {
                'duckdb_path': config.DUCKDB_PATH,
                'memory_limit': config.DUCKDB_MEMORY_LIMIT,
                'threads': config.DUCKDB_THREADS
            }
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
        
        # Initialize application
        init_application()
        
        logger.info("Starting Data Sync AI with DuckDB as PRIMARY processing engine...")
        logger.info("ALL files (regardless of size) will be processed using DuckDB")
        logger.info(f"Environment: {config.FLASK_ENV}")
        logger.info(f"DuckDB path: {config.DUCKDB_PATH}")
        logger.info(f"DuckDB memory limit: {config.DUCKDB_MEMORY_LIMIT}")
        logger.info(f"DuckDB threads: {config.DUCKDB_THREADS}")
        
        port = int(os.environ.get('PORT', config.PORT))
        app.run(debug=config.DEBUG, host='0.0.0.0', port=port)
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    finally:
        # Cleanup on shutdown
        try:
            fabric_service.close_connection()
            duckdb_service.close_connection()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
