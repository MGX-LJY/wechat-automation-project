# src/itchat_module/itchat_handler.py

import logging
import os
import re
import threading
import time
from collections import deque
from io import BytesIO
from typing import Optional, List, Tuple
from urllib.parse import urlparse, urlunparse
from PIL import Image
from lib import itchat
from lib.itchat.content import TEXT, SHARING
from src.config.config_manager import ConfigManager  # 新增导入
from src.itchat_module.admin_commands import AdminCommandsHandler  # 新增导入


class ItChatHandler:
    def __init__(self, error_handler, notifier, browser_controller, point_manager):
        self.config = ConfigManager.load_config()
        self.monitor_groups: List[str] = self.config.get('wechat', {}).get('monitor_groups', [])
        self.target_individuals: List[str] = self.config.get('wechat', {}).get('target_individuals', [])
        self.admins: List[str] = self.config.get('wechat', {}).get('admins', [])
        self.error_handler = error_handler
        self.point_manager = point_manager
        self.qr_path = self.config.get('wechat', {}).get('login_qr_path', 'qr.png')
        self.max_retries = self.config.get('wechat', {}).get('itchat', {}).get('qr_check', {}).get('max_retries', 5)
        self.retry_interval = self.config.get('wechat', {}).get('itchat', {}).get('qr_check', {}).get('retry_interval',
                                                                                                      2)
        self.login_event = threading.Event()
        self.point_manager = point_manager

        self.message_handler = MessageHandler(
            error_handler=error_handler,
            monitor_groups=self.monitor_groups,
            target_individuals=self.target_individuals,
            admins=self.admins,
            notifier=notifier,
            browser_controller=browser_controller,
            point_manager=self.point_manager,
        )

        self.uploader = None
        self.message_handler.set_uploader(self.uploader)

        logging.info("消息处理器初始化完成，但尚未绑定 Uploader")

        # 初始化 AdminCommandsHandler
        self.admin_commands_handler = AdminCommandsHandler(
            config=self.config,
            point_manager=self.point_manager,
            notifier=notifier,
            browser_controller=browser_controller,
            error_handler=error_handler
        )

    def set_uploader(self, uploader):
        """绑定 Uploader 实例到消息处理器"""
        self.uploader = uploader
        self.message_handler.set_uploader(uploader)
        logging.info("Uploader 已绑定到消息处理器")

    def set_auto_clicker(self, auto_clicker):
        """
        设置 MessageHandler 的 AutoClicker 实例
        """
        self.message_handler.set_auto_clicker(auto_clicker)
        logging.info("AutoClicker 已设置到消息处理器")

    def login(self):
        """执行微信登录过程，处理二维码显示和会话管理"""
        for attempt in range(1, self.max_retries + 1):
            session_file = 'itchat.pkl'
            if os.path.exists(session_file):
                os.remove(session_file)
                logging.info(f"已删除旧的会话文件: {session_file}")

            itchat.auto_login(
                hotReload=False,
                enableCmdQR=False,
                qrCallback=self.qr_callback
            )
            logging.info("微信登录成功")

            itchat.get_friends(update=True)
            itchat.get_chatrooms(update=True)
            logging.info("好友和群组信息已加载")

            self.login_event.set()
            return

        logging.critical("多次登录失败，应用启动失败。")
        raise Exception("多次登录失败，应用启动失败。")

    def run(self):
        """注册消息处理函数并启动 ItChat 客户端监听消息"""

        @itchat.msg_register([TEXT, SHARING], isGroupChat=True)
        def handle_group(msg):
            self.message_handler.handle_group_message(msg)

        @itchat.msg_register([TEXT, SHARING], isGroupChat=False)
        def handle_individual(msg):
            self.message_handler.handle_individual_message(msg)

        itchat.run()

    def qr_callback(self, uuid, status, qrcode):
        """处理二维码回调，保存并显示二维码图像"""
        logging.info(f"QR callback - UUID: {uuid}, Status: {status}")
        if status == '0':
            with open(self.qr_path, 'wb') as f:
                f.write(qrcode)
            logging.info(f"二维码已保存到 {self.qr_path}")

            Image.open(BytesIO(qrcode)).show(title="微信登录二维码")
        elif status == '201':
            logging.info("二维码已扫描，请在手机上确认登录。")
        elif status == '200':
            logging.info("登录成功")
        else:
            logging.warning(f"未知的QR回调状态: {status}")

    def logout(self):
        """登出微信账号，结束当前会话"""
        itchat.logout()
        logging.info("微信已退出")


class MessageHandler:
    """
    消息处理器，用于处理微信消息，提取URL并调用 AutoClicker
    """

    def __init__(self, error_handler, monitor_groups, target_individuals, admins, notifier=None,
                 browser_controller=None, point_manager=None, admin_commands_handler=None):
        self.config = ConfigManager.load_config()
        self.regex = re.compile(self.config.get('url', {}).get('regex', r'https?://[^\s"」]+'))
        self.validation = self.config.get('url', {}).get('validation', True)
        self.auto_clicker = None
        self.uploader = None
        self.error_handler = error_handler
        self.monitor_groups = monitor_groups
        self.target_individuals = target_individuals
        self.admins = admins
        self.notifier = notifier
        self.browser_controller = browser_controller
        self.log_dir = self.config.get('logging', {}).get('directory', 'logs')
        self.point_manager = point_manager
        self.group_types = self.config.get('wechat', {}).get('group_types', {})
        self.admin_commands_handler = admin_commands_handler  # 新增属性

        # 初始化 AdminCommandsHandler
        self.admin_commands_handler = AdminCommandsHandler(
            config=self.config,
            point_manager=self.point_manager,
            notifier=notifier,
            browser_controller=browser_controller,
            error_handler=error_handler
        )

    def set_auto_clicker(self, auto_clicker):
        """设置 AutoClicker 实例用于自动处理任务"""
        self.auto_clicker = auto_clicker

    def set_uploader(self, uploader):
        """设置 Uploader 实例用于上传相关信息"""
        self.uploader = uploader

    def get_message_content(self, msg) -> str:
        """获取消息的完整文本内容"""
        msg_type = msg.get('Type', getattr(msg, 'type', ''))
        if msg_type not in ['Text', 'Sharing']:
            return ''
        return msg.get('Text', msg.get('text', '')) if msg_type == 'Text' else msg.get('Url', msg.get('url', ''))

    def check_points(self, message_type, context_name, sender_name=None, group_type=None) -> bool:
        logging.debug(
            f"开始积分检查 - 消息类型: {message_type}, 上下文名称: {context_name}, 发送者: {sender_name}, 群组类型: {group_type}")
        if message_type == 'group':
            if group_type == 'whole':
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
                has_points = self.point_manager.has_user_points(context_name, sender_name)
                logging.debug(f"用户 '{sender_name}' 在群组 '{context_name}' 中是否有足够的积分: {has_points}")
                if not has_points:
                    logging.info(f"用户 '{sender_name}' 在群组 '{context_name}' 中的积分不足")
                    return False
            else:
                logging.warning(f"未知的群组类型: {group_type}")
                return False
        elif message_type == 'individual':
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

        # 尝试获取群组名称
        group_name = msg.get('User', {}).get('NickName', '')
        if group_name not in self.monitor_groups:
            logging.debug(f"忽略来自非监控群组的消息: {group_name}")
            return

        # 获取群组类型
        if group_name in self.group_types.get('whole_groups', []):
            group_type = 'whole'
        elif group_name in self.group_types.get('non_whole_groups', []):
            group_type = 'non-whole'
        else:
            # 默认设为整体群组
            group_type = 'whole'

        logging.debug(f"群组类型: {group_type}")

        # 获取发送者昵称
        sender_nickname = msg.get('ActualNickName', '')
        logging.debug(f"发送者昵称: {sender_nickname}")

        # 提取URL
        urls = self.extract_urls(msg)
        logging.debug(f"提取的URLs: {urls}")
        if not urls:
            logging.debug("未找到任何URL，停止处理")
            return

        # 处理URL，得到有效的URL列表
        valid_urls = self.process_urls(urls)
        logging.debug(f"有效的URLs: {valid_urls}")
        if not valid_urls:
            logging.debug("未找到有效的URL，停止处理")
            return

        logging.debug(f"群组名称: {group_name}")
        logging.debug(f"发送者昵称: {sender_nickname}")
        logging.debug(f"群组类型: {group_type}")

        # 在积分检查之前添加日志
        logging.debug("即将进行积分检查")
        point_check = self.check_points(
            message_type='group',
            context_name=group_name,
            sender_name=sender_nickname,
            group_type=group_type
        )
        logging.debug(f"积分检查结果: {point_check}")
        if not point_check:
            logging.debug("积分检查未通过，停止处理")
            return

        # 通过积分检查后，调用上传和添加任务函数
        for url, soft_id in valid_urls:
            logging.debug(f"处理 URL: {url}, soft_id: {soft_id}")
            if self.uploader and soft_id:
                self.uploader.upload_group_id(
                    recipient_name=group_name,
                    soft_id=soft_id,
                    sender_nickname=sender_nickname if group_type == 'non-whole' else None,
                    recipient_type='group',
                    group_type=group_type
                )
                logging.info(f"上传信息到 Uploader: {group_name}, {soft_id}, 发送者: {sender_nickname}")
            else:
                logging.warning("Uploader 未设置，或无法上传接收者和 soft_id 信息。")

            if self.auto_clicker:
                self.auto_clicker.add_task(url)
                logging.info(f"已添加任务到下载队列: {url}")
            else:
                logging.warning("AutoClicker 未设置，无法添加任务。")

    def handle_individual_message(self, msg):
        """处理来自个人的消息，提取URL或执行管理员命令"""
        logging.debug(f"处理个人消息: {msg}")

        sender = msg['User'].get('NickName', '')
        logging.debug(f"发送者昵称: {sender}")
        logging.debug(f"监控的个人列表: {self.target_individuals}")
        logging.debug(f"管理员列表: {self.admins}")

        if sender not in self.target_individuals and sender not in self.admins:
            logging.debug(f"忽略来自非监控个人的消息: {sender}")
            return

        if sender in self.admins:
            content = self.get_message_content(msg)  # 获取完整消息内容
            logging.debug(f"管理员命令内容: {content}")
            response = self.handle_admin_command(content)
            if response and self.notifier:
                self.notifier.notify(response)
            return

        # 提取URL
        urls = self.extract_urls(msg)
        logging.debug(f"提取的URLs: {urls}")
        if not urls:
            logging.debug("未找到任何URL，停止处理")
            return

        # 处理URL，得到有效的URL列表
        valid_urls = self.process_urls(urls)
        logging.debug(f"有效的URLs: {valid_urls}")
        if not valid_urls:
            logging.debug("未找到有效的URL，停止处理")
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
                self.uploader.upload_group_id(
                    recipient_name=sender,
                    soft_id=soft_id,
                    recipient_type='individual'
                )
                logging.info(f"上传信息到 Uploader: {sender}, {soft_id}")
            else:
                logging.warning("Uploader 未设置，或无法上传接收者和 soft_id 信息。")

            if self.auto_clicker:
                self.auto_clicker.add_task(url)
                logging.info(f"已添加任务到下载队列: {url}")
            else:
                logging.warning("AutoClicker 未设置，无法添加任务。")

    def handle_admin_command(self, message: str) -> Optional[str]:
        """委托 AdminCommandsHandler 处理管理员命令"""
        response = self.admin_commands_handler.handle_command(message)
        return response


    def extract_urls(self, msg) -> List[str]:
        """从消息中提取URL列表"""
        msg_type = msg.get('Type', getattr(msg, 'type', ''))
        logging.debug(f"消息类型: {msg_type}")

        if msg_type not in ['Text', 'Sharing']:
            logging.debug(f"忽略非文本或分享类型的消息: {msg_type}")
            return []

        content = msg.get('Text', msg.get('text', '')) if msg_type == 'Text' else msg.get('Url', msg.get('url', ''))
        logging.debug(f"消息内容: {content}")

        urls = self.regex.findall(content)
        logging.debug(f"正则表达式提取的URLs: {urls}")
        return urls

    def process_urls(self, urls: List[str]) -> List[Tuple[str, Optional[str]]]:
        """清理、验证并处理URL，返回有效的 (url, soft_id) 列表"""
        valid_urls = []
        for url in urls:
            clean_url = self.clean_url(url)
            logging.debug(f"清理后的URL: {clean_url}")

            if self.validation and not self.validate_url(clean_url):
                logging.warning(f"URL 验证失败: {clean_url}")
                continue

            soft_id_match = re.search(r'/soft/(\d+)\.html', clean_url)
            if soft_id_match:
                soft_id = soft_id_match.group(1)
                logging.debug(f"从URL中提取的 soft_id: {soft_id}")
            else:
                logging.warning(f"无法从 URL 中提取 soft_id: {clean_url}")
                soft_id = None

            valid_urls.append((clean_url, soft_id))

        return valid_urls

    def clean_url(self, url: str) -> str:
        """清理URL，移除锚点和不必要的字符"""
        parsed = urlparse(url)
        clean = parsed._replace(fragment='')
        cleaned_url = urlunparse(clean).rstrip('」””"\'')
        return cleaned_url

    def validate_url(self, url: str) -> bool:
        """验证URL是否以http://或https://开头"""
        return url.startswith(('http://', 'https://'))

    def get_last_n_logs(self, n: int) -> Optional[str]:
        """获取日志目录下最新日志文件的最后n行内容"""
        log_files = [f for f in os.listdir(self.log_dir) if f.endswith('.log')]
        if not log_files:
            logging.warning("日志目录下没有日志文件。")
            return None

        latest_log_file = max(log_files, key=lambda x: os.path.getmtime(os.path.join(self.log_dir, x)))
        log_path = os.path.join(self.log_dir, latest_log_file)

        with open(log_path, 'r', encoding='utf-8') as f:
            return ''.join(deque(f, n))

def send_long_message(notifier, message: str, max_length: int = 2000):
    """将长消息分割为多个部分并逐段发送"""
    for i in range(0, len(message), max_length):
        notifier.notify(message[i:i + max_length])
