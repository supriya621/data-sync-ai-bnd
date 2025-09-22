#!/usr/bin/env python3
"""Test Microsoft Fabric SQL Connection"""

import os
from dotenv import load_dotenv
import pyodbc

load_dotenv()

def test_fabric_connection():
    """Test the Microsoft Fabric SQL connection"""
    
    print("🔍 Testing Microsoft Fabric SQL Connection...")
    
    # Get credentials from .env
    client_id = os.getenv('AZURE_CLIENT_ID')
    tenant_id = os.getenv('AZURE_TENANT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    server = os.getenv('FABRIC_SERVER')
    database = os.getenv('FABRIC_DATABASE')
    
    print(f"📡 Server: {server}")
    print(f"🗄️  Database: {database}")
    print(f"🔑 Client ID: {client_id}")
    print(f"🏢 Tenant ID: {tenant_id}")
    
    # Build connection string
    connection_string = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={server};"
        f"Database={database};"
        f"Authentication=ActiveDirectoryServicePrincipal;"
        f"UID={client_id};"
        f"PWD={client_secret};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=30;"
    )
    
    try:
        print("\n⏳ Attempting connection...")
        
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            
            # Test basic query
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()[0]
            print(f"✅ Connection successful!")
            print(f"📊 SQL Server Version: {version[:100]}...")
            
            # Test login_details table
            cursor.execute("SELECT COUNT(*) FROM login_details")
            user_count = cursor.fetchone()[0]
            print(f"👥 Users in database: {user_count}")
            
            # List some users (first 3 emails only)
            cursor.execute("SELECT TOP 3 email, role FROM login_details ORDER BY created_at DESC")
            users = cursor.fetchall()
            print("\n📋 Recent users:")
            for user in users:
                print(f"   - {user[0]} ({user[1]})")
                
    except pyodbc.Error as e:
        print(f"❌ Connection failed!")
        print(f"🔥 Error: {e}")
        
        if "TCP Provider" in str(e):
            print("\n🔧 Troubleshooting TCP Provider Error:")
            print("   1. Check your internet connection")
            print("   2. Verify Fabric workspace is active")
            print("   3. Check if your IP is whitelisted")
            print("   4. Try restarting the Fabric SQL endpoint")
            
        elif "Authentication" in str(e):
            print("\n🔧 Troubleshooting Authentication Error:")
            print("   1. Verify Service Principal credentials")
            print("   2. Check if Service Principal has database access")
            print("   3. Ensure tenant ID is correct")
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    test_fabric_connection()
