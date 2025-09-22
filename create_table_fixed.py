import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.fabric_service import fabric_service

try:
    print("Checking data type of validation_rule_types.rule_type_id...")
    
    # Get the actual data type of rule_type_id
    type_query = """
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'validation_rule_types' 
    AND COLUMN_NAME = 'rule_type_id'
    """
    
    result = fabric_service.execute_query(type_query)
    if result:
        col_info = result[0]
        print(f"rule_type_id column info: {col_info}")
        data_type = col_info[1]
        max_length = col_info[2]
        
        # Build the correct data type string
        if max_length and data_type in ['varchar', 'nvarchar', 'char', 'nchar']:
            correct_type = f"{data_type}({max_length})"
        else:
            correct_type = data_type
            
        print(f"Using data type: {correct_type}")
    else:
        print("Could not find rule_type_id column info")
        correct_type = "INT"  # fallback
    
    # Create table with matching data type
    sql = f"""CREATE TABLE column_validations (
        id INT IDENTITY(1,1) PRIMARY KEY,
        template_id INT NOT NULL,
        column_name NVARCHAR(255) NOT NULL,
        rule_type_id {correct_type} NOT NULL,
        created_at DATETIME2 DEFAULT GETDATE(),
        CONSTRAINT FK_column_validations_rule_type 
            FOREIGN KEY (rule_type_id) REFERENCES validation_rule_types(rule_type_id)
    )"""
    
    print(f"Creating table with SQL:")
    print(sql)
    
    fabric_service.execute_non_query(sql)
    print("SUCCESS: column_validations table created with matching data types!")
    
    # Test the table
    test_query = "SELECT COUNT(*) FROM column_validations"
    test_result = fabric_service.execute_query(test_query)
    print(f"Table test successful - contains {test_result[0][0]} records")
    
    print("\nNow restart your Flask server and test rule configuration!")
    
except Exception as e:
    if "already exists" in str(e).lower():
        print("Table already exists - that's good!")
    else:
        print(f"Failed to create table: {e}")
        
        # Try to get more info about the existing column
        try:
            print("\nTrying to get more details about validation_rule_types structure...")
            structure_query = """
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'validation_rule_types'
            ORDER BY ORDINAL_POSITION
            """
            structure = fabric_service.execute_query(structure_query)
            for col in structure:
                print(f"  {col[0]}: {col[1]} (max_len: {col[2]}, precision: {col[3]}, scale: {col[4]})")
                
        except Exception as e2:
            print(f"Could not get table structure: {e2}")
