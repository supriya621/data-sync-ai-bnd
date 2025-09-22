-- Rule Configuration History Table
-- Stores configuration history for users with all required metadata

CREATE TABLE rule_configuration_history (
    history_id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NOT NULL,
    template_id INT NOT NULL,
    file_name NVARCHAR(255) NOT NULL,          -- Internal filename
    original_file_name NVARCHAR(255) NOT NULL,  -- User-friendly filename
    sheet_name NVARCHAR(100),                   -- Excel sheet name if applicable
    total_rules_configured INT DEFAULT 0,
    configured_columns_count INT DEFAULT 0,
    configuration_summary NTEXT,                -- JSON string of rule details
    file_size_mb DECIMAL(10,2),                -- File size in MB
    total_rows INT,                             -- Total rows in the file
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE(),
    is_active BIT DEFAULT 1,                    -- Soft delete flag
    
    -- Foreign key constraints
    FOREIGN KEY (user_id) REFERENCES login_details(id),
    FOREIGN KEY (template_id) REFERENCES excel_templates(template_id)
);

-- Indexes for better performance
CREATE INDEX IX_rule_configuration_history_user_id ON rule_configuration_history(user_id);
CREATE INDEX IX_rule_configuration_history_template_id ON rule_configuration_history(template_id);
CREATE INDEX IX_rule_configuration_history_created_at ON rule_configuration_history(created_at);
CREATE INDEX IX_rule_configuration_history_is_active ON rule_configuration_history(is_active);

-- Composite index for common queries
CREATE INDEX IX_rule_configuration_history_user_active ON rule_configuration_history(user_id, is_active, updated_at);

PRINT 'Rule Configuration History table created successfully with indexes';
