# src/error_handling/error_handler.py

import logging
import traceback
from src.notification.notifier import Notifier

class ErrorHandler:
    def __init__(self, notifier: Notifier, log_callback=None):
        self.notifier = notifier
        self.log_callback = log_callback

    def handle_exception(self, exception=None):
        # 仅记录简短的错误信息
        logging.error("网络异常")
        if self.log_callback:
            self.log_callback("网络异常")
        self.notifier.notify("网络异常")
        if exception:
            self.send_exception_details(exception)

    def send_exception_details(self, exception):
        # 记录详细的异常信息
        exception_details = ''.join(traceback.format_exception(None, exception, exception.__traceback__))
        logging.error(f"详细异常信息: {exception_details}")
        self.notifier.notify(f"详细异常信息: {exception_details}")
