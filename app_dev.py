"""
Data Sync AI - DuckDB Only Mode (Development)
Simplified version using only DuckDB (no Fabric SQL dependency)
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

# Load environment variables first
load_dotenv()

# Set development environment BEFORE importing DuckDB service
os.environ['FLASK_ENV'] = 'development'

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# Import DuckDB service only
from backend.services.duckdb_service import duckdb_service

# Initialize Flask app
app = Flask(__name__, static_folder='../data-sync-ai-fnd/dist', static_url_path='')
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './sessions'
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# Initialize extensions
Session(app)
CORS(app, supports_credentials=True, origins=['http://localhost:5173', 'http://localhost:3000'])

# Ensure directories exist
os.makedirs('./sessions', exist_ok=True)
os.makedirs('./uploads', exist_ok=True)
os.makedirs('./logs', exist_ok=True)
os.makedirs('./data', exist_ok=True)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# In-memory user database (for development)
users_db = {
    1: {
        'id': 1,
        'email': 'admin@example.com',
        'password': bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
        'first_name': 'Admin',
        'last_name': 'User',
        'created_at': datetime.now().isoformat()
    }
}
user_counter = 1

# Comprehensive Generic validation rules
GENERIC_RULES = {
    'Required': {
        'name': 'Required',
        'description': 'Ensures the field is not null'
    },
    'Int': {
        'name': 'Int', 
        'description': 'Validates integer format'
    },
    'Float': {
        'name': 'Float',
        'description': 'Validates number format (integer or decimal)'
    },
    'Text': {
        'name': 'Text',
        'description': 'Allows text with quotes and parentheses'
    },
    'Email': {
        'name': 'Email',
        'description': 'Validates email format'
    },
    'Date': {
        'name': 'Date',
        'description': 'Validates date format'
    },
    'Boolean': {
        'name': 'Boolean',
        'description': 'Validates boolean format (true/false or 0/1)'
    },
    'Alphanumeric': {
        'name': 'Alphanumeric',
        'description': 'Validates alphanumeric format'
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
        
        user = users_db.get(session['user_id'])
        if not user or user['id'] != 1:  # Only user ID 1 is admin
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

# Authentication Routes
@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password required'}), 400
        
        # Find user
        user = None
        for u in users_db.values():
            if u['email'].lower() == email.lower():
                user = u
                break
        
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        # Create session
        session['user_id'] = user['id']
        session['email'] = user['email']
        session['first_name'] = user['first_name']
        
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
        logger.error(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'Login failed'}), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration"""
    try:
        global user_counter
        data = request.get_json()
        
        required_fields = ['first_name', 'last_name', 'email', 'mobile', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        # Check if user exists
        for user in users_db.values():
            if user['email'].lower() == data['email'].lower():
                return jsonify({'success': False, 'message': 'User already exists'}), 409
        
        # Create new user
        user_counter += 1
        hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        users_db[user_counter] = {
            'id': user_counter,
            'email': data['email'].lower(),
            'password': hashed_password,
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'mobile': data.get('mobile', ''),
            'created_at': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'message': 'Registration successful. You can now login.'
        }), 201
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'success': False, 'message': 'Registration failed'}), 500

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    """User logout with DuckDB cleanup"""
    session_id = session.get('session_id')
    template_id = session.get('current_template_id')
    
    # Clean up DuckDB session data
    if session_id and template_id:
        try:
            duckdb_service.cleanup_session_data(session_id, template_id)
        except Exception as e:
            logger.warning(f"Failed to cleanup session data: {e}")
    
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'}), 200

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    """Check authentication status"""
    if 'user_id' in session:
        user = users_db.get(session['user_id'])
        if user:
            return jsonify({
                'success': True,
                'user': {
                    'id': user['id'],
                    'email': user['email'],
                    'first_name': user['first_name'],
                    'last_name': user.get('last_name', ''),
                    'role': 'admin' if user['id'] == 1 else 'user'
                }
            }), 200
    
    return jsonify({'success': False, 'message': 'Not authenticated'}), 401

# Admin Routes
@app.route('/api/admin/users', methods=['GET'])
@admin_required
def get_users():
    """Get all users for admin dashboard"""
    try:
        users_list = []
        for user in users_db.values():
            if user['id'] != 1:  # Don't show admin
                users_list.append({
                    'id': user['id'],
                    'email': user['email'],
                    'first_name': user['first_name'],
                    'last_name': user.get('last_name', ''),
                    'mobile': user.get('mobile', ''),
                    'created_at': user.get('created_at', ''),
                    'is_approved': True  # Always approved in dev mode
                })
        
        return jsonify({'success': True, 'users': users_list}), 200
        
    except Exception as e:
        logger.error(f"Get users error: {e}")
        return jsonify({'success': False, 'message': 'Failed to get users'}), 500

# File Upload Route - ALWAYS uses DuckDB
@app.route('/api/files/upload', methods=['POST'])
@login_required
def upload_file():
    """Upload file for DuckDB processing"""
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
        
        # Read file to get basic info
        if filepath.endswith('.csv'):
            df_sample = pd.read_csv(filepath, nrows=5)
            total_rows = sum(1 for line in open(filepath, 'r', encoding='utf-8')) - 1
        elif filepath.endswith(('.xlsx', '.xls')):
            df_sample = pd.read_excel(filepath, nrows=5)
            df_full = pd.read_excel(filepath)
            total_rows = len(df_full)
        else:
            return jsonify({'success': False, 'message': 'Unsupported file format'}), 400
        
        # Generate template ID
        template_id = int(time.time() * 1000)  # Simple ID generation
        
        # Store in session
        session['current_file'] = {
            'filename': filename,
            'filepath': filepath,
            'headers': df_sample.columns.tolist(),
            'row_count': total_rows,
            'preview': df_sample.to_dict('records'),
            'template_id': template_id,
            'processing_engine': 'DuckDB'
        }
        
        session['current_template_id'] = template_id
        
        # Load into DuckDB
        session_id = get_session_id()
        duckdb_result = duckdb_service.load_file_data(filepath, session_id, template_id)
        logger.info(f"File loaded into DuckDB: {total_rows} rows")
        
        return jsonify({
            'success': True,
            'file_info': session['current_file'],
            'message': f'File loaded successfully using DuckDB ({total_rows} rows)'
        }), 200
        
    except Exception as e:
        logger.error(f"File upload error: {e}")
        return jsonify({'success': False, 'message': f'File upload failed: {str(e)}'}), 500

# Rule Configuration Routes
@app.route('/api/validation/configure-headers', methods=['POST'])
@login_required
def configure_headers():
    """Step 1: Select headers for validation"""
    try:
        data = request.get_json()
        selected_headers = data.get('selected_headers', [])
        
        if not session.get('current_file'):
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
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
    """Step 2: Configure generic rules"""
    try:
        data = request.get_json()
        rules_config = data.get('rules_config', {})
        
        if not session.get('selected_headers'):
            return jsonify({'success': False, 'message': 'Headers not configured'}), 400
        
        session['rules_config'] = rules_config
        
        return jsonify({
            'success': True,
            'message': 'Rules configured successfully (DuckDB ready)',
            'rules_config': rules_config,
            'processing_engine': 'DuckDB'
        }), 200
        
    except Exception as e:
        logger.error(f"Configure rules error: {e}")
        return jsonify({'success': False, 'message': 'Rule configuration failed'}), 500

@app.route('/api/validation/review-config', methods=['GET'])
@login_required
def review_configuration():
    """Step 3: Review configuration"""
    try:
        if not session.get('current_file') or not session.get('rules_config'):
            return jsonify({'success': False, 'message': 'Configuration incomplete'}), 400
        
        config_summary = {
            'file_info': session['current_file'],
            'selected_headers': session.get('selected_headers', []),
            'rules_config': session.get('rules_config', {}),
            'rules_details': {rule: GENERIC_RULES[rule]['description'] for rule in GENERIC_RULES},
            'processing_engine': 'DuckDB'
        }
        
        return jsonify({
            'success': True,
            'configuration': config_summary
        }), 200
        
    except Exception as e:
        logger.error(f"Review configuration error: {e}")
        return jsonify({'success': False, 'message': 'Configuration review failed'}), 500

# Data Validation Routes
@app.route('/api/validation/validate', methods=['POST'])
@login_required
def validate_data():
    """Step 4: Validate data using DuckDB"""
    try:
        if not session.get('current_file') or not session.get('rules_config'):
            return jsonify({'success': False, 'message': 'Configuration incomplete'}), 400
        
        current_file = session['current_file']
        rules_config = session['rules_config']
        template_id = session['current_template_id']
        session_id = get_session_id()
        
        start_time = time.time()
        
        # Use DuckDB for validation
        validation_result = duckdb_service.validate_data(session_id, template_id, rules_config)
        
        # Get sample data
        sample_data = duckdb_service.get_data_rows(session_id, template_id, 
                                                 session['selected_headers'])[:100]
        
        processing_time = int((time.time() - start_time) * 1000)
        
        session['validation_errors'] = validation_result['error_cell_locations']
        
        logger.info(f"DuckDB validation completed: {validation_result['total_errors']} errors found")
        
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
        return jsonify({'success': False, 'message': f'Validation failed: {str(e)}'}), 500

def convert_errors_to_list(error_dict):
    """Convert error dictionary to list format"""
    errors_list = []
    for column_name, column_errors in error_dict.items():
        for error in column_errors:
            errors_list.append({
                'row': error['row'],
                'column': column_name,
                'value': error['value'],
                'rule_failed': error['rule_failed'],
                'description': error.get('reason', '')
            })
    return errors_list

@app.route('/api/validation/correct', methods=['POST'])
@login_required
def correct_errors():
    """Step 5: Apply corrections"""
    try:
        data = request.get_json()
        corrections = data.get('corrections', {})
        
        if not corrections:
            return jsonify({'success': False, 'message': 'No corrections provided'}), 400
        
        session['corrections'] = corrections
        
        return jsonify({
            'success': True,
            'message': f'Corrections applied successfully',
            'corrected_rows': len(corrections)
        }), 200
        
    except Exception as e:
        logger.error(f"Error correction failed: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/validation/review-changes', methods=['GET'])
@login_required
def review_changes():
    """Step 6: Review changes"""
    try:
        corrections = session.get('corrections', {})
        
        if not corrections:
            return jsonify({
                'success': True,
                'changes': [],
                'total_changes': 0
            }), 200
        
        changes = []
        for correction_key, new_value in corrections.items():
            parts = correction_key.split('_', 1)
            if len(parts) == 2:
                row_num, column = parts[0], parts[1]
                changes.append({
                    'row': int(row_num),
                    'column': column,
                    'original_value': 'Error Value',
                    'corrected_value': new_value
                })
        
        return jsonify({
            'success': True,
            'changes': changes,
            'total_changes': len(changes)
        }), 200
        
    except Exception as e:
        logger.error(f"Review changes error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/files/download-corrected', methods=['GET'])
@login_required
def download_corrected():
    """Download corrected file"""
    try:
        current_file = session.get('current_file')
        session_id = get_session_id()
        template_id = session['current_template_id']
        headers = session.get('selected_headers', [])
        
        # Get data from DuckDB
        corrected_data = duckdb_service.get_data_rows(session_id, template_id, headers)
        
        if not corrected_data:
            return jsonify({'success': False, 'message': 'No data available'}), 400
        
        # Create DataFrame
        df = pd.DataFrame(corrected_data)
        original_filename = current_file['filename']
        
        base_name, ext = os.path.splitext(original_filename)
        corrected_filename = f"{base_name}_corrected_duckdb{ext}"
        corrected_filepath = os.path.join(app.config['UPLOAD_FOLDER'], corrected_filename)
        
        # Save file
        if ext.lower() == '.csv':
            df.to_csv(corrected_filepath, index=False)
        else:
            df.to_excel(corrected_filepath, index=False)
        
        return send_file(corrected_filepath, as_attachment=True, download_name=corrected_filename)
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/validation/rules', methods=['GET'])
@login_required
def get_available_rules():
    """Get available rules"""
    rules_info = {}
    for rule_id, rule_data in GENERIC_RULES.items():
        rules_info[rule_id] = {
            'name': rule_data['name'],
            'description': rule_data['description']
        }
    
    return jsonify({
        'success': True,
        'rules': rules_info
    }), 200

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check"""
    try:
        duckdb_status = {"status": "success", "message": "DuckDB operational"}
        try:
            duckdb_service.connection.execute("SELECT 1")
        except Exception as e:
            duckdb_status = {"status": "error", "message": f"DuckDB error: {str(e)}"}
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'duckdb': duckdb_status
            },
            'processing_engine': 'DuckDB Only (Development Mode)',
            'note': 'Fabric SQL disabled for development'
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# Static file serving
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_static(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return app.send_static_file(path)
    return app.send_static_file('index.html')

if __name__ == '__main__':
    try:
        logger.info("🚀 Starting Data Sync AI - DuckDB Development Mode")
        logger.info("📊 ALL files processed using DuckDB")
        logger.info("⚠️  Fabric SQL disabled for development")
        logger.info(f"DuckDB path: ./data/datasync.duckdb")
        
        port = int(os.environ.get('PORT', 5000))
        app.run(debug=False, host='0.0.0.0', port=port)  # Disable debug to avoid reloader
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    finally:
        try:
            duckdb_service.close_connection()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
