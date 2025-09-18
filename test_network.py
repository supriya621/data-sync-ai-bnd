"""
Test network connectivity to Fabric SQL endpoint
"""

import socket
import os
from dotenv import load_dotenv

load_dotenv()

def test_fabric_connectivity():
    """Test if we can reach the Fabric SQL endpoint"""
    
    fabric_server = os.getenv('FABRIC_SERVER')
    if not fabric_server:
        print("❌ FABRIC_SERVER not found in environment")
        return False
    
    # Extract hostname and port
    if ',' in fabric_server:
        hostname, port = fabric_server.split(',')
        port = int(port)
    else:
        hostname = fabric_server
        port = 1433
    
    print(f"Testing connection to: {hostname}:{port}")
    
    try:
        # Test TCP connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((hostname, port))
        sock.close()
        
        if result == 0:
            print(f"✅ Network connection successful to {hostname}:{port}")
            return True
        else:
            print(f"❌ Network connection failed to {hostname}:{port}")
            print(f"   Error code: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Network test failed: {e}")
        return False

if __name__ == '__main__':
    test_fabric_connectivity()
