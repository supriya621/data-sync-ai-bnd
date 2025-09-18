"""
Data Sync AI - SQL Fabric Edition
All persistent data stored in Microsoft SQL Fabric, DuckDB used only for large file processing
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

# SQL FABRIC PRIORITY - All persistent data goes to SQL Fabric
SQL_FABRIC_AVAILABLE = False

def initialize_application():
    """Initialize the application and ensure SQL Fabric is ready"""
    global SQL_FABRIC_AVAILABLE
    
    logger.info("Initializing Data Sync AI with SQL Fabric storage...")
    
    try:
        # Test SQL Fabric connection
        fabric_test = fabric_service.test_connection()
        if fabric_test['status'] == 'success':
            logger.info("✅ SQL Fabric connection successful")
            
            # Initialize database tables
            fabric_service.init_database()
            fabric_service.create_default_rules()
            
            SQL_FABRIC_AVAILABLE = True
            logger.info("✅ SQL Fabric database initialized and ready")
            
        else:
            logger.error(f"❌ SQL Fabric connection failed: {fabric_test['message']}")
            logger.error("Application will not start without SQL Fabric connectivity")
            raise Exception("SQL Fabric connection required")
            
    except Exception as e:
        logger.error(f"Failed to initialize SQL Fabric: {str(e)}")
        raise
    
    try:
        # Initialize DuckDB for temporary processing only
        duckdb_service.initialize_for_processing()
        logger.info("✅ DuckDB ready for large file processing")
        
    except Exception as e:
        logger.warning(f"DuckDB initialization warning (will use fallback): {str(e)}")

# ========================
# AUTHENTICATION ENDPOINTS - ALL DATA IN SQL FABRIC
# ========================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration - stores in SQL Fabric"""
    try:
        if not SQL_FABRIC_AVAILABLE:
            return jsonify({'success': False, 'message': 'SQL Fabric not available'}), 500
            
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'email', 'mobile', 'password']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        # Check if user already exists in SQL Fabric
        existing_user = fabric_service.get_user_by_email(data['email'])
        if existing_user:
            return jsonify({'success': False, 'message': 'User already exists'}), 400
        
        # Hash password
        hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Prepare user data for SQL Fabric
        user_data = {
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'email': data['email'],
            'mobile': data['mobile'],
            'password': hashed_password
        }
        
        # Create user in SQL Fabric
        user_id = fabric_service.create_user(user_data)
        
        logger.info(f"User registered successfully in SQL Fabric: {data['email']} (ID: {user_id})")
        return jsonify({'success': True, 'message': 'Registration successful, awaiting approval'}), 201
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'success': False, 'message': 'Registration failed'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login - authenticates against SQL Fabric"""
    try:
        if not SQL_FABRIC_AVAILABLE:
            return jsonify({'success': False, 'message': 'SQL Fabric not available'}), 500
            
        data = request.get_json()
        email = data.get('email') or data.get('username')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password required'}), 400
        
        # Get user from SQL Fabric
        user = fabric_service.get_user_by_email(email)
        if not user:
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        # Verify password
        if not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        # Create session
        session['user_id'] = user['id']
        session['email'] = user['email']
        session['first_name'] = user['first_name']
        session['last_name'] = user['last_name']
        session['logged_in'] = True
        
        logger.info(f"User logged in successfully: {email}")
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'email': user['email'],
                'first_name': user['first_name'],
                'last_name': user['last_name']
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'success': False, 'message': 'Login failed'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """User logout - clears session"""
    try:
        session.clear()
        return jsonify({'success': True, 'message': 'Logged out successfully'}), 200
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({'success': False, 'message': 'Logout failed'}), 500

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    """Check authentication status"""
    try:
        if session.get('logged_in') and session.get('user_id'):
            return jsonify({
                'success': True,
                'user': {
                    'id': session.get('user_id'),
                    'email': session.get('email'),
                    'first_name': session.get('first_name'),
                    'last_name': session.get('last_name')
                }
            }), 200
        else:
            return jsonify({'success': False, 'message': 'Not authenticated'}), 401
            
    except Exception as e:
        logger.error(f"Auth check error: {str(e)}")
        return jsonify({'success': False, 'message': 'Authentication check failed'}), 500

# ========================
# FILE UPLOAD AND PROCESSING - DUCKDB FOR PROCESSING, FABRIC FOR STORAGE
# ========================

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload and process file - DuckDB for processing, SQL Fabric for results"""
    try:
        if not session.get('logged_in'):
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
            
        if not SQL_FABRIC_AVAILABLE:
            return jsonify({'success': False, 'message': 'SQL Fabric not available'}), 500
            
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file provided'}), 400
        
        file = request.files['file']
        if not file.filename:
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        # Save uploaded file
        filename = f"{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join(config.UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        try:
            # Process file with DuckDB for performance
            if filepath.endswith('.csv'):
                df = pd.read_csv(filepath)
            elif filepath.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(filepath)
            else:
                return jsonify({'success': False, 'message': 'Unsupported file format'}), 400
            
            # Store file data temporarily in DuckDB for processing
            session_id = str(uuid.uuid4())
            template_id = duckdb_service.store_file_data(df, session_id)
            
            # Store template metadata in SQL Fabric
            template_data = {
                'template_name': file.filename,
                'user_id': session['user_id'],
                'sheet_name': 'Sheet1',
                'headers': json.dumps(df.columns.tolist()),
                'status': 'ACTIVE'
            }
            
            # Create template in SQL Fabric
            fabric_template_id = fabric_service.create_template(template_data)
            
            # Store session metadata
            session['current_file'] = {
                'filename': file.filename,
                'filepath': filepath,
                'template_id': fabric_template_id,
                'duckdb_session_id': session_id,
                'headers': df.columns.tolist(),
                'row_count': len(df),
                'uploaded_at': datetime.now().isoformat()
            }
            
            logger.info(f"File processed: {file.filename} ({len(df)} rows) - Template ID: {fabric_template_id}")
            
            return jsonify({
                'success': True,
                'message': 'File uploaded and processed successfully',
                'file_info': {
                    'filename': file.filename,
                    'headers': df.columns.tolist(),
                    'row_count': len(df),
                    'template_id': fabric_template_id
                }
            }), 200
            
        finally:
            # Clean up uploaded file
            if os.path.exists(filepath):
                os.remove(filepath)
                
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        return jsonify({'success': False, 'message': f'Upload failed: {str(e)}'}), 500

# ========================
# DATA VALIDATION - FABRIC FOR RULES, DUCKDB FOR PROCESSING
# ========================

@app.route('/api/validation-rules', methods=['GET'])
def get_validation_rules():
    """Get available validation rules from SQL Fabric"""
    try:
        if not SQL_FABRIC_AVAILABLE:
            return jsonify({'success': False, 'message': 'SQL Fabric not available'}), 500
            
        rules = fabric_service.get_validation_rules()
        return jsonify({'success': True, 'rules': rules}), 200
        
    except Exception as e:
        logger.error(f"Error getting validation rules: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to get validation rules'}), 500

@app.route('/api/validate', methods=['POST'])
def validate_data():
    """Validate data using DuckDB processing and store results in SQL Fabric"""
    try:
        if not session.get('logged_in'):
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
            
        if not SQL_FABRIC_AVAILABLE:
            return jsonify({'success': False, 'message': 'SQL Fabric not available'}), 500
            
        data = request.get_json()
        validation_rules = data.get('validation_rules', {})
        
        current_file = session.get('current_file')
        if not current_file:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        # Process validation using DuckDB for performance
        validation_results = duckdb_service.validate_data(
            current_file['duckdb_session_id'],
            current_file['template_id'],
            validation_rules
        )
        
        # Store validation results in SQL Fabric
        history_data = {
            'template_id': current_file['template_id'],
            'template_name': current_file['filename'],
            'error_count': len(validation_results.get('errors', [])),
            'user_id': session['user_id'],
            'processing_time_ms': validation_results.get('processing_time', 0),
            'file_size_mb': validation_results.get('file_size_mb', 0)
        }
        
        history_id = fabric_service.store_validation_history(history_data)
        
        # Store individual corrections in SQL Fabric
        if validation_results.get('errors'):
            fabric_service.store_validation_corrections(history_id, validation_results['errors'])
        
        logger.info(f"Validation completed: {len(validation_results.get('errors', []))} errors found")
        
        return jsonify({
            'success': True,
            'validation_results': validation_results,
            'history_id': history_id
        }), 200
        
    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({'success': False, 'message': f'Validation failed: {str(e)}'}), 500

# ========================
# HEALTH CHECK AND STATUS
# ========================

@app.route('/api/health', methods=['GET'])
def health_check():
    """System health check"""
    try:
        fabric_status = fabric_service.test_connection()
        duckdb_status = duckdb_service.test_connection() if hasattr(duckdb_service, 'test_connection') else {'status': 'available'}
        
        return jsonify({
            'status': 'healthy',
            'sql_fabric': fabric_status,
            'duckdb': duckdb_status,
            'data_storage': 'SQL Fabric (Primary)',
            'file_processing': 'DuckDB (Performance)',
            'version': '2.0 - SQL Fabric Edition'
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
# APPLICATION STARTUP
# ========================

if __name__ == '__main__':
    try:
        # Initialize application with SQL Fabric
        initialize_application()
        
        if not SQL_FABRIC_AVAILABLE:
            logger.error("❌ Cannot start application - SQL Fabric not available")
            logger.error("Please run: python init_fabric.py")
            sys.exit(1)
        
        logger.info("🚀 Starting Data Sync AI - SQL Fabric Edition")
        logger.info("✅ All persistent data will be stored in SQL Fabric")
        logger.info("✅ DuckDB will handle large file processing")
        logger.info(f"Environment: {config.FLASK_ENV}")
        logger.info(f"Server: {config.FABRIC_SERVER}")
        logger.info(f"Database: {config.FABRIC_DATABASE}")
        
        port = int(os.environ.get('PORT', config.PORT))
        app.run(debug=config.DEBUG, host='0.0.0.0', port=port)
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        print(f"\n❌ Application startup failed: {e}")
        print("\nPlease ensure SQL Fabric is properly configured and run:")
        print("  python init_fabric.py")
        sys.exit(1)
        
    finally:
        # Cleanup on shutdown
        try:
            fabric_service.close_connection()
            duckdb_service.close_connection()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
