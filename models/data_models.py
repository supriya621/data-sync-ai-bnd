"""
Data models and structures
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class TemplateStatus(Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class ValidationFrequency(Enum):
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"

class ProcessingMethod(Enum):
    PANDAS = "PANDAS"
    DUCKDB = "DUCKDB"

@dataclass
class User:
    """User model"""
    id: int
    first_name: str
    last_name: str
    email: str
    mobile: str
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'mobile': self.mobile,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

@dataclass
class Template:
    """Template model"""
    template_id: int
    template_name: str
    user_id: int
    sheet_name: str
    headers: List[str]
    status: TemplateStatus = TemplateStatus.ACTIVE
    is_corrected: bool = False
    validation_frequency: Optional[ValidationFrequency] = None
    remote_file_path: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'template_id': self.template_id,
            'template_name': self.template_name,
            'user_id': self.user_id,
            'sheet_name': self.sheet_name,
            'headers': self.headers,
            'status': self.status.value,
            'is_corrected': self.is_corrected,
            'validation_frequency': self.validation_frequency.value if self.validation_frequency else None,
            'remote_file_path': self.remote_file_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

@dataclass
class ValidationRule:
    """Validation rule model"""
    rule_type_id: int
    rule_name: str
    description: str
    parameters: Dict[str, Any]
    is_active: bool = True
    is_custom: bool = False
    column_name: Optional[str] = None
    template_id: Optional[int] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'rule_type_id': self.rule_type_id,
            'rule_name': self.rule_name,
            'description': self.description,
            'parameters': self.parameters,
            'is_active': self.is_active,
            'is_custom': self.is_custom,
            'column_name': self.column_name,
            'template_id': self.template_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

@dataclass
class ValidationError:
    """Validation error model"""
    row: int
    value: str
    rule_failed: str
    reason: str
    column_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'row': self.row,
            'value': self.value,
            'rule_failed': self.rule_failed,
            'reason': self.reason,
            'column_name': self.column_name
        }

@dataclass
class ValidationResult:
    """Validation result model"""
    template_id: int
    error_cell_locations: Dict[str, List[ValidationError]]
    data_rows: List[Dict[str, Any]]
    processing_time_ms: int
    processing_method: ProcessingMethod
    total_errors: int = 0
    timestamp: Optional[datetime] = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'template_id': self.template_id,
            'error_cell_locations': {
                col: [error.to_dict() for error in errors] 
                for col, errors in self.error_cell_locations.items()
            },
            'data_rows': self.data_rows,
            'processing_time_ms': self.processing_time_ms,
            'processing_method': self.processing_method.value,
            'total_errors': self.total_errors,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

@dataclass
class FileInfo:
    """File information model"""
    filename: str
    size_bytes: int
    size_mb: float
    created_at: float
    modified_at: float
    is_large_file: bool
    file_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'filename': self.filename,
            'size_bytes': self.size_bytes,
            'size_mb': self.size_mb,
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'is_large_file': self.is_large_file,
            'file_type': self.file_type
        }

@dataclass
class UploadResult:
    """File upload result model"""
    success: bool
    template_id: Optional[int]
    filename: str
    processing_method: ProcessingMethod
    processing_time_ms: int
    has_existing_rules: bool
    headers: List[str]
    sheet_name: str
    file_info: Optional[FileInfo] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'template_id': self.template_id,
            'filename': self.filename,
            'processing_method': self.processing_method.value,
            'processing_time_ms': self.processing_time_ms,
            'has_existing_rules': self.has_existing_rules,
            'headers': self.headers,
            'sheet_name': self.sheet_name,
            'file_info': self.file_info.to_dict() if self.file_info else None,
            'error_message': self.error_message
        }

@dataclass
class SessionData:
    """Session data model"""
    session_id: str
    user_id: Optional[int]
    template_id: Optional[int]
    file_path: Optional[str]
    headers: List[str] = field(default_factory=list)
    current_step: int = 1
    is_large_file: bool = False
    processing_time: int = 0
    has_existing_rules: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'template_id': self.template_id,
            'file_path': self.file_path,
            'headers': self.headers,
            'current_step': self.current_step,
            'is_large_file': self.is_large_file,
            'processing_time': self.processing_time,
            'has_existing_rules': self.has_existing_rules
        }

class APIResponse:
    """Standard API response format"""
    
    @staticmethod
    def success(data: Any = None, message: str = "Success") -> Dict[str, Any]:
        response = {'success': True, 'message': message}
        if data is not None:
            response['data'] = data
        return response
    
    @staticmethod
    def error(message: str, error_code: str = None, details: Any = None) -> Dict[str, Any]:
        response = {'success': False, 'message': message}
        if error_code:
            response['error_code'] = error_code
        if details:
            response['details'] = details
        return response
    
    @staticmethod
    def validation_error(errors: Dict[str, List[str]]) -> Dict[str, Any]:
        return {
            'success': False,
            'message': 'Validation failed',
            'validation_errors': errors
        }
