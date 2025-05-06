import os
import shutil
import subprocess
import requests
import zipfile
import time
import logging
from pathlib import Path
import psutil
import argparse

import time
import logging
import argparse
import os
from datetime import datetime
import pyautogui as pg
from logger import setup_logging
from game_install_controller import SteamOKController
from dll_inject import DLLInjector
from config import load_config, get_config
from csv_logger import GameStatusLogger
from debug_screenshot_manager import DebugScreenshotManager
from task_status_logger import TaskStatusLogger
from upload_usmap import upload_usmap
import re
import threading


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("zip_processor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ZipProcessor")

def download_zip(task, mounted_folder, zip_name, output_path):
    """Copy the client package zip file from mounted folder
    
    Args:
        task: The task dictionary containing the task ID
        mounted_folder: Path to the mounted folder containing zip files
        zip_name: Name of the zip file to copy
        output_path: Path where to save downloaded files
    """
    try:
        task_id = task['id']
        
        # Create downloads directory if it doesn't exist
        download_dir = Path(output_path)
        download_dir.mkdir(exist_ok=True)
        
        # Use the provided zip name directly
        source_path = os.path.join(mounted_folder, zip_name)
        dest_path = str(download_dir / zip_name)
        
        # Set download path in task dictionary
        task['zip_path'] = dest_path
        
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

def extract_zip(task, output_path, zip_name):
    """Extract the downloaded zip file"""
    try:
        zip_path = os.path.join(output_path, zip_name)
        extract_dir = Path(f"extracted_{task['id']}")
        extract_dir.mkdir(exist_ok=True)
        
        task['extract_folder'] = str(extract_dir)
        
        logger.info(f"Extracting {zip_path} to {extract_dir}")
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        logger.info(f"Extraction completed for task {task['id']}")
        return True
    except Exception as e:
        logger.error(f"Failed to extract zip for task {task['id']}: {str(e)}")
        return False

def delete_zip_and_extract_folder(task, output_path, zip_name):
    """Clean up downloaded zip and extracted folder"""
    try:
        zip_path = os.path.join(output_path, zip_name)
        # Remove the zip file
        if os.path.exists(zip_path):
            os.remove(zip_path)
            logger.info(f"Deleted zip file: {zip_path}")
        
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
                    if 'prereqsetup' in file_lower or 'crashreportclient' in file_lower:
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

def inject(pid):
    """Inject DLL into the process"""
    try:
        if not pid:
            logger.error("No valid PID provided for injection")
            return None
        
        # Check if process is still running
        if not psutil.pid_exists(pid):
            logger.error(f"Process with PID {pid} no longer exists")
            return None
        
        logger.info(f"Injecting DLL into process with PID: {pid}")
        
        # Path to your injector tool
        injector_path = "path/to/injector.exe"  # Replace with actual path
        dll_path = "path/to/injection.dll"      # Replace with actual path
        
        # Run the injector
        result = subprocess.run([injector_path, str(pid), dll_path], 
                                capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Injection failed: {result.stderr}")
            return None
        
        logger.info(f"Injection successful: {result.stdout}")
        
        # Look for USMap path in the output
        # This depends on your injector's output format
        usmap_path = None
        # Parse the output to find usmap_path
        
        return usmap_path
    except Exception as e:
        logger.error(f"Injection error: {str(e)}")
        return None

def upload_usmap(task):
    """Upload the USMap file to server"""
    try:
        if 'usmap_path' not in task or not task['usmap_path']:
            logger.error(f"No USMap path available for task {task['id']}")
            return False
        
        usmap_path = task['usmap_path']
        task_id = task['id']
        
        logger.info(f"Uploading USMap for task {task_id}: {usmap_path}")
        
        # API endpoint for upload
        upload_url = f"https://api-endpoint.example.com/upload/{task_id}"  # Replace with actual API endpoint
        
        with open(usmap_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(upload_url, files=files)
            response.raise_for_status()
        
        logger.info(f"USMap upload successful for task {task_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload USMap for task {task['id']}: {str(e)}")
        return False

def process_task(task_id, mounted_folder=None, zip_name=None, output_path="downloads"):
    """Process a single task
    
    Args:
        task_id: The ID of the task to process
        mounted_folder: Path to the mounted folder containing zip files
        zip_name: Name of the zip file to use
        output_path: Path where to save downloaded files
    """
    task = {'id': task_id}
    logger.info(f"Processing task ID: {task_id}")
    
    try:
        # Step 1: Download zip
        if not download_zip(task, mounted_folder, zip_name, output_path):
            logger.error(f"Aborting task {task_id} due to download failure")
            return False
        
        # Step 2: Extract zip
        if not extract_zip(task, output_path, zip_name):
            logger.error(f"Aborting task {task_id} due to extraction failure")
            delete_zip_and_extract_folder(task, output_path, zip_name)
            return False
        
        # Step 3: Find executables
        exe_paths = find_exe(task['extract_folder'])
        if not exe_paths:
            logger.error(f"Aborting task {task_id} due to missing executable")
            delete_zip_and_extract_folder(task, output_path, zip_name)
            return False
        
        # Step 4-7: Try each executable with complete workflow
        success = False
        for exe_path in exe_paths:
            logger.info(f"===== Attempting full workflow with executable: {exe_path} =====")
            
            # Step 4: Run the executable
            logger.info(f"Step 4: Running executable: {exe_path}")
            pid = run_exe(exe_path)
            if not pid:
                logger.warning(f"Failed to run executable: {exe_path}, trying next if available")
                continue
            
            logger.info(f"Successfully started executable: {exe_path} with PID: {pid}")
            
            # Step 5: Inject DLL
            logger.info(f"Step 5: Injecting DLL into process: {pid}")
            usmap_path = inject(pid)
            if not usmap_path:
                logger.warning(f"DLL injection failed for executable: {exe_path}, trying next if available")
                continue
            
            task['usmap_path'] = usmap_path
            logger.info(f"DLL injection successful, USMap path: {usmap_path}")
            
            # Step 6: Upload USMap
            logger.info(f"Step 6: Uploading USMap file")
            if not upload_usmap(task):
                logger.warning(f"USMap upload failed for executable: {exe_path}, trying next if available")
                continue
            
            logger.info(f"USMap upload successful for executable: {exe_path}")
            
            # If we reach here, all steps were successful
            success = True
            logger.info(f"Full workflow successful with executable: {exe_path}")
            break
        
        # Step 7: Clean up regardless of success
        logger.info(f"Step 7: Cleaning up")
        delete_zip_and_extract_folder(task, output_path, zip_name)
        
        if success:
            logger.info(f"Task {task_id} completed successfully")
            return True
        else:
            logger.error(f"Task {task_id} failed - all executables failed to complete the workflow")
            return False
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        delete_zip_and_extract_folder(task, output_path, zip_name)
        return False

def main():
    """Process all tasks in the specified range"""
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Process tasks for USMap generation')
    parser.add_argument('--start', type=int, default=174, help='Starting task ID')
    parser.add_argument('--end', type=int, default=376, help='Ending task ID')
    parser.add_argument('--mounted-folder', type=str, required=True, help='Path to the mounted folder containing zip files')
    parser.add_argument('--zip-name', type=str, required=True, help='Name of the zip file to use')
    parser.add_argument('--output-path', type=str, default='downloads', help='Path where to save downloaded files')
    parser.add_argument('--delay', type=int, default=5, help='Delay in seconds between processing tasks')
    
    args = parser.parse_args()
    start_id = args.start
    end_id = args.end
    mounted_folder = args.mounted_folder
    zip_name = args.zip_name
    output_path = args.output_path
    delay = args.delay
    
    logger.info(f"Starting batch processing for task IDs {start_id} to {end_id}")
    logger.info(f"Using mounted folder: {mounted_folder}")
    logger.info(f"Using zip file: {zip_name}")
    logger.info(f"Using output path: {output_path}")
    
    for task_id in range(start_id, end_id + 1):
        logger.info(f"=== Processing task ID: {task_id} ===")
        success = process_task(task_id, mounted_folder, zip_name, output_path)
        
        if success:
            logger.info(f"Task {task_id} completed successfully")
        else:
            logger.error(f"Task {task_id} failed")
        
        # Add a delay between tasks to avoid overwhelming resources
        logger.info(f"Waiting {delay} seconds before next task...")
        time.sleep(delay)
    
    logger.info("Batch processing completed")

if __name__ == '__main__':
    main()

