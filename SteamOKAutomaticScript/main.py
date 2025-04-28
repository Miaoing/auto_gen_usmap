import time
import logging
import pandas as pd
import argparse
import os
from datetime import datetime
import pyautogui as pg
from logger import setup_logging
from game_install_controller import SteamOKController
from ocr_helper import OcrHelper
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
    parser.add_argument('--inject', action='store_true', help='Run the DLL injection process')
    parser.add_argument('--config', help='Path to custom configuration file')
    args = parser.parse_args()
    
    # If custom config is provided, reload configuration
    if args.config:
        global config
        config = load_config(args.config)
        logger.info(f"Using custom configuration file: {args.config}")
    
    # Initialize the CSV logger
    csv_logger = GameStatusLogger()
    logger.info(f"CSV logging enabled to: {csv_logger.get_csv_path()}")
    
    # Initialize the debug screenshot manager
    screenshot_mgr = DebugScreenshotManager()
    
    # Connect the screenshot manager to the game controller
    screenshot_mgr
    
    # If injection mode is selected, run the injector and exit
    if args.inject:
        logger.info("Running in DLL injection mode...")
        # Initialize the DLL injector with configuration loaded from config
        injector = DLLInjector()
        result = injector.run_injection_process()
        
        log_dir = None
        if hasattr(injector, 'latest_log_dir') and injector.latest_log_dir:
            log_dir = injector.latest_log_dir
            logger.info(f"Injection log directory: {log_dir}")
            
        if isinstance(result, str):  # If result is a string, it's the USMap path
            logger.info(f"DLL injection successful, USMap path: {result}")
            csv_logger.log_injection_success("Unknown", result, log_dir)
            print(f"DLL injection successful, USMap path: {result}")
        elif result == "timeout":
            logger.error("DLL injection timed out")
            csv_logger.log_injection_timeout("Unknown", log_dir)
            print("DLL injection timed out")
        elif result == "crashed":
            logger.error("DLL injection crashed")
            csv_logger.log_injection_crash("Unknown", "Game process crashed", log_dir)
            print("DLL injection crashed")
        elif result:
            logger.info("DLL injection successful")
            csv_logger.log_injection_success("Unknown", "No USMap path found", log_dir)
            print("DLL injection successful")
        else:
            logger.error("DLL injection failed")
            csv_logger.log_injection_crash("Unknown", "Injection failed", log_dir)
            print("DLL injection failed")
        return
    
    # Otherwise, run the normal game installation process
    try:
        logger.info("脚本启动中...")
        
        # Initialize OCR if enabled in config
        if config['ocr']['enabled']:
            OcrHelper.initialize()

        # Initialize the game controller with the Excel path from config
        controller = SteamOKController(excel_path=config['paths']['results_excel'], screenshot_mgr=screenshot_mgr)
        # Note: Game installation timeout can be configured in config.yaml under timing.installation_timeout
        
        # Initialize the DLL injector
        injector = DLLInjector()
        
        try:
            df = pd.read_excel(config['paths']['test_games_excel'])
            start_index = df.index[df.iloc[:, 2].isna()].tolist()[0] if any(df.iloc[:, 2].isna()) else 0
            games = df.iloc[start_index:, 1].tolist()
            logger.info(f"从第{start_index + 1}行开始加载{len(games)}个游戏")
        except Exception as e:
            logger.error(f"从Excel加载游戏列表时出错: {e}")
            games = []

        for game in games:
            try:
                # Take initial screenshot at game processing start
                screenshot_mgr.take_screenshot(game, "start_processing", min_interval_seconds=0)
                
                # Process the game (download and check if playable)
                result = controller.process_game(game)
                
                # Take screenshot after processing result
                screenshot_mgr.take_screenshot(game, "after_processing", min_interval_seconds=0)
                
                if not result:
                    logger.error(f"Game {game} failed to download or is not playable")
                    csv_logger.log_download_error(game, "Game failed to download or is not playable")
                    print(f"{game}: 不可玩, 未注入DLL")
                    time.sleep(config['timing']['retry_delay'])
                    continue
                
                # Log successful download
                csv_logger.log_download_success(game)
                logger.info(f"Game {game} is playable, download successful")
                
                # Initialize inject_result to False by default
                inject_result = False
                
                # If the game is successfully processed and DLL injection is enabled in config
                if config['dll_injection']['enabled']:
                    # Take screenshot before injection
                    screenshot_mgr.take_screenshot(game, "before_injection", min_interval_seconds=0)
                    
                    logger.info(f"Game {game} is playable, starting DLL injection process...")
                    inject_result = injector.run_injection_process()
                    
                    # Take screenshot after injection
                    screenshot_mgr.take_screenshot(game, "after_injection", min_interval_seconds=0)
                    
                    # Get the latest log directory if available
                    log_dir = None
                    if hasattr(injector, 'latest_log_dir') and injector.latest_log_dir:
                        log_dir = injector.latest_log_dir
                        logger.info(f"Injection log directory for {game}: {log_dir}")
                    
                    if isinstance(inject_result, str):  # If result is a string, it's the USMap path
                        logger.info(f"DLL injection successful for game: {game}, USMap path: {inject_result}")
                        csv_logger.log_injection_success(game, inject_result, log_dir)
                        print(f"{game}: 可玩, 已注入DLL, USMap路径: {inject_result}")
                    elif inject_result == "timeout":
                        logger.error(f"DLL injection timed out for game: {game}")
                        csv_logger.log_injection_timeout(game, log_dir)
                        print(f"{game}: 可玩, DLL注入超时")
                    elif inject_result == "crashed":
                        logger.error(f"Game crashed during injection: {game}")
                        csv_logger.log_injection_crash(game, "Game process crashed", log_dir)
                        print(f"{game}: 可玩, DLL注入时游戏崩溃")
                    elif inject_result:
                        logger.info(f"DLL injection successful for game: {game}, but no USMap path found")
                        csv_logger.log_injection_success(game, "No USMap path found", log_dir)
                        print(f"{game}: 可玩, 已注入DLL")
                    else:
                        logger.error(f"DLL injection failed for game: {game}")
                        csv_logger.log_injection_crash(game, "Injection failed", log_dir)
                        print(f"{game}: 可玩, 未注入DLL")
                else:
                    # If DLL injection is disabled
                    print(f"{game}: 可玩, DLL注入已禁用")
                
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
