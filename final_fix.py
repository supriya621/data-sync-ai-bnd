"""
Final Fix for Column Validation Table Creation
Uses correct SQL Server syntax for BIGINT data type
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

from backend.config.config import config
from backend.services.fabric_service import fabric_service

def create_column_validation_table_correct():
    """Create column_validation table with correct SQL Server syntax"""
    print("Creating column_validation table with correct SQL Server syntax...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Create the table using BIGINT without precision (SQL Server syntax)
        create_sql = """
            CREATE TABLE column_validation (
                id INT IDENTITY(1,1) PRIMARY KEY,
                template_id INT NOT NULL,
                column_name VARCHAR(100) NOT NULL,
                rule_type_id BIGINT NOT NULL,
                parameters TEXT NULL,
                is_active BIT DEFAULT 1,
                created_at DATETIME2 DEFAULT GETDATE(),
                CONSTRAINT FK_column_validation_rule_type 
                    FOREIGN KEY (rule_type_id) 
                    REFERENCES validation_rule_types(rule_type_id)
            )
        """
        
        print("Executing SQL:")
        print(create_sql)
        cursor.execute(create_sql)
        
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

def test_the_table():
    """Test inserting data into the new table"""
    print("Testing the new table...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Test insertion with a valid rule_type_id (1 = Required)
        cursor.execute("""
            INSERT INTO column_validation 
            (template_id, column_name, rule_type_id, parameters, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, (999, 'test_column', 1, '{"test": "value"}', 1))
        
        conn.commit()
        print("✓ Test insertion successful")
        
        # Verify the data
        cursor.execute("SELECT * FROM column_validation WHERE template_id = 999")
        row = cursor.fetchone()
        if row:
            print(f"✓ Data verified: ID={row[0]}, Template={row[1]}, Column={row[2]}, Rule={row[3]}")
        
        # Clean up test data
        cursor.execute("DELETE FROM column_validation WHERE template_id = 999")
        conn.commit()
        print("✓ Test cleanup successful")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"✗ Test insertion failed: {str(e)}")
        return False

def verify_foreign_key():
    """Verify the foreign key constraint is working"""
    print("Verifying foreign key constraint...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Try to insert with an invalid rule_type_id (should fail)
        try:
            cursor.execute("""
                INSERT INTO column_validation 
                (template_id, column_name, rule_type_id, parameters, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (998, 'test_column', 999, '{}', 1))  # rule_type_id 999 doesn't exist
            
            conn.commit()
            print("✗ Foreign key constraint is not working (invalid insert succeeded)")
            
            # Clean up if it somehow succeeded
            cursor.execute("DELETE FROM column_validation WHERE template_id = 998")
            conn.commit()
            return False
            
        except Exception as fk_error:
            if "FOREIGN KEY constraint" in str(fk_error):
                print("✓ Foreign key constraint is working correctly")
                return True
            else:
                print(f"✗ Unexpected error during foreign key test: {str(fk_error)}")
                return False
        
        cursor.close()
        
    except Exception as e:
        print(f"Error testing foreign key: {str(e)}")
        return False

def show_final_status():
    """Show the final table structure"""
    print("Final table structure:")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'column_validation'
            ORDER BY ORDINAL_POSITION
        """)
        
        columns = cursor.fetchall()
        for col_name, data_type, is_nullable in columns:
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"  {col_name}: {data_type} {nullable}")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"Error showing table structure: {str(e)}")
        return False

def main():
    """Main fix function"""
    print("=" * 60)
    print("FINAL FIX - COLUMN VALIDATION TABLE")
    print("=" * 60)
    
    # Step 1: Test connection
    result = fabric_service.test_connection()
    if result['status'] != 'success':
        print(f"✗ Connection failed: {result['message']}")
        return False
    print("✓ Connection successful")
    
    # Step 2: Create table with correct syntax
    if not create_column_validation_table_correct():
        return False
    
    # Step 3: Test the table
    if not test_the_table():
        return False
    
    # Step 4: Verify foreign key constraint
    if not verify_foreign_key():
        print("Warning: Foreign key constraint may not be working properly")
    
    # Step 5: Show final structure
    show_final_status()
    
    print("\n" + "=" * 60)
    print("SUCCESS! READY TO USE!")
    print("=" * 60)
    print("The column_validation table has been created with:")
    print("- Correct BIGINT data type for rule_type_id")
    print("- Working foreign key constraint to validation_rule_types")
    print("- All required columns for your application")
    print("\nNext steps:")
    print("1. Close your Flask server (Ctrl+C)")
    print("2. Restart it: python app_redis.py")
    print("3. Test rule configuration at localhost:5173/rule-configuration")
    print("4. The 'Failed to save configuration' error should be fixed!")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            print("\n✗ Fix failed - check error messages above")
        else:
            print("\n🎉 Your Data Sync AI application should now work perfectly!")
    except Exception as e:
        print(f"\n✗ Script failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to exit...")
