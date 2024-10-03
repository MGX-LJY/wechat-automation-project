# src/auto_click/auto_clicker.py

import webbrowser
import logging
import time
import os
from threading import Thread

class AutoClicker:
    def __init__(self, error_handler, download_watcher):
        """
        初始化 AutoClicker。

        :param error_handler: 用于处理异常的 ErrorHandler 实例。
        :param download_watcher: 用于监控下载的 DownloadWatcher 实例。
        """
        self.error_handler = error_handler
        self.download_watcher = download_watcher
        self.url_queue = []
        self.batch_size = 3
        self.wait_time = 180  # 每批之间等待3分钟（180秒）
        self.links_clicked = 0
        self.links_before_cleanup = 5
        self.processing = False

    def add_urls(self, urls):
        """
        添加多个URL到队列中。

        :param urls: 要添加的URL列表。
        """
        self.url_queue.extend(urls)
        # 如果没有在处理队列，启动处理线程
        if not self.processing:
            self.processing = True
            Thread(target=self.process_queue).start()

    def process_queue(self):
        """
        处理URL队列，分批打开链接。
        """
        try:
            while self.url_queue:
                # 取出一批链接
                batch = self.url_queue[:self.batch_size]
                self.url_queue = self.url_queue[self.batch_size:]
                logging.info(f"开始处理一批链接，共 {len(batch)} 个")
                for url in batch:
                    self.open_url(url)
                    self.links_clicked += 1
                    # 检查是否需要进行浏览器清理
                    if self.links_clicked % self.links_before_cleanup == 0:
                        logging.info("已点击5个链接，等待下载完成并关闭浏览器")
                # 如果队列还有链接，且不是最后一批，等待指定的时间
                if self.url_queue:
                    logging.info(f"等待 {self.wait_time} 秒后继续处理下一批链接")
                    time.sleep(self.wait_time)
            self.processing = False
        except Exception as e:
            logging.error(f"处理URL队列时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            self.processing = False

    def open_url(self, url):
        """
        打开指定的 URL。

        :param url: 要打开的 URL。
        """
        try:
            logging.info(f"打开URL: {url}")
            webbrowser.get('safari').open(url)
        except Exception as e:
            logging.error(f"打开URL时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def close_safari(self):
        """
        关闭 Safari 浏览器。
        """
        try:
            logging.info("关闭 Safari 浏览器")
            os.system("osascript -e 'tell application \"Safari\" to quit'")
        except Exception as e:
            logging.error(f"关闭 Safari 时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
