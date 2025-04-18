import pyautogui as pg
from cnocr import CnOcr
import logging

logger = logging.getLogger()


class OcrHelper:
    screen_size_x, screen_size_y = pg.size()
    ocr = None

    @classmethod
    def initialize(cls):
        """初始化OCR"""
        if cls.ocr is None:
            try:
                cls.ocr = CnOcr()
            except Exception as e:
                logger.error(f"Error initializing OCR: {e}")
                raise

    # Define region for OCR areas
    FULL_SCREEN = (0, 0, screen_size_x, screen_size_y)
    CENTER_REGION = (int(screen_size_x / 3), int(screen_size_y / 6),
                     int(screen_size_x / 3), int(screen_size_y * 2 / 3))
    SEARCH_BOX_REGION = (int(screen_size_x / 4), int(screen_size_y / 10),
                         int(screen_size_x / 2), int(screen_size_y / 8))
    GAME_LIST_REGION = (int(screen_size_x / 4), int(screen_size_y / 6),
                        int(screen_size_x / 2), int(screen_size_y * 2 / 3))

    @classmethod
    def find_txt_and_click(cls, txt, region=None, click=False, offset=None):
        """查找文字并点击"""
        try:
            if region is None:
                region = cls.FULL_SCREEN
            if isinstance(txt, str):
                txt = [txt]
            screenshot = pg.screenshot(region=region)
            ocr_result = cls.ocr.ocr(screenshot)
            for item in ocr_result:
                text = item['text']
                if any(t.lower() in text.lower() for t in txt):
                    if click:
                        pos = item['position']
                        x = region[0] + (pos[0] + pos[2]) / 2
                        y = region[1] + (pos[1] + pos[3]) / 2
                        if offset:
                            x += offset[0]
                            y += offset[1]
                        pg.moveTo(x, y)
                        pg.click()
                        logger.debug(f"Clicked text: {text} at position ({x}, {y})")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error in find_txt_and_click: {e}")
            return False
