import os
import csv
import time
import logging
import requests
from datetime import datetime
from search_tasks import search_error_tasks

logger = logging.getLogger()

class TaskStatusLogger:
    """
    Maintains a CSV file with task status information, periodically pulling from the database
    using the search_tasks functionality.
    """
    def __init__(self, csv_path="task_status.csv", webhook_url=None, base_url="http://localhost:8080"):
        self.csv_path = csv_path
        self.webhook_url = webhook_url
        self.base_url = base_url
        self.ensure_csv_exists()
        self.last_pull_time = 0
        self.pull_interval = 60  # Pull every 60 seconds

    def ensure_csv_exists(self):
        """Create CSV file if it doesn't exist"""
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'id', 'Steam_Game_Name', 'Status', 'USMap_Path', 
                    'Error_Detail', 'Last_Updated'
                ])
                writer.writeheader()
            logger.info(f"Created new task status CSV file: {self.csv_path}")

    def get_csv_path(self):
        """Return the path to the CSV file"""
        return self.csv_path

    def pull_task_data(self, force=False):
        """
        Pull task data from the database if the pull interval has elapsed or force is True
        Only adds new tasks, does not update existing ones
        
        Args:
            force (bool): If True, pull data regardless of the time since last pull
            
        Returns:
            list: List of new tasks added to the CSV, or None if no pull was performed or no new tasks found
        """
        current_time = time.time()
        if force or (current_time - self.last_pull_time) >= self.pull_interval:
            logger.info("Pulling task data from database...")
            try:
                tasks = search_error_tasks(self.base_url)
                if tasks:
                    # Only count and return new tasks
                    current_task_ids = set(self.load_current_tasks().keys())
                    new_tasks = [task for task in tasks if task['id'] not in current_task_ids]
                    if new_tasks:
                        self.update_tasks_in_csv(new_tasks)
                        logger.info(f"Found {len(tasks)} tasks, added {len(new_tasks)} new tasks to CSV")
                        self.last_pull_time = current_time
                        return new_tasks
                    else:
                        logger.info(f"Found {len(tasks)} tasks, but all are already in CSV")
                        self.last_pull_time = current_time
                        return []
                else:
                    logger.info("No tasks found in database")
                    self.last_pull_time = current_time
                    return []
                
            except Exception as e:
                logger.error(f"Error pulling task data: {str(e)}")
                return None
        return None

    def update_tasks_in_csv(self, tasks):
        """
        Update the CSV file with tasks pulled from the database
        Only adds new tasks, does not update existing ones
        
        Args:
            tasks (list): List of task dictionaries from search_error_tasks
        """
        current_tasks = self.load_current_tasks()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        new_tasks_added = 0
        
        # Only add new tasks, don't update existing ones
        for task in tasks:
            task_id = task['id']
            if task_id not in current_tasks:
                # Add new task
                current_tasks[task_id] = {
                    'id': task_id,
                    'Steam_Game_Name': task['game_name'],
                    'Status': 'unprocessed',
                    'USMap_Path': '',
                    'Error_Detail': task.get('info', ''),
                    'Last_Updated': timestamp
                }
                
                new_tasks_added += 1
                
                # Send webhook notification for new task
                if self.webhook_url:
                    self.send_webhook({
                        'type': 'new_task',
                        'task_id': task_id,
                        'game_name': task['game_name'],
                        'status': 'unprocessed',
                        'timestamp': timestamp
                    })
        
        # Only save if we added new tasks
        if new_tasks_added > 0:
            # Write all tasks back to CSV
            self.save_tasks(current_tasks)
            logger.info(f"Added {new_tasks_added} new tasks to CSV")
        else:
            logger.debug("No new tasks to add to CSV")

    def load_current_tasks(self):
        """
        Load existing tasks from CSV
        
        Returns:
            dict: Dictionary of tasks with task_id as key
        """
        tasks = {}
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    tasks[row['id']] = row
        except Exception as e:
            logger.error(f"Error loading tasks from CSV: {str(e)}")
        return tasks

    def save_tasks(self, tasks):
        """
        Save tasks dictionary to CSV
        
        Args:
            tasks (dict): Dictionary of tasks with task_id as key
        """
        try:
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'id', 'Steam_Game_Name', 'Status', 'USMap_Path', 
                    'Error_Detail', 'Last_Updated'
                ])
                writer.writeheader()
                writer.writerows(tasks.values())
        except Exception as e:
            logger.error(f"Error saving tasks to CSV: {str(e)}")

    def get_unprocessed_tasks(self, limit=5):
        """
        Get a list of unprocessed tasks from the CSV
        
        Args:
            limit (int): Maximum number of tasks to return
            
        Returns:
            list: List of unprocessed task dictionaries
        """
        tasks = self.load_current_tasks()
        unprocessed = [task for task in tasks.values() if task['Status'] == 'unprocessed']
        return unprocessed[:limit]

    def update_task_status(self, task_id, status, usmap_path=None, error_detail=None):
        """
        Update the status of a task in the CSV
        
        Args:
            task_id (str): ID of the task to update
            status (str): New status value
            usmap_path (str, optional): Path to USMAP file if status is 'completed'
            error_detail (str, optional): Error details if status is 'error'
        """
        tasks = self.load_current_tasks()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if task_id in tasks:
            task = tasks[task_id]
            old_status = task['Status']
            task['Status'] = status
            task['Last_Updated'] = timestamp
            
            if usmap_path:
                task['USMap_Path'] = usmap_path
            
            if error_detail:
                task['Error_Detail'] = error_detail
            
            # Save the updated tasks
            self.save_tasks(tasks)
            
            # Send webhook notification for status change
            if self.webhook_url and old_status != status:
                self.send_webhook({
                    'type': 'status_change',
                    'task_id': task_id,
                    'game_name': task['Steam_Game_Name'],
                    'old_status': old_status,
                    'new_status': status,
                    'usmap_path': usmap_path if usmap_path else '',
                    'error_detail': error_detail if error_detail else '',
                    'timestamp': timestamp
                })
            
            logger.info(f"Updated task {task_id} status to {status}")
            return True
        else:
            logger.error(f"Task {task_id} not found in CSV")
            return False

    def mark_task_processing(self, task_id):
        """Mark a task as being processed"""
        return self.update_task_status(task_id, 'processing')

    def mark_task_completed(self, task_id, usmap_path):
        """Mark a task as completed with USMAP path"""
        return self.update_task_status(task_id, 'completed', usmap_path=usmap_path)

    def mark_task_error(self, task_id, error_detail):
        """Mark a task as having an error"""
        return self.update_task_status(task_id, 'error', error_detail=error_detail)

    def send_webhook(self, data):
        """
        Send a webhook notification with format compatible with WeChat/DingTalk/Feishu
        
        Args:
            data (dict): Data to send in the webhook
        """
        if not self.webhook_url:
            return
        
        # 构建消息内容
        if data['type'] == 'new_task':
            content = f"🆕 新任务添加:\n任务ID: {data['task_id']}\n游戏: {data['game_name']}\n状态: {data['status']}\n时间: {data['timestamp']}"
        elif data['type'] == 'status_change':
            content = f"📝 任务状态更新:\n任务ID: {data['task_id']}\n游戏: {data['game_name']}\n状态: {data['old_status']} -> {data['new_status']}"
            if data['usmap_path']:
                content += f"\nUSMap路径: {data['usmap_path']}"
            if data['error_detail']:
                content += f"\n错误详情: {data['error_detail']}"
            content += f"\n时间: {data['timestamp']}"
        else:
            content = f"📢 任务通知: {str(data)}"
        
        # 使用与csv_logger.py相同的消息格式
        headers = {
            'Content-Type': 'application/json'
        }
        
        payload = {
            'msgtype': 'text',
            'text': {
                'content': content
            }
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                headers=headers,
                json=payload
            )
            
            if response.status_code >= 200 and response.status_code < 300:
                logger.debug(f"Webhook sent successfully: {data['type']}")
            else:
                logger.error(f"Failed to send webhook: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Error sending webhook: {str(e)}")

# For testing purposes
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger()
    
    task_logger = TaskStatusLogger()
    # Force pull data
    tasks = task_logger.pull_task_data(force=True)
    
    if tasks:
        print(f"Found {len(tasks)} tasks")
        # Get unprocessed tasks
        unprocessed = task_logger.get_unprocessed_tasks()
        print(f"Unprocessed tasks: {len(unprocessed)}")
        for task in unprocessed:
            print(f"  {task['id']}: {task['Steam_Game_Name']}")
    else:
        print("No tasks found or error occurred") 