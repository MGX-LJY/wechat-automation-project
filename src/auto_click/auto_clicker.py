# src/auto_click/auto_clicker.py

import webbrowser
import logging
import time
import os
from threading import Thread, Lock

class AutoClicker:
    def __init__(self, error_handler):
        """
        初始化 AutoClicker。

        :param error_handler: 用于处理异常的 ErrorHandler 实例。
        """
        self.error_handler = error_handler
        self.url_queue = []
        self.batch_size = 3
        self.wait_time = 180  # 每批之间等待3分钟（180秒）
        self.processing = False
        self.lock = Lock()  # 用于线程安全地访问队列

    def add_urls(self, urls):
        """
        添加多个URL到队列中。

        :param urls: 要添加的URL列表。
        """
        with self.lock:
            self.url_queue.extend(urls)
            logging.debug(f"添加URL到队列: {urls}")
        # 如果没有在处理队列，启动处理线程
        with self.lock:
            if not self.processing:
                self.processing = True
                Thread(target=self.process_queue, daemon=True).start()
                logging.debug("启动新的处理线程")

    def process_queue(self):
        """
        处理URL队列，分批打开链接。
        """
        try:
            logging.info("开始处理URL队列")
            while True:
                with self.lock:
                    if not self.url_queue:
                        logging.info("URL队列为空，停止处理线程")
                        self.processing = False
                        break
                    # 取出一批链接
                    batch = self.url_queue[:self.batch_size]
                    self.url_queue = self.url_queue[self.batch_size:]
                    logging.info(f"开始处理一批链接，共 {len(batch)} 个")

                for url in batch:
                    self.open_url(url)

                with self.lock:
                    if self.url_queue:
                        logging.info(f"等待 {self.wait_time} 秒后继续处理下一批链接")
                        time.sleep(self.wait_time)
            logging.info("所有链接已处理完毕")
        except Exception as e:
            logging.error(f"处理URL队列时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            with self.lock:
                self.processing = False

    def open_url(self, url):
        """
        打开指定的 URL。

        :param url: 要打开的 URL。
        """
        try:
            logging.info(f"打开URL: {url}")
            webbrowser.get('safari').open(url)
            time.sleep(1)  # 等待Safari打开标签页，防止过快打开
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
