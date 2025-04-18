import os
import time
import logging
import subprocess
import pyautogui as pg
import psutil
import pygetwindow as gw
from datetime import datetime
from logger import setup_logging

logger = setup_logging()

class DLLInjector:
    def __init__(self, game_folder=None):
        self.injector_path = "C:\\Users\\Administrator\\Documents\\AutoHotkey\\inject.exe"
        self.playable_image_paths = [
            (os.path.join(os.path.dirname(__file__), "png/playable.png"), 0.8),
            (os.path.join(os.path.dirname(__file__), "png/start_game.png"), 0.75)
        ]
        self.game_folder = game_folder  # Game folder path passed as an argument
        
    def activate_steam_window(self):
        """Activate Steam window and bring it to the front"""
        try:
            # Get all windows with 'Steam' in the title
            windows = gw.getWindowsWithTitle("Steam")
            if not windows:
                logger.error("Steam window not found")
                return False

            for window in windows:
                if window.title == "Steam":
                    window.restore()  # Restore window if minimized
                    time.sleep(0.3)
                    window.activate()  # Activate and bring window to front
                    time.sleep(0.3)
                    
                    # Click on the window to ensure it's active
                    pg.click((window.left + window.right)//2, window.top + 10)
                    logger.info("Steam window activated and brought to front")
                    return True

            logger.error("No window with exact 'Steam' title found")
            return False
        except Exception as e:
            logger.error(f"Error activating Steam window: {str(e)}")
            return False
        
    def detect_and_click_playable(self, max_retries=10, retry_interval=2):
        """
        Detect the 'playable.png' image on screen and click it.
        Returns True if successful, False otherwise.
        """
        logger.info("Looking for playable button...")
        for i in range(max_retries):
            try:
                for image_path, confidence in self.playable_image_paths:
                    print("playable_location", image_path, confidence)
                    try:
                        playable_location = pg.locateOnScreen(image_path, confidence=confidence)
                    except Exception as e:
                        logger.error(f"Error locating image: {str(e)}")
                        continue
                    logger.info(playable_location)                    
                    if playable_location:
                        logger.info("Found playable button!")
                        playable_center = pg.center(playable_location)
                        print(playable_center)
                        pg.click(playable_center)
                        logger.info("Clicked playable button")
                        return True
                    
                    logger.info(f"Playable button not found, retrying ({i+1}/{max_retries})...")
                    time.sleep(retry_interval)
                
            except Exception as e:
                logger.error(f"Error detecting playable button: {str(e)}")
                time.sleep(retry_interval)
        
        logger.error("Failed to find playable button after maximum retries")
        return False
    
    def get_running_processes(self):
        """Get a set of (name, exe_path, pid) for all currently running processes"""
        processes = set()
        for proc in psutil.process_iter(['name', 'exe', 'pid']):
            try:
                if proc.info['exe']:  # Only record processes with exe paths
                    processes.add((proc.info['name'], proc.info['exe'], proc.info['pid']))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return processes
    
    def get_process_details(self, pid):
        """Get detailed information about a process by PID"""
        try:
            # Check if process exists before trying to get details
            if not psutil.pid_exists(pid):
                logger.error(f"Process with PID {pid} does not exist")
                return None
                
            proc = psutil.Process(pid)
            
            # Get basic info first to ensure the process is still accessible
            name = proc.name()
            exe_path = proc.exe()
            
            # Now get the rest of the details
            memory_mb = proc.memory_info().rss / (1024 * 1024)  # Convert to MB
            create_time = datetime.fromtimestamp(proc.create_time()).strftime('%H:%M:%S')
            
            # Get parent process name safely
            try:
                parent = psutil.Process(proc.ppid()).name() if proc.ppid() else "No parent"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                parent = "Unknown parent"
                
            return {
                'name': name,
                'exe': exe_path,
                'memory_mb': round(memory_mb, 2),
                'cpu_percent': proc.cpu_percent(interval=0.1),
                'create_time': create_time,
                'num_threads': proc.num_threads(),
                'parent_process': parent
            }
        except psutil.NoSuchProcess:
            logger.error(f"Process PID not found (pid={pid})")
            return None
        except psutil.AccessDenied:
            logger.error(f"Access denied when accessing process (pid={pid})")
            # Try to get minimal information
            try:
                name = psutil.Process(pid).name()
                return {
                    'name': name,
                    'exe': "Access denied",
                    'memory_mb': 0,
                    'cpu_percent': 0,
                    'create_time': "Unknown",
                    'num_threads': 0,
                    'parent_process': "Unknown"
                }
            except:
                return None
        except Exception as e:
            logger.error(f"Error getting process details for PID {pid}: {str(e)}")
            return None
    
    def is_from_game_folder(self, exe_path):
        """
        Check if the executable is from the specified game folder.
        Returns True if it is, False otherwise.
        """
        if not exe_path or not self.game_folder:
            return False
            
        # Convert to lowercase and normalize path separator for comparison
        exe_path_norm = exe_path.lower().replace('\\', '/')
        game_folder_norm = self.game_folder.lower().replace('\\', '/')
        
        # Check if the executable is in the game folder
        if game_folder_norm in exe_path_norm:
            logger.info(f"Process {exe_path} is in the specified game folder {self.game_folder}")
            return True
            
        return False
    
    def find_new_game_process(self, before, after):
        """
        Compare before and after process sets, return the most likely game process
        """
        # Find new processes (those in 'after' but not in 'before')
        before_pids = {pid for _, _, pid in before}
        new_processes = []
        
        for name, exe, pid in after:
            if pid not in before_pids:
                new_processes.append((name, exe, pid))
        
        # Filter out common system processes
        system_keywords = [
            'svchost', 'explorer', 'dllhost', 'runtimebroker', 'steamwebhelper',
            'taskmgr', 'python', 'cmd', 'conhost', 'searchapp', 'rundll32'
        ]
        
        game_processes = []
        for name, exe, pid in new_processes:
            if not any(keyword in name.lower() for keyword in system_keywords) and name.lower().endswith('.exe'):
                # Check if it's from the specified game folder
                if self.game_folder is None or self.is_from_game_folder(exe):
                    game_processes.append((name, exe, pid))
                    logger.info(f"Found potential game process: {name} (PID: {pid}) at {exe}")
                else:
                    logger.info(f"Skipping process not from game folder: {name} ({exe})")
        
        if not game_processes:
            logger.error("No new game processes detected from the specified folder")
            return None
        
        # Get detailed information for each potential game process
        process_details = []
        for name, exe, pid in game_processes:
            try:
                # Verify process still exists before getting details
                if psutil.pid_exists(pid):
                    details = self.get_process_details(pid)
                    if details:
                        process_details.append((name, exe, pid, details))
                    else:
                        logger.error(f"Could not get details for process {name} (PID: {pid})")
                else:
                    logger.error(f"Process {name} (PID: {pid}) no longer exists")
            except Exception as e:
                logger.error(f"Error processing {name} (PID: {pid}): {str(e)}")
        
        if not process_details:
            # If we couldn't get details for any process but we have game processes, 
            # return the first one as a fallback
            if game_processes:
                name, exe, pid = game_processes[0]
                logger.warning(f"Using fallback: returning game process without details: {name} (PID: {pid})")
                return {"pid": pid, "name": name, "exe": exe}
            
            logger.error("Could not get details for any new game processes")
            return None
        
        # Sort processes by memory usage (usually the main game uses the most memory)
        process_details.sort(key=lambda x: x[3]['memory_mb'], reverse=True)
        
        # Log all detected processes for debugging
        logger.info(f"Detected {len(process_details)} potential game processes:")
        for i, (name, exe, pid, details) in enumerate(process_details):
            logger.info(f"{i+1}. {name} (PID: {pid}) - Memory: {details['memory_mb']} MB, CPU: {details['cpu_percent']}%, Threads: {details['num_threads']}")
        
        # Return the process with the highest memory usage as the most likely game process
        selected_process = process_details[0]
        name, exe, pid, details = selected_process
        
        logger.info(f"Selected game process: {name} (PID: {pid})")
        logger.info(f"  Path: {exe}")
        logger.info(f"  Memory Usage: {details['memory_mb']} MB")
        logger.info(f"  CPU Usage: {details['cpu_percent']}%")
        logger.info(f"  Created at: {details['create_time']}")
        logger.info(f"  Thread Count: {details['num_threads']}")
        logger.info(f"  Parent Process: {details['parent_process']}")
        
        return {"pid": pid, "name": name, "exe": exe}
    
    def inject_dll(self, pid):
        """
        Inject DLL into the game process using inject.exe
        """
        if not os.path.exists(self.injector_path):
            logger.error(f"Injector executable not found at: {self.injector_path}")
            return False
        
        try:
            logger.info(f"Running injector with PID: {pid}")
            cmd = f'"{self.injector_path}" {pid}'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Injection successful")
                return True
            else:
                logger.error(f"Injection failed with return code {result.returncode}")
                logger.error(f"Error output: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error running injector: {str(e)}")
            return False

    def minimize_window_by_pid(self, pid):
        """
        Minimize a window associated with the given PID.
        For full-screen games, tries several approaches.
        """
        try:
            logger.info(f"Attempting to minimize window for PID {pid}")
            
            # First approach: Try using pygetwindow to find and minimize the window directly
            window_found = False
            try:
                all_windows = gw.getAllWindows()
                logger.info(f"Found {len(all_windows)} windows total")
                
                for window in all_windows:
                    try:
                        window_pid = gw._getWindowPid(window._hWnd)
                        # Log all windows with title for debugging
                        if window.title:
                            logger.info(f"Window: '{window.title}' (PID: {window_pid})")
                        
                        if window_pid == pid:
                            logger.info(f"Found matching window for PID {pid}: '{window.title}'")
                            window_found = True
                            window.minimize()
                            logger.info(f"Minimized window: '{window.title}'")
                            return True
                    except Exception as e:
                        logger.error(f"Error checking window: {str(e)}")
                        continue  # Skip this window if we can't get its PID
            except Exception as e:
                logger.error(f"Error in window enumeration: {str(e)}")
            
            if not window_found:
                logger.warning(f"Could not find any window associated with PID {pid}")
                
                # Second approach: For full-screen games, try Alt+Tab to switch away
                logger.info("Trying Alt+Tab approach for full-screen game...")
                pg.keyDown('alt')
                pg.press('tab')
                time.sleep(0.5)
                pg.keyUp('alt')
                time.sleep(0.5)
                
                # Third approach: Try Win+D to minimize all windows
                # logger.info("Trying Win+D to minimize all windows...")
                # pg.keyDown('winleft')
                # pg.press('d')
                # pg.keyUp('winleft')
                # time.sleep(0.5)
                
                logger.info("Attempted alternative minimization approaches")
                return True  # Return true since we tried our best
                
            return False
        except Exception as e:
            logger.error(f"Error minimizing window for PID {pid}: {str(e)}")
            return False

    def run_injection_process(self):
        """
        Full process: activate Steam window, detect playable button, click it, get game process, and inject DLL
        """
        logger.info("Starting DLL injection process...")
        if self.game_folder:
            logger.info(f"Using game folder: {self.game_folder}")
        else:
            logger.info("No game folder specified, will detect any new process")
        
        # Step 1: Activate the Steam window
        if not self.activate_steam_window():
            logger.error("Failed to activate Steam window")
            return False
        
        # Step 2: Record processes BEFORE clicking playable button
        logger.info("Recording processes before game launch...")
        before_processes = self.get_running_processes()
        
        # Step 3: Detect and click playable button
        if not self.detect_and_click_playable():
            logger.error("Failed to find and click playable button")
            return False
        
        # Step 4: Wait for the game process to start
        logger.info(f"Waiting 60 seconds for game to launch...")
        time.sleep(60)  # Increased wait time for game launch
        
        # Step 5: Get processes after waiting
        logger.info("Recording processes after game launch...")
        after_processes = self.get_running_processes()
        
        # Step 6: Find the most likely game process
        game_process = self.find_new_game_process(before_processes, after_processes)
        
        if not game_process:
            logger.error("Failed to detect game process")
            return False
        
        # Step 7: Minimize the game window before injection
        pid = game_process["pid"]
        logger.info(f"Attempting to minimize game window (PID: {pid})")
        self.minimize_window_by_pid(pid)
        
        # Give the window a moment to minimize
        time.sleep(1)
        
        # Step 8: Inject DLL into the game process
        if self.inject_dll(pid):
            logger.info(f"Successfully injected DLL into {game_process['name']} (PID: {pid})")
            return True
        else:
            logger.error(f"Failed to inject DLL into {game_process['name']} (PID: {pid})")
            return False


if __name__ == "__main__":
    import sys
    
    # Check if a game folder was provided as a command line argument
    game_folder = None
    if len(sys.argv) > 1:
        game_folder = sys.argv[1]
        
    injector = DLLInjector(game_folder)
    injector.run_injection_process()
