# auto_download.py

import os
import queue
import re
import time
import logging
import random
from concurrent.futures import ThreadPoolExecutor
import threading
from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage.errors import ContextLostError, ElementLostError
from src.file_upload.uploader import Uploader  # 确保正确导入 Uploader 类

BASE_DIR = os.path.dirname(__file__)
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'Downloads')  # 配置下载路径
LOCK = threading.Lock()


class XKW:
    def __init__(self, thread=1, work=False, download_dir=None, uploader=None):
        self.thread = thread
        self.work = work
        self.uploader = uploader  # 接收 Uploader 实例
        self.tabs = queue.Queue()
        self.task = queue.Queue()
        self.co = ChromiumOptions()
        # self.co.headless()  # 不打开浏览器窗口，需要先登录然后再开启无浏览器模式
        self.co.no_imgs()  # 不加载图片
        self.co.set_download_path(download_dir or DOWNLOAD_DIR)  # 设置下载路径
        # self.co.set_argument('--no-sandbox')  # 无沙盒模式
        self.page = ChromiumPage(self.co)

        logging.info(f"ChromiumPage initialized with address: {self.page.address}")
        self.url = "https://www.zxxk.com/soft/{xid}.html"
        self.dls_url = "https://www.zxxk.com/soft/softdownload?softid={xid}"
        self.make_tabs()
        if self.work:
            self.manager = threading.Thread(target=self.run, daemon=True)
            self.manager.start()
            logging.info("XKW manager thread started.")

    def close_tabs(self, tabs):
        for tab in tabs:
            try:
                tab.close()
                logging.debug("Closed a browser tab.")
            except Exception as e:
                logging.error(f"关闭标签页时出错: {e}", exc_info=True)

    def make_tabs(self):
        try:
            tabs = self.page.get_tabs()
            logging.debug(f"Current tabs: {tabs}")
            while len(tabs) < self.thread:
                self.page.new_tab()
                tabs = self.page.get_tabs()
                logging.debug(f"Added new tab. Total tabs: {len(tabs)}")
            if len(tabs) > self.thread:
                self.close_tabs(tabs[self.thread:])
                tabs = self.page.get_tabs()[:self.thread]
            for tab in tabs:
                self.tabs.put(tab)
            logging.info(f"Initialized {self.thread} tabs for downloading.")
        except Exception as e:
            logging.error(f"初始化标签页时出错: {e}", exc_info=True)

    def match_downloaded_file(self, title):
        logging.debug(f"开始匹配下载的文件，标题: {title}")

        try:
            if not title:
                logging.error("标题为空，无法匹配下载文件")
                return None

            download_dir = self.co.download_path
            logging.debug(f"下载目录: {download_dir}")

            max_wait_time = 600  # 最大等待时间（秒），即10分钟
            retry_interval = 10  # 重试间隔（秒）
            elapsed_time = 0

            # 处理标题：去除所有非中文字符和数字字符
            processed_title = re.sub(r'[^\u4e00-\u9fa5\d]', '', title)
            logging.debug(f"处理后的标题: {processed_title}")

            # 创建一个更灵活的正则表达式，允许任意字符在关键字符之间
            pattern_string = '.*'.join(re.escape(char) for char in processed_title)
            pattern = re.compile(pattern_string, re.IGNORECASE)

            while elapsed_time < max_wait_time:
                logging.debug("当前下载目录下的文件:")
                for file_name in os.listdir(download_dir):
                    logging.debug(f" - {file_name}")

                    # 直接使用正则表达式进行匹配
                    if pattern.search(file_name):
                        file_path = os.path.join(download_dir, file_name)
                        if os.path.exists(file_path):
                            # 检查文件是否下载完成
                            if self.is_file_download_complete(file_path):
                                logging.info(f"匹配到下载的文件: {file_path}")
                                return file_path
                            else:
                                logging.debug(f"文件 {file_path} 尚未下载完成，等待中...")
                # 未找到文件，等待一段时间后重试
                time.sleep(retry_interval)
                elapsed_time += retry_interval
                logging.debug(f"未找到匹配的文件 '{title}'，等待 {retry_interval} 秒后重试... (已等待 {elapsed_time}/{max_wait_time} 秒)")

            # 超过最大等待时间，放弃匹配
            logging.error(f"在 {max_wait_time} 秒内未能找到匹配的下载文件: {title}")
            return None
        except Exception as e:
            logging.error(f"匹配下载文件时发生错误: {e}", exc_info=True)
            return None

    def is_file_download_complete(self, file_path):
        """
        检查文件是否下载完成，通过检查文件大小是否稳定。
        """
        try:
            initial_size = os.path.getsize(file_path)
            time.sleep(2)  # 增加等待时间，确保文件下载完成
            final_size = os.path.getsize(file_path)
            if initial_size == final_size:
                return True
            else:
                logging.debug(f"文件 {file_path} 大小变化，可能正在下载中。")
                return False
        except Exception as e:
            logging.error(f"检查文件下载完成时发生错误: {e}", exc_info=True)
            return False

    def extract_id_and_title(self, tab, url):
        """
        从页面中提取 soft_id 和标题
        """
        try:
            # 尝试加载页面
            tab.get(url)
            # 停止页面加载以加快速度
            tab.stop_loading()

            # 使用提供的方法提取标题
            h1 = tab.s_ele("t:h1@@class=res-title clearfix")
            if h1:
                # 已删除与后缀名相关的代码
                title_element = h1.child("t:span")
                if title_element:
                    title = title_element.text.strip()
                    logging.info(f"从 h1 标签中获取到标题: {title}")
                else:
                    logging.error(f"无法从 h1 标签中获取到 span 元素，URL: {url}")
                    return None, None
            else:
                logging.error(f"无法从页面中找到 h1.res-title 标签，URL: {url}")
                return None, None

            # 从 URL 中提取 soft_id
            match = re.search(r'/soft/(\d+)\.html', url)
            if match:
                soft_id = match.group(1)
                logging.info(f"从 URL 中提取到 soft_id: {soft_id}")
            else:
                logging.error(f"无法从 URL 中提取 soft_id，跳过 URL: {url}")
                return None, None

            return soft_id, title

        except ContextLostError as e:
            logging.error(f"页面上下文丢失，重新获取标签页。错误: {e}")
            # 重新获取标签页
            try:
                tab = self.tabs.get(timeout=10)
                return self.extract_id_and_title(tab, url)
            except queue.Empty:
                logging.error("无法重新获取标签页，跳过 URL")
                return None, None

        except Exception as e:
            logging.error(f"提取 ID 和标题时出错: {e}", exc_info=True)
            return None, None

    def listener(self, tab, download_button, url, title, soft_id, retry=0, max_retries=3):
        if retry > max_retries:
            logging.error(f"超过最大重试次数，下载失败: {url}")
            print("超过最大重试次数，下载失败。")
            return False  # 明确返回 False

        logging.info(f"开始下载 {url}, 重试次数: {retry}")
        print("开始下载", url)
        try:
            tab.listen.start(True, method="GET")
            download_button.click(by_js=True)
            print("clicked")
            time.sleep(2)  # 增加等待时间
            for item in tab.listen.steps(timeout=5):
                if item.url.startswith("https://files.zxxk.com/?mkey="):
                    # 停止页面加载
                    tab.listen.stop()
                    tab.stop_loading()
                    logging.info(f"下载链接获取成功: {item.url}")
                    print(item.url)

                    # 调用文件匹配函数
                    print("准备调用 match_downloaded_file")
                    file_path = self.match_downloaded_file(title)
                    print("成功调用 match_downloaded_file")

                    if file_path and os.path.exists(file_path):
                        filename = os.path.basename(file_path)
                        logging.info(f"下载完成文件: {filename}, ID: {soft_id}")
                        print(f"下载完成文件: {filename}, ID: {soft_id}")

                        # 将 file_path + soft_id 传递给 Uploader
                        if self.uploader:
                            try:
                                self.uploader.add_upload_task(file_path, soft_id)  # 使用 add_upload_task
                                logging.info(f"已将文件 {file_path} 和 soft_id {soft_id} 添加到上传任务队列。")
                                print(f"已将文件 {file_path} 和 soft_id {soft_id} 添加到上传任务队列。")
                            except AttributeError as ae:
                                logging.error(f"上传过程中发生 AttributeError: {ae}", exc_info=True)
                                print(f"上传过程中发生 AttributeError: {ae}")
                            except Exception as e:
                                logging.error(f"添加上传任务时发生错误: {e}", exc_info=True)
                                print(f"添加上传任务时发生错误: {e}")
                        else:
                            logging.warning("Uploader 未设置，无法上传文件信息。")
                            print("Uploader 未设置，无法上传文件信息。")
                        return True  # 明确返回 True
                    else:
                        logging.error(f"文件路径无效或文件不存在: {file_path}")
                        print(f"文件路径无效或文件不存在: {file_path}")
                        return False  # 明确返回 False

                elif "20600001" in item.url:
                    logging.warning("请求过于频繁，暂停1秒后重试。")
                    print("请求过于频繁，暂停1秒后重试。")
                    time.sleep(1)
                    return self.listener(tab, download_button, url, title, soft_id, retry=retry + 1,
                                         max_retries=max_retries)
            else:
                # 未找到下载链接，尝试刷新页面并重试
                logging.warning(f"未找到下载链接，尝试刷新页面并重试: {url}, 当前重试次数: {retry}")
                print(f"未找到下载链接，尝试刷新页面并重试: {url}, 当前重试次数: {retry}")
                tab.get(url)
                time.sleep(3)  # 等待页面加载
                new_download_button = tab("#btnSoftDownload")  # 重新查找下载按钮
                if new_download_button:
                    return self.listener(tab, new_download_button, url, title, soft_id, retry=retry + 1,
                                         max_retries=max_retries)
                else:
                    logging.warning(f"重新查找下载按钮失败，尝试刷新页面后再次下载: {url}, 当前重试次数: {retry}")
                    print(f"重新查找下载按钮失败，尝试刷新页面后再次下载: {url}, 当前重试次数: {retry}")
                    if retry < max_retries:
                        tab.get(url)
                        time.sleep(3)
                        new_download_button = tab("#btnSoftDownload")
                        if new_download_button:
                            return self.listener(tab, new_download_button, url, title, soft_id, retry=retry + 1,
                                                 max_retries=max_retries)
                    logging.error(f"重新查找下载按钮失败，下载失败: {url}")
                    print(f"重新查找下载按钮失败，下载失败: {url}")
                    return False
        except (ContextLostError, ElementLostError) as e:
            logging.warning(f"页面上下文丢失或元素丢失，重试下载: {url}, 错误信息: {e}")
            print(f"页面上下文丢失或元素丢失，重试下载: {url}")
            time.sleep(5)
            return self.listener(tab, download_button, url, title, soft_id, retry=retry + 1, max_retries=max_retries)
        except Exception as e:
            logging.error(f"下载过程中出错: {e}", exc_info=True)
            print(f"下载过程中出错: {e}")
            # 出现异常，进行重试
            time.sleep(5)
            return self.listener(tab, download_button, url, title, soft_id, retry=retry + 1, max_retries=max_retries)

    def download(self, url):
        try:
            delay = random.uniform(1, 3)
            logging.debug(f"随机延迟 {delay:.2f} 秒")
            time.sleep(delay)
            tab = self.tabs.get(timeout=30)  # 设置超时避免阻塞
            tab.get(url)
            soft_id, title = self.extract_id_and_title(tab, url)
            if not soft_id or not title:
                logging.error(f"无法提取 ID 和标题，跳过 URL: {url}")
                self.tabs.put(tab)
                return

            download_button = tab("#btnSoftDownload")  # 下载按钮
            if not download_button:
                logging.error(f"无法找到下载按钮，跳过URL: {url}")
                self.tabs.put(tab)
                return

            logging.info(f"准备点击下载按钮，soft_id: {soft_id}")
            # 开始下载
            success = self.listener(tab, download_button, url, title, soft_id)
            if success:
                logging.info(f"下载成功，开始处理上传任务: {url}")
                # 匹配下载的文件
                file_path = self.match_downloaded_file(title)
                if not file_path:
                    logging.error(f"匹配下载的文件失败，跳过 URL: {url}")
                else:
                    # 将文件路径和 soft_id 传递给上传模块
                    if self.uploader:
                        try:
                            self.uploader.add_upload_task(file_path, soft_id)  # 使用 add_upload_task
                            logging.info(f"已将文件 {file_path} 和 soft_id {soft_id} 添加到上传任务队列。")
                        except AttributeError as ae:
                            logging.error(f"上传过程中发生 AttributeError: {ae}", exc_info=True)
                        except Exception as e:
                            logging.error(f"添加上传任务时发生错误: {e}", exc_info=True)
                    else:
                        logging.warning("Uploader 未设置，无法传递上传任务。")
            else:
                logging.error(f"下载失败，跳过 URL: {url}")
        except queue.Empty:
            logging.warning("任务队列为空，等待新任务。")
        except Exception as e:
            logging.error(f"下载过程中出错: {e}", exc_info=True)
            # 在发生异常时，确保 tab 被放回队列
            if 'tab' in locals():
                self.tabs.put(tab)
        finally:
            if 'tab' in locals():
                self.tabs.put(tab)

    def run(self):
        with ThreadPoolExecutor(max_workers=self.thread * 2) as executor:
            futures = []
            while self.work:
                try:
                    url = self.task.get(timeout=5)  # 等待新任务
                    if url is None:
                        logging.info("接收到退出信号，停止下载管理。")
                        print("接收到退出信号，停止下载管理。")
                        break
                    future = executor.submit(self.download, url)
                    futures.append(future)
                    logging.info(f"已提交下载任务到线程池: {url}")
                    print(f"已提交下载任务到线程池: {url}")
                except queue.Empty:
                    continue  # 没有任务，继续等待
                except Exception as e:
                    logging.error(f"任务分发时出错: {e}", exc_info=True)
                    print(f"任务分发时出错: {e}")
            # 等待所有任务完成
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"下载任务中出现未捕获的异常: {e}", exc_info=True)
                    print(f"下载任务中出现未捕获的异常: {e}")

    def add_task(self, url):
        self.task.put(url)
        logging.info(f"添加新下载任务: {url}")