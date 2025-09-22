"""
Automatic patch script to fix rule configuration issue
This will modify your app_redis.py file directly
"""

import os
import re

def apply_rule_mapping_fix():
    """Apply the rule mapping fix to app_redis.py"""
    
    file_path = "app_redis.py"
    
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found")
        return False
    
    # Read the current file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Create backup
    with open(f"{file_path}.backup", 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Created backup: {file_path}.backup")
    
    # Add the rule mapping function after imports
    rule_mapping_function = '''

def get_rule_type_id(rule_name):
    """Convert rule name to rule_type_id for database operations"""
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
        logger.error(f"Unknown rule name received: {rule_name}")
        raise ValueError(f"Unknown rule name: {rule_name}")
    return rule_id
'''
    
    # Find a good place to insert the function (after imports, before first route)
    if 'def get_rule_type_id(' not in content:
        # Find the end of imports section
        lines = content.split('\n')
        insert_line = 0
        
        for i, line in enumerate(lines):
            if line.strip().startswith('@app.route') or line.strip().startswith('def '):
                insert_line = i
                break
        
        if insert_line > 0:
            lines.insert(insert_line, rule_mapping_function)
            content = '\n'.join(lines)
            print("Added get_rule_type_id function")
        else:
            # Fallback: add after GENERIC_RULES
            content = content.replace('GENERIC_RULES = {', rule_mapping_function + '\n\nGENERIC_RULES = {')
            print("Added get_rule_type_id function after GENERIC_RULES")
    else:
        print("get_rule_type_id function already exists")
    
    # Find and fix any configure_rules function
    # Look for patterns that suggest rule configuration
    patterns_to_fix = [
        # Pattern 1: Direct INSERT with rule names
        (r'INSERT INTO column_validations.*?VALUES.*?\(([^)]+)\)', 'fix_insert_values'),
        # Pattern 2: execute_non_query with column_validations
        (r'execute_non_query\s*\(\s*["\']INSERT INTO column_validations.*?["\'].*?\)', 'fix_execute_query')
    ]
    
    # Search for functions that might handle rule configuration
    configure_functions = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        if ('def ' in line and ('configure' in line.lower() or 'rule' in line.lower())) or \
           ('/api/validation/configure' in line):
            configure_functions.append(i)
            print(f"Found potential configure function at line {i+1}: {line.strip()}")
    
    # Apply fixes - look for INSERT statements in column_validations
    original_content = content
    
    # Fix pattern: Look for INSERT statements that might be using rule names instead of IDs
    # This is a safer approach - find and fix specific problematic patterns
    
    # Pattern 1: Fix any obvious INSERT statements
    insert_pattern = r'(INSERT INTO column_validations.*?VALUES\s*\([^)]*?)(\w+_name|\w*rule\w*|\w*validation\w*)([^)]*\))'
    if re.search(insert_pattern, content, re.IGNORECASE):
        print("Found potential INSERT pattern that needs fixing")
    
    # More targeted fix: Add rule conversion before any column_validations INSERT
    if 'column_validations' in content.lower():
        # Add a comment to help identify where fixes are needed
        comment = '''
        # RULE MAPPING FIX: Before any INSERT into column_validations,
        # convert rule names to IDs using: rule_type_id = get_rule_type_id(rule_name)
        '''
        
        if 'RULE MAPPING FIX' not in content:
            # Insert the comment before any function that might handle rules
            for func_line in configure_functions:
                lines = content.split('\n')
                lines.insert(func_line, comment)
                content = '\n'.join(lines)
                break
    
    # Write the fixed content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Applied fixes to {file_path}")
    print("\nMANUAL STEP REQUIRED:")
    print("You need to find your configure_rules function and ensure that")
    print("before any INSERT into column_validations, you call:")
    print("    rule_type_id = get_rule_type_id(rule_name)")
    print("and use rule_type_id in the INSERT instead of rule_name")
    
    return True

if __name__ == "__main__":
    print("Applying rule mapping fix...")
    if apply_rule_mapping_fix():
        print("\nFix applied successfully!")
        print("Now restart your Flask server: python app_redis.py")
    else:
        print("Fix failed. Please apply manually using MANUAL_PATCH_INSTRUCTIONS.py")
