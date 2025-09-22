"""
Test alternative Fabric SQL connection methods
"""
import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

def test_alternative_connections():
    """Test different ODBC connection string formats"""
    
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    tenant_id = os.getenv('AZURE_TENANT_ID')
    server = os.getenv('FABRIC_SERVER').split(',')[0]  # Remove port
    database = os.getenv('FABRIC_DATABASE')
    
    # Alternative connection string formats
    connection_configs = [
        {
            "name": "Standard Service Principal",
            "connection_string": (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"UID={client_id};"
                f"PWD={client_secret};"
                f"Authentication=ActiveDirectoryServicePrincipal;"
                f"Encrypt=yes;"
                f"TrustServerCertificate=yes;"  # More permissive
                f"LoginTimeout=120;"
            )
        },
        {
            "name": "Alternative Format",
            "connection_string": (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"UID={client_id};"
                f"PWD={client_secret};"
                f"Authentication=ActiveDirectoryServicePrincipal;"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout=30;"
                f"Command Timeout=30;"
            )
        },
        {
            "name": "With Explicit Tenant",
            "connection_string": (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"UID={client_id}@{tenant_id};"  # Include tenant in UID
                f"PWD={client_secret};"
                f"Authentication=ActiveDirectoryServicePrincipal;"
                f"Encrypt=yes;"
                f"TrustServerCertificate=yes;"
                f"LoginTimeout=60;"
            )
        }
    ]
    
    for config in connection_configs:
        print(f"\n=== Testing: {config['name']} ===")
        
        try:
            print("Attempting connection...")
            connection = pyodbc.connect(config['connection_string'])
            print("✅ SUCCESS! Connection established")
            
            # Test query
            cursor = connection.cursor()
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            print(f"✅ Query successful: {result}")
            
            cursor.close()
            connection.close()
            
            print(f"🎉 WORKING CONFIGURATION: {config['name']}")
            print(f"Connection string format that works:")
            print(config['connection_string'].replace(client_secret, "***SECRET***"))
            return True
            
        except Exception as e:
            error_str = str(e)
            print(f"❌ Failed: {error_str}")
            
            # Analyze error
            if "0xA190" in error_str:
                print("   → Service Principal authentication failed")
                print("   → Check: Client secret expired? Permissions missing?")
            elif "timeout" in error_str.lower():
                print("   → Connection timeout - try different timeout values")
            elif "invalid" in error_str.lower():
                print("   → Invalid connection string format")
    
    return False

if __name__ == "__main__":
    print("=== Alternative Fabric SQL Connection Test ===")
    print("\nTesting different connection string formats...")
    
    if not test_alternative_connections():
        print("\n🔧 RECOMMENDED FIXES:")
        print("1. Check Azure Portal - generate new client secret")
        print("2. Verify Service Principal has Fabric permissions")
        print("3. Contact Azure admin if needed")
    
    print(f"\nCredentials being tested:")
    print(f"Client ID: {os.getenv('AZURE_CLIENT_ID')}")
    print(f"Tenant ID: {os.getenv('AZURE_TENANT_ID')}")
    print(f"Server: {os.getenv('FABRIC_SERVER')}")
