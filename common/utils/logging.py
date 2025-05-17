import logging
import sys

from common.utils.config import config


def setup_logging(name: str) -> logging.Logger:
    """Set up logging for the application."""
    # Use dictionary access for config
    log_config = config["logging"]
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_config["level"]))
    
    # Avoid duplicate handlers
    if not logger.handlers:
        # Create console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, log_config["level"]))
        
        # Create formatter
        formatter = logging.Formatter(log_config["format"])
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)
    
    return logger
