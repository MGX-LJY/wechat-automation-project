# src/notification/notifier.py

import logging
from typing import Optional, List
from lib import itchat

class WeChatNotifier:
    def __init__(self, recipient: str):
        """
        初始化 WeChatNotifier

        :param recipient: 接收者的微信昵称或微信ID
        """
        if not recipient:
            logging.error("WeChatNotifier 初始化时未提供接收者")
            raise ValueError("接收者不能为空")

        self.recipient = recipient
        self.user_name = None  # 延迟查找接收者

    def _find_recipient(self):
        """
        查找接收者的 UserName
        """
        try:
            # 尝试通过微信ID查找
            user = itchat.search_friends(userName=self.recipient)
            if user:
                self.user_name = user['UserName']
                logging.debug(f"通过微信ID找到接收者: {self.recipient}")
                return

            # 尝试通过昵称查找
            users = itchat.search_friends(name=self.recipient)
            if users:
                self.user_name = users[0]['UserName']
                logging.debug(f"通过昵称找到接收者: {self.recipient}")
                return

            # 尝试在群聊中查找
            groups = itchat.search_chatrooms(name=self.recipient)
            if groups:
                self.user_name = groups[0]['UserName']
                logging.debug(f"通过群聊昵称找到接收者: {self.recipient}")
                return

            # 如果未找到接收者，记录错误并列出所有好友和群聊
            logging.error(f"未找到接收者: {self.recipient}")
            self._log_available_contacts()
        except Exception as e:
            logging.error(f"查找接收者时发生错误: {e}", exc_info=True)

    def _log_available_contacts(self):
        """
        记录所有好友和群聊的名称，帮助调试
        """
        try:
            friends = itchat.get_friends(update=True)
            logging.debug("好友列表:")
            for friend in friends:
                logging.debug(f"好友: {friend['NickName']} (ID: {friend['UserName']})")

            chatrooms = itchat.get_chatrooms(update=True)
            logging.debug("群聊列表:")
            for chatroom in chatrooms:
                logging.debug(f"群聊: {chatroom['NickName']} (ID: {chatroom['UserName']})")
        except Exception as e:
            logging.error(f"记录可用联系人时发生错误: {e}", exc_info=True)

    def send_message(self, message: str) -> bool:
        """
        发送消息给接收者

        :param message: 要发送的消息内容
        :return: 发送是否成功
        """
        if not self.user_name:
            self._find_recipient()
            if not self.user_name:
                logging.error(f"无法发送消息，因为未找到接收者: {self.recipient}")
                return False

        try:
            itchat.send_msg(msg=message, toUserName=self.user_name)
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
        if not self.user_name:
            self._find_recipient()
            if not self.user_name:
                logging.error(f"无法发送图片，因为未找到接收者: {self.recipient}")
                return False

        try:
            itchat.send_image(image_path, toUserName=self.user_name)
            logging.info(f"已发送图片给 {self.recipient}: {image_path}")
            return True
        except Exception as e:
            logging.error(f"发送图片给 {self.recipient} 时发生错误: {e}", exc_info=True)
            return False

    def send_images(self, image_paths: List[str]) -> bool:
        """
        发送多张图片给接收者

        :param image_paths: 图片文件的路径列表
        :return: 是否全部发送成功
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

        :param config: 配置字典，包含 'method' 和 'recipient'
        """
        self.method = config.get('method', 'wechat').lower()
        self.recipient = config.get('recipient', '')
        self.error_recipient = config.get('error_recipient', '')  # 新增 error_recipient
        self.wechat_notifier: Optional[WeChatNotifier] = None
        self.wechat_error_notifier: Optional[WeChatNotifier] = None  # 用于错误通知

        if self.method == 'wechat':
            if not self.recipient:
                logging.error("微信通知的接收者未配置")
                raise ValueError("微信通知的接收者未配置")
            self.wechat_notifier = WeChatNotifier(self.recipient)
            if self.error_recipient:
                self.wechat_error_notifier = WeChatNotifier(self.error_recipient)
        else:
            logging.warning(f"未知的通知方法: {self.method}")

    def notify(self, message: str, is_error: bool = False) -> bool:
        """
        发送通知

        :param message: 要发送的消息内容
        :param is_error: 是否为错误通知
        :return: 发送是否成功
        """
        if self.method == 'wechat':
            notifier = self.wechat_error_notifier if is_error else self.wechat_notifier
            if notifier is None:
                # 如果未配置错误通知接收者，使用默认接收者
                notifier = self.wechat_notifier
                logging.warning("未配置错误通知接收者，使用默认接收者发送错误通知")
            if notifier:
                return notifier.send_message(message)
            else:
                logging.warning("未配置对应的 WeChatNotifier 实例")
                return False
        else:
            logging.warning(f"无法发送通知，未知的通知方法: {self.method}")
            return False

    def notify_long_message(self, message: str, max_length: int = 2000) -> bool:
        """
        分割长消息并逐段发送

        :param message: 要发送的长消息内容
        :param max_length: 每段消息的最大长度
        :return: 发送是否全部成功
        """
        try:
            for i in range(0, len(message), max_length):
                part = message[i:i + max_length]
                success = self.notify(part)  # 确保调用的是 self.notify(part)
                if not success:
                    logging.error("发送部分长消息时失败")
                    return False
            return True
        except Exception as e:
            logging.error(f"发送长消息时发生错误: {e}", exc_info=True)
            return False

    def notify_images(self, image_paths: List[str], is_error: bool = False) -> bool:
        """
        发送图片通知

        :param image_paths: 图片文件的路径列表
        :param is_error: 是否为错误通知
        :return: 发送是否成功
        """
        if self.method == 'wechat':
            notifier = self.wechat_error_notifier if is_error else self.wechat_notifier
            if notifier:
                return notifier.send_images(image_paths)
            else:
                logging.warning("未配置对应的 WeChatNotifier 实例")
                return False
        else:
            logging.warning(f"无法发送通知，未知的通知方法: {self.method}")
            return False
