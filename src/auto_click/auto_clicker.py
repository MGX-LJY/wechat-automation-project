# src/auto_click/auto_clicker.py

import webbrowser
import logging
import time
import os
import threading
from queue import Queue, Empty

class AutoClicker:
    def __init__(self, error_handler, batch_size=3, wait_time=180, collect_timeout=5):
        """
        初始化 AutoClicker。

        :param error_handler: 用于处理异常的 ErrorHandler 实例。
        :param batch_size: 每批处理的URL数量。
        :param wait_time: 每批之间的等待时间（秒）。
        :param collect_timeout: 收集批次URL的超时时间（秒）。
        """
        self.error_handler = error_handler
        self.url_queue = Queue()
        self.batch_size = batch_size
        self.wait_time = wait_time
        self.collect_timeout = collect_timeout
        self.processing_thread = threading.Thread(target=self.process_queue, daemon=True)
        self.processing_thread.start()
        logging.info("AutoClicker 初始化完成，处理线程已启动。")

    def add_urls(self, urls):
        """
        添加多个URL到队列中。

        :param urls: 要添加的URL列表。
        """
        for url in urls:
            self.url_queue.put(url)
            logging.debug(f"添加URL到队列: {url}")

    def process_queue(self):
        """
        处理URL队列，分批打开链接。
        """
        try:
            logging.info("开始处理URL队列")
            while True:
                batch = []
                start_time = time.time()
                while len(batch) < self.batch_size and (time.time() - start_time) < self.collect_timeout:
                    try:
                        remaining_time = self.collect_timeout - (time.time() - start_time)
                        if remaining_time <= 0:
                            break
                        url = self.url_queue.get(timeout=remaining_time)
                        batch.append(url)
                    except Empty:
                        break  # 超时未获取到URL，结束本批处理

                if batch:
                    logging.info(f"开始处理一批链接，共 {len(batch)} 个")
                    for url in batch:
                        self.open_url(url)

                    if not self.url_queue.empty():
                        logging.info(f"等待 {self.wait_time} 秒后继续处理下一批链接")
                        time.sleep(self.wait_time)
                    else:
                        logging.info("当前队列处理完毕，无需等待。")
        except Exception as e:
            logging.error(f"处理URL队列时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

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
