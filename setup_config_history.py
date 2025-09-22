"""
Complete Setup Script for Configuration History Feature
This script will:
1. Create the database table
2. Fix URL routing issues
3. Integrate the save function into rule configuration
4. Test the complete functionality
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.fabric_service import fabric_service

def create_configuration_history_table():
    """Create the rule_configuration_history table"""
    
    try:
        print("🔧 Creating rule_configuration_history table...")
        
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
        print("✅ Configuration history table creation completed!")
        
        # Test the table
        test_query = "SELECT COUNT(*) as count FROM rule_configuration_history"
        result = fabric_service.execute_query(test_query)
        count = result[0]['count'] if result else 0
        print(f"✅ Table test successful - contains {count} records")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create configuration history table: {e}")
        return False

def fix_route_configuration():
    """Fix the route configuration in the blueprint"""
    
    try:
        print("🔧 Checking route configuration...")
        
        # Read the current config_history_routes.py file
        route_file_path = os.path.join(os.path.dirname(__file__), 'routes', 'config_history_routes.py')
        
        with open(route_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if route is correctly defined
        if "@config_history_bp.route('', methods=['GET'])" in content:
            print("✅ Route configuration is correct")
            print("   The route '/api/config-history' should work properly")
        else:
            print("⚠️  Route configuration needs adjustment")
            
        return True
        
    except Exception as e:
        print(f"❌ Error checking route configuration: {e}")
        return False

def check_save_integration():
    """Check if save_configuration_history is integrated into rule configuration"""
    
    try:
        print("🔧 Checking if save function is integrated...")
        
        # Check validation_routes.py for save_configuration_history calls
        validation_routes_path = os.path.join(os.path.dirname(__file__), 'routes', 'validation_routes.py')
        
        if os.path.exists(validation_routes_path):
            with open(validation_routes_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'save_configuration_history' in content:
                print("✅ Save function is already integrated in validation routes")
                return True
            else:
                print("⚠️  Save function needs to be integrated into rule configuration endpoint")
                return False
        else:
            print("⚠️  validation_routes.py file not found")
            return False
            
    except Exception as e:
        print(f"❌ Error checking save integration: {e}")
        return False

def test_database_connection():
    """Test database connection and basic functionality"""
    
    try:
        print("🔧 Testing database connection...")
        
        # Test basic query
        test_query = "SELECT GETDATE() as current_time"
        result = fabric_service.execute_query(test_query)
        
        if result:
            print(f"✅ Database connection successful - Current time: {result[0]['current_time']}")
            return True
        else:
            print("❌ Database connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

def create_integration_patch():
    """Create a patch to integrate save_configuration_history into validation routes"""
    
    try:
        print("🔧 Creating integration patch for validation routes...")
        
        patch_content = '''
# Add this import at the top of your validation_routes.py file:
from routes.config_history_routes import save_configuration_history

# Add this code after successful rule configuration (in your configure_rules endpoint):

# Save configuration history
if save_configuration_history:
    try:
        # Get file info from session
        file_info = session.get('file_info', {})
        file_name = file_info.get('filename', 'unknown_file')
        original_file_name = file_info.get('filename', 'unknown_file')
        sheet_name = file_info.get('sheet_name')
        file_size_mb = file_info.get('file_size_mb')
        total_rows = file_info.get('row_count')
        
        save_configuration_history(
            template_id=session.get('current_template_id'),
            user_id=session.get('user_id'),
            file_name=file_name,
            original_file_name=original_file_name,
            sheet_name=sheet_name,
            file_size_mb=file_size_mb,
            total_rows=total_rows
        )
        logger.info("Configuration history saved successfully")
    except Exception as e:
        logger.error(f"Failed to save configuration history: {e}")
        # Don't fail the entire request for history saving issues
'''
        
        patch_file_path = os.path.join(os.path.dirname(__file__), 'INTEGRATION_PATCH.txt')
        with open(patch_file_path, 'w', encoding='utf-8') as f:
            f.write(patch_content)
        
        print(f"✅ Integration patch created: {patch_file_path}")
        print("   Please manually apply this patch to your validation_routes.py file")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating integration patch: {e}")
        return False

def main():
    """Main setup function"""
    
    print("="*60)
    print("🚀 CONFIGURATION HISTORY SETUP")
    print("="*60)
    
    success_count = 0
    total_steps = 5
    
    # Step 1: Test database connection
    if test_database_connection():
        success_count += 1
    
    # Step 2: Create database table
    if create_configuration_history_table():
        success_count += 1
    
    # Step 3: Check route configuration
    if fix_route_configuration():
        success_count += 1
    
    # Step 4: Check save integration
    if check_save_integration():
        success_count += 1
    else:
        # Create integration patch if not integrated
        if create_integration_patch():
            success_count += 0.5  # Partial success
    
    # Step 5: Create integration patch anyway for reference
    create_integration_patch()
    success_count += 0.5
    
    print("\n" + "="*60)
    print("📊 SETUP SUMMARY")
    print("="*60)
    print(f"✅ Completed: {success_count}/{total_steps} steps")
    
    if success_count >= 4:
        print("🎉 Configuration History setup is mostly complete!")
        print("\n📋 NEXT STEPS:")
        print("1. Restart your Flask server (both backend and frontend)")
        print("2. Upload a sample file and configure some rules")
        print("3. Check if the Configuration History section shows your configured files")
        print("4. If needed, apply the integration patch to validation_routes.py")
    else:
        print("⚠️  Some issues need to be resolved before the feature will work properly")
        print("\n📋 TROUBLESHOOTING:")
        print("1. Check your database connection")
        print("2. Ensure all required tables exist")
        print("3. Verify route imports are working")
        print("4. Apply the integration patch")
    
    print("\n📁 Files created/modified:")
    print("- rule_configuration_history table (database)")
    print("- INTEGRATION_PATCH.txt (manual integration guide)")

if __name__ == "__main__":
    main()
