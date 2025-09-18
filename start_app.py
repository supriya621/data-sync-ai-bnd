"""
Enhanced App Runner with Auto Database Initialization
"""

import os
import sys
import logging
import bcrypt

# Set UTF-8 encoding for Windows console
if sys.platform.startswith('win'):
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Fix logging encoding issue
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('./logs/datasync.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Ensure directories exist
os.makedirs('./logs', exist_ok=True)
os.makedirs('./data', exist_ok=True)
os.makedirs('./uploads', exist_ok=True)
os.makedirs('./sessions', exist_ok=True)

print("🚀 Starting Data Sync AI...")
print("✅ Using DuckDB for data processing")
print("⚠️  SQL Fabric connection will be attempted but not required")

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.duckdb_service import duckdb_service

def auto_initialize_database():
    """Automatically initialize database with users on startup"""
    
    try:
        print("🔧 Auto-initializing database...")
        
        # Get the DuckDB connection
        conn = duckdb_service.connection
        
        # Create users table
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
        
        # Check if admin user exists
        check_admin = conn.execute("SELECT COUNT(*) FROM users WHERE email = 'admin@example.com'").fetchone()
        
        if check_admin[0] == 0:
            # Create default admin user
            admin_password = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            conn.execute("""
                INSERT INTO users (id, email, password, first_name, last_name, mobile, is_approved)
                VALUES (1, ?, ?, ?, ?, ?, TRUE)
            """, ('admin@example.com', admin_password, 'Admin', 'User', '1234567890'))
            
            print("✅ Default admin user created")
            
        # Check if test user exists  
        check_user = conn.execute("SELECT COUNT(*) FROM users WHERE email = 'user@example.com'").fetchone()
        
        if check_user[0] == 0:
            user_password = bcrypt.hashpw('user123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            conn.execute("""
                INSERT INTO users (id, email, password, first_name, last_name, mobile, is_approved)
                VALUES (2, ?, ?, ?, ?, ?, TRUE)
            """, ('user@example.com', user_password, 'Test', 'User', '0987654321'))
            
            print("✅ Default test user created")
        
        print("✅ Database ready with authentication")
        return True
        
    except Exception as e:
        print(f"❌ Auto-initialization failed: {str(e)}")
        return False

# Auto-initialize database
if auto_initialize_database():
    print("🔐 Login Credentials:")
    print("   Admin: admin@example.com / admin123")
    print("   User:  user@example.com / user123")
else:
    print("⚠️  Database initialization had issues, but continuing...")

# Import and run the clean application
from app_clean import app

if __name__ == '__main__':
    print(f"🌐 Server starting on http://localhost:5000")
    print("📁 Frontend should be running on http://localhost:5173")
    print("🛑 Press Ctrl+C to stop")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
