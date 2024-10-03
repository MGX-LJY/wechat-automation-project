# message_handler.py

import re
import logging
from urllib.parse import urlparse, urlunparse

class MessageHandler:
    def __init__(self, config, error_handler, monitor_groups):
        self.regex = config.get('regex', r'https?://[^\s#]+')
        self.validation = config.get('validation', True)
        self.auto_clicker = None
        self.error_handler = error_handler
        self.monitor_groups = monitor_groups

    def set_auto_clicker(self, auto_clicker):
        self.auto_clicker = auto_clicker

    def handle_message(self, msg):
        try:
            # 获取群组名称
            group_name = msg['User']['NickName'] if 'User' in msg else msg.user.nickName
            if group_name not in self.monitor_groups:
                return

            # 获取消息类型
            msg_type = msg['Type'] if 'Type' in msg else msg.type
            logging.debug(f"消息类型: {msg_type}")

            # 初始化消息内容
            message_content = ''

            # 根据消息类型获取内容
            if msg_type == 'Text':
                message_content = msg['Text'] if 'Text' in msg else msg.text
            elif msg_type == 'Sharing':
                message_content = msg['Url'] if 'Url' in msg else msg.url
            elif msg_type in ['Attachment', 'Video', 'Picture', 'Recording']:
                # 处理可能是函数的情况
                text_attr = msg['Text'] if 'Text' in msg else msg.text
                if callable(text_attr):
                    message_content = text_attr()
                else:
                    message_content = text_attr
            else:
                # 处理其他类型的消息
                content_attr = msg.get('Content', '') if 'Content' in msg else getattr(msg, 'content', '')
                if callable(content_attr):
                    message_content = content_attr()
                else:
                    message_content = content_attr

            logging.debug(f"处理消息内容: {message_content}")

            # 确保 message_content 是字符串类型
            if not isinstance(message_content, str):
                message_content = str(message_content)

            # 使用正则表达式提取URL
            urls = re.findall(self.regex, message_content)
            logging.info(f"识别到URL: {urls}")

            for url in urls:
                clean_url = self.clean_url(url)
                logging.debug(f"清理后的URL: {clean_url}")

                if self.validation and not self.validate_url(clean_url):
                    logging.warning(f"URL验证失败: {clean_url}")
                    continue

                if self.auto_clicker:
                    logging.debug(f"调用自动点击模块打开URL: {clean_url}")
                    self.auto_clicker.open_url(clean_url)

        except Exception as e:
            logging.error(f"处理消息时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def clean_url(self, url):
        """
        清理URL，去除片段部分
        """
        try:
            parsed = urlparse(url)
            clean = parsed._replace(fragment='')
            return urlunparse(clean)
        except Exception as e:
            logging.error(f"清理URL时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return url  # 返回原始URL

    def validate_url(self, url):
        """
        简单的URL验证逻辑，可根据需求扩展
        """
        return url.startswith('http://') or url.startswith('https://')
