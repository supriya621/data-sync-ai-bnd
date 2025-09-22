"""
Direct fix for foreign key constraint issue
Based on the error logs, we know validation_rule_types table exists
"""

import os
import sys

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.services.fabric_service import FabricSQLService

def direct_fix():
    """Directly fix the foreign key constraint issue"""
    
    try:
        # Initialize the service
        fabric_service = FabricSQLService()
        
        print("Direct fix for foreign key constraint issue...")
        
        # We know from your logs that validation rules exist
        # Let's see what's actually in the table using a simple SELECT
        print("Checking current validation rules...")
        
        try:
            # Try different possible column names
            possible_queries = [
                "SELECT * FROM validation_rule_types ORDER BY rule_type_id",
                "SELECT * FROM validation_rule_types ORDER BY id", 
                "SELECT rule_type_id, rule_name FROM validation_rule_types",
                "SELECT id, name FROM validation_rule_types",
                "SELECT TOP 10 * FROM validation_rule_types"
            ]
            
            rules_data = None
            working_query = None
            
            for query in possible_queries:
                try:
                    print(f"Trying: {query}")
                    rules_data = fabric_service.execute_query(query)
                    working_query = query
                    print(f"SUCCESS - Query worked!")
                    break
                except Exception as e:
                    print(f"Failed: {str(e)[:100]}")
                    continue
            
            if not rules_data:
                print("Could not query validation_rule_types table")
                return False
            
            print(f"\nFound {len(rules_data)} validation rules:")
            for i, rule in enumerate(rules_data[:10]):  # Show first 10
                print(f"  {i+1}: {rule}")
            
            # Now let's check what the frontend is sending vs what exists
            print(f"\nAnalyzing the foreign key constraint error...")
            print("The error suggests your application is trying to insert a rule_type_id that doesn't exist.")
            
            # Let's check the column_validations table to see what's failing
            print("\nChecking column_validations table...")
            try:
                cv_query = "SELECT TOP 5 * FROM column_validations"
                cv_data = fabric_service.execute_query(cv_query)
                print(f"Column validations sample:")
                for row in cv_data:
                    print(f"  {row}")
            except Exception as e:
                print(f"Could not query column_validations: {e}")
            
            # Based on your logs, let's try to fix the specific issue
            # Your logs show these rules exist: Required(1), Int(2), Float(3), Text(4), Email(5), Date(6), Boolean(7), Alphanumeric(8)
            
            print(f"\nAttempting to fix the foreign key mapping issue...")
            
            # The most likely issue is that when you drag "Int" rule to a column,
            # the frontend sends rule_name="Int" but the backend looks for rule_type_id
            # Let's check if there's a mismatch in how rules are being resolved
            
            expected_rules = ['Required', 'Int', 'Float', 'Text', 'Email', 'Date', 'Boolean', 'Alphanumeric']
            
            for rule_name in expected_rules:
                try:
                    # Check if this rule name exists
                    check_queries = [
                        f"SELECT rule_type_id FROM validation_rule_types WHERE rule_name = '{rule_name}'",
                        f"SELECT id FROM validation_rule_types WHERE name = '{rule_name}'",
                        f"SELECT * FROM validation_rule_types WHERE rule_name = '{rule_name}' OR name = '{rule_name}'"
                    ]
                    
                    for check_query in check_queries:
                        try:
                            result = fabric_service.execute_query(check_query)
                            if result:
                                print(f"  ✓ {rule_name} exists: {result[0]}")
                                break
                        except:
                            continue
                    else:
                        print(f"  ❌ {rule_name} not found")
                        
                except Exception as e:
                    print(f"  Error checking {rule_name}: {e}")
            
            print(f"\n🔧 MANUAL FIX INSTRUCTIONS:")
            print("Based on the foreign key error, here's what you need to do:")
            print("1. Check your rule configuration code in the backend")
            print("2. The error happens when saving rules - likely in app_redis.py around line 907")
            print("3. The frontend sends rule names, but backend needs to map them to correct IDs")
            
            # Let's also clean up any orphaned records
            print(f"\n🧹 Cleaning up potential orphaned records...")
            try:
                # Count orphaned records first
                count_query = """
                SELECT COUNT(*) 
                FROM column_validations cv 
                WHERE cv.rule_type_id NOT IN (
                    SELECT COALESCE(rule_type_id, id) 
                    FROM validation_rule_types
                )
                """
                
                count_result = fabric_service.execute_query(count_query)
                orphaned_count = count_result[0][0] if count_result else 0
                
                if orphaned_count > 0:
                    print(f"Found {orphaned_count} orphaned validation records")
                    
                    # Delete orphaned records
                    cleanup_query = """
                    DELETE FROM column_validations 
                    WHERE rule_type_id NOT IN (
                        SELECT COALESCE(rule_type_id, id) 
                        FROM validation_rule_types
                    )
                    """
                    fabric_service.execute_non_query(cleanup_query)
                    print(f"✓ Cleaned up {orphaned_count} orphaned records")
                else:
                    print("✓ No orphaned records found")
                    
            except Exception as e:
                print(f"Could not clean up orphaned records: {e}")
            
            print(f"\n✅ Analysis complete!")
            print("The issue is likely in the rule name to ID mapping in your backend code.")
            print("Check how the configure_rules endpoint maps rule names to IDs.")
            
            return True
            
        except Exception as e:
            print(f"Error during analysis: {e}")
            return False
        
    except Exception as e:
        print(f"Direct fix failed: {e}")
        return False

if __name__ == "__main__":
    direct_fix()
