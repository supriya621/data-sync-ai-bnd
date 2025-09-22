#!/usr/bin/env python3
"""Create admin user if connection works"""

import os
from dotenv import load_dotenv
import pyodbc
import bcrypt
from datetime import datetime

load_dotenv()

def create_admin_user():
    """Create admin@example.com user if it doesn't exist"""
    
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    server = os.getenv('FABRIC_SERVER')
    database = os.getenv('FABRIC_DATABASE')
    
    connection_string = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={server};"
        f"Database={database};"
        f"Authentication=ActiveDirectoryServicePrincipal;"
        f"UID={client_id};"
        f"PWD={client_secret};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
    )
    
    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            
            # Check if admin user exists
            cursor.execute("SELECT COUNT(*) FROM login_details WHERE email = 'admin@example.com'")
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                print("✅ admin@example.com already exists!")
                return
                
            # Create admin user
            password_hash = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            cursor.execute("""
                INSERT INTO login_details (email, password_hash, first_name, last_name, mobile, role, is_approved, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'admin@example.com',
                password_hash,
                'Admin',
                'User', 
                '1234567890',
                'admin',
                1,  # approved
                datetime.utcnow()
            ))
            
            conn.commit()
            print("✅ Created admin@example.com with password: admin123")
            
    except Exception as e:
        print(f"❌ Failed to create admin user: {e}")

if __name__ == "__main__":
    create_admin_user()
