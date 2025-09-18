"""
Test SQL Fabric Connection
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.fabric_service import fabric_service

def test_fabric_connection():
    """Test SQL Fabric connection"""
    try:
        print("Testing SQL Fabric connection...")
        
        # Try to get a connection
        conn = fabric_service.get_connection()
        
        # Test with a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT 1 as test_value")
        result = cursor.fetchone()
        
        if result:
            print(f"✅ SQL Fabric connection successful!")
            print(f"   Test query result: {result[0]}")
            return True
        else:
            print("❌ SQL Fabric connection failed - no result from test query")
            return False
            
    except Exception as e:
        print(f"❌ SQL Fabric connection failed: {str(e)}")
        return False
    finally:
        try:
            fabric_service.close_connection()
        except:
            pass

if __name__ == '__main__':
    test_fabric_connection()
