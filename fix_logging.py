"""
Quick fix for Windows Unicode logging errors
Run this to replace emojis with text symbols
"""

import os
import re

def fix_file(filepath):
    """Remove emojis that cause Windows console errors"""
    if not os.path.exists(filepath):
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace problematic emojis with simple text
    replacements = {
        '✅': '[SUCCESS]',
        '⚡': '[FAST]',
        '🚀': '[START]',
        '📁': '[FILE]',
        '📊': '[DATA]',
        '💾': '[SAVE]',
        '🎯': '[TARGET]',
        '🗑️': '[DELETE]',
        '🎉': '[COMPLETE]',
        '🔥': '[HOT]'
    }
    
    for emoji, text in replacements.items():
        content = content.replace(emoji, text)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Fixed: {filepath}")

# Fix the main files causing logging errors
files = [
    'app_redis.py',
    'backend/services/redis_service.py',
    'backend/services/cached_fabric_service.py'
]

for file in files:
    fix_file(file)
print("Logging fix complete!")
