# src/itchat_module/itchat_handler.py

import logging
import os
import re
import threading
import time
from io import BytesIO
from urllib.parse import urlparse, urlunparse
from PIL import Image
from lib import itchat
from lib.itchat.content import TEXT, SHARING
from typing import Optional, List
from collections import deque


class ItChatHandler:
    def __init__(self, config, error_handler, notifier, browser_controller):
        self.monitor_groups: List[str] = config.get('monitor_groups', [])
        self.target_individuals: List[str] = config.get('target_individuals', [])
        self.admins: List[str] = config.get('admins', [])
        self.error_handler = error_handler
        self.qr_path = config.get('login_qr_path', 'qr.png')
        self.max_retries = config.get('itchat', {}).get('qr_check', {}).get('max_retries', 5)
        self.retry_interval = config.get('itchat', {}).get('qr_check', {}).get('retry_interval', 2)
        self.login_event = threading.Event()

        self.message_handler = MessageHandler(
            config=config,
            error_handler=error_handler,
            monitor_groups=self.monitor_groups,
            target_individuals=self.target_individuals,
            admins=self.admins,
            notifier=notifier,
            browser_controller=browser_controller
        )

        self.uploader = None
        self.message_handler.set_uploader(self.uploader)

        logging.info("消息处理器初始化完成，但尚未绑定 Uploader")

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
            try:
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
            except Exception as e:
                logging.error(f"登录失败，第 {attempt} 次尝试。错误: {e}")
                self.error_handler.handle_exception(e)
                time.sleep(self.retry_interval)

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

        try:
            itchat.run()
        except Exception as e:
            logging.critical(f"ItChat 运行时发生致命错误: {e}")
            self.error_handler.handle_exception(e)

    def qr_callback(self, uuid, status, qrcode):
        """处理二维码回调，保存并显示二维码图像"""
        logging.info(f"QR callback - UUID: {uuid}, Status: {status}")
        try:
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
        except Exception as e:
            logging.error(f"处理QR码时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def logout(self):
        """登出微信账号，结束当前会话"""
        try:
            itchat.logout()
            logging.info("微信已退出")
        except Exception as e:
            logging.error(f"退出微信时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)


class MessageHandler:
    """
    消息处理器，用于处理微信消息，提取URL并调用 AutoClicker
    """

    def __init__(self, config, error_handler, monitor_groups, target_individuals, admins, notifier=None, browser_controller=None):
        self.regex = re.compile(config.get('regex', r'https?://[^\s"」]+'))
        self.validation = config.get('validation', True)
        self.auto_clicker = None
        self.uploader = None
        self.error_handler = error_handler
        self.monitor_groups = monitor_groups
        self.target_individuals = target_individuals
        self.admins = admins
        self.notifier = notifier
        self.browser_controller = browser_controller
        self.log_dir = config.get('logging', {}).get('directory', 'logs')

    def set_auto_clicker(self, auto_clicker):
        """设置 AutoClicker 实例用于自动处理任务"""
        self.auto_clicker = auto_clicker

    def set_uploader(self, uploader):
        """设置 Uploader 实例用于上传相关信息"""
        self.uploader = uploader

    def handle_group_message(self, msg):
        """处理来自群组的消息，提取并处理URL"""
        group_name = msg['User']['NickName']
        if group_name not in self.monitor_groups:
            logging.debug(f"忽略来自非监控群组的消息: {group_name}")
            return

        urls = self.extract_urls(msg)
        if not urls:
            return

        valid_urls = self.process_urls(urls, is_group=True, recipient_name=group_name)
        if self.auto_clicker and valid_urls:
            for url in valid_urls:
                self.auto_clicker.add_task(url)
                logging.info(f"已添加任务到下载队列: {url}")
        else:
            logging.warning("AutoClicker 未设置或没有有效的 URL，无法添加任务。")

    def handle_individual_message(self, msg):
        """处理来自个人的消息，提取URL或执行管理员命令"""
        sender = msg['User']['NickName']
        if sender not in self.target_individuals and sender not in self.admins:
            logging.debug(f"忽略来自非监控个人的消息: {sender}")
            return

        content = self.extract_urls(msg)
        if not content:
            return

        if sender in self.admins:
            response = self.handle_admin_command(content)
            if response and self.notifier:
                self.notifier.notify(response)
            return

        urls = self.extract_urls(msg)
        if not urls:
            return

        valid_urls = self.process_urls(urls, is_group=False, recipient_name=sender)
        if self.auto_clicker and valid_urls:
            for url in valid_urls:
                self.auto_clicker.add_task(url)
                logging.info(f"已添加任务到下载队列: {url}")
        else:
            logging.warning("AutoClicker 未设置或没有有效的 URL，无法添加任务。")

    def handle_admin_command(self, message: str) -> Optional[str]:
        """处理管理员发送的命令并执行相应操作"""
        commands = {
            'add_recipient': r'^添加接收者\s+(\S+)\s+(\d+)$',
            'delete_recipient': r'^删除接收者\s+(\S+)$',
            'update_remaining': r'^更新剩余次数\s+(\S+)\s+([+-]?\d+)$',
            'query_recipient': r'^查询接收者\s+(\S+)$',
            'get_all_recipients': r'^获取所有接收者$',
            'help': r'^帮助$|^help$',
            'restart_browser': r'^重启浏览器$|^restart browser$',
            'query_logs': r'^查询日志$|^query logs$',
            'query_browser': r'^查询浏览器$|^query browser$'
        }

        for cmd, pattern in commands.items():
            match = re.match(pattern, message)
            if match:
                if cmd == 'add_recipient':
                    name, count = match.groups()
                    return self.uploader.add_recipient(name, int(count)) if self.uploader else "Uploader 未设置。"
                elif cmd == 'delete_recipient':
                    name = match.group(1)
                    return self.uploader.delete_recipient(name) if self.uploader else "Uploader 未设置。"
                elif cmd == 'update_remaining':
                    name, delta = match.groups()
                    return self.uploader.update_remaining_count(name, int(delta)) if self.uploader else "Uploader 未设置。"
                elif cmd == 'query_recipient':
                    name = match.group(1)
                    info = self.uploader.get_recipient_info(name) if self.uploader else None
                    if info:
                        return f"接收者 '{info['name']}' 的剩余次数为 {info['remaining_count']}。"
                    return f"接收者 '{name}' 不存在。"
                elif cmd == 'get_all_recipients':
                    recipients = self.uploader.get_all_recipients() if self.uploader else []
                    return f"所有接收者列表：{', '.join(recipients)}" if recipients else "当前没有任何接收者。"
                elif cmd == 'help':
                    return self.get_help_message()
                elif cmd == 'restart_browser':
                    if self.browser_controller:
                        self.browser_controller.restart_browser()
                        return "浏览器已成功重启。"
                    return "浏览器控制器未设置，无法重启浏览器。"
                elif cmd == 'query_logs':
                    if self.notifier:
                        logs = self.get_last_n_logs(20)
                        if logs:
                            send_long_message(self.notifier, f"最近 20 行日志:\n{logs}")
                        else:
                            self.notifier.notify("无法读取日志文件或日志文件为空。")
                    else:
                        logging.error("Notifier 未设置，无法发送日志。")
                    return None
                elif cmd == 'query_browser':
                    if not self.browser_controller:
                        logging.error("浏览器控制器未设置，无法处理查询浏览器命令。")
                        if self.notifier:
                            self.notifier.notify("无法处理查询浏览器命令，因为浏览器控制器未设置。", is_error=True)
                        return "浏览器控制器未设置，无法查询浏览器。"

                    try:
                        screenshots = self.browser_controller.capture_all_tabs_screenshots()
                        if screenshots:
                            self.notifier.notify_images(screenshots)
                            for path in screenshots:
                                os.remove(path)
                                logging.debug(f"已删除临时截图文件: {path}")
                        else:
                            self.notifier.notify("无法捕获浏览器标签页的截图。", is_error=True)
                    except Exception as e:
                        logging.error(f"处理查询浏览器命令时发生错误: {e}", exc_info=True)
                        if self.notifier:
                            self.notifier.notify(f"处理查询浏览器命令时发生错误: {e}", is_error=True)
                    return None
        logging.warning(f"未知的管理员命令：{message}")
        return "未知的命令，请检查命令格式。"

    def get_help_message(self) -> str:
        """返回可用命令的帮助信息"""
        return (
            "可用命令如下：\n\n"
            "1. 添加接收者 <接收者名称> <初始剩余次数>\n"
            "   示例：添加接收者 User1 500\n\n"
            "2. 删除接收者 <接收者名称>\n"
            "   示例：删除接收者 User1\n\n"
            "3. 更新剩余次数 <接收者名称> <变化量>\n"
            "   示例：更新剩余次数 User1 -10\n\n"
            "4. 查询接收者 <接收者名称>\n"
            "   示例：查询接收者 User1\n\n"
            "5. 获取所有接收者\n"
            "   示例：获取所有接收者\n\n"
            "6. 帮助\n"
            "   示例：帮助\n\n"
            "7. 重启浏览器\n"
            "   示例：重启浏览器\n\n"
            "8. 查询日志\n"
            "   示例：查询日志\n\n"
            "9. 查询浏览器\n"
            "   示例：查询浏览器"
        )

    def extract_urls(self, msg) -> List[str]:
        """从消息中提取URL列表"""
        try:
            msg_type = msg.get('Type', getattr(msg, 'type', ''))
            if msg_type not in ['Text', 'Sharing']:
                logging.debug(f"忽略非文本或分享类型的消息: {msg_type}")
                return []

            content = msg.get('Text', msg.get('text', '')) if msg_type == 'Text' else msg.get('Url', msg.get('url', ''))
            return self.regex.findall(content)
        except Exception as e:
            logging.error(f"提取消息内容时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return []

    def process_urls(self, urls: List[str], is_group: bool, recipient_name: str) -> List[str]:
        """清理、验证并处理URL，上传相关信息，返回有效的URL列表"""
        valid_urls = []
        for url in urls:
            clean_url = self.clean_url(url)
            if self.validation and not self.validate_url(clean_url):
                logging.warning(f"URL 验证失败: {clean_url}")
                continue

            valid_urls.append(clean_url)

            soft_id_match = re.search(r'/soft/(\d+)\.html', clean_url)
            if soft_id_match:
                soft_id = soft_id_match.group(1)
                if self.uploader:
                    self.uploader.upload_group_id(recipient_name, soft_id)
                    logging.info(f"上传信息到 Uploader: {recipient_name}, {soft_id}")
                else:
                    logging.warning("Uploader 未设置，无法上传接收者和 soft_id 信息。")
            else:
                logging.warning(f"无法从 URL 中提取 soft_id: {clean_url}")

        return valid_urls

    def clean_url(self, url: str) -> str:
        """清理URL，移除锚点和不必要的字符"""
        try:
            parsed = urlparse(url)
            clean = parsed._replace(fragment='')
            cleaned_url = urlunparse(clean).rstrip('」””"\'')
            return cleaned_url
        except Exception as e:
            logging.error(f"清理 URL 时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return url

    def validate_url(self, url: str) -> bool:
        """验证URL是否以http://或https://开头"""
        return url.startswith(('http://', 'https://'))

    def get_last_n_logs(self, n: int) -> Optional[str]:
        """获取日志目录下最新日志文件的最后n行内容"""
        try:
            log_files = [f for f in os.listdir(self.log_dir) if f.endswith('.log')]
            if not log_files:
                logging.warning("日志目录下没有日志文件。")
                return None

            latest_log_file = max(log_files)
            log_path = os.path.join(self.log_dir, latest_log_file)

            with open(log_path, 'r', encoding='utf-8') as f:
                return ''.join(deque(f, n))
        except Exception as e:
            logging.error(f"读取日志文件时出错: {e}", exc_info=True)
            return None


def send_long_message(notifier, message: str, max_length: int = 2000):
    """将长消息分割为多个部分并逐段发送"""
    try:
        for i in range(0, len(message), max_length):
            notifier.notify(message[i:i + max_length])
    except Exception as e:
        logging.error(f"发送长消息时出错: {e}", exc_info=True)
