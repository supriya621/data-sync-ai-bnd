"""
Database initialization script for Rule Configuration History
Creates the necessary table and indexes in Microsoft Fabric SQL Server
"""

import os
import sys
import logging
from pathlib import Path

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Import your existing services
from backend.services.fabric_service import fabric_service

def create_configuration_history_table():
    """Create the rule_configuration_history table with all indexes"""
    try:
        # Read the SQL script
        sql_file_path = os.path.join(os.path.dirname(__file__), 'create_configuration_history_table.sql')
        
        with open(sql_file_path, 'r', encoding='utf-8') as file:
            sql_script = file.read()
        
        # Split by GO statements or semicolons and execute each statement
        statements = [stmt.strip() for stmt in sql_script.split(';') if stmt.strip() and not stmt.strip().startswith('--')]
        
        for statement in statements:
            if statement and not statement.upper().startswith('PRINT'):
                try:
                    fabric_service.execute_non_query(statement)
                    print(f"✅ Executed: {statement[:50]}...")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"⚠️  Already exists: {statement[:50]}...")
                    else:
                        print(f"❌ Error executing: {statement[:50]}... - {e}")
                        raise
        
        print("\n🎉 Rule Configuration History table created successfully!")
        print("✅ All indexes created")
        print("✅ Foreign key constraints established")
        
        # Verify the table exists
        verification_query = """
            SELECT COUNT(*) as table_exists 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'rule_configuration_history'
        """
        result = fabric_service.execute_query(verification_query)
        
        if result and result[0]['table_exists'] > 0:
            print("✅ Table verification successful")
            
            # Show table structure
            structure_query = """
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'rule_configuration_history'
                ORDER BY ORDINAL_POSITION
            """
            columns = fabric_service.execute_query(structure_query)
            
            print("\n📊 Table Structure:")
            for col in columns:
                print(f"   - {col['COLUMN_NAME']}: {col['DATA_TYPE']} {'NULL' if col['IS_NULLABLE'] == 'YES' else 'NOT NULL'}")
                
        return True
        
    except Exception as e:
        print(f"❌ Error creating configuration history table: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Creating Rule Configuration History table...")
    success = create_configuration_history_table()
    
    if success:
        print("\n✅ Database setup completed successfully!")
        print("🔄 You can now run your application with configuration history enabled.")
    else:
        print("\n❌ Database setup failed!")
        print("🔍 Check the error messages above and try again.")
