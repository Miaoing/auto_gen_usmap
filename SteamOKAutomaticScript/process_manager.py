import csv
import os
import time
from datetime import datetime
import json
from search_tasks import search_error_tasks
from upload_usmap import upload_usmap
import subprocess

class TaskManager:
    def __init__(self, csv_path="task_status.csv", base_url="http://localhost:8080"):
        self.csv_path = csv_path
        self.base_url = base_url
        self.ensure_csv_exists()

    def ensure_csv_exists(self):
        """Create CSV file if it doesn't exist"""
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'id', 'Steam_Game_Name', 'Status', 'USMap_Path', 
                    'Error_Detail', 'Last_Updated'
                ])
                writer.writeheader()

    def load_current_tasks(self):
        """Load existing tasks from CSV"""
        tasks = {}
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                tasks[row['id']] = row
        return tasks

    def save_task(self, task_data):
        """Save or update a task in CSV"""
        tasks = self.load_current_tasks()
        task_data['Last_Updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tasks[task_data['id']] = task_data

        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'id', 'Steam_Game_Name', 'Status', 'USMap_Path', 
                'Error_Detail', 'Last_Updated'
            ])
            writer.writeheader()
            writer.writerows(tasks.values())

    def check_game_status(self, game_name):
        """Check game processing status and get USMAP path if successful"""
        status_files = [f for f in os.listdir() if f.startswith('game_status_')]
        if not status_files:
            return None, None, "No status file found"

        latest_status_file = max(status_files)
        try:
            with open(latest_status_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['GameName'] == game_name:
                        if row['Status'] == 'INJECTION_SUCCESS':
                            return 'ended', row['USMapPath'], None
                        else:
                            return 'ended', None, row.get('ErrorDetails', 'Unknown error')
        except Exception as e:
            return None, None, f"Error reading status file: {str(e)}"
        
        return None, None, "Game not found in status file"

    def process_unprocessed_tasks(self):
        """Process tasks that are in unprocessed state"""
        tasks = self.load_current_tasks()
        for task_id, task in tasks.items():
            if task['Status'] == 'unprocessed':
                # Update status to running
                task['Status'] = 'running'
                self.save_task(task)

                # Here you would call your game processing script
                # Simulating with a print for now
                print(f"Processing game: {task['Steam_Game_Name']}")
                
                # Check status periodically
                while True:
                    status, usmap_path, error = self.check_game_status(task['Steam_Game_Name'])
                    if status == 'ended':
                        if usmap_path:
                            # Upload USMAP file
                            if upload_usmap(task_id, usmap_path, self.base_url):
                                task['Status'] = 'completed'
                                task['USMap_Path'] = usmap_path
                            else:
                                task['Status'] = 'error'
                                task['Error_Detail'] = 'Failed to upload USMAP'
                        else:
                            task['Status'] = 'error'
                            task['Error_Detail'] = error
                        self.save_task(task)
                        break
                    time.sleep(60)  # Check every minute

    def update_from_search(self):
        """Update task list from search results"""
        try:
            # Capture the output of search_error_tasks
            current_tasks = self.load_current_tasks()
            
            # Call search_error_tasks directly
            search_results = search_error_tasks(self.base_url)
            if not search_results:
                print("No new tasks found")
                return

            for task in search_results:
                task_id = task['id']  # Already a string from search_tasks
                if task_id not in current_tasks:
                    # Add new task
                    self.save_task({
                        'id': task_id,
                        'Steam_Game_Name': task['game_name'],
                        'Status': 'unprocessed',
                        'USMap_Path': '',
                        'Error_Detail': '',
                    })
                    print(f"Added new task for game: {task['game_name']}")
        except Exception as e:
            print(f"Error updating from search: {str(e)}")

def main():
    manager = TaskManager()
    
    while True:
        try:
            # Update task list from search
            manager.update_from_search()
            
            # Process unprocessed tasks
            manager.process_unprocessed_tasks()
            
            # Wait for a minute before next iteration
            time.sleep(60)
            
        except KeyboardInterrupt:
            print("\nShutting down gracefully...")
            break
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            time.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    main() 