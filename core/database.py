"""
Database initialization and management
"""

import logging
from services.fabric_service import fabric_service
from services.duckdb_service import duckdb_service

logger = logging.getLogger(__name__)

def init_database():
    """Initialize all database connections and schemas"""
    try:
        logger.info("Initializing databases...")
        
        # Validate configuration
        from config.config import config
        config.validate_config()
        
        # Initialize Fabric SQL
        logger.info("Setting up Fabric SQL database...")
        fabric_service.init_database()
        fabric_service.create_default_rules()
        
        # Create admin user if it doesn't exist
        create_admin_user()
        
        # Initialize DuckDB (already done in service constructor)
        logger.info("DuckDB initialized")
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

def create_admin_user():
    """Create default admin user"""
    try:
        import bcrypt
        
        # Check if admin user exists
        admin_user = fabric_service.get_user_by_email('admin@example.com')
        
        if not admin_user:
            admin_password = bcrypt.hashpw('admin'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            fabric_service.create_user({
                'first_name': 'Admin',
                'last_name': 'User',
                'email': 'admin@example.com',
                'mobile': '1234567890',
                'password': admin_password
            })
            logger.info("Default admin user created")
        else:
            logger.info("Admin user already exists")
            
    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")
        raise

def get_database_status():
    """Get status of all database connections"""
    status = {
        'fabric_sql': fabric_service.test_connection(),
        'duckdb': {'status': 'active', 'message': 'DuckDB connection active'}
    }
    return status
