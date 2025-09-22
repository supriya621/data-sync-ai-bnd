"""
Production Redis Configuration and Monitoring
High-performance settings optimized for 25K+ row processing
"""

import os
import logging
from typing import Dict, Any
import time
from datetime import datetime
import json

class RedisPerformanceMonitor:
    """Performance monitoring and optimization for Redis operations"""
    
    def __init__(self, redis_service):
        self.redis_service = redis_service
        self.performance_metrics = {
            'cache_hits': 0,
            'cache_misses': 0,
            'total_queries': 0,
            'avg_response_time': 0,
            'peak_memory_usage': 0,
            'total_operations': 0
        }
        self.operation_timings = []
        self.logger = logging.getLogger(__name__)
    
    def record_operation(self, operation_type: str, duration_ms: float, cache_hit: bool = False):
        """Record performance metrics for each Redis operation"""
        self.performance_metrics['total_operations'] += 1
        self.performance_metrics['total_queries'] += 1
        
        if cache_hit:
            self.performance_metrics['cache_hits'] += 1
        else:
            self.performance_metrics['cache_misses'] += 1
        
        self.operation_timings.append(duration_ms)
        
        # Update average response time (rolling average)
        if len(self.operation_timings) > 1000:  # Keep last 1000 operations
            self.operation_timings = self.operation_timings[-1000:]
        
        self.performance_metrics['avg_response_time'] = sum(self.operation_timings) / len(self.operation_timings)
        
        # Log slow operations
        if duration_ms > 100:  # Log operations slower than 100ms
            self.logger.warning(f"Slow Redis operation: {operation_type} took {duration_ms:.2f}ms")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        total_queries = self.performance_metrics['total_queries']
        cache_hit_rate = (self.performance_metrics['cache_hits'] / total_queries * 100) if total_queries > 0 else 0
        
        return {
            'cache_performance': {
                'hit_rate_percentage': round(cache_hit_rate, 2),
                'total_hits': self.performance_metrics['cache_hits'],
                'total_misses': self.performance_metrics['cache_misses'],
                'total_operations': self.performance_metrics['total_operations']
            },
            'response_times': {
                'average_ms': round(self.performance_metrics['avg_response_time'], 2),
                'recent_operations': len(self.operation_timings),
                'performance_grade': self._get_performance_grade()
            },
            'optimization_status': {
                'redis_connected': self.redis_service.is_connected,
                'fallback_cache_size': len(self.redis_service.fallback_cache),
                'recommended_actions': self._get_optimization_recommendations()
            },
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_performance_grade(self) -> str:
        """Get performance grade based on metrics"""
        avg_time = self.performance_metrics['avg_response_time']
        hit_rate = (self.performance_metrics['cache_hits'] / self.performance_metrics['total_queries'] * 100) if self.performance_metrics['total_queries'] > 0 else 0
        
        if avg_time < 10 and hit_rate > 90:
            return "A+ (Excellent)"
        elif avg_time < 20 and hit_rate > 80:
            return "A (Very Good)"
        elif avg_time < 50 and hit_rate > 70:
            return "B (Good)"
        elif avg_time < 100 and hit_rate > 50:
            return "C (Fair)"
        else:
            return "D (Needs Optimization)"
    
    def _get_optimization_recommendations(self) -> list:
        """Get optimization recommendations"""
        recommendations = []
        
        hit_rate = (self.performance_metrics['cache_hits'] / self.performance_metrics['total_queries'] * 100) if self.performance_metrics['total_queries'] > 0 else 0
        avg_time = self.performance_metrics['avg_response_time']
        
        if hit_rate < 80:
            recommendations.append("Consider increasing cache TTL for frequently accessed data")
        
        if avg_time > 50:
            recommendations.append("Check Redis server performance and network latency")
        
        if not self.redis_service.is_connected:
            recommendations.append("Redis connection issue - check server status")
        
        if len(self.redis_service.fallback_cache) > 1000:
            recommendations.append("Large fallback cache - consider Redis optimization")
        
        if not recommendations:
            recommendations.append("Performance is optimal - no action needed")
        
        return recommendations

# Production Redis Configuration Class
class ProductionRedisConfig:
    """Production-optimized Redis configuration"""
    
    @staticmethod
    def get_production_settings():
        """Get production Redis settings"""
        return {
            # Connection settings
            'REDIS_HOST': os.getenv('REDIS_HOST', 'localhost'),
            'REDIS_PORT': int(os.getenv('REDIS_PORT', 6379)),
            'REDIS_DB': int(os.getenv('REDIS_DB', 0)),
            'REDIS_PASSWORD': os.getenv('REDIS_PASSWORD'),
            
            # Performance settings
            'REDIS_MAX_CONNECTIONS': int(os.getenv('REDIS_MAX_CONNECTIONS', 20)),
            'REDIS_CONNECTION_TIMEOUT': int(os.getenv('REDIS_CONNECTION_TIMEOUT', 5)),
            'REDIS_SOCKET_TIMEOUT': int(os.getenv('REDIS_SOCKET_TIMEOUT', 5)),
            
            # Cache TTL settings optimized for 25K+ rows processing
            'CACHE_TTL': {
                'validation_rules': 3600,      # 1 hour - rules rarely change
                'user_sessions': 7200,         # 2 hours - longer for production
                'file_metadata': 1800,         # 30 minutes - file processing
                'user_profiles': 3600,         # 1 hour - user data
                'template_configs': 14400,     # 4 hours - template stability
                'processing_state': 3600,      # 1 hour - longer workflow support
                'validation_results': 1800     # 30 minutes - validation caching
            },
            
            # Memory optimization
            'REDIS_MEMORY_POLICY': 'allkeys-lru',  # Evict least recently used keys
            'REDIS_MAX_MEMORY': os.getenv('REDIS_MAX_MEMORY', '256mb'),
            
            # Monitoring
            'ENABLE_PERFORMANCE_MONITORING': os.getenv('ENABLE_PERFORMANCE_MONITORING', 'true').lower() == 'true',
            'LOG_SLOW_OPERATIONS': os.getenv('LOG_SLOW_OPERATIONS', 'true').lower() == 'true',
            'PERFORMANCE_LOG_THRESHOLD_MS': int(os.getenv('PERFORMANCE_LOG_THRESHOLD_MS', 100))
        }
    
    @staticmethod
    def validate_configuration():
        """Validate Redis configuration"""
        config = ProductionRedisConfig.get_production_settings()
        issues = []
        
        # Check Redis connection details
        if not config['REDIS_HOST']:
            issues.append("REDIS_HOST not configured")
        
        if config['REDIS_PORT'] < 1 or config['REDIS_PORT'] > 65535:
            issues.append("Invalid REDIS_PORT")
        
        # Check memory settings
        try:
            max_memory = config['REDIS_MAX_MEMORY']
            if max_memory and not max_memory.endswith(('mb', 'gb', 'kb')):
                issues.append("REDIS_MAX_MEMORY should end with mb/gb/kb")
        except:
            issues.append("Invalid REDIS_MAX_MEMORY format")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'config': config
        }

# Performance optimization utilities
class CacheOptimizer:
    """Utilities for optimizing cache performance"""
    
    @staticmethod
    def optimize_for_large_files():
        """Optimization settings for 25K+ row file processing"""
        return {
            'bulk_cache_operations': True,
            'batch_size': 1000,  # Process in batches for memory efficiency
            'compression_enabled': True,  # Compress large data structures
            'parallel_processing': True,  # Use parallel cache operations
            'prefetch_rules': True,  # Pre-load validation rules
            'session_persistence': True  # Maintain session across steps
        }
    
    @staticmethod
    def get_memory_usage_estimate(row_count: int, column_count: int) -> Dict[str, str]:
        """Estimate memory usage for file processing"""
        
        # Rough estimates based on typical data sizes
        bytes_per_cell = 50  # Average bytes per cell (including overhead)
        total_data_bytes = row_count * column_count * bytes_per_cell
        
        # Cache overhead (metadata, Redis structures, etc.)
        cache_overhead = total_data_bytes * 0.3
        
        total_memory = total_data_bytes + cache_overhead
        
        # Convert to human readable
        def format_bytes(bytes_val):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_val < 1024.0:
                    return f"{bytes_val:.1f}{unit}"
                bytes_val /= 1024.0
            return f"{bytes_val:.1f}TB"
        
        return {
            'raw_data_size': format_bytes(total_data_bytes),
            'cache_overhead': format_bytes(cache_overhead),
            'total_memory_estimate': format_bytes(total_memory),
            'recommended_redis_memory': format_bytes(total_memory * 2),  # 2x for safety
            'processing_feasible': total_memory < 1024 * 1024 * 1024  # < 1GB
        }

# Export production utilities
__all__ = [
    'RedisPerformanceMonitor',
    'ProductionRedisConfig', 
    'CacheOptimizer'
]
