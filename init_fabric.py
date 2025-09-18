"""
SQL Fabric Database Initialization Script
This script initializes your SQL Fabric database with all required tables and data.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# Import services
from backend.config.config import config
from backend.services.fabric_service import fabric_service

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_fabric_connection():
    """Test SQL Fabric connection"""
    logger.info("Testing SQL Fabric connection...")
    result = fabric_service.test_connection()
    
    if result['status'] == 'success':
        logger.info("✅ SQL Fabric connection successful!")
        return True
    else:
        logger.error(f"❌ SQL Fabric connection failed: {result['message']}")
        return False

def initialize_fabric_database():
    """Initialize SQL Fabric database with all required tables"""
    try:
        logger.info("Initializing SQL Fabric database schema...")
        
        # Initialize database tables
        fabric_service.init_database()
        logger.info("✅ Database tables created successfully!")
        
        # Create default validation rules
        fabric_service.create_default_rules()
        logger.info("✅ Default validation rules created!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        return False

def main():
    """Main initialization function"""
    print("=" * 50)
    print("SQL FABRIC DATABASE INITIALIZATION")
    print("=" * 50)
    
    try:
        # Test connection first
        if not test_fabric_connection():
            print("\n❌ Cannot proceed - SQL Fabric connection failed!")
            print("Please check your .env file configuration:")
            print(f"  - AZURE_CLIENT_ID: {config.AZURE_CLIENT_ID[:8]}...")
            print(f"  - AZURE_TENANT_ID: {config.AZURE_TENANT_ID[:8]}...")
            print(f"  - FABRIC_SERVER: {config.FABRIC_SERVER}")
            print(f"  - FABRIC_DATABASE: {config.FABRIC_DATABASE}")
            return False
        
        # Initialize database
        if not initialize_fabric_database():
            print("\n❌ Database initialization failed!")
            return False
        
        print("\n" + "=" * 50)
        print("✅ SQL FABRIC INITIALIZATION COMPLETE!")
        print("=" * 50)
        print("\nYour application is now ready to store all data in SQL Fabric:")
        print("  ✅ User authentication data")
        print("  ✅ Template configurations")
        print("  ✅ Validation rules and results")
        print("  ✅ Processing history")
        print("  ✅ Error corrections")
        print("\nDuckDB will only be used for temporary large file processing.")
        print("\nYou can now run your application with: python app_fabric.py")
        
        return True
        
    except Exception as e:
        logger.error(f"Initialization failed: {str(e)}")
        print(f"\n❌ Initialization failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
