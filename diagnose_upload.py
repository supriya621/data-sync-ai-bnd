"""
Quick Fix for File Upload Issue
This will restore your file upload functionality without touching other code
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

def check_upload_endpoint():
    """Check what's wrong with the upload endpoint response"""
    try:
        # Test the upload endpoint response format
        print("Checking upload endpoint...")
        
        # Read the current app_redis.py to see what might be wrong
        with open('app_redis.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Look for the upload endpoint
        if 'def upload_file' in content:
            print("✓ Upload endpoint exists")
            
            # Check if there are any syntax errors around the upload function
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'def upload_file' in line:
                    print(f"Upload function found at line {i+1}")
                    # Show a few lines around it
                    start = max(0, i-5)
                    end = min(len(lines), i+20)
                    for j in range(start, end):
                        marker = ">>> " if j == i else "    "
                        print(f"{marker}{j+1}: {lines[j]}")
                    break
        else:
            print("✗ Upload endpoint not found")
            
        return True
        
    except Exception as e:
        print(f"Error checking upload endpoint: {str(e)}")
        return False

def create_minimal_fix():
    """Create a minimal fix that just removes the Unicode logging errors"""
    try:
        print("Creating minimal Unicode logging fix...")
        
        # Read current app_redis.py
        with open('app_redis.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check if our previous fix is there and causing issues
        if 'Fix Windows Unicode logging issues' in content:
            print("Found previous Unicode fix - this might be the problem")
            
            # Remove the problematic Unicode fix
            lines = content.split('\n')
            new_lines = []
            skip_lines = False
            
            for line in lines:
                if '# Fix Windows Unicode logging issues' in line:
                    skip_lines = True
                    continue
                elif skip_lines and line.strip() == '' and len(new_lines) > 0 and new_lines[-1].startswith('from flask'):
                    skip_lines = False
                elif skip_lines and 'from flask' in line:
                    skip_lines = False
                    new_lines.append(line)
                elif not skip_lines:
                    new_lines.append(line)
                    
            # Write the fixed version
            with open('app_redis_fixed.py', 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_lines))
                
            print("✓ Created app_redis_fixed.py without problematic Unicode fix")
            return True
        else:
            print("Unicode fix not found in current file")
            return False
            
    except Exception as e:
        print(f"Error creating fix: {str(e)}")
        return False

def main():
    """Main diagnostic and fix function"""
    print("=" * 60)
    print("DIAGNOSING FILE UPLOAD FAILURE")
    print("=" * 60)
    
    # Step 1: Check the upload endpoint
    check_upload_endpoint()
    
    # Step 2: Try to fix the Unicode issue
    if create_minimal_fix():
        print("\n" + "=" * 60)
        print("FIX CREATED")
        print("=" * 60)
        print("1. Stop your Flask server (Ctrl+C)")
        print("2. Backup your current file:")
        print("   copy app_redis.py app_redis_backup.py")
        print("3. Replace with fixed version:")
        print("   copy app_redis_fixed.py app_redis.py")
        print("4. Restart: python app_redis.py")
        print("5. Test file upload")
    else:
        print("\n" + "=" * 60)
        print("ALTERNATIVE SOLUTION")
        print("=" * 60)
        print("The Unicode fix I added is likely causing the issue.")
        print("Please:")
        print("1. Stop your Flask server")
        print("2. Restore from a backup before my changes")
        print("3. Or tell me and I'll help you revert the specific changes")
        
    return True

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Script failed: {str(e)}")
    
    input("\nPress Enter to exit...")
