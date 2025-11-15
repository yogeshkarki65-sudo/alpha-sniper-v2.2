"""
Unified logging configuration for Alpha Sniper V3.0

Provides consistent logging across all components with:
- Console output with colors
- Rotating file logs per component
- Configurable log level via environment variable
- Thread-safe and idempotent
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


# ANSI color codes for console output
class LogColors:
    GREY = '\033[90m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD_RED = '\033[1;91m'
    RESET = '\033[0m'


# Custom formatter with colors for console
class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors to console output"""

    COLORS = {
        logging.DEBUG: LogColors.GREY,
        logging.INFO: LogColors.GREEN,
        logging.WARNING: LogColors.YELLOW,
        logging.ERROR: LogColors.RED,
        logging.CRITICAL: LogColors.BOLD_RED,
    }

    def format(self, record):
        # Add color based on log level
        color = self.COLORS.get(record.levelno, LogColors.RESET)
        record.levelname = f"{color}{record.levelname}{LogColors.RESET}"
        record.name = f"{LogColors.BLUE}{record.name}{LogColors.RESET}"
        return super().format(record)


# Track configured loggers to avoid duplicate handlers
_configured_loggers = set()


def configure_logging(
    component_name: str,
    log_dir: str = "logs",
    log_level: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Configure and return a logger for a specific component.

    Args:
        component_name: Name of the component (e.g., 'scanner', 'trader')
        log_dir: Directory for log files
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                  If None, reads from LOG_LEVEL env var, defaults to INFO
        max_bytes: Maximum size of each log file before rotation
        backup_count: Number of backup files to keep

    Returns:
        Configured logger instance

    Example:
        >>> logger = configure_logging('scanner')
        >>> logger.info('Scanner started')
        >>> logger.debug('Processing symbol: BTCUSDT')
    """

    # Get logger
    logger = logging.getLogger(component_name)

    # If already configured, return it (idempotent)
    if component_name in _configured_loggers:
        return logger

    # Determine log level
    if log_level is None:
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

    numeric_level = getattr(logging, log_level, logging.INFO)
    logger.setLevel(numeric_level)

    # Create logs directory if it doesn't exist
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Format strings
    detailed_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_formatter = ColoredFormatter(detailed_format, datefmt=date_format)
    console_handler.setFormatter(console_formatter)

    # File handler with rotation (no colors in files)
    log_file = os.path.join(log_dir, f"{component_name}.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(numeric_level)
    file_formatter = logging.Formatter(detailed_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    # Mark as configured
    _configured_loggers.add(component_name)

    return logger


def get_logger(component_name: str) -> logging.Logger:
    """
    Get a logger for a component. If not configured, configures it first.

    Args:
        component_name: Name of the component

    Returns:
        Logger instance
    """
    if component_name not in _configured_loggers:
        return configure_logging(component_name)
    return logging.getLogger(component_name)


# Convenience function for quick setup
def setup_root_logging(level: str = 'INFO'):
    """
    Setup basic logging for the entire application.
    Call this once at startup in main.py

    Args:
        level: Log level for all components
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


if __name__ == "__main__":
    # Test the logging system
    test_logger = configure_logging('test', log_level='DEBUG')

    test_logger.debug('This is a debug message')
    test_logger.info('This is an info message')
    test_logger.warning('This is a warning message')
    test_logger.error('This is an error message')
    test_logger.critical('This is a critical message')

    print("\n✅ Logging system test complete!")
    print(f"✅ Log file created at: logs/test.log")
