"""
Test direct Fabric SQL connection with extended timeout and alternative endpoints
"""
import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

def test_fabric_connection():
    """Test Fabric SQL connection with different configurations"""
    
    # Your credentials
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    server = os.getenv('FABRIC_SERVER')
    database = os.getenv('FABRIC_DATABASE')
    tenant_id = os.getenv('AZURE_TENANT_ID')
    
    # Test configurations
    configs = [
        {
            "name": "Original Config (with port)",
            "server": server,
            "timeout": 30
        },
        {
            "name": "Without Port",
            "server": server.split(',')[0],
            "timeout": 60
        },
        {
            "name": "Extended Timeout",
            "server": server.split(',')[0],
            "timeout": 120
        }
    ]
    
    for config in configs:
        print(f"\n=== Testing: {config['name']} ===")
        print(f"Server: {config['server']}")
        print(f"Timeout: {config['timeout']} seconds")
        
        try:
            connection_string = (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER={config['server']};"
                f"DATABASE={database};"
                f"UID={client_id};"
                f"PWD={client_secret};"
                f"Authentication=ActiveDirectoryServicePrincipal;"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"LoginTimeout={config['timeout']};"
            )
            
            print("Attempting connection...")
            connection = pyodbc.connect(connection_string)
            print("✅ SUCCESS! Connection established")
            
            # Test a simple query
            cursor = connection.cursor()
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            print(f"✅ Query test successful: {result}")
            
            cursor.close()
            connection.close()
            
            print(f"🎉 WORKING CONFIGURATION FOUND!")
            return True
            
        except Exception as e:
            print(f"❌ Failed: {str(e)}")
            
    return False

if __name__ == "__main__":
    print("=== Microsoft Fabric SQL Connection Test ===")
    if not test_fabric_connection():
        print("\n⚠️ All connection attempts failed")
        print("\nPossible causes:")
        print("1. Network/firewall blocking Azure endpoints")
        print("2. Service Principal credentials expired")
        print("3. Temporary Azure service issues")
        print("4. Azure tenant/subscription issues")
