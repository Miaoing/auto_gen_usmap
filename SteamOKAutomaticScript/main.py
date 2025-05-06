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

# Load configuration first
config = load_config()
logger = setup_logging()

def process_tasks(controller, injector, csv_logger, task_logger, screenshot_mgr, task_limit, retry_delay):
    """
    处理未完成的任务
    
    Args:
        controller: SteamOKController实例
        injector: DLLInjector实例
        csv_logger: GameStatusLogger实例
        task_logger: TaskStatusLogger实例
        screenshot_mgr: DebugScreenshotManager实例
        task_limit: 单次处理的最大任务数量
        retry_delay: 处理任务之间的延迟时间
        
    Returns:
        int: 处理的任务数量
    """
    # Get unprocessed tasks
    unprocessed_tasks = task_logger.get_unprocessed_tasks(limit=task_limit)
    processed_count = 0
    
    if not unprocessed_tasks:
        logger.info("没有发现未处理的任务，等待下一次检查")
        return 0

    logger.info(f"发现{len(unprocessed_tasks)}个未处理的任务，开始处理")
    
    for task in unprocessed_tasks:
        task_id = task['id']
        game_name = task['Steam_Game_Name']
        
        logger.info(f"开始处理任务 {task_id}: {game_name}")
        
        # Mark task as processing
        task_logger.mark_task_processing(task_id)
        
        try:
            # Take initial screenshot at game processing start
            screenshot_mgr.take_screenshot(game_name, "start_processing", min_interval_seconds=0)
            
            # Process the game (download and check if playable)
            process_result = controller.process_game(game_name)
            
            # Take screenshot after processing result
            screenshot_mgr.take_screenshot(game_name, "after_processing", min_interval_seconds=0)
            
            if not process_result["success"]:
                error_type = process_result["error_type"]
                error_data = process_result["data"] if process_result["data"] else "Unknown error"
                
                if error_type == "easyanticheat_detected":
                    # Handle EasyAntiCheat detection as a special case
                    logger.warning(f"Game {game_name} has EasyAntiCheat: {error_data}")
                    csv_logger.log_cancelled(game_name, f"EasyAntiCheat detected: {error_data}")
                    task_logger.mark_task_error(task_id, f"EasyAntiCheat detected: {error_data}")
                    print(f"{game_name}: ⚠️ 含有反作弊系统 (EasyAntiCheat)")
                else:
                    # Handle other download failures
                    logger.error(f"Game {game_name} failed: {error_type} - {error_data}")
                    csv_logger.log_download_error(game_name, f"{error_type}: {error_data}")
                    task_logger.mark_task_error(task_id, f"{error_type}: {error_data}")
                    print(f"{game_name}: ❌ 不可玩, 原因: {error_type}")
                    
                time.sleep(retry_delay)
                processed_count += 1
                continue
            
            # Log successful download
            csv_logger.log_download_success(game_name)
            logger.info(f"Game {game_name} is playable, download successful")
            
            # Take screenshot before injection
            screenshot_mgr.take_screenshot(game_name, "before_injection", min_interval_seconds=0)
            
            logger.info(f"Game {game_name} is playable, starting DLL injection process...")
            inject_result = injector.run_injection_process_with_retry()
            
            # Take screenshot after injection
            screenshot_mgr.take_screenshot(game_name, "after_injection", min_interval_seconds=0)
            
            # Get the latest log directory if available
            log_dir = None
            if hasattr(injector, 'latest_log_dir') and injector.latest_log_dir:
                log_dir = injector.latest_log_dir
                logger.info(f"Injection log directory for {game_name}: {log_dir}")
            
            # Handle the dictionary return format
            if inject_result["success"]:
                usmap_path = inject_result["data"]
                if usmap_path:  # If USMap path was found
                    logger.info(f"✅DLL injection successful for game: {game_name}, 📁 USMap path: {usmap_path}")
                    csv_logger.log_injection_success(game_name, usmap_path, log_dir)
                    
                    # Mark task as completed and store USMAP path
                    task_logger.mark_task_completed(task_id, usmap_path)
                    
                    # Attempt to upload USMAP file
                    upload_result = upload_usmap(task_id, usmap_path, base_url=args.base_url)
                    if upload_result:
                        logger.info(f"Successfully uploaded USMAP for task {task_id}")
                    else:
                        logger.error(f"Failed to upload USMAP for task {task_id}")
                        
                    print(f"{game_name}: ✅可玩, 💉已注入DLL, 📁USMap路径: {usmap_path}")
                else:
                    logger.info(f"DLL injection successful for game: {game_name}, but no USMap path found")
                    csv_logger.log_injection_success(game_name, "No USMap path found", log_dir)
                    task_logger.mark_task_error(task_id, "DLL injection successful but no USMap path found")
                    print(f"{game_name}: 可玩, 已注入DLL")
            else:
                error_type = inject_result["error_type"]
                error_data = inject_result["data"] if inject_result["data"] else "Unknown error"
                
                if error_type == "timeout":
                    logger.error(f"DLL injection timed out for game: {game_name}")
                    csv_logger.log_injection_timeout(game_name, log_dir)
                    task_logger.mark_task_error(task_id, "DLL injection timed out")
                    print(f"{game_name}: 可玩, DLL注入超时")
                elif error_type == "game_crashed":
                    logger.error(f"Game crashed during injection: {game_name}")
                    csv_logger.log_injection_crash(game_name, "Game process crashed", log_dir)
                    task_logger.mark_task_error(task_id, "Game crashed during DLL injection")
                    print(f"{game_name}: 可玩, DLL注入时游戏崩溃")
                else:
                    logger.error(f"DLL injection failed for game: {game_name}, error type: {error_type}, details: {error_data}")
                    csv_logger.log_injection_crash(game_name, f"Injection failed: {error_type}", log_dir)
                    task_logger.mark_task_error(task_id, f"DLL injection failed: {error_type}")
                    print(f"{game_name}: 可玩, 注入DLL失败 ({error_type})")
            
            processed_count += 1
            time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"处理游戏{game_name}时出错: {e}")
            csv_logger.log_download_error(game_name, f"处理游戏时出错: {str(e)}")
            task_logger.mark_task_error(task_id, f"处理游戏时出错: {str(e)}")
            print(f"处理游戏{game_name}时出错")
            processed_count += 1
            continue
    
    return processed_count

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='SteamOK Automatic Script')
    parser.add_argument('--config', help='Path to custom configuration file')
    parser.add_argument('--webhook_url', help='URL for webhook notifications')
    parser.add_argument('--task_limit', type=int, default=5, help='Maximum number of tasks to process per run')
    parser.add_argument('--check_interval', type=int, default=30, help='Interval in seconds between task checks when idle (default: 300)')
    parser.add_argument('--base_url', type=str, default='http://30.160.52.57:8080', help='Base URL for the server')
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
    
    # Initialize the task status logger
    task_logger = TaskStatusLogger(webhook_url=webhook_url, base_url=args.base_url)
    logger.info(f"Task status logging enabled to: {task_logger.get_csv_path()}")
    
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
        
        # Setup a thread for periodic task data pulling
        def pull_task_data_periodically():
            while True:
                try:
                    new_tasks = task_logger.pull_task_data()
                    if new_tasks and len(new_tasks) > 0:
                        logger.info(f"拉取到{len(new_tasks)}个新任务:")
                        # for task in new_tasks:
                            # logger.info(f"  - 任务ID: {task['id']}, 游戏: {task['game_name']}")
                    # 使用任务记录器内置的间隔控制，所以这里只需要稍等即可
                    time.sleep(30)  # Brief wait, the task_logger will handle the actual pull interval
                except Exception as e:
                    logger.error(f"任务拉取线程出错: {str(e)}")
                    time.sleep(60)  # Wait a minute before retrying
        
        # Start the periodic task pull thread
        pull_thread = threading.Thread(target=pull_task_data_periodically, daemon=True)
        pull_thread.start()
        
        # Initial pull of task data
        # task_logger.pull_task_data(force=True)
        for _ in tqdm(range(60), desc="Initial startup delay", unit="sec"):
            time.sleep(1)
        # Main processing loop - keep running until interrupted
        retry_delay = config['timing']['retry_delay']
        check_interval = args.check_interval
        
        while True:
            start_time = time.time()
            print(f"开始处理任务")
            # Process available tasks
            processed = process_tasks(
                controller=controller,
                injector=injector,
                csv_logger=csv_logger,
                task_logger=task_logger,
                screenshot_mgr=screenshot_mgr,
                task_limit=args.task_limit,
                retry_delay=retry_delay
            )
            
            
            # If we processed tasks, don't wait as long before checking again
            if processed > 0:
                logger.info(f"本次处理了 {processed} 个任务，30秒后检查新任务")
                time.sleep(30)  # Short wait after processing tasks
            else:
                # Calculate how long to wait - if processing took a long time, we might not need to wait at all
                elapsed = time.time() - start_time
                wait_time = max(0, check_interval - elapsed)
                
                if wait_time > 0:
                    logger.info(f"没有任务需要处理，等待 {wait_time:.0f} 秒后重新检查")
                    # Sleep in smaller increments to allow for cleaner shutdown
                    sleep_increment = 10  # 10 seconds
                    remaining = wait_time
                    while remaining > 0:
                        time.sleep(min(remaining, sleep_increment))
                        remaining -= sleep_increment
                        
    except KeyboardInterrupt:
        logger.info("收到中断信号，脚本正在退出...")
        print("脚本已中断")
    except Exception as e:
        logger.error(f"应用程序错误: {e}")
        print(f"错误: {e}")
    finally:
        logger.info("脚本结束")


if __name__ == "__main__":
    main()
