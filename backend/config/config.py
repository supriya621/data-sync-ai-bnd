import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

class Config:
    """Application configuration class"""
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    FLASK_ENV = os.environ.get('FLASK_ENV') or 'development'
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    PORT = int(os.environ.get('FLASK_PORT', 5000))
    
    # Microsoft Fabric SQL Configuration
    AZURE_CLIENT_ID = os.environ.get('AZURE_CLIENT_ID')
    AZURE_TENANT_ID = os.environ.get('AZURE_TENANT_ID')
    AZURE_CLIENT_SECRET = os.environ.get('AZURE_CLIENT_SECRET')
    FABRIC_SERVER = os.environ.get('FABRIC_SERVER')
    FABRIC_DATABASE = os.environ.get('FABRIC_DATABASE')
    
    # DuckDB Configuration
    DUCKDB_PATH = os.environ.get('DUCKDB_PATH', './data/datasync.duckdb')
    DUCKDB_MEMORY_LIMIT = os.environ.get('DUCKDB_MEMORY_LIMIT', '4GB')
    DUCKDB_THREADS = int(os.environ.get('DUCKDB_THREADS', '4'))
    
    # File Processing Configuration
    MAX_FILE_SIZE_MB = int(os.environ.get('MAX_FILE_SIZE_MB', '100'))
    LARGE_FILE_THRESHOLD = int(os.environ.get('LARGE_FILE_THRESHOLD', '100'))  # rows
    CHUNK_SIZE = int(os.environ.get('CHUNK_SIZE', '1000'))  # for processing large files
    
    # Upload Configuration
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', './uploads')
    SESSION_FILE_DIR = os.environ.get('SESSION_FILE_DIR', './sessions')
    
    # CORS Configuration
    ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
    
    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', './logs/datasync.log')
    
    @classmethod
    def validate_config(cls):
        """Validate required configuration values"""
        required_vars = [
            'AZURE_CLIENT_ID',
            'AZURE_TENANT_ID', 
            'AZURE_CLIENT_SECRET',
            'FABRIC_SERVER',
            'FABRIC_DATABASE'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True
    
    @classmethod
    def get_fabric_connection_string(cls):
        """Generate Fabric SQL connection string for access token authentication"""
        return (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={cls.FABRIC_SERVER};"
            f"DATABASE={cls.FABRIC_DATABASE};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
            f"Connection Timeout=30;"
        )
    
    @classmethod
    def setup_logging(cls):
        """Setup application logging"""
        os.makedirs(os.path.dirname(cls.LOG_FILE), exist_ok=True)
        
        logging.basicConfig(
            level=getattr(logging, cls.LOG_LEVEL.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(cls.LOG_FILE),
                logging.StreamHandler()
            ]
        )

# Initialize configuration
config = Config()
