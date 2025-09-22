"""
Fix Table Name Mismatch Issue
Creates the missing column_validation table that your application expects
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

from backend.config.config import config
from backend.services.fabric_service import fabric_service

def create_column_validation_table():
    """Create the column_validation table that the application expects"""
    print("Creating column_validation table...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Create the table with the same structure as column_validation_rules
        cursor.execute("""
            CREATE TABLE column_validation (
                id INT IDENTITY(1,1) PRIMARY KEY,
                template_id INT NOT NULL,
                column_name VARCHAR(100) NOT NULL,
                rule_type_id INT NOT NULL,
                parameters TEXT NULL,
                is_active BIT DEFAULT 1,
                created_at DATETIME2 DEFAULT GETDATE(),
                FOREIGN KEY (rule_type_id) REFERENCES validation_rule_types(rule_type_id)
            )
        """)
        
        conn.commit()
        cursor.close()
        print("✓ column_validation table created successfully")
        return True
        
    except Exception as e:
        if "There is already an object named 'column_validation'" in str(e):
            print("✓ column_validation table already exists")
            return True
        else:
            print(f"✗ Error creating table: {str(e)}")
            return False

def test_insertion_to_new_table():
    """Test inserting into the newly created table"""
    print("Testing insertion into column_validation table...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Test insertion
        cursor.execute("""
            INSERT INTO column_validation 
            (template_id, column_name, rule_type_id, parameters, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, (999, 'test_column', 1, '{}', 1))
        
        conn.commit()
        print("✓ Test insertion successful")
        
        # Clean up test data
        cursor.execute("DELETE FROM column_validation WHERE template_id = 999")
        conn.commit()
        print("✓ Test cleanup successful")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"✗ Test insertion failed: {str(e)}")
        if cursor:
            cursor.close()
        return False

def check_table_structure():
    """Compare structure of both tables"""
    print("Checking table structures...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Check column_validation_rules structure
        print("\ncolumn_validation_rules structure:")
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'column_validation_rules'
            ORDER BY ORDINAL_POSITION
        """)
        
        rules_columns = cursor.fetchall()
        for col_name, data_type, is_nullable in rules_columns:
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"  {col_name}: {data_type} {nullable}")
        
        # Check column_validation structure
        print("\ncolumn_validation structure:")
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'column_validation'
            ORDER BY ORDINAL_POSITION
        """)
        
        validation_columns = cursor.fetchall()
        for col_name, data_type, is_nullable in validation_columns:
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"  {col_name}: {data_type} {nullable}")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"Error checking structures: {str(e)}")
        return False

def main():
    """Main fix function"""
    print("=" * 60)
    print("FIXING TABLE NAME MISMATCH")
    print("=" * 60)
    
    # Step 1: Test connection
    result = fabric_service.test_connection()
    if result['status'] != 'success':
        print(f"✗ Connection failed: {result['message']}")
        return False
    print("✓ Connection successful")
    
    # Step 2: Create missing table
    if not create_column_validation_table():
        return False
    
    # Step 3: Test the fix
    if not test_insertion_to_new_table():
        return False
    
    # Step 4: Check structures
    check_table_structure()
    
    print("\n" + "=" * 60)
    print("✓ TABLE MISMATCH FIXED!")
    print("=" * 60)
    print("Changes made:")
    print("1. Created missing 'column_validation' table")
    print("2. Added proper foreign key constraint to validation_rule_types")
    print("3. Verified insertion works correctly")
    print("\nYour application should now work properly!")
    print("Restart your Flask app: python app_redis.py")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            print("\n✗ Fix failed - check error messages above")
    except Exception as e:
        print(f"\n✗ Script failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to exit...")
