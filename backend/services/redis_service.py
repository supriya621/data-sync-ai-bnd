"""
Redis Caching Service - High-Performance Caching Layer for Data Sync AI
Provides intelligent caching for validation rules, user sessions, file metadata, and more
"""

import redis
import json
import logging
from datetime import datetime, timedelta
from functools import wraps
import pickle
from typing import Any, Optional, Dict, List, Callable
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class RedisService:
    """High-performance Redis caching service with fallback mechanisms"""
    
    def __init__(self):
        self.redis_client = None
        self.is_connected = False
        self.fallback_cache = {}  # In-memory fallback cache
        
        # Redis configuration
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        self.redis_password = os.getenv('REDIS_PASSWORD', None)
        
        # Cache TTL settings (in seconds)
        self.DEFAULT_TTL = 3600  # 1 hour
        self.CACHE_TTL = {
            'validation_rules': 3600,      # 1 hour - validation rules rarely change
            'user_permissions': 1800,      # 30 minutes - user data
            'user_sessions': 86400,        # 24 hours - user sessions
            'file_metadata': 900,          # 15 minutes - file headers/metadata
            'template_configs': 7200,      # 2 hours - template configurations
            'rule_descriptions': 7200,     # 2 hours - rule descriptions
            'user_profiles': 3600,         # 1 hour - user profile data
            'processing_state': 1800       # 30 minutes - file processing state
        }
        
        self.connect()
    
    def connect(self):
        """Establish Redis connection with fallback support"""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                decode_responses=False,  # Handle binary data
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                max_connections=20
            )
            
            # Test connection
            self.redis_client.ping()
            self.is_connected = True
            logger.info(f"[SUCCESS] Redis connected: {self.redis_host}:{self.redis_port}")
            
        except Exception as e:
            logger.warning(f"❌ Redis connection failed: {e}")
            logger.info("📝 Using in-memory fallback cache")
            self.is_connected = False
    
    def _make_key(self, category: str, identifier: str) -> str:
        """Generate standardized cache key"""
        return f"datasync:{category}:{identifier}"
    
    def get(self, key: str, default=None) -> Any:
        """Get value from cache with fallback"""
        try:
            if self.is_connected:
                value = self.redis_client.get(key)
                if value is not None:
                    return pickle.loads(value)
            
            # Fallback to in-memory cache
            return self.fallback_cache.get(key, default)
            
        except Exception as e:
            logger.warning(f"Redis GET error: {e}")
            return self.fallback_cache.get(key, default)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL"""
        try:
            ttl = ttl or self.DEFAULT_TTL
            serialized_value = pickle.dumps(value)
            
            if self.is_connected:
                self.redis_client.setex(key, ttl, serialized_value)
                
            # Also store in fallback cache
            self.fallback_cache[key] = value
            
            return True
            
        except Exception as e:
            logger.warning(f"Redis SET error: {e}")
            # Store only in fallback cache
            self.fallback_cache[key] = value
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            if self.is_connected:
                self.redis_client.delete(key)
            
            self.fallback_cache.pop(key, None)
            return True
            
        except Exception as e:
            logger.warning(f"Redis DELETE error: {e}")
            self.fallback_cache.pop(key, None)
            return False
    
    def get_or_set(self, key: str, callable_func: Callable, ttl: Optional[int] = None) -> Any:
        """Get from cache or execute function and cache result"""
        # Try to get from cache first
        cached_value = self.get(key)
        if cached_value is not None:
            logger.debug(f"[TARGET] Cache HIT: {key}")
            return cached_value
        
        # Cache miss - execute function and cache result
        logger.debug(f"❌ Cache MISS: {key}")
        result = callable_func()
        if result is not None:
            self.set(key, result, ttl)
        
        return result
    
    def cache_validation_rules(self, rules_data: Dict) -> bool:
        """Cache validation rules with optimized TTL"""
        key = self._make_key("validation", "rules")
        return self.set(key, rules_data, self.CACHE_TTL['validation_rules'])
    
    def get_validation_rules(self) -> Optional[Dict]:
        """Get cached validation rules"""
        key = self._make_key("validation", "rules")
        return self.get(key)
    
    def cache_user_session(self, user_id: int, session_data: Dict) -> bool:
        """Cache user session data"""
        key = self._make_key("session", str(user_id))
        return self.set(key, session_data, self.CACHE_TTL['user_sessions'])
    
    def get_user_session(self, user_id: int) -> Optional[Dict]:
        """Get cached user session"""
        key = self._make_key("session", str(user_id))
        return self.get(key)
    
    def cache_file_metadata(self, session_id: str, metadata: Dict) -> bool:
        """Cache file processing metadata"""
        key = self._make_key("file_meta", session_id)
        return self.set(key, metadata, self.CACHE_TTL['file_metadata'])
    
    def get_file_metadata(self, session_id: str) -> Optional[Dict]:
        """Get cached file metadata"""
        key = self._make_key("file_meta", session_id)
        return self.get(key)
    
    def cache_user_profile(self, email: str, user_data: Dict) -> bool:
        """Cache user profile data"""
        key = self._make_key("user", email.lower())
        return self.set(key, user_data, self.CACHE_TTL['user_profiles'])
    
    def get_user_profile(self, email: str) -> Optional[Dict]:
        """Get cached user profile"""
        key = self._make_key("user", email.lower())
        return self.get(key)
    
    def invalidate_user_cache(self, email: str) -> bool:
        """Invalidate user-related cache entries"""
        user_key = self._make_key("user", email.lower())
        return self.delete(user_key)
    
    def cache_template_config(self, template_id: int, config_data: Dict) -> bool:
        """Cache template configuration"""
        key = self._make_key("template", str(template_id))
        return self.set(key, config_data, self.CACHE_TTL['template_configs'])
    
    def get_template_config(self, template_id: int) -> Optional[Dict]:
        """Get cached template configuration"""
        key = self._make_key("template", str(template_id))
        return self.get(key)
    
    def cache_processing_state(self, user_id: int, state_data: Dict) -> bool:
        """Cache multi-step processing state"""
        key = self._make_key("processing", str(user_id))
        return self.set(key, state_data, self.CACHE_TTL['processing_state'])
    
    def get_processing_state(self, user_id: int) -> Optional[Dict]:
        """Get cached processing state"""
        key = self._make_key("processing", str(user_id))
        return self.get(key)
    
    def clear_processing_state(self, user_id: int) -> bool:
        """Clear processing state cache"""
        key = self._make_key("processing", str(user_id))
        return self.delete(key)
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        stats = {
            'redis_connected': self.is_connected,
            'fallback_cache_size': len(self.fallback_cache),
            'redis_host': self.redis_host,
            'redis_port': self.redis_port
        }
        
        if self.is_connected:
            try:
                info = self.redis_client.info()
                stats.update({
                    'redis_memory_used': info.get('used_memory_human', 'N/A'),
                    'redis_connected_clients': info.get('connected_clients', 0),
                    'redis_total_commands': info.get('total_commands_processed', 0)
                })
            except Exception as e:
                logger.warning(f"Could not get Redis stats: {e}")
        
        return stats
    
    def flush_all(self) -> bool:
        """Clear all cache entries (use with caution)"""
        try:
            if self.is_connected:
                self.redis_client.flushdb()
            
            self.fallback_cache.clear()
            logger.info("🧹 All cache entries cleared")
            return True
            
        except Exception as e:
            logger.error(f"Error flushing cache: {e}")
            return False

# Global Redis service instance
redis_service = RedisService()

def cache_result(category: str, ttl: Optional[int] = None, key_func: Optional[Callable] = None):
    """Decorator for caching function results"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                func_name = func.__name__
                args_str = '_'.join(str(arg) for arg in args if isinstance(arg, (str, int, float)))
                cache_key = redis_service._make_key(category, f"{func_name}_{args_str}")
            
            # Try to get from cache
            return redis_service.get_or_set(cache_key, lambda: func(*args, **kwargs), ttl)
        
        return wrapper
    return decorator

def invalidate_cache(category: str, identifier: str) -> bool:
    """Utility function to invalidate specific cache entries"""
    key = redis_service._make_key(category, identifier)
    return redis_service.delete(key)

# Performance monitoring decorator
def monitor_performance(func_name: str = None):
    """Decorator to monitor function performance with caching"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            result = func(*args, **kwargs)
            end_time = datetime.now()
            
            execution_time = (end_time - start_time).total_seconds() * 1000  # ms
            
            name = func_name or func.__name__
            logger.info(f"[FAST] {name} executed in {execution_time:.2f}ms")
            
            return result
        return wrapper
    return decorator
