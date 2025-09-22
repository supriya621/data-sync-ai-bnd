"""
Fix Database Issues Script for Data Sync AI
This script fixes both the Unicode logging issues and missing validation rule types
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Fix Windows console encoding issues
import codecs
import locale

# Set console encoding to UTF-8
if os.name == 'nt':  # Windows
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleCP(65001)
    kernel32.SetConsoleOutputCP(65001)
    
    # Set stdout/stderr encoding
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

# Load environment variables
load_dotenv()

# Add project root to path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

# Import services
from backend.config.config import config
from backend.services.fabric_service import fabric_service

# Setup logging with proper encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def fix_logging_encoding():
    """Fix Unicode encoding issues in logging"""
    logger.info("Fixing logging encoding...")
    
    # Update all existing loggers to handle Unicode properly
    for name, logger_obj in logging.Logger.manager.loggerDict.items():
        if isinstance(logger_obj, logging.Logger):
            for handler in logger_obj.handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setStream(sys.stdout)
    
    logger.info("Logging encoding fixed - emojis should now display properly")

def test_fabric_connection():
    """Test SQL Fabric connection"""
    logger.info("Testing SQL Fabric connection...")
    try:
        result = fabric_service.test_connection()
        
        if result['status'] == 'success':
            logger.info("SQL Fabric connection successful!")
            return True
        else:
            logger.error(f"SQL Fabric connection failed: {result['message']}")
            return False
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return False

def check_database_schema():
    """Check if required tables exist"""
    logger.info("Checking database schema...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Check for validation_rule_types table
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'validation_rule_types'
        """)
        
        table_exists = cursor.fetchone()[0] > 0
        logger.info(f"validation_rule_types table exists: {table_exists}")
        
        if table_exists:
            # Check if it has data
            cursor.execute("SELECT COUNT(*) FROM validation_rule_types")
            rule_count = cursor.fetchone()[0]
            logger.info(f"validation_rule_types table has {rule_count} records")
            
            if rule_count > 0:
                # Show existing rules
                cursor.execute("SELECT rule_type_id, rule_name FROM validation_rule_types ORDER BY rule_type_id")
                rules = cursor.fetchall()
                logger.info("Existing validation rules:")
                for rule_id, rule_name in rules:
                    logger.info(f"  - ID: {rule_id}, Name: {rule_name}")
        
        cursor.close()
        return table_exists
        
    except Exception as e:
        logger.error(f"Error checking schema: {str(e)}")
        return False

def create_validation_rule_types_table():
    """Create validation_rule_types table if it doesn't exist"""
    logger.info("Creating validation_rule_types table...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Create the table
        cursor.execute("""
            CREATE TABLE validation_rule_types (
                rule_type_id INT PRIMARY KEY,
                rule_name VARCHAR(50) NOT NULL,
                description TEXT,
                parameters TEXT,
                is_active BIT DEFAULT 1,
                is_custom BIT DEFAULT 0,
                created_at DATETIME2 DEFAULT GETDATE()
            )
        """)
        
        conn.commit()
        cursor.close()
        logger.info("validation_rule_types table created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error creating table: {str(e)}")
        return False

def initialize_validation_rules():
    """Initialize validation rules using the existing function"""
    logger.info("Initializing validation rules...")
    
    try:
        # Use the existing function from fabric_service
        fabric_service.create_default_rules()
        logger.info("Validation rules initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing rules: {str(e)}")
        return False

def verify_fix():
    """Verify that the fix worked"""
    logger.info("Verifying fix...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Check if all required rules exist
        required_rules = ['Required', 'Int', 'Float', 'Text', 'Email', 'Date', 'Boolean', 'Alphanumeric']
        
        cursor.execute("""
            SELECT rule_name FROM validation_rule_types 
            WHERE rule_name IN ('Required', 'Int', 'Float', 'Text', 'Email', 'Date', 'Boolean', 'Alphanumeric')
        """)
        
        existing_rules = [row[0] for row in cursor.fetchall()]
        missing_rules = set(required_rules) - set(existing_rules)
        
        if missing_rules:
            logger.error(f"Missing rules: {missing_rules}")
            return False
        
        logger.info("All required validation rules are present")
        cursor.close()
        return True
        
    except Exception as e:
        logger.error(f"Verification failed: {str(e)}")
        return False

def main():
    """Main fix function"""
    print("=" * 60)
    print("DATA SYNC AI - DATABASE ISSUES FIX")
    print("=" * 60)
    
    try:
        # Step 1: Fix logging encoding
        fix_logging_encoding()
        logger.info("Step 1: Fixed logging encoding")
        
        # Step 2: Test connection
        if not test_fabric_connection():
            logger.error("Cannot proceed - database connection failed!")
            return False
        logger.info("Step 2: Database connection verified")
        
        # Step 3: Check schema
        schema_exists = check_database_schema()
        if not schema_exists:
            logger.info("Step 3: Creating missing schema...")
            if not create_validation_rule_types_table():
                return False
        else:
            logger.info("Step 3: Schema verified")
        
        # Step 4: Initialize validation rules
        if not initialize_validation_rules():
            return False
        logger.info("Step 4: Validation rules initialized")
        
        # Step 5: Verify fix
        if not verify_fix():
            return False
        logger.info("Step 5: Fix verified successfully")
        
        print("\n" + "=" * 60)
        print("SUCCESS! Database issues have been fixed!")
        print("=" * 60)
        print("\nChanges made:")
        print("  1. Fixed Unicode/emoji encoding in logs")
        print("  2. Ensured validation_rule_types table exists")
        print("  3. Populated default validation rules")
        print("  4. Verified all required rules are present")
        print("\nYou can now:")
        print("  - Restart your Flask application")
        print("  - Try configuring validation rules again")
        print("  - The drag-and-drop functionality should work")
        
        return True
        
    except Exception as e:
        logger.error(f"Fix failed: {str(e)}")
        print(f"\nFIX FAILED: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n" + "=" * 60)
        print("READY TO USE!")
        print("=" * 60)
        print("1. Close your current Flask server (Ctrl+C)")
        print("2. Restart it with: python app_redis.py")
        print("3. Try the rule configuration again")
        print("\nThe foreign key constraint error should now be resolved!")
    else:
        print("\n" + "=" * 60)
        print("MANUAL ACTION REQUIRED")
        print("=" * 60)
        print("Please check the error messages above and:")
        print("1. Verify your .env file configuration")
        print("2. Ensure SQL Fabric database is accessible")
        print("3. Check database permissions")
    
    input("\nPress Enter to exit...")
    sys.exit(0 if success else 1)
