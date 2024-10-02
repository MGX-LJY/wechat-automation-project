# src/message_handler.py

import re
import logging
from urllib.parse import urlparse, urlunparse

class MessageHandler:
    def __init__(self, config, error_handler):
        self.regex = config.get('regex', r'https?://[^\s#]+')  # 修改后的正则表达式
        self.validation = config.get('validation', True)
        self.auto_clicker = None
        self.error_handler = error_handler

    def set_auto_clicker(self, auto_clicker):
        self.auto_clicker = auto_clicker

    def handle_message(self, msg):
        try:
            message_content = msg.get('Content', '')
            logging.debug(f"处理消息内容: {message_content}")
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
            logging.error(f"处理消息时发生错误: {e}")
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
            logging.error(f"清理URL时发生错误: {e}")
            self.error_handler.handle_exception(e)
            return url  # 返回原始URL，尽管它可能包含片段

    def validate_url(self, url):
        """
        简单的URL验证逻辑，可根据需求扩展
        """
        return url.startswith('http://') or url.startswith('https://')
