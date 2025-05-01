import requests
import json
import csv
import os

def load_game_names():
    """
    Load game names from CSV file with UTF-8 encoding for Chinese characters
    """
    game_names = {}
    try:
        with open('game_with_id.csv', 'r', encoding='utf-8-sig') as f:  # utf-8-sig handles the BOM
            reader = csv.DictReader(f)
            for row in reader:
                game_names[row['id']] = row['Name']
    except FileNotFoundError:
        print("Warning: game_with_id.csv not found")
    except UnicodeDecodeError:
        # If UTF-8 fails, try with GB18030 which is common for Chinese Windows systems
        try:
            with open('game_with_id.csv', 'r', encoding='gb18030') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    game_names[row['id']] = row['Name']
        except UnicodeDecodeError:
            print("Warning: Unable to read Chinese characters in CSV file")
    return game_names

def search_error_tasks(base_url="http://localhost:8080"):
    """
    Search for error tasks with us_map/usmap in their info
    Returns:
        list: List of matching tasks with their details
    """
    # Load game names from CSV
    game_names = load_game_names()
    
    # First search by status
    url = f"{base_url}/api/search_tasks"
    
    # Search for error status tasks
    status_payload = {
        "query": "error",
        "title": "status"
    }
    
    try:
        # Make the POST request for error status
        response = requests.post(url, json=status_payload)
        
        if response.status_code == 200:
            error_tasks = response.json()
            
            # Now search in these tasks for us_map/usmap in info
            matching_tasks = []
            for task in error_tasks:
                info = task.get('info', '').lower()
                if 'us_map' in info or 'usmap' in info:
                    task_id = str(task.get('id'))
                    game_name = game_names.get(task_id, "Unknown Game")
                    
                    # Create a task entry with required fields
                    matching_tasks.append({
                        'id': task_id,
                        'name': task['name'],
                        'game_name': game_name,
                        'status': task['status'],
                        'info': task.get('info', ''),
                        'usmap': task.get('usmap', 'False')
                    })
            
            # Print summary for console output
            # print(f"\nFound {len(matching_tasks)} error tasks containing 'us_map' or 'usmap' in info:")
            # print("-" * 50)
            # for task in matching_tasks:
            #     print(f"Task ID: {task['id']}")
            #     print(f"Database Name: {task['name']}")
            #     print(f"Steam Game Name: {task['game_name']}")
            #     print(f"Status: {task['status']}")
            #     print(f"Info: {task['info']}")
            #     print(f"Has USMAP: {task['usmap']}")
            #     print("-" * 50)
            
            # Return the list of matching tasks
            return matching_tasks if matching_tasks else None
                
        elif response.status_code == 404:
            print("No error tasks found")
            return None
        else:
            print(f"Error: {response.status_code}")
            print(response.json().get('error', 'Unknown error'))
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"Could not connect to {base_url}. Make sure the server is running.")
        return None
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

if __name__ == "__main__":
    search_error_tasks() 