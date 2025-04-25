import os
import time
import logging
import subprocess
import pyautogui as pg
import psutil
import pygetwindow as gw
from datetime import datetime
from logger import setup_logging
import glob

# Disable PyAutoGUI fail-safe (not recommended for safety reasons)
pg.FAILSAFE = False

logger = setup_logging()

class DLLInjector:
    def __init__(self, game_folder, dll_injector_path="E:\\DLLInjector.lnk"):
        self.game_folder = game_folder
        self.dll_injector_path = dll_injector_path
        self.playable_image_paths = [
            (os.path.join(os.path.dirname(__file__), "png/playable.png"), 0.8),
            (os.path.join(os.path.dirname(__file__), "png/start_game.png"), 0.75)
        ]
        self.start_game2_path = os.path.join(os.path.dirname(__file__), "png/start_game2.png")
        self.yunxu_path = os.path.join(os.path.dirname(__file__), "png/yunxu.png")
        self.still_play_game_path = os.path.join(os.path.dirname(__file__), "png/still_play_game.png")
        
        # Sleep configuration dictionary
        self.sleep_config = {
            'window_activate': 0.3,  # Time to wait after window activation
            'click_delay': 0.5,      # Time to wait after clicking
            'dll_injector_start': 5, # Time to wait for DLL Injector to start
            'process_check': 2,      # Time between process checks
            'game_launch': 30,       # Time to wait for game to launch
            'minimize_wait': 1,      # Time to wait after minimizing windows
            'retry_interval': 2,     # Time between retries for various operations
            'keyboard_delay': 0.1,   # Time between keyboard actions
            'injection_check': 2,    # Time between injection status checks
            'window_close': 1,       # Time to wait after closing windows
            'injection_max_wait': 240, # Maximum time to wait for injection (4 minutes)
        }
        logger.info(f"DLLInjector initialized with game_folder: {game_folder}")
        
    def activate_steam_window(self):
        """Activate Steam window and bring it to the front"""
        try:
            windows = gw.getWindowsWithTitle("Steam")
            if not windows:
                logger.error("Steam window not found")
                return False

            for window in windows:
                if window.title == "Steam":
                    window.restore()
                    time.sleep(self.sleep_config['window_activate'])
                    window.activate()
                    time.sleep(self.sleep_config['window_activate'])
                    
                    pg.click((window.left + window.right)//2, window.top + 10)
                    logger.info("Steam window activated successfully")
                    return True

            logger.error("No window with exact 'Steam' title found")
            return False
        except Exception as e:
            logger.error(f"Failed to activate Steam window: {str(e)}")
            return False
        
    def detect_and_click_playable(self, max_retries=10, retry_interval=2):
        """
        Detect the 'playable.png' image on screen and click it.
        Returns True if successful, False otherwise.
        """
        logger.info("Searching for playable button...")
        for i in range(max_retries):
            try:
                for image_path, confidence in self.playable_image_paths:
                    logger.debug(f"Checking image: {image_path} with confidence: {confidence}")
                    try:
                        playable_location = pg.locateOnScreen(image_path, confidence=confidence)
                        if playable_location:
                            logger.info("Found playable button")
                            playable_center = pg.center(playable_location)
                            pg.click(playable_center)
                            logger.info("Clicked playable button successfully")
                            return True
                    except Exception as e:
                        logger.debug(f"Error locating image: {str(e)}")

                    logger.info(f"Playable button not found, retry {i+1}/{max_retries}")
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
        logger.debug(f"Found {len(processes)} running processes")
        return processes
    
    def get_process_details(self, pid):
        """Get detailed information about a process by PID"""
        try:
            if not psutil.pid_exists(pid):
                logger.error(f"Process with PID {pid} does not exist")
                return None
                
            proc = psutil.Process(pid)
            
            name = proc.name()
            exe_path = proc.exe()
            memory_mb = proc.memory_info().rss / (1024 * 1024)  # Convert to MB
            create_time = datetime.fromtimestamp(proc.create_time()).strftime('%H:%M:%S')
            
            try:
                parent = psutil.Process(proc.ppid()).name() if proc.ppid() else "No parent"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                parent = "Unknown parent"
                
            details = {
                'name': name,
                'exe': exe_path,
                'memory_mb': round(memory_mb, 2),
                'cpu_percent': proc.cpu_percent(interval=0.1),
                'create_time': create_time,
                'num_threads': proc.num_threads(),
                'parent_process': parent
            }
            logger.debug(f"Process details for PID {pid}: {details}")
            return details
            
        except psutil.NoSuchProcess:
            logger.error(f"Process PID not found (pid={pid})")
            return None
        except psutil.AccessDenied:
            logger.error(f"Access denied when accessing process (pid={pid})")
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
            
        exe_path_norm = exe_path.lower().replace('\\', '/')
        game_folder_norm = self.game_folder.lower().replace('\\', '/')
        
        if game_folder_norm in exe_path_norm:
            logger.debug(f"Process {exe_path} is in the specified game folder {self.game_folder}")
            return True
            
        return False
    
    def find_new_game_process(self, before, after):
        """
        Compare before and after process sets, return the most likely game process
        """
        before_pids = {pid for _, _, pid in before}
        new_processes = []
        
        for name, exe, pid in after:
            if pid not in before_pids:
                new_processes.append((name, exe, pid))
        
        system_keywords = [
            'svchost', 'explorer', 'dllhost', 'runtimebroker', 'steamwebhelper',
            'taskmgr', 'python', 'cmd', 'conhost', 'searchapp', 'rundll32'
        ]
        
        game_processes = []
        for name, exe, pid in new_processes:
            if not any(keyword in name.lower() for keyword in system_keywords) and name.lower().endswith('.exe'):
                if self.game_folder is None or self.is_from_game_folder(exe):
                    game_processes.append((name, exe, pid))
                    logger.info(f"Found potential game process: {name} (PID: {pid}) at {exe}")
                else:
                    logger.debug(f"Skipping process not from game folder: {name} ({exe})")
        
        if not game_processes:
            logger.error("No new game processes detected from the specified folder")
            return None
        
        process_details = []
        for name, exe, pid in game_processes:
            try:
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
            if game_processes:
                name, exe, pid = game_processes[0]
                logger.warning(f"Using fallback: returning game process without details: {name} (PID: {pid})")
                return {"pid": pid, "name": name, "exe": exe}
            
            logger.error("Could not get details for any new game processes")
            return None
        
        process_details.sort(key=lambda x: x[3]['memory_mb'], reverse=True)
        
        logger.info(f"Detected {len(process_details)} potential game processes:")
        for i, (name, exe, pid, details) in enumerate(process_details):
            logger.info(f"{i+1}. {name} (PID: {pid}) - Memory: {details['memory_mb']} MB, CPU: {details['cpu_percent']}%, Threads: {details['num_threads']}")
        
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
    
    def click_relative(self, window, x_ratio, y_ratio):
        """Click at a position relative to window size"""
        try:
            left, top, right, bottom = window.left, window.top, window.right, window.bottom
            width = right - left
            height = bottom - top

            x = left + int(width * (x_ratio / 300))
            y = top + int(height * (y_ratio / 400))

            pg.click(x, y)
            time.sleep(self.sleep_config['click_delay'])
            logger.debug(f"Clicked at relative position: ({x_ratio}, {y_ratio}) -> ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Error in click_relative: {str(e)}")
            return False

    def get_latest_log_directory(self, base_path="C:\\Dumper-7\\log", injection_start_time=None):
        """
        Get the most recent log directory created after injection start time
        """
        try:
            directories = glob.glob(os.path.join(base_path, "*"))
            if not directories:
                logger.error("No log directories found")
                return None

            valid_dirs = []
            for dir_path in directories:
                try:
                    dir_name = os.path.basename(dir_path)
                    dir_time = datetime.strptime(dir_name, "%Y%m%d_%H%M%S")
                    
                    if injection_start_time is None or dir_time > injection_start_time:
                        valid_dirs.append((dir_time, dir_path))
                except ValueError:
                    continue

            if not valid_dirs:
                logger.error("No valid timestamp directories found")
                return None

            latest_dir = max(valid_dirs, key=lambda x: x[0])[1]
            logger.info(f"Found latest log directory: {latest_dir}")
            return latest_dir

        except Exception as e:
            logger.error(f"Error finding latest log directory: {str(e)}")
            return None

    def check_injection_status(self, pid, check_interval=10, injection_start_time=None):
        """
        Check the injection status by monitoring log files
        Returns: 
            - True if injection succeeded
            - False if injection failed
            - "timeout" if injection took too long
            - "crashed" if game process ended unexpectedly
        """
        start_time = time.time()
        base_log_path = "C:\\Dumper-7\\log"
        max_wait_time = self.sleep_config['injection_max_wait']
        
        while time.time() - start_time < max_wait_time:
            try:
                if not psutil.pid_exists(pid):
                    logger.error("Game process crashed or ended unexpectedly")
                    log_dir = self.get_latest_log_directory(base_log_path, injection_start_time)
                    if log_dir:
                        crash_signal_path = os.path.join(log_dir, "crash.signal")
                        try:
                            with open(crash_signal_path, 'w') as f:
                                f.write(f"Process {pid} crashed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                            logger.info(f"Created crash signal file at {crash_signal_path}")
                        except Exception as e:
                            logger.error(f"Failed to create crash signal file: {str(e)}")
                    return "crashed"
            except Exception as e:
                logger.error(f"Error checking process status: {str(e)}")
                return False

            log_dir = self.get_latest_log_directory(base_log_path, injection_start_time)
            if not log_dir:
                time.sleep(check_interval)
                continue

            try:
                end_signal = os.path.exists(os.path.join(log_dir, "end.signal"))
                
                if end_signal:
                    success_signal = os.path.exists(os.path.join(log_dir, "success.signal"))
                    if success_signal:
                        logger.info("Injection completed successfully")
                        return True
                    else:
                        logger.error("Injection failed: process ended without success signal")
                        return False

                running_signal = os.path.exists(os.path.join(log_dir, "running.signal"))
                if running_signal:
                    logger.info("Injection still running...")
                    time.sleep(check_interval)
                    continue
                
                logger.error("Injection failed: neither running.signal nor end.signal found")
                return False
                
            except Exception as e:
                logger.error(f"Error checking injection status: {str(e)}")
                return False

            time.sleep(check_interval)

        logger.error(f"Injection timed out after {max_wait_time} seconds")
        return "timeout"

    def terminate_process(self, pid):
        """
        Terminate a process by its PID
        Returns True if successful, False otherwise
        """
        try:
            process = psutil.Process(pid)
            process.terminate()
            
            try:
                process.wait(timeout=10)
            except psutil.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                
            logger.info(f"Successfully terminated process with PID: {pid}")
            return True
        except psutil.NoSuchProcess:
            logger.info(f"Process with PID {pid} no longer exists")
            return True
        except Exception as e:
            logger.error(f"Error terminating process {pid}: {str(e)}")
            return False

    def inject_dll(self, pid):
        """
        Inject DLL by directly interacting with DLL Injector GUI
        """
        injection_start_time = datetime.now()
        try:
            windows = gw.getWindowsWithTitle("DLL Injector")
            if not windows:
                logger.info("DLL Injector not found, launching...")
                os.startfile(self.dll_injector_path)
                time.sleep(self.sleep_config['dll_injector_start'])
                
                windows = gw.getWindowsWithTitle("DLL Injector")
                if not windows:
                    logger.error("Could not find DLL Injector window after launch")
                    return False
            else:
                logger.info("Found existing DLL Injector window, activating...")

            logger.debug("Activating DLL Injector window")
            window = windows[0]
            window.activate()
            time.sleep(1)

            try:
                process = psutil.Process(pid)
                process_name = process.name().lower()
                logger.info(f"Target process: {process_name} (PID: {pid})")
            except Exception as e:
                logger.error(f"Error getting process name: {str(e)}")
                return False

            logger.debug("Inputting process ID...")
            self.click_relative(windows[0], 100, 115)
            time.sleep(self.sleep_config['window_activate'])
            
            pg.keyDown('ctrl')
            time.sleep(self.sleep_config['keyboard_delay'])
            pg.press('a')
            time.sleep(self.sleep_config['keyboard_delay'])
            pg.keyUp('ctrl')
            time.sleep(self.sleep_config['window_activate'])

            pg.press('backspace')
            time.sleep(self.sleep_config['click_delay'])

            pg.write(str(pid))
            time.sleep(self.sleep_config['window_activate'])

            logger.debug("Selecting executable...")
            self.click_relative(windows[0], 100, 135)
            time.sleep(self.sleep_config['window_activate'])

            logger.debug("Selecting DLL...")
            self.click_relative(windows[0], 200, 135)
            time.sleep(self.sleep_config['window_activate'])

            logger.debug("Initiating injection...")
            self.click_relative(windows[0], 250, 15)
            time.sleep(self.sleep_config['window_activate'])

            injection_status = self.check_injection_status(pid=pid, injection_start_time=injection_start_time)
            
            logger.info("Attempting to terminate game process...")
            self.terminate_process(pid)
            
            try:
                logger.info("Closing DLL Injector window...")
                windows[0].close()
                time.sleep(self.sleep_config['window_close'])
            except Exception as e:
                logger.error(f"Error closing DLL Injector window: {str(e)}")
            
            if injection_status is True:
                logger.info("DLL injection completed successfully")
                return True
            elif injection_status is False:
                logger.error("DLL injection failed")
                return False
            elif injection_status == "timeout":
                logger.error("DLL injection timed out after 10 minutes")
                return False
            elif injection_status == "crashed":
                logger.error("DLL injection failed: game process crashed")
                return False
            else:
                logger.error("DLL injection status unknown")
                return False

        except Exception as e:
            logger.error(f"Error during injection process: {str(e)}")
            self.terminate_process(pid)
            try:
                if 'windows' in locals():
                    logger.info("Closing DLL Injector window after error...")
                    for window in windows:
                        window.close()
                    time.sleep(self.sleep_config['window_close'])
            except Exception as close_error:
                logger.error(f"Error closing DLL Injector window after error: {str(close_error)}")
            return False

    def check_and_click_start_game2(self, max_retries=5, retry_interval=2):
        """
        Check for and click the start_game2.png button if it appears
        Returns True if button was found and clicked, False otherwise
        """
        logger.info("Checking for Steam launch options...")
        for i in range(max_retries):
            try:
                start_game2_location = pg.locateOnScreen(self.start_game2_path, confidence=0.75)
                if start_game2_location:
                    logger.info("Found Steam launch options button")
                    start_game2_center = pg.center(start_game2_location)
                    pg.click(start_game2_center)
                    logger.info("Clicked Steam launch options button")
                    time.sleep(2)
                    return True
                logger.info(f"Steam launch options not found, retry {i+1}/{max_retries}")
                time.sleep(retry_interval)
            except Exception as e:
                logger.error(f"Error checking for Steam launch options: {str(e)}")
                time.sleep(retry_interval)
        
        logger.info("No Steam launch options found after maximum retries")
        return False

    def check_and_click_yunxu(self, max_retries=5, retry_interval=1):
        """
        Check for and click the yunxu (allow) button if it appears for firewall permissions
        Returns True if button was found and clicked, False otherwise
        """
        logger.info("Checking for firewall permission dialog...")
        for i in range(max_retries):
            try:
                yunxu_location = pg.locateOnScreen(self.yunxu_path, confidence=0.75)
                if yunxu_location:
                    logger.info("Found firewall permission button")
                    yunxu_center = pg.center(yunxu_location)
                    pg.click(yunxu_center)
                    logger.info("Clicked firewall permission button")
                    time.sleep(1)
                    return True
                logger.info(f"Firewall permission dialog not found, retry {i+1}/{max_retries}")
                time.sleep(retry_interval)
            except Exception as e:
                logger.error(f"Error checking for firewall permission: {str(e)}")
                time.sleep(retry_interval)
        
        logger.info("No firewall permission dialog found after maximum retries")
        return False

    def check_and_click_still_play_game(self, max_retries=5, retry_interval=1):
        """
        Check for and click the still_play_game.png button if it appears
        Returns True if button was found and clicked, False otherwise
        """
        logger.info("Checking for cloud save dialog...")
        for i in range(max_retries):
            try:
                still_play_location = pg.locateOnScreen(self.still_play_game_path, confidence=0.75)
                if still_play_location:
                    logger.info("Found cloud save dialog")
                    still_play_center = pg.center(still_play_location)
                    pg.click(still_play_center)
                    logger.info("Clicked 'still play game' button")
                    time.sleep(1)
                    return True
                logger.info(f"Cloud save dialog not found, retry {i+1}/{max_retries}")
                time.sleep(retry_interval)
            except Exception as e:
                logger.error(f"Error checking for cloud save dialog: {str(e)}")
                time.sleep(retry_interval)
        
        logger.info("No cloud save dialog found after maximum retries")
        return False

    def run_injection_process(self):
        """
        Full process: activate Steam window, detect playable button, click it, get game process, and inject DLL
        """
        # logger.info("Starting DLL injection process...")
        # if self.game_folder:
        #     logger.info(f"Using game folder: {self.game_folder}")
        # else:
        #     logger.info("No game folder specified, will detect any new process")
        
        # if not self.activate_steam_window():
        #     logger.error("Failed to activate Steam window")
        #     return False
        
        # logger.info("Recording processes before game launch...")
        # before_processes = self.get_running_processes()
        
        # if not self.detect_and_click_playable():
        #     logger.error("Failed to find and click playable button")
        #     return False
        
        # logger.info("Checking for Steam launch options...")
        # self.check_and_click_start_game2()
        
        # logger.info("Checking for cloud save dialog...")
        # self.check_and_click_still_play_game()
        
        logger.info("Checking for firewall permission dialog...")
        self.check_and_click_yunxu()
        
        logger.info(f"Waiting for game to launch...")
        for i in range(self.sleep_config['game_launch'], 0, -1):
            logger.info(f"Waiting for game launch... {i} seconds remaining")
            time.sleep(1)
        
        logger.info("Recording processes after game launch...")
        after_processes = self.get_running_processes()
        
        game_process = self.find_new_game_process(before_processes, after_processes)
        
        if not game_process:
            logger.error("Failed to detect game process")
            return False
        
        logger.info("Minimizing all windows (Win + D)...")
        pg.hotkey('win', 'd')
        time.sleep(self.sleep_config['minimize_wait'])
        
        pid = game_process["pid"]
        if self.inject_dll(pid):
            logger.info(f"Successfully injected DLL into {game_process['name']} (PID: {pid})")
            return True
        else:
            logger.error(f"Failed to inject DLL into {game_process['name']} (PID: {pid})")
            return False


if __name__ == "__main__":
    import sys
    
    game_folder = None
    dll_injector_path = "E:\\DLLInjector.lnk"
    
    if len(sys.argv) > 1:
        game_folder = sys.argv[1]
    if len(sys.argv) > 2:
        dll_injector_path = sys.argv[2]
    
    logger.info(f"Starting DLL injection with game_folder: {game_folder}, dll_injector_path: {dll_injector_path}")
    injector = DLLInjector(game_folder, dll_injector_path)
    injector.run_injection_process()
