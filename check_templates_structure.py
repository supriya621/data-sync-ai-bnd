"""
Check Excel Templates Table Structure
"""
import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

def check_excel_templates_structure():
    """Check the structure of excel_templates table"""
    
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
    
    try:
        print("🔍 Checking excel_templates table structure...")
        connection = pyodbc.connect(connection_string)
        cursor = connection.cursor()
        
        # Check table structure
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'excel_templates'
            ORDER BY ORDINAL_POSITION
        """)
        
        columns = cursor.fetchall()
        
        if columns:
            print("✅ excel_templates table found!")
            print("\n📊 Table Structure:")
            print("-" * 50)
            for col in columns:
                print(f"{col[0]:<20} | {col[1]:<15} | Nullable: {col[2]}")
            
            # Check if user_id exists
            has_user_id = any(col[0].lower() == 'user_id' for col in columns)
            print(f"\n🔍 Has user_id column: {'✅ YES' if has_user_id else '❌ NO'}")
            
            # Show sample data
            cursor.execute("SELECT TOP 3 * FROM excel_templates")
            sample_data = cursor.fetchall()
            
            if sample_data:
                print("\n📋 Sample Data:")
                print("-" * 50)
                column_names = [col[0] for col in columns]
                for row in sample_data:
                    row_dict = dict(zip(column_names, row))
                    print(row_dict)
            else:
                print("\n📋 No sample data found (table is empty)")
            
            return has_user_id, [col[0] for col in columns]
            
        else:
            print("❌ excel_templates table not found!")
            return False, []
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"❌ Error checking table structure: {e}")
        return False, []

if __name__ == "__main__":
    print("=== Excel Templates Table Structure Check ===")
    has_user_id, columns = check_excel_templates_structure()
    
    print(f"\n🎯 Configuration History Setup:")
    if has_user_id:
        print("✅ Perfect! Table has user_id - can filter by user")
        print("📝 Your configuration history will show user-specific templates")
    else:
        print("⚠️  Table doesn't have user_id - will show all templates")
        print("💡 Consider adding user_id column for user-specific history")
        print("\n🔧 To add user_id column:")
        print("   ALTER TABLE excel_templates ADD user_id INT")
        print("   ALTER TABLE excel_templates ADD CONSTRAINT FK_excel_templates_user")
        print("   FOREIGN KEY (user_id) REFERENCES login_details(id)")
    
    print(f"\n📋 Available columns: {', '.join(columns)}")
