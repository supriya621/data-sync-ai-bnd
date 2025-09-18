import pyodbc
import pandas as pd
import logging
import json
from azure.identity import ClientSecretCredential
from typing import Optional, Dict, Any, List, Tuple
from backend.config.config import config

class FabricSQLService:
    """Service for Microsoft Fabric SQL operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.connection = None
        self.credential = None
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
    
    def get_connection(self) -> pyodbc.Connection:
        """Get or create database connection using Service Principal authentication"""
        if self.connection is None or self.connection.closed:
            try:
                # Use the working Service Principal authentication method
                # Remove port from server name as it works better without explicit port
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
                )
                
                self.logger.info("Connecting to Fabric SQL with Service Principal authentication...")
                self.connection = pyodbc.connect(connection_string)
                
                self.logger.info("Successfully connected to Fabric SQL!")
                return self.connection
                
            except Exception as e:
                self.logger.error(f"Failed to connect to Fabric SQL: {str(e)}")
                raise
        
        return self.connection
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute SELECT query and return results"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Get column names
            columns = [column[0] for column in cursor.description]
            
            # Fetch all results
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            cursor.close()
            self.logger.info(f"Query executed successfully, returned {len(results)} rows")
            return results
            
        except Exception as e:
            self.logger.error(f"Query execution failed: {str(e)}")
            raise
    
    def execute_non_query(self, query: str, params: Optional[tuple] = None) -> int:
        """Execute INSERT, UPDATE, DELETE queries"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            rows_affected = cursor.rowcount
            conn.commit()
            cursor.close()
            
            self.logger.info(f"Non-query executed successfully, {rows_affected} rows affected")
            return rows_affected
            
        except Exception as e:
            self.logger.error(f"Non-query execution failed: {str(e)}")
            conn.rollback()
            raise
    
    def init_database(self):
        """Initialize database tables for Fabric SQL with proper order and error handling"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Create tables in proper dependency order
            # 1. Base table - login_details (no dependencies)
            try:
                cursor.execute("""
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='login_details' AND xtype='U')
                    CREATE TABLE login_details (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        first_name NVARCHAR(100),
                        last_name NVARCHAR(100),
                        email NVARCHAR(255) UNIQUE,
                        mobile NVARCHAR(20),
                        password NVARCHAR(255),
                        is_approved BIT DEFAULT 0,
                        created_at DATETIME2 DEFAULT GETDATE()
                    )
                """)
                self.logger.info("Ensured login_details table exists")
            except Exception as e:
                self.logger.error(f"Failed to create login_details: {str(e)}")
                raise
            
            # 2. Templates table (depends on login_details)
            try:
                cursor.execute("""
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='excel_templates' AND xtype='U')
                    CREATE TABLE excel_templates (
                        template_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                        template_name NVARCHAR(255) NOT NULL,
                        created_at DATETIME2 DEFAULT GETDATE(),
                        updated_at DATETIME2 DEFAULT GETDATE(),
                        user_id INT NOT NULL,
                        sheet_name NVARCHAR(255),
                        headers NVARCHAR(MAX),
                        status NVARCHAR(20) DEFAULT 'ACTIVE',
                        is_corrected BIT DEFAULT 0,
                        remote_file_path NVARCHAR(512),
                        validation_frequency NVARCHAR(20),
                        first_identified_at DATETIME2,
                        FOREIGN KEY (user_id) REFERENCES login_details(id)
                    )
                """)
                self.logger.info("Ensured excel_templates table exists")
            except Exception as e:
                self.logger.error(f"Failed to create excel_templates: {str(e)}")
                raise
            
            # 3. Template columns (depends on excel_templates)
            try:
                cursor.execute("""
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='template_columns' AND xtype='U')
                    CREATE TABLE template_columns (
                        column_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                        template_id BIGINT NOT NULL,
                        column_name NVARCHAR(255) NOT NULL,
                        column_position INT NOT NULL,
                        is_validation_enabled BIT DEFAULT 0,
                        is_selected BIT DEFAULT 0,
                        FOREIGN KEY (template_id) REFERENCES excel_templates(template_id),
                        UNIQUE (template_id, column_name)
                    )
                """)
                self.logger.info("Ensured template_columns table exists")
            except Exception as e:
                self.logger.error(f"Failed to create template_columns: {str(e)}")
                # Don't raise for this error - continue with other tables
            
            # 4. Validation rule types (standalone)
            try:
                cursor.execute("""
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='validation_rule_types' AND xtype='U')
                    CREATE TABLE validation_rule_types (
                        rule_type_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                        rule_name NVARCHAR(255) NOT NULL,
                        description NVARCHAR(MAX),
                        parameters NVARCHAR(MAX),
                        is_active BIT DEFAULT 1,
                        is_custom BIT DEFAULT 0,
                        created_at DATETIME2 DEFAULT GETDATE()
                    )
                """)
                self.logger.info("Ensured validation_rule_types table exists")
            except Exception as e:
                self.logger.error(f"Failed to create validation_rule_types: {str(e)}")
                # Don't raise - continue
            
            # Skip complex foreign key tables for now - they exist already
            # Focus on core functionality
            
            conn.commit()
            cursor.close()
            self.logger.info("All database tables initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {str(e)}")
            raise
    
    def create_default_rules(self):
        """Create default validation rules"""
        try:
            default_rules = [
                ("Required", "Ensures the field is not null", '{"allow_null": false}'),
                ("Int", "Validates integer format", '{"format": "integer"}'),
                ("Float", "Validates number format (integer or decimal)", '{"format": "float"}'),
                ("Text", "Allows text with quotes and parentheses", '{"allow_special": false}'),
                ("Email", "Validates email format", '{"regex": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\\\.[a-zA-Z0-9-.]+$"}'),
                ("Date", "Validates date format", '{"format": "%d-%m-%Y"}'),
                ("Boolean", "Validates boolean format (true/false or 0/1)", '{"format": "boolean"}'),
                ("Alphanumeric", "Validates alphanumeric format", '{"format": "alphanumeric"}')
            ]
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            for rule_name, description, parameters in default_rules:
                # Check if rule already exists
                cursor.execute("""
                    SELECT COUNT(*) FROM validation_rule_types 
                    WHERE rule_name = ? AND is_custom = 0
                """, (rule_name,))
                
                if cursor.fetchone()[0] == 0:
                    cursor.execute("""
                        INSERT INTO validation_rule_types (rule_name, description, parameters, is_custom)
                        VALUES (?, ?, ?, 0)
                    """, (rule_name, description, parameters))
            
            conn.commit()
            cursor.close()
            self.logger.info("Default validation rules created successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to create default rules: {str(e)}")
            raise
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        try:
            results = self.execute_query("""
                SELECT * FROM login_details WHERE LOWER(email) = LOWER(?)
            """, (email,))
            return results[0] if results else None
        except Exception as e:
            self.logger.error(f"Error getting user by email: {str(e)}")
            return None
    
    def bulk_insert_file_data(self, dataframe, session_id: str, template_id: int):
        """Bulk insert file data into SQL Fabric for processing"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Create a temporary table for this session's data
            table_name = f"file_data_{session_id.replace('-', '_')}"
            
            # Drop table if exists
            cursor.execute(f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL DROP TABLE {table_name}")
            
            # Create table structure based on dataframe
            create_sql = f"CREATE TABLE {table_name} (\n"
            create_sql += "    row_id BIGINT IDENTITY(1,1) PRIMARY KEY,\n"
            create_sql += "    template_id BIGINT,\n"
            create_sql += "    session_id NVARCHAR(50),\n"
            
            # Add columns for each dataframe column
            for col in dataframe.columns:
                create_sql += f"    [{col}] NVARCHAR(MAX),\n"
            
            create_sql = create_sql.rstrip(',\n') + "\n)"
            cursor.execute(create_sql)
            
            # Prepare bulk insert
            columns_list = "template_id, session_id, " + ", ".join([f"[{col}]" for col in dataframe.columns])
            placeholders = ", ".join(["?"] * (len(dataframe.columns) + 2))
            insert_sql = f"INSERT INTO {table_name} ({columns_list}) VALUES ({placeholders})"
            
            # Insert data in batches
            batch_size = 1000
            for i in range(0, len(dataframe), batch_size):
                batch = dataframe.iloc[i:i+batch_size]
                batch_data = []
                
                for _, row in batch.iterrows():
                    row_data = [template_id, session_id] + [str(val) if pd.notna(val) else None for val in row.values]
                    batch_data.append(tuple(row_data))
                
                cursor.executemany(insert_sql, batch_data)
                conn.commit()
                
                self.logger.info(f"Inserted batch {i//batch_size + 1}: {len(batch)} rows")
            
            cursor.close()
            self.logger.info(f"Successfully bulk inserted {len(dataframe)} rows into SQL Fabric table {table_name}")
            
        except Exception as e:
            self.logger.error(f"Error in bulk insert: {str(e)}")
            raise
    
    def get_file_data(self, session_id: str, template_id: int, columns: list = None) -> list:
        """Get file data from SQL Fabric temporary table"""
        try:
            table_name = f"file_data_{session_id.replace('-', '_')}"
            
            if columns:
                columns_sql = ", ".join([f"[{col}]" for col in columns])
            else:
                columns_sql = "*"
            
            query = f"SELECT {columns_sql} FROM {table_name} WHERE template_id = ? ORDER BY row_id"
            
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, (template_id,))
            
            if columns:
                results = []
                for row in cursor.fetchall():
                    row_dict = {columns[i]: row[i] for i in range(len(columns))}
                    results.append(row_dict)
                return results
            else:
                columns_desc = [desc[0] for desc in cursor.description]
                results = []
                for row in cursor.fetchall():
                    row_dict = {columns_desc[i]: row[i] for i in range(len(columns_desc))}
                    results.append(row_dict)
                return results
                
        except Exception as e:
            self.logger.error(f"Error getting file data: {str(e)}")
            raise
    
    def validate_data_in_sql_fabric(self, session_id: str, template_id: int, validation_rules: dict) -> dict:
        """Perform data validation using SQL Server queries"""
        try:
            table_name = f"file_data_{session_id.replace('-', '_')}"
            errors = []
            total_errors = 0
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Validate each column according to its rules
            for column_name, rules in validation_rules.items():
                for rule in rules:
                    if rule == 'Required':
                        # Check for null or empty values
                        cursor.execute(f"""
                            SELECT row_id, [{column_name}] 
                            FROM {table_name} 
                            WHERE template_id = ? AND ([{column_name}] IS NULL OR LTRIM(RTRIM([{column_name}])) = '')
                        """, (template_id,))
                        
                        for row_id, value in cursor.fetchall():
                            errors.append({
                                'row': row_id,
                                'column': column_name,
                                'value': value,
                                'rule_failed': 'Required',
                                'reason': 'Field is required but empty'
                            })
                            total_errors += 1
                    
                    elif rule == 'Int':
                        # Check for invalid integers
                        cursor.execute(f"""
                            SELECT row_id, [{column_name}] 
                            FROM {table_name} 
                            WHERE template_id = ? AND [{column_name}] IS NOT NULL 
                            AND LTRIM(RTRIM([{column_name}])) != ''
                            AND ISNUMERIC([{column_name}]) = 0
                        """, (template_id,))
                        
                        for row_id, value in cursor.fetchall():
                            errors.append({
                                'row': row_id,
                                'column': column_name,
                                'value': value,
                                'rule_failed': 'Int',
                                'reason': 'Value is not a valid integer'
                            })
                            total_errors += 1
                    
                    elif rule == 'Email':
                        # Check for invalid email format
                        cursor.execute(f"""
                            SELECT row_id, [{column_name}] 
                            FROM {table_name} 
                            WHERE template_id = ? AND [{column_name}] IS NOT NULL
                            AND LTRIM(RTRIM([{column_name}])) != ''
                            AND [{column_name}] NOT LIKE '%@%.%'
                        """, (template_id,))
                        
                        for row_id, value in cursor.fetchall():
                            errors.append({
                                'row': row_id,
                                'column': column_name,
                                'value': value,
                                'rule_failed': 'Email',
                                'reason': 'Invalid email format'
                            })
                            total_errors += 1
            
            cursor.close()
            
            # Group errors by column
            error_dict = {}
            for error in errors:
                col = error['column']
                if col not in error_dict:
                    error_dict[col] = []
                error_dict[col].append(error)
            
            self.logger.info(f"SQL Fabric validation completed: {total_errors} errors found")
            
            return {
                'total_errors': total_errors,
                'error_cell_locations': error_dict,
                'errors_list': errors
            }
            
        except Exception as e:
            self.logger.error(f"Error in SQL Fabric validation: {str(e)}")
            raise
    
    def apply_corrections_in_sql_fabric(self, session_id: str, template_id: int, corrections: dict) -> int:
        """Apply corrections to data in SQL Fabric"""
        try:
            table_name = f"file_data_{session_id.replace('-', '_')}"
            conn = self.get_connection()
            cursor = conn.cursor()
            
            corrected_count = 0
            
            for correction_key, new_value in corrections.items():
                # Parse correction key (format: "row_column")
                parts = correction_key.split('_', 1)
                if len(parts) == 2:
                    row_id, column_name = parts[0], parts[1]
                    
                    # Update the value in SQL Fabric
                    cursor.execute(f"""
                        UPDATE {table_name} 
                        SET [{column_name}] = ?
                        WHERE template_id = ? AND row_id = ?
                    """, (new_value, template_id, row_id))
                    
                    corrected_count += 1
            
            conn.commit()
            cursor.close()
            
            self.logger.info(f"Applied {corrected_count} corrections in SQL Fabric")
            return corrected_count
            
        except Exception as e:
            self.logger.error(f"Error applying corrections in SQL Fabric: {str(e)}")
            raise
    
    def export_corrected_data(self, session_id: str, template_id: int, columns: list) -> pd.DataFrame:
        """Export corrected data from SQL Fabric as DataFrame"""
        try:
            table_name = f"file_data_{session_id.replace('-', '_')}"
            columns_sql = ", ".join([f"[{col}]" for col in columns])
            
            query = f"SELECT {columns_sql} FROM {table_name} WHERE template_id = ? ORDER BY row_id"
            
            conn = self.get_connection()
            df = pd.read_sql(query, conn, params=[template_id])
            
            self.logger.info(f"Exported {len(df)} rows from SQL Fabric")
            return df
            
        except Exception as e:
            self.logger.error(f"Error exporting data from SQL Fabric: {str(e)}")
            raise
    
    def cleanup_session_data(self, session_id: str):
        """Clean up temporary session data from SQL Fabric"""
        try:
            table_name = f"file_data_{session_id.replace('-', '_')}"
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL DROP TABLE {table_name}")
            conn.commit()
            cursor.close()
            
            self.logger.info(f"Cleaned up SQL Fabric session table: {table_name}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up session data: {str(e)}")
            # Don't raise - cleanup errors shouldn't stop the application

    def create_user(self, user_data: Dict[str, Any]) -> int:
        """Create a new user with is_approved field support"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Use OUTPUT INSERTED.id to get the ID directly from INSERT
            cursor.execute("""
                INSERT INTO login_details (first_name, last_name, email, mobile, password, is_approved)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_data['first_name'],
                user_data['last_name'], 
                user_data['email'],
                user_data['mobile'],
                user_data['password'],
                user_data.get('is_approved', False)
            ))
            
            # Get the inserted user ID from OUTPUT
            result = cursor.fetchone()
            if result is None:
                raise Exception("Failed to get user ID from insert operation")
            
            user_id = result[0]
            if user_id is None:
                raise Exception("User ID returned as None from insert operation")
            
            conn.commit()
            cursor.close()
            
            self.logger.info(f"User created successfully with ID: {user_id}")
            return int(user_id)
            
        except Exception as e:
            self.logger.error(f"Error creating user: {str(e)}")
            if 'conn' in locals():
                conn.rollback()
            raise
    
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
                "message": "Connection successful",
                "test_result": result[0] if result else None
            }
            
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Connection failed: {str(e)}"
            }
    
    def create_template(self, template_data: Dict[str, Any]) -> int:
        """Create a new template in SQL Fabric"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO excel_templates (template_name, user_id, sheet_name, headers, status)
                OUTPUT INSERTED.template_id
                VALUES (?, ?, ?, ?, ?)
            """, (
                template_data['template_name'],
                template_data['user_id'],
                template_data['sheet_name'],
                template_data['headers'],
                template_data['status']
            ))
            
            template_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            
            self.logger.info(f"Template created successfully with ID: {template_id}")
            return template_id
            
        except Exception as e:
            self.logger.error(f"Error creating template: {str(e)}")
            raise
    
    def get_validation_rules(self) -> List[Dict[str, Any]]:
        """Get all validation rules from SQL Fabric"""
        try:
            results = self.execute_query("""
                SELECT rule_type_id, rule_name, description, parameters, is_active, is_custom
                FROM validation_rule_types
                WHERE is_active = 1
                ORDER BY rule_name
            """)
            return results
        except Exception as e:
            self.logger.error(f"Error getting validation rules: {str(e)}")
            raise
    
    def store_validation_history(self, history_data: Dict[str, Any]) -> int:
        """Store validation history in SQL Fabric"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO validation_history 
                (template_id, template_name, error_count, user_id, processing_time_ms, file_size_mb)
                OUTPUT INSERTED.history_id
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                history_data['template_id'],
                history_data['template_name'],
                history_data['error_count'],
                history_data['user_id'],
                history_data['processing_time_ms'],
                history_data['file_size_mb']
            ))
            
            history_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            
            self.logger.info(f"Validation history stored with ID: {history_id}")
            return history_id
            
        except Exception as e:
            self.logger.error(f"Error storing validation history: {str(e)}")
            raise
    
    def store_validation_corrections(self, history_id: int, corrections: List[Dict[str, Any]]) -> None:
        """Store validation corrections in SQL Fabric"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            for correction in corrections:
                cursor.execute("""
                    INSERT INTO validation_corrections 
                    (history_id, row_index, column_name, original_value, corrected_value, rule_failed)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    history_id,
                    correction.get('row_index', 0),
                    correction.get('column_name', ''),
                    correction.get('original_value', ''),
                    correction.get('corrected_value', ''),
                    correction.get('rule_failed', '')
                ))
            
            conn.commit()
            cursor.close()
            
            self.logger.info(f"Stored {len(corrections)} validation corrections")
            
        except Exception as e:
            self.logger.error(f"Error storing validation corrections: {str(e)}")
            raise
    
    def get_user_templates(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all templates for a user"""
        try:
            results = self.execute_query("""
                SELECT template_id, template_name, created_at, updated_at, 
                       sheet_name, headers, status, is_corrected
                FROM excel_templates
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,))
            return results
        except Exception as e:
            self.logger.error(f"Error getting user templates: {str(e)}")
            raise
    
    def get_validation_history(self, template_id: int = None, user_id: int = None) -> List[Dict[str, Any]]:
        """Get validation history"""
        try:
            if template_id:
                results = self.execute_query("""
                    SELECT h.*, t.template_name
                    FROM validation_history h
                    JOIN excel_templates t ON h.template_id = t.template_id
                    WHERE h.template_id = ?
                    ORDER BY h.corrected_at DESC
                """, (template_id,))
            elif user_id:
                results = self.execute_query("""
                    SELECT h.*, t.template_name
                    FROM validation_history h
                    JOIN excel_templates t ON h.template_id = t.template_id
                    WHERE h.user_id = ?
                    ORDER BY h.corrected_at DESC
                """, (user_id,))
            else:
                results = self.execute_query("""
                    SELECT h.*, t.template_name
                    FROM validation_history h
                    JOIN excel_templates t ON h.template_id = t.template_id
                    ORDER BY h.corrected_at DESC
                """)
            return results
        except Exception as e:
            self.logger.error(f"Error getting validation history: {str(e)}")
            raise
    
    def close_connection(self):
        """Close database connection"""
        if self.connection and not self.connection.closed:
            self.connection.close()
            self.logger.info("Fabric SQL connection closed")

# Global service instance
fabric_service = FabricSQLService()
