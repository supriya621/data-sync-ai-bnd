"""
Logging configuration fix for Windows Unicode issues
Import this at the top of your app_redis.py to fix emoji logging issues
"""

import os
import sys
import codecs
import logging

def fix_windows_logging():
    """Fix Windows console encoding issues for emojis in logs"""
    if os.name == 'nt':  # Windows only
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleCP(65001)
            kernel32.SetConsoleOutputCP(65001)
            
            # Override stdout/stderr with UTF-8 writers
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)
            
            # Update logging handlers to use new stdout
            root_logger = logging.getLogger()
            for handler in root_logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setStream(sys.stdout)
                    
            return True
        except Exception as e:
            print(f"Warning: Could not fix Windows encoding: {e}")
            return False
    return True

# Call the fix when this module is imported
fix_windows_logging()
