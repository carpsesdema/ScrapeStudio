# utils/logger.py
import logging
import sys
import os

# Sensible defaults in case config isn't available
DEFAULT_LOGGER_NAME = "scrape_studio_fallback"
LOG_FILE_PATH = "logs/app.log"
LOG_LEVEL_CONSOLE = "INFO"
LOG_LEVEL_FILE = "DEBUG"

def setup_logger(name=None, log_file=None, console_level_str=None, file_level_str=None):
    """Sets up a standardized logger for the application."""
    try:
        from config import DEFAULT_LOGGER_NAME as cfg_name, LOG_FILE_PATH as cfg_log, \
                           LOG_LEVEL_CONSOLE as cfg_con, LOG_LEVEL_FILE as cfg_file
    except ImportError:
        cfg_name, cfg_log, cfg_con, cfg_file = DEFAULT_LOGGER_NAME, LOG_FILE_PATH, LOG_LEVEL_CONSOLE, LOG_LEVEL_FILE

    logger_name = name or cfg_name
    logger = logging.getLogger(logger_name)

    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)  # Set the lowest level on the logger itself

    log_dir = os.path.dirname(cfg_log)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    )

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(getattr(logging, (console_level_str or cfg_con).upper(), logging.INFO))
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Handler
    try:
        fh = logging.FileHandler(log_file or cfg_log, encoding='utf-8')
        fh.setLevel(getattr(logging, (file_level_str or cfg_file).upper(), logging.DEBUG))
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        logger.error(f"Failed to set up file logger at {log_file or cfg_log}: {e}", exc_info=False)

    return logger