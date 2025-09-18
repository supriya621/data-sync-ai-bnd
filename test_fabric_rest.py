"""
Test SQL Fabric using REST API instead of ODBC
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential

load_dotenv()

def test_fabric_rest_api():
    """Test Fabric SQL using REST API instead of ODBC"""
    
    # Get credentials
    tenant_id = os.getenv('AZURE_TENANT_ID')
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    fabric_server = os.getenv('FABRIC_SERVER')
    fabric_database = os.getenv('FABRIC_DATABASE')
    
    try:
        # Get access token
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Try different token scopes for REST API
        token_scopes = [
            "https://database.windows.net/.default",
            "https://analysis.windows.net/powerbi/api/.default",
            "https://management.azure.com/.default"
        ]
        
        for scope in token_scopes:
            try:
                print(f"\\nTesting REST API with scope: {scope}")
                token = credential.get_token(scope)
                
                # Extract server name without port
                server_name = fabric_server.split(',')[0]
                
                # Try Fabric SQL REST API endpoint
                rest_urls = [
                    f"https://{server_name}/v1/rest/services/database/query",
                    f"https://{server_name}/api/v1/databases/{fabric_database}/query", 
                    f"https://{server_name}/rest/v1/query",
                ]
                
                headers = {
                    'Authorization': f'Bearer {token.token}',
                    'Content-Type': 'application/json'
                }
                
                test_query = {
                    "query": "SELECT 1 as test_value",
                    "database": fabric_database
                }
                
                for url in rest_urls:
                    try:
                        print(f"  Trying: {url}")
                        response = requests.post(url, 
                                               headers=headers, 
                                               json=test_query, 
                                               timeout=30)
                        
                        print(f"  Status: {response.status_code}")
                        
                        if response.status_code == 200:
                            print(f"✅ SUCCESS with REST API!")
                            print(f"   URL: {url}")
                            print(f"   Response: {response.text[:200]}...")
                            return True
                        else:
                            print(f"  Response: {response.text[:100]}...")
                            
                    except requests.exceptions.RequestException as e:
                        print(f"  Request failed: {str(e)}")
                        continue
                        
            except Exception as e:
                print(f"Token acquisition failed for {scope}: {e}")
                continue
        
        print("\\n❌ All REST API attempts failed")
        return False
        
    except Exception as e:
        print(f"❌ REST API test failed: {e}")
        return False

if __name__ == '__main__':
    test_fabric_rest_api()
