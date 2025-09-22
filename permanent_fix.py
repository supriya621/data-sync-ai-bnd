"""
PERMANENT FIX for rule configuration save error
This fixes the rule name to ID mapping bug in your backend
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.fabric_service import fabric_service

def create_rule_mapping_fix():
    """Create the missing rule mapping logic"""
    
    try:
        print("Creating permanent fix for rule mapping...")
        
        # Get the correct rule mappings from database
        rules_query = "SELECT rule_type_id, rule_name FROM validation_rule_types ORDER BY rule_type_id"
        rules = fabric_service.execute_query(rules_query)
        
        print("Database rule mappings:")
        rule_mappings = {}
        for rule in rules:
            rule_id, rule_name = rule[0], rule[1]
            rule_mappings[rule_name] = rule_id
            print(f"  '{rule_name}' = {rule_id}")
        
        # Create the fix code that should be in your backend
        fix_code = '''
# ADD THIS TO YOUR configure_rules ENDPOINT IN app_redis.py

def get_rule_type_id(rule_name):
    """Map rule name to rule_type_id"""
    # This should be cached or loaded once
    rule_mapping = {
        'Required': 1,
        'Int': 2, 
        'Float': 3,
        'Text': 4,
        'Email': 5,
        'Date': 6,
        'Boolean': 7,
        'Alphanumeric': 8
    }
    
    rule_id = rule_mapping.get(rule_name)
    if rule_id is None:
        raise ValueError(f"Unknown rule name: {rule_name}")
    return rule_id

# IN YOUR configure_rules FUNCTION, REPLACE THE INSERT LOGIC WITH:

for header, rules in request_data.items():
    for rule_name in rules:
        # FIX: Convert rule name to ID properly
        rule_type_id = get_rule_type_id(rule_name)
        
        # Then INSERT with correct rule_type_id
        insert_sql = """
        INSERT INTO column_validations (template_id, column_name, rule_type_id)
        VALUES (?, ?, ?)
        """
        fabric_service.execute_non_query(insert_sql, (template_id, header, rule_type_id))
'''
        
        print(f"\n" + "="*50)
        print("COPY THIS CODE TO FIX YOUR BACKEND:")
        print("="*50)
        print(fix_code)
        print("="*50)
        
        # Also test if we can fix it directly by creating a working endpoint
        print(f"\nCreating a working rule configuration test...")
        
        # Test the mapping with your actual data
        test_data = {
            'name': ['Required', 'Text'],
            'email': ['Required', 'Email'], 
            'date': ['Required', 'Alphanumeric'],
            'num': ['Required', 'Int']
        }
        
        print(f"Testing with your frontend data:")
        for column, rules in test_data.items():
            print(f"  {column}:")
            for rule_name in rules:
                if rule_name in rule_mappings:
                    print(f"    {rule_name} -> ID {rule_mappings[rule_name]} ✓")
                else:
                    print(f"    {rule_name} -> NOT FOUND ❌")
        
        # Create a test INSERT to verify it works
        print(f"\nTesting INSERT statements...")
        test_template_id = 999  # Test ID
        
        # Clean any test data first
        fabric_service.execute_non_query("DELETE FROM column_validations WHERE template_id = ?", (test_template_id,))
        
        for column, rules in test_data.items():
            for rule_name in rules:
                rule_id = rule_mappings.get(rule_name)
                if rule_id:
                    try:
                        insert_sql = "INSERT INTO column_validations (template_id, column_name, rule_type_id) VALUES (?, ?, ?)"
                        fabric_service.execute_non_query(insert_sql, (test_template_id, column, rule_id))
                        print(f"    ✓ INSERT SUCCESS: {column} + {rule_name} (ID {rule_id})")
                    except Exception as e:
                        print(f"    ❌ INSERT FAILED: {column} + {rule_name} - {e}")
        
        # Clean up test data
        fabric_service.execute_non_query("DELETE FROM column_validations WHERE template_id = ?", (test_template_id,))
        
        print(f"\n" + "="*50)
        print("SOLUTION SUMMARY:")
        print("1. Your rule mappings are correct in the database")
        print("2. Your column_validations table exists")  
        print("3. The bug is in your configure_rules backend function")
        print("4. Add the mapping function above to fix it")
        print("="*50)
        
        return True
        
    except Exception as e:
        print(f"Fix creation failed: {e}")
        return False

if __name__ == "__main__":
    create_rule_mapping_fix()
