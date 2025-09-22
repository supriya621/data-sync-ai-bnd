"""
File Configuration History - Track user file configurations
Saves file details, headers, and rule configurations for history display
"""

import json
import logging
from datetime import datetime
from backend.services.fabric_service import fabric_service

logger = logging.getLogger(__name__)

def save_file_configuration_history(user_id, file_name, original_file_name, file_headers, 
                                   configured_rules, sheet_name=None, file_size_mb=None, 
                                   total_rows=None):
    """
    Save file configuration history when user configures validation rules
    
    Args:
        user_id (int): User ID from session
        file_name (str): Internal file name (with timestamp)
        original_file_name (str): Original uploaded file name
        file_headers (list): List of column headers from the file
        configured_rules (dict): Dictionary mapping column_name -> [rule_names]
        sheet_name (str, optional): Excel sheet name
        file_size_mb (float, optional): File size in MB
        total_rows (int, optional): Number of data rows
    
    Returns:
        int: history_id of created record, or None if failed
    """
    try:
        # Convert headers and rules to JSON
        headers_json = json.dumps(file_headers) if file_headers else '[]'
        rules_json = json.dumps(configured_rules) if configured_rules else '{}'
        
        # Calculate summary statistics
        total_rules = sum(len(rules) for rules in configured_rules.values()) if configured_rules else 0
        configured_columns = len([col for col, rules in configured_rules.items() if rules]) if configured_rules else 0
        
        # Create configuration summary
        summary_parts = []
        if configured_rules:
            for column, rules in configured_rules.items():
                if rules:  # Only include columns with rules
                    summary_parts.append(f"{column}: {', '.join(rules)}")
        
        configuration_summary = '; '.join(summary_parts[:5])  # Limit summary length
        if len(summary_parts) > 5:
            configuration_summary += f" ... (+{len(summary_parts) - 5} more)"
        
        # Insert configuration history
        insert_query = """
        INSERT INTO rule_configuration_history (
            user_id, file_name, original_file_name, sheet_name,
            file_headers, configured_rules, total_rules_configured,
            configured_columns_count, configuration_summary,
            file_size_mb, total_rows, validation_status,
            created_at, updated_at, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CONFIGURED', GETDATE(), GETDATE(), 1)
        """
        
        fabric_service.execute_non_query(insert_query, (
            user_id,
            file_name,
            original_file_name,
            sheet_name,
            headers_json,
            rules_json,
            total_rules,
            configured_columns,
            configuration_summary,
            file_size_mb,
            total_rows
        ))
        
        # Get the created history_id
        get_id_query = """
        SELECT TOP 1 history_id 
        FROM rule_configuration_history 
        WHERE user_id = ? AND file_name = ?
        ORDER BY created_at DESC
        """
        
        result = fabric_service.execute_query(get_id_query, (user_id, file_name))
        history_id = result[0]['history_id'] if result else None
        
        logger.info(f"Saved file configuration history {history_id}: {original_file_name} "
                   f"({configured_columns} columns, {total_rules} rules)")
        
        return history_id
        
    except Exception as e:
        logger.error(f"Error saving file configuration history: {e}")
        return None

def update_file_validation_status(history_id, validation_status, validation_results=None):
    """
    Update the validation status of a configuration history record
    
    Args:
        history_id (int): Configuration history ID
        validation_status (str): Status like 'VALIDATED', 'PROCESSING', 'COMPLETED'
        validation_results (dict, optional): Results from validation process
    """
    try:
        update_query = """
        UPDATE rule_configuration_history 
        SET validation_status = ?, updated_at = GETDATE()
        WHERE history_id = ?
        """
        
        fabric_service.execute_non_query(update_query, (validation_status, history_id))
        logger.info(f"Updated history {history_id} status to {validation_status}")
        
    except Exception as e:
        logger.error(f"Error updating validation status for history {history_id}: {e}")

def get_user_configuration_history(user_id, limit=20, offset=0):
    """
    Get configuration history for a user
    
    Args:
        user_id (int): User ID
        limit (int): Number of records to return
        offset (int): Offset for pagination
        
    Returns:
        dict: Configuration history data with pagination info
    """
    try:
        # Get configuration history records
        history_query = """
        SELECT 
            history_id,
            file_name,
            original_file_name,
            sheet_name,
            file_headers,
            configured_rules,
            total_rules_configured,
            configured_columns_count,
            configuration_summary,
            file_size_mb,
            total_rows,
            validation_status,
            created_at,
            updated_at
        FROM rule_configuration_history
        WHERE user_id = ? AND is_active = 1
        ORDER BY created_at DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
        
        history_records = fabric_service.execute_query(history_query, (user_id, offset, limit))
        
        # Get total count
        count_query = """
        SELECT COUNT(*) as total
        FROM rule_configuration_history
        WHERE user_id = ? AND is_active = 1
        """
        total_result = fabric_service.execute_query(count_query, (user_id,))
        total_count = total_result[0]['total'] if total_result else 0
        
        # Format records for frontend
        formatted_history = []
        for record in history_records:
            try:
                # Parse JSON fields
                headers = json.loads(record['file_headers']) if record['file_headers'] else []
                rules = json.loads(record['configured_rules']) if record['configured_rules'] else {}
                
                formatted_record = {
                    'history_id': record['history_id'],
                    'file_name': record['original_file_name'],  # Show original name to user
                    'sheet_name': record['sheet_name'] or 'Sheet1',
                    'headers': headers,
                    'configured_rules': rules,
                    'total_rules': record['total_rules_configured'] or 0,
                    'configured_columns': record['configured_columns_count'] or 0,
                    'configuration_summary': record['configuration_summary'] or '',
                    'file_size_mb': float(record['file_size_mb']) if record['file_size_mb'] else 0,
                    'total_rows': record['total_rows'] or 0,
                    'status': record['validation_status'] or 'CONFIGURED',
                    'configured_date': record['created_at'].strftime('%Y-%m-%d %H:%M') if record['created_at'] else '',
                    'last_updated': record['updated_at'].strftime('%Y-%m-%d %H:%M') if record['updated_at'] else '',
                    'can_revalidate': record['total_rules_configured'] > 0,
                    'headers_count': len(headers)
                }
                
                formatted_history.append(formatted_record)
                
            except Exception as parse_error:
                logger.warning(f"Error parsing history record {record['history_id']}: {parse_error}")
                # Add basic record even if JSON parsing fails
                formatted_record = {
                    'history_id': record['history_id'],
                    'file_name': record['original_file_name'],
                    'sheet_name': record['sheet_name'] or 'Sheet1',
                    'headers': [],
                    'configured_rules': {},
                    'total_rules': record['total_rules_configured'] or 0,
                    'configured_columns': record['configured_columns_count'] or 0,
                    'configuration_summary': record['configuration_summary'] or '',
                    'status': record['validation_status'] or 'ERROR',
                    'configured_date': record['created_at'].strftime('%Y-%m-%d %H:%M') if record['created_at'] else '',
                    'can_revalidate': False,
                    'headers_count': 0
                }
                formatted_history.append(formatted_record)
        
        return {
            'success': True,
            'history': formatted_history,
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + limit) < total_count
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting configuration history for user {user_id}: {e}")
        return {
            'success': False,
            'message': f'Failed to get configuration history: {str(e)}',
            'history': [],
            'pagination': {'total': 0, 'limit': limit, 'offset': offset, 'has_more': False}
        }

def delete_configuration_history(history_id, user_id):
    """
    Delete (soft delete) a configuration history record
    
    Args:
        history_id (int): History record ID to delete
        user_id (int): User ID (for ownership verification)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Verify ownership
        verify_query = """
        SELECT history_id FROM rule_configuration_history
        WHERE history_id = ? AND user_id = ? AND is_active = 1
        """
        
        verification = fabric_service.execute_query(verify_query, (history_id, user_id))
        
        if not verification:
            logger.warning(f"History {history_id} not found or not owned by user {user_id}")
            return False
        
        # Soft delete
        delete_query = """
        UPDATE rule_configuration_history
        SET is_active = 0, updated_at = GETDATE()
        WHERE history_id = ? AND user_id = ?
        """
        
        fabric_service.execute_non_query(delete_query, (history_id, user_id))
        logger.info(f"Deleted configuration history {history_id} for user {user_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error deleting configuration history {history_id}: {e}")
        return False

# Example usage functions for integration with your file upload/validation workflow

def example_save_configuration_when_user_configures_file():
    """
    Example of how to use this in your file configuration workflow
    Call this function when user completes rule configuration
    """
    
    # Example data (replace with actual data from your workflow)
    user_id = 1  # From session['user_id']
    file_name = "data_2025-09-22_15-30-45.xlsx"  # Internal name with timestamp
    original_file_name = "customer_data.xlsx"  # Original uploaded name
    file_headers = ["Name", "Email", "Age", "Department", "Salary"]  # From pandas
    
    # Configured rules - what user selected for each column
    configured_rules = {
        "Name": ["Required", "Text"],
        "Email": ["Required", "Email"],
        "Age": ["Required", "Int"],
        "Department": ["Required", "Text"],
        "Salary": ["Required", "Float"]
    }
    
    sheet_name = "Sheet1"
    file_size_mb = 2.5
    total_rows = 1500
    
    # Save the configuration
    history_id = save_file_configuration_history(
        user_id=user_id,
        file_name=file_name,
        original_file_name=original_file_name,
        file_headers=file_headers,
        configured_rules=configured_rules,
        sheet_name=sheet_name,
        file_size_mb=file_size_mb,
        total_rows=total_rows
    )
    
    return history_id

def example_integration_points():
    """
    Examples of where to integrate these functions in your existing code:
    
    1. In file upload endpoint - extract headers and basic info
    2. In rule configuration endpoint - save configured rules
    3. In validation endpoint - update validation status
    4. In history display endpoint - show user's configuration history
    """
    pass
