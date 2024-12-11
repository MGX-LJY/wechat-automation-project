import csv
import json
import logging
import os
import queue
import random
import re
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Tuple

from DrissionPage import ChromiumPage, ChromiumOptions, Chromium
from DrissionPage.errors import ContextLostError
from rapidfuzz import fuzz

from src.notification.notifier import Notifier

# 配置基础目录和下载目录
BASE_DIR = os.path.dirname(__file__)
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'Downloads')
STATE_DIR = os.path.join(BASE_DIR, 'state')  # 新增状态保存目录

# 初始化日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class ErrorHandler:
    """错误处理器类，用于捕获异常并发送通知。"""

    def __init__(self, notifier: Notifier):
        self.notifier = notifier

    def handle_exception(self, exception):
        """处理异常并发送通知。"""
        error_message = f"ErrorHandler 捕获到异常: {exception}"
        logging.error(error_message, exc_info=True)
        if self.notifier:
            self.notifier.notify(error_message, is_error=True)  # 发送错误通知


class XKW:
    """
    XKW 类用于管理自动化下载任务。

    参数:
    - thread: 线程数，即同时处理的任务数。
    - work: 是否开始工作。
    - download_dir: 下载目录。
    - uploader: 上传器实例，用于处理下载完成后的文件上传。
    - notifier: 通知器实例，用于发送通知消息。
    - co: ChromiumOptions 实例，用于配置浏览器。
    - manager: 管理器实例，用于管理多个 XKW 实例。
    - id: 实例的唯一标识符。
    - accounts: 账号列表，每个实例独有。
    """
    # 初始化下载计数器和锁
    download_counts_lock = threading.RLock()
    download_counts = {}
    download_counts_file = 'download_counts.json'
    download_log_file = 'download_log.csv'
    download_counts_loaded = False  # 标记是否已加载

    def __init__(self, thread=1, work=False, download_dir=None, uploader=None, notifier=None, co=None, manager=None,
                 id=None, accounts=None):
        self.id = id or str(uuid.uuid4())  # 分配唯一 ID
        self.thread = thread  # 线程数
        self.work = work  # 是否开始工作
        self.uploader = uploader  # 上传器
        self.notifier = notifier  # 通知器
        self.tabs = queue.Queue()  # 标签页队列
        self.task = queue.Queue()  # 下载任务队列
        self.co = co or ChromiumOptions()  # 浏览器配置
        self.co.no_imgs()  # 不加载图片
        self.co.set_download_path(download_dir or DOWNLOAD_DIR)  # 设置下载路径
        self.page = ChromiumPage(self.co)  # 创建 ChromiumPage 实例
        self.last_download_time = 0  # 记录上一次下载任务启动的时间
        self.download_lock = threading.Lock()  # 用于同步下载任务的启动时间
        self.manager = manager  # 保存 AutoDownloadManager 实例
        self.is_active = True  # 标记实例是否可用
        self.account_index_lock = threading.RLock()  # 新增锁，用于账号索引的同步
        self.login_status = False         # 登录状态
        self.daily_limit_reached = False  # 是否达到每日下载上限
        self.weekly_limit_reached = False  # 是否达到每周下载上限
        self.admin_intervention_required = False  # 是否需要管理员介入
        self.tab_ids = {}  # 新增：保存标签页与ID的映射
        self.tab_id_counter = 0  # 新增：用于给tab分配自增ID

        # 添加账号列表和当前账号索引
        if accounts is not None:
            self.accounts = accounts  # 使用传入的账号列表
        else:
            self.accounts = []  # 默认空列表
        self.current_account_index = 0  # 当前账号索引

        # 只在第一次初始化时加载下载计数
        if not XKW.download_counts_loaded:
            with XKW.download_counts_lock:
                if not XKW.download_counts_loaded:
                    if os.path.exists(XKW.download_counts_file):
                        with open(XKW.download_counts_file, 'r', encoding='utf-8') as f:
                            try:
                                XKW.download_counts = json.load(f)
                                logging.info(f"[{self.id}] 已加载下载计数数据: {XKW.download_counts}")
                            except json.JSONDecodeError:
                                logging.error(f"[{self.id}] 下载计数文件 '{XKW.download_counts_file}' 格式错误，初始化为空。")
                                XKW.download_counts = {}
                    else:
                        # 如果文件不存在，创建一个空的下载日志文件
                        with open(XKW.download_log_file, 'w', encoding='utf-8', newline='') as csvfile:
                            log_writer = csv.writer(csvfile)
                            log_writer.writerow(['时间', '账号', '下载次数'])
                        logging.info(f"[{self.id}] 下载计数文件 '{XKW.download_counts_file}' 不存在，已创建新的下载日志文件。")
                    XKW.download_counts_loaded = True

        # 如果存在下载日志文件不存在则创建
        if not os.path.exists(XKW.download_log_file):
            with open(XKW.download_log_file, 'w', encoding='utf-8', newline='') as csvfile:
                log_writer = csv.writer(csvfile)
                log_writer.writerow(['时间', '账号', '下载次数'])
            logging.info(f"[{self.id}] 下载日志文件 '{XKW.download_log_file}' 已创建。")

        logging.info(f"[{self.id}] ChromiumPage initialized with address: {self.page.address}")
        self.dls_url = "https://www.zxxk.com/soft/softdownload?softid={xid}"
        self.make_tabs()  # 初始化标签页
        if self.work:
            self.manager_thread = threading.Thread(target=self.run, daemon=True)
            self.manager_thread.start()
            logging.info("XKW manager 线程已启动。")

        self.handle_login_lock = threading.RLock()

        # 初始化状态保存路径
        self.state_file = os.path.join(STATE_DIR, f"[{self.id}] {self.id}_state.json")
        self.save_state_lock = threading.RLock()

        # 记录失败次数
        self.failure_count = 0
        self.failure_threshold = 3  # 失败阈值

    def save_state(self):
        """
        保存当前实例的状态到 JSON 文件。
        """
        with self.save_state_lock:
            state = {
                'instance_status': self.instance_status,
                'login_status': self.login_status,
                'daily_limit_reached': self.daily_limit_reached,
                'weekly_limit_reached': self.weekly_limit_reached,
                'admin_intervention_required': self.admin_intervention_required,
                'current_account_index': self.current_account_index
            }
            try:
                with open(self.state_file, 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False, indent=4)
                logging.info(f"[{self.id}] 实例状态已保存到 {self.state_file}")
            except Exception as e:
                logging.error(f"[{self.id}] 保存实例状态时出错: {e}", exc_info=True)
                if self.notifier:
                    self.notifier.notify(f"[{self.id}] 保存实例状态时出错: {e}", is_error=True)

    def load_state(self):
        """
        从 JSON 文件加载当前实例的状态。
        """
        if not os.path.exists(self.state_file):
            logging.info(f"[{self.id}] 状态文件不存在，跳过加载状态。")
            return

        with self.save_state_lock:
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                self.set_instance_status(state.get('instance_status', 'inactive'))
                self.login_status = state.get('login_status', False)
                self.daily_limit_reached = state.get('daily_limit_reached', False)
                self.weekly_limit_reached = state.get('weekly_limit_reached', False)
                self.admin_intervention_required = state.get('admin_intervention_required', False)
                self.current_account_index = state.get('current_account_index', 0)
                logging.info(f"[{self.id}] 已加载实例状态。")
            except json.JSONDecodeError:
                logging.error(f"[{self.id}] 状态文件格式错误，无法加载状态。")
            except Exception as e:
                logging.error(f"[{self.id}] 加载实例状态时出错: {e}", exc_info=True)
                if self.notifier:
                    self.notifier.notify(f"[{self.id}] 加载实例状态时出错: {e}", is_error=True)

    @property
    def instance_status(self) -> str:
        """返回实例的状态：'active' 或 'inactive'。"""
        return 'active' if self.is_active else 'inactive'

    def set_instance_status(self, status: str):
        """根据状态字符串设置实例的活跃状态。"""
        if status == 'active':
            if not self.is_active:
                self.is_active = True
                logging.info(f"[{self.id}] 实例状态已设置为 active。")
        elif status == 'inactive':
            if self.is_active:
                self.is_active = False
                logging.info(f"[{self.id}] 实例状态已设置为 inactive。")
        else:
            logging.warning(f"[{self.id}] 无法识别的实例状态: {status}")
        self.save_state()

    def set_login_status(self, status: bool):
        """设置实例的登录状态。"""
        self.login_status = status
        logging.info(f"[{self.id}] 登录状态已设置为: {'已登录' if status else '未登录'}")
        self.save_state()

    def set_daily_limit_reached(self, reached: bool):
        """设置是否达到每日下载上限。"""
        self.daily_limit_reached = reached
        logging.info(f"[{self.id}] 每日下载上限已{'达到' if reached else '未达到'}。")
        self.save_state()

    def set_weekly_limit_reached(self, reached: bool):
        """设置是否达到每周下载上限。"""
        self.weekly_limit_reached = reached
        logging.info(f"[{self.id}] 每周下载上限已{'达到' if reached else '未达到'}。")
        self.save_state()

    def set_admin_intervention_required(self, required: bool):
        """设置是否需要管理员介入。"""
        self.admin_intervention_required = required
        logging.info(f"[{self.id}] 需要管理员介入: {'是' if required else '否'}。")
        self.save_state()

    def __repr__(self):
        """返回实例的字符串表示。"""
        return f"XKW(id={self.id})"

    def close_tabs(self, tabs):
        """
        关闭给定的浏览器标签页列表。

        参数:
        - tabs: 要关闭的标签页列表。
        """
        for tab in tabs:
            try:
                tab.close()
                logging.debug(f"[{self.id}] 关闭了一个浏览器标签页。")
            except Exception as e:
                logging.error(f"[{self.id}] 关闭标签页时出错: {e}", exc_info=True)

    def make_tabs(self):
        """
        创建浏览器标签页，以供下载使用，并为每个标签页分配一个唯一ID。
        """
        try:
            tabs = self.page.get_tabs()
            logging.debug(f"[{self.id}] 当前标签页: {tabs}")
            while len(tabs) < self.thread:
                self.page.new_tab()
                tabs = self.page.get_tabs()
                logging.debug(f"[{self.id}] 添加新标签页。总标签页数: {len(tabs)}")
            if len(tabs) > self.thread:
                self.close_tabs(tabs[self.thread:])
                tabs = self.page.get_tabs()[:self.thread]

            for tab in tabs:
                # 为每个tab分配ID并保存映射
                self.tab_id_counter += 1
                tab_id = f"{self.id}_tab{self.tab_id_counter}"
                self.tab_ids[tab] = tab_id
                self.tabs.put(tab)
                logging.info(f"[{self.id}][{tab_id}] 初始化标签页: {tab}")

            logging.info(f"[{self.id}] 初始化了 {self.thread} 个标签页用于下载。")
        except Exception as e:
            logging.error(f"[{self.id}] 初始化标签页时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"[{self.id}] 初始化标签页时出错: {e}", is_error=True)

    def reset_tab(self, tab, tab_id):
        """
        重置标签页，将其导航到空白页以清除状态。

        参数:
        - tab: 需要重置的标签页。
        """
        try:
            time.sleep(0.1)
            tab.get('about:blank')
            logging.info(f"[{self.id}][{tab_id}]标签页已重置为 about:blank。")
        except Exception as e:
            logging.error(f"[{self.id}][{tab_id}] 导航标签页到空白页时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"[{self.id}][{tab_id}] 导航标签页到空白页时出错: {e}",
                                     is_error=True)

    def match_downloaded_file(self, title, soft_id, tab_id):
        """
        匹配下载的文件，基于给定的标题在下载目录中寻找匹配的文件。

        参数:
        - title: 要匹配的文件标题。

        返回:
        - 匹配到的文件路径，若未找到则返回 None。
        """
        logging.info(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 开始匹配下载的文件，标题: {title}")

        try:
            if not title:
                logging.error(f"[{self.id}][{tab_id}][soft_id:{soft_id}]  标题为空，无法匹配下载文件")
                return None

            download_dir = self.co.download_path
            logging.debug(f"[{self.id}][{tab_id}][soft_id:{soft_id}]  下载目录: {download_dir}")

            # 配置参数
            max_wait_time = 1800  # 最大等待时间（秒）
            initial_wait = 60  # 初始等待时间（秒）
            initial_interval = 0.5  # 前60秒的重试间隔（秒）
            subsequent_interval = 5  # 后续的重试间隔（秒）
            elapsed_time = 0

            # 预期的文件扩展名，可以根据需求调整
            expected_extensions = [
                '.pdf', '.mkv', '.mp4', '.zip', '.rar', '.7z',
                '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.wps'
            ]

            # 处理标题：保留中文、数字、空格、下划线、破折号、加号
            processed_title = re.sub(r'[^\u4e00-\u9fa5\d\s_\-\+]', '', title)
            processed_title = processed_title.strip().lower()
            processed_title = re.sub(r'[\-]+', ' ', processed_title)
            processed_title = re.sub(r'\++', ' ', processed_title)

            # 定义初始相似度阈值
            similarity_threshold = 100  # 前90秒的阈值

            # 正则表达式模式，用于匹配带数字编号的文件名，例如：[123456]filename.pdf
            numbered_file_pattern = re.compile(r'^\[\d+\]', re.IGNORECASE)

            while elapsed_time < max_wait_time:
                logging.debug(f"[{self.id}]当前下载目录下的文件:")
                candidates = []
                for file_name in os.listdir(download_dir):
                    logging.debug(f" - {file_name}")

                    # 跳过带数字编号的文件
                    if numbered_file_pattern.match(file_name):
                        logging.debug(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 文件 {file_name} 带有数字编号前缀，跳过。")
                        continue

                    # 过滤不期望的文件扩展名
                    _, ext = os.path.splitext(file_name)
                    if ext.lower() not in expected_extensions:
                        logging.debug(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 文件 {file_name} 的扩展名不在预期范围内，跳过。")
                        continue

                    # 忽略未下载完成的文件
                    if file_name.endswith('.crdownload'):
                        logging.debug(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 文件 {file_name} 尚未下载完成，跳过。")
                        continue

                    # 处理文件名：保留中文、数字、空格、下划线、破折号、加号
                    processed_file_name = re.sub(r'[^\u4e00-\u9fa5\d\s_\-\+]', '', file_name)
                    processed_file_name = processed_file_name.strip().lower()
                    processed_file_name = re.sub(r'[\-]+', ' ', processed_file_name)
                    processed_file_name = re.sub(r'\++', ' ', processed_file_name)

                    # 计算相似度
                    similarity = fuzz.partial_ratio(processed_title, processed_file_name)
                    logging.debug(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 文件 '{file_name}' 与标题的相似度: {similarity}")

                    if similarity >= similarity_threshold:
                        candidates.append((file_name, similarity))

                if candidates:
                    # 选择相似度最高的文件
                    best_match = max(candidates, key=lambda x: x[1])
                    best_file_name, best_similarity = best_match
                    file_path = os.path.join(download_dir, best_file_name)
                    if os.path.exists(file_path):
                        logging.info(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 匹配到下载的文件: {best_file_name} (相似度: {best_similarity})")
                        return file_path
                    else:
                        logging.debug(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 文件 {file_path} 不存在，等待中...")

                # 更新相似度阈值，根据 elapsed_time 决定
                if elapsed_time < 90:
                    similarity_threshold = 100
                elif elapsed_time < 360:
                    similarity_threshold = 85
                elif elapsed_time < 720:
                    similarity_threshold = 75
                else:
                    similarity_threshold = 65
                logging.debug(f"当前相似度阈值: {similarity_threshold}")

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
                    f"[{self.id}][{tab_id}][soft_id:{soft_id}] 未找到匹配的文件 '{title}'，等待 {sleep_time} 秒后重试... (已等待 {elapsed_time}/{max_wait_time} 秒)"
                )

            # 超过最大等待时间，放弃匹配
            logging.error(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 在 {max_wait_time} 秒内未能找到匹配的下载文件: {title}")
            if self.notifier:
                self.notifier.notify(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 在 {max_wait_time} 秒内未能找到匹配的下载文件: {title}", is_error=True)
            return None
        except Exception as e:
            logging.error(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 发生错误: {e}")
            if self.notifier:
                self.notifier.notify(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 发生错误: {e}", is_error=True)

    def extract_id_and_title(self, tab, url) -> Tuple[str, str]:
        """
        从页面中提取 soft_id 和标题。

        参数:
        - tab: 浏览器标签页。
        - url: 要提取的页面 URL。

        返回:
        - soft_id: 提取到的软件 ID。
        - title: 提取到的标题。
        """
        tab_id = self.tab_ids.get(tab, "unknown_tab")  # 获取 tab 对应的 ID，如果没有则返回一个默认值
        try:
            # 尝试加载页面
            tab.get(url)
            logging.info(f"[{self.id}][{tab_id}]开始从页面提取 ID 和标题：URL: {url}")

            tab.wait.load_start(timeout=10)
            tab.wait.doc_loaded(timeout=30)

            # 停止页面加载以加快速度
            tab.stop_loading()

            # 使用提供的方法提取标题
            h1 = tab.s_ele("t:h1@@class=res-title clearfix")
            if h1:
                title_element = h1.child("t:span")
                if title_element:
                    title = title_element.text.strip()
                    logging.info(f"[{self.id}][{tab_id}]从 h1 标签中获取到标题: {title}")
                else:
                    logging.error(f"[{self.id}][{tab_id}]无法从 h1 标签中获取到 span 元素，URL: {url}")
                    return None, None
            else:
                logging.error(f"[{self.id}][{tab_id}]无法从页面中找到 h1.res-title 标签，URL: {url}")
                return None, None

            # 检测页面是否包含“独家”和“教辅”，如果包含则跳过
            ele_dujia = tab.ele('tag:em@text()=独家')
            ele_jiaofu = tab.ele('tag:em@text()=教辅')
            if ele_dujia and ele_jiaofu:
                logging.info(f"[{self.id}][{tab_id}]内容包含‘独家’和‘教辅’，跳过该任务。URL: {url}")
                return None, None  # 信号跳过

            # 从 URL 中提取 soft_id
            match = re.search(r'/soft/(\d+)\.html', url)
            if match:
                soft_id = match.group(1)
                logging.info(f"[{self.id}][{tab_id}]从 URL 中提取到 soft_id: {soft_id}")
            else:
                logging.error(f"[{self.id}][{tab_id}]无法从 URL 中提取 soft_id，跳过 URL: {url}")
                return None, None

            return soft_id, title

        except ContextLostError as e:
            logging.error(f"[{self.id}][{tab_id}]页面上下文丢失，重新获取标签页。错误: {e}")
            if self.notifier:
                self.notifier.notify(f"[{self.id}][{tab_id}]页面上下文丢失，重新获取标签页。错误: {e}", is_error=True)
            # 重新获取标签页
            try:
                tab = self.tabs.get(timeout=10)
                return self.extract_id_and_title(tab, url)
            except queue.Empty:
                logging.error(f"[{self.id}][{tab_id}]无法重新获取标签页，跳过 URL: {url}")
                if self.notifier:
                    self.notifier.notify(f"[{self.id}][{tab_id}]无法重新获取标签页，跳过 URL: {url}", is_error=True)
                return None, None

        except Exception as e:
            logging.error(f"[{self.id}][{tab_id}]提取 ID 和标题时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"[{self.id}][{tab_id}]提取 ID 和标题时出错: {e}", is_error=True)
            return None, None

    def is_logged_in(self, tab):
        """
        检查当前是否已登录，并更新登录状态属性。
        如果未登录，则自动执行登录程序。
        增加标签页 ID 以便追踪。
        """
        tab_id = self.tab_ids.get(tab, "unknown_tab")  # 获取 tab 对应的 ID
        try:
            results = []
            for _ in range(2):
                result = self._check_login_status(tab)
                results.append(result)
                time.sleep(1)  # 可选：增加一点延迟
            if results[0] == results[1]:
                logged_in = results[0]
            else:
                # 如果前两次结果不一致，进行第三次检查
                logged_in = self._check_login_status(tab)

            if not logged_in:
                logging.info(f"[{self.id}][{tab_id}] 未登录，开始自动登录。")
                login_success = self.login(tab)
                if login_success:
                    logged_in = True
                else:
                    logged_in = False

            # 设置登录状态
            self.set_login_status(logged_in)
            logging.info(f"[{self.id}][{tab_id}] 登录状态: {'已登录' if logged_in else '未登录'}")
            return logged_in
        except Exception as e:
            logging.error(f"[{self.id}][{tab_id}] 检查登录状态时出错: {e}", exc_info=True)
            return False

    def _check_login_status(self, tab):
        """
        实际执行一次登录状态检查。
        增加标签页 ID 以便追踪。
        """
        tab_id = self.tab_ids.get(tab, "unknown_tab")  # 获取 tab 对应的 ID
        try:
            # 访问主页以检查登录状态
            tab.get('https://www.zxxk.com')
            time.sleep(10)  # 确保页面加载完成
            # 尝试找到“我的”元素，登录后该元素应存在
            my_element = tab.ele('text:我的', timeout=5)
            if my_element:
                logging.debug(f"[{self.id}][{tab_id}] 找到“我的”元素，用户已登录。")
                return True
            else:
                # 如果找不到“我的”元素，尝试查找“登录”按钮，未登录时应存在
                login_element = tab.ele('text:登录', timeout=5)
                return not bool(login_element)
        except Exception as e:
            logging.error(f"[{self.id}][{tab_id}] 执行登录状态检查时出错: {e}", exc_info=True)
            return False

    def login(self, tab):
        """
        执行登录操作，使用当前账号索引的账号。
        如果所有账号均无法登录，返回 False。
        增加标签页 ID 以便追踪。
        """
        tab_id = self.tab_ids.get(tab, "unknown_tab")  # 获取 tab 对应的 ID
        max_retries = len(self.accounts)  # 确保尝试所有账号
        retries = 0
        while retries < max_retries:
            account = self.accounts[self.current_account_index]
            username = account['username']
            password = account['password']
            nickname = account.get('nickname', username)
            try:
                # 访问登录页面
                tab.get('https://sso.zxxk.com/login')
                logging.info(f"[{self.id}][{tab_id}] 账号 {nickname} ({username}) 正在访问登录页面。")
                time.sleep(random.uniform(1, 2))  # 增加随机延迟，等待页面完全加载

                # 点击“账户密码/验证码登录”按钮
                login_switch_button = tab.ele('tag:button@@class=another@@text():账户密码/验证码登录', timeout=10)
                if login_switch_button:
                    login_switch_button.click()
                    logging.info(
                        f"[{self.id}][{tab_id}] 账号 {nickname} ({username}) 点击“账户密码/验证码登录”按钮成功。")
                    time.sleep(random.uniform(1, 2))  # 等待登录表单切换完成

                # 获取用户名和密码输入框
                username_field = tab.ele('#username', timeout=10)
                password_field = tab.ele('#password', timeout=10)

                # 清空输入框，确保没有残留内容
                username_field.clear()
                password_field.clear()
                logging.info(f"[{self.id}][{tab_id}] 账号 {nickname} ({username}) 清空用户名和密码输入框成功。")
                time.sleep(random.uniform(1, 2))  # 等待输入框清空

                # 输入用户名
                username_field.input(username)
                logging.info(f"[{self.id}][{tab_id}] 账号 {nickname} ({username}) 输入用户名成功。")
                time.sleep(random.uniform(1, 2))  # 增加延迟

                # 输入密码
                password_field.input(password)
                logging.info(f"[{self.id}][{tab_id}] 账号 {nickname} ({username}) 输入密码成功。")
                time.sleep(random.uniform(1, 2))  # 增加延迟

                # 点击登录按钮
                login_button = tab.ele('#accountLoginBtn', timeout=10)
                if login_button:
                    login_button.click()
                    logging.info(f"[{self.id}][{tab_id}] 账号 {nickname} ({username}) 点击登录按钮成功。")
                    time.sleep(random.uniform(1, 2))  # 等待登录结果

                # 检查是否登录成功
                if self.is_logged_in(tab):
                    logging.info(f"[{self.id}][{tab_id}] 账号 {nickname} ({username}) 登录成功。")
                    if self.notifier:
                        self.notifier.notify(f"[{self.id}][{tab_id}] 账号 {nickname} ({username}) 登录成功。")
                    return True
                else:
                    logging.warning(f"[{self.id}][{tab_id}] 账号 {nickname} ({username}) 登录失败，尝试下一个账号。")
                    if self.notifier:
                        self.notifier.notify(f"[{self.id}][{tab_id}] 账号 {nickname} ({username}) 登录失败。",
                                             is_error=True)
                    retries += 1
                    self.current_account_index = (self.current_account_index + 1) % len(self.accounts)
            except Exception as e:
                logging.error(f"[{self.id}][{tab_id}] 账号 {nickname} ({username}) 登录过程中出现错误：{e}",
                              exc_info=True)
                retries += 1

        # 如果重试次数用尽，发送通知并返回 False
        logging.error(f"[{self.id}][{tab_id}] 所有登录尝试失败，无法登录。")
        if self.notifier:
            self.notifier.notify(f"[{self.id}][{tab_id}] 所有登录尝试失败，无法登录。请检查账号状态或登录流程。",
                                 is_error=True)
        return False

    def get_nickname(self, tab) -> str:
        """
        悬停在“我的”元素上，并从下拉菜单中提取当前账号的昵称。
        支持昵称格式为“全能数字”或“全能数字X”，例如“全能02”或“全能1x”。
        增加标签页 ID 以便追踪。

        参数:
        - tab: 当前浏览器标签页。

        返回:
        - nickname: 当前账号的昵称。如果无法提取或不符合格式，则返回空字符串。
        """
        tab_id = self.tab_ids.get(tab, "unknown_tab")  # 获取 tab 对应的 ID
        max_attempts = 3
        attempt = 0
        while attempt < max_attempts:
            try:
                if attempt > 1:
                    # 在第2次（attempt=1）及以后尝试前先重新访问主页
                    logging.debug(f"[{self.id}][{tab_id}] 重试获取昵称，重新访问 https://www.zxxk.com")
                    tab.get('https://www.zxxk.com')
                    time.sleep(random.uniform(1, 2))  # 给页面足够的加载时间

                # 找到“我的”元素
                my_element = tab.ele('text:我的', timeout=10)
                if not my_element:
                    logging.error(f"[{self.id}][{tab_id}] 未找到“我的”元素，无法提取昵称。")
                    raise ValueError("未找到“我的”元素")

                # 悬停在“我的”元素上
                time.sleep(random.uniform(0.5, 1.0))  # 随机延迟，确保元素可交互
                my_element.hover()
                time.sleep(random.uniform(0.5, 1.0))  # 随机延迟，等待下拉菜单显示

                # 提取昵称
                nickname_element = tab.ele('tag:a@@class=username', timeout=5)
                if nickname_element:
                    nickname_text = nickname_element.text.strip()
                    logging.info(f"[{self.id}][{tab_id}] 提取到的昵称文本: {nickname_text}")

                    # 使用正则表达式匹配“全能”后跟一个或多个数字，后面可选“X”或“x”
                    match = re.match(r'^全能\d+([Xx])?$', nickname_text)
                    if match:
                        nickname = match.group()
                        logging.info(f"[{self.id}][{tab_id}] 提取到符合格式的昵称: {nickname}")
                        return nickname
                    else:
                        logging.error(
                            f"[{self.id}][{tab_id}] 提取到的昵称不符合格式要求（全能数字 或 全能数字X 或 全能数字x）：{nickname_text}")
                        raise ValueError("昵称格式不正确")
                else:
                    logging.error(f"[{self.id}][{tab_id}] 未找到昵称元素，无法提取昵称。")
                    raise ValueError("未找到昵称元素")

            except Exception as e:
                attempt += 1
                logging.error(f"[{self.id}][{tab_id}] 提取昵称时出错（尝试 {attempt}/{max_attempts}）：{e}", exc_info=True)
                if attempt >= max_attempts:
                    logging.error(f"[{self.id}][{tab_id}] 已达到最大尝试次数，无法提取有效昵称。")
                    return ""
                else:
                    # 等待一段时间后重试
                    time.sleep(1)
        return ""

    def listener(self, tab, download, url, title, soft_id):
        """
        监听下载过程，处理下载链接的获取和确认按钮的点击。
        移除了与登录相关的逻辑。

        参数:
        - tab: 当前浏览器标签页。
        - download: 下载按钮元素。
        - url: 要下载的URL。
        - title: 下载项的标题。
        - soft_id: 下载项的软ID。

        返回:
        - True: 如果下载成功或任务已妥善处理。
        - False: 如果下载失败且需要进一步处理。
        """
        tab_id = self.tab_ids.get(tab, "unknown_tab")
        try:
            logging.info(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 开始下载 {url}")
            tab.listen.start(True, method="GET")  # 开始监听网络请求
            download.click(by_js=True)  # 点击下载按钮

            # 尝试立即点击确认按钮，但如果未找到，不报错，直接继续
            time.sleep(random.uniform(5, 6))  # 随机延迟，等待页面加载
            self.click_confirm_button(tab, soft_id)

            # 设置总的等待时间和间隔
            max_wait_time = 60  # 修改为60秒
            elapsed_time = 0
            retry_interval = 5  # 每次循环等待的间隔时间（秒）

            logging.debug(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 设置最大等待时间为 {max_wait_time} 秒。")

            # 开始监听循环
            while elapsed_time < max_wait_time:
                start_loop_time = time.time()
                logging.debug(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 进入监听循环，已等待 {elapsed_time} 秒。")
                try:
                    for item in tab.listen.steps(timeout=10):  # 设置适当的超时
                        if item.url.startswith("https://files.zxxk.com/?mkey="):
                            tab.listen.stop()
                            tab.stop_loading()
                            logging.info(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 下载链接获取成功: {item.url}")
                            logging.info(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 下载成功，开始处理上传任务: {url}")
                            # 记录账号下载次数
                            self.account_count(url, tab, soft_id)
                            self.tabs.put(tab)
                            # 匹配下载的文件
                            file_path = self.match_downloaded_file(title, soft_id, tab_id)
                            if not file_path:
                                self.switch_browser_and_retry(tab, url, soft_id)
                                logging.error(
                                    f"[{self.id}][{tab_id}][soft_id:{soft_id}] 匹配下载的文件失败，切换浏览器进行下载: {url}")
                                if self.notifier:
                                    self.notifier.notify(
                                        f"[{self.id}][{tab_id}][soft_id:{soft_id}] 匹配下载文件失败，切换浏览器下载: {url}",
                                        is_error=True)
                                return True

                            # 获取当前账号的昵称
                            current_account = self.accounts[self.current_account_index]
                            nickname = current_account.get('nickname', current_account['username'])

                            # 上传逻辑
                            if self.uploader:
                                try:
                                    self.uploader.add_upload_task(file_path, soft_id)
                                    logging.info(
                                        f"[{self.id}][{tab_id}][soft_id:{soft_id}] 已将文件 {file_path} 和 soft_id {soft_id} 添加到上传任务队列。")
                                except Exception as e:
                                    logging.error(
                                        f"[{self.id}][{tab_id}][soft_id:{soft_id}] 添加上传任务时发生错误: {e}",
                                        exc_info=True)
                                    if self.notifier:
                                        self.notifier.notify(
                                            f"[{self.id}][{tab_id}][soft_id:{soft_id}] 添加上传任务时发生错误: {e}",
                                            is_error=True)
                            else:
                                logging.warning(
                                    f"[{self.id}][{tab_id}][soft_id:{soft_id}] Uploader 未设置，无法传递上传任务。")

                            self.reset_tab(tab, tab_id)
                            return True
                except Exception as e:
                    logging.error(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 监听过程中出错: {e}", exc_info=True)
                    if self.notifier:
                        self.notifier.notify(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 监听过程中出错: {e}",
                                             is_error=True)
                    self.reset_tab(tab, tab_id)
                    self.tabs.put(tab)
                    return False

                # 更新已等待时间
                loop_duration = time.time() - start_loop_time
                elapsed_time += loop_duration
                logging.debug(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 已累计等待时间: {elapsed_time:.2f} 秒。")

                # 确保循环不会因快速迭代而占用过多资源
                time.sleep(retry_interval)
                # 尝试点击确认按钮以确保页面状态
                self.click_confirm_button(tab)
            # 超过最大等待时间，下载失败
            logging.error(
                f"[{self.id}][{tab_id}][soft_id:{soft_id}] 在 {max_wait_time} 秒内未能找到匹配的下载文件: {url}")
            if self.notifier:
                self.notifier.notify(
                    f"[{self.id}][{tab_id}][soft_id:{soft_id}] 在 {max_wait_time} 秒内未能找到匹配的下载文件: {url}",
                    is_error=True)
            self.manager.disable_xkw_instance(self)
            self.switch_browser_and_retry(tab, url, soft_id)
            self.reset_tab(tab, tab_id)
            self.tabs.put(tab)
            # 检查账号是否登录
            if not self.is_logged_in(tab):
                logging.warning(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 账号未登录，尝试重新登录。")
                if self.notifier:
                    self.notifier.notify(
                        f"[{self.id}][{tab_id}][soft_id:{soft_id}] 账号未登录，进行登录并进行换实例下载。", is_error=True)
                return False

            # 如果超时并且登录状态下，设置需要管理员介入
            if self.login_status:
                self.set_admin_intervention_required(True)
                self.manager.disable_xkw_instance(self)
                logging.info(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 需要管理员介入以恢复实例。")
                if self.notifier:
                    self.notifier.notify(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 需要管理员介入以恢复实例。",
                                         is_error=True)

        except Exception as e:
            logging.error(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 下载过程中出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 下载过程中出错: {e}", is_error=True)
            self.reset_tab(tab, tab_id)
            self.tabs.put(tab)
            self.switch_browser_and_retry(tab, url, soft_id)
            return False

        return False  # 默认返回 False 以示未成功

    def click_confirm_button(self, tab, soft_id):
        """
        尝试点击确认按钮。

        参数:
        - tab: 当前浏览器标签页。

        返回:
        - True: 如果点击成功或找到确认按钮。
        - False: 如果未找到确认按钮。
        """
        tab_id = self.tab_ids.get(tab, "unknown_tab")
        try:
            iframe = tab.get_frame('#layui-layer-iframe100002')
            if iframe:
                a = iframe("t:a@@class=balance-payment-btn@@text()=确认")
                if a:
                    a.click()
                    logging.info(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 点击确认按钮成功。")
                    return True
                else:
                    logging.debug(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 未找到确认按钮。")
            else:
                logging.debug(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 未找到确认按钮的 iframe。")
        except Exception as e:
            logging.error(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 尝试点击确认按钮时发生错误: {e}", exc_info=True)
        return False

    def account_count(self, url, tab, soft_id):
        """
        记录账号的下载次数，并在达到每日或每周上限时切换账号。

        参数:
        - url: 下载的URL。
        - tab: 当前浏览器标签页。
        """
        tab_id = self.tab_ids.get(tab, "unknown_tab")
        try:
            # 获取当前日期和时间
            today = datetime.today()
            date_str = today.strftime('%Y-%m-%d')
            week_number = today.strftime('%Y-%W')  # 年份和周数组合，周从星期一开始

            time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            with self.account_index_lock:
                current_account_nickname = self.get_nickname(tab)
                if not current_account_nickname:
                    logging.warning("无法获取当前账号昵称，跳过记录。")
                    if self.notifier:
                        self.notifier.notify("无法获取当前账号昵称，跳过记录。", is_error=True)
                    return

                # 检查昵称是否在账号列表中
                matched_account = None
                for index, account in enumerate(self.accounts):
                    if account.get('nickname') == current_account_nickname:
                        self.current_account_index = index
                        matched_account = account
                        logging.info(
                            f"[{self.id}]匹配到账号：索引 {self.current_account_index}, 昵称: {current_account_nickname} ({matched_account.get('username', '')})")
                        break

                if not matched_account:
                    logging.warning(f"[{self.id}]未在账号列表中找到匹配的昵称：{current_account_nickname}")
                    with XKW.download_counts_lock:
                        with open(XKW.download_log_file, 'a', encoding='utf-8', newline='') as csvfile:
                            log_writer = csv.writer(csvfile)
                            log_writer.writerow([time_str, current_account_nickname, '未知账号'])
                    if self.notifier:
                        self.notifier.notify(f"[{self.id}]检测到未知昵称：{current_account_nickname}，已跳过记录。", is_error=True)
                    return

                # 更新下载计数
                with XKW.download_counts_lock:
                    account_counts = XKW.download_counts.get(current_account_nickname, {})
                    daily_count_info = account_counts.get('daily', {})
                    weekly_count_info = account_counts.get('weekly', {})

                    if daily_count_info.get('date') != date_str:
                        daily_count_info = {'date': date_str, 'count': 0}

                    if weekly_count_info.get('week') != week_number:
                        weekly_count_info = {'week': week_number, 'count': 0}

                    daily_count_info['count'] += 1
                    weekly_count_info['count'] += 1

                    account_counts['daily'] = daily_count_info
                    account_counts['weekly'] = weekly_count_info
                    XKW.download_counts[current_account_nickname] = account_counts

                    with open(XKW.download_counts_file, 'w', encoding='utf-8') as f:
                        json.dump(XKW.download_counts, f, ensure_ascii=False, indent=4)

                    with open(XKW.download_log_file, 'a', encoding='utf-8', newline='') as csvfile:
                        log_writer = csv.writer(csvfile)
                        log_writer.writerow([
                            time_str,
                            current_account_nickname,
                            f"[{self.id}]每日计数: {daily_count_info['count']}, 每周计数: {weekly_count_info['count']}"
                        ])

                    logging.info(
                        f"[{self.id}][{tab_id}][soft_id:{soft_id}] 账号 {current_account_nickname} 的下载计数已更新：每日 {daily_count_info['count']}, 每周 {weekly_count_info['count']}")

                    # 检查是否达到下载上限
                    if self.is_account_reached_limit(current_account_nickname):
                        limit_type = "每日" if daily_count_info['count'] >= 51 else "每周"
                        limit_value = 51 if daily_count_info['count'] >= 51 else 350

                        logging.info(f"[{self.id}]账号 {current_account_nickname} {limit_type}下载数量已达{limit_value}，切换账号。")
                        if self.notifier:
                            self.notifier.notify(
                                f"[{self.id}]账号 {current_account_nickname} {limit_type}下载数量已达{limit_value}，切换账号。")
                        self.manager.disable_xkw_instance(self)
                        self.switch_browser_and_retry(tab, url, soft_id)
        except Exception as e:
            logging.error(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 记录账号下载次数时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 记录账号下载次数时出错: {e}", is_error=True)

    def get_current_account_usage(self) -> str:
        """
        获取当前账号的使用情况，包括下载计数等信息。

        返回:
        - 包含账号使用情况的字符串。
        """
        try:
            nickname = self.get_nickname_current_account()

            if not nickname:
                return "无法获取当前账号的昵称，可能未登录或提取失败。"

            username = self.get_username_by_nickname(nickname)

            # 获取当前日期和周数
            today = datetime.today()
            date_str = today.strftime('%Y-%m-%d')
            week_number = today.strftime('%W')  # 年份和周数组合，周从星期一开始

            with XKW.download_counts_lock:
                account_counts = XKW.download_counts.get(nickname, {})
                daily_count_info = account_counts.get('daily', {})
                weekly_count_info = account_counts.get('weekly', {})

                # 检查并重置每日计数
                if daily_count_info.get('date') != date_str:
                    daily_count = 0
                else:
                    daily_count = daily_count_info.get('count', 0)

                # 检查并重置每周计数
                if weekly_count_info.get('week') != week_number:
                    weekly_count = 0
                else:
                    weekly_count = weekly_count_info.get('count', 0)

            usage_info = (
                f"[{self.id}]当前账号信息：\n"
                f"[{self.id}]昵称：{nickname}\n"
                f"[{self.id}]用户名：{username}\n"
                f"[{self.id}]今日下载次数：{daily_count}/51\n"
                f"[{self.id}]本周下载次数：{weekly_count}/350\n"
            )
            logging.info(f"[{self.id}]获取当前账号使用情况：\n{usage_info}")
            return usage_info

        except Exception as e:
            logging.error(f"[{self.id}]获取当前账号使用情况时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"[{self.id}]获取当前账号使用情况时出错: {e}", is_error=True)
            return "获取当前账号使用情况时发生错误。"

    def get_nickname_current_account(self) -> str:
        """
        使用 get_nickname 方法获取当前账号的昵称。

        返回:
        - 当前账号的昵称字符串，或空字符串表示获取失败。
        """
        try:
            # 获取一个活跃的标签页
            tab = self.tabs.get(timeout=10)  # 设置适当的超时时间
            tab_id = self.tab_ids.get(tab, "unknown_tab")  # 获取 tab_id
            tab.get('https://www.zxxk.com')
            nickname = self.get_nickname(tab)
            # 将标签页放回队列
            self.reset_tab(tab, tab_id)
            self.tabs.put(tab)
            return nickname
        except queue.Empty:
            logging.error("无法获取标签页以提取昵称。")
            if self.notifier:
                self.notifier.notify("无法获取标签页以提取昵称。", is_error=True)
            return ""
        except Exception as e:
            logging.error(f"[{self.id}]获取当前账号昵称时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"[{self.id}]获取当前账号昵称时出错: {e}", is_error=True)
            return ""

    def get_username_by_nickname(self, nickname: str) -> str:
        """
        根据昵称获取用户名。

        参数:
        - nickname: 账号的昵称。

        返回:
        - 对应的用户名，或空字符串如果未找到。
        """
        try:
            for account in self.accounts:
                if account.get('nickname') == nickname:
                    return account.get('username', '')
            logging.warning(f"[{self.id}]未找到昵称为 {nickname} 的账号。")
            return ""
        except Exception as e:
            logging.error(f"[{self.id}]根据昵称获取用户名时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"[{self.id}]根据昵称获取用户名时出错: {e}", is_error=True)
            return ""

    def handle_login_status(self, tab):
        try:
            with self.handle_login_lock:
                current_nickname = self.get_nickname(tab)
                logging.info(f"[{self.id}]当前账号昵称: {current_nickname}")

                if current_nickname:
                    # 检查当前账号是否达到下载上限
                    if self.is_account_reached_limit(current_nickname):
                        logging.info(f"[{self.id}]账号 {current_nickname} 已达到下载上限，禁用该实例。")
                        if self.notifier:
                            self.notifier.notify(f"[{self.id}]账号 {current_nickname} 已达到下载上限，实例已被禁用。",
                                                 is_error=True)
                        self.manager.disable_xkw_instance(self)
                        return

                # 尝试重新登录当前账号
                if not self.login(tab):
                    logging.error(f"[{self.id}]账号 {current_nickname} 登录失败，禁用该实例。")
                    if self.notifier:
                        self.notifier.notify(f"[{self.id}]账号 {current_nickname} 登录失败，实例已被禁用。",
                                             is_error=True)
                    self.manager.disable_xkw_instance(self)
        except Exception as e:
            logging.error(f'处理登录状态时发生错误：{e}', exc_info=True)
            if self.manager:
                self.manager.disable_xkw_instance(self)
            if self.notifier:
                error_trace = traceback.format_exc()
                self.notifier.notify(
                    f"[{self.id}]处理登录状态时发生错误：{e}\n详细信息：{error_trace}",
                    is_error=True
                )

    def is_account_reached_limit(self, nickname: str) -> bool:
        """
        检查指定昵称的账号是否达到每日或每周的下载上限。

        参数:
        - nickname: 账号的昵称。

        返回:
        - True: 达到上限。
        - False: 未达到上限。
        """
        try:
            today = datetime.today()
            date_str = today.strftime('%Y-%m-%d')
            week_number = today.strftime('%Y-%W')  # 年份和周数组合，周从星期一开始

            with XKW.download_counts_lock:
                account_counts = XKW.download_counts.get(nickname, {})
                daily_count_info = account_counts.get('daily', {})
                weekly_count_info = account_counts.get('weekly', {})

                # 获取每日下载次数
                if daily_count_info.get('date') == date_str:
                    daily_count = daily_count_info.get('count', 0)
                else:
                    daily_count = 0

                # 获取每周下载次数
                if weekly_count_info.get('week') == week_number:
                    weekly_count = weekly_count_info.get('count', 0)
                else:
                    weekly_count = 0

            # 检查是否达到每日或每周上限
            if daily_count >= 51 or weekly_count >= 350:
                if daily_count >= 51:
                    self.set_daily_limit_reached(True)
                if weekly_count >= 350:
                    self.set_weekly_limit_reached(True)
                return True
            else:
                # 如果未达到上限，确保属性为 False
                if daily_count < 51:
                    self.set_daily_limit_reached(False)
                if weekly_count < 350:
                    self.set_weekly_limit_reached(False)
                return False
        except Exception as e:
            logging.error(f"[{self.id}]检查账号下载上限时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"[{self.id}]检查账号下载上限时出错: {e}", is_error=True)
            return False

    def switch_browser_and_retry(self, tab, url, soft_id):
        """
        切换到另一个浏览器实例重新尝试下载。
        如果没有可用的实例，直接将任务添加到 pending_tasks 队列中。

        参数:
        - url: 需要重新下载的 URL。

        返回:
        - True: 如果成功切换并重新添加任务。
        - False: 如果没有可用的实例，任务已被添加到 pending_tasks。
        """
        tab_id = self.tab_ids.get(tab, "unknown_tab")
        try:
            available_xkw_instances = self.manager.get_available_xkw_instances(self)
            if available_xkw_instances:
                xkw_instance = random.choice(available_xkw_instances)
                logging.info(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 准备切换浏览器实例进行重试: {url}")
                if self.notifier:
                    self.notifier.notify(f"[{self.id}]切换到新的 XKW 实例 {xkw_instance.id} 进行下载。")

                # 将任务分配给选中的实例
                xkw_instance.add_task(url)
                logging.info(f"[{self.id}]已将 URL 添加到 XKW 实例 {xkw_instance.id} 的任务队列: {url}")
                return True
            else:
                logging.warning("没有可用的 XKW 实例进行重试。将任务添加到 pending_tasks 队列。")
                if self.notifier:
                    self.notifier.notify(f"[{self.id}]没有可用的实例可切换，任务已添加到 pending_tasks 队列：{url}", is_error=True)
                self.manager.enqueue_pending_task(url)
                return False
        except Exception as e:
            logging.error(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 切换浏览器实例时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 切换浏览器实例时出错: {e}", is_error=True)
            return False

    def download(self, url, tab):
        """
        执行下载任务，增加了重试机制。

        参数:
        - url: 要下载的文件的 URL。
        - tab: 当前浏览器标签页。
        """
        max_retries = 3
        attempt = 0
        tab_id = self.tab_ids.get(tab, "unknown_tab")
        soft_id = None  # 新增：提前定义soft_id变量，用于在下方步骤中使用
        while attempt < max_retries:
            try:
                logging.info(f"[{self.id}][{tab_id}] 准备下载 URL: {url} (尝试 {attempt + 1}/{max_retries})")
                pre_download_delay = random.uniform(0.5, 1)
                logging.debug(f"[{self.id}][{tab_id}] 下载前随机延迟 {pre_download_delay:.1f} 秒")
                time.sleep(pre_download_delay)

                tab.get(url)

                tab.wait.load_start(timeout=10)
                tab.wait.doc_loaded(timeout=30)

                extracted_soft_id, title = self.extract_id_and_title(tab, url)
                if extracted_soft_id and title:
                    soft_id = extracted_soft_id
                    logging.info(f"[{self.id}][{tab_id}] 提取到 soft_id: {soft_id}, title: {title}")
                else:
                    # 无法提取soft_id和title，跳过
                    logging.error(f"[{self.id}][{tab_id}] 无法提取 soft_id 或 title，跳过 URL: {url}")
                    self.reset_tab(tab, tab_id)
                    return

                download_button = tab("#btnSoftDownload")
                if not download_button:
                    logging.error(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 无法找到下载按钮，跳过URL: {url}")
                    if self.notifier:
                        self.notifier.notify(f"[{self.id}][{tab_id}] 无法找到下载按钮，跳过 URL: {url}", is_error=True)
                    self.reset_tab(tab, tab_id)
                    return

                logging.info(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 准备点击下载按钮，URL: {url}")
                click_delay = random.uniform(0.5, 1.5)
                logging.debug(f"[{self.id}][{tab_id}] 点击下载按钮前随机延迟 {click_delay:.1f} 秒")
                time.sleep(click_delay)

                success = self.listener(tab, download_button, url, title, soft_id)
                if success:
                    logging.info(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 下载成功: {url}")
                    break
                else:
                    attempt += 1
                    logging.warning(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 下载失败，准备重试: {url}")
                    self.reset_tab(tab, tab_id)
                    tab.get(url)
            except Exception as e:
                logging.error(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 下载过程中出错: {e}", exc_info=True)
                if self.notifier:
                    self.notifier.notify(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 下载过程中出错: {e}", is_error=True)
                self.reset_tab(tab, tab_id)
                tab.get(url)
                attempt += 1
        else:
            self.reset_tab(tab, tab_id)
            self.tabs.put(tab)
            logging.error(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 下载失败，已达到最大重试次数: {url}")
            if self.notifier:
                self.notifier.notify(f"[{self.id}][{tab_id}][soft_id:{soft_id}] 下载失败，已达到最大重试次数: {url}", is_error=True)

    def run(self):
        """
        管理下载任务的主循环，使用线程池执行下载任务。
        """
        with ThreadPoolExecutor(max_workers=self.thread) as executor:
            futures = []
            while self.work:
                try:
                    url = self.task.get(timeout=5)  # 获取新任务
                    if url is None:
                        logging.info("接收到退出信号，停止下载管理。")
                        break

                    # 控制下载启动间隔，确保至少2秒
                    current_time = time.time()
                    elapsed = current_time - self.last_download_time
                    if elapsed < 2:
                        wait_time = 2 - elapsed
                        logging.debug(f"[{self.id}]等待 {wait_time:.1f} 秒以确保下载间隔至少2秒。")
                        time.sleep(wait_time)
                    self.last_download_time = time.time()

                    try:
                        tab = self.tabs.get(timeout=600)  # 获取一个标签页，设置超时避免阻塞
                        logging.info(f"[{self.id}]获取到一个标签页用于下载: {tab}")
                    except queue.Empty:
                        logging.error("获取标签页超时，无法执行下载任务。")
                        if self.notifier:
                            self.notifier.notify("获取标签页超时，无法执行下载任务。", is_error=True)
                        continue

                    # 提交下载任务到线程池
                    future = executor.submit(self.download, url, tab)
                    futures.append(future)
                    logging.info(f"[{self.id}]已提交下载任务到线程池: {url}")

                    # 添加随机间隔，模拟任务分发的不规则性
                    task_dispatch_delay = random.uniform(0.1, 0.5)
                    logging.debug(f"[{self.id}]任务分发后随机延迟 {task_dispatch_delay:.1f} 秒")
                    time.sleep(task_dispatch_delay)
                except queue.Empty:
                    continue
                except Exception as e:
                    logging.error(f"[{self.id}]任务分发时出错: {e}", exc_info=True)
                    if self.notifier:
                        self.notifier.notify(f"[{self.id}]任务分发时出错: {e}", is_error=True)

            # 等待所有任务完成
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"[{self.id}]下载任务中出现未捕获的异常: {e}", exc_info=True)
                    if self.notifier:
                        self.notifier.notify(f"[{self.id}]下载任务中出现未捕获的异常: {e}", is_error=True)

    def add_task(self, url: str):
        """
        向任务队列添加一个下载任务。

        参数:
        - url: 要下载的文件的 URL。
        """
        self.task.put(url)
        logging.info(f"[{self.id}]任务已添加到队列: {url}")

    def start(self):
        """启动或重新启动 XKW 实例的运行线程。"""
        if not self.work:
            self.work = True
            self.manager_thread = threading.Thread(target=self.run, daemon=True)
            self.manager_thread.start()
            logging.info(f"[{self.id}]XKW manager 线程已重新启动，实例 ID: {self.id}")

    def stop(self):
        """
        停止 XKW 实例，关闭浏览器和线程。
        """
        try:
            logging.info("停止 XKW 实例。")
            self.work = False
            self.task.put(None)  # 发送退出信号
            self.page.close()
            logging.info("XKW 实例已停止。")
            self.save_state()  # 保存状态
        except Exception as e:
            logging.error(f"[{self.id}]停止过程中出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"[{self.id}]停止过程中出错: {e}", is_error=True)


class AutoDownloadManager:
    """
    自动下载管理器，管理多个 XKW 实例，协调下载任务的分配和实例的状态。
    """

    def __init__(self, uploader=None, notifier_config=None):
        """
        初始化 AutoDownloadManager。

        参数:
        - uploader: 上传器实例。
        - notifier_config: 通知器的配置。
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
        # 创建状态保存目录
        os.makedirs(STATE_DIR, exist_ok=True)
        # 创建两个 ChromiumOptions，指定不同的端口和用户数据路径
        co1 = ChromiumOptions().set_local_port(9222).set_user_data_path('data1')
        co2 = ChromiumOptions().set_local_port(9333).set_user_data_path('data2')
        co3 = ChromiumOptions().set_local_port(9444).set_user_data_path('data3')
        co4 = ChromiumOptions().set_local_port(9455).set_user_data_path('data4')
        co5 = ChromiumOptions().set_local_port(9466).set_user_data_path('data5')
        co6 = ChromiumOptions().set_local_port(9477).set_user_data_path('data6')
        co7 = ChromiumOptions().set_local_port(9488).set_user_data_path('data7')
        co8 = ChromiumOptions().set_local_port(9499).set_user_data_path('data8')
        co9 = ChromiumOptions().set_local_port(9500).set_user_data_path('data9')
        co10 = ChromiumOptions().set_local_port(9511).set_user_data_path('data10')
        co11 = ChromiumOptions().set_local_port(9522).set_user_data_path('data11')
        co12 = ChromiumOptions().set_local_port(9533).set_user_data_path('data12')
        co13 = ChromiumOptions().set_local_port(9544).set_user_data_path('data13')
        co14 = ChromiumOptions().set_local_port(9555).set_user_data_path('data14')
        co15 = ChromiumOptions().set_local_port(9566).set_user_data_path('data15')
        co16 = ChromiumOptions().set_local_port(9577).set_user_data_path('data16')
        co17 = ChromiumOptions().set_local_port(9588).set_user_data_path('data17')

        # 启动两个 Chromium 浏览器实例
        browser1 = Chromium(co1)
        browser2 = Chromium(co2)
        browser3 = Chromium(co3)
        browser4 = Chromium(co4)
        browser5 = Chromium(co5)
        browser6 = Chromium(co6)
        browser7 = Chromium(co7)
        browser8 = Chromium(co8)
        browser9 = Chromium(co9)
        browser10 = Chromium(co10)
        browser11 = Chromium(co11)
        browser12 = Chromium(co12)
        browser13 = Chromium(co13)
        browser14 = Chromium(co14)
        browser15 = Chromium(co15)
        browser16 = Chromium(co16)
        browser17 = Chromium(co17)

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        download_dir = DOWNLOAD_DIR

        # 为每个实例提供不同的账号列表
        accounts_xkw1 = [{'username': '13143019361', 'password': '428199Li@', 'nickname': '全能01X'},]
        accounts_xkw2 = [{'username': '19061531853', 'password': '428199Li@', 'nickname': '全能02'},]
        accounts_xkw3 = [{'username': '19563630322', 'password': '428199Li@', 'nickname': '全能03X'},]
        accounts_xkw4 = [{'username': '13343297668', 'password': '428199Li@', 'nickname': '全能04X'},]
        accounts_xkw5 = [{'username': '15324485548', 'password': '428199Li@', 'nickname': '全能05'},]
        accounts_xkw6 = [{'username': '19536946597', 'password': '428199Li@', 'nickname': '全能06X'},]
        accounts_xkw7 = [{'username': '13820043716', 'password': '428199Li@', 'nickname': '全能08X'},]
        accounts_xkw8 = [{'username': '15512733826', 'password': '428199Li@', 'nickname': '全能09X'},]
        accounts_xkw9 = [{'username': '13920946017', 'password': '428199Li@', 'nickname': '全能11X'},]
        accounts_xkw10 = [{'username': '19358191853', 'password': '428199Li@', 'nickname': '全能12X'},]
        accounts_xkw11 = [{'username': '18589186420', 'password': '428199Li@', 'nickname': '全能13x'},]
        accounts_xkw12 = [{'username': '19316031853', 'password': '428199Li@', 'nickname': '全能14X'},]
        accounts_xkw13 = [{'username': '19568101843', 'password': '428199Li@', 'nickname': '全能15X'},]
        accounts_xkw14 = [{'username': '13370328920', 'password': '428199Li@', 'nickname': '全能16'},]
        accounts_xkw15 = [{'username': '18330529099', 'password': '428199Li@', 'nickname': '全能17'},]
        accounts_xkw16 = [{'username': '18730596893', 'password': '428199Li@', 'nickname': '全能18'},]
        accounts_xkw17 = [{'username': '17332853851', 'password': '428199Li@', 'nickname': '全能20'},]

        # 创建两个 XKW 实例，分配唯一 ID，并传入各自的账号列表
        xkw1 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   co=co1, manager=self, id='xkw1', accounts=accounts_xkw1)
        xkw2 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   co=co2, manager=self, id='xkw2', accounts=accounts_xkw2)
        xkw3 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   co=co3, manager=self, id='xkw3', accounts=accounts_xkw3)
        xkw4 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   co=co4, manager=self, id='xkw4', accounts=accounts_xkw4)
        xkw5 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   co=co5, manager=self, id='xkw5', accounts=accounts_xkw5)
        xkw6 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   co=co6, manager=self, id='xkw6', accounts=accounts_xkw6)
        xkw7 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   co=co7, manager=self, id='xkw7', accounts=accounts_xkw7)
        xkw8 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   co=co8, manager=self, id='xkw8', accounts=accounts_xkw8)
        xkw9 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   co=co9, manager=self, id='xkw9', accounts=accounts_xkw9)
        xkw10 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                     co=co10, manager=self, id='xkw10', accounts=accounts_xkw10)
        xkw11 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                     co=co11, manager=self, id='xkw11', accounts=accounts_xkw11)
        xkw12 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                     co=co12, manager=self, id='xkw12', accounts=accounts_xkw12)
        xkw13 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                     co=co13, manager=self, id='xkw13', accounts=accounts_xkw13)
        xkw14 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                     co=co14, manager=self, id='xkw14', accounts=accounts_xkw14)
        xkw15 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                     co=co15, manager=self, id='xkw15', accounts=accounts_xkw15)
        xkw16 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                     co=co16, manager=self, id='xkw16', accounts=accounts_xkw16)
        xkw17 = XKW(thread=3, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                     co=co17, manager=self, id='xkw17', accounts=accounts_xkw17)

        self.xkw_instances = [xkw1, xkw2, xkw3, xkw4, xkw5, xkw6, xkw7, xkw8, xkw9, xkw10, xkw11, xkw12, xkw13, xkw14, xkw15, xkw16, xkw17]  # 所有的 XKW 实例
        self.active_xkw_instances = self.xkw_instances.copy()  # 活跃的 XKW 实例
        self.next_xkw_index = 0  # 用于轮询选择 XKW 实例
        self.xkw_lock = threading.RLock()
        self.status_check_thread = threading.Thread(target=self.periodic_status_check, daemon=True)
        self.status_check_thread.start()
        logging.info("定期实例状态检查线程已启动。")
        self.pending_tasks = queue.Queue()  # 用于保存挂起的下载任务
        self.paused = False  # 标志是否暂停任务分配
        self.load_instances_state()
    state_file = 'xkw_states.json'

    def save_instances_state(self):
        """
        保存所有实例的状态到 JSON 文件。
        """
        with self.xkw_lock:
            for xkw in self.xkw_instances:
                xkw.save_state()

    def load_instances_state(self):
        """
        从 JSON 文件加载所有实例的状态，并更新 active_xkw_instances 列表。
        """
        with self.xkw_lock:
            self.active_xkw_instances.clear()  # 清空当前的活跃实例列表
            for xkw in self.xkw_instances:
                if xkw.is_active:
                    self.active_xkw_instances.append(xkw)
                    logging.info(f"实例 {xkw.id} 已添加到 active_xkw_instances。")
                else:
                    logging.info(f"实例 {xkw.id} 当前为非活跃状态。")

    def disable_xkw_instance(self, xkw_instance):
        """
        禁用指定的 XKW 实例。

        参数:
        - xkw_instance: 要禁用的 XKW 实例。
        """
        try:
            with self.xkw_lock:
                if xkw_instance in self.active_xkw_instances:
                    xkw_instance.is_active = False
                    self.active_xkw_instances.remove(xkw_instance)
                    logging.info(f"实例 {xkw_instance.id} 已从活跃列表中移除。")
                    if self.notifier:
                        self.notifier.notify(f"实例 {xkw_instance.id} 已被禁用。", is_error=True)
        except AttributeError as e:
            logging.error(f"禁用实例时发生 AttributeError: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"禁用实例时发生 AttributeError: {e}", is_error=True)
        except Exception as e:
            logging.error(f"禁用实例时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"禁用实例时出错: {e}", is_error=True)

    def disable_all_instances(self) -> str:
        """
        禁用所有的 XKW 实例。

        返回:
        - 操作结果的字符串描述。
        """
        with self.xkw_lock:
            disabled = []
            for xkw in self.active_xkw_instances[:]:  # 遍历活跃实例的副本
                xkw.is_active = False
                disabled.append(xkw.id)
            # 清空活跃实例列表
            self.active_xkw_instances.clear()
            if disabled:
                logging.info(f"实例 {', '.join(disabled)} 已全部禁用。")
                if self.notifier:
                    self.notifier.notify(f"实例 {', '.join(disabled)} 已全部禁用。")
                return f"实例 {', '.join(disabled)} 已全部禁用。"
            else:
                logging.info("所有实例已经是禁用状态。")
                return "所有实例已经是禁用状态。"

    def get_available_xkw_instances(self, current_instance):
        """
        获取可用于重试下载的 XKW 实例列表，排除当前实例。

        参数:
        - current_instance: 当前的 XKW 实例。

        返回:
        - 可用的 XKW 实例列表。
        """
        return [xkw for xkw in self.active_xkw_instances if xkw != current_instance]

    def enable_xkw_instance(self, id: str) -> str:
        """
        恢复指定的 XKW 实例。

        参数:
        - id: 要恢复的 XKW 实例的 ID。

        返回:
        - 操作结果的字符串描述。
        """
        with self.xkw_lock:
            for xkw in self.xkw_instances:
                if xkw.id == id:
                    if not xkw.is_active:
                        xkw.is_active = True
                        self.active_xkw_instances.append(xkw)
                        xkw.start()  # 重新启动实例的运行线程
                        logging.info(f"实例 {xkw.id} 已被恢复。")
                        if self.notifier:
                            self.notifier.notify(f"实例 {xkw.id} 已被恢复。")
                        return f"实例 {xkw.id} 已被恢复。"
                    else:
                        logging.info(f"实例 {xkw.id} 已经是活跃状态。")
                        return f"实例 {xkw.id} 已经是活跃状态。"
            logging.warning(f"未找到实例 ID: {id}。")
            return f"未找到实例 ID: {id}。"

    def check_instance_status(self, xkw):
        """
        检查单个实例的状态。
        """
        try:
            # 先检查是否需要管理员介入
            if xkw.admin_intervention_required:
                logging.info(f"实例 {xkw.id} 需要管理员介入，跳过进一步检查。")
                return

            try:
                tab = xkw.tabs.get_nowait()  # 获取一个可用的标签页
            except queue.Empty:
                logging.warning(f"实例 {xkw.id} 没有可用的标签页进行状态检查。")
                return

            if not xkw.is_logged_in(tab):
                logging.warning(f"实例 {xkw.id} 未登录，尝试重新登录。")
                if xkw.login(tab):
                    logging.info(f"实例 {xkw.id} 登录成功。")
                else:
                    logging.error(f"实例 {xkw.id} 登录失败，标记需要管理员介入。")
                    xkw.set_admin_intervention_required(True)
                    self.disable_xkw_instance(xkw)
                    xkw.tabs.put(tab)  # 将标签页放回队列
                    return

            nickname = xkw.get_nickname_current_account()
            if nickname and xkw.is_account_reached_limit(nickname):
                logging.info(f"实例 {xkw.id} 达到下载上限，禁用实例。")
                self.disable_xkw_instance(xkw)

            xkw.tabs.put(tab)  # 将标签页放回队列

        except Exception as e:
            logging.error(f"检查实例 {xkw.id} 状态时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"检查实例 {xkw.id} 状态时出错: {e}", is_error=True)

    def check_instances_status(self):
        """
        检查所有活跃实例的状态，首先查看是否需要管理员介入。
        如果不需要，检查登录状态和下载上限。
        """
        with self.xkw_lock:
            instances = self.active_xkw_instances.copy()

        with ThreadPoolExecutor(max_workers=min(10, len(instances))) as executor:
            futures = {executor.submit(self.check_instance_status, xkw): xkw for xkw in instances}
            for future in as_completed(futures):
                xkw = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"检查实例 {xkw.id} 状态时发生未捕获的异常: {e}", exc_info=True)
                    if self.notifier:
                        self.notifier.notify(f"检查实例 {xkw.id} 状态时发生未捕获的异常: {e}", is_error=True)

    def periodic_status_check(self, interval=21600):
        """
        定期检查所有实例的状态。

        参数:
        - interval: 检查间隔（秒）。
        """
        while True:
            self.check_instances_status()
            time.sleep(interval)

    def query_all_instances_status(self) -> str:
        """
        查询所有实例的各个属性（活跃，登录，上限，管理员介入）。
        """
        try:
            status_infos = []
            with self.xkw_lock:
                for xkw in self.xkw_instances:
                    status_info = (
                        f"实例 ID: {xkw.id}\n"
                        f"  - 活跃状态: {'是' if xkw.is_active else '否'}\n"
                        f"  - 登录状态: {'已登录' if xkw.login_status else '未登录'}\n"
                        f"  - 每日下载上限已达: {'是' if xkw.daily_limit_reached else '否'}\n"
                        f"  - 每周下载上限已达: {'是' if xkw.weekly_limit_reached else '否'}\n"
                        f"  - 需要管理员介入: {'是' if xkw.admin_intervention_required else '否'}\n"
                    )
                    status_infos.append(status_info)
            full_status = "\n".join(status_infos)
            logging.info("查询所有实例的状态。")
            return full_status
        except Exception as e:
            logging.error(f"查询所有实例状态时出错: {e}", exc_info=True)
            return f"查询所有实例状态时出错: {e}"

    def set_instance_admin_intervention(self, instance_id: str, status: bool) -> str:
        """
        改变指定实例的 admin_intervention_required 属性。

        参数:
        - instance_id: 要修改的实例ID。
        - status: 需要设置的状态，True 或 False。

        返回:
        - 操作结果的字符串描述。
        """
        try:
            for xkw in self.xkw_instances:
                if xkw.id == instance_id:
                    xkw.set_admin_intervention_required(status)
                    if status:
                        self.disable_xkw_instance(xkw)
                        logging.info(f"实例 {instance_id} 已设置为需要管理员介入，并已被禁用。")
                        return f"实例 {instance_id} 已设置为需要管理员介入，并已被禁用。"
                    else:
                        logging.info(f"实例 {instance_id} 的需要管理员介入状态已取消。")
                        self.restore_instance(xkw)
                        return f"实例 {instance_id} 的需要管理员介入状态已取消。"
            logging.warning(f"未找到实例 ID: {instance_id}。")
            return f"未找到实例 ID: {instance_id}。"
        except Exception as e:
            logging.error(f"设置实例 '{instance_id}' 的管理员介入状态时出错: {e}", exc_info=True)
            return f"设置实例 '{instance_id}' 的管理员介入状态时出错: {e}"

    def add_task(self, url: str, current_instance=None):
        try:
            logging.info(f"准备添加 URL 到下载任务队列: {url}")
            with self.xkw_lock:
                available_instances = self.get_available_xkw_instances(current_instance)
                if not available_instances:
                    self.pending_tasks.put(url)
                    logging.info(f"没有活跃实例，任务已添加到 pending_tasks 队列：{url}")
                    if self.notifier:
                        self.notifier.notify(f"没有活跃实例，任务已添加到 pending_tasks 队列：{url}", is_error=True)
                    return

                selected_instance = random.choice(available_instances)
                selected_instance.add_task(url)
                logging.info(f"已将 URL 添加到 XKW 实例 {selected_instance.id} 的任务队列: {url}")

                # 添加随机延迟，模拟任务分发的不规则性
                delay_seconds = random.uniform(1, 2)
                logging.debug(f"分配任务后暂停 {delay_seconds:.1f} 秒")
                time.sleep(delay_seconds)
        except Exception as e:
            logging.error(f"添加 URL 时发生错误: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"添加 URL 时发生错误: {e}", is_error=True)

    def enqueue_pending_task(self, url: str):
        """
        将任务添加到 pending_tasks 队列，并暂停任务分配。
        """
        with self.xkw_lock:
            self.pending_tasks.put(url)
            self.paused = True
            logging.info(f"任务已添加到 pending_tasks 队列，并暂停任务分配。URL: {url}")
            if self.notifier:
                self.notifier.notify(f"任务已添加到 pending_tasks 队列，并暂停任务分配。URL: {url}", is_error=True)

    def pause_task_distribution(self):
        """
        暂停任务分配。
        """
        with self.xkw_lock:
            self.paused = True
            logging.info("任务分配已暂停。")
            if self.notifier:
                self.notifier.notify("任务分配已暂停，因为所有账号均达到下载次数限制。", is_error=True)

    def redistribute_pending_tasks(self):
        """
        重新分配 pending_tasks 队列中的任务到活跃的 XKW 实例中。
        """
        # 先恢复 paused 状态，以便 add_task 能够正常分配任务
        with self.xkw_lock:
            self.paused = False

            while not self.pending_tasks.empty():
                url = self.pending_tasks.get()
                self.add_task(url)  # 通过 AutoDownloadManager 的 add_task 进行任务分配

        logging.info("已重新分配所有 pending_tasks，恢复任务分配。")
        if self.notifier:
            self.notifier.notify("已重新分配所有 pending_tasks，恢复任务分配。")

    def restore_instance(self, id: str):
        """
        恢复指定的实例。

        参数:
        - id: 要恢复的实例的 ID。

        返回:
        - 操作结果的字符串描述。
        """
        try:
            for xkw in self.xkw_instances:
                if xkw.id == id:
                    if xkw.admin_intervention_required:
                        xkw.set_admin_intervention_required(False)
                        xkw.set_instance_status('active')  # 使用现有的方法设置状态
                        self.active_xkw_instances.append(xkw)
                        xkw.start()  # 重新启动实例的运行线程
                        logging.info(f"实例 {id} 已被恢复。")
                        if self.notifier:
                            self.notifier.notify(f"实例 {id} 已被恢复。")
                        return f"实例 {id} 已被恢复。"
                    else:
                        logging.info(f"实例 {id} 不需要恢复。")
                        return f"实例 {id} 不需要恢复。"
            logging.warning(f"未找到实例 ID: {id}。")
            return f"未找到实例 ID: {id}。"
        except Exception as e:
            logging.error(f"恢复实例 '{id}' 时出错: {e}", exc_info=True)
            return f"恢复实例 '{id}' 时出错: {e}"

    def get_current_account_usage(self) -> str:
        """
        获取所有活跃的 XKW 实例的账号使用情况。

        返回:
        - 包含所有活跃实例账号使用情况的字符串。
        """
        try:
            usage_infos = []
            with self.xkw_lock:
                for xkw_instance in self.active_xkw_instances:
                    usage_info = xkw_instance.get_current_account_usage()
                    usage_infos.append(f"实例 {xkw_instance.id}:\n{usage_info}")

            if usage_infos:
                full_usage_info = "\n\n".join(usage_infos)
                logging.info(f"获取当前所有活跃实例的账号使用情况：\n{full_usage_info}")
                return full_usage_info
            else:
                logging.info("当前没有活跃的实例，无法获取账号使用情况。")
                return "当前没有活跃的实例，无法获取账号使用情况。"
        except Exception as e:
            logging.error(f"获取当前账号使用情况时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"获取当前账号使用情况时出错: {e}", is_error=True)
            return "获取当前账号使用情况时发生错误。"

    def stop(self):
        """
        停止 AutoDownloadManager 和其内部的所有 XKW 实例。
        """
        try:
            logging.info("停止 AutoDownloadManager 和所有 XKW 实例。")
            for xkw in self.xkw_instances:
                xkw.stop()
            # 保存所有实例状态
            self.save_instances_state()
        except Exception as e:
            logging.error(f"停止过程中出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"停止过程中出错: {e}", is_error=True)
