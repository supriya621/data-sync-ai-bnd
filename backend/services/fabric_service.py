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
                    f"LoginTimeout=120;"
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
                        remote_file_path NVARCHAR(512) DEFAULT 'SQL_TABLE_ONLY',
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
        """ULTRA-FAST bulk insert - Target: <15 seconds for 25K rows"""
        import time
        start_time = time.time()
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Create table name
            table_name = f"file_data_{session_id.replace('-', '_')}"
            
            # Drop table if exists (fast operation)
            cursor.execute(f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL DROP TABLE {table_name}")
            
            # Create table structure with optimized column types
            create_sql = f"CREATE TABLE {table_name} (\n"
            create_sql += "    row_id BIGINT IDENTITY(1,1) PRIMARY KEY,\n"
            create_sql += "    template_id BIGINT,\n"
            create_sql += "    session_id NVARCHAR(50),\n"
            
            for col in dataframe.columns:
                create_sql += f"    [{col}] NVARCHAR(4000),\n"  # Reduced from MAX to 4000 for better performance
            
            create_sql = create_sql.rstrip(',\n') + "\n)"
            cursor.execute(create_sql)
            
            self.logger.info(f"ULTRA-FAST INSERT: Starting bulk insert for {len(dataframe)} rows...")
            
            # METHOD 1: Try ultra-optimized pandas to_sql (fastest when it works)
            success = self._try_ultra_fast_pandas_insert(table_name, dataframe, template_id, session_id)
            
            if not success:
                # METHOD 2: Ultra-fast pyodbc with maximum optimization
                self._ultra_fast_pyodbc_insert(cursor, conn, table_name, dataframe, template_id, session_id)
            
            cursor.close()
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"ULTRA-FAST INSERT COMPLETED: {len(dataframe)} rows in {elapsed_time:.2f} seconds ({len(dataframe)/elapsed_time:.0f} rows/sec)")
            
        except Exception as e:
            self.logger.error(f"Error in ultra-fast bulk insert: {str(e)}")
            raise
    
    def _try_ultra_fast_pandas_insert(self, table_name, dataframe, template_id, session_id):
        """Try pandas to_sql with maximum optimization"""
        try:
            # Only use pandas method if SQLAlchemy is available and configured properly
            try:
                from sqlalchemy import create_engine
                from urllib.parse import quote_plus
                
                # Prepare dataframe with metadata columns
                df_with_meta = dataframe.copy()
                df_with_meta.insert(0, 'template_id', template_id)
                df_with_meta.insert(1, 'session_id', session_id)
                
                # Create ultra-optimized connection string with compatible format
                server_no_port = config.FABRIC_SERVER.split(',')[0]
                
                # Use simpler connection string for better compatibility
                connection_string = (
                    f"mssql+pyodbc://?odbc_connect="
                    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                    f"SERVER={server_no_port};"
                    f"DATABASE={config.FABRIC_DATABASE};"
                    f"UID={config.AZURE_CLIENT_ID};"
                    f"PWD={config.AZURE_CLIENT_SECRET};"
                    f"Authentication=ActiveDirectoryServicePrincipal;"
                    f"Encrypt=yes;"
                    f"TrustServerCertificate=no;"
                    f"fast_executemany=True"
                )
                
                # Create engine with compatible settings
                engine = create_engine(
                    connection_string,
                    pool_pre_ping=False,
                    pool_recycle=-1,
                    echo=False
                )
                
                # Use pandas to_sql with maximum performance settings
                df_with_meta.to_sql(
                    name=table_name,
                    con=engine,
                    if_exists='append',
                    index=False,
                    method='multi',  # Multi-row INSERT statements
                    chunksize=10000  # Optimized chunk size
                )
                
                engine.dispose()
                self.logger.info(f"ULTRA-FAST: Successfully bulk inserted {len(dataframe)} rows using pandas to_sql")
                return True
                
            except ImportError as ie:
                self.logger.info(f"SQLAlchemy not available: {ie}")
                return False
                
        except Exception as e:
            self.logger.warning(f"Pandas ultra-fast insert failed: {e}")
            self.logger.info("Falling back to ultra-fast pyodbc method...")
            return False
    
    def _ultra_fast_pyodbc_insert(self, cursor, conn, table_name, dataframe, template_id, session_id):
        """Ultra-fast pyodbc insert with optimized batch sizing for large datasets"""
        try:
            # Prepare optimized bulk insert
            columns_list = "template_id, session_id, " + ", ".join([f"[{col}]" for col in dataframe.columns])
            placeholders = ", ".join(["?"] * (len(dataframe.columns) + 2))
            insert_sql = f"INSERT INTO {table_name} ({columns_list}) VALUES ({placeholders})"
            
            # ULTRA OPTIMIZATION: Enable fast_executemany
            cursor.fast_executemany = True
            
            # Smart batch sizing based on dataset size
            total_rows = len(dataframe)
            if total_rows <= 1000:
                # Small files: single batch
                batch_size = total_rows
                conn.autocommit = True
            elif total_rows <= 10000:
                # Medium files: 2-5 batches
                batch_size = 5000
                conn.autocommit = False
            else:
                # Large files: optimized smaller batches to avoid timeouts
                batch_size = 5000
                conn.autocommit = False
            
            self.logger.info(f"Processing {total_rows} rows in batches of {batch_size}")
            
            total_batches = (total_rows + batch_size - 1) // batch_size
            
            for i in range(0, total_rows, batch_size):
                batch = dataframe.iloc[i:i+batch_size]
                batch_data = []
                
                for _, row in batch.iterrows():
                    row_data = [template_id, session_id] + [
                        str(val)[:4000] if pd.notna(val) and val is not None else None 
                        for val in row.values
                    ]
                    batch_data.append(tuple(row_data))
                
                # Execute batch insert with timeout protection
                try:
                    cursor.executemany(insert_sql, batch_data)
                    if not conn.autocommit:
                        conn.commit()
                    
                    batch_num = (i // batch_size) + 1
                    self.logger.info(f"ULTRA-FAST batch {batch_num}/{total_batches}: {len(batch_data)} rows inserted")
                    
                except Exception as batch_error:
                    self.logger.error(f"Batch {batch_num} failed: {batch_error}")
                    if not conn.autocommit:
                        conn.rollback()
                    raise
            
            # Reset autocommit if changed
            if conn.autocommit:
                conn.autocommit = False
            
            self.logger.info(f"ULTRA-FAST: Successfully bulk inserted {total_rows} rows using optimized pyodbc with {total_batches} batches")
            
        except Exception as e:
            # Reset autocommit on error
            try:
                if conn.autocommit:
                    conn.autocommit = False
            except:
                pass
            self.logger.error(f"Error in ultra-fast pyodbc insert: {str(e)}")
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
                    
                    elif rule == 'Float':
                        # Check for invalid float values
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
                                'rule_failed': 'Float',
                                'reason': 'Value is not a valid number'
                            })
                            total_errors += 1
                    
                    elif rule == 'Text':
                        # NEW: Text rule validation - flag numeric values as errors
                        cursor.execute(f"""
                            SELECT row_id, [{column_name}] 
                            FROM {table_name} 
                            WHERE template_id = ? AND [{column_name}] IS NOT NULL 
                            AND LTRIM(RTRIM([{column_name}])) != ''
                            AND ISNUMERIC([{column_name}]) = 1
                        """, (template_id,))
                        
                        for row_id, value in cursor.fetchall():
                            errors.append({
                                'row': row_id,
                                'column': column_name,
                                'value': value,
                                'rule_failed': 'Text',
                                'reason': 'Value should be text, not numeric'
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
                    
                    elif rule == 'Boolean':
                        # Check for invalid boolean values
                        cursor.execute(f"""
                            SELECT row_id, [{column_name}] 
                            FROM {table_name} 
                            WHERE template_id = ? AND [{column_name}] IS NOT NULL
                            AND LTRIM(RTRIM([{column_name}])) != ''
                            AND UPPER(LTRIM(RTRIM([{column_name}]))) NOT IN ('TRUE', 'FALSE', '1', '0', 'YES', 'NO')
                        """, (template_id,))
                        
                        for row_id, value in cursor.fetchall():
                            errors.append({
                                'row': row_id,
                                'column': column_name,
                                'value': value,
                                'rule_failed': 'Boolean',
                                'reason': 'Value must be true/false, 1/0, or yes/no'
                            })
                            total_errors += 1
                    
                    elif rule == 'Alphanumeric':
                        # Check for non-alphanumeric values (contains special characters)
                        cursor.execute(f"""
                            SELECT row_id, [{column_name}] 
                            FROM {table_name} 
                            WHERE template_id = ? AND [{column_name}] IS NOT NULL
                            AND LTRIM(RTRIM([{column_name}])) != ''
                            AND [{column_name}] LIKE '%[^a-zA-Z0-9 ]%'
                        """, (template_id,))
                        
                        for row_id, value in cursor.fetchall():
                            errors.append({
                                'row': row_id,
                                'column': column_name,
                                'value': value,
                                'rule_failed': 'Alphanumeric',
                                'reason': 'Value should contain only letters, numbers and spaces'
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
    
    def apply_corrections_in_sql_fabric(self, corrections: dict, session_id: str, template_id: int) -> int:
        """Apply corrections to data in SQL Fabric - WITH DEBUG LOGGING"""
        try:
            table_name = f"file_data_{session_id.replace('-', '_')}"
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # ===== DEBUG SECTION =====
            # DEBUG: Log what corrections we received from frontend
            self.logger.info(f"[DEBUG] === CORRECTION DEBUG SESSION START ===")
            self.logger.info(f"[DEBUG] Received {len(corrections)} corrections from frontend:")
            for key, value in corrections.items():
                self.logger.info(f"[DEBUG] Frontend sent: '{key}' → '{value}'")
            
            # DEBUG: Show current table structure and data
            self.logger.info(f"[DEBUG] Examining table: {table_name}")
            cursor.execute(f"SELECT TOP 10 * FROM {table_name} WHERE template_id = ? ORDER BY row_id", (template_id,))
            all_rows = cursor.fetchall()
            if all_rows:
                columns = [desc[0] for desc in cursor.description]
                self.logger.info(f"[DEBUG] Table columns: {columns}")
                self.logger.info(f"[DEBUG] Current table data:")
                for row in all_rows:
                    row_dict = dict(zip(columns, row))
                    self.logger.info(f"[DEBUG]   {row_dict}")
            else:
                self.logger.error(f"[DEBUG] ERROR: No rows found in table {table_name}!")
            # ===== END DEBUG SECTION =====
            
            corrected_count = 0
            
            for correction_key, new_value in corrections.items():
                # Parse correction key (format: "row_column")
                parts = correction_key.split('_', 1)
                if len(parts) == 2:
                    row_id, column_name = parts[0], parts[1]
                    
                    # ===== DEBUG FOR EACH CORRECTION =====
                    self.logger.info(f"[DEBUG] --- Processing correction ---")
                    self.logger.info(f"[DEBUG] Original key: '{correction_key}'")
                    self.logger.info(f"[DEBUG] Parsed row_id: '{row_id}'")
                    self.logger.info(f"[DEBUG] Parsed column_name: '{column_name}'")
                    self.logger.info(f"[DEBUG] New value: '{new_value}'")
                    
                    # Check if this exact row and column exists
                    try:
                        cursor.execute(f"SELECT [{column_name}] FROM {table_name} WHERE template_id = ? AND row_id = ?", 
                                     (template_id, row_id))
                        existing_row = cursor.fetchone()
                        
                        if existing_row:
                            old_value = existing_row[0]
                            self.logger.info(f"[DEBUG] Found target: row_id={row_id}, column='{column_name}', current_value='{old_value}'")
                            
                            # Update the value
                            cursor.execute(f"""
                                UPDATE {table_name} 
                                SET [{column_name}] = ?
                                WHERE template_id = ? AND row_id = ?
                            """, (new_value, template_id, row_id))
                            
                            rows_affected = cursor.rowcount
                            self.logger.info(f"[DEBUG] Update result: {rows_affected} rows affected")
                            
                            if rows_affected > 0:
                                corrected_count += 1
                                self.logger.info(f"[DEBUG] SUCCESS: Updated row_id={row_id}, column='{column_name}': '{old_value}' → '{new_value}'")
                            else:
                                self.logger.error(f"[DEBUG] FAILED: Update command executed but 0 rows affected!")
                        else:
                            self.logger.error(f"[DEBUG] ERROR: No row found with row_id={row_id} for column '{column_name}'")
                            # Show what rows DO exist for this column
                            cursor.execute(f"SELECT row_id, [{column_name}] FROM {table_name} WHERE template_id = ? ORDER BY row_id", (template_id,))
                            available_rows = cursor.fetchall()
                            self.logger.info(f"[DEBUG] Available rows for column '{column_name}': {available_rows}")
                            
                    except Exception as col_error:
                        self.logger.error(f"[DEBUG] ERROR accessing column '{column_name}': {col_error}")
                    # ===== END DEBUG FOR EACH CORRECTION =====
                else:
                    self.logger.error(f"[DEBUG] ERROR: Invalid correction key format: '{correction_key}'")
            
            # ===== FINAL DEBUG SUMMARY =====
            self.logger.info(f"[DEBUG] === CORRECTION SUMMARY ===")
            self.logger.info(f"[DEBUG] Total corrections attempted: {len(corrections)}")
            self.logger.info(f"[DEBUG] Successful corrections: {corrected_count}")
            self.logger.info(f"[DEBUG] Failed corrections: {len(corrections) - corrected_count}")
            
            # Show final table state
            self.logger.info(f"[DEBUG] Final table state:")
            cursor.execute(f"SELECT TOP 10 * FROM {table_name} WHERE template_id = ? ORDER BY row_id", (template_id,))
            final_rows = cursor.fetchall()
            for row in final_rows:
                row_dict = dict(zip(columns, row))
                self.logger.info(f"[DEBUG]   {row_dict}")
            self.logger.info(f"[DEBUG] === CORRECTION DEBUG SESSION END ===")
            # ===== END FINAL DEBUG =====
            
            conn.commit()
            cursor.close()
            
            self.logger.info(f"Applied {corrected_count} corrections in SQL Fabric")
            return corrected_count
            
        except Exception as e:
            self.logger.error(f"Error applying corrections in SQL Fabric: {str(e)}")
            if 'conn' in locals():
                conn.rollback()
            raise
    
    def export_corrected_data(self, session_id: str, template_id: int, columns: list) -> pd.DataFrame:
        """Export corrected data from SQL Fabric as DataFrame - FIXED VERSION"""
        try:
            table_name = f"file_data_{session_id.replace('-', '_')}"
            columns_sql = ", ".join([f"[{col}]" for col in columns])
            
            query = f"SELECT {columns_sql} FROM {table_name} WHERE template_id = ? ORDER BY row_id"
            
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, (template_id,))
            
            # Get column names from cursor description
            column_names = [desc[0] for desc in cursor.description]
            
            # Fetch all rows
            rows = cursor.fetchall()
            cursor.close()
            
            # Convert to DataFrame manually instead of using pd.read_sql
            data_dict = {col: [] for col in column_names}
            
            for row in rows:
                for i, value in enumerate(row):
                    data_dict[column_names[i]].append(value)
            
            df = pd.DataFrame(data_dict)
            
            self.logger.info(f"Exported {len(df)} rows from SQL Fabric (FIXED METHOD)")
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
    

    
    def create_default_rules(self):
        """Create default validation rules in SQL Fabric"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Check if validation_rule_types table has any rules
            cursor.execute("SELECT COUNT(*) FROM validation_rule_types WHERE rule_name IN ('Required', 'Int', 'Float', 'Text', 'Email', 'Date', 'Boolean', 'Alphanumeric')")
            existing_count = cursor.fetchone()[0]
            
            if existing_count == 0:
                # Insert default validation rules
                default_rules = [
                    (1, 'Required', 'Ensures the field is not null', '{"allow_null": false}', 1, 0),
                    (2, 'Int', 'Validates integer format', '{"format": "integer"}', 1, 0),
                    (3, 'Float', 'Validates number format (integer or decimal)', '{"format": "float"}', 1, 0),
                    (4, 'Text', 'Allows text with quotes and parentheses', '{"allow_special": false}', 1, 0),
                    (5, 'Email', 'Validates email format', '{"regex": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$"}', 1, 0),
                    (6, 'Date', 'Validates date format', '{"format": "%d-%m-%Y"}', 1, 0),
                    (7, 'Boolean', 'Validates boolean format (true/false or 0/1)', '{"format": "boolean"}', 1, 0),
                    (8, 'Alphanumeric', 'Validates alphanumeric format', '{"format": "alphanumeric"}', 1, 0)
                ]
                
                for rule in default_rules:
                    cursor.execute("""
                        INSERT INTO validation_rule_types (rule_type_id, rule_name, description, parameters, is_active, is_custom)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, rule)
                
                conn.commit()
                self.logger.info("Default validation rules created successfully")
            else:
                self.logger.info(f"Default validation rules already exist ({existing_count} found)")
            
            # DEBUG: Show what's actually in the database
            cursor.execute("SELECT rule_type_id, rule_name FROM validation_rule_types ORDER BY rule_type_id")
            existing_rules = cursor.fetchall()
            self.logger.info(f"DEBUGGING - Current validation rules in DB:")
            for rule in existing_rules:
                self.logger.info(f"  ID: {rule[0]}, Name: {rule[1]}")
            
            cursor.close()
            
        except Exception as e:
            self.logger.error(f"Error creating default validation rules: {str(e)}")
            if 'conn' in locals():
                conn.rollback()
            raise
    
    def close_connection(self):
        """Close database connection"""
        if self.connection and not self.connection.closed:
            self.connection.close()
            self.logger.info("Fabric SQL connection closed")

# Global service instance
fabric_service = FabricSQLService()
