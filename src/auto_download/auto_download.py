import logging
import os
import pickle
import queue
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Tuple
from DrissionPage import ChromiumPage, ChromiumOptions, Chromium
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
        if self.notifier:
            self.notifier.notify(error_message, is_error=True)  # 发送错误通知


class StatisticsManager:
    _instance = None
    _singleton_lock = threading.Lock()

    def __new__(cls, save_interval=300, save_path='statistics.pkl'):
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super(StatisticsManager, cls).__new__(cls)
                cls._instance.__initialized = False
        return cls._instance

    def __init__(self, save_interval=300, save_path='statistics.pkl'):
        if self.__initialized:
            return
        self.lock = threading.Lock()
        self.total_tasks = 0
        self.successful_tasks = 0
        self.failed_tasks = 0
        self.total_download_time = 0.0  # 以秒为单位
        self.save_interval = save_interval
        self.save_path = save_path
        self.__initialized = True
        logging.info("StatisticsManager 单例实例初始化完成。")
        self.load_statistics()
        self.auto_save_thread = threading.Thread(target=self.auto_save, daemon=True)
        self.auto_save_thread.start()

    def record_task_submission(self, url):
        try:
            with self.lock:
                self.total_tasks += 1
                logging.debug(f"任务提交: {url}。总任务数: {self.total_tasks}")
        except Exception as e:
            logging.error(f"记录任务提交时出错: {e}", exc_info=True)

    def record_task_success(self, url, download_time):
        try:
            with self.lock:
                self.successful_tasks += 1
                self.total_download_time += download_time
                logging.debug(f"任务成功: {url}。成功任务数: {self.successful_tasks}，总下载时间: {self.total_download_time:.2f}秒")
                print(f"任务成功: {url}。成功任务数: {self.successful_tasks}，总下载时间: {self.total_download_time:.2f}秒")
        except Exception as e:
            logging.error(f"记录任务成功时出错: {e}", exc_info=True)

    def record_task_failure(self, url):
        try:
            with self.lock:
                self.failed_tasks += 1
                logging.debug(f"任务失败: {url}。失败任务数: {self.failed_tasks}")
                print(f"任务失败: {url}。失败任务数: {self.failed_tasks}")
        except Exception as e:
            logging.error(f"记录任务失败时出错: {e}", exc_info=True)

    def get_statistics(self):
        try:
            with self.lock:
                avg_download_time = (self.total_download_time / self.successful_tasks) if self.successful_tasks else 0
                success_rate = (self.successful_tasks / self.total_tasks * 100) if self.total_tasks else 0
                logging.debug(f"获取统计信息：总任务数={self.total_tasks}, 成功任务数={self.successful_tasks}, "
                              f"失败任务数={self.failed_tasks}, 平均下载时间={avg_download_time:.2f}秒, "
                              f"成功率={success_rate:.2f}%")
                return {
                    'total_tasks': self.total_tasks,
                    'successful_tasks': self.successful_tasks,
                    'failed_tasks': self.failed_tasks,
                    'average_download_time': avg_download_time,
                    'success_rate': success_rate
                }
        except Exception as e:
            logging.error(f"获取统计信息时出错: {e}", exc_info=True)
            return {
                'total_tasks': self.total_tasks,
                'successful_tasks': self.successful_tasks,
                'failed_tasks': self.failed_tasks,
                'average_download_time': 0,
                'success_rate': 0
            }

    def log_statistics(self):
        try:
            stats = self.get_statistics()
            logging.info(f"统计信息: 总任务数={stats['total_tasks']}, 成功任务数={stats['successful_tasks']}, "
                         f"失败任务数={stats['failed_tasks']}, 平均下载时间={stats['average_download_time']:.2f}秒, "
                         f"成功率={stats['success_rate']:.2f}%")
        except Exception as e:
            logging.error(f"记录统计信息时出错: {e}", exc_info=True)

    def save_statistics(self, filepath=None):
        """
        保存统计数据到磁盘。
        """
        try:
            if filepath is None:
                filepath = self.save_path
            stats = self.get_statistics()
            with open(filepath, 'wb') as f:
                pickle.dump(stats, f)
            logging.info(f"统计数据已保存到 {filepath}。")
        except Exception as e:
            logging.error(f"保存统计数据时出错: {e}", exc_info=True)

    def load_statistics(self, filepath=None):
        """
        从磁盘加载统计数据。
        """
        try:
            if filepath is None:
                filepath = self.save_path
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    stats = pickle.load(f)
                with self.lock:
                    self.total_tasks = stats.get('total_tasks', 0)
                    self.successful_tasks = stats.get('successful_tasks', 0)
                    self.failed_tasks = stats.get('failed_tasks', 0)
                    self.total_download_time = stats.get('average_download_time', 0.0) * stats.get('successful_tasks', 0)
                logging.info(f"统计数据已从 {filepath} 加载。")
        except Exception as e:
            logging.error(f"加载统计数据时出错: {e}", exc_info=True)

    def auto_save(self):
        while True:
            time.sleep(self.save_interval)
            self.save_statistics()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.save_statistics()


class XKW:
    def __init__(self, thread=1, work=False, download_dir=None, uploader=None, notifier=None, stats=None, co=None, manager=None):
        self.thread = thread
        self.work = work
        self.uploader = uploader  # 接收 Uploader 实例
        self.notifier = notifier  # 接收 Notifier 实例
        self.tabs = queue.Queue()
        self.task = queue.Queue()
        self.retry_counts: Dict[str, int] = {}  # 记录每个URL的重试次数
        self.co = co or ChromiumOptions()
        # self.co.headless()  # 不打开浏览器窗口，需要先登录然后再开启无浏览器模式
        self.co.no_imgs()  # 不加载图片
        self.co.set_download_path(download_dir or DOWNLOAD_DIR)  # 设置下载路径
        # self.co.set_argument('--no-sandbox')  # 无沙盒模式
        self.page = ChromiumPage(self.co)
        self.last_download_time = 0  # 记录上一次下载任务启动的时间
        self.download_lock = threading.Lock()  # 用于同步下载任务的启动时间
        self.manager = manager  # 新增：保存 AutoDownloadManager 实例

        logging.info(f"ChromiumPage initialized with address: {self.page.address}")
        self.dls_url = "https://www.zxxk.com/soft/softdownload?softid={xid}"
        self.make_tabs()
        if self.work:
            self.manager_thread = threading.Thread(target=self.run, daemon=True)
            self.manager_thread.start()
            logging.info("XKW manager 线程已启动。")

        # 初始化监控与统计
        self.stats = stats if stats else StatisticsManager()

        # 新增：用于记录每个 URL 被添加的次数和处理状态
        self.lock = threading.Lock()
        self.url_counts = {}
        self.processing_urls = set()
        self.completed_urls = set()
        self.url_download_events = {}  # 用于同步等待
        self.url_to_soft_id = {}
        self.url_to_file_path = {}

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

    def reset_tab(self, tab):
        """
        等待1秒后将标签页导航到空白页以重置状态。
        """
        try:
            logging.info("等待1秒后重置标签页到空白页。")
            time.sleep(1)
            tab.get('about:blank')
            logging.info("标签页已重置为 about:blank。")
        except Exception as e:
            logging.error(f"导航标签页到空白页时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"导航标签页到空白页时出错: {e}", is_error=True)

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
        start_time = time.time()  # 开始计时
        logging.info(f"下载成功，开始处理上传任务: {url}")
        # 匹配下载的文件
        file_path = self.match_downloaded_file(title)
        if not file_path:
            logging.error(f"匹配下载的文件失败，跳过 URL: {url}")
            if self.notifier:
                self.notifier.notify(f"匹配下载的文件失败，跳过 URL: {url}", is_error=True)
            self.stats.record_task_failure(url)
            return

        # 保存 URL 与 soft_id 和 file_path 的映射
        with self.lock:
            self.url_to_soft_id[url] = soft_id
            self.url_to_file_path[url] = file_path
            # 标记为已完成
            self.completed_urls.add(url)
            # 触发事件，通知等待的线程
            event = self.url_download_events.get(url)
            if event:
                event.set()

        # 记录下载成功
        download_time = time.time() - start_time
        self.stats.record_task_success(url, download_time)
        self.stats.log_statistics()

    def send_to_uploader(self, url):
        with self.lock:
            count = self.url_counts.get(url, 1)
            soft_id = self.url_to_soft_id.get(url)
            file_path = self.url_to_file_path.get(url)
        if not soft_id or not file_path:
            logging.error(f"无法找到 URL {url} 对应的 soft_id 或 file_path")
            return
        for i in range(count):
            self.uploader.add_upload_task(file_path, soft_id)
            logging.info(f"第 {i+1}/{count} 次将文件 {file_path} 和 soft_id {soft_id} 添加到上传任务队列。")

    def listener(self, tab, download, url, title, soft_id, retry=0, max_retries=2):
        base_delay = 2  # 基础延迟时间（秒）
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

                        # 等待1秒后重置标签页
                        self.reset_tab(tab)
                        return
                    elif "20600001" in item.url:
                        logging.warning("请求过于频繁，暂停后重试。")
                        backoff = base_delay * (2 ** retry)
                        jitter = random.uniform(0, 1)
                        total_delay = backoff + jitter
                        logging.debug(f"请求过于频繁，等待 {total_delay:.1f} 秒后重试。")
                        time.sleep(total_delay)
                        retry += 1
                        break
                else:
                    # 其他未处理的情况
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
                backoff = base_delay * (2 ** retry)
                jitter = random.uniform(0, 1)
                total_delay = backoff + jitter
                logging.debug(f"页面上下文丢失，等待 {total_delay:.1f} 秒后重试。")
                time.sleep(total_delay)
                retry += 1
                # 重置标签页并重新导航到 URL
                self.reset_tab(tab)
                tab.get(url)  # 重新加载页面
            except Exception as e:
                logging.error(f"下载过程中出错: {e}", exc_info=True)
                if self.notifier:
                    self.notifier.notify(f"下载过程中出错: {e}", is_error=True)
                # 指数退避
                backoff = base_delay * (2 ** retry)
                jitter = random.uniform(0, 1)
                total_delay = backoff + jitter
                logging.debug(f"下载出错，等待 {total_delay:.1f} 秒后重试。")
                time.sleep(total_delay)
                retry += 1
                # 重置标签页并重新导航到 URL
                self.reset_tab(tab)
                tab.get(url)  # 重新加载页面
            try:
                # 等待1秒后重置标签页
                self.reset_tab(tab)
            except Exception as reset_e:
                logging.error(f"导航标签页到空白页时出错: {reset_e}", exc_info=True)
                if self.notifier:
                    self.notifier.notify(f"导航标签页到空白页时出错: {reset_e}", is_error=True)

        # 超过最大重试次数，记录失败
        logging.error(f"下载任务最终失败: {url}")
        if self.notifier:
            self.notifier.notify(f"下载任务最终失败: {url}", is_error=True)
        self.stats.record_task_failure(url)

        # 尝试在另一个浏览器实例中重试下载
        logging.info(f"尝试在另一个浏览器实例中重试下载: {url}")
        if self.switch_browser_and_retry(url):
            logging.info(f"在另一个浏览器实例中成功下载: {url}")
            return
        else:
            logging.error(f"在所有浏览器实例中均未能成功下载: {url}")

    def switch_browser_and_retry(self, url):
        """
        切换到另一个浏览器实例重新尝试下载。
        """
        try:
            available_xkw_instances = self.manager.get_available_xkw_instances(self)
            if available_xkw_instances:
                xkw_instance = random.choice(available_xkw_instances)
                logging.info(f"切换到新的 XKW 实例进行下载: {xkw_instance}")
                xkw_instance.add_task(url)
                return True
            else:
                logging.error("没有可用的 XKW 实例进行重试。")
                return False
        except Exception as e:
            logging.error(f"切换浏览器实例时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"切换浏览器实例时出错: {e}", is_error=True)
            return False

    def download(self, url):
        start_time = time.time()  # 记录下载开始时间
        try:
            logging.info(f"准备下载 URL: {url}")
            # 增加随机延迟，模拟人类等待页面加载
            pre_download_delay = random.uniform(2, 5)
            logging.debug(f"下载前随机延迟 {pre_download_delay:.1f} 秒")
            time.sleep(pre_download_delay)

            tab = self.tabs.get(timeout=30)  # 设置超时避免阻塞
            logging.info(f"获取到一个标签页用于下载: {tab}")
            tab.get(url)

            soft_id, title = self.extract_id_and_title(tab, url)
            if not soft_id or not title:
                logging.error(f"提取 soft_id 或标题失败，跳过 URL: {url}")
                self.stats.record_task_failure(url)
                self.reset_tab(tab)
                return

            download_button = tab("#btnSoftDownload")  # 下载按钮
            if not download_button:
                logging.error(f"无法找到下载按钮，跳过URL: {url}")
                try:
                    # 等待1秒后重置标签页
                    self.reset_tab(tab)
                except Exception as e:
                    logging.error(f"导航标签页到空白页时出错: {e}", exc_info=True)
                if self.notifier:
                    self.notifier.notify(f"无法找到下载按钮，跳过 URL: {url}", is_error=True)
                self.stats.record_task_failure(url)
                return

            logging.info(f"准备点击下载按钮，soft_id: {soft_id}")
            click_delay = random.uniform(1, 3)
            logging.debug(f"点击下载按钮前随机延迟 {click_delay:.1f} 秒")
            time.sleep(click_delay)

            # 开始下载并处理后续任务
            self.listener(tab, download_button, url, title, soft_id)
        except queue.Empty:
            logging.warning("任务队列为空，等待新任务。")
        except Exception as e:
            logging.error(f"下载过程中出错: {e}", exc_info=True)
            if 'tab' in locals():
                try:
                    # 等待1秒后重置标签页
                    self.reset_tab(tab)
                except Exception as close_e:
                    logging.error(f"导航标签页到空白页时出错: {close_e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"下载过程中出错: {e}", is_error=True)
            self.stats.record_task_failure(url)
        finally:
            if 'tab' in locals():
                self.tabs.put(tab)

    def run(self):
        max_retries_per_url = 3  # 设置最大重试次数
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
                    if current_retry >= max_retries_per_url:
                        logging.error(f"URL {url} 已超过最大重试次数，跳过。")
                        if self.notifier:
                            self.notifier.notify(f"URL {url} 已超过最大重试次数，跳过。", is_error=True)
                        continue

                    # 控制下载启动间隔
                    with self.download_lock:
                        current_time = time.time()
                        elapsed = current_time - self.last_download_time
                        if elapsed < 2:
                            wait_time = 2 - elapsed
                            logging.debug(f"等待 {wait_time:.1f} 秒以确保下载间隔至少2秒。")
                            time.sleep(wait_time)
                        self.last_download_time = time.time()

                    # 提交下载任务
                    future = executor.submit(self.download, url)
                    futures.append(future)
                    logging.info(f"已提交下载任务到线程池: {url}")

                    # 增加随机间隔，模拟任务分发的不规则性
                    task_dispatch_delay = random.uniform(0.2, 1)
                    logging.debug(f"任务分发后随机延迟 {task_dispatch_delay:.1f} 秒")
                    time.sleep(task_dispatch_delay)
                except queue.Empty:
                    continue  # 直接继续等待新任务
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

    def add_task(self, url: str):
        with self.lock:
            self.stats.record_task_submission(url)  # 记录任务提交
            self.task.put(url)
            self.url_counts[url] = self.url_counts.get(url, 0) + 1
        logging.info(f"任务已添加到队列: {url}")

    def stop(self):
        """
        停止 XKW 实例，并保存统计数据。
        """
        try:
            logging.info("停止 XKW 实例。")
            self.work = False
            self.task.put(None)  # 发送退出信号
            self.stats.save_statistics()
            logging.info("统计数据已保存。")
            self.page.close()
            logging.info("XKW 实例已停止。")
        except Exception as e:
            logging.error(f"停止过程中出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"停止过程中出错: {e}", is_error=True)


class AutoDownloadManager:
    def __init__(self, uploader=None, notifier_config=None):
        """
        初始化 AutoDownloadManager。

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
        self.uploader = uploader

        # 初始化统计管理器
        self.stats = StatisticsManager()

        # 创建五个 ChromiumOptions，每个指定不同的端口和用户数据路径
        co1 = ChromiumOptions().set_local_port(9222).set_user_data_path('data1')
        co2 = ChromiumOptions().set_local_port(9333).set_user_data_path('data2')
        co3 = ChromiumOptions().set_local_port(9444).set_user_data_path('data3')
        co4 = ChromiumOptions().set_local_port(9555).set_user_data_path('data4')
        co5 = ChromiumOptions().set_local_port(9666).set_user_data_path('data5')

        # 启动五个 Chromium 浏览器实例
        browser1 = Chromium(co1)
        browser2 = Chromium(co2)
        browser3 = Chromium(co3)
        browser4 = Chromium(co4)
        browser5 = Chromium(co5)

        # 确保下载目录存在
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        # 使用相同的下载目录
        download_dir = DOWNLOAD_DIR

        # 创建五个 XKW 实例，所有实例使用相同的下载目录
        xkw1 = XKW(thread=5, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   stats=self.stats, co=co1, manager=self)
        xkw2 = XKW(thread=5, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   stats=self.stats, co=co2, manager=self)
        xkw3 = XKW(thread=5, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   stats=self.stats, co=co3, manager=self)
        xkw4 = XKW(thread=5, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   stats=self.stats, co=co4, manager=self)
        xkw5 = XKW(thread=5, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   stats=self.stats, co=co5, manager=self)

        # 将 xkw 实例添加到 xkw_instances 列表中
        self.xkw_instances = [xkw1, xkw2, xkw3, xkw4, xkw5]

        # 初始化轮询计数器
        self.next_xkw_index = 0
        self.xkw_lock = threading.Lock()

    def get_available_xkw_instances(self, current_instance):
        """
        获取可用于重试下载的 XKW 实例列表，排除当前实例。
        """
        return [xkw for xkw in self.xkw_instances if xkw != current_instance]

    def add_task(self, url: str):
        """
        添加单个 URL 到下载任务队列。

        :param url: 要添加的单个 URL。
        """
        try:
            logging.info(f"准备添加 URL 到下载任务队列: {url}")
            with self.xkw_lock:
                xkw = self.xkw_instances[self.next_xkw_index]
                self.next_xkw_index = (self.next_xkw_index + 1) % len(self.xkw_instances)
            xkw.add_task(url)
            logging.info(f"已将 URL 添加到 XKW 实例 {self.xkw_instances.index(xkw)+1} 的任务队列: {url}")
        except Exception as e:
            logging.error(f"添加 URL 时发生错误: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"添加 URL 时发生错误: {e}", is_error=True)

    def stop(self):
        """
        停止 AutoDownloadManager 和其内部的所有 XKW 实例。
        """
        try:
            logging.info("停止 AutoDownloadManager 和所有 XKW 实例。")
            for xkw in self.xkw_instances:
                xkw.stop()
        except Exception as e:
            logging.error(f"停止过程中出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"停止过程中出错: {e}", is_error=True)
