# src/error_handling/error_handler.py

import logging
import traceback
from typing import Optional
from src.notification.notifier import Notifier


class ErrorHandler:
    """
    错误处理器，用于捕获和处理应用中的异常。
    通过记录日志和发送通知来报告错误。
    """

    def __init__(self, notifier: Notifier, log_callback: Optional[callable] = None, notify_on_exception: bool = True):
        """
        初始化 ErrorHandler。

        :param notifier: 用于发送错误通知的 Notifier 实例。
        :param log_callback: 可选的回调函数，用于在错误发生时执行额外的日志操作。
        :param notify_on_exception: 是否在捕获到异常时发送通知。
        """
        self.notifier = notifier
        self.log_callback = log_callback
        self.notify_on_exception = notify_on_exception

    def handle_exception(self, exception: Optional[Exception] = None):
        """
        处理捕获到的异常。记录错误日志，并根据配置发送通知。

        :param exception: 捕获到的异常对象。如果为 None，则记录一个通用错误信息。
        """
        if exception:
            exception_type = type(exception).__name__
            exception_message = str(exception)
            logging.error(f"异常发生: {exception_type}: {exception_message}")

            if self.log_callback:
                self.log_callback(f"异常发生: {exception_type}: {exception_message}")

            if self.notify_on_exception:
                # 发送简短的错误通知
                notification_message = f"异常发生: {exception_type}: {exception_message}"
                success = self.notifier.notify(notification_message)
                if not success:
                    logging.warning("发送异常通知失败。")

                # 发送详细的异常信息
                self.send_exception_details(exception)
        else:
            # 未捕获到具体异常，记录通用错误信息
            logging.error("发生未知错误。")
            if self.log_callback:
                self.log_callback("发生未知错误。")
            if self.notify_on_exception:
                success = self.notifier.notify("发生未知错误。")
                if not success:
                    logging.warning("发送未知错误通知失败。")

    def send_exception_details(self, exception: Exception):
        """
        发送详细的异常信息，用于调试和排查问题。

        :param exception: 捕获到的异常对象。
        """
        exception_details = ''.join(traceback.format_exception(None, exception, exception.__traceback__))
        logging.error(f"详细异常信息:\n{exception_details}")

        if self.notify_on_exception:
            try:
                detailed_message = f"详细异常信息:\n{exception_details}"
                # 如果异常信息过长，分段发送以避免消息过长导致发送失败
                max_length = 2000  # 根据 Notifier 的限制调整
                for i in range(0, len(detailed_message), max_length):
                    segment = detailed_message[i:i + max_length]
                    success = self.notifier.notify(segment)
                    if not success:
                        logging.warning("发送详细异常信息的通知失败。")
            except Exception as e:
                logging.error(f"发送详细异常信息时发生错误: {e}", exc_info=True)

    def log_and_handle_exception(self, func):
        """
        装饰器，用于包装函数，自动捕获和处理异常。

        :param func: 被包装的函数。
        :return: 包装后的函数。
        """

        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.handle_exception(e)
                # 根据需要，可以选择重新抛出异常或返回特定值
                # 这里选择不重新抛出，以防止程序崩溃

        return wrapper
