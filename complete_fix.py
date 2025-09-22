"""
Complete the rule mapping fix in configure_rules function
This script will find and fix the specific INSERT statements that are causing the error
"""

import os
import re

def complete_rule_fix():
    """Complete the fix in configure_rules function"""
    
    file_path = "app_redis.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the configure_rules function and fix it
    lines = content.split('\n')
    
    # Find the start of configure_rules function
    configure_start = -1
    for i, line in enumerate(lines):
        if 'def configure_rules(' in line:
            configure_start = i
            print(f"Found configure_rules function at line {i+1}")
            break
    
    if configure_start == -1:
        print("Could not find configure_rules function")
        return False
    
    # Find the end of the function (next function or end of file)
    configure_end = len(lines)
    for i in range(configure_start + 1, len(lines)):
        if lines[i].strip().startswith('def ') or lines[i].strip().startswith('@app.route'):
            configure_end = i
            break
    
    print(f"Function spans lines {configure_start+1} to {configure_end}")
    
    # Extract and fix the function
    function_lines = lines[configure_start:configure_end]
    
    # Look for INSERT statements in this function and fix them
    fixed_function = []
    i = 0
    while i < len(function_lines):
        line = function_lines[i]
        
        # Check if this line contains an INSERT into column_validations
        if 'column_validations' in line.lower() and 'insert' in line.lower():
            print(f"Found INSERT statement at line {configure_start + i + 1}: {line.strip()}")
            
            # Look for the pattern where rule names are being inserted directly
            # Common patterns:
            # 1. execute_non_query with rule_name variable
            # 2. Direct INSERT with string interpolation
            
            # Add rule conversion before the INSERT
            indent = len(line) - len(line.lstrip())
            conversion_code = [
                " " * indent + "# Convert rule name to ID",
                " " * indent + "rule_type_id = get_rule_type_id(rule_name)"
            ]
            
            # Check if conversion is already present
            conversion_present = False
            for j in range(max(0, i-5), i):
                if 'get_rule_type_id' in function_lines[j]:
                    conversion_present = True
                    break
            
            if not conversion_present:
                # Insert conversion code before the INSERT
                fixed_function.extend(conversion_code)
                print(f"Added rule conversion before INSERT")
            
            # Fix the INSERT statement to use rule_type_id instead of rule_name
            fixed_line = line
            
            # Pattern 1: Replace rule_name with rule_type_id in the VALUES
            if 'rule_name' in line:
                fixed_line = line.replace('rule_name', 'rule_type_id')
                print(f"Replaced rule_name with rule_type_id in INSERT")
            
            # Pattern 2: Look for other patterns that might be using rule names directly
            patterns = [
                (r'(.*?)(rule\w*)(.*?)', r'\1rule_type_id\3'),
                (r'(.*?)(\w+_name)(.*?)', r'\1rule_type_id\3')
            ]
            
            for pattern, replacement in patterns:
                if re.search(pattern, fixed_line, re.IGNORECASE):
                    old_line = fixed_line
                    fixed_line = re.sub(pattern, replacement, fixed_line, flags=re.IGNORECASE)
                    if fixed_line != old_line:
                        print(f"Applied pattern fix to INSERT statement")
            
            fixed_function.append(fixed_line)
            
        else:
            # Check if this line processes rule names from request data
            if any(word in line.lower() for word in ['rule_name', 'rules', 'validation']) and '=' in line:
                # This might be where rule names are extracted from the request
                print(f"Found rule processing at line {configure_start + i + 1}: {line.strip()}")
                
                # Look ahead for the INSERT statement
                for j in range(i+1, min(i+10, len(function_lines))):
                    if 'column_validations' in function_lines[j].lower():
                        # Add rule conversion here if not already present
                        indent = len(line) - len(line.lstrip())
                        if not any('get_rule_type_id' in function_lines[k] for k in range(i, j)):
                            fixed_function.append(line)
                            fixed_function.append(" " * (indent + 4) + "rule_type_id = get_rule_type_id(rule_name)")
                            print(f"Added rule conversion after rule extraction")
                            i += 1
                            continue
            
            fixed_function.append(line)
        
        i += 1
    
    # Replace the function in the original content
    fixed_lines = lines[:configure_start] + fixed_function + lines[configure_end:]
    fixed_content = '\n'.join(fixed_lines)
    
    # Write the fixed file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print("Fix applied to configure_rules function")
    
    # Show the fixed function for verification
    print("\nFixed function preview:")
    for i, line in enumerate(fixed_function[:20]):  # Show first 20 lines
        print(f"{configure_start + i + 1:4}: {line}")
    
    return True

if __name__ == "__main__":
    print("Completing rule mapping fix in configure_rules function...")
    if complete_rule_fix():
        print("\nFix completed successfully!")
        print("Restart your Flask server: python app_redis.py")
        print("Then test rule configuration at localhost:5173/rule-configuration")
    else:
        print("Fix failed.")
