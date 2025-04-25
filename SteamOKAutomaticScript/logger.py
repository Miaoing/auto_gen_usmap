import logging
import os
from datetime import datetime
from colorama import init, Fore, Style

# Initialize colorama for Windows
init()

class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels"""
    
    def format(self, record):
        # Add colors based on log level
        if record.levelno == logging.DEBUG:
            color = Fore.CYAN
        elif record.levelno == logging.INFO:
            color = Fore.GREEN
        elif record.levelno == logging.WARNING:
            color = Fore.YELLOW
        elif record.levelno == logging.ERROR:
            color = Fore.RED
        elif record.levelno == logging.CRITICAL:
            color = Fore.RED + Style.BRIGHT
        else:
            color = Fore.WHITE

        # Format the message with color
        record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"
        return super().format(record)

def setup_logging():
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join("logs", f"steam_{timestamp}.log")
    
    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create formatters
    file_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = ColoredFormatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S"
    )

    # Create and configure handlers
    file_handler = logging.FileHandler(
        log_file,
        mode='a',
        encoding='utf-8'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)

    # Configure root logger
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Create and return logger
    logger = logging.getLogger()
    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger
