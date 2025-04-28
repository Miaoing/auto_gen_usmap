import requests
import json
import csv
import time
from datetime import datetime
import os
import glob

class CSVWatcher:
    def __init__(self, result_dir, webhook_url):
        self.result_dir = result_dir
        self.webhook_url = webhook_url
        self.current_csv_file = None
        self.last_position = 0
        self.processed_files = set()
        self.find_newest_csv()

    def find_newest_csv(self):
        """Find the newest CSV file in the result directory"""
        try:
            # Get all CSV files in the result directory
            csv_files = glob.glob(os.path.join(self.result_dir, "*.csv"))
            
            if not csv_files:
                print(f"No CSV files found in {self.result_dir}")
                return False
            
            # Find the newest file by modification time
            newest_file = max(csv_files, key=os.path.getmtime)
            
            # If this is a new file or we haven't processed any files yet
            if newest_file not in self.processed_files or self.current_csv_file is None:
                # If we were watching a different file before, add it to processed files
                if self.current_csv_file:
                    self.processed_files.add(self.current_csv_file)
                
                self.current_csv_file = newest_file
                self.last_position = 0
                self.initialize_position()
                
                print(f"Now watching: {self.current_csv_file}")
                self.send_message(f"Started watching new CSV file: {os.path.basename(self.current_csv_file)}")
                return True
            
            return False
            
        except Exception as e:
            print(f"Error finding newest CSV file: {e}")
            return False

    def initialize_position(self):
        """Initialize the last read position of the file"""
        if self.current_csv_file and os.path.exists(self.current_csv_file):
            with open(self.current_csv_file, 'r') as f:
                self.last_position = f.tell()
                # Read header
                next(csv.reader(f))
                # Move to end of file
                f.seek(0, 2)
                self.last_position = f.tell()

    def send_message(self, message):
        """
        Send a message to the group chat
        Args:
            message (str): The message to send
        """
        headers = {
            'Content-Type': 'application/json'
        }
        
        payload = {
            'msgtype': 'text',
            'text': {
                'content': message
            }
        }
        
        try:
            response = requests.post(self.webhook_url, headers=headers, json=payload)
            response.raise_for_status()
            print(f"Message sent successfully! Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error sending message: {e}")

    def check_for_updates(self):
        """Check for new lines in the CSV file and new CSV files in the directory"""
        # First check if there are new CSV files
        new_file_found = self.find_newest_csv()
        
        # If no current CSV file, nothing to check
        if not self.current_csv_file or not os.path.exists(self.current_csv_file):
            return
            
        try:
            with open(self.current_csv_file, 'r') as f:
                # Move to the last read position
                f.seek(self.last_position)
                
                # Read any new lines
                reader = csv.reader(f)
                for row in reader:
                    game_name = row[0]
                    status = row[1]
                    timestamp = row[2]
                    usmap_path = row[3]
                    
                    message = f"[{timestamp}] Game: {game_name} - Status: {status}"
                    if status == "INJECTION_SUCCESS" and usmap_path:
                        message += f"\nUSMap path: {usmap_path}"
                        
                    self.send_message(message)
                    print(f"New entry processed: {game_name} - {status}")
            
                # Update the last read position
                self.last_position = f.tell()

        except Exception as e:
            print(f"Error reading CSV file {self.current_csv_file}: {e}")

    def watch(self, interval=5):
        """
        Watch the result directory for new CSV files and changes to the current CSV file
        Args:
            interval (int): How often to check for changes (in seconds)
        """
        print(f"Starting to watch {self.result_dir} for new CSV files...")
        print(f"Checking every {interval} seconds...")
        
        while True:
            self.check_for_updates()
            time.sleep(interval)

if __name__ == "__main__":
    # Replace this with your actual webhook URL
    WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=41d709ab-4cbd-43bd-99a8-0be822b7584a"
    
    # Directory to watch for CSV files
    RESULT_DIR = r"C:\Users\Administrator\Documents\workspace\auto_gen_usmap\SteamOKAutomaticScript\result"
    
    # Create and start the watcher
    watcher = CSVWatcher(RESULT_DIR, WEBHOOK_URL)
    watcher.watch() 