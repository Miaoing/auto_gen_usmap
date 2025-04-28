import requests
import json
import csv
import time
from datetime import datetime
import os

class CSVWatcher:
    def __init__(self, csv_file, webhook_url):
        self.csv_file = csv_file
        self.webhook_url = webhook_url
        self.last_position = 0
        self.initialize_position()

    def initialize_position(self):
        """Initialize the last read position of the file"""
        if os.path.exists(self.csv_file):
            with open(self.csv_file, 'r') as f:
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
        """Check for new lines in the CSV file"""
        try:
            if not os.path.exists(self.csv_file):
                print(f"Waiting for CSV file {self.csv_file} to be created...")
                return

            with open(self.csv_file, 'r') as f:
                # Move to the last read position
                f.seek(self.last_position)
                
                # Read any new lines
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:  # Ensure we have both timestamp and message
                        message = f"New message at {row[0]}: {row[1]}"
                        self.send_message(message)
                        print(f"New line detected: {message}")
                
                # Update the last read position
                self.last_position = f.tell()

        except Exception as e:
            print(f"Error reading CSV file: {e}")

    def watch(self, interval=5):
        """
        Watch the CSV file for changes
        Args:
            interval (int): How often to check for changes (in seconds)
        """
        print(f"Starting to watch {self.csv_file} for changes...")
        print(f"Checking every {interval} seconds...")
        
        while True:
            self.check_for_updates()
            time.sleep(interval)

if __name__ == "__main__":
    # Replace this with your actual webhook URL
    WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=41d709ab-4cbd-43bd-99a8-0be822b7584a"
    CSV_FILE = r"data.csv"
    
    # Create and start the watcher
    watcher = CSVWatcher(CSV_FILE, WEBHOOK_URL)
    watcher.watch() 