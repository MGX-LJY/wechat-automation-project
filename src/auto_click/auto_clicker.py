# src/auto_click/auto_clicker.py

import webbrowser
import logging

class AutoClicker:
    def __init__(self, error_handler):
        """
        初始化 AutoClicker。

        :param error_handler: 用于处理异常的 ErrorHandler 实例。
        """
        self.download_watcher = None
        self.error_handler = error_handler

    def set_download_watcher(self, download_watcher):
        """
        设置下载监控模块。

        :param download_watcher: 下载监控模块的实例。
        """
        self.download_watcher = download_watcher
        logging.debug("下载监控模块已设置")

    def open_url(self, url):
        """
        打开指定的 URL，并调用下载监控模块（如果设置）。

        :param url: 要打开的 URL。
        """
        try:
            logging.info(f"打开URL: {url}")
            webbrowser.open(url)
            logging.debug(f"调用下载监控模块监控下载: {url}")
            if self.download_watcher:
                self.download_watcher.monitor_download(url)
                logging.debug("下载监控已启动")
        except Exception as e:
            logging.error(f"打开URL时发生错误: {e}")
            self.error_handler.handle_exception(e)
