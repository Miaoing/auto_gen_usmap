import os
import shutil
import subprocess
import requests
import zipfile
import time
import logging
import argparse
import re
import threading
from pathlib import Path
from datetime import datetime

# Third-party imports
import psutil
import pyautogui as pg
from tqdm import tqdm

# Local imports
from logger import setup_logging
from game_install_controller import SteamOKController
from dll_inject import DLLInjector
from config import load_config, get_config
from csv_logger import GameStatusLogger
from debug_screenshot_manager import DebugScreenshotManager
from task_status_logger import TaskStatusLogger
from upload_usmap import upload_usmap

# Load configuration first
config = load_config()
logger = setup_logging()

def download_zip(task, source_path, output_path):
    """Copy the client package zip file from mounted folder
    
    Args:
        task: The task dictionary containing the task ID
        source_path: Path to the source zip file
        output_path: Path where to save downloaded files
    """
    try:
        task_id = task['id']
        
        # Create downloads directory if it doesn't exist
        download_dir = Path(output_path)
        download_dir.mkdir(exist_ok=True)
        zip_name = os.path.basename(source_path)

        # Use the provided zip name directly
        dest_path = str(download_dir / zip_name)

        if os.path.exists(dest_path):
            logger.info(f"文件已存在: {dest_path}")
            return True
        # Set download path in task dictionary
        logger.info(f"Copying package for task ID {task_id} from mounted folder")
        logger.info(f"Using file: {source_path}")
        
        # Check if source file exists
        if not os.path.exists(source_path):
            logger.error(f"Source file does not exist: {source_path}")
            return False
        
        # Copy the file and measure time
        start_time = time.time()
        shutil.copy2(source_path, dest_path)
        end_time = time.time()
        copy_time = end_time - start_time
        
        # Get file size for reporting
        file_size = os.path.getsize(dest_path) / (1024 * 1024)  # Size in MB
        
        logger.info(f"File copy completed: {dest_path}")
        logger.info(f"Copy statistics: {file_size:.2f} MB in {copy_time:.2f} seconds ({file_size/copy_time:.2f} MB/s)")
        return True
    except Exception as e:
        logger.error(f"Failed to copy zip for task {task['id']}: {str(e)}")
        return False

def extract_zip(task, zip_path):
    """Extract the downloaded zip file"""
    try:
        extract_dir = Path(zip_path.replace('.zip', ''))
        if os.path.exists(extract_dir):
            logger.info(f"文件已存在: {extract_dir}")
            return True
        extract_dir.mkdir(exist_ok=True)
        
        logger.info(f"Extracting {zip_path} to {extract_dir}")
        
        # Measure extraction time
        start_time = time.time()
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Calculate extraction time
        end_time = time.time()
        extract_time = end_time - start_time
        
        # Get file size for reporting
        zip_size = os.path.getsize(zip_path) / (1024 * 1024)  # Size in MB
        
        logger.info(f"Extraction completed for task {task['id']}")
        logger.info(f"Extraction statistics: {zip_size:.2f} MB in {extract_time:.2f} seconds ({zip_size/extract_time:.2f} MB/s)")
        
        # Store the extract folder in the task for later use
        task['extract_folder'] = str(extract_dir)
        
        return True
    except Exception as e:
        logger.error(f"Failed to extract zip for task {task['id']}: {str(e)}")
        return False

def delete_zip_and_extract_folder(task, output_zip_path):
    """Clean up downloaded zip and extracted folder"""
    try:
        extract_folder = output_zip_path.replace('.zip', '')
        if os.path.exists(extract_folder):
            shutil.rmtree(extract_folder)
            logger.info(f"Deleted extract folder: {extract_folder}")
        # Remove the zip file
        if os.path.exists(output_zip_path):
            os.remove(output_zip_path)
            logger.info(f"Deleted zip file: {output_zip_path}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to clean up files for task {task['id']}: {str(e)}")
        return False

def find_exe(extract_folder):
    """Find executable file in the extracted folder
    
    Prioritizes executables in the following order:
    1. Contains 'shipping' in the name
    2. Any other executable
    
    Excludes executables containing 'PrereqSetup' or 'CrashReportClient'
    
    Returns a list of executables sorted by priority
    """
    try:
        # Lists to store found executables by priority
        shipping_exes = []
        other_exes = []
        
        # Find all executables
        logger.info(f"Searching for executables in {extract_folder}")
        for root, _, files in os.walk(extract_folder):
            for file in files:
                if file.lower().endswith('.exe'):
                    exe_path = os.path.join(root, file)
                    file_lower = file.lower()
                    
                    # Skip excluded executables
                    if 'prereqsetup' in file_lower or 'crashreportclient' in file_lower or '_commonredist' in file_lower or 'setup' in file_lower:
                        logger.info(f"Skipping excluded executable: {exe_path}")
                        continue
                    
                    # Prioritize shipping executables
                    if 'shipping' in file_lower:
                        logger.info(f"Found shipping executable: {exe_path}")
                        shipping_exes.append(exe_path)
                    else:
                        logger.info(f"Found other executable: {exe_path}")
                        other_exes.append(exe_path)
        
        # Combine lists with shipping executables first
        prioritized_exes = shipping_exes + other_exes
        
        if prioritized_exes:
            logger.info(f"Found {len(prioritized_exes)} potential executables")
            for exe in prioritized_exes:
                logger.info(f"  - {exe}")
            return prioritized_exes
        
        # No valid executable found
        logger.error(f"No suitable executable found in {extract_folder}")
        return []
    except Exception as e:
        logger.error(f"Error while searching for executable: {str(e)}")
        return []

def run_exe(exe_path):
    """Run the executable and return the process ID"""
    try:
        if not exe_path or not os.path.exists(exe_path):
            logger.error(f"Invalid executable path: {exe_path}")
            return None
        
        logger.info(f"Launching executable: {exe_path}")
        
        # Start the process
        process = subprocess.Popen([exe_path])
        pid = process.pid
        
        logger.info(f"Process started with PID: {pid}")
        
        # Give the process some time to initialize
        time.sleep(10)
        
        # Check if process is still running
        if process.poll() is not None:
            logger.error(f"Process {pid} exited prematurely with code {process.returncode}")
            return None
        
        return pid
    except Exception as e:
        logger.error(f"Failed to run executable: {str(e)}")
        return None


def check_anticheat(extract_folder):
    """Check for anti-cheat systems in the extracted folder
    
    Args:
        extract_folder: Path to the folder containing extracted files
        
    Returns:
        bool
    """
    try:
        logger.info(f"Scanning for anti-cheat systems in: {extract_folder}")
        
        # Check for EasyAntiCheat folder
        eac_folder = os.path.join(extract_folder, 'EasyAntiCheat')
        if os.path.exists(eac_folder) and os.path.isdir(eac_folder):
            logger.warning(f"⚠️ EasyAntiCheat folder detected in: {extract_folder}")
            return True
        
        # No anti-cheat detected
        logger.info("No anti-cheat systems detected")
        return False
    except Exception as e:
        logger.error(f"Error checking for anti-cheat: {str(e)}")
        # If there's an error, we'll continue anyway but log it
        return False
def batch_process_tasks(injector, csv_logger, task_logger, task_limit, retry_delay, output_path, base_url):
    unprocessed_tasks = task_logger.get_unprocessed_tasks(limit=task_limit)
    processed_count = 0
    if not unprocessed_tasks:
        logger.info("没有发现未处理的任务，等待下一次检查")
        return 0
    logger.info(f"发现{len(unprocessed_tasks)}个未处理的任务，开始处理")
    for task in unprocessed_tasks:
        task_id = task['id']
        zip_path = task['Zip_Path']
        game_name = task['Steam_Game_Name']

        logger.info(f"开始处理任务 {task_id}: {game_name}")

        # Mark task as processing
        task_logger.mark_task_processing(task_id)
        if process_task(task_id, zip_path, output_path, base_url, injector, csv_logger, task_logger, game_name):
            logger.info(f"任务 {task_id} 处理成功, 删除相关文件")
            output_zip_path = os.path.join(output_path, os.path.basename(zip_path))
            delete_zip_and_extract_folder(task, output_zip_path)
        processed_count += 1
    return processed_count

def process_task(task_id, zip_path, output_folder, base_url, injector, csv_logger, task_logger, game_name):
    """Process a single task
    
    Args:
        task_id: The ID of the task to process
        zip_path: Path to the zip file to process
        output_folder: Path where to save downloaded files
    """
    task = {'id': task_id}
    logger.info(f"Processing task ID: {task_id}")
    
    zip_name = os.path.basename(zip_path)
    output_zip_path = os.path.join(output_folder, zip_name)
    try:
        # Step 1: Download zip
        if not download_zip(task, zip_path, output_folder):
            logger.error(f"Aborting task {task_id}: {zip_name} due to download failure")
            return False
        
        # Step 2: Extract zip
        if not extract_zip(task, output_zip_path):
            logger.error(f"Aborting task {task_id}: {zip_name} due to extraction failure")
            return False
        
        # Step 2.5: Check for anti-cheat systems
        logger.info("Step 2.5: Checking for anti-cheat systems")
        extract_folder = f'{output_folder}/{zip_name.replace('.zip', '')}'
        if check_anticheat(extract_folder):
            logger.error(f"Aborting task {task_id}: {zip_name} due to anti-cheat detection")
            return False
        
        # Step 3: Find executables
        exe_paths = find_exe(extract_folder)
        if not exe_paths:
            logger.error(f"Aborting task {task_id}: {zip_name} due to missing executable")
            return False
        
        # Step 4-7: Try each executable with complete workflow
        success = False
        max_injection_retries = 3
        for exe_path in exe_paths:
            logger.info(f"===== Attempting full workflow with executable: {exe_path} =====")
            # Initialize inject_result to prevent "cannot access local variable" error
            inject_result = {"success": False, "error_type": "not_attempted", "data": None}
            for attempt in range(max_injection_retries):
                logger.info(f"Attempt {attempt + 1} of {max_injection_retries}...")
                # Step 4: Run the executable
                logger.info(f"Step 4: Running executable: {exe_path}")
                pid = run_exe(exe_path)
                if not pid:
                    logger.warning(f"Failed to run executable: {exe_path}, trying next if available")
                    continue
                
                logger.info(f"Successfully started executable: {exe_path} with PID: {pid}")
                
                # Step 5: Inject DLL
                logger.info(f"Step 5: Injecting DLL into process: {pid}")
                logger.info(f"Game {game_name} is playable, starting DLL injection process...")
                injector.game_folder = extract_folder
                inject_result = injector.run_injection_process(launch_from_steam=False, pid=pid)
                if inject_result["success"]:
                    break
                else:
                    logger.error(f"Injection failed: {inject_result['error_type']}")
            # Get the latest log directory if available
            log_dir = None
            if hasattr(injector, 'latest_log_dir') and injector.latest_log_dir:
                log_dir = injector.latest_log_dir
                logger.info(f"Injection log directory for {game_name}: {log_dir}")
            
            
            if inject_result["success"]:
                usmap_path = inject_result["data"]
                if usmap_path:  # If USMap path was found
                    logger.info(f"✅DLL injection successful for game: {game_name}, 📁 USMap path: {usmap_path}")
                    csv_logger.log_injection_success(game_name, usmap_path, log_dir)

                    # Mark task as completed and store USMAP path
                    task_logger.mark_task_completed(task_id, usmap_path)

                    # Attempt to upload USMAP file
                    upload_result = upload_usmap(task_id, usmap_path, base_url=base_url)

                    if upload_result:
                        logger.info(f"Successfully uploaded USMAP for task {task_id}")
                    else:
                        logger.error(f"Failed to upload USMAP for task {task_id}")
                        
                    print(f"{game_name}: ✅可玩, 💉已注入DLL, 📁USMap路径: {usmap_path}")
                                # If we reach here, all steps were successful
                    success = True
                    logger.info(f"Full workflow successful with executable: {exe_path}")
                    break
                else:
                    logger.warning(f"DLL injection failed for executable: {exe_path}, trying next if available")
                    continue
            else:
                error_type = inject_result["error_type"]
                error_data = inject_result["data"] if inject_result["data"] else "Unknown error"

                if error_type == "timeout":
                    logger.error(f"DLL injection timed out for game: {game_name}")
                    csv_logger.log_injection_timeout(game_name, log_dir)
                    task_logger.mark_task_error(task_id, "DLL injection timed out")
                    print(f"{game_name}: 可玩, DLL注入超时")
                elif error_type == "game_crashed":
                    logger.error(f"Game crashed during injection: {game_name}")
                    csv_logger.log_injection_crash(game_name, "Game process crashed", log_dir)
                    task_logger.mark_task_error(task_id, "Game crashed during DLL injection")
                    print(f"{game_name}: 可玩, DLL注入时游戏崩溃")
                else:
                    logger.error(f"DLL injection failed for game: {game_name}, error type: {error_type}, details: {error_data}")
                    csv_logger.log_injection_crash(game_name, f"Injection failed: {error_type}", log_dir)
                    task_logger.mark_task_error(task_id, f"DLL injection failed: {error_type}")
                    print(f"{game_name}: 可玩, 注入DLL失败 ({error_type})")
                logger.warning(f"DLL injection failed for executable: {exe_path}, trying next if available")
                continue
                
        
        if success:
            logger.info(f"Task {task_id} completed successfully")
            return True
        else:
            logger.error(f"Task {task_id} failed - all executables failed to complete the workflow")
            return False

    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        csv_logger.log_download_error(game_name, f"处理游戏时出错: {str(e)}")
        task_logger.mark_task_error(task_id, f"处理游戏时出错: {str(e)}")
        return False

def main():
    """Process all tasks in the specified range"""
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Process tasks for USMap generation')
    parser.add_argument('--start', type=int, default=179, help='Starting task ID')
    parser.add_argument('--end', type=int, default=375, help='Ending task ID')
    parser.add_argument('--mounted-folder', type=str, default=r'G:/', help='Path to the mounted folder containing zip files')
    parser.add_argument('--output-path', type=str, default=r'F:/extracted', help='Path where to save downloaded files')
    parser.add_argument('--delay', type=int, default=5, help='Delay in seconds between processing tasks')
    parser.add_argument('--base_url', type=str, default='http://30.160.52.57:8080', help='Base URL for the server')
    parser.add_argument('--webhook_url', default='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=d2ae19b3-0efd-44ef-b1f8-c6af76b113b5', help='URL for webhook notifications')
    parser.add_argument('--csv_path', type=str, default='task_status_local_games.csv', help='Path to the CSV file for task status')
    parser.add_argument('--check_interval', type=int, default=30, help='Interval in seconds between task checks when idle (default: 300)')
    parser.add_argument('--task_limit', type=int, default=5, help='Maximum number of tasks to process per run')

    args = parser.parse_args()
    start_id = args.start
    end_id = args.end
    mounted_folder = args.mounted_folder
    output_path = args.output_path
    delay = args.delay
    webhook_url = args.webhook_url
    task_limit = args.task_limit
    base_url = args.base_url
    
    # Initialize the CSV logger
    csv_logger = GameStatusLogger(webhook_url=webhook_url)
    logger.info(f"CSV logging enabled to: {csv_logger.get_csv_path()}")

    # Initialize the task status logger
    task_logger = TaskStatusLogger(webhook_url=webhook_url, base_url=args.base_url, csv_path=args.csv_path)
    logger.info(f"Task status logging enabled to: {task_logger.get_csv_path()}")
    
    # Run the normal game installation process
    try:
        logger.info("破解游戏脚本启动中...")
        injector = DLLInjector()
        
        
        # Setup a thread for periodic task data pulling
        def pull_task_data_periodically():
            while True:
                try:
                    new_tasks = task_logger.pull_task_data(task_id_list=None)
                    if new_tasks and len(new_tasks) > 0:
                        logger.info(f"拉取到{len(new_tasks)}个新任务:")
                    # 使用任务记录器内置的间隔控制，所以这里只需要稍等即可
                    time.sleep(30)  # Brief wait, the task_logger will handle the actual pull interval
                except Exception as e:
                    logger.error(f"任务拉取线程出错: {str(e)}")
                    time.sleep(60)  # Wait a minute before r

        # Start the periodic task pull thread
        pull_thread = threading.Thread(target=pull_task_data_periodically, daemon=True)
        pull_thread.start()

        # task_logger.pull_task_data(force=True)
        for _ in tqdm(range(30), desc="Initial startup delay", unit="sec"):
            time.sleep(1)
        # Main processing loop - keep running until interrupted
        retry_delay = config['timing']['retry_delay']
        check_interval = args.check_interval

        while True:
            start_time = time.time()
            print(f"开始处理任务")
            processed = batch_process_tasks(injector, csv_logger, task_logger, task_limit, retry_delay, output_path, base_url)
            # If we processed tasks, don't wait as long before checking again
            if processed > 0:
                logger.info(f"本次处理了 {processed} 个任务，30秒后检查新任务")
                time.sleep(30)  # Short wait after processing tasks
            else:
                # Calculate how long to wait - if processing took a long time, we might not need to wait at all
                elapsed = time.time() - start_time
                wait_time = max(0, check_interval - elapsed)
                
                if wait_time > 0:
                    logger.info(f"没有任务需要处理，等待 {wait_time:.0f} 秒后重新检查")
                    # Sleep in smaller increments to allow for cleaner shutdown
                    sleep_increment = 10  # 10 seconds
                    remaining = wait_time
                    while remaining > 0:
                        time.sleep(min(remaining, sleep_increment))
                        remaining -= sleep_increment
    except KeyboardInterrupt:
        logger.info("收到中断信号，脚本正在退出...")
        print("脚本已中断")
    except Exception as e:
        logger.error(f"应用程序错误: {e}")
        print(f"错误: {e}")
    finally:
        logger.info("脚本结束")
if __name__ == '__main__':
    main()

