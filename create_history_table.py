"""
Create Rule Configuration History Table
This tracks when users configure files with validation rules
"""
import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

def create_configuration_history_table():
    """Create the rule_configuration_history table in Fabric SQL"""
    
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    server = os.getenv('FABRIC_SERVER').split(',')[0]
    database = os.getenv('FABRIC_DATABASE')
    
    connection_string = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={client_id};"
        f"PWD={client_secret};"
        f"Authentication=ActiveDirectoryServicePrincipal;"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"LoginTimeout=120;"
    )
    
    # Create the table
    create_table_sql = """
    CREATE TABLE rule_configuration_history (
        history_id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL,
        file_name NVARCHAR(500) NOT NULL,
        original_file_name NVARCHAR(500) NOT NULL,
        sheet_name NVARCHAR(255),
        file_headers NVARCHAR(MAX),  -- JSON array of column headers
        configured_rules NVARCHAR(MAX),  -- JSON object of column->rules mapping
        total_rules_configured INT DEFAULT 0,
        configured_columns_count INT DEFAULT 0,
        configuration_summary NVARCHAR(MAX),
        file_size_mb DECIMAL(10,2),
        total_rows INT,
        validation_status NVARCHAR(50) DEFAULT 'CONFIGURED',  -- CONFIGURED, VALIDATED, PROCESSED
        created_at DATETIME DEFAULT GETDATE(),
        updated_at DATETIME DEFAULT GETDATE(),
        is_active BIT DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES login_details(id)
    )
    """
    
    # Create indexes for better performance
    create_indexes_sql = [
        "CREATE INDEX IX_rule_configuration_history_user_id ON rule_configuration_history(user_id)",
        "CREATE INDEX IX_rule_configuration_history_created_at ON rule_configuration_history(created_at DESC)",
        "CREATE INDEX IX_rule_configuration_history_active ON rule_configuration_history(is_active, user_id)"
    ]
    
    try:
        print("🔧 Creating rule_configuration_history table...")
        connection = pyodbc.connect(connection_string)
        cursor = connection.cursor()
        
        # Check if table already exists
        check_table_sql = """
        SELECT COUNT(*) as table_count 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_NAME = 'rule_configuration_history'
        """
        
        cursor.execute(check_table_sql)
        table_exists = cursor.fetchone()[0] > 0
        
        if table_exists:
            print("✅ Table rule_configuration_history already exists")
        else:
            # Create the table
            cursor.execute(create_table_sql)
            print("✅ Created table rule_configuration_history")
            
            # Create indexes
            for index_sql in create_indexes_sql:
                try:
                    cursor.execute(index_sql)
                    print(f"✅ Created index: {index_sql.split('INDEX ')[1].split(' ON')[0]}")
                except Exception as e:
                    print(f"⚠️ Index creation warning: {e}")
            
            connection.commit()
            print("🎉 rule_configuration_history table created successfully!")
        
        # Test the table
        cursor.execute("SELECT TOP 1 * FROM rule_configuration_history")
        print("✅ Table is accessible and ready to use")
        
        cursor.close()
        connection.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        return False

if __name__ == "__main__":
    print("=== Creating Rule Configuration History Table ===")
    success = create_configuration_history_table()
    
    if success:
        print("\n🚀 Ready to track file configuration history!")
        print("Now your backend can save:")
        print("  - File names and headers")
        print("  - User configuration details") 
        print("  - Validation rule mappings")
        print("  - File processing history")
    else:
        print("\n❌ Failed to create table. Check connection and permissions.")
