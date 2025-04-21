import logging
import os
import time

import pyautogui as pg
import pygetwindow as gw
import pyperclip
import re
import pandas as pd
from openpyxl import load_workbook
from openpyxl.drawing.image import Image

logger = logging.getLogger()


class SteamOKController:
    def __init__(self, excel_path='result/games.xlsx'):
        self.results = {}  # 存储游戏检查结果
        self.current_game_index = 0  # 当前处理的游戏索引
        self.error_messages = {}  # 存储游戏安装失败的错误信息
        self.excel_path = excel_path  # Excel文件路径

    def _format_game_name(self, game_name):
        """格式化游戏名称，只保留中文和英文字母字符"""
        # 使用正则表达式只保留中文、英文字母和数字
        formatted_name = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', game_name)
        return formatted_name

    def activate_steamok_window(self):
        """激活SteamOK窗口并确保它处于最前面"""
        try:
            # 获取所有窗口标题
            windows = gw.getWindowsWithTitle("SteamOK")
            if not windows:
                logger.error("SteamOK window not found")
                return False

            for window in windows:
                if window.title == "SteamOK":  # 精确匹配标题
                    logger.info(f"Found exact match for SteamOK window: {window.title}")
                    window.restore()
                    time.sleep(0.3)
                    window.activate()
                    time.sleep(0.3)

                    pg.click(window.left + 10, window.top + 10)
                    logger.info("SteamOK window activated and brought to front")
                    return True

            logger.error("No window with exact 'SteamOK' title found")
            return False
        except Exception as e:
            logger.error(f"Error activating SteamOK window")
            return False

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
                
                # 获取并保存搜索结果的截图
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
                pg.click(header_x, first_game_y)
                time.sleep(0.5)
                
                # 获取并保存点击后的截图
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
                # 获取并保存点击后的截图
                screenshot = pg.screenshot(region=(window.left, window.top, window.width, window.height))
                formatted_name = self._format_game_name(game_name)
                game_dir = f"screenshots/{formatted_name}"
                os.makedirs(game_dir, exist_ok=True)
                screenshot_path = f"{game_dir}/detail.png"
                screenshot.save(screenshot_path)
                
                # 更新Excel文件
                try:
                    df = pd.read_excel(self.excel_path)
                    df.iloc[self.current_game_index, 2] = screenshot_path
                    df.to_excel(self.excel_path, index=False)
                except Exception as e:
                    logger.error(f"Error updating Excel with detail screenshot: {e}")
                
                return True
            else:
                logger.error("Game list header not found")
                return False
        except Exception as e:
            logger.error(f"Error clicking first result: {e}")
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
            logger.info("开始尝试点击安装按钮流程")
            time.sleep(1)
            
            # 尝试通过OCR识别安装按钮和reinstall按钮
            install_button_image = os.path.join(os.path.dirname(__file__), "png/install.png")
            reinstall_button_image = os.path.join(os.path.dirname(__file__), "png/reInstall.png")
            
            logger.info("尝试寻找安装按钮和reinstall按钮...")
            install_button_location = None
            reinstall_button_location = None
            
            try:
                install_button_location = pg.locateOnScreen(install_button_image, confidence=0.9)
            except Exception as e:
                logger.warning("未找到安装按钮，将在后续重试")
                
            try:
                reinstall_button_location = pg.locateOnScreen(reinstall_button_image, confidence=0.9)
            except Exception as e:
                logger.debug("未找到reinstall按钮")
            
            time.sleep(2)
            
            # 如果找到reinstall按钮，优先点击它
            if reinstall_button_location:
                logger.info("找到reinstall按钮，优先点击")
                reinstall_button_center = (
                    reinstall_button_location[0] + reinstall_button_location[2] / 2,
                    reinstall_button_location[1] + reinstall_button_location[3] / 2
                )
                pg.click(reinstall_button_center)
                time.sleep(3)
                logger.info("已点击reinstall按钮")
                
                # 重新检查安装按钮
                try:
                    install_button_location = pg.locateOnScreen(install_button_image, confidence=0.8)
                except Exception as e:
                    logger.warning("重新检查时未找到安装按钮")
                
                return True
            
            # 如果找到安装按钮，点击它
            if install_button_location:
                logger.info("找到安装按钮")
                install_button_center = (
                    install_button_location[0] + (install_button_location[2]) / 2,
                    install_button_location[1] + (install_button_location[3]) / 2
                )
                logger.debug(f"按钮中心坐标：{install_button_center}")
                pg.click(install_button_center)
                logger.info("已点击安装按钮")
                time.sleep(5)

                # 检测许可协议的accept按钮
                logger.info("开始检查是否存在许可协议accept按钮...")
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
                    logger.info("已点击许可协议的accept按钮")
                else:
                    logger.info("未找到许可协议accept按钮，继续执行")

                return True
            else:
                logger.error("未找到安装按钮，请检查按钮图片是否正确或界面是否正确显示")
                return False

        except Exception as e:
            logger.error(f"点击安装按钮过程出错: {str(e)}", exc_info=True)
            return False

    def activate_steam_window(self):
        """激活Steam窗口并确保它处于最前面"""
        try:
            # 获取所有窗口标题
            windows = gw.getWindowsWithTitle("Steam")
            if not windows:
                logger.error("Steam window not found")
                return False

            for window in windows:
                if window.title == "Steam":
                    window.restore()  # 恢复窗口，如果它最小化了
                    window.activate()  # 激活并确保窗口处于最前面
                    logger.info("Steam window activated and brought to front")
                    return True

            logger.error("No window with exact 'Steam' title found")
            return False

        except Exception as e:
            logger.error(f"Error activating Steam window")
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

    def check_installation_complete(self):
        """持续检测安装完成状态，失败后继续检测"""
        playable_image = os.path.join(os.path.dirname(__file__), "png/playable.png")
        playable2_image = os.path.join(os.path.dirname(__file__), "png/playable2.png")

        while True:
            try:
                if not self.activate_steam_window():
                    logger.warning("激活Steam窗口失败，5秒后重试...")
                    time.sleep(5)
                    continue

                try:
                    # 同时检测两个图标
                    playable2_location = None
                    playable_location = None
                    
                    try:
                        playable2_location = pg.locateOnScreen(playable2_image, confidence=0.72)
                        logger.debug(f"playable2图标检测成功")
                    except Exception as e:
                        logger.debug(f"playable2图标检测失败")                    
                    try:
                        playable_location = pg.locateOnScreen(playable_image, confidence=0.88)
                        logger.debug(f"playable图标检测成功")
                    except Exception as e:
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
                        logger.info("✅ 检测到安装完成")
                        return True

                except Exception as e:
                    logger.debug(f"图像识别失败: {str(e)}", exc_info=True)

                logger.info("⏳ 安装尚未完成，5秒后重试...")
                time.sleep(5)

            except Exception as e:
                logger.error(f"检测出错: {str(e)}，10秒后重试", exc_info=True)
                time.sleep(10)

    def process_game(self, game_name):
        """处理单个游戏的完整流程"""
        try:
            logger.info(f"Processing game: {game_name}")

            # 将SteamOK窗口移到最前面
            if not self.activate_steamok_window():
                error_msg = "Failed to activate SteamOK window"
                logger.error(f"{error_msg} for game: {game_name}")
                self.results[game_name] = False
                self.error_messages[game_name] = error_msg
                self._save_game_result(game_name, False, error_msg)
                return False

            # 搜索游戏
            if not self.search_game(game_name):
                error_msg = "Failed to search game"
                logger.error(f"{error_msg}: {game_name}")
                self.results[game_name] = False
                self.error_messages[game_name] = error_msg
                self._save_game_result(game_name, False, error_msg)
                return False

            # 点击第一个结果
            if not self.click_first_result(game_name):
                error_msg = "Failed to click first result"
                logger.error(f"{error_msg} for game: {game_name}")
                self.results[game_name] = False
                self.error_messages[game_name] = error_msg
                self._save_game_result(game_name, False, error_msg)
                return False

            # 检查并点击"马上玩"按钮
            if not self.check_play_button():
                error_msg = "Failed to click '马上玩' button"
                logger.error(f"{error_msg} for game: {game_name}")
                self.results[game_name] = False
                self.error_messages[game_name] = error_msg
                self._save_game_result(game_name, False, error_msg)
                return False

            # 检查并点击确认按钮
            if not self.confirm_start_game():
                error_msg = "Failed to click confirmation button"
                logger.error(f"{error_msg} for game: {game_name}")
                self.results[game_name] = False
                self.error_messages[game_name] = error_msg
                self._save_game_result(game_name, False, error_msg)
                return False

            # 最多尝试10次点击安装按钮
            install_success = False
            for attempt in range(10):
                logger.info(f"第{attempt + 1}次尝试点击安装按钮，等待50秒...")

                # 最小化SteamOK窗口
                if not self.move_steamok_to_background():
                    logger.warning("最小化SteamOK窗口失败...")
                    continue

                # 尝试点击安装按钮
                if self.click_install_button():
                    logger.info("成功检测并点击安装按钮")
                    install_success = True
                    break
                time.sleep(10)


            # 10次尝试后仍未成功
            if not install_success:
                error_msg = "超时错误：10次尝试后仍未能成功点击安装按钮"
                logger.error(error_msg)
                self.error_messages[game_name] = error_msg
                self._save_game_result(game_name, False, error_msg)
                return False

            # 等待安装完成
            if not self.check_installation_complete():
                error_msg = "Installation process failed or timed out"
                logger.error(f"{error_msg} for game: {game_name}")
                self.results[game_name] = False
                self.error_messages[game_name] = error_msg
                self._save_game_result(game_name, False, error_msg)
                return False

            # time.sleep(5)
            # logger.info("游戏安装完成，开始进行打包")

            # 游戏安装完成后，立即进行打包
            # from game_packer import GamePacker
            # packer = GamePacker()
            # if not packer.process_latest_game(game_name):
            #     error_msg = "Game packing failed after installation"
            #     logger.error(f"{error_msg} for game: {game_name}")
            #     self.results[game_name] = False
            #     self.error_messages[game_name] = error_msg
            #     self._save_game_result(game_name, False, error_msg)
            #     return False

            self.results[game_name] = True
            logger.info(f"Successfully processed game: {game_name}")
            self._save_game_result(game_name, True)
            return True

        except Exception as e:
            error_msg = f"Error processing game: {str(e)}"
            logger.error(error_msg)
            self.results[game_name] = False
            self.error_messages[game_name] = error_msg
            self._save_game_result(game_name, False, error_msg)
            return False

    def _save_game_result(self, game_name, available, error_msg=None):
        """保存单个游戏的检查结果到Excel文件"""
        try:
            # 使用pandas更新基本信息
            df = pd.read_excel(self.excel_path)
            game_index = df.index[df.iloc[:, 1] == game_name].tolist()
            if game_index:
                # 更新游戏状态（第三列）
                df.iloc[game_index[0], 2] = "是" if available else "否"
                # 如果游戏安装失败，在第四列记录错误信息
                if not available and error_msg:
                    df.iloc[game_index[0], 3] = error_msg

            # 保存更新后的Excel文件
            df.to_excel(self.excel_path, index=False)
            logger.info(f"Result saved to {self.excel_path} for game: {game_name}")

            # 同时保存到txt文件作为备份
            os.makedirs(os.path.dirname(self.excel_path), exist_ok=True)
            txt_path = os.path.join(os.path.dirname(self.excel_path), 'game_results.txt')
            with open(txt_path, 'a', encoding='utf-8') as f:
                status = "可以开玩" if available else "不可开玩"
                error_info = f" (错误: {error_msg})" if not available and error_msg else ""
                f.write(f"{game_name}: {status}{error_info}\n")

        except Exception as e:
            logger.error(f"Error saving result for game {game_name}: {e}")

    def save_results(self):
        """保存检查结果到Excel文件"""
        try:
            df = pd.read_excel(self.excel_path)
            for game, available in self.results.items():
                # 在Excel中找到对应的游戏行
                game_index = df.index[df.iloc[:, 0] == game].tolist()
                if game_index:
                    # 更新游戏状态（第二列）
                    df.iloc[game_index[0], 1] = "是" if result else "否"
                    # 如果游戏安装失败，在第三列记录错误信息
                    if not result and game_name in self.error_messages:
                        df.iloc[game_index[0], 2] = self.error_messages[game_name]

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
