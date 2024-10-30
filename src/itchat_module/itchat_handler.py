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
from lib.itchat.content import TEXT, SHARING  # 添加 SHARING 类型
from typing import Optional  # 添加这一行
from collections import deque  # 添加这一行


class ItChatHandler:
    def __init__(self, config, error_handler, notifier, browser_controller, log_callback=None, qr_queue=None):
        self.monitor_groups = config.get('monitor_groups', [])
        self.target_individuals = config.get('target_individuals', [])
        self.admins = config.get('admins', [])  # 获取管理员列表
        self.error_handler = error_handler
        self.qr_path = config.get('login_qr_path', 'qr.png')
        self.log_callback = log_callback
        self.max_retries = config.get('itchat', {}).get('qr_check', {}).get('max_retries', 5)
        self.retry_interval = config.get('itchat', {}).get('qr_check', {}).get('retry_interval', 2)
        self.qr_queue = qr_queue  # Queue to send QR code data to GUI
        self.login_event = threading.Event()

        # 初始化消息处理器，并传递 notifier 和 admins
        self.message_handler = MessageHandler(
            config=config,
            error_handler=error_handler,
            monitor_groups=self.monitor_groups,
            target_individuals=self.target_individuals,
            admins=self.admins,  # 传递管理员列表
            notifier=notifier,
            browser_controller=browser_controller  # 传递浏览器控制器
        )

        # Uploader 实例将在外部传递
        self.uploader = None  # 初始化为空，稍后通过主程序传递
        self.message_handler.set_uploader(self.uploader)

        logging.info("消息处理器初始化完成，但尚未绑定 Uploader")

    def set_uploader(self, uploader):
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
        retries = 0
        while retries < self.max_retries:
            try:
                # 删除旧的会话文件
                session_file = 'itchat.pkl'
                if os.path.exists(session_file):
                    os.remove(session_file)
                    logging.info(f"已删除旧的会话文件: {session_file}")
                    if self.log_callback:
                        self.log_callback(f"已删除旧的会话文件: {session_file}")

                # 登录微信，设置 hotReload=False
                itchat.auto_login(
                    hotReload=False,  # 禁用 Hot Reload
                    enableCmdQR=False,
                    qrCallback=self.qr_callback
                )
                logging.info("微信登录成功")
                if self.log_callback:
                    self.log_callback("微信登录成功")

                # 加载好友和群组信息
                itchat.get_friends(update=True)
                itchat.get_chatrooms(update=True)
                logging.info("好友和群组信息已加载")

                self.login_event.set()
                return  # 登录成功，退出方法
            except Exception as e:
                retries += 1
                logging.error(f"登录失败，第 {retries} 次尝试。错误: {e}")
                if self.log_callback:
                    self.log_callback(f"登录失败，第 {retries} 次尝试。错误: {e}")
                self.error_handler.handle_exception(e)
                time.sleep(self.retry_interval)

        logging.critical("多次登录失败，应用启动失败。")
        if self.log_callback:
            self.log_callback("多次登录失败，应用启动失败。")
        raise Exception("多次登录失败，应用启动失败。")

    def run(self):
        # 注册群组消息处理函数
        @itchat.msg_register([TEXT, SHARING], isGroupChat=True)
        def handle_group_messages(msg):
            self.message_handler.handle_group_message(msg)

        # 注册个人消息处理函数
        @itchat.msg_register([TEXT, SHARING], isGroupChat=False)
        def handle_individual_messages(msg):
            self.message_handler.handle_individual_message(msg)

        try:
            itchat.run()
        except Exception as e:
            logging.critical(f"ItChat 运行时发生致命错误: {e}")
            if self.log_callback:
                self.log_callback(f"ItChat 运行时发生致命错误: {e}")
            self.error_handler.handle_exception(e)

    def qr_callback(self, uuid, status, qrcode):
        """
        处理二维码回调。
        """
        logging.info(f"QR callback called with uuid: {uuid}, status: {status}")
        if status == '0':
            logging.info("QR code downloaded.")
            if self.log_callback:
                self.log_callback("QR code下载。")
            try:
                qr_image_data = qrcode
                # 保存二维码到文件
                with open(self.qr_path, 'wb') as f:
                    f.write(qr_image_data)
                logging.info(f"二维码已保存到 {self.qr_path}")
                if self.log_callback:
                    self.log_callback(f"二维码已保存到 {self.qr_path}")

                # 显示二维码
                image = Image.open(BytesIO(qr_image_data))
                image.show(title="微信登录二维码")

                # 将二维码图像数据发送到GUI队列
                if self.qr_queue:
                    self.qr_queue.put(qr_image_data)
            except Exception as e:
                logging.error(f"处理QR码时发生错误: {e}", exc_info=True)
                self.error_handler.handle_exception(e)
        elif status == '201':
            logging.info("二维码已扫描，请在手机上确认登录。")
            if self.log_callback:
                self.log_callback("二维码已扫描，请在手机上确认登录。")
        elif status == '200':
            logging.info("登录成功")
            if self.log_callback:
                self.log_callback("登录成功")
        else:
            logging.warning(f"未知的QR回调状态: {status}")
            if self.log_callback:
                self.log_callback(f"未知的QR回调状态: {status}")

    def logout(self):
        try:
            itchat.logout()
            logging.info("微信已退出")
            if self.log_callback:
                self.log_callback("微信已退出")
        except Exception as e:
            logging.error(f"退出微信时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

class MessageHandler:
    """
    消息处理器，用于处理微信消息，提取URL并调用 AutoClicker
    """

    def __init__(self, config, error_handler, monitor_groups, target_individuals, admins, notifier=None, browser_controller=None):
        self.regex = config.get('regex', r'https?://[^\s"」]+')
        self.validation = config.get('validation', True)
        self.auto_clicker = None
        self.error_handler = error_handler
        self.monitor_groups = monitor_groups
        self.target_individuals = target_individuals
        self.admins = admins  # 新增管理员列表
        self.uploader = None  # 初始化为 None
        self.notifier = notifier  # 添加 Notifier 实例
        self.browser_controller = browser_controller  # 添加浏览器控制器实例
        self.log_dir = config.get('logging', {}).get('directory', 'logs')  # 获取日志目录

    def set_auto_clicker(self, auto_clicker):
        self.auto_clicker = auto_clicker

    def set_uploader(self, uploader):
        """
        设置 Uploader 实例
        """
        self.uploader = uploader

    def handle_group_message(self, msg):
        """
        处理来自群组的消息
        """
        try:
            group_name = msg['User']['NickName']
            if group_name not in self.monitor_groups:
                logging.debug(f"消息来自非监控群组: {group_name}")
                return

            message_content = self.extract_message_content(msg)
            if not message_content:
                return

            urls = re.findall(self.regex, message_content)
            logging.info(f"识别到 URL: {urls}")

            valid_urls = self.process_urls(urls, is_group=True, recipient_name=group_name)

            # 将有效的 URL 添加到 AutoClicker 队列
            if self.auto_clicker and valid_urls:
                logging.debug(f"调用 AutoClicker 添加任务 URL: {valid_urls}")
                for url in valid_urls:
                    self.auto_clicker.add_task(url)
                    logging.info(f"任务已添加到下载任务队列: {url}")
            else:
                logging.warning("AutoClicker 未设置或没有有效的 URL，无法添加任务。")

        except Exception as e:
            logging.error(f"处理群组消息时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def handle_individual_message(self, msg):
        """
        处理来自个人的消息
        """
        try:
            sender = msg['User']['NickName']
            if sender not in self.target_individuals and sender not in self.admins:
                logging.debug(f"消息来自非监控个人: {sender}")
                return

            message_content = self.extract_message_content(msg)
            if not message_content:
                return

            # 如果发送者是管理员，检查是否为查询命令或其他管理员命令
            if sender in self.admins:
                if self.is_query_logs_command(message_content):
                    if self.notifier:
                        logs = self.get_last_n_logs(20)
                        if logs:
                            self.notifier.notify_long_message(f"最近 20 行日志:\n{logs}")
                        else:
                            self.notifier.notify("无法读取日志文件或日志文件为空。")
                    return  # 处理完命令后返回
                elif self.is_query_browser_command(message_content):
                    self.handle_query_browser_command()
                    return
                else:
                    # 处理其他管理员命令
                    response = self.handle_admin_command(message_content)
                    if response:
                        if self.notifier:
                            self.notifier.notify(response)
                    return

            # 对于非管理员的消息，处理URL
            if sender in self.target_individuals:
                urls = re.findall(self.regex, message_content)
                logging.info(f"识别到 URL: {urls}")

                valid_urls = self.process_urls(urls, is_group=False, recipient_name=sender)

                # 将有效的 URL 添加到 AutoClicker 队列
                if self.auto_clicker and valid_urls:
                    logging.debug(f"调用 AutoClicker 添加任务 URL: {valid_urls}")
                    for url in valid_urls:
                        self.auto_clicker.add_task(url)
                        logging.info(f"任务已添加到下载任务队列: {url}")
                else:
                    logging.warning("AutoClicker 未设置或没有有效的 URL，无法添加任务。")

        except Exception as e:
            logging.error(f"处理个人消息时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def handle_admin_command(self, message: str) -> Optional[str]:
        """
        处理管理员发送的命令
        :param message: 消息内容
        :return: 操作结果的反馈信息
        """
        try:
            # 使用正则表达式解析命令
            add_recipient_pattern = r'^添加接收者\s+(\S+)\s+(\d+)$'
            delete_recipient_pattern = r'^删除接收者\s+(\S+)$'
            update_remaining_pattern = r'^更新剩余次数\s+(\S+)\s+([+-]?\d+)$'
            query_recipient_pattern = r'^查询接收者\s+(\S+)$'
            get_all_recipients_pattern = r'^获取所有接收者$'
            help_pattern = r'^帮助$|^help$'  # 新增 help 命令的匹配模式

            if re.match(add_recipient_pattern, message):
                match = re.match(add_recipient_pattern, message)
                recipient_name = match.group(1)
                initial_count = int(match.group(2))
                response = self.uploader.add_recipient(recipient_name, initial_count)
                return response

            elif re.match(delete_recipient_pattern, message):
                match = re.match(delete_recipient_pattern, message)
                recipient_name = match.group(1)
                response = self.uploader.delete_recipient(recipient_name)
                return response

            elif re.match(update_remaining_pattern, message):
                match = re.match(update_remaining_pattern, message)
                recipient_name = match.group(1)
                count_change = int(match.group(2))
                response = self.uploader.update_remaining_count(recipient_name, count_change)
                return response

            elif re.match(query_recipient_pattern, message):
                match = re.match(query_recipient_pattern, message)
                recipient_name = match.group(1)
                info = self.uploader.get_recipient_info(recipient_name)
                if info:
                    return f"接收者 '{info['name']}' 的剩余次数为 {info['remaining_count']}。"
                else:
                    return f"接收者 '{recipient_name}' 不存在。"

            elif re.match(get_all_recipients_pattern, message):
                recipients = self.uploader.get_all_recipients()
                if recipients:
                    recipients_str = ', '.join(recipients)
                    return f"所有接收者列表：{recipients_str}"
                else:
                    return "当前没有任何接收者。"

            elif re.match(help_pattern, message):
                help_message = (
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
                    "   示例：帮助"
                )
                return help_message

            else:
                logging.warning(f"未知的管理员命令：{message}")
                return "未知的命令，请检查命令格式。"

        except Exception as e:
            logging.error(f"处理管理员命令时发生错误：{e}", exc_info=True)
            return f"处理命令时发生错误：{e}"

    def is_query_browser_command(self, message: str) -> bool:
        """
        判断消息是否为查询浏览器命令
        仅限于管理员发送
        """
        return message.strip().lower() in ['查询浏览器', 'query browser']

    def handle_query_browser_command(self):
        """
        处理查询浏览器命令，捕获截图并发送给管理员
        """
        if not self.browser_controller:
            logging.error("浏览器控制器未设置，无法处理查询浏览器命令。")
            if self.notifier:
                self.notifier.notify("无法处理查询浏览器命令，因为浏览器控制器未设置。", is_error=True)
            return

        logging.info("收到查询浏览器命令，开始捕获截图。")
        try:
            screenshot_paths = self.browser_controller.capture_all_tabs_screenshots()
            if screenshot_paths:
                self.notifier.notify_images(screenshot_paths)
                logging.info("浏览器标签页截图已发送给管理员。")

                # 删除临时截图文件
                for path in screenshot_paths:
                    try:
                        os.remove(path)
                        logging.debug(f"已删除临时截图文件: {path}")
                    except Exception as e:
                        logging.warning(f"无法删除临时截图文件 {path}: {e}")
            else:
                self.notifier.notify("无法捕获浏览器标签页的截图。", is_error=True)
        except Exception as e:
            logging.error(f"处理查询浏览器命令时发生错误: {e}", exc_info=True)
            if self.notifier:
                self.notifier.notify(f"处理查询浏览器命令时发生错误: {e}", is_error=True)


    def extract_message_content(self, msg):
        """
        提取消息内容
        """
        try:
            msg_type = msg['Type'] if 'Type' in msg else getattr(msg, 'type', '')
            logging.debug(f"消息类型: {msg_type}")

            if msg_type not in ['Text', 'Sharing']:
                logging.debug(f"忽略非文本或分享类型的消息: {msg_type}")
                return ''

            if msg_type == 'Text':
                return msg['Text'] if 'Text' in msg else getattr(msg, 'text', '')
            elif msg_type == 'Sharing':
                sharing_url = msg['Url'] if 'Url' in msg else getattr(msg, 'url', '')
                logging.debug(f"分享消息的 URL: {sharing_url}")
                return sharing_url

        except Exception as e:
            logging.error(f"提取消息内容时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return ''

    def process_urls(self, urls, is_group, recipient_name):
        """
        处理和验证 URLs
        """
        valid_urls = []
        for url in urls:
            clean_url = self.clean_url(url)
            logging.debug(f"清理后的 URL: {clean_url}")

            if self.validation and not self.validate_url(clean_url):
                logging.warning(f"URL 验证失败: {clean_url}")
                continue

            valid_urls.append(clean_url)

            # 从 URL 中提取 soft_id
            match = re.search(r'/soft/(\d+)\.html', clean_url)
            if match:
                soft_id = match.group(1)
                logging.info(f"从 URL 中提取到 soft_id: {soft_id}")

                # 将群组名称或发送者和 soft_id 传递给 Uploader
                if self.uploader:
                    self.uploader.upload_group_id(recipient_name, soft_id)
                    logging.info(f"上传信息到 Uploader: {recipient_name}, {soft_id}")
                else:
                    logging.warning("Uploader 未设置，无法上传接收者和 soft_id 信息。")
            else:
                logging.warning(f"无法从 URL 中提取 soft_id: {clean_url}")

        return valid_urls

    def clean_url(self, url):
        """
        清理 URL，移除锚点或其他不必要的部分
        """
        try:
            # 去除片段部分
            parsed = urlparse(url)
            clean = parsed._replace(fragment='')
            cleaned_url = urlunparse(clean)

            # 去除尾部非 URL 字符，如引号或特殊符号
            cleaned_url = cleaned_url.rstrip('」””"\'')  # 根据需要添加更多字符

            return cleaned_url
        except Exception as e:
            logging.error(f"清理 URL 时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return url  # 返回原始 URL

    def validate_url(self, url):
        """
        验证 URL 是否符合预期的格式或条件
        """
        return url.startswith('http://') or url.startswith('https://')

    def is_query_logs_command(self, message: str) -> bool:
        """
        判断消息是否为查询日志命令
        仅限于管理员发送
        """
        return message.strip().lower() in ['查询日志', 'query logs']

    def get_last_n_logs(self, n: int) -> Optional[str]:
        """
        获取日志目录下最新日志文件的最后 n 行
        """
        try:
            # 找到最新的日志文件
            log_files = [f for f in os.listdir(self.log_dir) if f.endswith('.log')]
            if not log_files:
                logging.warning("日志目录下没有日志文件。")
                return None

            # 假设日志文件以日期命名，找到最新的文件
            latest_log_file = max(log_files)
            log_path = os.path.join(self.log_dir, latest_log_file)

            # 读取最后 n 行
            with open(log_path, 'r', encoding='utf-8') as f:
                return ''.join(deque(f, n))
        except Exception as e:
            logging.error(f"读取日志文件时出错: {e}", exc_info=True)
            return None

def send_long_message(notifier, message: str, max_length: int = 2000):
    """
    分割长消息并逐段发送
    """
    try:
        for i in range(0, len(message), max_length):
            part = message[i:i + max_length]
            notifier.notify(part)
    except Exception as e:
        logging.error(f"发送长消息时出错: {e}", exc_info=True)