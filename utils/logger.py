import logging
import sys
from utils.config_loader import get_config

def setup_logger(name: str = None) -> logging.Logger:
    """Setup logger based on configuration"""
    config = get_config()
    log_level = config.get('system.log_level', 'INFO')
    
    # Convert string level to logging constant
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    logger = logging.getLogger(name or __name__)
    logger.setLevel(level)
    
    # Avoid adding handlers multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger