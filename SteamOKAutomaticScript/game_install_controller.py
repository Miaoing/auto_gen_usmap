import logging
import os
import time

import pyautogui as pg
import pygetwindow as gw
import pyperclip
import re
import pandas as pd
import win32gui
from openpyxl import load_workbook
from openpyxl.drawing.image import Image
from license_agreement_handler import LicenseAgreementHandler
from tqdm import tqdm
from image_utils import ImageDetector
from window_utils import activate_window_by_typing, activate_window_by_title, activate_window
from config.config_loader import get_config

logger = logging.getLogger()

# Global variable for screenshot manager - DEPRECATED
# This will be set by main.py when calling process_game
# Now using self.screenshot_mgr inside the SteamOKController class instead

class SteamOKController:
    def __init__(self, excel_path='result/games.xlsx', screenshot_mgr=None):
        self.results = {}  # 存储游戏检查结果
        self.current_game_index = 0  # 当前处理的游戏索引
        self.error_messages = {}  # 存储游戏安装失败的错误信息
        self.excel_path = excel_path  # Excel文件路径
        self.confirm_quit_path = os.path.join(os.path.dirname(__file__), "png/confirm_quit.png")
        self.license_handler = LicenseAgreementHandler()  # 创建许可协议处理器实例
        self.screenshot_mgr = screenshot_mgr  # Store screenshot manager as instance variable
        
        # Load configuration
        self.config = get_config()
        
        # Initialize paths for image detection
        self.steam_ok_not_save_path = os.path.join(os.path.dirname(__file__), "png/steamok_not_save.png")
        
        # Create ImageDetector with default config (we'll just use it for the check_and_click_image method)
        image_detector_config = {
            'dll_injection': {
                'sleep_timings': {'retry_interval': 2},
                'retry_counts': {'default': 5},
                'images': {'steam_ok_not_save_confidence': 0.8}
            }
        }
        self.image_detector = ImageDetector(image_detector_config)
        
        # Installation timeout from config (with fallback to 2 hours = 7200 seconds)
        self.installation_timeout = self.config.get('timing', {}).get('installation_timeout', 7200)
        logger.info(f"Installation timeout set to {self.installation_timeout} seconds ({self.installation_timeout/60:.1f} minutes)")
        
        logger.info(f"SteamOKController initialized with excel_path: {excel_path}")
        if self.screenshot_mgr:
            logger.info("Screenshot manager is configured and ready")
        else:
            logger.info("No screenshot manager provided, using fallback screenshot methods")

    def _format_game_name(self, game_name):
        """格式化游戏名称，只保留中文和英文字母字符"""
        formatted_name = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', game_name)
        logger.debug(f"Formatted game name: {formatted_name} (original: {game_name})")
        return formatted_name

    def activate_steamok_window(self):
        """激活SteamOK窗口并确保它处于最前面"""
        return activate_window("SteamOK", self.config.get('timing', {}))

    def activate_steam_window(self):
        """激活Steam窗口并确保它处于最前面"""
        return activate_window("Steam", self.config.get('timing', {}))

    def search_game(self, game_name):
        try:

            search_box_image = os.path.join(
                os.path.dirname(__file__),
                "png/search_box.png"
            )
            logger.debug(f"Search box image path: {search_box_image}")

            # 尝试提高匹配精度
            search_box_location = pg.locateOnScreen(
                search_box_image,
                confidence=0.7  # 只保留confidence
            )
            if search_box_location:
                search_box_center = (
                    search_box_location[0] + search_box_location[2] / 2,
                    search_box_location[1] + search_box_location[3] / 2
                )
                # 点击搜索框
                pg.click(search_box_center)
                time.sleep(0.5)  # 稍作延迟确保焦点

                # 清空之前的游戏名称
                pg.hotkey('ctrl', 'a')  # 选中输入框中的所有内容
                time.sleep(0.1)  # 等待选中
                pg.press('backspace')  # 清除选中的内容
                time.sleep(0.1)  # 等待清除完成

                # 确保焦点在搜索框内，重新点击搜索框并等待
                pg.click(search_box_center)
                time.sleep(0.5)  # 确保焦点

                # 复制游戏名称到剪贴板
                pyperclip.copy(game_name)
                # 粘贴游戏名
                pg.hotkey('ctrl', 'v')
                pg.press('enter')  # 模拟按下回车键
                time.sleep(2)  # 等待2秒，确保搜索动作完成
                
                # Take debug screenshot with new manager if available
                if self.screenshot_mgr:
                    self.screenshot_mgr.take_screenshot(game_name, "search_results", min_interval_seconds=0)
                else:
                    # Original screenshot code - kept for backward compatibility
                    windows = gw.getWindowsWithTitle("SteamOK")
                    if not windows:
                        logger.error("SteamOK window not found")
                        return False

                    window = None
                    for w in windows:
                        if w.title == "SteamOK":  # 精确匹配标题
                            window = w
                            break

                    if not window:
                        logger.error("No window with exact 'SteamOK' title found")
                        return False

                    screenshot = pg.screenshot(region=(window.left, window.top, window.width, window.height))
                    formatted_name = self._format_game_name(game_name)
                    game_dir = f"screenshots/{formatted_name}"
                    os.makedirs(game_dir, exist_ok=True)
                    screenshot_path = f"{game_dir}/search.png"
                    screenshot.save(screenshot_path)
                    logger.info(f"Search screenshot saved to: {screenshot_path}")
                
                return True
            else:
                logger.error("Search box not found via image")
                # Take debug screenshot even when search box not found
                if self.screenshot_mgr:
                    self.screenshot_mgr.take_screenshot(game_name, "search_box_not_found", min_interval_seconds=0)
                else:
                    screenshot = pg.screenshot()
                    screenshot.save("debug_search_box_not_found.png")
                return False

        except Exception as e:
            logger.error(f"Error searching game: {str(e)}", exc_info=True)
            return False

    def find_game_list_header_location(self):
        """通过OCR找到游戏列表的表头位置"""
        try:
            # 读取游戏列表表头截图
            game_list_header_image = os.path.join(
                os.path.dirname(__file__),
                "png/game_list.png"
            )
            # 尝试提高匹配精度
            game_list_header_location = pg.locateOnScreen(
                game_list_header_image,
                confidence=0.65  # 只保留confidence
            )
            if game_list_header_location:
                game_list_header_center = (
                    game_list_header_location[0] + game_list_header_location[2] / 2,
                    game_list_header_location[1] + game_list_header_location[3] / 2
                )
                return game_list_header_center
            else:
                logger.error("Game list header not found via image")
                return None
        except Exception as e:
            logger.error(f"Error finding game list header")
            return None

    def click_first_result(self, game_name):
        """点击第一个搜索结果"""
        try:
            time.sleep(0.5)  # 等待搜索结果加载

            # 通过OCR找到游戏列表表头的位置
            header_location = self.find_game_list_header_location()
            if header_location:
                header_x, header_y = header_location
                # 点击表头下方的位置，假设第一个游戏就位于下方
                first_game_y = header_y + 50  # 调整偏移量，使得点击下方的第一个游戏
                pg.click(header_x, first_game_y)  # 点击第一个游戏
                logger.info(f"Clicked first result for game: {game_name}")
                time.sleep(1)  # 等待游戏详情页加载
                
                # Take debug screenshot 
                if self.screenshot_mgr:
                    self.screenshot_mgr.take_screenshot(game_name, "game_details", min_interval_seconds=0)
                
                return True
            else:
                logger.error(f"Failed to find game list header for game: {game_name}")
                return False
        except Exception as e:
            logger.error(f"Error clicking first result: {str(e)}", exc_info=True)
            return False

    def check_play_button(self):
        """检查并点击'马上开玩'按钮"""
        try:
            # 尝试通过OCR识别 '马上开玩' 按钮
            play_button_image = os.path.join(os.path.dirname(__file__), "png/play.png")
            play_button_location = pg.locateOnScreen(play_button_image, confidence=0.9)  # 提高精度

            if play_button_location:
                # 找到按钮，点击按钮中心
                play_button_center = (
                    play_button_location[0] + play_button_location[2] / 2,
                    play_button_location[1] + play_button_location[3] / 2
                )
                # 调整点击位置以增加偏移量，可以微调这部分
                play_button_center = (play_button_center[0], play_button_center[1] + 10)  # 向下移动10个像素

                pg.click(play_button_center)
                time.sleep(1)
                logger.info("Clicked '马上玩' button")
                return True
            else:
                logger.error("'马上玩' button not found")
                return False

        except Exception as e:
            logger.error(f"Error checking play button")
            return False

    def confirm_start_game(self):
        """检查并点击确认按钮"""
        try:
            # 尝试通过OCR识别确认按钮
            confirm_button_image = os.path.join(os.path.dirname(__file__), "png/confirm_button.png")
            confirm_button_location = pg.locateOnScreen(confirm_button_image, confidence=0.84)  # 提高精度

            if confirm_button_location:
                # 找到确认按钮，点击按钮中心
                confirm_button_center = (
                    confirm_button_location[0] + confirm_button_location[2] / 2,
                    confirm_button_location[1] + confirm_button_location[3] / 2
                )
                # 调整点击位置以增加偏移量，可以微调这部分
                # confirm_button_center = (confirm_button_center[0], confirm_button_center[1] + 10)  # 向下移动10个像素

                pg.click(confirm_button_center)
                time.sleep(1)
                logger.info("Clicked '确认' button")
                return True
            else:
                logger.error("'确认' button not found")
                return False

        except Exception as e:
            logger.error(f"Error confirming start game")
            return False

    def click_install_button(self):
        """点击安装按钮"""
        try:
            logger.info("Starting installation button click process")
            time.sleep(1)
            
            install_button_image = os.path.join(os.path.dirname(__file__), "png/install.png")
            reinstall_button_image = os.path.join(os.path.dirname(__file__), "png/reInstall.png")
            
            logger.debug("Searching for install/reinstall buttons...")
            install_button_location = None
            reinstall_button_location = None

            try:
                install_button_location = pg.locateOnScreen(install_button_image, confidence=0.9)
            except Exception as e:
                logger.warning("Install button not found, will retry later")

            if install_button_location is None:
                try:
                    reinstall_button_location = pg.locateOnScreen(reinstall_button_image, confidence=0.9)
                except Exception as e:
                    logger.debug("Reinstall button not found")
                
                time.sleep(2)
                
                if reinstall_button_location:
                    logger.info("Found reinstall button, clicking...")
                    reinstall_button_center = (
                        reinstall_button_location[0] + reinstall_button_location[2] / 2,
                        reinstall_button_location[1] + reinstall_button_location[3] / 2
                    )
                    pg.click(reinstall_button_center)
                    time.sleep(10)
                    logger.info("Clicked reinstall button successfully")
                    
                    try:
                        install_button_location = pg.locateOnScreen(install_button_image, confidence=0.8)
                    except Exception as e:
                        logger.warning("Install button not found after reinstall")
                    
                    if install_button_location:
                        logger.info("Found install button after reinstall")
                    else:
                        logger.warning("Install button not found after reinstall, continuing with download")
                        return True

            if install_button_location:
                logger.info("Found install button, clicking...")
                install_button_center = (
                    install_button_location[0] + (install_button_location[2]) / 2,
                    install_button_location[1] + (install_button_location[3]) / 2
                )
                logger.debug(f"Button center coordinates: {install_button_center}")
                pg.click(install_button_center)
                logger.info("Clicked install button successfully")
                time.sleep(5)

                logger.debug("Checking for license agreement accept button...")
                accept_button_image = os.path.join(os.path.dirname(__file__), "png/accept.png")
                try:
                    accept_button_location = pg.locateOnScreen(accept_button_image, confidence=0.8)
                except Exception as e:
                    accept_button_location = None

                if accept_button_location:
                    time.sleep(5)
                    accept_button_center = (
                        accept_button_location[0] + accept_button_location[2] / 2,
                        accept_button_location[1] + accept_button_location[3] / 2
                    )
                    pg.click(accept_button_center)
                    time.sleep(3)
                    logger.info("Clicked license agreement accept button")
                else:
                    logger.info("No license agreement accept button found, continuing")

                return True
            else:
                logger.error("Install button not found, please check button images or interface")
                return False

        except Exception as e:
            logger.error(f"Error during install button click process: {str(e)}", exc_info=True)
            return False

    def move_steamok_to_background(self):
        """将SteamOK窗口移到后台"""
        try:
            windows = gw.getWindowsWithTitle("SteamOK")
            if not windows:
                logger.error("SteamOK window not found")
                return False

            for window in windows:
                if window.title == "SteamOK":
                    window.minimize()  # 将SteamOK窗口最小化，移到后台
                    logger.info("SteamOK window minimized and moved to background")
                    return True
        except Exception as e:
            logger.error(f"Error minimizing SteamOK window")
            return False

    def move_game_to_background(self):
        """将游戏窗口移到后台"""
        try:
            # 获取所有窗口标题
            windows = gw.getAllWindows()
            if not windows:
                logger.error("No windows found")
                return False

            for window in windows:
                # 排除Steam和SteamOK窗口
                if window.title != "Steam" and window.title != "SteamOK" and window.title:
                    window.minimize()  # 将游戏窗口最小化，移到后台
                    logger.info(f"Game window '{window.title}' minimized and moved to background")
                    return True

            logger.error("No game window found")
            return False
        except Exception as e:
            logger.error(f"Error minimizing game window: {e}")
            return False

    def check_installation_complete(self, game_name=None):
        """持续检测安装完成状态，失败后继续检测，有超时限制"""
        playable_image = os.path.join(os.path.dirname(__file__), "png/playable.png")
        playable2_image = os.path.join(os.path.dirname(__file__), "png/playable2.png")

        # Record start time for timeout tracking
        start_time = time.time()
        check_count = 0
        last_progress_update = ""
        
        # Get timeout in minutes for display purposes
        timeout_minutes = self.installation_timeout / 60
        
        logger.info(f"⏳ 开始监控安装进度 ({timeout_minutes:.1f}分钟超时限制)")
        
        while True:
            try:
                # Check if we've exceeded the timeout
                elapsed_time = time.time() - start_time
                if elapsed_time > self.installation_timeout:
                    logger.error(f"Installation timeout after {elapsed_time:.1f} seconds ({timeout_minutes:.1f} minute limit)")
                    return False
                
                # Only log every 6 checks (approximately every minute) to reduce console output
                check_count += 1
                should_log = (check_count % 6 == 0)
                
                if not self.activate_steam_window():
                    if should_log:
                        logger.warning("激活Steam窗口失败，5秒后重试...")
                    time.sleep(5)
                    continue

                try:
                    # 同时检测两个图标
                    playable2_location = None
                    playable_location = None
                    
                    try:
                        playable2_location = pg.locateOnScreen(playable2_image, confidence=0.72)
                        if should_log:
                            logger.debug(f"playable2图标检测成功")
                    except Exception as e:
                        if should_log and check_count > 12:  # Only log after 2 minutes
                            logger.debug(f"playable2图标检测失败")                    
                    try:
                        playable_location = pg.locateOnScreen(playable_image, confidence=0.88)
                        if should_log:
                            logger.debug(f"playable图标检测成功")
                    except Exception as e:
                        if should_log and check_count > 12:  # Only log after 2 minutes
                            logger.debug(f"playable图标检测失败")

                    # 轻微移动Steam窗口以防止睡眠
                    windows = gw.getWindowsWithTitle("Steam")
                    if windows:
                        for window in windows:
                            if window.title == "Steam":
                                pg.click(window.left + 5, window.top + 5)
                                time.sleep(1)
                                break

                    # 任意一个图标检测到就返回True
                    if playable2_location or playable_location:
                        elapsed_min = elapsed_time / 60
                        logger.info(f"✅ 检测到安装完成，用时 {elapsed_min:.1f} 分钟")
                        return True

                except Exception as e:
                    if should_log and check_count > 12:  # Only log after 2 minutes
                        logger.debug(f"图像识别失败: {str(e)}")

                # Only log periodically to reduce console output
                if should_log:
                    elapsed_min = elapsed_time / 60
                    progress_percent = min(int((elapsed_min / timeout_minutes) * 100), 99)
                    
                    # Create a progress bar-like indicator 
                    progress_indicator = f"[{'=' * int(progress_percent/5)}{'>' if progress_percent < 99 else '='}{'.' * (20-int(progress_percent/5))}]"
                    
                    # Create a clean progress message
                    current_progress = f"⏳ 安装进度: {progress_indicator} {progress_percent}% ({elapsed_min:.1f}/{timeout_minutes:.1f}分钟)"
                    
                    # Only print if the message has changed
                    if current_progress != last_progress_update:
                        logger.info(current_progress)
                        last_progress_update = current_progress
                        
                        # Take an occasional progress screenshot
                        if self.screenshot_mgr and game_name and (progress_percent % 20 == 0):
                            self.screenshot_mgr.take_screenshot(game_name, f"progress_{progress_percent}pct", min_interval_seconds=1200)
                
                time.sleep(10)

            except Exception as e:
                if check_count % 6 == 0:  # Only log every 6 checks
                    logger.error(f"检测出错: {str(e)}，10秒后重试")
                time.sleep(10)

    def check_and_click_not_save_button(self):
        """Check for and click the 'Not Save' button if it appears"""
        logger.info("Checking for 'Not Save' button...")
        result = self.image_detector.check_and_click_image(
            image_path=self.steam_ok_not_save_path,
            max_retries=3,
            confidence=0.8
        )
        
        if result:
            logger.info("'Not Save' button found and clicked successfully")
        else:
            logger.info("'Not Save' button was not found or could not be clicked (this is normal if the dialog isn't shown)")
            
        return result

    def process_game(self, game_name):
        """处理单个游戏的完整流程"""
        try:
            logger.info(f"Starting game processing: {game_name}")
            
            self.license_handler.start()
            logger.debug("License agreement handler started")

            if not self.activate_steamok_window():
                error_msg = "Failed to activate SteamOK window"
                logger.error(f"{error_msg} for game: {game_name}")
                self._handle_game_error(game_name, error_msg)
                return False
            
            # Check for and click "Not Save" button if it appears
            if self.check_and_click_not_save_button():
                # If button was found and clicked, give it a moment to process
                time.sleep(1.5)
            
            if not self.search_game(game_name):
                error_msg = "Failed to search game"
                logger.error(f"{error_msg}: {game_name}")
                self._handle_game_error(game_name, error_msg)
                return False

            if not self.click_first_result(game_name):
                error_msg = "Failed to click first result"
                logger.error(f"{error_msg} for game: {game_name}")
                self._handle_game_error(game_name, error_msg)
                return False

            if not self.check_play_button():
                error_msg = "Failed to click play button"
                logger.error(f"{error_msg} for game: {game_name}")
                self._handle_game_error(game_name, error_msg)
                return False

            if not self.confirm_start_game():
                error_msg = "Failed to click confirmation button"
                logger.error(f"{error_msg} for game: {game_name}")
                self._handle_game_error(game_name, error_msg)
                return False

            # Take screenshot right after confirming game start
            if self.screenshot_mgr:
                self.screenshot_mgr.take_screenshot(game_name, "after_start_game", min_interval_seconds=0)

            logger.info("Waiting 40 seconds for game startup...")
            for _ in tqdm(range(40), desc="Waiting for game startup"):
                time.sleep(1)
            
            logger.info("Waiting for game to start...")
            while not self.move_steamok_to_background() and not self.activate_steam_window():
                logger.warning("Failed to activate Steam window, retrying...")
                time.sleep(5)
                continue

            success = False
            for attempt in range(10):
                logger.info(f"Attempt {attempt + 1}/10...")
                
                if not self.move_steamok_to_background():
                    logger.warning("Failed to minimize SteamOK window")
                    
                if not self.activate_steam_window():
                    logger.warning("Failed to activate Steam window, retrying...")
                    time.sleep(5)
                    continue
                
                if not self.move_steamok_to_background():
                    logger.warning("Failed to minimize SteamOK window")
                elif self.click_install_button():
                    logger.info("Successfully clicked install button")
                    
                    # Take screenshot after clicking install
                    if self.screenshot_mgr:
                        self.screenshot_mgr.take_screenshot(game_name, "after_install_click", min_interval_seconds=0)
                        
                    if self.check_installation_complete(game_name):
                        logger.info("Game installation completed successfully")
                        success = True
                        break
                    else:
                        timeout_minutes = self.installation_timeout / 60
                        error_msg = f"Installation timeout after {timeout_minutes:.1f} minutes"
                        logger.error(error_msg)
                        self._handle_game_error(game_name, error_msg)
                        return False
                
                time.sleep(5)

            if not success:
                error_msg = "Timeout: Failed to complete installation after 10 attempts"
                logger.error(error_msg)
                self._handle_game_error(game_name, error_msg)
                return False

            self.results[game_name] = True
            self._save_game_result(game_name, True)
            logger.info(f"Successfully processed game: {game_name}")
            return True

        except Exception as e:
            logger.error(f"Error processing game {game_name}: {str(e)}", exc_info=True)
            self._handle_game_error(game_name, str(e))
            return False

    def _handle_game_error(self, game_name, error_msg):
        """Handle game processing errors consistently"""
        self.results[game_name] = False
        self.error_messages[game_name] = error_msg
        
        # Don't use print, use logger instead
        logger.error(f"Game processing failed: {game_name} - {error_msg}")
        
        # Save the result to CSV/Excel
        self._save_game_result(game_name, False, error_msg)
        self.license_handler.stop()

    def _save_game_result(self, game_name, available, error_msg=None):
        """保存单个游戏的检查结果到Excel文件"""
        try:
            df = pd.read_excel(self.excel_path)
            game_index = df.index[df.iloc[:, 1] == game_name].tolist()
            
            # Get current timestamp for logging
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            
            if game_index:
                # Update availability status (column 2)
                df.iloc[game_index[0], 2] = "是" if available else "否"
                
                # If not available, update error message column
                if not available and error_msg:
                    # Format error message with timestamp for timeout errors
                    if "timeout" in error_msg.lower():
                        timeout_minutes = self.installation_timeout / 60
                        error_with_time = f"[{timestamp}] 安装超时({timeout_minutes:.1f}分钟): {error_msg}"
                        df.iloc[game_index[0], 3] = error_with_time
                    else:
                        error_with_time = f"[{timestamp}] {error_msg}"
                        df.iloc[game_index[0], 3] = error_with_time
                
                # Update timestamp column if it exists (assuming it's column 4)
                if df.shape[1] > 4:  
                    df.iloc[game_index[0], 4] = timestamp

            # Save the updated Excel file
            df.to_excel(self.excel_path, index=False)
            logger.info(f"Saved result for {game_name} to {self.excel_path}")

            # Also save to text file as backup
            os.makedirs(os.path.dirname(self.excel_path), exist_ok=True)
            txt_path = os.path.join(os.path.dirname(self.excel_path), 'game_results.txt')
            with open(txt_path, 'a', encoding='utf-8') as f:
                status = "可以开玩" if available else "不可开玩"
                error_info = f" (错误: {error_msg}, 时间: {timestamp})" if not available and error_msg else ""
                f.write(f"{game_name}: {status}{error_info}\n")

        except Exception as e:
            logger.error(f"Error saving result for {game_name}: {str(e)}")

    def save_results(self):
        """保存检查结果到Excel文件"""
        try:
            df = pd.read_excel(self.excel_path)
            for game, available in self.results.items():
                # 在Excel中找到对应的游戏行
                game_index = df.index[df.iloc[:, 0] == game].tolist()
                if game_index:
                    # 更新游戏状态（第二列）
                    df.iloc[game_index[0], 1] = "是" if available else "否"
                    # 如果游戏安装失败，在第三列记录错误信息
                    if not available and game in self.error_messages:
                        df.iloc[game_index[0], 2] = self.error_messages[game]

            # 保存更新后的Excel文件
            df.to_excel(self.excel_path, index=False)
            logger.info(f"Results saved to {self.excel_path}")
            
            # 同时保存到txt文件作为备份
            txt_path = os.path.join(os.path.dirname(self.excel_path), 'game_results.txt')
            with open(txt_path, 'w', encoding='utf-8') as f:
                for game, available in self.results.items():
                    status = "可以开玩" if available else "不可开玩"
                    error_info = f" (错误: {self.error_messages[game]})" if not available and game in self.error_messages else ""
                    f.write(f"{game}: {status}{error_info}\n")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")
