import requests
import os
import sys
import base64

def rerun_task(task_id, base_url="http://localhost:8080"):
    """
    Rerun a specific task
    
    Args:
        task_id (str): The ID of the task
        base_url (str): Base URL of the server
    """
    url = f"{base_url}/api/task/{task_id}"
    
    try:
        response = requests.post(url)
        
        if response.status_code == 200:
            print(f"Successfully triggered rerun for task {task_id}")
            return True
        else:
            print(f"Error triggering rerun: {response.status_code}")
            print(f"Error message: {response.json().get('error', 'Unknown error')}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"Could not connect to {base_url} when trying to rerun task.")
        return False
    except Exception as e:
        print(f"An error occurred while trying to rerun task: {str(e)}")
        return False

def upload_usmap(task_id, usmap_path, base_url="http://localhost:8080", aes_key=None, ue_version=None):
    """
    Upload a USMAP file for a specific task and rerun the task if upload is successful
    
    Args:
        task_id (str): The ID of the task
        usmap_path (str): Absolute path to the USMAP file
        base_url (str): Base URL of the server
        aes_key (str, optional): AES key for encryption/decryption
        ue_version (str, optional): Unreal Engine version
    """
    if not os.path.exists(usmap_path):
        print(f"Error: USMAP file not found at {usmap_path}")
        return False
        
    url = f"{base_url}/api/upload_usmap"
    
    try:
        # Load USMAP file as binary data
        with open(usmap_path, 'rb') as f:
            usmap_data = f.read()
        
        # Prepare data for the API call
        data = {
            'taskId': str(task_id),
        }
        
        # Add optional parameters if provided
        if aes_key:
            data['aesKey'] = aes_key
        if ue_version:
            data['ueVersion'] = ue_version
            
        # Send binary data directly
        headers = {'Content-Type': 'application/json'}
        files = {
            'file': (os.path.basename(usmap_path), usmap_data, 'application/octet-stream')
        }
            
        # Make the POST request
        response = requests.post(url, files=files, data=data)
        
        if response.status_code == 200:
            print(f"Successfully uploaded USMAP for task {task_id}")
            print(f"Response: {response.json().get('message', '')}")
            
            # After successful upload, trigger task rerun
            print("\nTriggering task rerun...")
            if rerun_task(task_id, base_url):
                print("Task has been successfully queued for rerun")
                return True
            else:
                print("Failed to trigger task rerun")
                return False
        else:
            print(f"Error uploading USMAP: {response.status_code}")
            print(f"Error message: {response.json().get('error', 'Unknown error')}")
            return False
                
    except requests.exceptions.ConnectionError:
        print(f"Could not connect to {base_url}. Make sure the server is running.")
        return False
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

def main():
    if len(sys.argv) < 3:
        print("Usage: python upload_usmap.py <task_id> <usmap_file_path> [aes_key] [ue_version]")
        print("Example: python upload_usmap.py 123 C:\\path\\to\\your\\file.usmap")
        sys.exit(1)
        
    task_id = sys.argv[1]
    usmap_path = sys.argv[2]
    
    # Get optional parameters if provided
    aes_key = sys.argv[3] if len(sys.argv) > 3 else None
    ue_version = sys.argv[4] if len(sys.argv) > 4 else None
    
    # You can change the base_url here if needed
    base_url = "http://30.160.52.57:8080"
    
    upload_usmap(task_id, usmap_path, base_url, aes_key, ue_version)

if __name__ == "__main__":
    main() 