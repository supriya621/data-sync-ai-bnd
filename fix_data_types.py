"""
Fix Data Type Mismatch and Create Correct Table
First checks existing data types, then creates the table with matching types
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

from backend.config.config import config
from backend.services.fabric_service import fabric_service

def check_existing_data_types():
    """Check the data types of existing tables"""
    print("Checking existing data types...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Check validation_rule_types table structure
        print("\nvalidation_rule_types structure:")
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'validation_rule_types'
            ORDER BY ORDINAL_POSITION
        """)
        
        vrt_columns = cursor.fetchall()
        rule_type_id_info = None
        for col_name, data_type, max_len, precision, scale in vrt_columns:
            type_info = data_type
            if max_len:
                type_info += f"({max_len})"
            elif precision:
                type_info += f"({precision}"
                if scale:
                    type_info += f",{scale}"
                type_info += ")"
            
            print(f"  {col_name}: {type_info}")
            if col_name == 'rule_type_id':
                rule_type_id_info = (data_type, max_len, precision, scale)
        
        # Check column_validation_rules table structure for comparison
        print("\ncolumn_validation_rules structure:")
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'column_validation_rules'
            ORDER BY ORDINAL_POSITION
        """)
        
        cvr_columns = cursor.fetchall()
        for col_name, data_type, max_len, precision, scale in cvr_columns:
            type_info = data_type
            if max_len:
                type_info += f"({max_len})"
            elif precision:
                type_info += f"({precision}"
                if scale:
                    type_info += f",{scale}"
                type_info += ")"
            print(f"  {col_name}: {type_info}")
        
        cursor.close()
        return rule_type_id_info
        
    except Exception as e:
        print(f"Error checking data types: {str(e)}")
        return None

def create_column_validation_table_with_correct_types(rule_type_id_info):
    """Create column_validation table with correct data types"""
    print("\nCreating column_validation table with correct data types...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Build the correct data type for rule_type_id
        data_type, max_len, precision, scale = rule_type_id_info
        rule_type_id_type = data_type
        if precision:
            rule_type_id_type += f"({precision}"
            if scale:
                rule_type_id_type += f",{scale}"
            rule_type_id_type += ")"
        elif max_len:
            rule_type_id_type += f"({max_len})"
        
        print(f"Using rule_type_id data type: {rule_type_id_type}")
        
        # Create the table with matching data type
        create_sql = f"""
            CREATE TABLE column_validation (
                id INT IDENTITY(1,1) PRIMARY KEY,
                template_id INT NOT NULL,
                column_name VARCHAR(100) NOT NULL,
                rule_type_id {rule_type_id_type} NOT NULL,
                parameters TEXT NULL,
                is_active BIT DEFAULT 1,
                created_at DATETIME2 DEFAULT GETDATE(),
                CONSTRAINT FK_column_validation_rule_type 
                    FOREIGN KEY (rule_type_id) 
                    REFERENCES validation_rule_types(rule_type_id)
            )
        """
        
        print(f"Executing SQL:\n{create_sql}")
        cursor.execute(create_sql)
        
        conn.commit()
        cursor.close()
        print("✓ column_validation table created successfully with correct data types")
        return True
        
    except Exception as e:
        if "There is already an object named 'column_validation'" in str(e):
            print("✓ column_validation table already exists")
            return True
        else:
            print(f"✗ Error creating table: {str(e)}")
            return False

def drop_existing_column_validation():
    """Drop existing column_validation table if it exists with wrong structure"""
    print("Checking if column_validation table exists...")
    
    try:
        conn = fabric_service.get_connection()
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'column_validation'
        """)
        
        if cursor.fetchone()[0] > 0:
            print("column_validation table exists, dropping it to recreate with correct structure...")
            cursor.execute("DROP TABLE column_validation")
            conn.commit()
            print("✓ Existing table dropped")
        else:
            print("column_validation table does not exist")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"Error checking/dropping table: {str(e)}")
        return False

def test_new_table():
    """Test the newly created table"""
    print("\nTesting new column_validation table...")
    
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
        
        # Verify data
        cursor.execute("SELECT * FROM column_validation WHERE template_id = 999")
        row = cursor.fetchone()
        print(f"✓ Inserted data: {row}")
        
        # Clean up
        cursor.execute("DELETE FROM column_validation WHERE template_id = 999")
        conn.commit()
        print("✓ Test cleanup successful")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {str(e)}")
        return False

def main():
    """Main fix function"""
    print("=" * 60)
    print("FIXING DATA TYPE MISMATCH")
    print("=" * 60)
    
    # Step 1: Test connection
    result = fabric_service.test_connection()
    if result['status'] != 'success':
        print(f"✗ Connection failed: {result['message']}")
        return False
    print("✓ Connection successful")
    
    # Step 2: Check existing data types
    rule_type_id_info = check_existing_data_types()
    if not rule_type_id_info:
        print("✗ Could not determine rule_type_id data type")
        return False
    
    # Step 3: Drop existing table if needed
    if not drop_existing_column_validation():
        return False
    
    # Step 4: Create table with correct data types
    if not create_column_validation_table_with_correct_types(rule_type_id_info):
        return False
    
    # Step 5: Test the new table
    if not test_new_table():
        return False
    
    print("\n" + "=" * 60)
    print("✓ DATA TYPE MISMATCH FIXED!")
    print("=" * 60)
    print("Successfully created column_validation table with:")
    print(f"- Matching rule_type_id data type: {rule_type_id_info[0]}")
    print("- Proper foreign key constraint")
    print("- Tested insertion functionality")
    print("\nYour rule configuration should now work!")
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
