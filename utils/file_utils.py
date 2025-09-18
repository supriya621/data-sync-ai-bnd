"""
File processing utilities
"""

import os
import csv
import pandas as pd
import logging
from io import StringIO
from typing import Dict, Tuple, Any
from config.config import config
from services.duckdb_service import duckdb_service

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv', 'txt', 'dat'}

def is_allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_large_file(file_path: str) -> bool:
    """Determine if file is large and needs DuckDB processing"""
    try:
        if file_path.endswith(('.xlsx', '.xls')):
            # Estimate rows from file size
            file_size = os.path.getsize(file_path)
            estimated_rows = file_size / 1024  # Rough estimate
            return estimated_rows > config.LARGE_FILE_THRESHOLD
        elif file_path.endswith(('.csv', '.txt', '.dat')):
            row_count = sum(1 for line in open(file_path, 'r', encoding='utf-8')) - 1
            return row_count > config.LARGE_FILE_THRESHOLD
        return False
    except Exception as e:
        logger.warning(f"Could not determine file size: {e}")
        return False

def read_file_optimized(file_path: str, template_id: int = None) -> Tuple[Dict, bool]:
    """Read file with optimization for large files"""
    try:
        from utils.session_utils import get_session_id
        session_id = get_session_id()
        
        # Check if it's a large file
        if is_large_file(file_path):
            logger.info(f"Processing large file with DuckDB: {file_path}")
            
            # Use DuckDB for large file processing
            result = duckdb_service.load_file_data(file_path, session_id, template_id or 0)
            
            if result['success']:
                return result['sheets'], True  # True indicates DuckDB processing
            else:
                raise Exception("Failed to process large file with DuckDB")
        else:
            logger.info(f"Processing small file directly: {file_path}")
            
            # Use traditional pandas processing for small files
            return read_file_traditional(file_path), False  # False indicates traditional processing
            
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
        raise

def read_file_traditional(file_path: str) -> Dict:
    """Traditional file reading method for smaller files"""
    try:
        if file_path.endswith(('.xlsx', '.xls')):
            xl = pd.ExcelFile(file_path)
            sheets = {sheet_name: pd.read_excel(file_path, sheet_name=sheet_name, header=None) 
                     for sheet_name in xl.sheet_names}
            return sheets
        elif file_path.endswith(('.txt', '.csv', '.dat')):
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            if not content.strip():
                raise ValueError("File is empty.")
            
            try:
                dialect = csv.Sniffer().sniff(content[:1024])
                sep = dialect.delimiter
            except:
                sep = detect_delimiter(file_path)
            
            df = pd.read_csv(file_path, header=None, sep=sep, encoding='utf-8', quotechar='"', engine='python')
            df.columns = [str(col) for col in df.columns]
            return {'Sheet1': df}
        else:
            raise ValueError("Unsupported file type.")
    except Exception as e:
        raise ValueError(f"Error reading file: {str(e)}")

def detect_delimiter(file_path: str) -> str:
    """Detect delimiter for CSV files"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(1024)
        if not content.strip():
            return ','
        
        delimiters = [',', ';', '|', '/', '\t', ':', '-']
        best_delimiter, max_columns = None, 0
        
        for delim in delimiters:
            try:
                sample_df = pd.read_csv(StringIO(content), sep=delim, header=None, nrows=5)
                if sample_df.shape[1] > max_columns:
                    max_columns = sample_df.shape[1]
                    best_delimiter = delim
            except Exception:
                continue
        
        return best_delimiter or ','
    except Exception:
        return ','

def find_header_row(df: pd.DataFrame, max_rows: int = 10) -> int:
    """Find header row in dataframe"""
    try:
        for i in range(min(len(df), max_rows)):
            row = df.iloc[i].dropna()
            if not row.empty and all(isinstance(x, str) for x in row if pd.notna(x)):
                return i
        return 0 if not df.empty and len(df.columns) > 0 else -1
    except Exception:
        return -1

def get_file_info(file_path: str) -> Dict[str, Any]:
    """Get file information"""
    try:
        if not os.path.exists(file_path):
            return None
        
        stat = os.stat(file_path)
        return {
            'size_bytes': stat.st_size,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'created_at': stat.st_ctime,
            'modified_at': stat.st_mtime,
            'is_large_file': is_large_file(file_path)
        }
    except Exception as e:
        logger.error(f"Error getting file info for {file_path}: {e}")
        return None

def validate_file_content(file_path: str) -> Dict[str, Any]:
    """Validate file content and structure"""
    try:
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'info': {}
        }
        
        # Check file size
        file_size = os.path.getsize(file_path)
        max_size = config.MAX_FILE_SIZE_MB * 1024 * 1024
        
        if file_size > max_size:
            result['valid'] = False
            result['errors'].append(f"File size ({file_size / (1024*1024):.2f}MB) exceeds limit ({config.MAX_FILE_SIZE_MB}MB)")
        
        # Try to read file structure
        try:
            sheets, is_large = read_file_optimized(file_path)
            
            if not sheets:
                result['valid'] = False
                result['errors'].append("No readable sheets found in file")
                return result
            
            # Check each sheet
            for sheet_name, sheet_data in sheets.items():
                if is_large:
                    # For DuckDB processed files
                    headers = sheet_data.get('headers', [])
                    row_count = sheet_data.get('row_count', 0)
                else:
                    # For traditionally processed files
                    if hasattr(sheet_data, 'shape'):
                        row_count = sheet_data.shape[0]
                        header_row = find_header_row(sheet_data)
                        headers = sheet_data.iloc[header_row].tolist() if header_row != -1 else []
                    else:
                        row_count = 0
                        headers = []
                
                result['info'][sheet_name] = {
                    'headers': headers,
                    'row_count': row_count,
                    'processing_method': 'DuckDB' if is_large else 'Pandas'
                }
                
                if not headers:
                    result['warnings'].append(f"No headers detected in sheet '{sheet_name}'")
                
                if row_count == 0:
                    result['warnings'].append(f"No data rows found in sheet '{sheet_name}'")
        
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f"Failed to read file content: {str(e)}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error validating file content: {e}")
        return {
            'valid': False,
            'errors': [f"File validation failed: {str(e)}"],
            'warnings': [],
            'info': {}
        }

def cleanup_uploaded_file(file_path: str):
    """Clean up uploaded file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup file {file_path}: {e}")

def normalize_data_rows(data_rows: list) -> list:
    """Normalize data rows for consistent frontend handling"""
    normalized = []
    for row in data_rows:
        normalized_row = {}
        for key, value in row.items():
            if value is None or value == '' or pd.isna(value):
                normalized_row[key] = 'NULL'
            else:
                normalized_row[key] = str(value)
        normalized.append(normalized_row)
    return normalized
