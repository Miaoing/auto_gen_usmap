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
import re

# Load configuration first
config = load_config()
logger = setup_logging()

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='SteamOK Automatic Script')
    parser.add_argument('--config', help='Path to custom configuration file')
    parser.add_argument('--webhook_url', help='URL for webhook notifications')
    args = parser.parse_args()
    
    # If custom config is provided, reload configuration
    if args.config:
        global config
        config = load_config(args.config)
        logger.info(f"Using custom configuration file: {args.config}")
    
    # Initialize the CSV logger
    webhook_url = args.webhook_url
    csv_logger = GameStatusLogger(webhook_url=webhook_url)
    logger.info(f"CSV logging enabled to: {csv_logger.get_csv_path()}")
    if webhook_url:
        logger.info(f"Webhook notifications enabled with URL: {webhook_url}")
    
    # Initialize the debug screenshot manager
    screenshot_mgr = DebugScreenshotManager()
    
    # Run the normal game installation process
    try:
        logger.info("脚本启动中...")
        
        # Initialize the game controller without Excel path
        controller = SteamOKController(screenshot_mgr=screenshot_mgr)
        # Note: Game installation timeout can be configured in config.yaml under timing.installation_timeout
        
        # Initialize the DLL injector
        injector = DLLInjector()
        
        # Assume games is a list - for testing purposes, you can define a sample list here
        # In a real scenario, you would pass this list from elsewhere
        games = ["Partisans 1941", "Azur Lane Crosswave", "Redfall"]  # Example list, replace as needed
        logger.info(f"加载{len(games)}个游戏")

        for game in games:
            try:
                # Take initial screenshot at game processing start
                screenshot_mgr.take_screenshot(game, "start_processing", min_interval_seconds=0)
                
                # Process the game (download and check if playable)
                process_result = controller.process_game(game)
                
                # Take screenshot after processing result
                screenshot_mgr.take_screenshot(game, "after_processing", min_interval_seconds=0)
                
                if not process_result["success"]:
                    error_type = process_result["error_type"]
                    error_data = process_result["data"] if process_result["data"] else "Unknown error"
                    
                    if error_type == "easyanticheat_detected":
                        # Handle EasyAntiCheat detection as a special case
                        logger.warning(f"Game {game} has EasyAntiCheat: {error_data}")
                        csv_logger.log_cancelled(game, f"EasyAntiCheat detected: {error_data}")
                        print(f"{game}: ⚠️ 含有反作弊系统 (EasyAntiCheat)")
                    else:
                        # Handle other download failures
                        logger.error(f"Game {game} failed: {error_type} - {error_data}")
                        csv_logger.log_download_error(game, f"{error_type}: {error_data}")
                        print(f"{game}: ❌ 不可玩, 原因: {error_type}")
                        
                    time.sleep(config['timing']['retry_delay'])
                    continue
                
                # Log successful download
                csv_logger.log_download_success(game)
                logger.info(f"Game {game} is playable, download successful")
                
                # Take screenshot before injection
                screenshot_mgr.take_screenshot(game, "before_injection", min_interval_seconds=0)
                
                logger.info(f"Game {game} is playable, starting DLL injection process...")
                inject_result = injector.run_injection_process_with_retry()
                
                # Take screenshot after injection
                screenshot_mgr.take_screenshot(game, "after_injection", min_interval_seconds=0)
                
                # Get the latest log directory if available
                log_dir = None
                if hasattr(injector, 'latest_log_dir') and injector.latest_log_dir:
                    log_dir = injector.latest_log_dir
                    logger.info(f"Injection log directory for {game}: {log_dir}")
                
                # Handle the dictionary return format
                if inject_result["success"]:
                    usmap_path = inject_result["data"]
                    if usmap_path:  # If USMap path was found
                        logger.info(f"✅DLL injection successful for game: {game}, 📁 USMap path: {usmap_path}")
                        csv_logger.log_injection_success(game, usmap_path, log_dir)
                        print(f"{game}: ✅可玩, 💉已注入DLL, 📁USMap路径: {usmap_path}")
                    else:
                        logger.info(f"DLL injection successful for game: {game}, but no USMap path found")
                        csv_logger.log_injection_success(game, "No USMap path found", log_dir)
                        print(f"{game}: 可玩, 已注入DLL")
                else:
                    error_type = inject_result["error_type"]
                    error_data = inject_result["data"] if inject_result["data"] else "Unknown error"
                    
                    if error_type == "timeout":
                        logger.error(f"DLL injection timed out for game: {game}")
                        csv_logger.log_injection_timeout(game, log_dir)
                        print(f"{game}: 可玩, DLL注入超时")
                    elif error_type == "game_crashed":
                        logger.error(f"Game crashed during injection: {game}")
                        csv_logger.log_injection_crash(game, "Game process crashed", log_dir)
                        print(f"{game}: 可玩, DLL注入时游戏崩溃")
                    else:
                        logger.error(f"DLL injection failed for game: {game}, error type: {error_type}, details: {error_data}")
                        csv_logger.log_injection_crash(game, f"Injection failed: {error_type}", log_dir)
                        print(f"{game}: 可玩, 注入DLL失败 ({error_type})")
                
                time.sleep(config['timing']['retry_delay'])
            except Exception as e:
                logger.error(f"处理游戏{game}时出错: {e}")
                csv_logger.log_download_error(game, f"处理游戏时出错: {str(e)}")
                print(f"处理游戏{game}时出错")
                continue

        print(f"处理完成。结果已保存到CSV文件: {csv_logger.get_csv_path()}")
    except Exception as e:
        logger.error(f"应用程序错误: {e}")
        print(f"错误: {e}")
    finally:
        logger.info("脚本结束")


if __name__ == "__main__":
    main()
