"""
Test Azure/Microsoft Fabric connectivity
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_azure_endpoints():
    """Test connectivity to Azure endpoints"""
    endpoints = [
        "https://login.windows.net",
        "https://login.microsoftonline.com",
        "https://database.fabric.microsoft.com"
    ]
    
    for endpoint in endpoints:
        try:
            print(f"Testing {endpoint}...")
            response = requests.get(endpoint, timeout=10)
            print(f"✅ {endpoint} - Status: {response.status_code}")
        except requests.exceptions.Timeout:
            print(f"❌ {endpoint} - TIMEOUT")
        except requests.exceptions.ConnectionError as e:
            print(f"❌ {endpoint} - CONNECTION ERROR: {e}")
        except Exception as e:
            print(f"⚠️ {endpoint} - ERROR: {e}")

def test_fabric_server_connectivity():
    """Test direct connectivity to Fabric server"""
    fabric_server = os.getenv('FABRIC_SERVER')
    if fabric_server:
        server_host = fabric_server.split(',')[0]  # Remove port
        print(f"\nTesting Fabric server: {server_host}")
        
        import socket
        try:
            socket.setdefaulttimeout(10)
            result = socket.getaddrinfo(server_host, 1433)
            print(f"✅ Fabric server DNS resolution successful")
        except Exception as e:
            print(f"❌ Fabric server DNS/connectivity issue: {e}")

if __name__ == "__main__":
    print("=== Azure Connectivity Test ===")
    test_azure_endpoints()
    print("\n=== Fabric Server Connectivity ===")
    test_fabric_server_connectivity()
    
    print(f"\nCredentials being used:")
    print(f"AZURE_CLIENT_ID: {os.getenv('AZURE_CLIENT_ID')}")
    print(f"AZURE_TENANT_ID: {os.getenv('AZURE_TENANT_ID')}")
    print(f"FABRIC_SERVER: {os.getenv('FABRIC_SERVER')}")
    print(f"FABRIC_DATABASE: {os.getenv('FABRIC_DATABASE')}")
