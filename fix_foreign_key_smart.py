"""
Fix foreign key constraint issue - Database Discovery Version
This script will first discover your actual table structure, then fix the issue
"""

import os
import sys
import logging

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.services.fabric_service import FabricSQLService

def discover_and_fix():
    """Discover actual table structure and fix foreign key constraint issue"""
    
    try:
        # Initialize the service
        fabric_service = FabricSQLService()
        
        print("🔍 Discovering your database table structure...")
        
        # First, discover the actual column names in validation_rule_types
        print("\n📋 Checking validation_rule_types table structure...")
        try:
            # Get table schema
            schema_query = """
            SELECT COLUMN_NAME, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'validation_rule_types'
            ORDER BY ORDINAL_POSITION
            """
            columns = fabric_service.execute_query(schema_query)
            
            print("   Columns found:")
            column_names = []
            for col in columns:
                print(f"   - {col[0]} ({col[1]})")
                column_names.append(col[0])
            
            # Determine the correct column names
            id_column = None
            name_column = None
            
            # Look for ID column
            for col in column_names:
                if 'id' in col.lower() and ('rule' in col.lower() or 'type' in col.lower()):
                    id_column = col
                    break
            
            # Look for name column
            for col in column_names:
                if 'name' in col.lower():
                    name_column = col
                    break
                elif 'rule_name' in col.lower():
                    name_column = col
                    break
            
            if not id_column or not name_column:
                print(f"❌ Could not determine column names. Found: {column_names}")
                print("   Please check your validation_rule_types table structure")
                return False
            
            print(f"   Using ID column: {id_column}")
            print(f"   Using Name column: {name_column}")
            
            # Now check what's in the table
            query_rules = f"SELECT {id_column}, {name_column} FROM validation_rule_types ORDER BY {id_column}"
            existing_rules = fabric_service.execute_query(query_rules)
            
            print(f"\n📋 Current validation rule types:")
            for rule in existing_rules:
                print(f"   ID: {rule[0]}, Name: {rule[1]}")
            
            # Check what your frontend is expecting by looking at recent errors
            print(f"\n🔍 Found {len(existing_rules)} existing rules")
            
            # Map rule names to the IDs your application expects
            rule_name_to_id = {
                'Required': 1,
                'Int': 2,
                'Float': 3, 
                'Text': 4,
                'Email': 5,
                'Date': 6,
                'Boolean': 7,
                'Alphanumeric': 8
            }
            
            existing_names = {rule[1]: rule[0] for rule in existing_rules}
            print(f"\nExisting rule mapping: {existing_names}")
            
            # Check for missing or mismatched rules
            issues_found = []
            for expected_name, expected_id in rule_name_to_id.items():
                if expected_name not in existing_names:
                    issues_found.append(f"Missing rule: {expected_name} (should be ID {expected_id})")
                elif existing_names[expected_name] != expected_id:
                    issues_found.append(f"Wrong ID for {expected_name}: has {existing_names[expected_name]}, should be {expected_id}")
            
            if issues_found:
                print(f"\n❌ Found {len(issues_found)} issues:")
                for issue in issues_found:
                    print(f"   - {issue}")
                
                print(f"\n🔧 Attempting to fix...")
                
                # For each expected rule, ensure it exists with correct ID
                for expected_name, expected_id in rule_name_to_id.items():
                    try:
                        if expected_name not in existing_names:
                            # Insert missing rule
                            insert_cols = [id_column, name_column]
                            if 'description' in column_names:
                                insert_cols.append('description')
                            if 'created_at' in column_names:
                                insert_cols.append('created_at')
                            
                            values_placeholder = ', '.join(['?'] * len(insert_cols))
                            insert_query = f"INSERT INTO validation_rule_types ({', '.join(insert_cols)}) VALUES ({values_placeholder})"
                            
                            values = [expected_id, expected_name]
                            if 'description' in insert_cols:
                                values.append(f"{expected_name} validation rule")
                            if 'created_at' in insert_cols:
                                values.append(None)  # Let it use GETDATE() default
                            
                            fabric_service.execute_non_query(insert_query, values)
                            print(f"   ✓ Added: {expected_name} (ID: {expected_id})")
                            
                        elif existing_names[expected_name] != expected_id:
                            # Update existing rule to have correct ID
                            print(f"   ⚠️  {expected_name} has wrong ID. This requires manual fix.")
                            print(f"      Current: ID {existing_names[expected_name]}")
                            print(f"      Expected: ID {expected_id}")
                            
                    except Exception as e:
                        if "duplicate" in str(e).lower() or "primary key" in str(e).lower():
                            print(f"   - {expected_name} already exists")
                        else:
                            print(f"   ❌ Failed to fix {expected_name}: {e}")
                
            else:
                print("✓ All required rule types are present with correct IDs")
            
            # Now check and clean up column_validations
            print(f"\n🔍 Checking column_validations table...")
            try:
                check_query = f"""
                SELECT COUNT(*) as orphaned_count
                FROM column_validations cv
                LEFT JOIN validation_rule_types vrt ON cv.rule_type_id = vrt.{id_column}
                WHERE vrt.{id_column} IS NULL
                """
                
                result = fabric_service.execute_query(check_query)
                orphaned_count = result[0][0] if result else 0
                
                if orphaned_count > 0:
                    print(f"❌ Found {orphaned_count} orphaned validation records")
                    
                    # Clean them up
                    cleanup_query = f"""
                    DELETE FROM column_validations 
                    WHERE rule_type_id NOT IN (SELECT {id_column} FROM validation_rule_types)
                    """
                    fabric_service.execute_non_query(cleanup_query)
                    print(f"   ✓ Cleaned up orphaned records")
                else:
                    print("✓ No orphaned validation records found")
                    
            except Exception as e:
                print(f"⚠️ Could not check column_validations: {e}")
            
            print(f"\n✅ Database structure analysis and fixes completed!")
            print(f"🔄 Please restart your Flask server and try the rule configuration again.")
            
            return True
            
        except Exception as e:
            print(f"❌ Could not discover table structure: {e}")
            return False
        
    except Exception as e:
        print(f"❌ Fix failed: {e}")
        return False

if __name__ == "__main__":
    discover_and_fix()
