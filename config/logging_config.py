"""
Alpha Sniper v4.1 Logging Configuration
Rotating file handlers with console output
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from config.config import config


def setup_logging() -> logging.Logger:
    """
    Setup rotating file logger with console output
    Returns: Configured logger instance
    """
    # Create logs directory
    os.makedirs(config.LOG_DIR, exist_ok=True)

    # Create logger
    logger = logging.getLogger('alpha_sniper')
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (rotating)
    if config.LOG_TO_FILE:
        log_file = os.path.join(config.LOG_DIR, 'alpha_sniper.log')
        max_bytes = config.MAX_LOG_SIZE_MB * 1024 * 1024
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=config.LOG_BACKUP_COUNT
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


# Global logger instance
logger = setup_logging()
