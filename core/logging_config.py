"""
Logging configuration for the application
"""

import os
import logging
import logging.handlers
from config.config import config

def setup_logging(app):
    """Configure application logging"""
    try:
        # Ensure log directory exists
        log_dir = os.path.dirname(config.LOG_FILE)
        os.makedirs(log_dir, exist_ok=True)
        
        # Set logging level
        log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        
        # Clear existing handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            config.LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        
        # Configure root logger
        logging.root.setLevel(log_level)
        logging.root.addHandler(file_handler)
        logging.root.addHandler(console_handler)
        
        # Configure Flask app logger
        app.logger.setLevel(log_level)
        app.logger.addHandler(file_handler)
        app.logger.addHandler(console_handler)
        
        # Suppress some verbose loggers in production
        if not config.DEBUG:
            logging.getLogger('werkzeug').setLevel(logging.WARNING)
            logging.getLogger('urllib3').setLevel(logging.WARNING)
        
        logging.info("Logging configured successfully")
        
    except Exception as e:
        print(f"Failed to setup logging: {e}")
        raise

def get_logger(name):
    """Get a logger instance"""
    return logging.getLogger(name)
