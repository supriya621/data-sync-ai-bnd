"""
Discover actual table names and fix the column_validations issue
"""

import os
import sys

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.services.fabric_service import FabricSQLService

def discover_table_names():
    """Discover the actual table names in your database"""
    
    try:
        fabric_service = FabricSQLService()
        
        print("🔍 Discovering all tables in your database...")
        
        # Get all table names
        tables_query = """
        SELECT TABLE_NAME, TABLE_SCHEMA 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
        """
        
        tables = fabric_service.execute_query(tables_query)
        
        print(f"📋 Found {len(tables)} tables:")
        for table in tables:
            print(f"   - {table[0]} (schema: {table[1]})")
        
        # Look for tables that might be the column validations table
        print(f"\n🔍 Looking for column validation tables...")
        column_validation_tables = []
        for table in tables:
            table_name = table[0].lower()
            if 'column' in table_name and ('valid' in table_name or 'rule' in table_name):
                column_validation_tables.append(table[0])
                print(f"   📌 Possible match: {table[0]}")
        
        # Also look for any table containing 'valid'
        print(f"\n🔍 All tables containing 'valid':")
        for table in tables:
            if 'valid' in table[0].lower():
                print(f"   - {table[0]}")
        
        # Check foreign key constraints to see what table the constraint actually references
        print(f"\n🔍 Looking for foreign key constraints...")
        fk_query = """
        SELECT 
            fk.name AS constraint_name,
            tp.name AS parent_table,
            cp.name AS parent_column,
            tr.name AS referenced_table,
            cr.name AS referenced_column
        FROM sys.foreign_keys fk
        INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        INNER JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
        INNER JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id AND fkc.parent_column_id = cp.column_id
        INNER JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
        INNER JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id AND fkc.referenced_column_id = cr.column_id
        WHERE fk.name LIKE '%column_va%' OR tr.name = 'validation_rule_types'
        """
        
        try:
            constraints = fabric_service.execute_query(fk_query)
            if constraints:
                print("   Foreign key constraints found:")
                for constraint in constraints:
                    print(f"   - {constraint[0]}: {constraint[1]}.{constraint[2]} -> {constraint[3]}.{constraint[4]}")
                    if constraint[0].startswith('FK__column_va'):
                        print(f"   📌 This is likely your column validations table: {constraint[1]}")
                        column_validation_tables.append(constraint[1])
            else:
                print("   No foreign key constraints found matching the pattern")
        except Exception as e:
            print(f"   Could not query foreign key constraints: {e}")
        
        # If we found potential column validation tables, examine their structure
        if column_validation_tables:
            # Remove duplicates
            column_validation_tables = list(set(column_validation_tables))
            print(f"\n📋 Examining potential column validation tables:")
            
            for table_name in column_validation_tables:
                print(f"\n   Table: {table_name}")
                try:
                    # Get column structure
                    columns_query = f"""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = '{table_name}'
                    ORDER BY ORDINAL_POSITION
                    """
                    columns = fabric_service.execute_query(columns_query)
                    
                    print(f"   Columns:")
                    for col in columns:
                        print(f"     - {col[0]} ({col[1]}, nullable: {col[2]})")
                    
                    # Sample some data
                    try:
                        sample_query = f"SELECT TOP 3 * FROM {table_name}"
                        samples = fabric_service.execute_query(sample_query)
                        if samples:
                            print(f"   Sample data:")
                            for i, row in enumerate(samples, 1):
                                print(f"     Row {i}: {row}")
                        else:
                            print(f"   No data in table")
                    except Exception as e:
                        print(f"   Could not sample data: {e}")
                        
                except Exception as e:
                    print(f"   Could not examine table {table_name}: {e}")
        
        else:
            print(f"\n❌ No column validation tables found!")
            print("This means the table needs to be created.")
            
            # Let's create the missing table
            print(f"\n🔧 Creating missing column_validations table...")
            
            create_table_sql = """
            CREATE TABLE column_validations (
                id INT IDENTITY(1,1) PRIMARY KEY,
                template_id INT NOT NULL,
                column_name NVARCHAR(255) NOT NULL,
                rule_type_id INT NOT NULL,
                created_at DATETIME2 DEFAULT GETDATE(),
                updated_at DATETIME2 DEFAULT GETDATE(),
                CONSTRAINT FK_column_validations_rule_type 
                    FOREIGN KEY (rule_type_id) REFERENCES validation_rule_types(rule_type_id),
                CONSTRAINT UQ_template_column_rule 
                    UNIQUE (template_id, column_name, rule_type_id)
            )
            """
            
            try:
                fabric_service.execute_non_query(create_table_sql)
                print(f"   ✅ Created column_validations table successfully!")
                
                # Verify the table was created
                verify_query = """
                SELECT COLUMN_NAME, DATA_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'column_validations'
                ORDER BY ORDINAL_POSITION
                """
                new_columns = fabric_service.execute_query(verify_query)
                print(f"   📋 New table structure:")
                for col in new_columns:
                    print(f"     - {col[0]} ({col[1]})")
                
            except Exception as e:
                print(f"   ❌ Failed to create table: {e}")
                print(f"   You may need to create it manually or check permissions")
        
        print(f"\n✅ Table discovery and fix completed!")
        return True
        
    except Exception as e:
        print(f"❌ Table discovery failed: {e}")
        return False

if __name__ == "__main__":
    discover_table_names()
