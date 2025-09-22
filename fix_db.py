"""
Quick Fix for Database Issues - Standalone Version
Run this from the main data-sync-ai-bnd directory
"""

import os
import sys
import logging

# Fix Windows console encoding issues
if os.name == 'nt':  # Windows
    os.system('chcp 65001 > nul')  # Set console to UTF-8

# Load environment variables first
from dotenv import load_dotenv
load_dotenv()

# Import services
from backend.config.config import config
from backend.services.fabric_service import fabric_service

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_connection():
    """Test SQL Fabric connection"""
    print("Testing SQL Fabric connection...")
    try:
        result = fabric_service.test_connection()
        if result['status'] == 'success':
            print("✓ SQL Fabric connection successful!")
            return True
        else:
            print(f"✗ Connection failed: {result['message']}")
            return False
    except Exception as e:
        print(f"✗ Connection error: {str(e)}")
        return False

def check_validation_rules():
    """Check if validation rules exist"""
    print("Checking validation rules...")
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'validation_rule_types'
        """)
        
        if cursor.fetchone()[0] == 0:
            print("✗ validation_rule_types table does not exist")
            return False
        
        # Check rule count
        cursor.execute("SELECT COUNT(*) FROM validation_rule_types")
        rule_count = cursor.fetchone()[0]
        print(f"Found {rule_count} validation rules")
        
        if rule_count == 0:
            return False
            
        # Show existing rules
        cursor.execute("SELECT rule_type_id, rule_name FROM validation_rule_types ORDER BY rule_type_id")
        rules = cursor.fetchall()
        print("Current rules:")
        for rule_id, rule_name in rules:
            print(f"  {rule_id}: {rule_name}")
        
        cursor.close()
        return rule_count >= 8  # Should have at least 8 basic rules
        
    except Exception as e:
        print(f"✗ Error checking rules: {str(e)}")
        return False

def create_missing_table():
    """Create validation_rule_types table"""
    print("Creating validation_rule_types table...")
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
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
        print("✓ Table created successfully")
        return True
        
    except Exception as e:
        print(f"✗ Error creating table: {str(e)}")
        return False

def insert_default_rules():
    """Insert default validation rules"""
    print("Inserting default validation rules...")
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Default rules that match your application's expectations
        default_rules = [
            (1, 'Required', 'Ensures the field is not null', '{"allow_null": false}', 1, 0),
            (2, 'Int', 'Validates integer format', '{"format": "integer"}', 1, 0),
            (3, 'Float', 'Validates number format', '{"format": "float"}', 1, 0),
            (4, 'Text', 'Allows text values', '{"allow_special": false}', 1, 0),
            (5, 'Email', 'Validates email format', '{"regex": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$"}', 1, 0),
            (6, 'Date', 'Validates date format', '{"format": "%d-%m-%Y"}', 1, 0),
            (7, 'Boolean', 'Validates boolean format', '{"format": "boolean"}', 1, 0),
            (8, 'Alphanumeric', 'Validates alphanumeric format', '{"format": "alphanumeric"}', 1, 0)
        ]
        
        for rule in default_rules:
            try:
                cursor.execute("""
                    INSERT INTO validation_rule_types 
                    (rule_type_id, rule_name, description, parameters, is_active, is_custom)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, rule)
                print(f"✓ Inserted rule: {rule[1]}")
            except Exception as e:
                print(f"✗ Error inserting rule {rule[1]}: {str(e)}")
        
        conn.commit()
        cursor.close()
        print("✓ Default rules inserted")
        return True
        
    except Exception as e:
        print(f"✗ Error inserting rules: {str(e)}")
        return False

def main():
    """Main fix function"""
    print("=" * 50)
    print("DATABASE ISSUES FIX")
    print("=" * 50)
    
    # Step 1: Test connection
    if not test_connection():
        print("\n✗ FAILED: Cannot connect to database")
        return False
    
    # Step 2: Check current state
    rules_exist = check_validation_rules()
    
    if not rules_exist:
        print("\n" + "-" * 30)
        print("FIXING MISSING RULES")
        print("-" * 30)
        
        # Try to create table first (in case it doesn't exist)
        try:
            create_missing_table()
        except:
            pass  # Table might already exist
        
        # Insert rules
        if not insert_default_rules():
            print("\n✗ FAILED: Could not insert validation rules")
            return False
        
        # Verify fix
        if not check_validation_rules():
            print("\n✗ FAILED: Rules still missing after insert")
            return False
    
    print("\n" + "=" * 50)
    print("✓ SUCCESS: Database is ready!")
    print("=" * 50)
    print("You can now:")
    print("1. Restart your Flask app: python app_redis.py")
    print("2. Try rule configuration again")
    print("3. The foreign key error should be resolved")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            print("\n" + "=" * 50)
            print("MANUAL ACTION NEEDED")
            print("=" * 50)
            print("Please check:")
            print("1. Your .env file has correct database settings")
            print("2. You can connect to SQL Fabric")
            print("3. You have write permissions to the database")
    except Exception as e:
        print(f"\n✗ Script failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to exit...")
