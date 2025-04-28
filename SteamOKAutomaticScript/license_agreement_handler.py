import threading
import time
import logging
import pyautogui as pg
import os

logger = logging.getLogger()

class LicenseAgreementHandler:
    def __init__(self):
        self.running = False
        self.thread = None
        # 定义所有可能的接受按钮图片
        self.accept_button_images = [
            os.path.join(os.path.dirname(__file__), "png/steam_accept_button.png"),
            os.path.join(os.path.dirname(__file__), "png/accept2.png")
        ]
        self.check_interval = 2  # 检查间隔（秒）

    def _check_and_accept_license(self):
        """检查并点击许可协议接受按钮"""
        try:
            for accept_image in self.accept_button_images:
                try:
                    accept_button_location = pg.locateOnScreen(accept_image, confidence=0.8)
                    if accept_button_location:
                        accept_button_center = (
                            accept_button_location[0] + accept_button_location[2] / 2,
                            accept_button_location[1] + accept_button_location[3] / 2
                        )
                        pg.click(accept_button_center)
                        logger.info(f"检测到并点击了许可协议接受按钮: {os.path.basename(accept_image)}")
                        time.sleep(1)  # 点击后等待1秒
                        return True  # 如果找到一个并点击成功，就返回
                except Exception as e:
                    # logger.debug(f"检查许可协议按钮 {os.path.basename(accept_image)} 时出错: {str(e)}")
                    continue  # 继续检查下一个按钮
            return False
        except Exception as e:
            logger.debug(f"检查许可协议时出错: {str(e)}")
            return False

    def _monitor_license_agreement(self):
        """后台线程持续监控许可协议"""
        while self.running:
            self._check_and_accept_license()
            time.sleep(self.check_interval)

    def start(self):
        """启动许可协议监控线程"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._monitor_license_agreement)
            self.thread.daemon = True  # 设置为守护线程，主程序退出时自动结束
            self.thread.start()
            logger.info("启动许可协议监控线程")

    def stop(self):
        """停止许可协议监控线程"""
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join(timeout=1)
            logger.info("停止许可协议监控线程") 