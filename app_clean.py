"""
Data Sync AI - Clean Version with DuckDB Fallback
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

# Global flag to track SQL Fabric availability
SQL_FABRIC_AVAILABLE = False

# Helper functions for scalable data handling
def get_current_file_metadata():
    """Get file metadata from session (lightweight)"""
    return session.get('current_file_metadata', None)

def get_file_data_from_duckdb(template_id, session_id, headers=None, limit=None):
    """Retrieve file data from DuckDB (scalable for large datasets)"""
    try:
        conn = duckdb_service.connection
        
        if headers:
            headers_str = "', '".join(headers)
            query = f"""
                SELECT row_index, column_name, column_value 
                FROM file_data 
                WHERE session_id = ? AND template_id = ? 
                AND column_name IN ('{headers_str}')
                ORDER BY row_index, column_name
            """
        else:
            query = """
                SELECT row_index, column_name, column_value 
                FROM file_data 
                WHERE session_id = ? AND template_id = ? 
                ORDER BY row_index, column_name
            """
        
        if limit:
            query += f" LIMIT {limit}"
        
        result = conn.execute(query, (session_id, template_id)).fetchall()
        
        # Convert to structured format
        data = {}
        for row_index, column_name, column_value in result:
            if row_index not in data:
                data[row_index] = {}
            data[row_index][column_name] = column_value
        
        return list(data.values())
        
    except Exception as e:
        logger.error(f"Error retrieving file data from DuckDB: {e}")
        return []

def cleanup_old_file_data():
    """Clean up old file data from DuckDB to prevent storage bloat"""
    try:
        # Remove data older than 24 hours
        conn = duckdb_service.connection
        conn.execute("""
            DELETE FROM file_data 
            WHERE created_at < (CURRENT_TIMESTAMP - INTERVAL '24 hours')
        """)
        logger.info("Cleaned up old file data from DuckDB")
    except Exception as e:
        logger.error(f"Error cleaning up old file data: {e}")

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
            # Use DuckDB with sequence for ID generation
            conn = duckdb_service.connection
            conn.execute("""
                INSERT INTO users (id, email, password, first_name, last_name, mobile, is_approved)
                VALUES (nextval('users_id_seq'), ?, ?, ?, ?, ?, FALSE)
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
    
    # Create user management tables in DuckDB
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            email VARCHAR UNIQUE,
            password VARCHAR,
            first_name VARCHAR,
            last_name VARCHAR,
            mobile VARCHAR,
            is_approved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create sequence for auto-incrementing IDs
    try:
        conn.execute("CREATE SEQUENCE IF NOT EXISTS users_id_seq START 2")  # Start at 2 since admin is 1
    except:
        pass  # Sequence might already exist
    
    # Create default admin user in DuckDB
    admin_exists = conn.execute("SELECT COUNT(*) as count FROM users WHERE email = 'admin@example.com'").fetchall()
    if admin_exists[0][0] == 0:
        admin_password = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        conn.execute("""
            INSERT INTO users (id, email, password, first_name, last_name, mobile, is_approved)
            VALUES (1, 'admin@example.com', ?, 'Admin', 'User', '1234567890', TRUE)
        """, (admin_password,))
        logger.info("Default admin user created in DuckDB")
    
    logger.info("DuckDB fallback mode initialized successfully")

# ========================
# AUTHENTICATION ROUTES
# ========================

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

# ========================
# ADMIN ROUTES
# ========================

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

# ========================
# FILE UPLOAD ROUTES
# ========================

@app.route('/api/files/upload', methods=['POST'])
@login_required
def upload_file():
    """File upload endpoint with scalable data storage"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        # Save file
        filename = f"{session['user_id']}_{str(uuid.uuid4())}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Process with DuckDB
        session_id = get_session_id()
        template_id = int(time.time() * 1000)  # Simple template ID
        
        # Load file data into DuckDB (handles large files efficiently)
        file_info = duckdb_service.load_file_data(filepath, session_id, template_id)
        
        # Store ONLY metadata in session (not the actual data)
        session['current_file_metadata'] = {
            'filename': file.filename,
            'filepath': filepath,
            'template_id': template_id,
            'session_id': session_id,
            'headers': file_info['headers'][:50],  # Limit headers stored in session
            'row_count': file_info['row_count'],
            'upload_time': datetime.utcnow().isoformat()
        }
        session['current_template_id'] = template_id
        
        logger.info(f"File uploaded and processed: {file.filename} ({file_info['row_count']} rows) - Data stored in DuckDB")
        
        return jsonify({
            'success': True,
            'message': 'File uploaded successfully',
            'file_info': {
                'filename': file.filename,
                'headers': file_info['headers'],
                'row_count': file_info['row_count'],
                'storage': 'DuckDB',
                'scalable': True
            },
            'processing_engine': 'DuckDB'
        }), 200
        
    except Exception as e:
        logger.error(f"File upload error: {e}")
        return jsonify({'success': False, 'message': f'File upload failed: {str(e)}'}), 500

# ========================
# VALIDATION ROUTES
# ========================

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

# Add route to get file data sample (for preview without loading everything)
@app.route('/api/files/preview', methods=['GET'])
@login_required
def get_file_preview():
    """Get file data preview (first 100 rows) without loading full dataset"""
    try:
        file_metadata = get_current_file_metadata()
        if not file_metadata:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        # Get only first 100 rows for preview
        preview_data = get_file_data_from_duckdb(
            template_id=file_metadata['template_id'],
            session_id=file_metadata['session_id'],
            limit=100  # Scalable - only load what's needed
        )
        
        return jsonify({
            'success': True,
            'preview_data': preview_data,
            'total_rows': file_metadata['row_count'],
            'showing': f"First {min(100, file_metadata['row_count'])} rows",
            'storage': 'DuckDB (scalable)'
        }), 200
        
    except Exception as e:
        logger.error(f"File preview error: {e}")
@app.route('/api/validation/configure-headers', methods=['POST'])
@login_required  
def configure_headers():
    """Configure selected headers - scalable approach"""
    try:
        data = request.get_json()
        selected_headers = data.get('selected_headers', [])
        
        if not selected_headers:
            return jsonify({'success': False, 'message': 'No headers selected'}), 400
        
        file_metadata = get_current_file_metadata()
        if not file_metadata:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        # Store headers in session (lightweight metadata only)
        session['selected_headers'] = selected_headers
        
        # Update file metadata
        session['current_file_metadata']['selected_headers'] = selected_headers
        
        return jsonify({
            'success': True,
            'message': 'Headers configured successfully',
            'selected_headers': selected_headers,
            'total_rows': file_metadata['row_count'],
            'storage_method': 'DuckDB (scalable for large files)'
        }), 200
        
    except Exception as e:
        logger.error(f"Header configuration error: {e}")
        return jsonify({'success': False, 'message': 'Header configuration failed'}), 500

@app.route('/api/validation/process-chunk', methods=['POST'])
@login_required
def process_data_chunk():
    """Process data in chunks for validation - handles large files efficiently"""
    try:
        data = request.get_json()
        chunk_start = data.get('chunk_start', 0)
        chunk_size = data.get('chunk_size', 1000)  # Process 1000 rows at a time
        
        file_metadata = get_current_file_metadata()
        if not file_metadata:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        selected_headers = session.get('selected_headers', [])
        if not selected_headers:
            return jsonify({'success': False, 'message': 'No headers selected'}), 400
        
        # Get specific chunk of data from DuckDB
        conn = duckdb_service.connection
        headers_placeholder = "', '".join(selected_headers)
        query = f"""
            SELECT row_index, column_name, column_value 
            FROM file_data 
            WHERE session_id = ? AND template_id = ? 
            AND column_name IN ('{headers_placeholder}')
            AND row_index >= ? AND row_index < ?
            ORDER BY row_index, column_name
        """
        
        chunk_data = conn.execute(query, (
            file_metadata['session_id'],
            file_metadata['template_id'], 
            chunk_start,
            chunk_start + chunk_size
        )).fetchall()
        
        # Process chunk for validation
        chunk_results = []
        current_row = {}
        current_row_index = None
        
        for row_index, column_name, column_value in chunk_data:
            if row_index != current_row_index:
                if current_row:
                    chunk_results.append(current_row)
                current_row = {'row_index': row_index}
                current_row_index = row_index
            current_row[column_name] = column_value
        
        if current_row:
            chunk_results.append(current_row)
        
        return jsonify({
            'success': True,
            'chunk_data': chunk_results,
            'chunk_start': chunk_start,
            'chunk_size': len(chunk_results),
            'total_rows': file_metadata['row_count'],
            'has_more': chunk_start + chunk_size < file_metadata['row_count'],
            'processing': 'DuckDB chunked processing (scalable)'
        }), 200
        
    except Exception as e:
        logger.error(f"Chunk processing error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ========================
# HEALTH CHECK
# ========================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'sql_fabric_available': SQL_FABRIC_AVAILABLE,
            'processing_engine': 'DuckDB',
            'duckdb_path': config.DUCKDB_PATH
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# ========================
# STATIC FILE SERVING
# ========================

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_static(path):
    """Serve static files from frontend build"""
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return app.send_static_file(path)
    return app.send_static_file('index.html')

# ========================
# MAIN APPLICATION STARTUP
# ========================

if __name__ == '__main__':
    try:
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
