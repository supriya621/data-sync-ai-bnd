"""
Quick Start Script for Data Sync AI
Uses DuckDB with optional Fabric SQL fallback
"""

import os
import sys
import logging

# Set UTF-8 encoding for Windows console
if sys.platform.startswith('win'):
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Fix logging encoding issue
import logging
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
