"""
Simple Redis Connection Test
Tests if Redis is running and accessible
"""

import redis
import sys
import time

def test_redis_connection():
    """Test Redis connection with different configurations"""
    
    configurations = [
        {'host': 'localhost', 'port': 6379, 'db': 0},
        {'host': '127.0.0.1', 'port': 6379, 'db': 0},
    ]
    
    for config in configurations:
        try:
            print(f"Testing Redis connection: {config['host']}:{config['port']}")
            
            # Create Redis client
            r = redis.Redis(**config, socket_connect_timeout=5)
            
            # Test connection
            response = r.ping()
            
            if response:
                print("✅ Redis connection successful!")
                
                # Test basic operations
                r.set('test_key', 'test_value')
                value = r.get('test_key')
                
                if value and value.decode('utf-8') == 'test_value':
                    print("✅ Redis read/write operations successful!")
                    r.delete('test_key')  # Cleanup
                    return True
                else:
                    print("❌ Redis read/write test failed")
                    
        except redis.ConnectionError as e:
            print(f"❌ Redis connection failed: {e}")
        except Exception as e:
            print(f"❌ Redis test error: {e}")
    
    return False

def main():
    print("==========================================")
    print("     Data Sync AI - Redis Connection Test")
    print("==========================================")
    print()
    
    if test_redis_connection():
        print("\n🎉 Redis is ready for your Data Sync AI application!")
        print("\nYou can now run: python app_redis.py")
    else:
        print("\n⚠️ Redis is not running or not accessible")
        print("\nPlease start Redis server first:")
        print("- Option 1: Run quick_redis.bat")
        print("- Option 2: Run redis-server in a separate terminal")
        print("- Option 3: Start Docker Redis container")
    
    print("\nPress any key to exit...")
    input()

if __name__ == "__main__":
    main()
