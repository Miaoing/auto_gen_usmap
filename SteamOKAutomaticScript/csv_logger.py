import os
import csv
import logging
import datetime
import requests
from pathlib import Path

logger = logging.getLogger()

class GameStatusLogger:
    """
    A class to log game processing status information to CSV files.
    
    This logger tracks:
    - Game name
    - Status (DOWNLOAD_ERROR, DOWNLOAD_SUCCESS, INJECTION_CRASH, INJECTION_SUCCESS, INJECTION_TIMEOUT)
    - USMap path (if successful)
    - Injection log directory (if applicable)
    - Timestamp
    - Error details (if any)
    """
    
    def __init__(self, webhook_url=None):
        """
        Initialize the GameStatusLogger.
        
        Args:
            webhook_url (str, optional): URL for webhook notifications. If None, no notifications will be sent.
        """
        # Set up CSV path with timestamp if none provided
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.result_dir = Path("result")
        self.result_dir.mkdir(exist_ok=True)
        self.csv_path = self.result_dir / f"game_status_{timestamp}.csv"
        self.webhook_url = webhook_url
        
        # Set up CSV headers
        self.headers = [
            "GameName", 
            "Status", 
            "Timestamp", 
            "USMapPath",
            "InjectionLogDir", 
            "ErrorDetails"
        ]
        
        # Initialize CSV file if it doesn't exist
        self.initialize_csv()
        
        logger.info(f"GameStatusLogger initialized with CSV path: {self.csv_path}")
        if self.webhook_url:
            logger.info(f"Webhook notifications enabled")
    
    def initialize_csv(self):
        """Initialize the CSV file with headers if it doesn't exist."""
        if not self.csv_path.exists():
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(self.headers)
            logger.info(f"Created new CSV log file at {self.csv_path}")
    
    def send_webhook_notification(self, message):
        """
        Send a notification to the webhook URL if it is configured.
        
        Args:
            message (str): The message to send
        """
        if not self.webhook_url:
            return
            
        headers = {
            'Content-Type': 'application/json'
        }
        
        payload = {
            'msgtype': 'text',
            'text': {
                'content': message
            }
        }
        
        try:
            response = requests.post(self.webhook_url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(f"Webhook notification sent successfully! Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending webhook notification: {e}")
    
    def log_game_status(self, game_name, status, usmap_path=None, injection_log_dir=None, error_details=None):
        """
        Log the game status to the CSV file.
        
        Args:
            game_name (str): Name of the game
            status (str): Status of the game process (DOWNLOAD_ERROR, DOWNLOAD_SUCCESS, 
                         INJECTION_CRASH, INJECTION_SUCCESS, INJECTION_TIMEOUT)
            usmap_path (str, optional): Path to the USMap file if injection was successful
            injection_log_dir (str, optional): Path to the injection log directory
            error_details (str, optional): Error details if an error occurred
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(self.csv_path, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                game_name,
                status,
                timestamp,
                usmap_path or "",
                injection_log_dir or "",
                error_details or ""
            ])
        
        logger.info(f"Logged game status: {game_name} - {status}")
        
        # Send webhook notification if enabled
        if self.webhook_url:
            # Construct a complete message with all fields
            message = f"[{timestamp}] Game: {game_name} - Status: {status}"
            
            # Add USMap path if present
            if usmap_path:
                message += f"\nUSMap path: {usmap_path}"
            
            # Add Injection log directory if present
            if injection_log_dir:
                message += f"\nInjection log directory: {injection_log_dir}"
            
            # Add Error details if present
            if error_details:
                message += f"\nError details: {error_details}"
                
            self.send_webhook_notification(message)
    
    def log_download_error(self, game_name, error_details=None):
        """Log a download error for a game."""
        self.log_game_status(
            game_name=game_name,
            status="DOWNLOAD_ERROR",
            error_details=error_details
        )
    
    def log_download_success(self, game_name):
        """Log a successful download for a game."""
        self.log_game_status(
            game_name=game_name,
            status="DOWNLOAD_SUCCESS"
        )
    
    def log_injection_crash(self, game_name, error_details=None, injection_log_dir=None):
        """
        Log an injection crash for a game.
        
        Args:
            game_name (str): Name of the game
            error_details (str, optional): Error details if an error occurred
            injection_log_dir (str, optional): Path to the injection log directory
        """
        self.log_game_status(
            game_name=game_name,
            status="INJECTION_CRASH",
            injection_log_dir=injection_log_dir,
            error_details=error_details
        )
    
    def log_injection_timeout(self, game_name, injection_log_dir=None):
        """
        Log an injection timeout for a game.
        
        Args:
            game_name (str): Name of the game
            injection_log_dir (str, optional): Path to the injection log directory
        """
        self.log_game_status(
            game_name=game_name,
            status="INJECTION_TIMEOUT",
            injection_log_dir=injection_log_dir,
            error_details="Injection process timed out"
        )
    
    def log_injection_success(self, game_name, usmap_path, injection_log_dir=None):
        """
        Log a successful injection for a game.
        
        Args:
            game_name (str): Name of the game
            usmap_path (str): Path to the USMap file
            injection_log_dir (str, optional): Path to the injection log directory
        """
        self.log_game_status(
            game_name=game_name,
            status="INJECTION_SUCCESS",
            usmap_path=usmap_path,
            injection_log_dir=injection_log_dir
        )
    
    def get_csv_path(self):
        """Return the path to the CSV file."""
        return str(self.csv_path) 