import logging
import os
import queue
import random
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple

import DrissionPage
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
        # self.co.headless()  # 不打开浏览器窗口，需要先登录然后再开启无浏览器模式
        self.co.no_imgs()  # 不加载图片
        self.co.set_download_path(download_dir or DOWNLOAD_DIR)  # 设置下载路径
        # self.co.set_argument('--no-sandbox')  # 无沙盒模式
        self.page = ChromiumPage(self.co)  # 创建 ChromiumPage 实例
        self.last_download_time = 0  # 记录上一次下载任务启动的时间
        self.download_lock = threading.Lock()  # 用于同步下载任务的启动时间
        self.manager = manager  # 保存 AutoDownloadManager 实例
        self.is_active = True  # 标记实例是否可用
        self.lock = threading.Lock()  # 线程锁
        self.failed_tasks = []  # 添加用于记录失败任务的列表

        # 添加账号列表和当前账号索引
        self.accounts = accounts if accounts else []
        self.current_account_index = 0  # 当前账号索引
        self.account_failures = [0] * len(self.accounts)  # 每个账号的失败计数器
        self.max_account_failures = 3  # 每个账号允许的最大连续失败次数

        logging.info(f"ChromiumPage initialized with address: {self.page.address}")
        self.dls_url = "https://www.zxxk.com/soft/softdownload?softid={xid}"
        self.make_tabs()  # 初始化标签页
        if self.work:
            self.manager_thread = threading.Thread(target=self.run, daemon=True)
            self.manager_thread.start()
            logging.info("XKW manager 线程已启动。")

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
                logging.debug("关闭了一个浏览器标签页。")
            except Exception as e:
                logging.error(f"关闭标签页时出错: {e}", exc_info=True)

    def make_tabs(self):
        """
        创建浏览器标签页，以供下载使用。
        """
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
        重置标签页，将其导航到空白页以清除状态。

        参数:
        - tab: 需要重置的标签页。
        """
        try:
            logging.info("等待0.1秒后重置标签页到空白页。")
            time.sleep(0.1)
            tab.get('about:blank')
            logging.info("标签页已重置为 about:blank。")
        except Exception as e:
            logging.error(f"导航标签页到空白页时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"导航标签页到空白页时出错: {e}", is_error=True)

    def match_downloaded_file(self, title):
        """
        匹配下载的文件，基于给定的标题在下载目录中寻找匹配的文件。

        参数:
        - title: 要匹配的文件标题。

        返回:
        - 匹配到的文件路径，若未找到则返回 None。
        """
        logging.debug(f"开始匹配下载的文件，标题: {title}")

        try:
            if not title:
                logging.error("标题为空，无法匹配下载文件")
                return None

            download_dir = self.co.download_path
            logging.debug(f"下载目录: {download_dir}")

            max_wait_time = 3600  # 最大等待时间（秒），即一个小时
            initial_wait = 60  # 初始等待时间（秒）
            initial_interval = 0.5  # 前60秒的重试间隔（秒）
            subsequent_interval = 5  # 后续的重试间隔（秒）
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
                            logging.info(f"匹配到下载的文件: {file_path}")
                            return file_path
                        else:
                            logging.debug(f"文件 {file_path} 不存在，等待中...")

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

            # 检测页面是否包含“独家”和“教辅”，如果包含则跳过
            ele_dujia = tab.ele('tag:em@text()=独家')
            ele_jiaofu = tab.ele('tag:em@text()=教辅')
            if ele_dujia and ele_jiaofu:
                logging.info(f"内容包含‘独家’和‘教辅’，跳过该任务。URL: {url}")
                return None, None  # 信号跳过

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

    def increment_failure_count(self):
        """
        增加当前账号的失败计数，如果达到上限，切换账号。
        如果所有账号都无法使用，才禁用实例。
        """
        with self.lock:
            self.account_failures[self.current_account_index] += 1
            current_failures = self.account_failures[self.current_account_index]
            logging.warning(f"账号 {self.accounts[self.current_account_index]['username']} 的连续失败次数增加到 {current_failures}。")

            if current_failures >= self.max_account_failures:
                logging.warning(f"账号 {self.accounts[self.current_account_index]['username']} 失败次数过多，切换账号。")
                self.switch_account()
                # 尝试登录新账号
                try:
                    tab = self.tabs.get(timeout=10)
                    if not self.login(tab):
                        # 如果登录失败，检查所有账号是否都已尝试
                        if all(failures >= self.max_account_failures for failures in self.account_failures):
                            self.is_active = False
                            logging.error(f"实例 {self.id} 所有账号均不可用，已禁用实例。")
                            if self.manager:
                                self.manager.disable_xkw_instance(self)
                            if self.notifier:
                                self.notifier.notify(f"实例 {self.id} 已被禁用，所有账号均无法使用。", is_error=True)
                    self.tabs.put(tab)
                except Exception as e:
                    logging.error(f"登录新账号时出错: {e}", exc_info=True)
                    if self.notifier:
                        self.notifier.notify(f"登录新账号时出错: {e}", is_error=True)

    def is_logged_in(self, tab):
        """
        检查当前是否已登录。

        参数:
        - tab: 浏览器标签页。

        返回:
        - True: 已登录。
        - False: 未登录。
        """
        try:
            tab.get('https://www.zxxk.com')
            time.sleep(10)  # 确保页面加载完成
            # 尝试找到“我的”元素或其他登录后特有的元素
            my_element = tab.ele('text:我的', timeout=5)
            if my_element:
                return True
            else:
                # 如果找不到“我的”元素，尝试查找登录按钮
                login_element = tab.ele('text:登录', timeout=5)
                return not bool(login_element)
        except Exception as e:
            logging.error(f"检查登录状态时出错: {e}", exc_info=True)
            return False

    def login(self, tab):
        """
        执行登录操作，使用当前账号索引的账号。

        参数:
        - tab: 浏览器标签页。

        返回:
        - True: 登录成功或已登录。
        - False: 登录失败。
        """
        try:
            if self.is_logged_in(tab):
                logging.info('当前账号已经登录，无需再次登录。')
                return True
        except Exception as e:
            logging.error(f"检查登录状态时出错: {e}", exc_info=True)
            # 如果检查登录状态时出错，继续尝试登录

        max_retries = 3
        retries = 0
        while retries < max_retries:
            account = self.accounts[self.current_account_index]
            username = account['username']
            password = account['password']
            try:
                # 访问登录页面
                tab.get('https://sso.zxxk.com/login')
                logging.info('访问登录页面成功。')
                time.sleep(random.uniform(1, 2))  # 增加随机延迟，等待页面完全加载

                # 点击“账户密码/验证码登录”按钮
                login_switch_button = tab.ele('tag:button@@class=another@@text():账户密码/验证码登录', timeout=10)
                if not login_switch_button:
                    logging.warning("没有找到“账户密码/验证码登录”按钮，可能已经登录。")
                    if self.is_logged_in(tab):
                        logging.info('登录状态已确认。')
                        return True
                    else:
                        logging.error("无法找到登录按钮且未检测到登录状态。")
                        retries += 1
                        continue
                login_switch_button.click()
                logging.info('点击“账户密码/验证码登录”按钮成功。')
                time.sleep(random.uniform(1, 2))  # 等待登录表单切换完成

                # 获取用户名和密码输入框
                username_field = tab.ele('#username', timeout=10)
                password_field = tab.ele('#password', timeout=10)

                # 清空输入框，确保没有残留内容
                username_field.clear()
                password_field.clear()
                logging.info('清空用户名和密码输入框成功。')
                time.sleep(random.uniform(1, 2))  # 等待输入框清空

                # 输入用户名
                username_field.input(username)
                logging.info('输入用户名成功。')
                time.sleep(random.uniform(1, 2))  # 增加延迟

                # 输入密码
                password_field.input(password)
                logging.info('输入密码成功。')
                time.sleep(random.uniform(1, 2))  # 增加延迟

                # 点击登录按钮
                login_button = tab.ele('#accountLoginBtn', timeout=10)
                login_button.click()
                logging.info('点击登录按钮成功。')
                time.sleep(random.uniform(1, 2))  # 等待登录结果

                # 检查是否登录成功
                if self.is_logged_in(tab):
                    logging.info(f'账号 {username} 登录成功。')
                    return True
                else:
                    logging.warning(f'账号 {username} 登录失败。')
                    retries += 1
            except DrissionPage.errors.ElementNotFoundError as e:
                logging.error(f'登录过程中出现错误：{e}')
                # 检查是否已登录
                if self.is_logged_in(tab):
                    logging.info('检测到已经登录，跳过登录步骤。')
                    return True
                retries += 1
            except Exception as e:
                logging.error(f'登录过程中出现错误：{e}', exc_info=True)
                retries += 1
        # 如果重试次数用尽，发送通知并返回 False
        error_message = f"所有登录尝试失败，账号 {username} 无法登录。请检查账号状态或登录流程。"
        logging.error(error_message)
        if self.notifier:
            self.notifier.notify(error_message, is_error=True)
        return False

    def logout(self, tab):
        """
        执行退出操作。

        参数:
        - tab: 浏览器标签页。
        """
        tab.get('https://www.zxxk.com')
        if not self.is_logged_in(tab):
            logging.info('当前未登录，无需执行退出操作。')
            return
        # 等待 '我的' 元素出现并将鼠标移动到其上方
        my_element = tab.ele('text:我的', timeout=10)
        my_element.hover()
        time.sleep(1)  # 等待下拉菜单显示

        # 等待 '退出' 元素出现并点击
        logout_element = tab.ele('text:退出', timeout=10)
        logout_element.click()
        logging.info('退出成功。')

    def switch_account(self):
        """
        切换到下一个可用账号。
        """
        with self.lock:
            tried_accounts = 0
            total_accounts = len(self.accounts)
            while tried_accounts < total_accounts:
                self.current_account_index = (self.current_account_index + 1) % total_accounts
                if self.account_failures[self.current_account_index] < self.max_account_failures:
                    break
                tried_accounts += 1
            account = self.accounts[self.current_account_index]
            logging.info(f'切换到账号：{account["username"]}')

    def listener(self, tab, download, url, title, soft_id):
        """
        监听下载过程，处理下载逻辑和异常情况。

        参数:
        - tab: 浏览器标签页。
        - download: 下载按钮元素。
        - url: 下载页面的 URL。
        - title: 文件标题。
        - soft_id: 文件的 soft_id。
        """
        success = False
        try:
            logging.info(f"开始下载 {url}")
            tab.listen.start(True, method="GET")  # 开始监听网络请求
            download.click(by_js=True)  # 点击下载按钮
            # 监听下载链接
            while True:
                for item in tab.listen.steps(timeout=10):
                    if item.url.startswith("https://files.zxxk.com/?mkey="):
                        # 捕获到下载链接
                        tab.listen.stop()
                        tab.stop_loading()
                        logging.info(f"下载链接获取成功: {item.url}")
                        # 重置当前账号的失败计数
                        with self.lock:
                            self.account_failures[self.current_account_index] = 0
                        logging.info(f"下载成功，开始处理上传任务: {url}")

                        # 匹配下载的文件
                        file_path = self.match_downloaded_file(title)
                        if not file_path:
                            logging.error(f"匹配下载的文件失败，跳过 URL: {url}")
                            if self.notifier:
                                self.notifier.notify(f"匹配下载的文件失败，跳过 URL: {url}", is_error=True)
                            # 记录失败的任务
                            self.record_failed_task(url, title, soft_id, reason="匹配下载的文件失败")
                            return

                        # 将文件路径和 soft_id 传递给上传模块
                        if self.uploader:
                            try:
                                # 等待文件可用
                                max_wait = 600
                                wait_interval = 1
                                elapsed = 0
                                while elapsed < max_wait:
                                    if self.is_file_available(file_path):
                                        break
                                    time.sleep(wait_interval)
                                    elapsed += wait_interval
                                    logging.info(f"等待文件可用: {file_path} ({elapsed}/{max_wait} 秒)")
                                else:
                                    logging.error(f"文件在 {max_wait} 秒内不可用: {file_path}")
                                    if self.notifier:
                                        self.notifier.notify(f"文件在 {max_wait} 秒内不可用，无法上传: {file_path}",
                                                             is_error=True)
                                    # 记录失败的任务
                                    self.record_failed_task(url, title, soft_id, reason="文件在规定时间内不可用")
                                    return

                                self.uploader.add_upload_task(file_path, soft_id)
                                logging.info(f"已将文件 {file_path} 和 soft_id {soft_id} 添加到上传任务队列。")
                            except Exception as e:
                                logging.error(f"添加上传任务时发生错误: {e}", exc_info=True)
                                if self.notifier:
                                    self.notifier.notify(f"添加上传任务时发生错误: {e}", is_error=True)
                                # 记录失败的任务
                                self.record_failed_task(url, title, soft_id, reason=f"添加上传任务时发生错误: {e}")
                        else:
                            logging.warning("Uploader 未设置，无法传递上传任务。")
                            # 记录失败的任务
                            self.record_failed_task(url, title, soft_id, reason="Uploader 未设置")
                        # 重置标签页
                        self.reset_tab(tab)
                        success = True
                        return  # 下载成功，退出方法
                    elif "20600001" in item.url:
                        logging.warning("请求过于频繁，暂停后重试。")
                        # 不进行重试，直接处理为失败
                        logging.warning(f"下载失败: {url}")
                        # 记录失败的任务
                        self.record_failed_task(url, title, soft_id, reason="请求过于频繁")
                        break
                else:
                    # 未捕获到下载链接，处理特殊情况
                    time.sleep(0.5)
                    iframe = tab.get_frame('#layui-layer-iframe100002')
                    if iframe:
                        a = iframe("t:a@@class=balance-payment-btn@@text()=确认")
                        if a:
                            a.click()
                            logging.info("点击确认按钮成功。")
                            continue
                    logging.warning(f"下载失败: {url}")
                    # 记录失败的任务
                    self.record_failed_task(url, title, soft_id, reason="未捕获到下载链接")
                    break  # 退出监听循环
            # 如果执行到这里，说明下载失败
        except Exception as e:
            logging.error(f"下载过程中出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"下载过程中出错: {e}", is_error=True)
            # 记录失败的任务
            self.record_failed_task(url, title, soft_id, reason=f"下载过程中出错: {e}")
        finally:
            if not success:
                # 增加当前账号的失败计数并尝试切换账号
                self.increment_failure_count()
                self.reset_tab(tab)
                self.tabs.put(tab)

    def record_failed_task(self, url, title, soft_id, reason=""):
        """
        记录下载失败的任务，以便后续处理。

        参数:
        - url: 下载页面的 URL。
        - title: 文件标题。
        - soft_id: 文件的 soft_id。
        - reason: 失败的原因（可选）。
        """
        failed_task = {
            "url": url,
            "title": title,
            "soft_id": soft_id,
            "reason": reason,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with self.lock:
            self.failed_tasks.append(failed_task)
        logging.info(f"记录失败的任务: {failed_task}")

    def is_file_available(self, file_path: str) -> bool:
        """检查文件是否可用（未被其他进程占用）。"""
        try:
            with open(file_path, 'rb'):
                return True
        except OSError:
            return False

    def handle_login_status(self, tab):
        """
        检查登录状态并根据情况进行登录或退出切换账号。

        参数:
        - tab: 浏览器标签页。
        """
        if not self.is_logged_in(tab):
            logging.info('未登录，开始登录。')
            if not self.login(tab):
                logging.error('登录失败，切换账号。')
                self.increment_failure_count()
        else:
            logging.info('已登录，执行退出并切换账号。')
            self.logout(tab)
            self.switch_account()
            if not self.login(tab):
                logging.error('切换账号后登录失败。')
                self.increment_failure_count()

    def download(self, url, tab):
        """
        执行下载任务。

        参数:
        - url: 要下载的文件的 URL。
        - tab: 浏览器标签页。
        """
        try:
            logging.info(f"准备下载 URL: {url}")
            # 增加随机延迟，模拟人类等待页面加载
            pre_download_delay = random.uniform(0.5, 1)
            logging.debug(f"下载前随机延迟 {pre_download_delay:.1f} 秒")
            time.sleep(pre_download_delay)

            tab.get(url)

            soft_id, title = self.extract_id_and_title(tab, url)
            if not soft_id or not title:
                if soft_id is None and title is None:
                    logging.info(f"任务被跳过: {url}")
                else:
                    logging.error(f"提取 soft_id 或标题失败，跳过 URL: {url}")
                self.reset_tab(tab)
                return

            download_button = tab("#btnSoftDownload")  # 获取下载按钮
            if not download_button:
                logging.error(f"无法找到下载按钮，跳过URL: {url}")
                if self.notifier:
                    self.notifier.notify(f"无法找到下载按钮，跳过 URL: {url}", is_error=True)
                self.reset_tab(tab)
                return
            logging.info(f"准备点击下载按钮，soft_id: {soft_id}")
            click_delay = random.uniform(0.5, 1.5)  # 点击前的随机延迟
            logging.debug(f"点击下载按钮前随机延迟 {click_delay:.1f} 秒")
            time.sleep(click_delay)
            self.listener(tab, download_button, url, title, soft_id)
        except Exception as e:
            logging.error(f"下载过程中出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"下载过程中出错: {e}", is_error=True)
            self.reset_tab(tab)

    def run(self):
        """
        管理下载任务的主循环，使用线程池执行下载任务。
        """
        with ThreadPoolExecutor(max_workers=self.thread) as executor:
            futures = set()
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
                        logging.debug(f"等待 {wait_time:.1f} 秒以确保下载间隔至少2秒。")
                        time.sleep(wait_time)
                    self.last_download_time = time.time()

                    # 提交下载任务到线程池
                    future = executor.submit(self._download_task, url)
                    futures.add(future)
                    logging.info(f"已提交下载任务到线程池: {url}")

                    # 清理已完成的 futures
                    done_futures = set(f for f in futures if f.done())
                    for done_future in done_futures:
                        futures.remove(done_future)
                        try:
                            done_future.result()
                        except Exception as e:
                            logging.error(f"下载任务中出现未捕获的异常: {e}", exc_info=True)
                            if self.notifier:
                                self.notifier.notify(f"下载任务中出现未捕获的异常: {e}", is_error=True)

                    # 增加随机间隔，模拟任务分发的不规则性
                    task_dispatch_delay = random.uniform(0.1, 0.5)
                    logging.debug(f"任务分发后随机延迟 {task_dispatch_delay:.1f} 秒")
                    time.sleep(task_dispatch_delay)
                except queue.Empty:
                    continue
                except Exception as e:
                    logging.error(f"任务分发时出错: {e}", exc_info=True)
                    if self.notifier:
                        self.notifier.notify(f"任务分发时出错: {e}", is_error=True)

            # 等待所有任务完成
            logging.info("等待所有下载任务完成...")
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"下载任务中出现未捕获的异常: {e}", exc_info=True)
                    if self.notifier:
                        self.notifier.notify(f"下载任务中出现未捕获的异常: {e}", is_error=True)

    def _download_task(self, url):
        """
        下载任务的辅助函数，用于在线程池中执行。

        参数:
        - url: 要下载的文件的 URL。
        """
        try:
            tab = self.tabs.get(timeout=30)  # 获取一个标签页，设置超时避免阻塞
            logging.info(f"获取到一个标签页用于下载: {tab}")

            self.download(url, tab)
            self.tabs.put(tab)
        except Exception as e:
            logging.error(f"运行下载过程中出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"运行下载过程中出错: {e}", is_error=True)
            if 'tab' in locals():
                self.tabs.put(tab)

    def add_task(self, url: str):
        """
        向任务队列添加一个下载任务。

        参数:
        - url: 要下载的文件的 URL。
        """
        self.task.put(url)
        logging.info(f"任务已添加到队列: {url}")

    def start(self):
        """启动或重新启动 XKW 实例的运行线程。"""
        if not self.work:
            self.work = True
            with self.lock:
                self.account_failures = [0] * len(self.accounts)  # 重置所有账号的失败计数
            self.manager_thread = threading.Thread(target=self.run, daemon=True)
            self.manager_thread.start()
            logging.info(f"XKW manager 线程已重新启动，实例 ID: {self.id}")

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
        except Exception as e:
            logging.error(f"停止过程中出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"停止过程中出错: {e}", is_error=True)


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

        # 创建两个 ChromiumOptions，指定不同的端口和用户数据路径
        co1 = ChromiumOptions().set_local_port(9222).set_user_data_path('data1')
        co2 = ChromiumOptions().set_local_port(9333).set_user_data_path('data2')

        # 启动两个 Chromium 浏览器实例
        browser1 = Chromium(co1)
        browser2 = Chromium(co2)

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        download_dir = DOWNLOAD_DIR

        # 为每个实例提供不同的账号列表
        accounts_xkw1 = [
            {'username': '19061531853', 'password': '428199Li@'},
            {'username': '19568101843', 'password': '428199Li@'},
            {'username': '13343297668', 'password': '428199Li@'},
            {'username': '15512733826', 'password': '428199Li@'},
            {'username': '19536946597', 'password': '428199Li@'},
            {'username': '19563630322', 'password': '428199Li@'}
        ]

        accounts_xkw2 = [
            {'username': '19358191853', 'password': '428199Li@'},
            {'username': '13143019361', 'password': '428199Li@'},
            {'username': '19316031853', 'password': '428199Li@'},
            {'username': '18589186420', 'password': '428199Li@'}
        ]

        # 创建两个 XKW 实例，分配唯一 ID，并传入各自的账号列表
        xkw1 = XKW(thread=5, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   co=co1, manager=self, id='xkw1', accounts=accounts_xkw1)
        xkw2 = XKW(thread=5, work=True, download_dir=download_dir, uploader=uploader, notifier=self.notifier,
                   co=co2, manager=self, id='xkw2', accounts=accounts_xkw2)

        self.xkw_instances = [xkw1, xkw2]  # 所有的 XKW 实例
        self.active_xkw_instances = self.xkw_instances.copy()  # 活跃的 XKW 实例
        self.next_xkw_index = 0  # 用于轮询选择 XKW 实例
        self.xkw_lock = threading.Lock()  # 线程锁

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

                    # 当实例被禁用时，尝试使用其他账号重新登录并下载
                    if not self.active_xkw_instances:
                        logging.warning("所有浏览器实例均不可用，向管理员发送报告。")
                        if self.notifier:
                            self.notifier.notify("所有浏览器实例均不可用，请检查账号状态或网络连接。", is_error=True)
        except AttributeError as e:
            logging.error(f"禁用实例时发生 AttributeError: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"禁用实例时发生 AttributeError: {e}", is_error=True)
        except Exception as e:
            logging.error(f"禁用实例时出错: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"禁用实例时出错: {e}", is_error=True)

    def get_available_xkw_instances(self, current_instance):
        """
        获取可用于重试下载的 XKW 实例列表，排除当前实例。

        参数:
        - current_instance: 当前的 XKW 实例。

        返回:
        - 可用的 XKW 实例列表。
        """
        return [xkw for xkw in self.active_xkw_instances if xkw != current_instance]

    def add_task(self, url: str):
        """
        添加单个 URL 到下载任务队列。

        参数:
        - url: 要下载的文件的 URL。
        """
        try:
            logging.info(f"准备添加 URL 到下载任务队列: {url}")
            with self.xkw_lock:
                if not self.active_xkw_instances:
                    logging.error("没有可用的 XKW 实例来处理任务。向管理员发送报告。")
                    if self.notifier:
                        self.notifier.notify("没有可用的 XKW 实例来处理下载任务。", is_error=True)
                    return
                # 从可用实例中选择一个
                xkw = self.active_xkw_instances[self.next_xkw_index % len(self.active_xkw_instances)]
                self.next_xkw_index += 1
            xkw.add_task(url)
            logging.info(f"已将 URL 添加到 XKW 实例 {xkw.id} 的任务队列: {url}")

            delay_seconds = random.uniform(1, 2)
            logging.info(f"分配任务后暂停 {delay_seconds:.1f} 秒")
            time.sleep(delay_seconds)
        except Exception as e:
            logging.error(f"添加 URL 时发生错误: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"添加 URL 时发生错误: {e}", is_error=True)

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

    def enable_all_instances(self) -> str:
        """
        恢复所有被禁用的 XKW 实例。

        返回:
        - 操作结果的字符串描述。
        """
        with self.xkw_lock:
            restored = []
            for xkw in self.xkw_instances:
                if not xkw.is_active:
                    xkw.is_active = True
                    xkw.start()  # 重新启动实例的运行线程
                    self.active_xkw_instances.append(xkw)
                    restored.append(xkw.id)
            if restored:
                logging.info(f"实例 {', '.join(restored)} 已全部恢复。")
                if self.notifier:
                    self.notifier.notify(f"实例 {', '.join(restored)} 已全部恢复。")
                return f"实例 {', '.join(restored)} 已全部恢复。"
            else:
                logging.info("所有实例已经是活跃状态。")
                return "所有实例已经是活跃状态。"

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
