"""
Create Rule Configuration History Table
Stores history of configured files with metadata for easy retrieval and management
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.fabric_service import fabric_service

def create_configuration_history_table():
    """Create the rule_configuration_history table"""
    
    try:
        print("Creating rule_configuration_history table...")
        
        # Create the configuration history table
        create_sql = """
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'rule_configuration_history')
        BEGIN
            CREATE TABLE rule_configuration_history (
                history_id INT IDENTITY(1,1) PRIMARY KEY,
                user_id INT NOT NULL,
                template_id INT NOT NULL,
                file_name NVARCHAR(500) NOT NULL,
                original_file_name NVARCHAR(500) NOT NULL,
                sheet_name NVARCHAR(255),
                total_rules_configured INT DEFAULT 0,
                configured_columns_count INT DEFAULT 0,
                configuration_summary NVARCHAR(MAX), -- JSON string of configured rules
                file_size_mb DECIMAL(10,2),
                total_rows INT DEFAULT 0,
                created_at DATETIME2 DEFAULT GETDATE(),
                updated_at DATETIME2 DEFAULT GETDATE(),
                is_active BIT DEFAULT 1,
                
                -- Foreign key constraints
                CONSTRAINT FK_rule_config_history_user 
                    FOREIGN KEY (user_id) REFERENCES users(id),
                CONSTRAINT FK_rule_config_history_template 
                    FOREIGN KEY (template_id) REFERENCES excel_templates(template_id),
                
                -- Indexes for performance
                INDEX IX_config_history_user_active (user_id, is_active),
                INDEX IX_config_history_created_at (created_at DESC)
            )
            PRINT 'Created rule_configuration_history table successfully!'
        END
        ELSE
        BEGIN
            PRINT 'rule_configuration_history table already exists'
        END
        """
        
        fabric_service.execute_non_query(create_sql)
        print("Configuration history table creation completed!")
        
        # Test the table
        test_query = "SELECT COUNT(*) FROM rule_configuration_history"
        result = fabric_service.execute_query(test_query)
        print(f"Table test successful - contains {result[0][0]} records")
        
        return True
        
    except Exception as e:
        print(f"Failed to create configuration history table: {e}")
        return False

def create_helper_procedures():
    """Create stored procedures to help with configuration history management"""
    
    try:
        print("Creating helper procedures...")
        
        # Procedure to update configuration history when rules are modified
        update_proc_sql = """
        IF OBJECT_ID('sp_UpdateConfigurationHistory', 'P') IS NOT NULL
            DROP PROCEDURE sp_UpdateConfigurationHistory
        """
        fabric_service.execute_non_query(update_proc_sql)
        
        create_proc_sql = """
        CREATE PROCEDURE sp_UpdateConfigurationHistory
            @template_id INT
        AS
        BEGIN
            SET NOCOUNT ON;
            
            -- Update the configuration history record
            UPDATE rch 
            SET 
                total_rules_configured = rule_counts.total_rules,
                configured_columns_count = rule_counts.column_count,
                configuration_summary = rule_counts.rule_summary,
                updated_at = GETDATE()
            FROM rule_configuration_history rch
            CROSS APPLY (
                SELECT 
                    COUNT(cvr.column_validation_id) as total_rules,
                    COUNT(DISTINCT tc.column_id) as column_count,
                    STRING_AGG(CONCAT(tc.column_name, ':', vrt.rule_name), '; ') as rule_summary
                FROM template_columns tc
                JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id  
                JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
                WHERE tc.template_id = @template_id AND tc.is_selected = 1
            ) rule_counts
            WHERE rch.template_id = @template_id
        END
        """
        fabric_service.execute_non_query(create_proc_sql)
        print("Helper procedures created successfully!")
        
        return True
        
    except Exception as e:
        print(f"Failed to create helper procedures: {e}")
        return False

if __name__ == "__main__":
    if create_configuration_history_table() and create_helper_procedures():
        print("\n✅ SUCCESS! Configuration history table and procedures created!")
        print("\nNext steps:")
        print("1. Run: python update_models_for_history.py")
        print("2. Run: python create_history_routes.py") 
        print("3. Restart your Flask server")
        print("4. Test the new history functionality")
    else:
        print("\n❌ Failed to create configuration history components")
