"""
Test different token scopes for Fabric SQL
"""

import os
import sys
import pyodbc
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential

load_dotenv()

def test_fabric_token_scopes():
    """Test different token scopes for Fabric SQL"""
    
    tenant_id = os.getenv('AZURE_TENANT_ID')
    client_id = os.getenv('AZURE_CLIENT_ID') 
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    fabric_server = os.getenv('FABRIC_SERVER')
    fabric_database = os.getenv('FABRIC_DATABASE')
    
    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )
    
    # Different token scopes to try
    scopes_to_try = [
        "https://database.windows.net/.default",  # Standard Azure SQL
        "https://analysis.windows.net/powerbi/api/.default",  # Power BI/Fabric
        "https://storage.azure.com/.default",  # Azure Storage
        "https://graph.microsoft.com/.default",  # Microsoft Graph
    ]
    
    connection_string = f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={fabric_server};DATABASE={fabric_database};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    
    for scope in scopes_to_try:
        print(f"\\nTesting token scope: {scope}")
        
        try:
            token = credential.get_token(scope)
            print(f"✅ Token acquired successfully")
            
            connection = pyodbc.connect(
                connection_string,
                attrs_before={
                    1256: token.token.encode('utf-16le')
                }
            )
            
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
            print(f"✅ CONNECTION SUCCESSFUL with scope: {scope}")
            print(f"   Result: {result[0]}")
            
            cursor.close()
            connection.close()
            return True
            
        except Exception as e:
            print(f"❌ Failed with scope {scope}: {str(e)}")
            continue
    
    print("\\n❌ All token scopes failed")
    return False

if __name__ == '__main__':
    test_fabric_token_scopes()
