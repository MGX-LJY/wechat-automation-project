# src/auto_click/auto_clicker.py

import webbrowser
import logging

class AutoClicker:
    def __init__(self, error_handler):
        """
        初始化 AutoClicker。

        :param error_handler: 用于处理异常的 ErrorHandler 实例。
        """
        self.error_handler = error_handler

    def open_url(self, url):
        """
        打开指定的 URL。

        :param url: 要打开的 URL。
        """
        try:
            logging.info(f"打开URL: {url}")
            webbrowser.open(url)
        except Exception as e:
            logging.error(f"打开URL时发生错误: {e}")
            self.error_handler.handle_exception(e)
