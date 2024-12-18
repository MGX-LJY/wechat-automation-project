import logging
import os
import queue
import re
import threading
import time
from collections import deque
from typing import Optional, List, Any
from urllib.parse import urlparse, urlunparse
from lib.wxautox.wxauto import WeChat
from src.config.config_manager import ConfigManager
from src.itchat_module.admin_commands import AdminCommandsHandler


class WxAutoHandler:
    """
    微信登录和消息处理的主类，负责初始化配置、登录微信、绑定消息处理器等操作。
    """

    def __init__(self, error_handler, notifier, browser_controller, point_manager):
        # 加载配置
        self.config = ConfigManager.load_config()
        # 获取管理员列表
        self.admins: List[str] = self.config.get('wechat', {}).get('admins', [])
        # 获取监听列表
        self.listen_list: List[str] = self.config.get('wechat', {}).get('listen_list', [])
        # 从 group_types 中提取群组
        group_types = self.config.get('wechat', {}).get('group_types', {})
        self.whole_groups: List[str] = group_types.get('whole_groups', [])
        self.non_whole_groups: List[str] = group_types.get('non_whole_groups', [])
        self.error_handler = error_handler
        # 最大重试次数
        self.max_retries = self.config.get('wechat', {}).get('wxauto', {}).get('qr_check', {}).get('max_retries', 5)
        # 重试间隔时间
        self.retry_interval = self.config.get('wechat', {}).get('wxauto', {}).get('qr_check', {}).get('retry_interval', 2)
        # 登录事件，用于线程同步
        self.point_manager = point_manager
        self.uploader = None  # Uploader 实例
        logging.info("消息处理器初始化完成，但尚未绑定 Uploader")

        # 初始化 DownloadTaskQueue
        self.download_queue = DownloadTaskQueue(browser_controller=browser_controller)
        # 初始化 AdminCommandsHandler，用于处理管理员命令
        self.admin_commands_handler = AdminCommandsHandler(
            config=self.config,
            point_manager=self.point_manager,
            notifier=notifier,
            browser_controller=browser_controller,
            error_handler=error_handler
        )

        # 初始化消息处理器
        self.message_handler = MessageHandler(
            error_handler=error_handler,
            admins=self.admins,
            notifier=notifier,
            browser_controller=browser_controller,
            point_manager=self.point_manager,
            admin_commands_handler=self.admin_commands_handler,
            add_download_task_callback=self.add_download_task  # 添加回调
        )
        # 设置消息处理器的 uploader
        self.message_handler.set_uploader(self.uploader)

        # 初始化 wxauto 微信对象
        self.wx = WeChat()

        # 添加监听对象
        self.add_listen_chats()

        # 启动监听线程
        self.listen_thread = threading.Thread(target=self.listen_messages, daemon=True)
        self.listen_thread.start()

    def add_listen_chats(self):
        """添加监听列表中的聊天对象"""
        for chat in self.listen_list:
            try:
                self.wx.AddListenChat(who=chat, savepic=True)
                logging.info(f"已添加监听聊天对象: {chat}")
            except Exception as e:
                logging.error(f"添加监听聊天对象 {chat} 时出错: {e}")

    def listen_messages(self):
        """持续监听消息，并对接收到的消息进行解析处理"""
        wait = 1  # 设置1秒查看一次是否有新消息
        logging.info("开始启动消息监听线程")
        while True:
            try:
                msgs = self.wx.GetListenMessage()
                for chat in msgs:
                    who = chat.who  # 获取聊天窗口名（人或群名）
                    one_msgs = msgs.get(chat)  # 获取消息内容
                    for msg in one_msgs:
                        content = msg.content    # 获取消息内容，字符串类型的消息内容
                        logging.debug(f'【{who}】：{content}')
                        self.run(msg)
            except Exception as e:
                logging.error(f"监听消息时出错: {e}")
                self.error_handler.handle_error(e)
            time.sleep(wait)

    def run(self, msg):
        """处理接收到的消息内容"""
        if msg.chat_type == 'friend':
            self.message_handler.handle_individual_message(msg)
        elif msg.chat_type == 'group':
            logging.info(f"处理群组消息来自 {msg.sender} 在 {msg.chat_name}: {msg.content}")
            self.message_handler.handle_group_message(msg)

    def set_uploader(self, uploader):
        """绑定 Uploader 实例到消息处理器"""
        self.uploader = uploader
        self.message_handler.set_uploader(uploader)

    def update_config(self, new_config):
        """更新配置并应用变化"""
        self.config = new_config
        # 更新监听列表
        self.listen_list = self.config.get('wechat', {}).get('listen_list', [])

        # 从 group_types 中提取群组
        group_types = self.config.get('wechat', {}).get('group_types', {})
        self.whole_groups: List[str] = group_types.get('whole_groups', [])
        self.non_whole_groups: List[str] = group_types.get('non_whole_groups', [])

        # 更新管理员列表
        self.admins: List[str] = self.config.get('wechat', {}).get('admins', [])

        # 更新 MessageHandler 的配置
        self.message_handler.update_config(new_config)

        # 重新添加监听对象
        self.add_listen_chats()
        logging.info("WxAutoHandler 配置已更新")

    def add_download_task(self, url: str):
        """将下载任务添加到队列"""
        self.download_queue.add_task(url)

class MessageHandler:
    """
    消息处理器，用于处理微信消息，提取URL并调用相关处理逻辑
    """

    def __init__(self, error_handler, admins, notifier=None,
                 browser_controller=None, point_manager=None, admin_commands_handler=None,
                 add_download_task_callback=None):
        # 加载配置
        self.config = ConfigManager.load_config()
        # 初始化正则表达式，用于匹配URL
        self.regex = re.compile(self.config.get('url', {}).get('regex', r'https?://[^\s"」]+'))
        # URL 验证开关
        self.validation = self.config.get('url', {}).get('validation', True)
        self.uploader = None  # Uploader 实例
        self.error_handler = error_handler
        # 监控的群组、个人和管理员列表
        self.admins = admins
        self.notifier = notifier
        self.browser_controller = browser_controller
        # 日志目录
        self.log_dir = self.config.get('logging', {}).get('directory', 'logs')
        self.point_manager = point_manager
        # 群组类型配置
        self.group_types = self.config.get('wechat', {}).get('group_types', {})
        self.admin_commands_handler = admin_commands_handler
        self.add_download_task_callback = add_download_task_callback

    def update_config(self, new_config):
        """更新配置并应用变化"""
        self.config = new_config
        # 更新正则表达式和验证设置
        self.regex = re.compile(self.config.get('url', {}).get('regex', r'https?://[^\s"」]+'))
        self.validation = self.config.get('url', {}).get('validation', True)
        # 更新日志目录和群组类型配置
        self.log_dir = self.config.get('logging', {}).get('directory', 'logs')
        self.group_types = self.config.get('wechat', {}).get('group_types', {})

        logging.info("MessageHandler 配置已更新")

    def set_uploader(self, uploader):
        """设置 Uploader 实例用于上传相关信息"""
        self.uploader = uploader

    def get_message_content(self, msg) -> str:
        """获取消息的完整文本内容"""
        try:
            # 获取消息类型，并转换为小写以便比较
            msg_type = getattr(msg, 'type', '').lower()
            logging.debug(f"消息类型: {msg_type}")

            # 仅处理 'friend' 和 'self' 类型的消息
            if msg_type not in ['friend', 'self']:
                logging.debug(f"忽略类型为 '{msg_type}' 的消息")
                return ''

            # 提取消息内容，并去除前后空白字符
            content = getattr(msg, 'content', '').strip()
            logging.debug(f"提取的消息内容: {content}")

            return content
        except AttributeError as e:
            logging.error(f"无法提取消息内容，消息对象缺少预期的属性: {e}")
            return ''

    def check_points(self, message_type, context_name, sender_name=None, group_type=None) -> bool:
        """
        检查消息发送者或群组是否有足够的积分

        :param message_type: 消息类型，'group' 或 'individual'
        :param context_name: 群组名或个人名
        :param sender_name: 发送者昵称（如果是非整体群组，需要提供）
        :param group_type: 群组类型，'whole' 或 'non-whole'
        :return: 是否有足够的积分
        """
        logging.debug(
            f"开始积分检查 - 消息类型: {message_type}, 上下文名称: {context_name}, 发送者: {sender_name}, 群组类型: {group_type}")
        if message_type == 'group':
            if group_type == 'whole':
                # 整体群组积分检查
                has_points = self.point_manager.has_group_points(context_name)
                logging.debug(f"群组 '{context_name}' 是否有足够的积分: {has_points}")
                if not has_points:
                    logging.info(f"群组 '{context_name}' 的积分不足")
                    return False
            elif group_type == 'non-whole':
                if sender_name is None:
                    logging.warning("非整体群组需要提供发送者昵称")
                    return False
                # 确保用户存在于数据库中
                self.point_manager.ensure_user(context_name, sender_name)
                # 用户积分检查
                has_points = self.point_manager.has_user_points(context_name, sender_name)
                logging.debug(f"用户 '{sender_name}' 在群组 '{context_name}' 中是否有足够的积分: {has_points}")
                if not has_points:
                    logging.info(f"用户 '{sender_name}' 在群组 '{context_name}' 中的积分不足")
                    return False
            else:
                logging.warning(f"未知的群组类型: {group_type}")
                return False
        elif message_type == 'individual':
            # 个人积分检查
            has_points = self.point_manager.has_recipient_points(context_name)
            logging.debug(f"个人 '{context_name}' 是否有足够的积分: {has_points}")
            if not has_points:
                logging.info(f"个人 '{context_name}' 的积分不足")
                return False
        else:
            logging.warning(f"未知的消息类型: {message_type}")
            return False
        logging.debug("积分检查通过")
        return True

    def handle_group_message(self, msg):
        """处理来自群组的消息，提取并处理URL"""
        logging.debug(f"处理群组消息: {msg}")

        # 获取消息属性
        group_name = msg.chat_name  # 群组名称

        # 确定群组类型
        if group_name in self.group_types.get('whole', []):
            group_type = 'whole'
        elif group_name in self.group_types.get('non-whole', []):
            group_type = 'non-whole'
        else:
            group_type = 'whole'  # 默认类型

        # 获取发送者昵称
        sender_nickname = msg.sender  # 发送者昵称

        setattr(msg, 'group_type', group_type)

        # 提取消息中的URL
        urls = self.extract_urls(msg)
        if not urls:
            return

        # 处理URL，得到有效的URL列表
        valid_urls = self.process_urls(urls)
        if not valid_urls:
            return

        # 进行积分检查
        point_check = self.check_points(
            message_type='group',
            context_name=group_name,
            sender_name=sender_nickname,
            group_type=group_type
        )
        if not point_check:
            return

        # 通过积分检查后，调用上传和添加任务函数
        for url, soft_id in valid_urls:
            if self.uploader and soft_id:
                # 上传群组ID和 soft_id
                self.uploader.upload_group_id(
                    recipient_name=group_name,
                    soft_id=soft_id,
                    sender_nickname=sender_nickname if group_type == 'non-whole' else None,
                    recipient_type='group',
                    group_type=group_type
                )
            else:
                logging.warning("Uploader 未设置，或无法上传接收者和 soft_id 信息。")

            # 使用回调将任务添加到队列
            if self.add_download_task_callback:
                self.add_download_task_callback(url)
            else:
                logging.warning("下载任务回调未设置，无法添加下载任务。")

    def handle_individual_message(self, msg):
        """处理来自个人的消息，提取URL或执行管理员命令"""
        logging.debug(f"处理个人消息: {msg}")

        # 获取消息属性
        sender = msg.sender  # 发送者昵称
        logging.debug(f"发送者昵称: {sender}")
        logging.debug(f"管理员列表: {self.admins}")

        if sender in self.admins:
            # 如果是管理员，处理命令
            content = self.get_message_content(msg)  # 获取完整消息内容
            response = self.handle_admin_command(content)
            if response and self.notifier:
                # 发送命令处理的响应
                self.notifier.notify(response)
            return

        # 提取URL
        urls = self.extract_urls(msg)
        if not urls:
            return

        # 处理URL，得到有效的URL列表
        valid_urls = self.process_urls(urls)
        if not valid_urls:
            return

        # 检查积分
        if not self.check_points(
                message_type='individual',
                context_name=sender
        ):
            return

        # 通过积分检查后，调用上传和添加任务函数
        for url, soft_id in valid_urls:
            if self.uploader and soft_id:
                # 上传个人ID和 soft_id
                self.uploader.upload_group_id(
                    recipient_name=sender,
                    soft_id=soft_id,
                    recipient_type='individual'
                )
            else:
                logging.warning("Uploader 未设置，或无法上传接收者和 soft_id 信息。")

            # 使用回调将任务添加到队列
            if self.add_download_task_callback:
                self.add_download_task_callback(url)
            else:
                logging.warning("下载任务回调未设置，无法添加下载任务。")

    def handle_admin_command(self, message: str) -> Optional[str]:
        """委托 AdminCommandsHandler 处理管理员命令"""
        response = self.admin_commands_handler.handle_command(message)
        return response

    def extract_urls(self, msg) -> List[str]:
        """从消息中提取URL列表"""
        content = self.get_message_content(msg)
        if not content:
            return []

        # 使用正则表达式提取URL
        urls = self.regex.findall(content)
        return urls

    def process_urls(self, urls: List[str]) -> list[tuple[bytes, str | None | Any]]:
        """清理、验证并处理URL，返回有效的 (url, soft_id) 列表"""
        valid_urls = []
        for url in urls:
            # 清理URL并验证
            # 使用 urlparse 解析URL
            parsed = urlparse(url)
            # 移除 fragment（#后面的部分）
            clean = parsed._replace(fragment='')
            # 重新构建 URL，并移除结尾的特殊字符
            cleaned_url = urlunparse(clean).rstrip('」””"\'')
            # 验证URL（检查是否以 http:// 或 https:// 开头）
            if self.validation and not cleaned_url.startswith(('http://', 'https://')):
                logging.warning(f"URL 验证失败: {cleaned_url}")
                continue

            # 从URL中提取 soft_id
            soft_id_match = re.search(r'/soft/(\d+)\.html', cleaned_url)
            if soft_id_match:
                soft_id = soft_id_match.group(1)
            else:
                logging.warning(f"无法从 URL 中提取 soft_id: {cleaned_url}")
                soft_id = None

            valid_urls.append((cleaned_url, soft_id))

        return valid_urls

    def get_last_n_logs(self, n: int) -> Optional[str]:
        """获取日志目录下最新日志文件的最后 n 行内容"""
        log_files = [f for f in os.listdir(self.log_dir) if f.endswith('.log')]
        if not log_files:
            logging.warning("日志目录下没有日志文件。")
            return None

        # 找到最新的日志文件
        latest_log_file = max(log_files, key=lambda x: os.path.getmtime(os.path.join(self.log_dir, x)))
        log_path = os.path.join(self.log_dir, latest_log_file)

        with open(log_path, 'r', encoding='utf-8') as f:
            # 使用 deque 读取文件的最后 n 行
            return ''.join(deque(f, n))

class DownloadTaskQueue:
    def __init__(self, browser_controller, batch_size=10, initial_interval=30,
                 min_interval=5, max_interval=60, high_threshold=20, low_threshold=10):
        """
        初始化下载任务队列，并设置动态调整间隔时间的参数。

        :param browser_controller: 用于处理下载任务的浏览器控制器实例
        :param batch_size: 每批处理的链接数量
        :param initial_interval: 初始处理间隔时间（秒）
        :param min_interval: 最小处理间隔时间（秒）
        :param max_interval: 最大处理间隔时间（秒）
        :param high_threshold: 队列长度高阈值，超过此值将增加间隔
        :param low_threshold: 队列长度低阈值，低于此值将减少间隔
        """
        self.browser_controller = browser_controller
        self.batch_size = batch_size
        self.current_interval = initial_interval
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.queue = queue.Queue()
        self.lock = threading.Lock()  # 用于保护 current_interval
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()
        logging.debug("下载任务队列已启动，初始间隔时间为 %s 秒", self.current_interval)

    def add_task(self, url: str):
        """将下载任务添加到队列中"""
        self.queue.put(url)
        logging.debug(f"任务已添加到队列: {url}")

    def adjust_interval(self):
        """根据队列长度动态调整处理间隔时间"""
        queue_size = self.queue.qsize()
        with self.lock:
            if queue_size > self.high_threshold:
                # 计算需要增加的倍数，确保延迟显著增加
                multiplier = 2 + (queue_size - self.high_threshold) // 10
                new_interval = self.current_interval * multiplier
                self.current_interval = min(new_interval, self.max_interval)
                logging.debug(f"队列长度为 {queue_size}，增加处理间隔到 {self.current_interval:.2f} 秒")
            elif queue_size < self.low_threshold:
                # 减少间隔时间
                self.current_interval = max(self.current_interval / 1.5, self.min_interval)
                logging.debug(f"队列长度为 {queue_size}，减少处理间隔到 {self.current_interval:.2f} 秒")
            else:
                logging.debug(f"队列长度为 {queue_size}，保持处理间隔为 {self.current_interval:.2f} 秒")

    def worker(self):
        """后台线程，定期处理下载任务，并动态调整间隔时间"""
        while True:
            batch = []
            for _ in range(self.batch_size):
                try:
                    # 使用较短的超时时间，例如 1 秒
                    url = self.queue.get(timeout=1)
                    batch.append(url)
                except queue.Empty:
                    break

            if batch:
                logging.info(f"开始处理 {len(batch)} 个下载任务")
                for url in batch:
                    try:
                        self.browser_controller.add_task(url)
                        logging.info(f"已添加任务到下载队列: {url}")
                    except Exception as e:
                        logging.error(f"处理任务 {url} 时出错: {e}")
                # 动态调整间隔时间
                self.adjust_interval()
            else:
                logging.debug("任务队列为空，等待新的任务")
                # 动态调整间隔时间
                self.adjust_interval()

            # 等待当前间隔时间再处理下一批任务
            with self.lock:
                interval = self.current_interval
            logging.debug(f"等待 {interval:.2f} 秒后处理下一批任务")
            time.sleep(interval)