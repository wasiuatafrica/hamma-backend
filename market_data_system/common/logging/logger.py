import logging
import sys
from pathlib import Path
from datetime import datetime
import os

from common.utils.config import settings

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Set up logging format
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"

# Get the current date for the log file name
current_date = datetime.now().strftime("%Y-%m-%d")
log_file = logs_dir / f"{current_date}.log"

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format=log_format,
    datefmt=date_format,
    handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
)


def get_logger(name):
    """Get a logger with the specified name."""
    return logging.getLogger(name)
