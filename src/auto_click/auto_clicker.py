import logging
import time
import threading
from src.auto_download.auto_download import XKW  # 导入 XKW 类
import sys


class ErrorHandler:
    def handle_exception(self, exception):
        # 示例错误处理，可以根据需求扩展
        logging.error(f"ErrorHandler 捕获到异常: {exception}", exc_info=True)


class AutoClicker:
    def __init__(self, error_handler=None, download_dir=None):
        """
        初始化 AutoClicker。

        :param error_handler: 用于处理异常的 ErrorHandler 实例。
        :param download_dir: 下载文件的目标目录。
        """
        self.error_handler = error_handler or ErrorHandler()
        self.opened_count = 0
        self.timer_running = False
        self.count_lock = threading.Lock()

        # 初始化日志记录器
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # 初始化 XKW 实例，用于处理下载任务
        self.downloader = XKW(
            thread=3,  # 根据需要调整线程数
            work=True,
            download_dir=download_dir,  # 传递下载目录
        )
        logging.info("AutoDownload (XKW) 实例已初始化。")

    def open_url(self, url):
        """
        打开指定的 URL，并进行计数控制，同时将下载任务添加到 downloader。

        :param url: 要打开的 URL。
        """
        try:
            logging.info(f"准备处理URL: {url}")
            # 将下载任务添加到 downloader，由 downloader 负责打开和下载
            self.downloader.add_task(url)
            logging.info(f"已将URL添加到下载任务队列: {url}")
        except Exception as e:
            logging.error(f"处理URL时发生未知错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def add_urls(self, urls):
        """
        添加多个 URL 到下载任务队列。

        :param urls: 包含多个 URL 的列表或可迭代对象。
        """
        try:
            logging.info(f"准备批量添加 {len(urls)} 个 URL 到下载任务队列。")
            for url in urls:
                self.downloader.add_task(url)
            logging.info(f"已批量添加 {len(urls)} 个 URL 到下载任务队列。")
        except Exception as e:
            logging.error(f"批量添加 URL 时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def add_task(self, url):
        """
        添加单个 URL 到下载任务队列。

        :param url: 要添加的单个 URL。
        """
        try:
            logging.info(f"准备添加单个 URL 到下载任务队列: {url}")
            self.downloader.add_task(url)
            logging.info(f"已添加单个 URL 到下载任务队列: {url}")
        except Exception as e:
            logging.error(f"添加单个 URL 时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def stop(self):
        """
        停止 AutoClicker 和其内部的 XKW 实例。
        """
        try:
            logging.info("停止 AutoClicker 和 XKW 实例。")
            self.downloader.stop()
        except Exception as e:
            logging.error(f"停止过程中出错: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
