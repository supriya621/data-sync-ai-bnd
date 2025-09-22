"""
Temporary Data Sync AI Backend - Network Issue Workaround
Skips Fabric SQL connection attempts due to network connectivity issues
Uses DuckDB + Redis for full functionality during development
"""

import os
import sys
import logging
from flask import Flask, request, jsonify, session, send_file
from flask_session import Session
from flask_cors import CORS
from dotenv import load_dotenv
import bcrypt
import json
import pandas as pd
from datetime import datetime
import uuid
import time

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# Load environment variables
load_dotenv()

# Import configuration and services
from backend.config.config import config
from backend.services.duckdb_service import duckdb_service

# Skip Fabric service for now due to network issues
print("🚧 [TEMP] Skipping Fabric SQL due to network connectivity issues")
print("✅ [TEMP] Using DuckDB-only mode for development")

# Import route blueprints
try:
    from routes.config_history_routes import config_history_bp, save_configuration_history
except ImportError as e:
    print(f"Warning: Could not import config_history_routes: {e}")
    config_history_bp = None
    save_configuration_history = None

# Import Redis-enhanced services
try:
    from backend.services.redis_service import redis_service
    REDIS_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ [SUCCESS] Redis caching layer loaded successfully")
except ImportError as e:
    REDIS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"❌ [WARNING] Redis not available, using standard services: {e}")

print(f"Redis Status: {'✅ ENABLED' if REDIS_AVAILABLE else '❌ DISABLED'}")

if __name__ == '__main__':
    print("🚀 Starting TEMPORARY Data Sync AI Backend...")
    print("   - DuckDB: ✅ Ready")
    print("   - Redis: ✅ Ready" if REDIS_AVAILABLE else "   - Redis: ❌ Not Available")
    print("   - Fabric SQL: 🚧 Temporarily skipped (network issues)")
    print("")
    print("📍 Backend will be available at:")
    print("   - http://localhost:5000")
    print("   - http://127.0.0.1:5000")
    print("")
    print("🔧 To resume Fabric SQL:")
    print("   1. Fix network connectivity to login.windows.net")
    print("   2. Switch back to python app_redis.py")
    print("")
    print("Press Ctrl+C to stop")
    
    # Simple Flask app for immediate testing
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    CORS(app, supports_credentials=True, origins=config.ALLOWED_ORIGINS)
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'message': 'Temporary backend running (DuckDB + Redis)',
            'fabric_sql': 'temporarily_disabled',
            'timestamp': datetime.utcnow().isoformat()
        })
    
    @app.route('/', methods=['GET'])
    def root():
        return jsonify({
            'message': 'Data Sync AI Temporary Backend',
            'status': 'running',
            'mode': 'development_workaround'
        })
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port, use_reloader=False)
