import os
import shutil
import subprocess
import requests
import zipfile
import time
import logging
from pathlib import Path
import psutil

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

def download_zip(task):
    """Download the client package zip file"""
    try:
        task_id = task['id']
        download_url = f"https://api-endpoint.example.com/download/{task_id}"  # Replace with actual API endpoint
        
        # Create downloads directory if it doesn't exist
        download_dir = Path("downloads")
        download_dir.mkdir(exist_ok=True)
        
        # Set download path
        task['zip_path'] = str(download_dir / f"client_package_{task_id}.zip")
        
        logger.info(f"Downloading package for task ID {task_id}")
        
        # Download the file
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        
        with open(task['zip_path'], 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Download completed: {task['zip_path']}")
        return True
    except Exception as e:
        logger.error(f"Failed to download zip for task {task['id']}: {str(e)}")
        return False

def extract_zip(task):
    """Extract the downloaded zip file"""
    try:
        zip_path = task['zip_path']
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

def delete_zip_and_extract_folder(task):
    """Clean up downloaded zip and extracted folder"""
    try:
        # Remove the zip file
        if 'zip_path' in task and os.path.exists(task['zip_path']):
            os.remove(task['zip_path'])
            logger.info(f"Deleted zip file: {task['zip_path']}")
        
        # Remove the extracted folder
        if 'extract_folder' in task and os.path.exists(task['extract_folder']):
            shutil.rmtree(task['extract_folder'])
            logger.info(f"Deleted extracted folder: {task['extract_folder']}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to clean up files for task {task['id']}: {str(e)}")
        return False

def find_exe(extract_folder):
    """Find executable file in the extracted folder"""
    try:
        for root, _, files in os.walk(extract_folder):
            for file in files:
                if file.lower().endswith('.exe'):
                    exe_path = os.path.join(root, file)
                    logger.info(f"Found executable: {exe_path}")
                    return exe_path
        
        logger.error(f"No executable found in {extract_folder}")
        return None
    except Exception as e:
        logger.error(f"Error while searching for executable: {str(e)}")
        return None

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

def process_task(task_id):
    """Process a single task"""
    task = {'id': task_id}
    logger.info(f"Processing task ID: {task_id}")
    
    try:
        # Step 1: Download zip
        if not download_zip(task):
            logger.error(f"Aborting task {task_id} due to download failure")
            return False
        
        # Step 2: Extract zip
        if not extract_zip(task):
            logger.error(f"Aborting task {task_id} due to extraction failure")
            delete_zip_and_extract_folder(task)
            return False
        
        # Step 3: Find executable
        exe_path = find_exe(task['extract_folder'])
        if not exe_path:
            logger.error(f"Aborting task {task_id} due to missing executable")
            delete_zip_and_extract_folder(task)
            return False
        
        # Step 4: Run executable
        pid = run_exe(exe_path)
        if not pid:
            logger.error(f"Aborting task {task_id} due to execution failure")
            delete_zip_and_extract_folder(task)
            return False
        
        # Step 5: Inject DLL
        usmap_path = inject(pid)
        task['usmap_path'] = usmap_path
        
        # Step 6: Upload USMap if available
        if usmap_path:
            upload_usmap(task)
        
        # Step 7: Clean up
        delete_zip_and_extract_folder(task)
        
        logger.info(f"Task {task_id} completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        delete_zip_and_extract_folder(task)
        return False

def main():
    """Process all tasks in the specified range"""
    start_id = 174
    end_id = 376
    
    logger.info(f"Starting batch processing for task IDs {start_id} to {end_id}")
    
    for task_id in range(start_id, end_id + 1):
        logger.info(f"=== Processing task ID: {task_id} ===")
        success = process_task(task_id)
        
        if success:
            logger.info(f"Task {task_id} completed successfully")
        else:
            logger.error(f"Task {task_id} failed")
        
        # Add a delay between tasks to avoid overwhelming resources
        time.sleep(5)
    
    logger.info("Batch processing completed")

if __name__ == '__main__':
    main()