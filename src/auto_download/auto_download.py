import logging
import os
import queue
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Tuple
from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage.errors import ContextLostError
from src.notification.notifier import Notifier

# 配置基础目录和下载目录
BASE_DIR = os.path.dirname(__file__)
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'Downloads')
LOCK = threading.Lock()

# 初始化日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class ErrorHandler:
    def __init__(self, notifier: Notifier):
        self.notifier = notifier

    def handle_exception(self, exception):
        error_message = f"ErrorHandler 捕获到异常: {exception}"
        logging.error(error_message, exc_info=True)
        self.notifier.notify(error_message, is_error=True)  # 发送错误通知


class XKW:
    def __init__(self, thread=1, work=False, download_dir=None, uploader=None, notifier=None):
        self.thread = thread
        self.work = work
        self.uploader = uploader  # 接收 Uploader 实例
        self.notifier = notifier  # 接收 Notifier 实例
        self.tabs = queue.Queue()
        self.task = queue.Queue()
        self.failed_tasks = queue.Queue()  # 队列用于存储失败的任务
        self.retry_counts: Dict[str, int] = {}  # 记录每个URL的重试次数
        self.co = ChromiumOptions()
        # self.co.headless()  # 不打开浏览器窗口，需要先登录然后再开启无浏览器模式
        self.co.no_imgs()  # 不加载图片
        self.co.set_download_path(download_dir or DOWNLOAD_DIR)  # 设置下载路径
        # self.co.set_argument('--no-sandbox')  # 无沙盒模式
        self.page = ChromiumPage(self.co)

        logging.info(f"ChromiumPage initialized with address: {self.page.address}")
        self.dls_url = "https://www.zxxk.com/soft/softdownload?softid={xid}"
        self.make_tabs()
        if self.work:
            self.manager = threading.Thread(target=self.run, daemon=True)
            self.manager.start()
            logging.info("XKW manager 线程已启动。")

    def close_tabs(self, tabs):
        for tab in tabs:
            try:
                tab.close()
                logging.debug("关闭了一个浏览器标签页。")
            except Exception as e:
                logging.error(f"关闭标签页时出错: {e}", exc_info=True)

    def make_tabs(self):
        try:
            tabs = self.page.get_tabs()
            logging.debug(f"当前标签页: {tabs}")
            while len(tabs) < self.thread:
                self.page.new_tab()
                tabs = self.page.get_tabs()
                logging.debug(f"添加新标签页。总标签页数: {len(tabs)}")
            if len(tabs) > self.thread:
                self.close_tabs(tabs[self.thread:])
                tabs = self.page.get_tabs()[:self.thread]
            for tab in tabs:
                self.tabs.put(tab)
            logging.info(f"初始化了 {self.thread} 个标签页用于下载。")
        except Exception as e:
            logging.error(f"初始化标签页时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"初始化标签页时出错: {e}", is_error=True)

    def match_downloaded_file(self, title):
        logging.debug(f"开始匹配下载的文件，标题: {title}")

        try:
            if not title:
                logging.error("标题为空，无法匹配下载文件")
                return None

            download_dir = self.co.download_path
            logging.debug(f"下载目录: {download_dir}")

            max_wait_time = 1800  # 最大等待时间（秒），即30分钟
            initial_wait = 60  # 初始等待时间（秒）
            initial_interval = 1  # 前60秒的重试间隔（秒）
            subsequent_interval = 10  # 后续的重试间隔（秒）
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

                    if pattern.search(file_name):
                        file_path = os.path.join(download_dir, file_name)
                        if os.path.exists(file_path):
                            if self.is_file_download_complete(file_path):
                                logging.info(f"匹配到下载的文件: {file_path}")
                                return file_path
                            else:
                                logging.debug(f"文件 {file_path} 尚未下载完成，等待中...")

                # 确定下一次的重试间隔
                if elapsed_time < initial_wait:
                    retry_interval = initial_interval
                else:
                    retry_interval = subsequent_interval

                # 计算剩余时间，避免超过最大等待时间
                remaining_time = max_wait_time - elapsed_time
                sleep_time = min(retry_interval, remaining_time)

                # 未找到文件，等待一段时间后重试
                time.sleep(sleep_time)
                elapsed_time += sleep_time
                logging.debug(
                    f"未找到匹配的文件 '{title}'，等待 {sleep_time} 秒后重试... (已等待 {elapsed_time}/{max_wait_time} 秒)")
            # 超过最大等待时间，放弃匹配
            logging.error(f"在 {max_wait_time} 秒内未能找到匹配的下载文件: {title}")
            if self.notifier:
                self.notifier.notify(f"在 {max_wait_time} 秒内未能找到匹配的下载文件: {title}", is_error=True)
            return None
        except Exception as e:
            logging.error(f"匹配下载文件时发生错误: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"匹配下载文件时发生错误: {e}", is_error=True)
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
            if self.notifier:
                self.notifier.notify(f"检查文件下载完成时发生错误: {e}", is_error=True)
            return False

    def capture_all_tabs_screenshots(self) -> List[str]:
        """
        捕获所有标签页的截图，并返回截图文件路径列表
        """
        screenshot_paths = []
        try:
            tabs = self.page.get_tabs()
            for index, tab in enumerate(tabs):
                try:
                    # 定义截图文件名
                    screenshot_name = f"tab_{index + 1}.png"
                    screenshot_path = os.path.join(DOWNLOAD_DIR, screenshot_name)

                    # 使用 get_screenshot 方法保存截图
                    # 根据文档，path 参数用于保存截图
                    # full_page=True 捕获整个页面，full_page=False 仅捕获可视部分
                    success = tab.get_screenshot(path=screenshot_path, full_page=True)

                    if success:
                        screenshot_paths.append(screenshot_path)
                        logging.info(f"已捕获标签页 {index + 1} 的截图: {screenshot_path}")
                    else:
                        logging.warning(f"无法捕获标签页 {index + 1} 的截图")
                except Exception as e:
                    logging.error(f"捕获标签页 {index + 1} 截图时出错: {e}", exc_info=True)
        except Exception as e:
            logging.error(f"获取标签页列表时发生错误: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"获取标签页列表时发生错误: {e}", is_error=True)
        return screenshot_paths

    def restart_browser(self):
        """
        重启浏览器：将所有标签页导航到空白页，并重新初始化它们。
        """
        try:
            logging.info("开始重启浏览器。")
            if self.page:
                current_tabs = self.page.get_tabs()
                for tab in current_tabs:
                    try:
                        tab.go('about:blank')
                        logging.debug("将标签页导航到空白页。")
                    except Exception as e:
                        logging.error(f"导航标签页到空白页时出错: {e}", exc_info=True)

                logging.info("所有浏览器标签页已导航到空白页。")
                if self.notifier:
                    self.notifier.notify("所有浏览器标签页已导航到空白页。")

                # 重新初始化标签页
                self.make_tabs()
                logging.info("浏览器标签页已重新初始化。")
                if self.notifier:
                    self.notifier.notify("浏览器已成功重启。")
            else:
                logging.error("ChromiumPage 实例未初始化，无法重启浏览器。")
                if self.notifier:
                    self.notifier.notify("ChromiumPage 实例未初始化，无法重启浏览器。", is_error=True)
        except Exception as e:
            logging.error(f"重启浏览器时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"重启浏览器时出错: {e}", is_error=True)

    def extract_id_and_title(self, tab, url) -> Tuple[str, str]:
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
            if self.notifier:
                self.notifier.notify(f"页面上下文丢失，重新获取标签页。错误: {e}", is_error=True)
            # 重新获取标签页
            try:
                tab = self.tabs.get(timeout=10)
                return self.extract_id_and_title(tab, url)
            except queue.Empty:
                logging.error("无法重新获取标签页，跳过 URL")
                if self.notifier:
                    self.notifier.notify("无法重新获取标签页，跳过 URL", is_error=True)
                return None, None

        except Exception as e:
            logging.error(f"提取 ID 和标题时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"提取 ID 和标题时出错: {e}", is_error=True)
            return None, None

    def handle_success(self, url, title, soft_id):
        logging.info(f"下载成功，开始处理上传任务: {url}")
        # 匹配下载的文件
        file_path = self.match_downloaded_file(title)
        if not file_path:
            logging.error(f"匹配下载的文件失败，跳过 URL: {url}")
            self.failed_tasks.put(url)  # 将失败的任务重新放入失败队列
            if self.notifier:
                self.notifier.notify(f"匹配下载的文件失败，跳过 URL: {url}", is_error=True)
            return

        # 将文件路径和 soft_id 传递给上传模块
        if self.uploader:
            try:
                self.uploader.add_upload_task(file_path, soft_id)  # 使用 add_upload_task
                logging.info(f"已将文件 {file_path} 和 soft_id {soft_id} 添加到上传任务队列。")
            except AttributeError as ae:
                logging.error(f"上传过程中发生 AttributeError: {ae}", exc_info=True)
                self.failed_tasks.put(url)  # 将失败的任务重新放入失败队列
                if self.notifier:
                    self.notifier.notify(f"上传过程中发生 AttributeError: {ae}", is_error=True)
            except Exception as e:
                logging.error(f"添加上传任务时发生错误: {e}", exc_info=True)
                self.failed_tasks.put(url)  # 将失败的任务重新放入失败队列
                if self.notifier:
                    self.notifier.notify(f"添加上传任务时发生错误: {e}", is_error=True)
        else:
            logging.warning("Uploader 未设置，无法传递上传任务。")

    def listener(self, tab, download, url, title, soft_id, retry=0, max_retries=5):
        while retry < max_retries:
            logging.info(f"开始下载 {url}, 重试次数: {retry}")
            try:
                tab.listen.start(True, method="GET")
                download.click(by_js=True)
                for item in tab.listen.steps(timeout=10):
                    if item.url.startswith("https://files.zxxk.com/?mkey="):
                        tab.listen.stop()
                        tab.stop_loading()
                        logging.info(f"下载链接获取成功: {item.url}")
                        self.handle_success(url, title, soft_id)
                        return
                    elif "20600001" in item.url:
                        logging.warning("请求过于频繁，暂停1秒后重试。")
                        time.sleep(1)
                        retry += 1
                        break
                else:
                    time.sleep(1)
                    iframe = tab.get_frame('#layui-layer-iframe100002')
                    if iframe:
                        a = iframe("t:a@@class=balance-payment-btn@@text()=确认")
                        if a:
                            a.click()
                            logging.info("点击确认按钮成功。")
                            continue
                    logging.warning(f"下载失败，尝试重新下载: {url}, 当前重试次数: {retry}")
                    time.sleep(3)
                    retry += 1
            except ContextLostError as e:
                logging.warning(f"页面上下文丢失，重试下载: {url}, 错误信息: {e}")
                if self.notifier:
                    self.notifier.notify(f"页面上下文丢失，重试下载: {url}, 错误信息: {e}", is_error=True)
                time.sleep(5)
                retry += 1
            except Exception as e:
                logging.error(f"下载过程中出错: {e}", exc_info=True)
                if self.notifier:
                    self.notifier.notify(f"下载过程中出错: {e}", is_error=True)
                time.sleep(5)
                retry += 1
        # 超过最大重试次数，记录失败
        logging.error(f"下载任务最终失败: {url}")
        self.failed_tasks.put(url)  # 将最终失败的任务放入失败队列
        if self.notifier:
            self.notifier.notify(f"下载任务最终失败: {url}", is_error=True)

    def download(self, url):
        try:
            logging.info(f"准备下载 URL: {url}")
            delay = random.uniform(1, 2)
            logging.debug(f"随机延迟 {delay:.1f} 秒")
            time.sleep(delay)

            tab = self.tabs.get(timeout=30)  # 设置超时避免阻塞
            logging.info(f"获取到一个标签页用于下载: {tab}")
            tab.get(url)

            soft_id, title = self.extract_id_and_title(tab, url)
            if not soft_id or not title:
                logging.error(f"无法提取 ID 和标题，跳过 URL: {url}")
                self.tabs.put(tab)
                self.failed_tasks.put(url)  # 将失败的任务重新放入失败队列
                if self.notifier:
                    self.notifier.notify(f"无法提取 ID 和标题，跳过 URL: {url}", is_error=True)
                return

            download_button = tab("#btnSoftDownload")  # 下载按钮
            if not download_button:
                logging.error(f"无法找到下载按钮，跳过URL: {url}")
                self.tabs.put(tab)
                self.failed_tasks.put(url)  # 将失败的任务重新放入失败队列
                if self.notifier:
                    self.notifier.notify(f"无法找到下载按钮，跳过 URL: {url}", is_error=True)
                return

            logging.info(f"准备点击下载按钮，soft_id: {soft_id}")
            # 开始下载并处理后续任务
            self.listener(tab, download_button, url, title, soft_id)
        except queue.Empty:
            logging.warning("任务队列为空，等待新任务。")
        except Exception as e:
            logging.error(f"下载过程中出错: {e}", exc_info=True)
            if 'tab' in locals():
                self.tabs.put(tab)
            self.failed_tasks.put(url)  # 将失败的任务重新放入失败队列
            if self.notifier:
                self.notifier.notify(f"下载过程中出错: {e}", is_error=True)
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
                        break
                    # 检查URL是否已经超过重试次数
                    current_retry = self.retry_counts.get(url, 0)
                    if current_retry >= 5:
                        logging.error(f"URL {url} 已超过最大重试次数，跳过。")
                        if self.notifier:
                            self.notifier.notify(f"URL {url} 已超过最大重试次数，跳过。", is_error=True)
                        continue
                    future = executor.submit(self.download, url)
                    futures.append(future)
                    logging.info(f"已提交下载任务到线程池: {url}")
                except queue.Empty:
                    # 处理失败的任务
                    try:
                        failed_url = self.failed_tasks.get_nowait()
                        self.retry_counts[failed_url] = self.retry_counts.get(failed_url, 0) + 1
                        if self.retry_counts[failed_url] <= 5:
                            logging.info(f"重新添加失败的URL到任务队列: {failed_url}, 重试次数: {self.retry_counts[failed_url]}")
                            self.task.put(failed_url)
                        else:
                            logging.error(f"URL {failed_url} 超过最大重试次数，无法下载。")
                            if self.notifier:
                                self.notifier.notify(f"URL {failed_url} 超过最大重试次数，无法下载。", is_error=True)
                    except queue.Empty:
                        continue  # 没有失败任务，继续等待
                except Exception as e:
                    logging.error(f"任务分发时出错: {e}", exc_info=True)
                    if self.notifier:
                        self.notifier.notify(f"任务分发时出错: {e}", is_error=True)
            # 等待所有任务完成
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"下载任务中出现未捕获的异常: {e}", exc_info=True)
                    if self.notifier:
                        self.notifier.notify(f"下载任务中出现未捕获的异常: {e}", is_error=True)

    def add_task(self, url):
        self.task.put(url)

    def stop(self):
        """
        停止 XKW 实例。
        """
        try:
            logging.info("停止 XKW 实例。")
            self.work = False
            self.task.put(None)  # 发送退出信号
            self.page.close()
            logging.info("XKW 实例已停止。")
        except Exception as e:
            logging.error(f"停止过程中出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"停止过程中出错: {e}", is_error=True)


class AutoDownloadManager:
    def __init__(self, thread=3, download_dir=None, uploader=None, notifier_config=None):
        """
        初始化 AutoDownloadManager。

        :param thread: 下载线程数。
        :param download_dir: 下载文件的目标目录。
        :param uploader: 上传模块实例，用于处理上传任务。
        :param notifier_config: 通知配置字典，包含 'method' 和 'error_recipient'
        """
        self.notifier = None
        if notifier_config:
            try:
                self.notifier = Notifier(notifier_config)
                logging.info("Notifier 已初始化。")
            except Exception as e:
                logging.error(f"初始化 Notifier 时出错: {e}", exc_info=True)

        self.error_handler = ErrorHandler(self.notifier)
        self.downloader = XKW(
            thread=thread,
            work=True,
            download_dir=download_dir,
            uploader=uploader,
            notifier=self.notifier
        )
        logging.info("AutoDownloadManager 已初始化。")

    def open_url(self, url):
        """
        打开指定的 URL，并将下载任务添加到 downloader。

        :param url: 要打开的 URL。
        """
        try:
            logging.info(f"准备处理URL: {url}")
            self.downloader.add_task(url)
            logging.info(f"已将URL添加到下载任务队列: {url}")
        except Exception as e:
            logging.error(f"处理URL时发生未知错误: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"处理URL时发生未知错误: {e}", is_error=True)

    def add_urls(self, urls: List[str]):
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
            if self.notifier:
                self.notifier.notify(f"批量添加 URL 时发生错误: {e}", is_error=True)

    def add_task(self, url: str):
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
            if self.notifier:
                self.notifier.notify(f"添加单个 URL 时发生错误: {e}", is_error=True)

    def restart_browser(self):
        """
        重启浏览器，通过调用 downloader 的 restart_browser 方法。
        """
        try:
            if self.downloader:
                logging.info("调用 downloader 重启浏览器。")
                self.downloader.restart_browser()
            else:
                logging.error("Downloader 未初始化，无法重启浏览器。")
                if self.notifier:
                    self.notifier.notify("Downloader 未初始化，无法重启浏览器。", is_error=True)
        except Exception as e:
            logging.error(f"重启浏览器时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"重启浏览器时出错: {e}", is_error=True)

    def stop(self):
        """
        停止 AutoDownloadManager 和其内部的 XKW 实例。
        """
        try:
            logging.info("停止 AutoDownloadManager 和 XKW 实例。")
            self.downloader.stop()
        except Exception as e:
            logging.error(f"停止过程中出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"停止过程中出错: {e}", is_error=True)
