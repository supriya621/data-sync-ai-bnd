import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.fabric_service import fabric_service

# Simple creation with the correct BIGINT data type
sql = """CREATE TABLE column_validations (
    id INT IDENTITY(1,1) PRIMARY KEY,
    template_id INT NOT NULL,
    column_name NVARCHAR(255) NOT NULL,
    rule_type_id BIGINT NOT NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    CONSTRAINT FK_column_validations_rule_type 
        FOREIGN KEY (rule_type_id) REFERENCES validation_rule_types(rule_type_id)
)"""

try:
    fabric_service.execute_non_query(sql)
    print("SUCCESS: column_validations table created with BIGINT rule_type_id!")
    print("Restart your Flask server and test rule configuration.")
except Exception as e:
    print(f"Error: {e}")
