"""
Database Initialization Script for Data Sync AI
Creates users table and default admin user in DuckDB
"""

import os
import sys
import bcrypt
from datetime import datetime

# Add the backend directory to Python path  
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.duckdb_service import duckdb_service

def init_database():
    """Initialize database with users table and default admin"""
    
    print("🔧 Initializing Data Sync AI Database...")
    
    try:
        # Get the DuckDB connection directly
        conn = duckdb_service.connection
        
        # Create users table (matching exact structure from app_clean.py)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                email VARCHAR UNIQUE,
                password VARCHAR,
                first_name VARCHAR,
                last_name VARCHAR,
                mobile VARCHAR,
                is_approved BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Users table created successfully")
        
        # Create sequence for auto-incrementing IDs (start at 2 since admin is 1)
        try:
            conn.execute("CREATE SEQUENCE IF NOT EXISTS users_id_seq START 2")
            print("✅ Users ID sequence created successfully")
        except Exception as seq_error:
            print(f"ℹ️  Sequence already exists or not needed: {seq_error}")
            # This is not critical, we can manually manage IDs
            
        # Create templates table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                headers TEXT NOT NULL,
                rules TEXT NOT NULL,
                created_by VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        print("✅ Templates table created successfully")
            
        # Check if admin user exists
        check_admin = conn.execute("SELECT COUNT(*) FROM users WHERE email = 'admin@example.com'").fetchone()
        
        if check_admin[0] == 0:
            # Create default admin user (ID = 1, as expected by the app)
            admin_password = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            conn.execute("""
                INSERT INTO users (id, email, password, first_name, last_name, mobile, is_approved)
                VALUES (1, ?, ?, ?, ?, ?, TRUE)
            """, ('admin@example.com', admin_password, 'Admin', 'User', '1234567890'))
            
            print("✅ Default admin user created (ID: 1)")
            print("   📧 Email: admin@example.com")
            print("   🔑 Password: admin123")
        else:
            print("ℹ️  Admin user already exists")
            
        # Check if test user exists  
        check_user = conn.execute("SELECT COUNT(*) FROM users WHERE email = 'user@example.com'").fetchone()
        
        if check_user[0] == 0:
            user_password = bcrypt.hashpw('user123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            conn.execute("""
                INSERT INTO users (id, email, password, first_name, last_name, mobile, is_approved)
                VALUES (2, ?, ?, ?, ?, ?, TRUE)
            """, ('user@example.com', user_password, 'Test', 'User', '0987654321'))
            
            print("✅ Default test user created (ID: 2)")
            print("   📧 Email: user@example.com")
            print("   🔑 Password: user123")
        else:
            print("ℹ️  Test user already exists")
            
        # Show all users
        users = conn.execute("""
            SELECT id, email, first_name, last_name, is_approved 
            FROM users ORDER BY id
        """).fetchall()
        
        print("\n👥 Current Users:")
        for user_id, email, first_name, last_name, is_approved in users:
            status = "✅ Approved" if is_approved else "⏳ Pending"
            name = f"{first_name} {last_name}" if first_name and last_name else "No Name"
            role = "👑 Admin" if user_id == 1 else "👤 User"
            print(f"   • {name} ({email}) - {role} - {status}")
                
        print("\n🎉 Database initialization complete!")
        print("🚀 You can now login to your application")
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("⚠️  Important: Stop your Flask server (Ctrl+C) before running this script!")
    print("   This script needs exclusive access to initialize the database.\n")
    
    success = init_database()
    if success:
        print("\n✅ Ready to start your application!")
        print("Run: python run_app.py")
        print("\n🔐 Login Credentials:")
        print("Admin: admin@example.com / admin123")
        print("User:  user@example.com / user123")
    else:
        print("\n❌ Please fix the errors and try again")
