# config.py
"""
Main Configuration File for Scrape Studio
"""
import os

# --- Application Info ---
APP_NAME = "ScrapeStudio"
VERSION = "1.0.0"

# --- Logging ---
DEFAULT_LOGGER_NAME = "scrapestudio_logger"
LOG_FILE_PATH = "logs/app.log"
LOG_LEVEL_CONSOLE = "INFO"
LOG_LEVEL_FILE = "DEBUG"

# --- HTTP Fetching ---
USER_AGENT = f"{APP_NAME}/{VERSION} (github.com/your-repo/ScrapeStudio)"
DEFAULT_REQUEST_TIMEOUT = 20  # seconds
MAX_CONCURRENT_FETCHERS = 5 # Number of parallel downloads

# --- Rate Limiting ---
DEFAULT_DELAY_BETWEEN_REQUESTS = 2.0  # seconds
RESPECT_ROBOTS_TXT = True

# --- Export Settings ---
DEFAULT_EXPORT_DIR = "./data_exports"
# Create export directory if it doesn't exist
os.makedirs(DEFAULT_EXPORT_DIR, exist_ok=True)