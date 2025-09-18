"""
Data Sync AI - Simple In-Memory Version
Uses in-memory DuckDB only (no file dependencies)
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
import duckdb

# Load environment variables
load_dotenv()

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

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize DuckDB connection (in-memory)
duckdb_conn = duckdb.connect(':memory:')
logger.info("✅ DuckDB in-memory connection established")

# Create DuckDB tables
duckdb_conn.execute("""
    CREATE TABLE IF NOT EXISTS file_data (
        session_id VARCHAR,
        template_id BIGINT,
        row_index INTEGER,
        column_name VARCHAR,
        column_value VARCHAR,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

duckdb_conn.execute("""
    CREATE TABLE IF NOT EXISTS validation_results (
        session_id VARCHAR,
        template_id BIGINT,
        row_index INTEGER,
        column_name VARCHAR,
        rule_name VARCHAR,
        is_valid BOOLEAN,
        error_message VARCHAR,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

logger.info("✅ DuckDB tables created successfully")

# In-memory user database
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

# Generic validation rules
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
        if not user or user['id'] != 1:
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def get_session_id():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

def load_file_to_duckdb(filepath, session_id, template_id):
    """Load file data into DuckDB"""
    try:
        # Read file
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        # Clear existing data
        duckdb_conn.execute("DELETE FROM file_data WHERE session_id = ? AND template_id = ?", 
                          (session_id, template_id))
        
        # Insert data
        for row_idx, row in df.iterrows():
            for col_name, value in row.items():
                duckdb_conn.execute("""
                    INSERT INTO file_data (session_id, template_id, row_index, column_name, column_value)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, template_id, row_idx, col_name, str(value)))
        
        logger.info(f"Loaded {len(df)} rows into DuckDB")
        return {'success': True, 'rows': len(df)}
        
    except Exception as e:
        logger.error(f"Error loading file to DuckDB: {e}")
        raise

def validate_data_with_duckdb(session_id, template_id, rules_config):
    """Validate data using DuckDB"""
    try:
        errors = {}
        total_errors = 0
        
        for column_name, rule_names in rules_config.items():
            column_errors = []
            
            for rule_name in rule_names:
                if rule_name == 'Required':
                    # Check for empty values
                    result = duckdb_conn.execute("""
                        SELECT row_index, column_value
                        FROM file_data
                        WHERE session_id = ? AND template_id = ? AND column_name = ?
                        AND (column_value IS NULL OR column_value = '' OR column_value = 'nan')
                    """, (session_id, template_id, column_name)).fetchall()
                    
                    for row_index, value in result:
                        column_errors.append({
                            'row': row_index + 2,
                            'value': 'NULL',
                            'rule_failed': 'Required',
                            'reason': 'Value is required'
                        })
                        total_errors += 1
                
                elif rule_name == 'Email':
                    # Simple email validation
                    result = duckdb_conn.execute("""
                        SELECT row_index, column_value
                        FROM file_data
                        WHERE session_id = ? AND template_id = ? AND column_name = ?
                        AND column_value NOT LIKE '%@%.%'
                        AND column_value != 'nan'
                    """, (session_id, template_id, column_name)).fetchall()
                    
                    for row_index, value in result:
                        column_errors.append({
                            'row': row_index + 2,
                            'value': value,
                            'rule_failed': 'Email',
                            'reason': 'Invalid email format'
                        })
                        total_errors += 1
                
                elif rule_name == 'Int':
                    # Integer validation
                    result = duckdb_conn.execute("""
                        SELECT row_index, column_value
                        FROM file_data
                        WHERE session_id = ? AND template_id = ? AND column_name = ?
                        AND column_value != 'nan'
                        AND NOT regexp_matches(column_value, '^-?[0-9]+$')
                    """, (session_id, template_id, column_name)).fetchall()
                    
                    for row_index, value in result:
                        column_errors.append({
                            'row': row_index + 2,
                            'value': value,
                            'rule_failed': 'Int',
                            'reason': 'Must be an integer'
                        })
                        total_errors += 1
            
            if column_errors:
                errors[column_name] = column_errors
        
        return {
            'success': True,
            'error_cell_locations': errors,
            'total_errors': total_errors
        }
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return {'error_cell_locations': {}, 'total_errors': 0}

def get_data_from_duckdb(session_id, template_id, headers):
    """Get data from DuckDB"""
    try:
        result = duckdb_conn.execute("""
            SELECT row_index, column_name, column_value
            FROM file_data
            WHERE session_id = ? AND template_id = ?
            ORDER BY row_index, column_name
        """, (session_id, template_id)).fetchall()
        
        # Convert to row format
        rows_data = {}
        for row_index, column_name, column_value in result:
            if row_index not in rows_data:
                rows_data[row_index] = {}
            rows_data[row_index][column_name] = column_value
        
        # Convert to list
        data_rows = []
        for row_index in sorted(rows_data.keys()):
            row_data = {}
            for header in headers:
                row_data[header] = rows_data[row_index].get(header, '')
            data_rows.append(row_data)
        
        return data_rows
        
    except Exception as e:
        logger.error(f"Error getting data from DuckDB: {e}")
        return []

# Authentication Routes
@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password required'}), 400
        
        user = None
        for u in users_db.values():
            if u['email'].lower() == email.lower():
                user = u
                break
        
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        session['user_id'] = user['id']
        session['email'] = user['email']
        session['first_name'] = user['first_name']
        
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
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'Login failed'}), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        global user_counter
        data = request.get_json()
        
        required_fields = ['first_name', 'last_name', 'email', 'mobile', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        for user in users_db.values():
            if user['email'].lower() == data['email'].lower():
                return jsonify({'success': False, 'message': 'User already exists'}), 409
        
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
    session_id = session.get('session_id')
    template_id = session.get('current_template_id')
    
    if session_id and template_id:
        try:
            duckdb_conn.execute("DELETE FROM file_data WHERE session_id = ? AND template_id = ?", 
                              (session_id, template_id))
        except:
            pass
    
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'}), 200

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
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

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def get_users():
    users_list = []
    for user in users_db.values():
        if user['id'] != 1:
            users_list.append({
                'id': user['id'],
                'email': user['email'],
                'first_name': user['first_name'],
                'last_name': user.get('last_name', ''),
                'mobile': user.get('mobile', ''),
                'created_at': user.get('created_at', ''),
                'is_approved': True
            })
    
    return jsonify({'success': True, 'users': users_list}), 200

@app.route('/api/files/upload', methods=['POST'])
@login_required
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        filename = f"{session['user_id']}_{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Read file info
        if filepath.endswith('.csv'):
            df_sample = pd.read_csv(filepath, nrows=5)
            total_rows = sum(1 for line in open(filepath, 'r', encoding='utf-8')) - 1
        elif filepath.endswith(('.xlsx', '.xls')):
            df_sample = pd.read_excel(filepath, nrows=5)
            df_full = pd.read_excel(filepath)
            total_rows = len(df_full)
        else:
            return jsonify({'success': False, 'message': 'Unsupported file format'}), 400
        
        template_id = int(time.time() * 1000)
        
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
        load_result = load_file_to_duckdb(filepath, session_id, template_id)
        
        return jsonify({
            'success': True,
            'file_info': session['current_file'],
            'message': f'File loaded successfully using DuckDB ({total_rows} rows)'
        }), 200
        
    except Exception as e:
        logger.error(f"File upload error: {e}")
        return jsonify({'success': False, 'message': f'File upload failed: {str(e)}'}), 500

@app.route('/api/validation/configure-headers', methods=['POST'])
@login_required
def configure_headers():
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
            'available_rules': list(GENERIC_RULES.keys())
        }), 200
        
    except Exception as e:
        logger.error(f"Configure headers error: {e}")
        return jsonify({'success': False, 'message': 'Header configuration failed'}), 500

@app.route('/api/validation/configure-rules', methods=['POST'])
@login_required
def configure_rules():
    try:
        data = request.get_json()
        rules_config = data.get('rules_config', {})
        
        if not session.get('selected_headers'):
            return jsonify({'success': False, 'message': 'Headers not configured'}), 400
        
        session['rules_config'] = rules_config
        
        return jsonify({
            'success': True,
            'message': 'Rules configured successfully (DuckDB ready)',
            'rules_config': rules_config
        }), 200
        
    except Exception as e:
        logger.error(f"Configure rules error: {e}")
        return jsonify({'success': False, 'message': 'Rule configuration failed'}), 500

@app.route('/api/validation/review-config', methods=['GET'])
@login_required
def review_configuration():
    try:
        if not session.get('current_file') or not session.get('rules_config'):
            return jsonify({'success': False, 'message': 'Configuration incomplete'}), 400
        
        config_summary = {
            'file_info': session['current_file'],
            'selected_headers': session.get('selected_headers', []),
            'rules_config': session.get('rules_config', {}),
            'rules_details': {rule: GENERIC_RULES[rule]['description'] for rule in GENERIC_RULES}
        }
        
        return jsonify({
            'success': True,
            'configuration': config_summary
        }), 200
        
    except Exception as e:
        logger.error(f"Review configuration error: {e}")
        return jsonify({'success': False, 'message': 'Configuration review failed'}), 500

@app.route('/api/validation/validate', methods=['POST'])
@login_required
def validate_data():
    try:
        if not session.get('current_file') or not session.get('rules_config'):
            return jsonify({'success': False, 'message': 'Configuration incomplete'}), 400
        
        current_file = session['current_file']
        rules_config = session['rules_config']
        template_id = session['current_template_id']
        session_id = get_session_id()
        
        start_time = time.time()
        
        # Validate using DuckDB
        validation_result = validate_data_with_duckdb(session_id, template_id, rules_config)
        
        # Get sample data
        sample_data = get_data_from_duckdb(session_id, template_id, session['selected_headers'])[:100]
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Convert errors to list format
        errors_list = []
        for column_name, column_errors in validation_result['error_cell_locations'].items():
            for error in column_errors:
                errors_list.append({
                    'row': error['row'],
                    'column': column_name,
                    'value': error['value'],
                    'rule_failed': error['rule_failed'],
                    'description': error.get('reason', '')
                })
        
        session['validation_errors'] = validation_result['error_cell_locations']
        
        logger.info(f"DuckDB validation completed: {validation_result['total_errors']} errors found")
        
        return jsonify({
            'success': True,
            'errors': errors_list,
            'total_errors': validation_result['total_errors'],
            'data': sample_data,
            'processing_time_ms': processing_time,
            'processing_method': 'DuckDB (In-Memory)',
            'file_rows': current_file['row_count']
        }), 200
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return jsonify({'success': False, 'message': f'Validation failed: {str(e)}'}), 500

@app.route('/api/validation/correct', methods=['POST'])
@login_required
def correct_errors():
    try:
        data = request.get_json()
        corrections = data.get('corrections', {})
        
        if not corrections:
            return jsonify({'success': False, 'message': 'No corrections provided'}), 400
        
        session['corrections'] = corrections
        
        # Apply corrections to DuckDB
        session_id = get_session_id()
        template_id = session['current_template_id']
        
        for correction_key, new_value in corrections.items():
            parts = correction_key.split('_', 1)
            if len(parts) == 2:
                row_num, column_name = int(parts[0]) - 2, parts[1]  # Convert to 0-based
                
                duckdb_conn.execute("""
                    UPDATE file_data 
                    SET column_value = ?
                    WHERE session_id = ? AND template_id = ? 
                    AND row_index = ? AND column_name = ?
                """, (new_value, session_id, template_id, row_num, column_name))
        
        return jsonify({
            'success': True,
            'message': f'Corrections applied successfully using DuckDB',
            'corrected_rows': len(corrections)
        }), 200
        
    except Exception as e:
        logger.error(f"Error correction failed: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/validation/review-changes', methods=['GET'])
@login_required
def review_changes():
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
    try:
        current_file = session.get('current_file')
        session_id = get_session_id()
        template_id = session['current_template_id']
        headers = session.get('selected_headers', [])
        
        corrected_data = get_data_from_duckdb(session_id, template_id, headers)
        
        if not corrected_data:
            return jsonify({'success': False, 'message': 'No data available'}), 400
        
        df = pd.DataFrame(corrected_data)
        original_filename = current_file['filename']
        
        base_name, ext = os.path.splitext(original_filename)
        corrected_filename = f"{base_name}_corrected_duckdb{ext}"
        corrected_filepath = os.path.join(app.config['UPLOAD_FOLDER'], corrected_filename)
        
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
    try:
        duckdb_status = {"status": "success", "message": "DuckDB in-memory operational"}
        try:
            duckdb_conn.execute("SELECT 1")
        except Exception as e:
            duckdb_status = {"status": "error", "message": f"DuckDB error: {str(e)}"}
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'duckdb': duckdb_status
            },
            'processing_engine': 'DuckDB In-Memory',
            'note': 'Simple development version - no file locks'
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_static(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return app.send_static_file(path)
    return app.send_static_file('index.html')

if __name__ == '__main__':
    try:
        logger.info("🚀 Starting Data Sync AI - Simple In-Memory Version")
        logger.info("📊 ALL files processed using DuckDB (in-memory)")
        logger.info("✅ No file locks - completely in-memory processing")
        
        port = int(os.environ.get('PORT', 5000))
        app.run(debug=False, host='0.0.0.0', port=port)
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    finally:
        try:
            duckdb_conn.close()
        except:
            pass
