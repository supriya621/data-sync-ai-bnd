"""
General API routes - status, health checks, system information
"""

import os
import logging
import platform
import psutil
from datetime import datetime
from flask import Blueprint, jsonify, request, current_app
from middleware.auth import login_required, admin_required
from core.database import get_database_status
from services.fabric_service import fabric_service
from services.duckdb_service import duckdb_service
from utils.session_utils import get_session_data

logger = logging.getLogger(__name__)

# Create blueprint
api_bp = Blueprint('api', __name__)

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Basic health check
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'environment': current_app.config.get('ENV', 'development')
        }
        
        # Check database connections
        try:
            db_status = get_database_status()
            health_status['databases'] = db_status
        except Exception as e:
            health_status['databases'] = {'error': str(e)}
            health_status['status'] = 'degraded'
        
        # Check disk space
        try:
            upload_folder = current_app.config['UPLOAD_FOLDER']
            disk_usage = psutil.disk_usage(upload_folder)
            health_status['disk_space'] = {
                'total_gb': round(disk_usage.total / (1024**3), 2),
                'used_gb': round(disk_usage.used / (1024**3), 2),
                'free_gb': round(disk_usage.free / (1024**3), 2),
                'usage_percent': round((disk_usage.used / disk_usage.total) * 100, 2)
            }
            
            # Warn if disk space is low
            if health_status['disk_space']['usage_percent'] > 90:
                health_status['status'] = 'warning'
                health_status['warnings'] = ['Low disk space']
        except Exception as e:
            health_status['disk_space'] = {'error': str(e)}
        
        return jsonify(health_status), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@api_bp.route('/status', methods=['GET'])
@login_required
def system_status():
    """Detailed system status for authenticated users"""
    try:
        status_info = {
            'system': {
                'platform': platform.system(),
                'platform_version': platform.version(),
                'python_version': platform.python_version(),
                'cpu_count': psutil.cpu_count(),
                'memory_total_gb': round(psutil.virtual_memory().total / (1024**3), 2),
                'memory_available_gb': round(psutil.virtual_memory().available / (1024**3), 2),
                'uptime_seconds': psutil.boot_time()
            },
            'application': {
                'upload_folder': current_app.config['UPLOAD_FOLDER'],
                'debug_mode': current_app.debug,
                'environment': current_app.config.get('ENV', 'development'),
                'session_data': get_session_data()
            },
            'databases': get_database_status(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify({
            'success': True,
            'status': status_info
        }), 200
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/config', methods=['GET'])
@admin_required
def get_configuration():
    """Get application configuration (admin only)"""
    try:
        from config.config import config
        
        # Safe configuration (exclude sensitive data)
        safe_config = {
            'flask': {
                'env': config.FLASK_ENV,
                'debug': config.DEBUG,
                'port': config.PORT
            },
            'file_processing': {
                'max_file_size_mb': config.MAX_FILE_SIZE_MB,
                'large_file_threshold': config.LARGE_FILE_THRESHOLD,
                'chunk_size': config.CHUNK_SIZE
            },
            'duckdb': {
                'memory_limit': config.DUCKDB_MEMORY_LIMIT,
                'threads': config.DUCKDB_THREADS,
                'path': config.DUCKDB_PATH
            },
            'logging': {
                'level': config.LOG_LEVEL,
                'file': config.LOG_FILE
            },
            'paths': {
                'upload_folder': config.UPLOAD_FOLDER,
                'session_file_dir': config.SESSION_FILE_DIR
            }
        }
        
        return jsonify({
            'success': True,
            'configuration': safe_config
        }), 200
        
    except Exception as e:
        logger.error(f"Configuration retrieval failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve configuration'
        }), 500

@api_bp.route('/statistics', methods=['GET'])
@login_required
def get_statistics():
    """Get usage statistics"""
    try:
        # Get user-specific statistics
        user_stats = fabric_service.execute_query("""
            SELECT 
                COUNT(DISTINCT et.template_id) as total_templates,
                COUNT(DISTINCT vh.history_id) as total_validations,
                SUM(vh.error_count) as total_errors_corrected,
                AVG(vh.processing_time_ms) as avg_processing_time_ms
            FROM excel_templates et
            LEFT JOIN validation_history vh ON et.template_id = vh.template_id
            WHERE et.user_id = ?
        """, (request.json.get('user_id') if request.is_json else None,))
        
        # Get system-wide statistics (if admin)
        system_stats = None
        if request.args.get('include_system') == 'true':
            try:
                system_stats = fabric_service.execute_query("""
                    SELECT 
                        COUNT(DISTINCT ld.id) as total_users,
                        COUNT(DISTINCT et.template_id) as total_templates,
                        COUNT(DISTINCT vh.history_id) as total_validations,
                        SUM(vh.error_count) as total_errors_corrected
                    FROM login_details ld
                    LEFT JOIN excel_templates et ON ld.id = et.user_id
                    LEFT JOIN validation_history vh ON et.template_id = vh.template_id
                """)
                system_stats = system_stats[0] if system_stats else {}
            except Exception:
                # User doesn't have admin privileges
                pass
        
        response_data = {
            'success': True,
            'user_statistics': user_stats[0] if user_stats else {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if system_stats:
            response_data['system_statistics'] = system_stats
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Statistics retrieval failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve statistics'
        }), 500

@api_bp.route('/cleanup', methods=['POST'])
@admin_required
def system_cleanup():
    """Clean up old files and data (admin only)"""
    try:
        cleanup_results = {
            'files_deleted': 0,
            'sessions_cleared': 0,
            'temp_data_cleared': 0
        }
        
        # Clean up old uploaded files (older than 30 days)
        import time
        cutoff_time = time.time() - (30 * 24 * 60 * 60)  # 30 days ago
        
        upload_folder = current_app.config['UPLOAD_FOLDER']
        for filename in os.listdir(upload_folder):
            file_path = os.path.join(upload_folder, filename)
            try:
                if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff_time:
                    # Check if file is referenced in database
                    refs = fabric_service.execute_query("""
                        SELECT COUNT(*) as count FROM excel_templates 
                        WHERE template_name = ? AND status = 'ACTIVE'
                    """, (filename,))
                    
                    if refs[0]['count'] == 0:
                        os.remove(file_path)
                        cleanup_results['files_deleted'] += 1
            except Exception as e:
                logger.warning(f"Failed to cleanup file {filename}: {e}")
        
        # Clean up old session files
        session_folder = current_app.config['SESSION_FILE_DIR']
        for filename in os.listdir(session_folder):
            session_file = os.path.join(session_folder, filename)
            try:
                if os.path.isfile(session_file) and os.path.getmtime(session_file) < cutoff_time:
                    os.remove(session_file)
                    cleanup_results['sessions_cleared'] += 1
            except Exception as e:
                logger.warning(f"Failed to cleanup session file {filename}: {e}")
        
        # Clean up old DuckDB temporary data
        try:
            duckdb_service.connection.execute("""
                DELETE FROM file_data 
                WHERE created_at < NOW() - INTERVAL 30 DAY
            """)
            duckdb_service.connection.execute("""
                DELETE FROM validation_results 
                WHERE created_at < NOW() - INTERVAL 30 DAY
            """)
            cleanup_results['temp_data_cleared'] = 1
        except Exception as e:
            logger.warning(f"Failed to cleanup DuckDB temp data: {e}")
        
        logger.info(f"System cleanup completed: {cleanup_results}")
        return jsonify({
            'success': True,
            'message': 'System cleanup completed',
            'results': cleanup_results
        }), 200
        
    except Exception as e:
        logger.error(f"System cleanup failed: {e}")
        return jsonify({
            'success': False,
            'error': 'System cleanup failed'
        }), 500

@api_bp.route('/logs', methods=['GET'])
@admin_required
def get_logs():
    """Get application logs (admin only)"""
    try:
        from config.config import config
        
        lines = int(request.args.get('lines', 100))
        level = request.args.get('level', 'INFO').upper()
        
        if not os.path.exists(config.LOG_FILE):
            return jsonify({
                'success': True,
                'logs': [],
                'message': 'Log file not found'
            }), 200
        
        # Read log file
        with open(config.LOG_FILE, 'r') as f:
            log_lines = f.readlines()
        
        # Filter by level and get last N lines
        filtered_lines = []
        for line in log_lines[-lines:]:
            if level in line or level == 'ALL':
                filtered_lines.append(line.strip())
        
        return jsonify({
            'success': True,
            'logs': filtered_lines,
            'total_lines': len(log_lines),
            'filtered_lines': len(filtered_lines)
        }), 200
        
    except Exception as e:
        logger.error(f"Log retrieval failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve logs'
        }), 500
