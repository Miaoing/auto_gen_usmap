#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Steam Games Cleanup Script

This script deletes files and directories in the Steam installation to free up space.
It removes:
- Game directories in steamapps/common/
- In-progress downloads in steamapps/downloading/
- Temporary files in steamapps/temp/
- Game manifest files (appmanifest_*.acf)
- Shader cache files in shadercache/

The Steam directory path is read from the application's configuration file.
"""

import os
import shutil
import glob
import logging
from pathlib import Path
import time
import sys
import datetime
import argparse

# Add parent directory to path so we can import from config package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import config loader from the config package
from config import get_config, load_config

# Set up logging
logger = logging.getLogger(__name__)

class SteamGamesCleaner:
    """Class to handle the Steam games cleanup process."""
    
    def __init__(self, preserve_after=None):
        """
        Initialize the cleaner with configuration.
        
        Args:
            preserve_after: Timestamp (in seconds since epoch) after which files should not be deleted
        """
        # Ensure config is loaded
        self.config = get_config()
        
        # Get Steam apps directory from config
        self.steam_apps_dir = self.config['paths']['steam_apps_base']
        logger.info(f"Using Steam apps directory: {self.steam_apps_dir}")
        
        # Set timestamp for file preservation
        self.preserve_after = preserve_after
        if self.preserve_after:
            timestamp = datetime.datetime.fromtimestamp(self.preserve_after).strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"Preserving files created after: {timestamp}")
        
        # Verify the directory exists
        if not os.path.exists(self.steam_apps_dir):
            raise FileNotFoundError(f"Steam apps directory not found: {self.steam_apps_dir}")

    def should_delete(self, path):
        """
        Check if a file or directory should be deleted based on its modification time.
        
        Args:
            path: Path to the file or directory
            
        Returns:
            bool: True if the file should be deleted, False otherwise
        """
        if not self.preserve_after:
            return True
            
        try:
            # Get the modification time of the file/directory
            mtime = os.path.getmtime(path)
            # If the file was modified after the preserve_after timestamp, don't delete it
            if mtime > self.preserve_after:
                timestamp = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"Preserving {path} (modified on {timestamp})")
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking modification time for {path}: {str(e)}")
            # If we can't check the timestamp, assume it's safe to delete
            return True

    def delete_directory(self, directory_path):
        """
        Delete a directory and all its contents.
        
        Args:
            directory_path: Path to the directory to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            if os.path.exists(directory_path):
                # Check if we should preserve this directory based on timestamp
                if not self.should_delete(directory_path):
                    logger.info(f"Skipping directory due to timestamp: {directory_path}")
                    return False
                
                if os.path.isdir(directory_path):
                    shutil.rmtree(directory_path)
                    logger.info(f"Deleted directory: {directory_path}")
                else:
                    os.remove(directory_path)
                    logger.info(f"Deleted file: {directory_path}")
                return True
            else:
                logger.info(f"Directory does not exist, skipping: {directory_path}")
                return True
        except Exception as e:
            logger.error(f"Error deleting {directory_path}: {str(e)}")
            return False

    def delete_files(self, file_pattern):
        """
        Delete files matching a pattern.
        
        Args:
            file_pattern: Glob pattern for files to delete
            
        Returns:
            int: Number of files deleted
        """
        try:
            files = glob.glob(file_pattern)
            deleted_count = 0
            
            for file_path in files:
                try:
                    if os.path.isfile(file_path):
                        # Check if we should preserve this file based on timestamp
                        if not self.should_delete(file_path):
                            logger.info(f"Skipping file due to timestamp: {file_path}")
                            continue
                            
                        os.remove(file_path)
                        logger.info(f"Deleted file: {file_path}")
                        deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting file {file_path}: {str(e)}")
            
            return deleted_count
        except Exception as e:
            logger.error(f"Error while processing file pattern {file_pattern}: {str(e)}")
            return 0

    def clean_steamapps(self):
        """
        Clean up Steam apps directory by removing game files and directories.
        
        Returns:
            dict: Statistics of deletion operations
        """
        stats = {
            'common_dirs_deleted': 0,
            'downloading_dirs_deleted': 0,
            'temp_dirs_deleted': 0,
            'manifest_files_deleted': 0,
            'shadercache_dirs_deleted': 0
        }
        
        # 1. Delete game directories in steamapps/common/
        common_dir = os.path.join(self.steam_apps_dir, 'common')
        if os.path.exists(common_dir):
            game_dirs = [os.path.join(common_dir, d) for d in os.listdir(common_dir) 
                         if os.path.isdir(os.path.join(common_dir, d))]
            
            for game_dir in game_dirs:
                if self.delete_directory(game_dir):
                    stats['common_dirs_deleted'] += 1
        
        # 2. Delete downloading directory
        downloading_dir = os.path.join(self.steam_apps_dir, 'downloading')
        if os.path.exists(downloading_dir):
            download_dirs = [os.path.join(downloading_dir, d) for d in os.listdir(downloading_dir) 
                             if os.path.isdir(os.path.join(downloading_dir, d))]
            
            for download_dir in download_dirs:
                if self.delete_directory(download_dir):
                    stats['downloading_dirs_deleted'] += 1
        
        # 3. Delete temp directory
        temp_dir = os.path.join(self.steam_apps_dir, 'temp')
        if os.path.exists(temp_dir):
            temp_items = [os.path.join(temp_dir, d) for d in os.listdir(temp_dir)]
            
            for item in temp_items:
                if self.delete_directory(item):
                    stats['temp_dirs_deleted'] += 1
        
        # 4. Delete game manifest files (appmanifest_*.acf)
        manifest_pattern = os.path.join(self.steam_apps_dir, 'appmanifest_*.acf')
        stats['manifest_files_deleted'] = self.delete_files(manifest_pattern)
        
        # 5. Delete shader cache directories
        shadercache_dir = os.path.join(self.steam_apps_dir, 'shadercache')
        if os.path.exists(shadercache_dir):
            cache_dirs = [os.path.join(shadercache_dir, d) for d in os.listdir(shadercache_dir) 
                          if os.path.isdir(os.path.join(shadercache_dir, d))]
            
            for cache_dir in cache_dirs:
                if self.delete_directory(cache_dir):
                    stats['shadercache_dirs_deleted'] += 1
        
        return stats

def setup_logging():
    """Configure logging for the script."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), 
                    'logs', 
                    f'steam_cleanup_{time.strftime("%Y%m%d_%H%M%S")}.log'
                )
            )
        ]
    )
    return logging.getLogger(__name__)

def parse_time_string(time_string):
    """
    Parse a time string into a timestamp.
    Accepts formats: 
    - ISO format (YYYY-MM-DD HH:MM:SS)
    - Relative time like '2h', '30m', '1d' for hours, minutes, days ago
    
    Args:
        time_string: String representing a time
        
    Returns:
        float: Timestamp (seconds since epoch)
    """
    if not time_string:
        return None
        
    try:
        # Check if it's a relative time format
        if time_string.endswith(('m', 'h', 'd')):
            unit = time_string[-1]
            value = int(time_string[:-1])
            
            now = datetime.datetime.now()
            if unit == 'm':  # minutes
                delta = datetime.timedelta(minutes=value)
            elif unit == 'h':  # hours
                delta = datetime.timedelta(hours=value)
            elif unit == 'd':  # days
                delta = datetime.timedelta(days=value)
                
            return (now - delta).timestamp()
        else:
            # Try ISO format
            dt = datetime.datetime.fromisoformat(time_string)
            return dt.timestamp()
    except Exception as e:
        logger.error(f"Error parsing time string '{time_string}': {str(e)}")
        logger.error("Valid formats: 'YYYY-MM-DD HH:MM:SS' or relative times like '2h', '30m', '1d'")
        return None

def main():
    """Main function to run the Steam games cleanup process."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Clean up Steam game directories')
    parser.add_argument('--preserve-after', 
                       help='Preserve files modified after this timestamp. Formats: YYYY-MM-DD HH:MM:SS or relative times like 2h, 30m, 1d')
    parser.add_argument('--config', help='Path to custom configuration file')
    args = parser.parse_args()
    
    # If custom config is provided, reload configuration
    if args.config:
        config = load_config(args.config)
    
    # Set up logging
    global logger
    logger = setup_logging()
    
    # Parse the preserve-after timestamp if provided
    preserve_after = None
    if args.preserve_after:
        preserve_after = parse_time_string(args.preserve_after)
        if not preserve_after:
            logger.error(f"Invalid time format: {args.preserve_after}")
            return 1
    
    logger.info("Starting Steam games cleanup process")
    
    try:
        # Ensure the logs directory exists
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        # Initialize the cleaner with the preserve_after timestamp
        cleaner = SteamGamesCleaner(preserve_after=preserve_after)
        
        # Run the cleanup process
        logger.info(f"Cleaning up Steam games in directory: {cleaner.steam_apps_dir}")
        stats = cleaner.clean_steamapps()
        
        # Log the results
        logger.info("Cleanup completed successfully")
        logger.info(f"Statistics: {stats}")
        print("Steam games cleanup completed successfully.")
        print(f"- Game directories deleted: {stats['common_dirs_deleted']}")
        print(f"- Downloading directories deleted: {stats['downloading_dirs_deleted']}")
        print(f"- Temporary files deleted: {stats['temp_dirs_deleted']}")
        print(f"- Game manifest files deleted: {stats['manifest_files_deleted']}")
        print(f"- Shader cache directories deleted: {stats['shadercache_dirs_deleted']}")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        print(f"Error during cleanup: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 