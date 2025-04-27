"""
Utility module for window management and interactions in the SteamOKAutomaticScript.
Provides functions for activating, finding, and interacting with windows.
"""
import time
import logging
import pyautogui as pg
import pygetwindow as gw

# Get logger
logger = logging.getLogger()

def activate_window_by_typing(window_name, sleep_config=None):
    """
    Activate a window by using the Windows search function (Win key + typing)
    
    Args:
        window_name: The name of the window/application to activate
        sleep_config: Optional dictionary with sleep configuration values.
                     If None, default values will be used.
                     
    Returns:
        True if successful, False otherwise
    """
    # Default sleep values if none provided
    if sleep_config is None:
        sleep_config = {
            'window_activate': 1,
            'typing_delay': 0.5,
            'app_launch': 1
        }
    
    try:
        # Press the Windows key to open start menu
        pg.hotkey('win')
        time.sleep(sleep_config.get('typing_delay', 0.5))  # Wait for start menu to open
        
        # Type the window name
        pg.write(window_name)
        time.sleep(sleep_config.get('typing_delay', 0.5))  # Wait for search results
        
        # Press Enter to select and launch the application
        pg.press('enter')
        time.sleep(sleep_config.get('typing_delay', 0.5))
        
        # Sometimes a second Enter is needed if the search result is selected but not launched
        pg.press('enter')
        time.sleep(sleep_config.get('app_launch', 1))  # Wait for application to launch
        
        logger.info(f"{window_name} window activated using Win+Type method")
        return True
        
    except Exception as e:
        logger.error(f"Error activating {window_name} window using Win+Type method: {str(e)}")
        return False

def activate_window_by_title(window_title, sleep_config=None):
    """
    Activate a window by finding it based on its title and bringing it to front
    
    Args:
        window_title: The title of the window to activate
        sleep_config: Optional dictionary with sleep configuration values.
                     If None, default values will be used.
                     
    Returns:
        True if successful, False otherwise
    """
    # Default sleep values if none provided
    if sleep_config is None:
        sleep_config = {
            'window_activate': 1,
            'click_delay': 0.5
        }
        
    try:
        windows = gw.getWindowsWithTitle(window_title)
        if not windows:
            logger.error(f"No windows found with title: {window_title}")
            return False
            
        # Find window with exact title match if possible
        target_window = None
        for window in windows:
            if window.title == window_title:
                target_window = window
                break
                
        # If no exact match, use the first one with a partial match
        if target_window is None:
            target_window = windows[0]
            
        # Restore the window if minimized
        target_window.restore()
        time.sleep(sleep_config.get('window_activate', 1))
        
        # Activate the window
        target_window.activate()
        time.sleep(sleep_config.get('window_activate', 1))
        
        # Click near the top of the window to ensure it's focused
        pg.click((target_window.left + target_window.right)//2, target_window.top + 10)
        time.sleep(sleep_config.get('click_delay', 0.5))
        
        logger.info(f"{window_title} window activated successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to activate window {window_title}: {str(e)}")
        return False 