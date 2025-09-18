"""
Test specific Fabric SQL connection formats
"""

import os
import sys
import pyodbc
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential

load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

def test_fabric_formats():
    """Test different Fabric-specific connection formats"""
    
    # Get credentials
    tenant_id = os.getenv('AZURE_TENANT_ID')
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    fabric_server = os.getenv('FABRIC_SERVER')
    fabric_database = os.getenv('FABRIC_DATABASE')
    
    if not all([tenant_id, client_id, client_secret, fabric_server, fabric_database]):
        print("❌ Missing required environment variables")
        return False
    
    # Get access token
    try:
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        token = credential.get_token("https://database.windows.net/.default")
        print("✅ Azure authentication successful")
    except Exception as e:
        print(f"❌ Azure authentication failed: {e}")
        return False
    
    # Fabric-specific connection strings
    connection_strings = [
        # Format 1: Standard Fabric format
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={fabric_server};DATABASE={fabric_database};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;",
        
        # Format 2: With TCP prefix
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER=tcp:{fabric_server};DATABASE={fabric_database};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;",
        
        # Format 3: Minimal format
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={fabric_server};DATABASE={fabric_database};Encrypt=yes;",
        
        # Format 4: With additional Fabric settings
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={fabric_server};DATABASE={fabric_database};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;Login Timeout=30;",
        
        # Format 5: Try without specifying port
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={fabric_server.split(',')[0]};DATABASE={fabric_database};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;",
    ]
    
    for i, conn_str in enumerate(connection_strings, 1):
        print(f"\\nTesting Format {i}:")
        print(f"Connection String: {conn_str}")
        
        try:
            connection = pyodbc.connect(
                conn_str,
                attrs_before={
                    1256: token.token.encode('utf-16le')  # SQL_COPT_SS_ACCESS_TOKEN
                }
            )
            
            # Test query
            cursor = connection.cursor()
            cursor.execute("SELECT 1 as test_value, @@VERSION as version")
            result = cursor.fetchone()
            
            print(f"✅ Format {i} SUCCESS!")
            print(f"   Test result: {result[0]}")
            print(f"   SQL Server version: {result[1][:50]}...")
            
            cursor.close()
            connection.close()
            return True
            
        except Exception as e:
            print(f"❌ Format {i} failed: {str(e)}")
            continue
    
    print("\\n❌ All connection formats failed")
    return False

if __name__ == '__main__':
    test_fabric_formats()
