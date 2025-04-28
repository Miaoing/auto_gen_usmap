import os
import time
import logging
import pyautogui as pg
from datetime import datetime
import re

logger = logging.getLogger(__name__)

# Define a timestamp format for debug screenshot folders
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

class DebugScreenshotManager:
    def __init__(self, base_folder="screenshots"):
        self.base_folder = base_folder
        self.game_folders = {}
        self.last_screenshot_time = {}
        # Create base screenshots folder if it doesn't exist
        os.makedirs(base_folder, exist_ok=True)
        logger.info(f"Debug screenshot manager initialized with base folder: {base_folder}")
        
    def get_game_folder(self, game_name):
        """Get or create a timestamped folder for a specific game's screenshots"""
        if game_name not in self.game_folders:
            # Format game name to be folder-friendly
            formatted_name = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', game_name)
            timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
            game_folder = os.path.join(self.base_folder, f"{formatted_name}_{timestamp}")
            os.makedirs(game_folder, exist_ok=True)
            self.game_folders[game_name] = game_folder
            self.last_screenshot_time[game_name] = 0
            logger.info(f"Created debug screenshot folder for game '{game_name}': {game_folder}")
        
        return self.game_folders[game_name]
    
    def take_screenshot(self, game_name, screenshot_type, min_interval_seconds=300):
        """
        Take a debug screenshot for a game if the minimum interval has passed
        
        Args:
            game_name: Name of the game being processed
            screenshot_type: Type/description of the screenshot (e.g., 'search', 'install')
            min_interval_seconds: Minimum seconds between screenshots (default: 5 minutes)
        
        Returns:
            Path to the saved screenshot or None if screenshot wasn't taken
        """
        current_time = time.time()
        
        # Check if minimum interval has passed since last screenshot
        if game_name in self.last_screenshot_time:
            time_since_last = current_time - self.last_screenshot_time[game_name]
            if time_since_last < min_interval_seconds:
                # Skip screenshot if we're taking them too frequently
                logger.debug(f"Skipping '{screenshot_type}' screenshot for '{game_name}' - too frequent ({time_since_last:.1f}s < {min_interval_seconds}s)")
                return None
        
        # Update last screenshot time
        self.last_screenshot_time[game_name] = current_time
        
        # Create timestamped filename
        timestamp = datetime.now().strftime("%H%M%S")
        game_folder = self.get_game_folder(game_name)
        screenshot_path = os.path.join(game_folder, f"{screenshot_type}_{timestamp}.png")
        
        try:
            # Take and save the screenshot
            screenshot = pg.screenshot()
            screenshot.save(screenshot_path)
            logger.info(f"Debug screenshot saved: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            logger.error(f"Failed to take debug screenshot: {str(e)}")
            return None 