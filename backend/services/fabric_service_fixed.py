import pyodbc
import pandas as pd
import logging
import json
from azure.identity import ClientSecretCredential
from typing import Optional, Dict, Any, List, Tuple
import time
from backend.config.config import config

class FabricSQLService:
    """Service for Microsoft Fabric SQL operations with robust connection handling"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.connection = None
        self.credential = None
        self.last_connection_time = 0
        self.connection_timeout = 300  # 5 minutes - refresh connection after this time
        self.max_retries = 3
        self._setup_authentication()
    
    def _setup_authentication(self):
        """Setup Azure authentication"""
        try:
            self.credential = ClientSecretCredential(
                tenant_id=config.AZURE_TENANT_ID,
                client_id=config.AZURE_CLIENT_ID,
                client_secret=config.AZURE_CLIENT_SECRET
            )
            self.logger.info("Azure authentication configured successfully")
        except Exception as e:
            self.logger.error(f"Failed to setup Azure authentication: {str(e)}")
            raise
    
    def _is_connection_valid(self) -> bool:
        """Check if current connection is valid and not stale"""
        if self.connection is None:
            return False
        
        try:
            # Check if connection is closed
            if self.connection.closed:
                return False
            
            # Check connection age
            current_time = time.time()
            if current_time - self.last_connection_time > self.connection_timeout:
                self.logger.info("Connection is stale, will refresh")
                return False
            
            # Test connection with a simple query
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return True
            
        except Exception as e:
            self.logger.warning(f"Connection validation failed: {str(e)}")
            return False
    
    def _create_fresh_connection(self) -> pyodbc.Connection:
        """Create a new database connection"""
        server_no_port = config.FABRIC_SERVER.split(',')[0]
        
        connection_string = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={server_no_port};"
            f"DATABASE={config.FABRIC_DATABASE};"
            f"UID={config.AZURE_CLIENT_ID};"
            f"PWD={config.AZURE_CLIENT_SECRET};"
            f"Authentication=ActiveDirectoryServicePrincipal;"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
            f"LoginTimeout=120;"
        )
        
        self.logger.info("Creating fresh Fabric SQL connection...")
        connection = pyodbc.connect(connection_string)
        self.last_connection_time = time.time()
        self.logger.info("Fresh Fabric SQL connection established successfully!")
        return connection
    
    def get_connection(self) -> pyodbc.Connection:
        """Get valid database connection with automatic reconnection"""
        # If current connection is invalid, create a new one
        if not self._is_connection_valid():
            try:
                # Close old connection if it exists
                if self.connection:
                    try:
                        self.connection.close()
                    except:
                        pass  # Ignore errors when closing broken connection
                
                # Create fresh connection
                self.connection = self._create_fresh_connection()
                
            except Exception as e:
                self.logger.error(f"Failed to establish Fabric SQL connection: {str(e)}")
                raise
        
        return self.connection
    
    def _execute_with_retry(self, query: str, params: Optional[tuple] = None, fetch_results: bool = True):
        """Execute query with automatic retry on connection failures"""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                if fetch_results:
                    # Get column names and results
                    columns = [column[0] for column in cursor.description]
                    results = []
                    for row in cursor.fetchall():
                        results.append(dict(zip(columns, row)))
                    
                    cursor.close()
                    self.logger.debug(f"Query executed successfully, returned {len(results)} rows")
                    return results
                else:
                    # For non-query operations (INSERT, UPDATE, DELETE)
                    rows_affected = cursor.rowcount
                    conn.commit()
                    cursor.close()
                    self.logger.debug(f"Non-query executed successfully, {rows_affected} rows affected")
                    return rows_affected
                    
            except Exception as e:
                last_exception = e
                error_str = str(e)
                
                # Check if it's a connection-related error
                if any(error_code in error_str for error_code in ['08S01', '10054', 'Communication link failure', 'Connection was forcibly closed']):
                    self.logger.warning(f"Connection error on attempt {attempt + 1}: {error_str}")
                    
                    # Mark connection as invalid so next get_connection() will create a fresh one
                    self.connection = None
                    
                    if attempt < self.max_retries - 1:
                        self.logger.info(f"Retrying query (attempt {attempt + 2}/{self.max_retries})...")
                        time.sleep(1)  # Brief pause before retry
                        continue
                else:
                    # Non-connection error, don't retry
                    self.logger.error(f"Query execution failed (non-connection error): {error_str}")
                    raise
        
        # All retries failed
        self.logger.error(f"Query failed after {self.max_retries} attempts. Last error: {str(last_exception)}")
        raise last_exception
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute SELECT query and return results with automatic retry"""
        return self._execute_with_retry(query, params, fetch_results=True)
    
    def execute_non_query(self, query: str, params: Optional[tuple] = None) -> int:
        """Execute INSERT, UPDATE, DELETE queries with automatic retry"""
        return self._execute_with_retry(query, params, fetch_results=False)
    
    def test_connection(self) -> Dict[str, Any]:
        """Test database connection and return status"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 as test_result")
            result = cursor.fetchone()
            cursor.close()
            
            return {
                "status": "success",
                "message": "Fabric SQL connection is healthy",
                "test_result": result[0] if result else None,
                "connection_age": time.time() - self.last_connection_time
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Fabric SQL connection failed: {str(e)}"
            }
    
    def close_connection(self):
        """Close database connection"""
        if self.connection:
            try:
                self.connection.close()
                self.logger.info("Fabric SQL connection closed successfully")
            except Exception as e:
                self.logger.warning(f"Error closing connection: {str(e)}")
            finally:
                self.connection = None
    
    # User Management Methods (with retry support)
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email address"""
        try:
            query = """
            SELECT id, email, password_hash, first_name, last_name, is_active, created_date, last_login
            FROM login_details 
            WHERE email = ?
            """
            results = self.execute_query(query, (email,))
            return results[0] if results else None
        except Exception as e:
            self.logger.error(f"Error getting user by email: {str(e)}")
            raise
    
    def create_user(self, email: str, password_hash: str, first_name: str, last_name: str) -> int:
        """Create a new user"""
        try:
            query = """
            INSERT INTO login_details (email, password_hash, first_name, last_name, is_active, created_date) 
            VALUES (?, ?, ?, ?, 1, GETDATE())
            """
            self.execute_non_query(query, (email, password_hash, first_name, last_name))
            
            # Get the new user's ID
            user = self.get_user_by_email(email)
            return user['id'] if user else None
        except Exception as e:
            self.logger.error(f"Error creating user: {str(e)}")
            raise
    
    def update_last_login(self, user_id: int):
        """Update user's last login timestamp"""
        try:
            query = "UPDATE login_details SET last_login = GETDATE() WHERE id = ?"
            self.execute_non_query(query, (user_id,))
        except Exception as e:
            self.logger.error(f"Error updating last login: {str(e)}")
            raise
    
    # Template Management Methods (with retry support)
    def save_template(self, template_data: Dict[str, Any]) -> int:
        """Save Excel template configuration"""
        try:
            query = """
            INSERT INTO excel_templates (name, description, created_date, template_config) 
            VALUES (?, ?, GETDATE(), ?)
            """
            self.execute_non_query(query, (
                template_data['name'],
                template_data.get('description', ''),
                json.dumps(template_data.get('config', {}))
            ))
            
            # Get the new template ID
            get_id_query = "SELECT TOP 1 id FROM excel_templates WHERE name = ? ORDER BY created_date DESC"
            results = self.execute_query(get_id_query, (template_data['name'],))
            return results[0]['id'] if results else None
        except Exception as e:
            self.logger.error(f"Error saving template: {str(e)}")
            raise
    
    def get_templates(self) -> List[Dict[str, Any]]:
        """Get all template configurations"""
        try:
            query = """
            SELECT id, name, description, created_date, template_config
            FROM excel_templates 
            ORDER BY created_date DESC
            """
            return self.execute_query(query)
        except Exception as e:
            self.logger.error(f"Error getting templates: {str(e)}")
            raise
    
    # Validation Rules Methods (with retry support)
    def get_validation_rules(self) -> List[Dict[str, Any]]:
        """Get all validation rules"""
        try:
            query = """
            SELECT id, name, description, parameters, created_date, is_active
            FROM validation_rule_types 
            WHERE is_active = 1
            ORDER BY name
            """
            return self.execute_query(query)
        except Exception as e:
            self.logger.error(f"Error getting validation rules: {str(e)}")
            raise
    
    def ensure_default_validation_rules(self):
        """Ensure default validation rules exist in the database"""
        try:
            # Check existing rules
            existing_rules = self.get_validation_rules()
            existing_names = {rule['name'] for rule in existing_rules}
            
            if len(existing_rules) >= 8:
                self.logger.info(f"Default validation rules already exist ({len(existing_rules)} found)")
                
                # Debug: Show current rules
                self.logger.info("DEBUGGING - Current validation rules in DB:")
                for rule in existing_rules:
                    self.logger.info(f"  ID: {rule['id']}, Name: {rule['name']}")
                return existing_rules
            
            # Define default rules
            default_rules = [
                {'name': 'Required', 'description': 'Ensures the field is not null', 'parameters': '{"allow_null": false}'},
                {'name': 'Int', 'description': 'Validates integer format', 'parameters': '{"format": "integer"}'},
                {'name': 'Float', 'description': 'Validates number format (integer or decimal)', 'parameters': '{"format": "float"}'},
                {'name': 'Text', 'description': 'Allows text with quotes and parentheses', 'parameters': '{"allow_special": false}'},
                {'name': 'Email', 'description': 'Validates email format', 'parameters': '{"regex": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\\\.[a-zA-Z0-9-.]+$"}'},
                {'name': 'Date', 'description': 'Validates date format', 'parameters': '{"format": "%d-%m-%Y"}'},
                {'name': 'Boolean', 'description': 'Validates boolean format (true/false or 0/1)', 'parameters': '{"format": "boolean"}'},
                {'name': 'Alphanumeric', 'description': 'Validates alphanumeric format', 'parameters': '{"format": "alphanumeric"}'}
            ]
            
            # Insert missing rules
            for rule in default_rules:
                if rule['name'] not in existing_names:
                    insert_query = """
                    INSERT INTO validation_rule_types (name, description, parameters, created_date, is_active) 
                    VALUES (?, ?, ?, GETDATE(), 1)
                    """
                    self.execute_non_query(insert_query, (rule['name'], rule['description'], rule['parameters']))
                    self.logger.info(f"Added default validation rule: {rule['name']}")
            
            # Return updated rules
            return self.get_validation_rules()
            
        except Exception as e:
            self.logger.error(f"Error ensuring default validation rules: {str(e)}")
            raise
    
    def initialize_database(self):
        """Initialize database tables and default data with retry support"""
        try:
            # Create tables
            self._create_tables()
            
            # Ensure default validation rules exist
            self.ensure_default_validation_rules()
            
            self.logger.info("All database tables initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {str(e)}")
            raise
    
    def _create_tables(self):
        """Create required database tables if they don't exist"""
        tables = {
            'login_details': """
            CREATE TABLE IF NOT EXISTS login_details (
                id INT IDENTITY(1,1) PRIMARY KEY,
                email NVARCHAR(255) UNIQUE NOT NULL,
                password_hash NVARCHAR(255) NOT NULL,
                first_name NVARCHAR(100),
                last_name NVARCHAR(100),
                is_active BIT DEFAULT 1,
                created_date DATETIME DEFAULT GETDATE(),
                last_login DATETIME
            )
            """,
            'excel_templates': """
            CREATE TABLE IF NOT EXISTS excel_templates (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255) NOT NULL,
                description NVARCHAR(MAX),
                created_date DATETIME DEFAULT GETDATE(),
                template_config NVARCHAR(MAX)
            )
            """,
            'template_columns': """
            CREATE TABLE IF NOT EXISTS template_columns (
                id INT IDENTITY(1,1) PRIMARY KEY,
                template_id INT NOT NULL,
                column_name NVARCHAR(255) NOT NULL,
                data_type NVARCHAR(100),
                validation_rule_id INT,
                is_required BIT DEFAULT 0,
                column_order INT,
                FOREIGN KEY (template_id) REFERENCES excel_templates(id)
            )
            """,
            'validation_rule_types': """
            CREATE TABLE IF NOT EXISTS validation_rule_types (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(100) UNIQUE NOT NULL,
                description NVARCHAR(MAX),
                parameters NVARCHAR(MAX),
                created_date DATETIME DEFAULT GETDATE(),
                is_active BIT DEFAULT 1
            )
            """
        }
        
        for table_name, create_sql in tables.items():
            try:
                self.execute_non_query(create_sql)
                self.logger.info(f"Ensured {table_name} table exists")
            except Exception as e:
                self.logger.error(f"Error creating {table_name} table: {str(e)}")
                raise

# Global fabric service instance
fabric_service = FabricSQLService()
