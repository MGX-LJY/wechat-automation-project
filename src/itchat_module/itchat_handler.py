# src/itchat_module/itchat_module.py

import logging
import os
import time
import threading
import re
from urllib.parse import urlparse, urlunparse
from io import BytesIO
from PIL import Image
from lib import itchat
from lib.itchat.content import TEXT, ATTACHMENT

class ItChatHandler:
    def __init__(self, config, error_handler, log_callback=None, qr_queue=None):
        self.monitor_groups = config.get('monitor_groups', [])
        self.error_handler = error_handler
        self.message_callback = None
        self.qr_path = config.get('login_qr_path', 'qr.png')
        self.log_callback = log_callback
        self.max_retries = config.get('itchat', {}).get('qr_check', {}).get('max_retries', 5)
        self.retry_interval = config.get('itchat', {}).get('qr_check', {}).get('retry_interval', 2)
        self.qr_queue = qr_queue  # Queue to send QR code data to GUI
        self.login_event = threading.Event()

        # 初始化消息处理器
        self.message_handler = MessageHandler(config, error_handler, self.monitor_groups)
        self.message_handler.set_auto_clicker(None)  # 可以在外部设置 AutoClicker

    def set_message_callback(self, callback):
        self.message_callback = callback
        self.message_handler.set_auto_clicker(callback)  # 假设 callback 是 AutoClicker 实例

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
        # 注册文本和附件消息的处理函数
        @itchat.msg_register([TEXT, ATTACHMENT], isGroupChat=True)
        def handle_group_messages(msg):
            try:
                # 更新群组列表
                itchat.get_chatrooms(update=True)
                group_name = msg['User']['NickName']
                logging.debug(f"收到群组消息，群名: {group_name}")
                if group_name in self.monitor_groups:
                    logging.info(f"来自群组 {group_name} 的消息: {msg['Content']}")
                    if self.message_callback:
                        self.message_callback.handle_message(msg)
            except Exception as e:
                logging.error(f"处理群组消息时发生错误: {e}")
                if self.log_callback:
                    self.log_callback(f"处理群组消息时发生错误: {e}")
                self.error_handler.handle_exception(e)

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
                self.log_callback("QR code downloaded.")
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
    消息处理器，用于处理微信消息，提取URL并调用AutoClicker
    """

    def __init__(self, config, error_handler, monitor_groups):
        # 改进的正则表达式，排除尾部可能的引号或特殊字符
        self.regex = config.get('regex', r'https?://[^\s"」]+')
        self.validation = config.get('validation', True)
        self.auto_clicker = None
        self.error_handler = error_handler
        self.monitor_groups = monitor_groups

    def set_auto_clicker(self, auto_clicker):
        self.auto_clicker = auto_clicker

    def handle_message(self, msg):
        try:
            # 获取群组名称
            group_name = msg['User']['NickName'] if 'User' in msg else getattr(msg.user, 'NickName', '')
            if group_name not in self.monitor_groups:
                logging.debug(f"消息来自非监控群组: {group_name}")
                return

            # 获取消息类型
            msg_type = msg['Type'] if 'Type' in msg else getattr(msg, 'type', '')
            logging.debug(f"消息类型: {msg_type}")

            # 仅处理文本和分享消息，忽略其他类型
            if msg_type not in ['Text', 'Sharing']:
                logging.debug(f"忽略非文本或分享类型的消息: {msg_type}")
                return

            # 初始化消息内容
            message_content = ''

            # 根据消息类型获取内容
            if msg_type == 'Text':
                message_content = msg['Text'] if 'Text' in msg else getattr(msg, 'text', '')
            elif msg_type == 'Sharing':
                message_content = msg['Url'] if 'Url' in msg else getattr(msg, 'url', '')

            logging.debug(f"处理消息内容: {message_content}")

            # 确保 message_content 是字符串类型
            if not isinstance(message_content, str):
                message_content = str(message_content)

            # 使用正则表达式提取URL
            urls = re.findall(self.regex, message_content)
            logging.info(f"识别到URL: {urls}")

            # 处理和收集有效的URL
            valid_urls = []
            for url in urls:
                clean_url = self.clean_url(url)
                logging.debug(f"清理后的URL: {clean_url}")

                if self.validation and not self.validate_url(clean_url):
                    logging.warning(f"URL验证失败: {clean_url}")
                    continue

                valid_urls.append(clean_url)

            # 将有效的URL添加到AutoClicker队列
            if self.auto_clicker and valid_urls:
                logging.debug(f"调用自动点击模块添加URL: {valid_urls}")
                for url in valid_urls:
                    self.auto_clicker.add_task(url)

        except Exception as e:
            logging.error(f"处理消息时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def clean_url(self, url):
        """
        清理URL，去除片段部分和尾部的非URL字符
        """
        try:
            # 去除片段部分
            parsed = urlparse(url)
            clean = parsed._replace(fragment='')
            cleaned_url = urlunparse(clean)

            # 去除尾部非URL字符，如引号或特殊符号
            cleaned_url = cleaned_url.rstrip('」””"\'')  # 根据需要添加更多字符

            return cleaned_url
        except Exception as e:
            logging.error(f"清理URL时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return url  # 返回原始URL

    def validate_url(self, url):
        """
        简单的URL验证逻辑，可根据需求扩展
        """
        return url.startswith('http://') or url.startswith('https://')
