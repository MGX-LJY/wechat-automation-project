# src/notification/notifier.py

import logging
from typing import Optional, List
from lib.wxautox.wxauto import WeChat

class WeChatNotifier:
    """
    用于发送通知的类，支持微信通知。
    """
    def __init__(self, recipient: str):
        """
        初始化 WeChatNotifier

        :param recipient: 接收者的微信昵称或微信ID
        """
        if not recipient:
            logging.error("WeChatNotifier 初始化时未提供接收者")
            raise ValueError("接收者不能为空")

        self.recipient = recipient
        self.wx = WeChat()

    def send_message(self, message: str) -> bool:
        """
        发送消息给接收者

        :param message: 要发送的消息内容
        :return: 发送是否成功
        """
        try:
            # 发送消息
            self.wx.SendMsg(msg=message, who=self.recipient)
            logging.info(f"已发送通知消息给 {self.recipient}")
            return True
        except Exception as e:
            logging.error(f"发送消息给 {self.recipient} 时发生错误: {e}", exc_info=True)
            return False

    def send_image(self, image_path: str) -> bool:
        """
        发送图片给接收者

        :param image_path: 图片文件的路径
        :return: 发送是否成功
        """
        try:
            # 发送图片
            self.wx.SendFiles(filepath=image_path, who=self.recipient)
            logging.info(f"已发送图片给 {self.recipient}: {image_path}")
            return True
        except Exception as e:
            logging.error(f"发送图片给 {self.recipient} 时发生错误: {e}", exc_info=True)
            return False

    def send_images(self, image_paths: List[str]) -> bool:
        """
        发送多张图片给接收者

        :param image_paths: 图片文件的路径列表
        :return: 发送是否成功
        """
        success = True
        for image_path in image_paths:
            if not self.send_image(image_path):
                success = False
        return success


class Notifier:
    def __init__(self, config: dict):
        """
        初始化 Notifier

        :param config: 配置字典，包含 'method' 和 'admins'
        """
        wechat_config = config.get('wechat', {})
        self.method = wechat_config.get('method', 'wechat').lower()
        self.admins = wechat_config.get('admins', [])

        self.wechat_notifiers: List[WeChatNotifier] = []

        if self.method == 'wechat':
            if not self.admins:
                logging.error("微信通知的管理员列表未配置")
                raise ValueError("微信通知的管理员列表未配置")

            # 创建 WeChatNotifier 实例列表
            for admin in self.admins:
                notifier = WeChatNotifier(admin)
                self.wechat_notifiers.append(notifier)
        else:
            logging.warning(f"未知的通知方法: {self.method}")

    def notify(self, message: str, is_error: bool = False) -> bool:
        """
        发送通知

        :param message: 要发送的消息内容
        :param is_error: 是否为错误通知（此版本所有通知均发送给管理员）
        :return: 发送是否成功
        """
        if self.method == 'wechat':
            success = True
            for notifier in self.wechat_notifiers:
                if not notifier.send_message(message):
                    success = False
            return success
        else:
            logging.warning(f"无法发送通知，未知的通知方法: {self.method}")
            return False

    def notify_long_message(self, message: str, max_length: int = 2000, is_error: bool = False) -> bool:
        """
        分割长消息并逐段发送

        :param message: 要发送的长消息内容
        :param max_length: 每段消息的最大长度
        :param is_error: 是否为错误通知
        :return: 发送是否全部成功
        """
        try:
            success = True
            for i in range(0, len(message), max_length):
                part = message[i:i + max_length]
                part_success = self.notify(part, is_error=is_error)
                if not part_success:
                    logging.error("发送部分长消息时失败")
                    success = False
            return success
        except Exception as e:
            logging.error(f"发送长消息时发生错误: {e}", exc_info=True)
            return False

    def notify_images(self, image_paths: List[str], is_error: bool = False) -> bool:
        """
        发送图片通知

        :param image_paths: 图片文件的路径列表
        :param is_error: 是否为错误通知（此版本所有通知均发送给管理员）
        :return: 发送是否成功
        """
        if self.method == 'wechat':
            success = True
            for notifier in self.wechat_notifiers:
                if not notifier.send_images(image_paths):
                    success = False
            return success
        else:
            logging.warning(f"无法发送通知，未知的通知方法: {self.method}")
            return False
