"""
Fix foreign key constraint issue in rule configuration
This script will fix the rule type ID mapping issue
"""

import os
import sys
import logging

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.services.fabric_service import FabricSQLService

def fix_rule_mapping_issue():
    """Fix the foreign key constraint issue by ensuring proper rule type mapping"""
    
    try:
        # Initialize the service
        fabric_service = FabricSQLService()
        
        print("🔧 Fixing foreign key constraint issue...")
        
        # First, let's check what's in the validation_rule_types table
        query_rules = "SELECT rule_type_id, rule_type_name FROM validation_rule_types ORDER BY rule_type_id"
        existing_rules = fabric_service.execute_query(query_rules)
        
        print("\n📋 Current validation rule types:")
        for rule in existing_rules:
            print(f"   ID: {rule[0]}, Name: {rule[1]}")
        
        # Check if we have the expected rules
        expected_rules = [
            (1, 'Required'),
            (2, 'Int'), 
            (3, 'Float'),
            (4, 'Text'),
            (5, 'Email'),
            (6, 'Date'),
            (7, 'Boolean'),
            (8, 'Alphanumeric')
        ]
        
        existing_ids = {rule[0] for rule in existing_rules}
        existing_names = {rule[1] for rule in existing_rules}
        
        print(f"\n🔍 Found {len(existing_rules)} existing rules")
        
        # Insert missing rules
        missing_rules = []
        for rule_id, rule_name in expected_rules:
            if rule_id not in existing_ids or rule_name not in existing_names:
                missing_rules.append((rule_id, rule_name))
        
        if missing_rules:
            print(f"➕ Adding {len(missing_rules)} missing rule types...")
            for rule_id, rule_name in missing_rules:
                try:
                    insert_query = """
                    INSERT INTO validation_rule_types (rule_type_id, rule_type_name, description, created_at)
                    VALUES (?, ?, ?, GETDATE())
                    """
                    fabric_service.execute_non_query(insert_query, (rule_id, rule_name, f"{rule_name} validation rule"))
                    print(f"   ✓ Added: {rule_name} (ID: {rule_id})")
                except Exception as e:
                    if "duplicate" in str(e).lower() or "primary key" in str(e).lower():
                        print(f"   - {rule_name} already exists (ID: {rule_id})")
                    else:
                        print(f"   ❌ Failed to add {rule_name}: {e}")
        else:
            print("✓ All required rule types are present")
        
        # Now check column_validations table structure
        print("\n🔍 Checking column_validations table structure...")
        try:
            # Check if there are any problematic records
            check_query = """
            SELECT cv.template_id, cv.column_name, cv.rule_type_id, vrt.rule_type_name
            FROM column_validations cv
            LEFT JOIN validation_rule_types vrt ON cv.rule_type_id = vrt.rule_type_id
            WHERE vrt.rule_type_id IS NULL
            """
            
            orphaned_records = fabric_service.execute_query(check_query)
            
            if orphaned_records:
                print(f"❌ Found {len(orphaned_records)} orphaned validation records")
                for record in orphaned_records:
                    print(f"   Template {record[0]}, Column: {record[1]}, Missing Rule ID: {record[2]}")
                
                # Clean up orphaned records
                print("🧹 Cleaning up orphaned records...")
                cleanup_query = """
                DELETE FROM column_validations 
                WHERE rule_type_id NOT IN (SELECT rule_type_id FROM validation_rule_types)
                """
                result = fabric_service.execute_non_query(cleanup_query)
                print(f"   ✓ Cleaned up {result} orphaned records")
            else:
                print("✓ No orphaned validation records found")
                
        except Exception as e:
            print(f"⚠️ Could not check column_validations: {e}")
        
        print("\n✅ Foreign key constraint fix completed!")
        print("🔄 Please restart your Flask server and try the rule configuration again.")
        
        return True
        
    except Exception as e:
        print(f"❌ Fix failed: {e}")
        return False

if __name__ == "__main__":
    fix_rule_mapping_issue()
