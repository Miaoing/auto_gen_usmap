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
        self.retry_interval = self.config['image_detector']['retry_interval']
        self.max_retries = self.config['image_detector']['max_retries']
        self.confidence = self.config['image_detector']['default_confidence']
        self.wait_after_click = self.config['image_detector']['wait_after_click']

    def check_and_click_image(self, image_path, max_retries=None, confidence=None):
        """
        Generic method to check for and click an image on screen
        
        Args:
            image_path: Path to the image file to look for
            wait_after_click: Time to wait after clicking the image
        
        Returns:
            True if image was found and clicked, False otherwise
        """
        max_retries = max_retries or self.max_retries
        confidence = confidence or self.confidence

        # Extract image basename for logging and config lookup
        image_basename = os.path.splitext(os.path.basename(image_path))[0]
        
        logger.info(f"Checking for {image_basename}...")
        for i in range(max_retries):
            try:
                location = pg.locateOnScreen(image_path, confidence=confidence)
                if location:
                    logger.info(f"Found {image_basename}")
                    center = pg.center(location)
                    pg.click(center)
                    logger.info(f"Clicked {image_basename}")
                    time.sleep(self.wait_after_click)
                    return True
                logger.info(f"{image_basename} not found, retry {i+1}/{max_retries}")
                time.sleep(self.retry_interval)
            except Exception as e:
                logger.warning(f"{image_basename} not found: {str(e)}")
                time.sleep(self.retry_interval)
        
        logger.info(f"No {image_basename} found after maximum retries")
        return False 