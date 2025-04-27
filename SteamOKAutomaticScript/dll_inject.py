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
from config import get_config, load_config
from tqdm import tqdm
from image_utils import ImageDetector
from window_utils import activate_window_by_title, activate_window_by_typing

# Disable PyAutoGUI fail-safe (not recommended for safety reasons)
pg.FAILSAFE = False

logger = setup_logging()

class DLLInjector:
    def __init__(self):
        # Load configuration
        self.config = get_config()
        
        # Initialize parameters from config
        self.game_folder = self.config['paths']['steam_apps_common']
        self.dll_injector_path = self.config['paths']['dll_injector_path']
        
        # Image paths and confidence levels from config
        dll_config = self.config['dll_injection']
        
        # Set up image paths with confidence levels for playable button
        playable_image = os.path.join(os.path.dirname(__file__), dll_config['images']['playable_image'])
        playable_confidence = dll_config['images']['playable_confidence']
        start_game_image = os.path.join(os.path.dirname(__file__), dll_config['images']['start_game_image'])
        start_game_confidence = dll_config['images']['start_game_confidence']
        
        self.playable_image_paths = [
            (playable_image, playable_confidence),
            (start_game_image, start_game_confidence)
        ]
        
        # Set up paths for other dialog images
        self.start_game2_path = os.path.join(os.path.dirname(__file__), dll_config['images']['start_game2_image'])
        self.comfirm_vr_path = os.path.join(os.path.dirname(__file__), dll_config['images']['comfirm_vr_image'])
        self.yunxu_path = os.path.join(os.path.dirname(__file__), dll_config['images']['yunxu_image'])
        self.still_play_game_path = os.path.join(os.path.dirname(__file__), dll_config['images']['still_play_game_image'])
        
        # Load sleep configuration from config
        self.sleep_config = dll_config['sleep_timings']
        
        # Get system process keywords for filtering
        self.system_process_keywords = dll_config['process_detection']['system_process_keywords']
        
        # Base log directory
        self.base_log_directory = dll_config['paths']['log_directory']
        
        # Retry counts
        self.retry_counts = dll_config['retry_counts']
        
        # Initialize image detector
        self.image_detector = ImageDetector(self.config)
        
        # Track the latest log directory
        self.latest_log_dir = None
        
        logger.info(f"DLLInjector initialized with game_folder: {self.game_folder}")
        logger.info(f"DLL injector path: {self.dll_injector_path}")
        
    def activate_steam_window(self):
        """Activate Steam window and bring it to the front"""
        try:
            # Try to activate Steam using the window_utils module
            return activate_window_by_title("Steam", self.sleep_config)
            
        except Exception as e:
            logger.error(f"Failed to activate Steam window with window_utils: {str(e)}")
            # Fall back to the typing method if the above fails
            return activate_window_by_typing("Steam", self.sleep_config)
        
    def detect_and_click_playable(self):
        """
        Detect the 'playable.png' image on screen and click it.
        Returns True if successful, False otherwise.
        """
        max_retries = self.retry_counts['playable_detection']
        retry_interval = self.sleep_config['retry_interval']
        
        logger.info("Searching for playable button...")
        
        # Try each playable image in sequence
        for image_path, confidence in self.playable_image_paths:
            result = self.image_detector.check_and_click_image(
                image_path=image_path,
                confidence=confidence,
                max_retries=max_retries,
            )
            if result:
                return True
                
        logger.error("Failed to find playable button after trying all images")
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
        
        game_processes = []
        for name, exe, pid in new_processes:
            if not any(keyword in name.lower() for keyword in self.system_process_keywords) and name.lower().endswith('.exe'):
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

    def get_latest_log_directory(self, base_path, injection_start_time):
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
            
            # Store the latest log directory as a class attribute
            self.latest_log_dir = latest_dir
            
            return latest_dir

        except Exception as e:
            logger.error(f"Error finding latest log directory: {str(e)}")
            return None

    def check_injection_status(self, pid, check_interval=None, injection_start_time=None):
        """
        Check the injection status by monitoring log files
        Returns: 
            - True if injection succeeded
            - False if injection failed
            - "timeout" if injection took too long
            - "crashed" if game process ended unexpectedly
        """
        check_interval = check_interval or self.sleep_config['injection_check']
        start_time = time.time()
        base_log_path = self.base_log_directory
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

    def get_usmap_path(self, log_dir):
        """
        Get the USMap path from the injection log directory
        Returns the usmap path if found, None otherwise
        """

        # Try to find the USMap in the parent directory structure (sibling to log dir)
        try:
            # Get the parent directory of the log directory
            parent_dir = os.path.dirname(os.path.dirname(log_dir))
            logger.info(f"Checking parent directory: {parent_dir}")
            
            # Get the injection timestamp from the log directory name
            log_dir_name = os.path.basename(log_dir)
            injection_time = datetime.strptime(log_dir_name, "%Y%m%d_%H%M%S")
            
            # Find all timestamp directories under the parent directory
            timestamp_dirs = []
            for item in os.listdir(parent_dir):
                item_path = os.path.join(parent_dir, item)
                if os.path.isdir(item_path):
                    try:
                        # Try to parse the directory name as a timestamp
                        dir_time = datetime.strptime(item, "%Y%m%d_%H%M%S")
                        # Only consider directories created after injection
                        if dir_time >= injection_time:
                            timestamp_dirs.append((dir_time, item_path))
                    except ValueError:
                        # Not a timestamp directory, skip
                        continue
            
            if timestamp_dirs:
                # Sort by timestamp, most recent first
                timestamp_dirs.sort(reverse=True)
                
                # Check each directory for a Mappings folder with usmap files
                for _, dir_path in timestamp_dirs:
                    mappings_dir = os.path.join(dir_path, "Mappings")
                    
                    if os.path.exists(mappings_dir) and os.path.isdir(mappings_dir):
                        logger.info(f"Found Mappings directory: {mappings_dir}")
                        
                        # Look for .usmap files in the Mappings directory
                        usmap_files = glob.glob(os.path.join(mappings_dir, "*.usmap"))
                        
                        if usmap_files:
                            usmap_path = usmap_files[0]
                            logger.info(f"Found USMap file in Mappings directory: {usmap_path}")
                            return usmap_path
        except Exception as e:
            logger.error(f"Error searching for USMap in parent directory structure: {str(e)}")
        
        # If we get here, no usmap path was found
        logger.error(f"No USMap file found for the injection")
        return None


    def inject_dll(self, pid):
        """
        Inject DLL by directly interacting with DLL Injector GUI
        Returns True if successful, False if failed, or the USMap path if injection succeeded
        """
        injection_start_time = datetime.now()
        log_dir = None
        
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
            log_dir = self.get_latest_log_directory(self.base_log_directory, injection_start_time)
            
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
                # Get USMap path if injection was successful
                usmap_path = self.get_usmap_path(log_dir) if log_dir else None
                if usmap_path:
                    logger.info(f"USMap successfully generated at: {usmap_path}")
                    return usmap_path
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

        
    def run_injection_process(self):
        """
        Full process: activate Steam window, detect playable button, click it, get game process, and inject DLL
        Returns True if successful, False if failed, or the USMap path if injection succeeded
        """
        logger.info("Starting DLL injection process...")
        if self.game_folder:
            logger.info(f"Using game folder: {self.game_folder}")
        else:
            logger.info("No game folder specified, will detect any new process")
        
        if not self.activate_steam_window():
            logger.error("Failed to activate Steam window")
            return False
        
        logger.info("Recording processes before game launch...")
        before_processes = self.get_running_processes()
        
        if not self.detect_and_click_playable():
            logger.error("Failed to find and click playable button")
            return False
        
        # Define dialogs to check in order
        dialogs_to_check = [
            {"name": "Steam launch options", "image_path": self.start_game2_path},
            {"name": "VR launch options", "image_path": self.comfirm_vr_path},
            {"name": "cloud save dialog", "image_path": self.still_play_game_path},
            {"name": "firewall permission dialog", "image_path": self.yunxu_path}
        ]
        
        # Check for and handle various dialogs
        for dialog in dialogs_to_check:
            logger.info(f"Checking for {dialog['name']}...")
            self.image_detector.check_and_click_image(
                image_path=dialog['image_path'],
                max_retries=5,
            )
        
        logger.info(f"Waiting for game to launch...")
        game_launch_time = self.sleep_config['game_launch']
        for _ in tqdm(range(game_launch_time), desc="Waiting for game launch", unit="s"):
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
        injection_result = self.inject_dll(pid)
        
        if injection_result is True:
            logger.info(f"Successfully injected DLL into {game_process['name']} (PID: {pid})")
            return True
        elif isinstance(injection_result, str):  # If result is a string, it's the USMap path
            logger.info(f"Successfully injected DLL into {game_process['name']} (PID: {pid}) and generated USMap at: {injection_result}")
            return injection_result
        else:
            logger.error(f"Failed to inject DLL into {game_process['name']} (PID: {pid})")
            return False


if __name__ == "__main__":
    import sys
    
    # Load configuration
    config = load_config()
    
    # Parse command line arguments if any
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        logger.info(f"Loading custom configuration from: {config_path}")
        config = load_config(config_path)

    # Create and run injector
    logger.info("Starting DLL injection process")
    injector = DLLInjector()
    
    result = injector.run_injection_process()
    logger.info(f"DLL injection process {'successful' if result else 'failed'}")
    print(f"DLL injection {'successful' if result else 'failed'}")
