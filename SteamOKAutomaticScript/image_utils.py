"""
Utility module for image detection and clicking in the SteamOKAutomaticScript.
Handles all screen image recognition and interaction operations.
"""
import os
import time
import logging
import pyautogui as pg
from logger import setup_logging

# Get logger
logger = logging.getLogger()

class ImageDetector:
    """
    Class for detecting images on screen and interacting with them.
    Provides utilities for finding and clicking UI elements.
    """
    
    def __init__(self, config):
        """
        Initialize the image detector with configuration settings.
        
        Args:
            config: The loaded configuration dictionary
        """
        self.config = config
        self.sleep_config = config['dll_injection']['sleep_timings']
        self.retry_counts = config['dll_injection']['retry_counts']
    
    def check_and_click_image(self, image_path, max_retries=5,
                             confidence=None, wait_after_click=1):
        """
        Generic method to check for and click an image on screen
        
        Args:
            image_path: Path to the image file to look for
            max_retries: Override for max retries count
            retry_interval: Override for retry interval
            confidence: Override for confidence level
            wait_after_click: Time to wait after clicking the image
        
        Returns:
            True if image was found and clicked, False otherwise
        """
        # Get retry interval from parameter or default
        retry_interval = self.sleep_config.get('retry_interval', 2)
        
        # Extract image basename for logging and config lookup
        image_basename = os.path.splitext(os.path.basename(image_path))[0]
        
        # If confidence is not provided, try to get it from config based on image name
        if confidence is None:
            confidence = self.config['dll_injection']['images'].get(f"{image_basename}_confidence", 0.8)
        
        logger.info(f"Checking for {image_basename}...")
        for i in range(max_retries):
            try:
                location = pg.locateOnScreen(image_path, confidence=confidence)
                if location:
                    logger.info(f"Found {image_basename}")
                    center = pg.center(location)
                    pg.click(center)
                    logger.info(f"Clicked {image_basename}")
                    time.sleep(wait_after_click)
                    return True
                logger.info(f"{image_basename} not found, retry {i+1}/{max_retries}")
                time.sleep(retry_interval)
            except Exception as e:
                logger.warning(f"{image_basename} not found: {str(e)}")
                time.sleep(retry_interval)
        
        logger.info(f"No {image_basename} found after maximum retries")
        return False 