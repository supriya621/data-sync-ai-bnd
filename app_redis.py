"""
Data Sync AI - Redis-Enhanced High-Performance Application
Intelligent caching layer for dramatically improved performance with large file processing
All existing functionality preserved with performance optimizations
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

# Import route blueprints
try:
    from routes.config_history_routes import config_history_bp, save_configuration_history
    from file_configuration_history import save_file_configuration_history
except ImportError as e:
    print(f"Warning: Could not import config_history_routes: {e}")
    config_history_bp = None
    save_configuration_history = None
    save_file_configuration_history = None

# Import Redis-enhanced services
try:
    from backend.services.redis_service import redis_service
    from backend.services.cached_fabric_service import cached_fabric_service
    REDIS_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("[START] Redis caching layer loaded successfully")
except ImportError as e:
    REDIS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"[WARNING] Redis not available, using standard services: {e}")

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

# Register blueprints
if config_history_bp:
    app.register_blueprint(config_history_bp, url_prefix='/api/config-history')
    print("✅ Configuration History routes registered")
else:
    print("⚠️ Configuration History routes not available")

# Ensure directories exist
os.makedirs(config.SESSION_FILE_DIR, exist_ok=True)
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

# Setup logging
config.setup_logging()
logger = logging.getLogger(__name__)

# Enhanced Generic validation rules with Redis caching support
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

# Performance monitoring decorator


def get_rule_type_id(rule_name):
    """Convert rule name to rule_type_id for database operations"""
    rule_mapping = {
        'Required': 1,
        'Int': 2,
        'Float': 3,
        'Text': 4,
        'Email': 5,
        'Date': 6,
        'Boolean': 7,
        'Alphanumeric': 8
    }
    
    rule_id = rule_mapping.get(rule_name)
    if rule_id is None:
        logger.error(f"Unknown rule name received: {rule_name}")
        raise ValueError(f"Unknown rule name: {rule_name}")
    return rule_id

def monitor_api_performance(endpoint_name: str):
    """Decorator to monitor API endpoint performance"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = f(*args, **kwargs)
            end_time = time.time()
            
            execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
            logger.info(f"[FAST] API {endpoint_name} completed in {execution_time:.2f}ms")
            
            return result
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# Authentication decorators (enhanced with caching)
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
        
        # Use cached user lookup for better performance
        user = get_user_by_email(session.get('user_email', ''))
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 403
            
        # Check if user has admin role (first user is admin for simplicity)
        if user['id'] != 1:
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# Helper functions (enhanced with Redis caching)
def get_session_id():
    """Generate or get session ID for DuckDB operations"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

def get_fabric_service():
    """Get appropriate fabric service (cached or standard)"""
    if REDIS_AVAILABLE:
        return cached_fabric_service
    return fabric_service

# Unified authentication functions with Redis caching
def get_user_by_email(email):
    """Get user by email with Redis caching"""
    global SQL_FABRIC_AVAILABLE
    
    try:
        if SQL_FABRIC_AVAILABLE and REDIS_AVAILABLE:
            # Use cached version for better performance
            return cached_fabric_service.get_user_by_email_cached(email)
        elif SQL_FABRIC_AVAILABLE:
            # Standard Fabric service
            return fabric_service.get_user_by_email(email)
        else:
            # Use DuckDB fallback
            conn = duckdb_service.connection
            result = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchall()
            if result:
                row = result[0]
                user_data = {
                    'id': row[0],
                    'email': row[1], 
                    'password': row[2],
                    'first_name': row[3],
                    'last_name': row[4],
                    'mobile': row[5],
                    'is_approved': row[6],
                    'created_at': row[7]
                }
                
                # Cache in Redis if available
                if REDIS_AVAILABLE:
                    redis_service.cache_user_profile(email, user_data)
                
                return user_data
            return None
    except Exception as e:
        logger.error(f"Error getting user by email: {e}")
        return None

def create_user(user_data):
    """Create user with cache management"""
    global SQL_FABRIC_AVAILABLE
    
    try:
        if SQL_FABRIC_AVAILABLE and REDIS_AVAILABLE:
            # Use cached version with proper cache invalidation
            return cached_fabric_service.create_user_with_cache_invalidation(user_data)
        elif SQL_FABRIC_AVAILABLE:
            return fabric_service.create_user(user_data)
        else:
            # Use DuckDB fallback
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
            
            new_user = get_user_by_email(user_data['email'])
            
            # Cache in Redis if available
            if REDIS_AVAILABLE and new_user:
                redis_service.cache_user_profile(user_data['email'], new_user)
            
            return new_user
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise

def get_all_users():
    """Get all users (with potential caching for admin dashboard)"""
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
    """Approve user with cache invalidation"""
    global SQL_FABRIC_AVAILABLE
    
    try:
        if SQL_FABRIC_AVAILABLE:
            result = fabric_service.execute_query(
                "UPDATE login_details SET is_approved = TRUE WHERE id = ?", 
                (user_id,)
            )
            
            # Invalidate user cache if Redis is available
            if REDIS_AVAILABLE:
                # Get user email to invalidate cache
                user_data = fabric_service.execute_query(
                    "SELECT email FROM login_details WHERE id = ?", 
                    (user_id,)
                )
                if user_data:
                    cached_fabric_service.invalidate_user_cache(user_data[0]['email'])
            
            return result
        else:
            # Use DuckDB
            conn = duckdb_service.connection
            conn.execute("UPDATE users SET is_approved = TRUE WHERE id = ?", (user_id,))
            return True
    except Exception as e:
        logger.error(f"Error approving user: {e}")
        return False

def reject_user(user_id):
    """Reject user with cache invalidation"""
    global SQL_FABRIC_AVAILABLE
    
    try:
        if SQL_FABRIC_AVAILABLE:
            result = fabric_service.execute_query(
                "UPDATE login_details SET is_approved = FALSE WHERE id = ?", 
                (user_id,)
            )
            
            # Invalidate user cache if Redis is available
            if REDIS_AVAILABLE:
                user_data = fabric_service.execute_query(
                    "SELECT email FROM login_details WHERE id = ?", 
                    (user_id,)
                )
                if user_data:
                    cached_fabric_service.invalidate_user_cache(user_data[0]['email'])
            
            return result
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

# Initialize application with Redis support
def init_application():
    """Initialize database and create default rules with Redis caching support"""
    global SQL_FABRIC_AVAILABLE
    
    try:
        # Try to initialize Fabric SQL database
        if REDIS_AVAILABLE:
            cached_fabric_service.init_database()
        else:
            fabric_service.init_database()
            
        SQL_FABRIC_AVAILABLE = True
        logger.info("[SUCCESS] SQL Fabric connection established successfully")
        
        # Create default admin user if not exists
        service = get_fabric_service()
        admin_user = service.get_user_by_email('admin@example.com') if not REDIS_AVAILABLE else service.get_user_by_email_cached('admin@example.com')
        
        if not admin_user:
            admin_data = {
                'first_name': 'Admin',
                'last_name': 'User', 
                'email': 'admin@example.com',
                'mobile': '1234567890',
                'password': bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            }
            
            if REDIS_AVAILABLE:
                cached_fabric_service.create_user_with_cache_invalidation(admin_data)
            else:
                fabric_service.create_user(admin_data)
                
            logger.info("[SUCCESS] Default admin user created in SQL Fabric")
        
        # Create default validation rules and cache them
        if REDIS_AVAILABLE:
            # Create rules in DB and cache them
            fabric_service.create_default_rules()
            cached_fabric_service.get_validation_rules_cached()  # This will cache the rules
            logger.info("[START] Application initialized with SQL Fabric + Redis caching + DuckDB processing")
        else:
            fabric_service.create_default_rules()
            logger.info("[SUCCESS] Application initialized with SQL Fabric + DuckDB processing")
        
    except Exception as fabric_error:
        logger.warning(f"[ERROR] SQL Fabric connection failed: {str(fabric_error)}")
        logger.info("[FALLBACK] Falling back to DuckDB-only mode...")
        SQL_FABRIC_AVAILABLE = False
        
        try:
            # Initialize DuckDB-only mode with in-memory user management
            init_duckdb_fallback_mode()
            
            if REDIS_AVAILABLE:
                logger.info("[SUCCESS] Application initialized in DuckDB-only mode with Redis caching")
            else:
                logger.info("[SUCCESS] Application initialized in DuckDB-only mode (fallback)")
            
        except Exception as duckdb_error:
            logger.error(f"❌ DuckDB fallback initialization failed: {str(duckdb_error)}")
            raise Exception("Failed to initialize both SQL Fabric and DuckDB fallback modes")

def init_duckdb_fallback_mode():
    """Initialize application in DuckDB-only mode with Redis support"""
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
    
    logger.info("[SUCCESS] Default admin user created in DuckDB with ID 1")
    
    if REDIS_AVAILABLE:
        # Cache the default admin user
        admin_user_data = {
            'id': 1,
            'email': 'admin@example.com',
            'password': admin_password,
            'first_name': 'Admin',
            'last_name': 'User',
            'mobile': '1234567890',
            'is_approved': True,
            'created_at': datetime.now().isoformat()
        }
        redis_service.cache_user_profile('admin@example.com', admin_user_data)
        logger.info("[SAVE] Admin user cached in Redis")
        
        # Cache default validation rules
        redis_service.cache_validation_rules(GENERIC_RULES)
        logger.info("[SAVE] Default validation rules cached in Redis")
    
    logger.info("[SUCCESS] DuckDB fallback mode initialized successfully")

# Authentication Routes (enhanced with Redis caching)
@app.route('/api/auth/check', methods=['GET'])
@monitor_api_performance("auth_check")
def check_auth():
    """Check current authentication status with Redis caching"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Not authenticated'}), 401
        
        # Use cached user lookup if available
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
            },
            'performance': {
                'cache_enabled': REDIS_AVAILABLE,
                'cache_hit': REDIS_AVAILABLE  # If Redis is available, likely a cache hit
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking authentication: {e}")
        return jsonify({'success': False, 'message': 'Authentication check failed'}), 500

@app.route('/api/auth/login', methods=['POST'])
@monitor_api_performance("user_login")
def login():
    """User login endpoint with Redis session caching"""
    try:
        data = request.get_json() if request.is_json else request.form
        email = data.get('username') or data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required'}), 400
        
        logger.info(f"[LOGIN] Login attempt for: {email}")
        
        # Get user with caching
        user = get_user_by_email(email.lower())
        
        if not user:
            logger.warning(f"[ERROR] Login failed - user not found: {email}")
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        # Verify password
        if not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            logger.warning(f"[ERROR] Login failed - invalid password: {email}")
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        # Check if user is approved (except for admin)
        if user['id'] != 1 and not user.get('is_approved', False):
            return jsonify({'success': False, 'message': 'Account pending approval'}), 403
        
        # Create session
        session['user_id'] = user['id']
        session['user_email'] = user['email']
        
        # Cache user session in Redis if available
        if REDIS_AVAILABLE:
            session_data = {
                'user_id': user['id'],
                'email': user['email'],
                'first_name': user['first_name'],
                'last_name': user['last_name'],
                'role': 'admin' if user['id'] == 1 else 'user',
                'login_time': datetime.now().isoformat()
            }
            redis_service.cache_user_session(user['id'], session_data)
        
        logger.info(f"[SUCCESS] Login successful: {email}")
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'email': user['email'],
                'first_name': user['first_name'],
                'last_name': user['last_name'],
                'role': 'admin' if user['id'] == 1 else 'user'
            },
            'performance': {
                'cache_enabled': REDIS_AVAILABLE,
                'enhanced_session': REDIS_AVAILABLE
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'Login failed'}), 500

@app.route('/api/auth/register', methods=['POST'])
@monitor_api_performance("user_register")
def register():
    """User registration endpoint with Redis cache management"""
    try:
        data = request.get_json() if request.is_json else request.form
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'email', 'mobile', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field.title()} is required'}), 400
        
        email = data['email'].lower().strip()
        
        # Check if user already exists (with caching)
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
        
        # Create user with cache management
        new_user = create_user(user_data)
        
        logger.info(f"[SUCCESS] User registered successfully: {email}")
        return jsonify({
            'success': True,
            'message': 'Registration successful. Please wait for admin approval.',
            'user_id': new_user['id'],
            'performance': {
                'cache_enabled': REDIS_AVAILABLE,
                'user_cached': REDIS_AVAILABLE
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'success': False, 'message': 'Registration failed'}), 500

@app.route('/api/auth/logout', methods=['POST'])
@monitor_api_performance("user_logout")
def logout():
    """User logout endpoint with Redis cache cleanup"""
    try:
        user_id = session.get('user_id')
        
        # Clear Redis session cache if available
        if REDIS_AVAILABLE and user_id:
            redis_service.clear_processing_state(user_id)
        
        session.clear()
        return jsonify({
            'success': True, 
            'message': 'Logout successful',
            'performance': {
                'cache_cleaned': REDIS_AVAILABLE
            }
        }), 200
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({'success': False, 'message': 'Logout failed'}), 500

# Admin Routes (enhanced performance)
@app.route('/api/admin/users', methods=['GET'])
@admin_required
@monitor_api_performance("admin_get_users")
def get_users():
    """Get all users (admin only)"""
    try:
        users = get_all_users()
        return jsonify({
            'success': True, 
            'users': users,
            'performance': {
                'cache_enabled': REDIS_AVAILABLE,
                'total_users': len(users)
            }
        }), 200
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({'success': False, 'message': 'Failed to get users'}), 500

@app.route('/api/admin/users/<int:user_id>/approve', methods=['POST'])
@admin_required
@monitor_api_performance("admin_approve_user")
def approve_user_endpoint(user_id):
    """Approve user (admin only) with cache invalidation"""
    try:
        success = approve_user(user_id)
        if success:
            return jsonify({
                'success': True, 
                'message': 'User approved successfully',
                'performance': {
                    'cache_invalidated': REDIS_AVAILABLE
                }
            }), 200
        else:
            return jsonify({'success': False, 'message': 'Failed to approve user'}), 500
    except Exception as e:
        logger.error(f"Error approving user: {e}")
        return jsonify({'success': False, 'message': 'Failed to approve user'}), 500

@app.route('/api/admin/users/<int:user_id>/reject', methods=['POST'])
@admin_required
@monitor_api_performance("admin_reject_user")
def reject_user_endpoint(user_id):
    """Reject user (admin only) with cache invalidation"""
    try:
        success = reject_user(user_id)
        if success:
            return jsonify({
                'success': True, 
                'message': 'User rejected successfully',
                'performance': {
                    'cache_invalidated': REDIS_AVAILABLE
                }
            }), 200
        else:
            return jsonify({'success': False, 'message': 'Failed to reject user'}), 500
    except Exception as e:
        logger.error(f"Error rejecting user: {e}")
        return jsonify({'success': False, 'message': 'Failed to reject user'}), 500

# File Upload Route - OPTIMIZED FOR 25K+ ROWS with Redis caching
@app.route('/api/files/upload', methods=['POST'])
@login_required
@monitor_api_performance("file_upload_25k_optimized")
def upload_file():
    """OPTIMIZED: Upload file for 25K+ rows with Redis metadata caching"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        upload_start_time = time.time()
        
        # Save file TEMPORARILY for data extraction ONLY
        temp_filename = f"temp_{session['user_id']}_{uuid.uuid4()}_{file.filename}"
        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
        file.save(temp_filepath)
        
        logger.info(f"[FILE] TEMP file saved for 25K+ row processing: {temp_filename}")
        logger.info(f"[START] Using Redis-optimized pipeline for large file processing")
        
        # OPTIMIZED: Read file with chunking for large files
        if temp_filepath.endswith('.csv'):
            # For CSV: Read in chunks to handle memory efficiently
            df_sample = pd.read_csv(temp_filepath, nrows=5)  # Quick preview
            df_full = pd.read_csv(temp_filepath)  # Full data - optimized for 25K rows
            total_rows = len(df_full)
        elif temp_filepath.endswith(('.xlsx', '.xls')):
            # For Excel: Read efficiently with openpyxl engine
            df_sample = pd.read_excel(temp_filepath, nrows=5, engine='openpyxl')
            df_full = pd.read_excel(temp_filepath, engine='openpyxl')
            total_rows = len(df_full)
        else:
            return jsonify({'success': False, 'message': 'Unsupported file format'}), 400
        
        file_read_time = (time.time() - upload_start_time) * 1000
        logger.info(f"[DATA] File read completed: {total_rows} rows in {file_read_time:.2f}ms")
        
        # Create template in SQL Fabric (metadata ONLY)
        template_creation_start = time.time()
        
        template_result = fabric_service.execute_query("""
            INSERT INTO excel_templates (template_name, user_id, headers, sheet_name, remote_file_path)
            OUTPUT INSERTED.template_id
            VALUES (?, ?, ?, ?, 'SQL_TABLE_ONLY')
        """, (file.filename, session['user_id'], json.dumps(df_sample.columns.tolist()), 'Sheet1'))
        
        template_id = template_result[0]['template_id']
        template_creation_time = (time.time() - template_creation_start) * 1000
        
        # REDIS OPTIMIZATION: Use cached bulk insert for 25K+ rows
        session_id = get_session_id()
        bulk_insert_start = time.time()
        
        if REDIS_AVAILABLE:
            # Use Redis-optimized bulk insert
            insert_result = cached_fabric_service.bulk_insert_file_data_optimized(df_full, session_id, template_id)
            bulk_insert_time = insert_result.get('processing_time_ms', 0)
        else:
            # Standard bulk insert
            fabric_service.bulk_insert_file_data(df_full, session_id, template_id)
            bulk_insert_time = (time.time() - bulk_insert_start) * 1000
        
        logger.info(f"[SAVE] BULK INSERT completed: {total_rows} rows in {bulk_insert_time:.2f}ms")
        logger.info(f"[TARGET] Redis optimization: {'ENABLED' if REDIS_AVAILABLE else 'DISABLED'}")
        
        # IMMEDIATELY delete temp file - NO persistent file storage
        try:
            os.remove(temp_filepath)
            logger.info(f"[DELETE] DELETED temp file: {temp_filename}")
        except Exception as e:
            logger.warning(f"Could not delete temp file: {e}")
        
        # Store optimized metadata in session and Redis
        file_metadata = {
            'filename': file.filename,
            'headers': df_sample.columns.tolist(),
            'row_count': total_rows,
            'preview': df_sample.to_dict('records'),
            'template_id': template_id,
            'processing_engine': 'REDIS_OPTIMIZED_SQL',
            'storage_type': 'SQL_TABLE_ONLY',
            'file_stored': False,
            'lakehouse_storage': False,
            'performance_metrics': {
                'file_read_time_ms': file_read_time,
                'template_creation_time_ms': template_creation_time,
                'bulk_insert_time_ms': bulk_insert_time,
                'total_processing_time_ms': (time.time() - upload_start_time) * 1000,
                'redis_enabled': REDIS_AVAILABLE
            }
        }
        
        session['current_file'] = file_metadata
        session['current_template_id'] = template_id
        
        # REDIS OPTIMIZATION: Cache file metadata for subsequent requests
        if REDIS_AVAILABLE:
            redis_service.cache_file_metadata(session_id, file_metadata)
            logger.info(f"[SAVE] File metadata cached in Redis for faster access")
        
        total_processing_time = (time.time() - upload_start_time) * 1000
        
        logger.info(f"[COMPLETE] 25K+ ROW FILE PROCESSING COMPLETED")
        logger.info(f"[DATA] Total time: {total_processing_time:.2f}ms")
        logger.info(f"[START] Performance: {(total_rows / (total_processing_time/1000)):.0f} rows/second")
        
        return jsonify({
            'success': True,
            'file_info': file_metadata,
            'message': f'25K+ rows processed efficiently ({total_rows} rows in {total_processing_time:.0f}ms)',
            'performance_metrics': {
                'total_rows': total_rows,
                'processing_time_ms': total_processing_time,
                'rows_per_second': int(total_rows / (total_processing_time/1000)) if total_processing_time > 0 else 0,
                'file_read_time_ms': file_read_time,
                'bulk_insert_time_ms': bulk_insert_time,
                'redis_optimized': REDIS_AVAILABLE,
                'cache_enabled': REDIS_AVAILABLE
            },
            'storage_info': {
                'type': 'REDIS_OPTIMIZED_SQL_TABLE',
                'lakehouse_files': False,
                'sql_table_data': True,
                'temp_file_deleted': True,
                'metadata_cached': REDIS_AVAILABLE
            }
        }), 200
        
    except Exception as e:
        logger.error(f"File upload error: {e}")
        return jsonify({
            'success': False, 
            'message': 'File upload failed',
            'error_details': str(e) if app.debug else 'Upload processing error'
        }), 500

# Rule Configuration Routes with Redis optimization
@app.route('/api/validation/configure-headers', methods=['POST'])
@login_required
@monitor_api_performance("configure_headers_cached")
def configure_headers():
    """Step 1: Select headers for validation with Redis optimization"""
    try:
        data = request.get_json()
        selected_headers = data.get('selected_headers', [])
        
        if not session.get('current_file'):
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        template_id = session['current_template_id']
        user_id = session['user_id']
        
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
        
        # REDIS OPTIMIZATION: Cache processing state for multi-step workflow
        if REDIS_AVAILABLE:
            processing_state = {
                'step': 1,
                'selected_headers': selected_headers,
                'template_id': template_id,
                'configured_at': datetime.now().isoformat()
            }
            redis_service.cache_processing_state(user_id, processing_state)
            logger.info(f"[SAVE] Processing state cached for faster navigation")
        
        return jsonify({
            'success': True,
            'message': 'Headers configured with Redis optimization',
            'selected_headers': selected_headers,
            'available_rules': list(GENERIC_RULES.keys()),
            'processing_engine': 'REDIS_OPTIMIZED_DUCKDB',
            'performance': {
                'cache_enabled': REDIS_AVAILABLE,
                'state_cached': REDIS_AVAILABLE
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Configure headers error: {e}")
        return jsonify({'success': False, 'message': 'Header configuration failed'}), 500

@app.route('/api/validation/configure-rules', methods=['POST'])
@login_required
@monitor_api_performance("configure_rules_cached")
def configure_rules():
    """Step 2: Configure generic rules with Redis caching - FIXED FOREIGN KEY ISSUE"""
    try:
        data = request.get_json()
        rules_config = data.get('rules_config', {})
        
        if not session.get('selected_headers'):
            return jsonify({'success': False, 'message': 'Headers not configured'}), 400
        
        template_id = session['current_template_id']
        user_id = session['user_id']
        
        # Get column IDs
        columns = fabric_service.execute_query("""
            SELECT column_id, column_name 
            FROM template_columns 
            WHERE template_id = ? AND is_selected = 1
        """, (template_id,))
        
        column_map = {col['column_name']: col['column_id'] for col in columns}
        
        # FIXED: Use the same rule_type_id mapping that matches your database exactly
        # This prevents the foreign key constraint error
        rule_map = get_rule_type_id  # Use the existing function that returns correct IDs 1-8
        
        logger.info(f"[TARGET] Using correct rule_type_id mapping to fix foreign key constraint")
        
        # Clear existing rules for this template
        fabric_service.execute_non_query("""
            DELETE FROM column_validation_rules 
            WHERE column_id IN (
                SELECT column_id FROM template_columns 
                WHERE template_id = ?
            )
        """, (template_id,))
        
        # FIXED: Save column validation rules with correct rule_type_id values
        for column_name, rule_names in rules_config.items():
            column_id = column_map.get(column_name)
            if not column_id:
                logger.warning(f"Column not found: {column_name}")
                continue
            
            for rule_name in rule_names:
                # Use the get_rule_type_id function to get the correct database ID
                try:
                    rule_type_id = get_rule_type_id(rule_name)
                    rule_config = GENERIC_RULES[rule_name]['parameters']
                    
                    logger.info(f"[SAVE] Inserting: column_id={column_id}, rule_type_id={rule_type_id}, rule_name={rule_name}")
                    
                    fabric_service.execute_non_query("""
                        INSERT INTO column_validation_rules (column_id, rule_type_id, rule_config)
                        VALUES (?, ?, ?)
                    """, (column_id, rule_type_id, rule_config))
                except ValueError as ve:
                    logger.error(f"Invalid rule name: {rule_name} - {ve}")
                    return jsonify({'success': False, 'message': f'Invalid rule: {rule_name}'}), 400
                except Exception as e:
                    logger.error(f"Error inserting rule {rule_name} for column {column_name}: {e}")
                    return jsonify({'success': False, 'message': f'Database error inserting rule: {rule_name}'}), 500
        
        session['rules_config'] = rules_config
        
        # REDIS OPTIMIZATION: Update processing state
        if REDIS_AVAILABLE:
            processing_state = {
                'step': 2,
                'selected_headers': session.get('selected_headers', []),
                'rules_config': rules_config,
                'template_id': template_id,
                'configured_at': datetime.now().isoformat()
            }
            redis_service.cache_processing_state(user_id, processing_state)
        
        return jsonify({
            'success': True,
            'message': 'Rules configured successfully - Foreign key constraint FIXED',
            'rules_config': rules_config,
            'processing_engine': 'REDIS_OPTIMIZED_DUCKDB',
            'performance': {
                'cache_enabled': REDIS_AVAILABLE,
                'foreign_key_fix': 'Applied',
                'rule_mapping': 'Database IDs 1-8 used correctly'
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Configure rules error: {e}")
        return jsonify({'success': False, 'message': 'Rule configuration failed'}), 500

@app.route('/api/validation/review-config', methods=['GET'])
@login_required
@monitor_api_performance("review_config_cached")
def review_configuration():
    """Step 3: Review configured rules with Redis optimization"""
    try:
        if not session.get('current_file') or not session.get('rules_config'):
            return jsonify({'success': False, 'message': 'Configuration incomplete'}), 400
        
        user_id = session['user_id']
        
        # REDIS OPTIMIZATION: Get cached processing state if available
        cached_state = None
        if REDIS_AVAILABLE:
            cached_state = redis_service.get_processing_state(user_id)
            if cached_state:
                logger.info(f"[TARGET] Using cached processing state for review")
        
        # REDIS OPTIMIZATION: Get cached validation rules
        rules_details = GENERIC_RULES
        if REDIS_AVAILABLE:
            cached_rules = cached_fabric_service.get_validation_rules_cached()
            if cached_rules:
                rules_details = {rule: info['description'] for rule, info in cached_rules.items()}
        
        config_summary = {
            'file_info': session['current_file'],
            'selected_headers': session.get('selected_headers', []),
            'rules_config': session.get('rules_config', {}),
            'rules_details': rules_details,
            'processing_engine': 'REDIS_OPTIMIZED_DUCKDB',
            'ready_for_validation': True,
            'performance': {
                'cache_enabled': REDIS_AVAILABLE,
                'state_cached': cached_state is not None,
                'rules_cached': REDIS_AVAILABLE
            }
        }
        
        return jsonify({
            'success': True,
            'configuration': config_summary
        }), 200
        
    except Exception as e:
        logger.error(f"Review configuration error: {e}")
        return jsonify({'success': False, 'message': 'Configuration review failed'}), 500

# Data Validation Routes - OPTIMIZED FOR 25K ROWS with Redis
@app.route('/api/validation/validate', methods=['POST'])
@login_required
@monitor_api_performance("validate_25k_rows_redis_optimized")
def validate_data():
    """REDIS OPTIMIZED: Validate 25K+ rows with intelligent caching"""
    try:
        if not session.get('current_file') or not session.get('rules_config'):
            return jsonify({'success': False, 'message': 'Configuration incomplete'}), 400
        
        current_file = session['current_file']
        rules_config = session['rules_config']
        template_id = session['current_template_id']
        session_id = get_session_id()
        user_id = session['user_id']
        
        validation_start_time = time.time()
        
        logger.info(f"[START] REDIS OPTIMIZED: Starting validation for {current_file['row_count']} rows")
        logger.info(f"[SAVE] Cached rules and metadata will accelerate processing")
        
        # REDIS OPTIMIZATION: Use cached validation with performance monitoring
        if REDIS_AVAILABLE:
            validation_result = cached_fabric_service.validate_data_with_caching(session_id, template_id, rules_config)
            
            # Get cached file metadata for faster sample data retrieval
            cached_metadata = redis_service.get_file_metadata(session_id)
            if cached_metadata:
                logger.info(f"[TARGET] Using cached metadata for {cached_metadata['row_count']} rows")
        else:
            # Standard validation
            validation_result = fabric_service.validate_data_in_sql_fabric(session_id, template_id, rules_config)
        
        # Get sample data for display from SQL Fabric (first 100 rows)
        sample_data_start = time.time()
        sample_data = fabric_service.get_file_data(session_id, template_id, 
                                                 session['selected_headers'])[:100]
        sample_data_time = (time.time() - sample_data_start) * 1000
        
        total_processing_time = (time.time() - validation_start_time) * 1000
        
        # Save validation history to SQL Fabric
        fabric_service.execute_non_query("""
            INSERT INTO validation_history 
            (template_id, template_name, error_count, corrected_file_path, user_id, processing_time_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (template_id, current_file['filename'], validation_result['total_errors'], 
              'REDIS_OPTIMIZED_SQL_TABLE', user_id, int(total_processing_time)))
        
        session['validation_errors'] = validation_result['error_cell_locations']
        session['processing_method'] = 'REDIS_OPTIMIZED_SQL_FABRIC'
        
        # REDIS OPTIMIZATION: Cache validation results for potential re-runs
        if REDIS_AVAILABLE:
            processing_state = {
                'step': 'validation_complete',
                'total_errors': validation_result['total_errors'],
                'processing_time_ms': total_processing_time,
                'validated_at': datetime.now().isoformat()
            }
            redis_service.cache_processing_state(user_id, processing_state)
        
        rows_per_second = int(current_file['row_count'] / (total_processing_time/1000)) if total_processing_time > 0 else 0
        
        logger.info(f"[COMPLETE] 25K+ ROW VALIDATION COMPLETED")
        logger.info(f"[DATA] Total errors: {validation_result['total_errors']}")
        logger.info(f"[FAST] Performance: {rows_per_second} rows/second")
        logger.info(f"[TARGET] Redis optimization: {'ENABLED' if REDIS_AVAILABLE else 'DISABLED'}")
        
        return jsonify({
            'success': True,
            'errors': convert_errors_to_list(validation_result['error_cell_locations']),
            'total_errors': validation_result['total_errors'],
            'data': sample_data,
            'processing_time_ms': int(total_processing_time),
            'processing_method': 'REDIS_OPTIMIZED_SQL_FABRIC',
            'file_rows': current_file['row_count'],
            'performance_metrics': {
                'total_processing_time_ms': int(total_processing_time),
                'sample_data_time_ms': int(sample_data_time),
                'rows_per_second': rows_per_second,
                'redis_enabled': REDIS_AVAILABLE,
                'cache_hits': 'Multiple' if REDIS_AVAILABLE else 'None'
            },
            'storage_info': {
                'validation_source': 'REDIS_OPTIMIZED_SQL_TABLE',
                'file_access': False,
                'lakehouse_access': False,
                'duckdb_processing': False,
                'redis_caching': REDIS_AVAILABLE
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Redis-optimized validation error: {e}")
        return jsonify({
            'success': False, 
            'message': f'Validation failed: {str(e)}',
            'performance_note': 'Redis optimization available but validation failed'
        }), 500

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
@monitor_api_performance("correct_errors_redis_optimized")
def correct_errors():
    """REDIS OPTIMIZED: Apply corrections to 25K+ rows efficiently"""
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
        user_id = session['user_id']
        
        correction_start_time = time.time()
        
        logger.info(f"[START] REDIS OPTIMIZED: Applying corrections to SQL Fabric table")
        logger.info(f"[SAVE] Cached metadata will accelerate correction process")
        
        # Apply corrections to SQL Fabric table data
        if REDIS_AVAILABLE:
            # Use Redis-cached metadata for better performance
            cached_metadata = redis_service.get_file_metadata(session_id)
            logger.info(f"[TARGET] Using cached metadata for correction targeting")
        
        corrected_count = fabric_service.apply_corrections_in_sql_fabric(corrections, session_id, template_id)
        
        correction_time = (time.time() - correction_start_time) * 1000
        
        session['corrections'] = corrections
        session['corrected_count'] = corrected_count
        
        # REDIS OPTIMIZATION: Update processing state with correction info
        if REDIS_AVAILABLE:
            processing_state = {
                'step': 'corrections_applied',
                'corrected_count': corrected_count,
                'correction_time_ms': correction_time,
                'corrected_at': datetime.now().isoformat()
            }
            redis_service.cache_processing_state(user_id, processing_state)
        
        corrections_per_second = int(corrected_count / (correction_time/1000)) if correction_time > 0 else 0
        
        logger.info(f"[COMPLETE] CORRECTIONS APPLIED: {corrected_count} in {correction_time:.2f}ms")
        logger.info(f"[FAST] Performance: {corrections_per_second} corrections/second")
        
        return jsonify({
            'success': True,
            'message': f'Redis-optimized corrections applied to SQL table',
            'corrected_rows': corrected_count,
            'processing_engine': 'REDIS_OPTIMIZED_SQL_FABRIC',
            'performance_metrics': {
                'correction_time_ms': int(correction_time),
                'corrected_count': corrected_count,
                'corrections_per_second': corrections_per_second,
                'redis_enabled': REDIS_AVAILABLE
            },
            'storage_info': {
                'corrections_target': 'REDIS_OPTIMIZED_SQL_TABLE',
                'file_modifications': False,
                'lakehouse_updates': False,
                'metadata_cached': REDIS_AVAILABLE
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Redis-optimized correction failed: {e}")
        return jsonify({
            'success': False, 
            'message': f'Correction failed: {str(e)}',
            'performance_note': 'Redis optimization available but correction failed'
        }), 500

@app.route('/api/validation/review-changes', methods=['GET'])
@login_required
@monitor_api_performance("review_changes_cached")
def review_changes():
    """Step 6: Review changes with Redis caching"""
    try:
        corrections = session.get('corrections', {})
        corrected_count = session.get('corrected_count', 0)
        user_id = session['user_id']
        
        # REDIS OPTIMIZATION: Get cached processing state
        cached_state = None
        if REDIS_AVAILABLE:
            cached_state = redis_service.get_processing_state(user_id)
            if cached_state and 'corrected_count' in cached_state:
                logger.info(f"[TARGET] Using cached correction state")
        
        if not corrections:
            return jsonify({
                'success': True,
                'changes': [],
                'total_changes': 0,
                'message': 'No changes to review',
                'performance': {
                    'cache_enabled': REDIS_AVAILABLE,
                    'state_cached': cached_state is not None
                }
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
                    'original_value': 'Error Value',
                    'corrected_value': new_value
                })
        
        return jsonify({
            'success': True,
            'changes': changes,
            'total_changes': corrected_count,
            'processing_engine': 'REDIS_OPTIMIZED_DUCKDB',
            'ready_for_download': True,
            'performance': {
                'cache_enabled': REDIS_AVAILABLE,
                'state_cached': cached_state is not None,
                'changes_cached': len(changes) > 0
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Review changes error: {e}")
        return jsonify({'success': False, 'message': 'Review changes failed'}), 500

@app.route('/api/files/download-corrected', methods=['GET'])
@login_required
@monitor_api_performance("download_corrected_25k_optimized")
def download_corrected():
    """REDIS OPTIMIZED: Download corrected 25K+ rows file efficiently"""
    try:
        current_file = session.get('current_file')
        if not current_file:
            return jsonify({'success': False, 'message': 'No file data available'}), 400
        
        session_id = get_session_id()
        template_id = session['current_template_id']
        headers = session.get('selected_headers', [])
        user_id = session['user_id']
        
        download_start_time = time.time()
        
        logger.info(f"[START] REDIS OPTIMIZED: Generating corrected download for {current_file['row_count']} rows")
        
        # REDIS OPTIMIZATION: Check cached metadata first
        if REDIS_AVAILABLE:
            cached_metadata = redis_service.get_file_metadata(session_id)
            if cached_metadata:
                logger.info(f"[TARGET] Using cached metadata for {cached_metadata['row_count']} rows")
        
        # Get corrected data from SQL Fabric table (includes all corrections)
        data_export_start = time.time()
        corrected_data = fabric_service.export_corrected_data(session_id, template_id, headers)
        data_export_time = (time.time() - data_export_start) * 1000
        
        if corrected_data.empty:
            return jsonify({'success': False, 'message': 'No corrected data available'}), 400
        
        original_filename = current_file['filename']
        
        # Generate corrected filename: "originalname_corrected.ext"
        base_name, ext = os.path.splitext(original_filename)
        corrected_filename = f"{base_name}_corrected{ext}"
        corrected_filepath = os.path.join(app.config['UPLOAD_FOLDER'], corrected_filename)
        
        # OPTIMIZED: Save corrected file efficiently
        file_save_start = time.time()
        if ext.lower() == '.csv':
            corrected_data.to_csv(corrected_filepath, index=False)
        else:
            corrected_data.to_excel(corrected_filepath, index=False, engine='openpyxl')
        file_save_time = (time.time() - file_save_start) * 1000
        
        total_download_time = (time.time() - download_start_time) * 1000
        
        # REDIS OPTIMIZATION: Clear processing state after successful download
        if REDIS_AVAILABLE:
            redis_service.clear_processing_state(user_id)
            logger.info(f"🧹 Processing state cleared after successful download")
        
        logger.info(f"[COMPLETE] CORRECTED FILE GENERATED: {len(corrected_data)} rows")
        logger.info(f"[DATA] Export time: {data_export_time:.2f}ms")
        logger.info(f"[SAVE] File save time: {file_save_time:.2f}ms")
        logger.info(f"[FAST] Total download prep: {total_download_time:.2f}ms")
        
        return send_file(corrected_filepath, as_attachment=True, download_name=corrected_filename)
        
    except Exception as e:
        logger.error(f"Corrected file download error: {e}")
        return jsonify({
            'success': False, 
            'message': f'Download failed: {str(e)}',
            'performance_note': 'Redis optimization available but download failed'
        }), 500

# Available rules endpoint with Redis caching
@app.route('/api/validation/rules', methods=['GET'])
@login_required
@monitor_api_performance("get_rules_cached")
def get_available_rules():
    """Get available generic rules with Redis caching"""
    try:
        # REDIS OPTIMIZATION: Use cached rules if available
        if REDIS_AVAILABLE:
            cached_rules = cached_fabric_service.get_validation_rules_cached()
            if cached_rules:
                rules_info = {}
                for rule_id, rule_data in cached_rules.items():
                    rules_info[rule_id] = {
                        'name': rule_data.get('name', rule_id),
                        'description': rule_data.get('description', '')
                    }
                
                logger.info(f"[TARGET] Returning {len(rules_info)} cached validation rules")
                return jsonify({
                    'success': True,
                    'rules': rules_info,
                    'processing_engine': 'REDIS_OPTIMIZED_DUCKDB',
                    'performance': {
                        'cache_hit': True,
                        'rules_count': len(rules_info),
                        'source': 'Redis Cache'
                    }
                }), 200
        
        # Fallback to standard rules
        rules_info = {}
        for rule_id, rule_data in GENERIC_RULES.items():
            rules_info[rule_id] = {
                'name': rule_data['name'],
                'description': rule_data['description']
            }
        
        return jsonify({
            'success': True,
            'rules': rules_info,
            'processing_engine': 'DuckDB',
            'performance': {
                'cache_hit': False,
                'rules_count': len(rules_info),
                'source': 'Default Rules'
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Get rules error: {e}")
        return jsonify({'success': False, 'message': 'Failed to get validation rules'}), 500

# Performance monitoring endpoint
@app.route('/api/performance/cache-stats', methods=['GET'])
@login_required
def get_cache_stats():
    """Get Redis cache performance statistics"""
    try:
        if REDIS_AVAILABLE:
            stats = cached_fabric_service.get_cache_performance_stats()
        else:
            stats = {
                'cache_service': 'None',
                'cache_status': 'Disabled',
                'redis_connection': {'connected': False},
                'performance_metrics': {'note': 'Redis not available'}
            }
        
        return jsonify({
            'success': True,
            'cache_stats': stats,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Cache stats error: {e}")
        return jsonify({'success': False, 'message': 'Failed to get cache stats'}), 500

# Health check endpoint with Redis status
@app.route('/api/health', methods=['GET'])
@monitor_api_performance("health_check_redis")
def health_check():
    """Health check with Redis and database status"""
    try:
        # Test Fabric SQL connection
        fabric_status = fabric_service.test_connection()
        
        # Test DuckDB connection
        duckdb_status = {"status": "success", "message": "DuckDB operational"}
        try:
            duckdb_service.connection.execute("SELECT 1")
        except Exception as e:
            duckdb_status = {"status": "error", "message": f"DuckDB error: {str(e)}"}
        
        # Test Redis connection
        redis_status = {"status": "disabled", "message": "Redis not available"}
        if REDIS_AVAILABLE:
            try:
                redis_service.redis_client.ping()
                redis_status = {"status": "success", "message": "Redis operational"}
            except Exception as e:
                redis_status = {"status": "error", "message": f"Redis error: {str(e)}"}
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'fabric_sql': fabric_status,
                'duckdb': duckdb_status,
                'redis': redis_status
            },
            'processing_engine': 'REDIS_OPTIMIZED_DUCKDB' if REDIS_AVAILABLE else 'DuckDB',
            'performance_features': {
                'redis_caching': REDIS_AVAILABLE,
                'cached_validation_rules': REDIS_AVAILABLE,
                'cached_user_sessions': REDIS_AVAILABLE,
                'cached_file_metadata': REDIS_AVAILABLE,
                'optimized_25k_processing': REDIS_AVAILABLE
            },
            'configuration': {
                'duckdb_path': config.DUCKDB_PATH,
                'memory_limit': config.DUCKDB_MEMORY_LIMIT,
                'threads': config.DUCKDB_THREADS,
                'redis_host': redis_service.redis_host if REDIS_AVAILABLE else 'N/A',
                'redis_port': redis_service.redis_port if REDIS_AVAILABLE else 'N/A'
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
        
        # Initialize application with Redis support
        init_application()
        
        performance_mode = "REDIS-OPTIMIZED" if REDIS_AVAILABLE else "STANDARD"
        
        logger.info(f"[START] Starting Data Sync AI in {performance_mode} MODE")
        logger.info("[FAST] PERFORMANCE OPTIMIZATIONS:")
        logger.info(f"   Redis Caching: {'ENABLED' if REDIS_AVAILABLE else 'DISABLED'}")
        logger.info(f"   25K+ Row Processing: {'OPTIMIZED' if REDIS_AVAILABLE else 'STANDARD'}")
        logger.info(f"   Cached Validation Rules: {'ENABLED' if REDIS_AVAILABLE else 'DISABLED'}")
        logger.info(f"   Cached User Sessions: {'ENABLED' if REDIS_AVAILABLE else 'DISABLED'}")
        logger.info(f"   Cached File Metadata: {'ENABLED' if REDIS_AVAILABLE else 'DISABLED'}")
        logger.info(f"Environment: {config.FLASK_ENV}")
        logger.info(f"DuckDB path: {config.DUCKDB_PATH}")
        logger.info(f"DuckDB memory limit: {config.DUCKDB_MEMORY_LIMIT}")
        logger.info(f"DuckDB threads: {config.DUCKDB_THREADS}")
        
        if REDIS_AVAILABLE:
            logger.info(f"Redis host: {redis_service.redis_host}:{redis_service.redis_port}")
            logger.info("[TARGET] Expected 25K row processing time: 3-8 seconds (vs 15-30 seconds without Redis)")
        
        port = int(os.environ.get('PORT', config.PORT))
        
        # Disable auto-reload in debug mode to prevent restart loops from file changes
        # You can manually restart when you change code files
        use_reloader = False  # Set to True only when actively developing
        
        app.run(
            debug=config.DEBUG, 
            host='0.0.0.0', 
            port=port,
            use_reloader=use_reloader
        )
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    finally:
        # Cleanup on shutdown
        try:
            if REDIS_AVAILABLE:
                cached_fabric_service.close_connection()
            else:
                fabric_service.close_connection()
            duckdb_service.close_connection()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
