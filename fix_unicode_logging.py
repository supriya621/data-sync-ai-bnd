"""
Fix Unicode logging issues on Windows
Replace emojis with simple text symbols
"""

import os
import re

def fix_unicode_in_file(filepath):
    """Replace Unicode emojis with simple text symbols"""
    
    if not os.path.exists(filepath):
        return False
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace common emojis with text symbols
    replacements = {
        '✅': '[OK]',
        '❌': '[ERROR]', 
        '⚠️': '[WARNING]',
        '🚀': '[STARTING]',
        '⚡': '[PERFORMANCE]'
    }
    
    modified = False
    for emoji, replacement in replacements.items():
        if emoji in content:
            content = content.replace(emoji, replacement)
            modified = True
    
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed Unicode in {filepath}")
        return True
    
    return False

if __name__ == "__main__":
    files_to_fix = [
        'app_redis.py',
        'backend/services/cached_fabric_service.py',
        'backend/services/redis_service.py'
    ]
    
    for file in files_to_fix:
        if fix_unicode_in_file(file):
            print(f"✓ Fixed {file}")
        else:
            print(f"- No changes needed in {file}")
