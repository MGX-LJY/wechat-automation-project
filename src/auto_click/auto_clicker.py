# src/auto_click/auto_clicker.py

import webbrowser
import logging
import time
import subprocess
import threading
from queue import Queue, Empty

class AutoClicker:
    def __init__(self, error_handler, batch_size=4, wait_time=60, collect_timeout=5, close_after_count=7, close_wait_time=300):
        """
        初始化 AutoClicker。

        :param error_handler: 用于处理异常的 ErrorHandler 实例。
        :param batch_size: 每批处理的URL数量。
        :param wait_time: 每批之间的等待时间（秒）。
        :param collect_timeout: 收集批次URL的超时时间（秒）。
        :param close_after_count: 达到此计数后关闭浏览器。
        :param close_wait_time: 达到计数后等待的时间（秒）。
        """
        self.error_handler = error_handler
        self.url_queue = Queue()
        self.batch_size = batch_size
        self.wait_time = wait_time
        self.collect_timeout = collect_timeout
        self.close_after_count = close_after_count
        self.close_wait_time = close_wait_time

        self.opened_count = 0
        self.timer_running = False
        self.count_lock = threading.Lock()

        # 启动处理线程一次
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

                    # 在处理完当前批次后，检查是否需要等待
                    if not self.url_queue.empty():
                        logging.info(f"等待 {self.wait_time} 秒后继续处理下一批链接")
                        time.sleep(self.wait_time)
                    else:
                        logging.info("当前队列处理完毕，无需等待。")
                else:
                    # 队列为空时不记录日志，避免日志充斥
                    time.sleep(5)
        except Exception as e:
            logging.error(f"处理URL队列时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def open_url(self, url):
        """
        打开指定的 URL，并进行计数控制。

        :param url: 要打开的 URL。
        """
        try:
            logging.info(f"打开URL: {url}")
            webbrowser.get('safari').open(url)
            time.sleep(1)  # 等待Safari打开标签页，防止过快打开

            # 更新已打开的URL计数
            self.increment_count()

        except Exception as e:
            logging.error(f"打开URL时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def increment_count(self):
        """
        增加已打开URL的计数，并在达到阈值时启动计时器关闭浏览器。
        """
        with self.count_lock:
            self.opened_count += 1
            logging.debug(f"已打开的URL数量: {self.opened_count}")

            if self.opened_count >= self.close_after_count and not self.timer_running:
                self.timer_running = True
                logging.info(f"已打开 {self.close_after_count} 个链接，启动计时器将在 {self.close_wait_time} 秒后关闭浏览器")
                timer_thread = threading.Thread(target=self.close_timer, daemon=True)
                timer_thread.start()

    def close_timer(self):
        """
        等待指定时间后关闭浏览器，并重置计数和计时器状态。
        """
        try:
            logging.info(f"计时器启动，等待 {self.close_wait_time} 秒后关闭浏览器")
            time.sleep(self.close_wait_time)
            self.close_safari()
        except Exception as e:
            logging.error(f"计时器运行时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
        finally:
            with self.count_lock:
                self.opened_count = 0
                self.timer_running = False
                logging.debug("计数器已重置")

    def close_safari(self):
        """
        关闭 Safari 浏览器。
        """
        try:
            logging.info("尝试关闭 Safari 浏览器")
            result = subprocess.run(['osascript', '-e', 'tell application "Safari" to quit'], capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"关闭 Safari 失败: {result.stderr.strip()}")
            else:
                logging.info("Safari 已成功关闭")
        except Exception as e:
            logging.error(f"关闭 Safari 时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
