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

def activate_window_by_typing(window_name, sleep_config):
    """
    Activate a window by using the Windows search function (Win key + typing)
    
    Args:
        window_name: The name of the window/application to activate
        sleep_config: Optional dictionary with sleep configuration values.
                     If None, default values will be used.
                     
    Returns:
        True if successful, False otherwise
    """
    try:
        # Press the Windows key to open start menu
        pg.hotkey('win')
        time.sleep(sleep_config.get('typing_delay'))  # Wait for start menu to open
        
        # Type the window name
        pg.write(window_name)
        time.sleep(sleep_config.get('typing_delay'))  # Wait for search results
        
        # Press Enter to select and launch the application
        pg.press('enter')
        time.sleep(sleep_config.get('typing_delay'))
        
        # Sometimes a second Enter is needed if the search result is selected but not launched
        pg.press('enter')
        time.sleep(sleep_config.get('app_launch_delay'))  # Wait for application to launch
        
        logger.info(f"{window_name} window activated using Win+Type method")
        return True
        
    except Exception as e:
        logger.error(f"Error activating {window_name} window using Win+Type method: {str(e)}")
        return False

def activate_window_by_title(window_title, sleep_config):
    """
    Activate a window by finding it based on its title and bringing it to front
    
    Args:
        window_title: The title of the window to activate
        sleep_config: Optional dictionary with sleep configuration values.
                     If None, default values will be used.
                     
    Returns:
        True if successful, False otherwise
    """

        
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
        time.sleep(sleep_config.get('window_activate_delay'))
        
        # Activate the window
        target_window.activate()
        time.sleep(sleep_config.get('window_activate_delay'))
        
        # Click near the top of the window to ensure it's focused
        pg.click((target_window.left + target_window.right)//2, target_window.top + 10)
        time.sleep(sleep_config.get('click_delay'))
        
        logger.info(f"{window_title} window activated successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to activate window by title - {window_title}: {str(e)}")
        return False 

def activate_window(window_name, sleep_config):
    """
    Activate a window using the most reliable method available.
    First tries to find and activate an existing window by title,
    if that fails, falls back to the typing method.
    
    Args:
        window_name: The name of the window/application to activate
        sleep_config: Optional dictionary with sleep configuration values.
                     If None, default values will be used.
                     
    Returns:
        True if activation was successful by any method, False otherwise
    """
    logger.info(f"Attempting to activate {window_name} window...")
    # Show desktop first by sending Windows+D
    pg.hotkey('win', 'd')
    time.sleep(0.5)
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # First try to activate by title (faster if window exists)
            if activate_window_by_title(window_name, sleep_config):
                logger.info(f"Successfully activated {window_name} window by title")
                return True
        except Exception as e:
            logger.warning(f"Failed to activate {window_name} window by title: {str(e)}")
        
        # If activation by title failed, try the typing method
        logger.info(f"Falling back to typing method for {window_name}")
        activate_window_by_typing(window_name, sleep_config)
        logger.info(f"Try to activate {window_name} window by typing")

    # If both methods failed
    logger.error(f"Failed to activate {window_name} window by any method")
    return False 

if __name__ == "__main__":
    sleep_config = {
        'typing_delay': 0.5,
        'app_launch_delay': 0.5,
        'window_activate_delay': 0.5,
        'click_delay': 1
    }
    activate_window("Steam", sleep_config)
    activate_window("SteamOK", sleep_config)
    
