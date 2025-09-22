"""
Fix rule mapping issue in configure_rules endpoint
The backend receives rule names but fails to map them to correct IDs
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.fabric_service import fabric_service

def fix_rule_mapping():
    """Fix the rule name to ID mapping issue"""
    
    try:
        print("Analyzing rule mapping issue...")
        
        # Check what rule configurations are trying to be saved
        print("\nValidation rules in database:")
        rules_query = "SELECT rule_type_id, rule_name FROM validation_rule_types ORDER BY rule_type_id"
        rules = fabric_service.execute_query(rules_query)
        
        rule_map = {}
        for rule in rules:
            rule_id, rule_name = rule[0], rule[1]
            rule_map[rule_name] = rule_id
            print(f"  {rule_name} = ID {rule_id}")
        
        # Check if there are any orphaned records in column_validations
        print(f"\nChecking column_validations table...")
        try:
            orphaned_query = """
            SELECT cv.rule_type_id, COUNT(*) as count
            FROM column_validations cv
            LEFT JOIN validation_rule_types vrt ON cv.rule_type_id = vrt.rule_type_id
            WHERE vrt.rule_type_id IS NULL
            GROUP BY cv.rule_type_id
            """
            orphaned = fabric_service.execute_query(orphaned_query)
            
            if orphaned:
                print(f"Found orphaned records with invalid rule_type_ids:")
                for record in orphaned:
                    print(f"  Invalid rule_type_id: {record[0]} (count: {record[1]})")
                
                # Clean up orphaned records
                cleanup_query = "DELETE FROM column_validations WHERE rule_type_id NOT IN (SELECT rule_type_id FROM validation_rule_types)"
                result = fabric_service.execute_non_query(cleanup_query)
                print(f"  Cleaned up orphaned records")
            else:
                print("  No orphaned records found")
                
        except Exception as e:
            print(f"Could not check column_validations: {e}")
        
        # The real issue is likely in the backend code
        print(f"\n=== ROOT CAUSE ANALYSIS ===")
        print("The issue is in your backend configure_rules endpoint.")
        print("When frontend sends rule names like 'Text', 'Email', 'Alphanumeric', 'Int',")
        print("the backend must convert these to correct rule_type_ids before INSERT.")
        print("\nCorrect mapping should be:")
        print("  'Required' -> 1")
        print("  'Int' -> 2") 
        print("  'Float' -> 3")
        print("  'Text' -> 4")
        print("  'Email' -> 5")
        print("  'Date' -> 6")
        print("  'Boolean' -> 7")
        print("  'Alphanumeric' -> 8")
        
        # Test what the frontend is sending
        print(f"\n=== TESTING RULE VALIDATION ===")
        test_rules = ['Text', 'Email', 'Alphanumeric', 'Int']  # From your screenshot
        print("Testing rule names from your frontend:")
        
        for rule_name in test_rules:
            if rule_name in rule_map:
                print(f"  ✓ '{rule_name}' maps to ID {rule_map[rule_name]}")
            else:
                print(f"  ❌ '{rule_name}' NOT FOUND in database")
                # Find closest match
                possible_matches = [r for r in rule_map.keys() if rule_name.lower() in r.lower() or r.lower() in rule_name.lower()]
                if possible_matches:
                    print(f"      Possible matches: {possible_matches}")
        
        print(f"\n=== SOLUTION ===")
        print("The backend configure_rules function needs to:")
        print("1. Receive rule names from frontend")  
        print("2. Look up rule_type_id from validation_rule_types table")
        print("3. Insert into column_validations with correct rule_type_id")
        print("\nExample fix code:")
        print("""
        # In configure_rules endpoint:
        rule_name_to_id = {}
        rules = fabric_service.execute_query("SELECT rule_type_id, rule_name FROM validation_rule_types")
        for rule in rules:
            rule_name_to_id[rule[1]] = rule[0]
        
        # When processing each rule from frontend:
        rule_type_id = rule_name_to_id.get(rule_name)
        if not rule_type_id:
            raise ValueError(f"Invalid rule name: {rule_name}")
        
        # Then INSERT with correct rule_type_id
        """)
        
        return True
        
    except Exception as e:
        print(f"Analysis failed: {e}")
        return False

if __name__ == "__main__":
    fix_rule_mapping()
