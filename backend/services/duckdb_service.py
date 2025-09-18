import duckdb
import pandas as pd
import logging
import os
import json
import time
import uuid
from typing import Optional, Dict, Any, List, Tuple
from backend.config.config import config

class DuckDBService:
    """Service for DuckDB operations - optimized for large data processing"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.db_path = config.DUCKDB_PATH
        self.connection = None
        self._ensure_db_directory()
        self._initialize_database()
    
    def _ensure_db_directory(self):
        """Ensure the database directory exists"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            self.logger.info(f"Created database directory: {db_dir}")
    
    def _initialize_database(self):
        """Initialize DuckDB database with optimizations for large data"""
        try:
            # Use in-memory database for development to avoid file locks
            if os.getenv('FLASK_ENV', 'development') == 'development':
                self.connection = duckdb.connect(':memory:')
                self.logger.info("Using in-memory DuckDB for development")
            else:
                self.connection = duckdb.connect(self.db_path)
                self.logger.info(f"Using file-based DuckDB: {self.db_path}")
            
            # Set performance optimizations
            self.connection.execute(f"PRAGMA memory_limit='4GB'")
            self.connection.execute(f"PRAGMA threads=4")
            self.connection.execute("SET enable_progress_bar=true")
            
            # Create tables for temporary data processing
            self._create_processing_tables()
            
            self.logger.info(f"DuckDB initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize DuckDB: {str(e)}")
            raise
    
    def _create_processing_tables(self):
        """Create tables for data processing"""
        try:
            # Table for storing file data temporarily
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS file_data (
                    session_id VARCHAR,
                    template_id BIGINT,
                    row_index INTEGER,
                    column_name VARCHAR,
                    column_value VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Table for validation results
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS validation_results (
                    session_id VARCHAR,
                    template_id BIGINT,
                    row_index INTEGER,
                    column_name VARCHAR,
                    rule_name VARCHAR,
                    is_valid BOOLEAN,
                    error_message VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_data_session 
                ON file_data(session_id, template_id)
            """)
            
            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_validation_results_session 
                ON validation_results(session_id, template_id)
            """)
            
            self.logger.info("Processing tables created successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to create processing tables: {str(e)}")
            raise
    
    def load_file_data(self, file_path: str, session_id: str, template_id: int, 
                      chunk_size: int = None) -> Dict[str, Any]:
        """Load file data into DuckDB for processing large files"""
        start_time = time.time()
        chunk_size = chunk_size or config.CHUNK_SIZE
        
        try:
            conn = self.connection
            
            # Clear existing data for this session
            conn.execute("""
                DELETE FROM file_data 
                WHERE session_id = ? AND template_id = ?
            """, (session_id, template_id))
            
            # Detect file type and load accordingly
            if file_path.endswith(('.xlsx', '.xls')):
                return self._load_excel_file(file_path, session_id, template_id, chunk_size)
            elif file_path.endswith(('.csv', '.txt', '.dat')):
                return self._load_csv_file(file_path, session_id, template_id, chunk_size)
            else:
                raise ValueError(f"Unsupported file type: {file_path}")
                
        except Exception as e:
            self.logger.error(f"Failed to load file data: {str(e)}")
            raise
    
    def _load_excel_file(self, file_path: str, session_id: str, template_id: int, 
                        chunk_size: int) -> Dict[str, Any]:
        """Load Excel file in chunks"""
        try:
            # Read Excel file metadata
            xl = pd.ExcelFile(file_path)
            sheet_names = xl.sheet_names
            
            results = {}
            total_rows = 0
            
            for sheet_name in sheet_names:
                sheet_data = pd.read_excel(file_path, sheet_name=sheet_name)
                total_rows += len(sheet_data)
                
                # Find header row
                header_row = self._find_header_row(sheet_data)
                if header_row == -1:
                    continue
                
                headers = sheet_data.iloc[header_row].tolist()
                data_rows = sheet_data.iloc[header_row + 1:].reset_index(drop=True)
                
                # Process in chunks if large
                if len(data_rows) > config.LARGE_FILE_THRESHOLD:
                    self._process_data_chunks(data_rows, headers, session_id, template_id, chunk_size)
                else:
                    self._process_small_data(data_rows, headers, session_id, template_id)
                
                results[sheet_name] = {
                    'headers': headers,
                    'row_count': len(data_rows),
                    'header_row': header_row
                }
            
            return {
                'success': True,
                'sheets': results,
                'total_rows': total_rows,
                'processing_method': 'chunks' if total_rows > config.LARGE_FILE_THRESHOLD else 'direct'
            }
            
        except Exception as e:
            self.logger.error(f"Error loading Excel file: {str(e)}")
            raise
    
    def _load_csv_file(self, file_path: str, session_id: str, template_id: int, 
                      chunk_size: int) -> Dict[str, Any]:
        """Load CSV file in chunks"""
        try:
            # Try to detect delimiter
            delimiter = self._detect_delimiter(file_path)
            
            # Process large files in chunks
            total_rows = sum(1 for line in open(file_path, 'r', encoding='utf-8')) - 1
            
            if total_rows > config.LARGE_FILE_THRESHOLD:
                return self._process_csv_chunks(file_path, delimiter, session_id, template_id, chunk_size)
            else:
                df = pd.read_csv(file_path, sep=delimiter)
                headers = df.columns.tolist()
                self._process_small_data(df, headers, session_id, template_id)
                
                return {
                    'success': True,
                    'sheets': {'Sheet1': {'headers': headers, 'row_count': len(df), 'header_row': 0}},
                    'total_rows': total_rows,
                    'processing_method': 'direct'
                }
                
        except Exception as e:
            self.logger.error(f"Error loading CSV file: {str(e)}")
            raise
    
    def _process_csv_chunks(self, file_path: str, delimiter: str, session_id: str, 
                           template_id: int, chunk_size: int) -> Dict[str, Any]:
        """Process large CSV files in chunks"""
        try:
            conn = self.connection
            headers = None
            total_rows = 0
            
            # Use pandas chunk reader
            for chunk_num, chunk in enumerate(pd.read_csv(file_path, sep=delimiter, chunksize=chunk_size)):
                if headers is None:
                    headers = chunk.columns.tolist()
                
                # Prepare data for insertion
                data_to_insert = []
                for row_idx, (_, row) in enumerate(chunk.iterrows()):
                    global_row_idx = chunk_num * chunk_size + row_idx
                    for col_name in headers:
                        value = str(row[col_name]) if pd.notna(row[col_name]) else 'NULL'
                        data_to_insert.append((session_id, template_id, global_row_idx, col_name, value))
                
                # Batch insert chunk data
                conn.executemany("""
                    INSERT INTO file_data (session_id, template_id, row_index, column_name, column_value)
                    VALUES (?, ?, ?, ?, ?)
                """, data_to_insert)
                
                total_rows += len(chunk)
                self.logger.info(f"Processed chunk {chunk_num + 1}, total rows: {total_rows}")
            
            return {
                'success': True,
                'sheets': {'Sheet1': {'headers': headers, 'row_count': total_rows, 'header_row': 0}},
                'total_rows': total_rows,
                'processing_method': 'chunks'
            }
            
        except Exception as e:
            self.logger.error(f"Error processing CSV chunks: {str(e)}")
            raise
    
    def validate_data(self, session_id: str, template_id: int, 
                     validation_rules: Dict[str, List[str]]) -> Dict[str, Any]:
        """Validate data using DuckDB for performance"""
        start_time = time.time()
        
        try:
            conn = self.connection
            
            # Clear previous validation results
            conn.execute("""
                DELETE FROM validation_results 
                WHERE session_id = ? AND template_id = ?
            """, (session_id, template_id))
            
            total_errors = 0
            validation_results = {}
            
            for column_name, rules in validation_rules.items():
                column_errors = []
                
                for rule_name in rules:
                    errors = self._validate_column_rule(conn, session_id, template_id, 
                                                      column_name, rule_name)
                    column_errors.extend(errors)
                    total_errors += len(errors)
                
                if column_errors:
                    validation_results[column_name] = column_errors
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return {
                'success': True,
                'error_cell_locations': validation_results,
                'total_errors': total_errors,
                'processing_time_ms': processing_time
            }
            
        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            raise
    
    def _validate_column_rule(self, conn: duckdb.DuckDBPyConnection, session_id: str, 
                             template_id: int, column_name: str, rule_name: str) -> List[Dict]:
        """Validate a specific column rule using SQL"""
        try:
            errors = []
            
            if rule_name == 'Required':
                # Check for null or empty values
                result = conn.execute("""
                    SELECT row_index, column_value
                    FROM file_data
                    WHERE session_id = ? AND template_id = ? AND column_name = ?
                    AND (column_value IS NULL OR column_value = '' OR column_value = 'NULL')
                """, (session_id, template_id, column_name)).fetchall()
                
                for row_index, value in result:
                    errors.append({
                        'row': row_index + 1,
                        'value': 'NULL',
                        'rule_failed': 'Required',
                        'reason': 'Value is required'
                    })
            
            elif rule_name == 'Int':
                # Check for non-integer values
                result = conn.execute("""
                    SELECT row_index, column_value
                    FROM file_data
                    WHERE session_id = ? AND template_id = ? AND column_name = ?
                    AND column_value != 'NULL'
                    AND NOT regexp_matches(column_value, '^-?\\d+$')
                """, (session_id, template_id, column_name)).fetchall()
                
                for row_index, value in result:
                    errors.append({
                        'row': row_index + 1,
                        'value': value,
                        'rule_failed': 'Int',
                        'reason': 'Must be an integer'
                    })
            
            elif rule_name == 'Float':
                # Check for non-numeric values
                result = conn.execute("""
                    SELECT row_index, column_value
                    FROM file_data
                    WHERE session_id = ? AND template_id = ? AND column_name = ?
                    AND column_value != 'NULL'
                    AND NOT regexp_matches(column_value, '^-?\\d*\\.?\\d+$')
                """, (session_id, template_id, column_name)).fetchall()
                
                for row_index, value in result:
                    errors.append({
                        'row': row_index + 1,
                        'value': value,
                        'rule_failed': 'Float',
                        'reason': 'Must be a number'
                    })
            
            elif rule_name == 'Email':
                # Check for invalid email format
                result = conn.execute("""
                    SELECT row_index, column_value
                    FROM file_data
                    WHERE session_id = ? AND template_id = ? AND column_name = ?
                    AND column_value != 'NULL'
                    AND NOT regexp_matches(column_value, '^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$')
                """, (session_id, template_id, column_name)).fetchall()
                
                for row_index, value in result:
                    errors.append({
                        'row': row_index + 1,
                        'value': value,
                        'rule_failed': 'Email',
                        'reason': 'Invalid email format'
                    })
            
            elif rule_name == 'Alphanumeric':
                # Check for non-alphanumeric values
                result = conn.execute("""
                    SELECT row_index, column_value
                    FROM file_data
                    WHERE session_id = ? AND template_id = ? AND column_name = ?
                    AND column_value != 'NULL'
                    AND NOT regexp_matches(column_value, '^[a-zA-Z0-9]+$')
                """, (session_id, template_id, column_name)).fetchall()
                
                for row_index, value in result:
                    non_alphanum = ''.join([c for c in value if not c.isalnum()])
                    errors.append({
                        'row': row_index + 1,
                        'value': value,
                        'rule_failed': 'Alphanumeric',
                        'reason': f'Contains non-alphanumeric characters: {non_alphanum}'
                    })
            
            return errors
            
        except Exception as e:
            self.logger.error(f"Error validating column rule {rule_name}: {str(e)}")
            return []
    
    def get_data_rows(self, session_id: str, template_id: int, 
                     headers: List[str]) -> List[Dict[str, Any]]:
        """Get data rows from DuckDB"""
        try:
            conn = self.connection
            
            # Get all data for the session, pivoted by column
            query = """
                SELECT row_index, column_name, column_value
                FROM file_data
                WHERE session_id = ? AND template_id = ?
                ORDER BY row_index, column_name
            """
            
            result = conn.execute(query, (session_id, template_id)).fetchall()
            
            # Convert to row format
            rows_data = {}
            for row_index, column_name, column_value in result:
                if row_index not in rows_data:
                    rows_data[row_index] = {}
                rows_data[row_index][column_name] = column_value
            
            # Convert to list format
            data_rows = []
            for row_index in sorted(rows_data.keys()):
                row_data = {}
                for header in headers:
                    row_data[header] = rows_data[row_index].get(header, 'NULL')
                data_rows.append(row_data)
            
            return data_rows
            
        except Exception as e:
            self.logger.error(f"Error getting data rows: {str(e)}")
            return []
    
    def cleanup_session_data(self, session_id: str, template_id: int):
        """Clean up session data from DuckDB"""
        try:
            conn = self.connection
            
            # Delete file data
            conn.execute("""
                DELETE FROM file_data 
                WHERE session_id = ? AND template_id = ?
            """, (session_id, template_id))
            
            # Delete validation results
            conn.execute("""
                DELETE FROM validation_results 
                WHERE session_id = ? AND template_id = ?
            """, (session_id, template_id))
            
            self.logger.info(f"Cleaned up session data for {session_id}/{template_id}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up session data: {str(e)}")
    
    def _find_header_row(self, df: pd.DataFrame) -> int:
        """Find the header row in the dataframe"""
        for i in range(min(len(df), 10)):
            row = df.iloc[i].dropna()
            if not row.empty and all(isinstance(x, str) for x in row if pd.notna(x)):
                return i
        return 0
    
    def _detect_delimiter(self, file_path: str) -> str:
        """Detect CSV delimiter"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                sample = f.read(1024)
            
            delimiters = [',', ';', '|', '\t']
            delimiter_counts = {}
            
            for delim in delimiters:
                delimiter_counts[delim] = sample.count(delim)
            
            return max(delimiter_counts, key=delimiter_counts.get)
            
        except Exception:
            return ','
    
    def _process_data_chunks(self, data_rows: pd.DataFrame, headers: List[str], 
                            session_id: str, template_id: int, chunk_size: int):
        """Process data in chunks for large datasets"""
        try:
            conn = self.connection
            
            for start_idx in range(0, len(data_rows), chunk_size):
                end_idx = min(start_idx + chunk_size, len(data_rows))
                chunk = data_rows.iloc[start_idx:end_idx]
                
                # Prepare data for insertion
                data_to_insert = []
                for row_idx, (_, row) in enumerate(chunk.iterrows()):
                    global_row_idx = start_idx + row_idx
                    for col_name in headers:
                        value = str(row[col_name]) if pd.notna(row[col_name]) else 'NULL'
                        data_to_insert.append((session_id, template_id, global_row_idx, col_name, value))
                
                # Batch insert chunk data
                conn.executemany("""
                    INSERT INTO file_data (session_id, template_id, row_index, column_name, column_value)
                    VALUES (?, ?, ?, ?, ?)
                """, data_to_insert)
                
                self.logger.info(f"Processed chunk {start_idx}-{end_idx}")
                
        except Exception as e:
            self.logger.error(f"Error processing data chunks: {str(e)}")
            raise
    
    def _process_small_data(self, data_rows: pd.DataFrame, headers: List[str], 
                           session_id: str, template_id: int):
        """Process small datasets directly"""
        try:
            conn = self.connection
            
            # Prepare all data for insertion
            data_to_insert = []
            for row_idx, (_, row) in enumerate(data_rows.iterrows()):
                for col_name in headers:
                    value = str(row[col_name]) if pd.notna(row[col_name]) else 'NULL'
                    data_to_insert.append((session_id, template_id, row_idx, col_name, value))
            
            # Batch insert all data
            conn.executemany("""
                INSERT INTO file_data (session_id, template_id, row_index, column_name, column_value)
                VALUES (?, ?, ?, ?, ?)
            """, data_to_insert)
            
            self.logger.info(f"Processed {len(data_rows)} rows directly")
            
        except Exception as e:
            self.logger.error(f"Error processing small data: {str(e)}")
            raise
    
    def initialize_for_processing(self):
        """Initialize DuckDB specifically for large file processing"""
        try:
            # Create file_data table for temporary processing
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS file_data (
                    session_id VARCHAR,
                    template_id BIGINT,
                    row_index INTEGER,
                    column_name VARCHAR,
                    column_value VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_data_session 
                ON file_data(session_id, template_id)
            """)
            
            self.logger.info("DuckDB initialized for file processing")
            
        except Exception as e:
            self.logger.error(f"Error initializing DuckDB for processing: {str(e)}")
            raise
    
    def store_file_data(self, df, session_id: str) -> str:
        """Store file data temporarily in DuckDB for processing"""
        try:
            template_id = str(uuid.uuid4())
            
            # Clear any existing data for this session
            self.connection.execute(
                "DELETE FROM file_data WHERE session_id = ?", 
                (session_id,)
            )
            
            # Store data in long format for efficient processing
            data_to_insert = []
            for row_idx, row in df.iterrows():
                for col_name in df.columns:
                    value = str(row[col_name]) if pd.notna(row[col_name]) else ''
                    data_to_insert.append((
                        session_id, 
                        template_id, 
                        row_idx, 
                        col_name, 
                        value
                    ))
            
            # Batch insert for performance
            self.connection.executemany(
                "INSERT INTO file_data (session_id, template_id, row_index, column_name, column_value) VALUES (?, ?, ?, ?, ?)",
                data_to_insert
            )
            
            self.logger.info(f"Stored {len(df)} rows x {len(df.columns)} columns in DuckDB (session: {session_id})")
            return template_id
            
        except Exception as e:
            self.logger.error(f"Error storing file data in DuckDB: {str(e)}")
            raise
    
    def validate_data(self, session_id: str, template_id: str, validation_rules: Dict[str, List[str]]) -> Dict[str, Any]:
        """Validate data using DuckDB's SQL engine for performance"""
        try:
            start_time = time.time()
            errors = []
            
            # Get unique columns that have validation rules
            columns_to_validate = list(validation_rules.keys())
            
            if not columns_to_validate:
                return {
                    'errors': [],
                    'total_rows': 0,
                    'processing_time': 0
                }
            
            # Get total row count
            total_rows = self.connection.execute(
                "SELECT COUNT(DISTINCT row_index) FROM file_data WHERE session_id = ?",
                (session_id,)
            ).fetchone()[0]
            
            # Validate each column with its rules
            for column_name, rules in validation_rules.items():
                for rule_name in rules:
                    column_errors = self._validate_column_with_rule(
                        session_id, column_name, rule_name
                    )
                    errors.extend(column_errors)
            
            processing_time = int((time.time() - start_time) * 1000)  # milliseconds
            
            self.logger.info(f"DuckDB validation completed: {len(errors)} errors in {processing_time}ms")
            
            return {
                'errors': errors,
                'total_rows': total_rows,
                'processing_time': processing_time,
                'file_size_mb': self._get_session_size_mb(session_id)
            }
            
        except Exception as e:
            self.logger.error(f"Error during DuckDB validation: {str(e)}")
            raise
    
    def _validate_column_with_rule(self, session_id: str, column_name: str, rule_name: str) -> List[Dict[str, Any]]:
        """Validate a specific column with a specific rule using DuckDB SQL"""
        errors = []
        
        try:
            if rule_name == 'Required':
                # Check for null/empty values
                results = self.connection.execute("""
                    SELECT row_index, column_value 
                    FROM file_data 
                    WHERE session_id = ? AND column_name = ? 
                    AND (column_value IS NULL OR column_value = '' OR TRIM(column_value) = '')
                """, (session_id, column_name)).fetchall()
                
                for row_index, value in results:
                    errors.append({
                        'row_index': row_index,
                        'column_name': column_name,
                        'original_value': value or '',
                        'rule_failed': 'Required',
                        'error_message': 'Required field cannot be empty'
                    })
            
            elif rule_name == 'Int':
                # Check for non-integer values
                results = self.connection.execute("""
                    SELECT row_index, column_value 
                    FROM file_data 
                    WHERE session_id = ? AND column_name = ? 
                    AND column_value IS NOT NULL AND TRIM(column_value) != ''
                    AND NOT REGEXP_MATCHES(TRIM(column_value), '^-?\\d+
)
                """, (session_id, column_name)).fetchall()
                
                for row_index, value in results:
                    errors.append({
                        'row_index': row_index,
                        'column_name': column_name,
                        'original_value': value,
                        'rule_failed': 'Int',
                        'error_message': 'Value must be an integer'
                    })
            
            elif rule_name == 'Float':
                # Check for non-numeric values
                results = self.connection.execute("""
                    SELECT row_index, column_value 
                    FROM file_data 
                    WHERE session_id = ? AND column_name = ? 
                    AND column_value IS NOT NULL AND TRIM(column_value) != ''
                    AND NOT REGEXP_MATCHES(TRIM(column_value), '^-?\\d*\\.?\\d+
)
                """, (session_id, column_name)).fetchall()
                
                for row_index, value in results:
                    errors.append({
                        'row_index': row_index,
                        'column_name': column_name,
                        'original_value': value,
                        'rule_failed': 'Float',
                        'error_message': 'Value must be a number'
                    })
            
            elif rule_name == 'Email':
                # Check for invalid email format
                results = self.connection.execute("""
                    SELECT row_index, column_value 
                    FROM file_data 
                    WHERE session_id = ? AND column_name = ? 
                    AND column_value IS NOT NULL AND TRIM(column_value) != ''
                    AND NOT REGEXP_MATCHES(TRIM(column_value), '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}
)
                """, (session_id, column_name)).fetchall()
                
                for row_index, value in results:
                    errors.append({
                        'row_index': row_index,
                        'column_name': column_name,
                        'original_value': value,
                        'rule_failed': 'Email',
                        'error_message': 'Invalid email format'
                    })
            
            # Add more validation rules as needed
            
        except Exception as e:
            self.logger.error(f"Error validating column {column_name} with rule {rule_name}: {str(e)}")
        
        return errors
    
    def _get_session_size_mb(self, session_id: str) -> float:
        """Calculate approximate size of session data in MB"""
        try:
            result = self.connection.execute("""
                SELECT COUNT(*) * AVG(LENGTH(column_value)) 
                FROM file_data 
                WHERE session_id = ?
            """, (session_id,)).fetchone()
            
            size_bytes = result[0] if result and result[0] else 0
            return round(size_bytes / (1024 * 1024), 2)  # Convert to MB
            
        except Exception as e:
            self.logger.warning(f"Error calculating session size: {str(e)}")
            return 0.0
    
    def cleanup_session_data(self, session_id: str):
        """Clean up session data from DuckDB"""
        try:
            self.connection.execute(
                "DELETE FROM file_data WHERE session_id = ?",
                (session_id,)
            )
            self.logger.info(f"Cleaned up session data: {session_id}")
        except Exception as e:
            self.logger.error(f"Error cleaning up session data: {str(e)}")
    
    def test_connection(self) -> Dict[str, str]:
        """Test DuckDB connection"""
        try:
            result = self.connection.execute("SELECT 1 as test").fetchone()
            return {'status': 'success', 'message': 'DuckDB connection working'}
        except Exception as e:
            return {'status': 'error', 'message': f'DuckDB error: {str(e)}'}
    
    def close_connection(self):
        """Close DuckDB connection"""
        if self.connection:
            self.connection.close()
            self.logger.info("DuckDB connection closed")

# Global service instance
duckdb_service = DuckDBService()
