"""
Enhanced Fabric Service with Redis Caching Integration
High-performance caching layer for Microsoft Fabric SQL operations
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import time

from .fabric_service import FabricSQLService
from .redis_service import redis_service, cache_result, monitor_performance

logger = logging.getLogger(__name__)

class CachedFabricService(FabricSQLService):
    """Enhanced Fabric Service with intelligent Redis caching"""
    
    def __init__(self):
        super().__init__()
        self.cache = redis_service
        logger.info("[START] CachedFabricService initialized with Redis support")
    
    @monitor_performance("get_validation_rules")
    def get_validation_rules_cached(self) -> Dict[str, Any]:
        """Get validation rules with Redis caching"""
        
        def fetch_rules_from_db():
            """Fetch validation rules from database"""
            logger.debug("🔍 Fetching validation rules from SQL Fabric...")
            return self._get_validation_rules_from_db()
        
        # Try cache first, fallback to DB
        cached_rules = self.cache.get_validation_rules()
        if cached_rules is not None:
            logger.debug("[TARGET] Cache HIT: validation_rules")
            return cached_rules
        
        # Cache miss - fetch from DB and cache
        logger.debug("❌ Cache MISS: validation_rules - fetching from DB")
        rules = fetch_rules_from_db()
        
        if rules:
            self.cache.cache_validation_rules(rules)
            logger.debug("[SAVE] Validation rules cached successfully")
        
        return rules
    
    def _get_validation_rules_from_db(self) -> Dict[str, Any]:
        """Internal method to fetch validation rules from database"""
        try:
            # Use parent class method to get rules
            rules_result = self.execute_query("""
                SELECT rule_name, description, parameters, is_active, is_custom
                FROM validation_rule_types 
                WHERE is_active = 1
                ORDER BY rule_name
            """)
            
            if not rules_result:
                return self._get_default_validation_rules()
            
            rules_dict = {}
            for rule in rules_result:
                rules_dict[rule['rule_name']] = {
                    'name': rule['rule_name'],
                    'description': rule['description'],
                    'parameters': rule.get('parameters', '{}'),
                    'is_custom': rule.get('is_custom', False)
                }
            
            return rules_dict
            
        except Exception as e:
            logger.warning(f"Error fetching rules from DB: {e}")
            return self._get_default_validation_rules()
    
    def _get_default_validation_rules(self) -> Dict[str, Any]:
        """Get default validation rules as fallback"""
        return {
            'Required': {
                'name': 'Required',
                'description': 'Ensures the field is not null',
                'parameters': '{"allow_null": false}',
                'is_custom': False
            },
            'Int': {
                'name': 'Int', 
                'description': 'Validates integer format',
                'parameters': '{"format": "integer"}',
                'is_custom': False
            },
            'Float': {
                'name': 'Float',
                'description': 'Validates number format (integer or decimal)', 
                'parameters': '{"format": "float"}',
                'is_custom': False
            },
            'Text': {
                'name': 'Text',
                'description': 'Allows text with quotes and parentheses',
                'parameters': '{"allow_special": false}',
                'is_custom': False
            },
            'Email': {
                'name': 'Email',
                'description': 'Validates email format',
                'parameters': '{"regex": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\\\.[a-zA-Z0-9-.]+$"}',
                'is_custom': False
            },
            'Date': {
                'name': 'Date',
                'description': 'Validates date format',
                'parameters': '{"format": "%d-%m-%Y"}',
                'is_custom': False
            },
            'Boolean': {
                'name': 'Boolean',
                'description': 'Validates boolean format (true/false or 0/1)',
                'parameters': '{"format": "boolean"}',
                'is_custom': False
            },
            'Alphanumeric': {
                'name': 'Alphanumeric',
                'description': 'Validates alphanumeric format',
                'parameters': '{"format": "alphanumeric"}',
                'is_custom': False
            }
        }
    
    @monitor_performance("get_user_by_email")
    def get_user_by_email_cached(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email with Redis caching"""
        
        def fetch_user_from_db():
            """Fetch user from database"""
            logger.debug(f"🔍 Fetching user from SQL Fabric: {email}")
            return super(CachedFabricService, self).get_user_by_email(email)
        
        # Try cache first
        cached_user = self.cache.get_user_profile(email)
        if cached_user is not None:
            logger.debug(f"[TARGET] Cache HIT: user_{email}")
            return cached_user
        
        # Cache miss - fetch from DB
        logger.debug(f"❌ Cache MISS: user_{email} - fetching from DB")
        user = fetch_user_from_db()
        
        if user:
            self.cache.cache_user_profile(email, user)
            logger.debug(f"[SAVE] User profile cached: {email}")
        
        return user
    
    @monitor_performance("bulk_insert_file_data")
    def bulk_insert_file_data_optimized(self, df, session_id: str, template_id: int) -> Dict[str, Any]:
        """Optimized bulk insert with performance monitoring and metadata caching"""
        start_time = time.time()
        
        try:
            # Cache file metadata for faster subsequent access
            metadata = {
                'session_id': session_id,
                'template_id': template_id,
                'row_count': len(df),
                'columns': df.columns.tolist(),
                'cached_at': datetime.now().isoformat()
            }
            
            self.cache.cache_file_metadata(session_id, metadata)
            
            # Execute the actual bulk insert using parent method
            result = super().bulk_insert_file_data(df, session_id, template_id)
            
            processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            logger.info(f"[FAST] Bulk insert completed: {len(df)} rows in {processing_time:.2f}ms")
            
            return {
                'success': True,
                'rows_inserted': len(df),
                'processing_time_ms': processing_time,
                'cached_metadata': True
            }
            
        except Exception as e:
            logger.error(f"Bulk insert error: {e}")
            raise
    
    @monitor_performance("validate_data_in_sql_fabric")
    def validate_data_with_caching(self, session_id: str, template_id: int, rules_config: Dict) -> Dict[str, Any]:
        """Enhanced data validation with cached rules and optimized performance"""
        start_time = time.time()
        
        try:
            # Get cached validation rules (much faster than DB query)
            cached_rules = self.get_validation_rules_cached()
            
            # Get cached file metadata
            file_metadata = self.cache.get_file_metadata(session_id)
            if file_metadata:
                logger.debug(f"[TARGET] Using cached file metadata: {file_metadata['row_count']} rows")
            
            # Execute validation using parent method
            validation_result = super().validate_data_in_sql_fabric(session_id, template_id, rules_config)
            
            processing_time = (time.time() - start_time) * 1000
            
            # Cache validation results for potential re-runs
            validation_cache_key = f"validation_{session_id}_{template_id}"
            validation_summary = {
                'total_errors': validation_result.get('total_errors', 0),
                'error_types': len(validation_result.get('error_cell_locations', {})),
                'validated_at': datetime.now().isoformat(),
                'processing_time_ms': processing_time
            }
            
            self.cache.set(
                self.cache._make_key("validation", validation_cache_key),
                validation_summary,
                ttl=900  # Cache validation results for 15 minutes
            )
            
            logger.info(f"[FAST] Data validation completed: {validation_result.get('total_errors', 0)} errors in {processing_time:.2f}ms")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            raise
    
    def invalidate_user_cache(self, email: str) -> bool:
        """Invalidate user cache when user data changes"""
        return self.cache.invalidate_user_cache(email)
    
    def invalidate_validation_rules_cache(self) -> bool:
        """Invalidate validation rules cache when rules are updated"""
        key = self.cache._make_key("validation", "rules")
        success = self.cache.delete(key)
        if success:
            logger.info("🧹 Validation rules cache invalidated")
        return success
    
    @monitor_performance("create_user")
    def create_user_with_cache_invalidation(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create user and manage cache appropriately"""
        try:
            # Create user using parent method
            new_user = super().create_user(user_data)
            
            # Cache the new user profile
            if new_user:
                email = user_data.get('email', '').lower()
                self.cache.cache_user_profile(email, new_user)
                logger.debug(f"[SAVE] New user profile cached: {email}")
            
            return new_user
            
        except Exception as e:
            logger.error(f"Create user error: {e}")
            raise
    
    def get_cache_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache performance statistics"""
        cache_stats = self.cache.get_cache_stats()
        
        return {
            'cache_service': 'Redis',
            'cache_status': 'Connected' if cache_stats['redis_connected'] else 'Fallback Mode',
            'redis_connection': {
                'host': cache_stats['redis_host'],
                'port': cache_stats['redis_port'],
                'connected': cache_stats['redis_connected']
            },
            'performance_metrics': {
                'fallback_cache_size': cache_stats['fallback_cache_size'],
                'redis_memory_used': cache_stats.get('redis_memory_used', 'N/A'),
                'connected_clients': cache_stats.get('redis_connected_clients', 0)
            },
            'cache_ttl_settings': self.cache.CACHE_TTL
        }

# Create the cached service instance
cached_fabric_service = CachedFabricService()
