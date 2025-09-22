"""
Simple fix for missing column_validations table
"""

import os
import sys

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.services.fabric_service import FabricSQLService

def create_missing_table():
    """Create the missing column_validations table"""
    
    try:
        fabric_service = FabricSQLService()
        
        print("Creating missing column_validations table...")
        
        # First, check if a similar table already exists
        check_query = """
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_NAME LIKE '%column%' OR TABLE_NAME LIKE '%valid%'
        """
        
        existing_tables = fabric_service.execute_query(check_query)
        print(f"Tables with 'column' or 'valid' in name:")
        for table in existing_tables:
            print(f"  - {table[0]}")
        
        # Try to create the missing table
        create_sql = """
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'column_validations')
        BEGIN
            CREATE TABLE column_validations (
                id INT IDENTITY(1,1) PRIMARY KEY,
                template_id INT NOT NULL,
                column_name NVARCHAR(255) NOT NULL,
                rule_type_id INT NOT NULL,
                created_at DATETIME2 DEFAULT GETDATE(),
                CONSTRAINT FK_column_validations_rule_type 
                    FOREIGN KEY (rule_type_id) REFERENCES validation_rule_types(rule_type_id)
            )
            PRINT 'Created column_validations table'
        END
        ELSE
        BEGIN
            PRINT 'column_validations table already exists'
        END
        """
        
        fabric_service.execute_non_query(create_sql)
        print("Table creation completed successfully!")
        
        # Test the table
        test_query = "SELECT COUNT(*) FROM column_validations"
        result = fabric_service.execute_query(test_query)
        print(f"Table test successful - contains {result[0][0]} records")
        
        return True
        
    except Exception as e:
        print(f"Failed to create table: {e}")
        return False

if __name__ == "__main__":
    if create_missing_table():
        print("\nSUCCESS! Now restart your Flask server:")
        print("1. Stop Flask server (Ctrl+C)")
        print("2. Run: python app_redis.py")
        print("3. Test rule configuration at localhost:5173/rule-configuration")
    else:
        print("\nFailed to create table. The issue might be:")
        print("1. Database permissions")
        print("2. Different table name already exists")
        print("3. Connection issue")
