# src/message_handler.py

import re
import logging
from urllib.parse import urlparse, urlunparse

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
                self.auto_clicker.add_urls(valid_urls)

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
