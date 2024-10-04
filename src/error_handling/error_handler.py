# src/error_handling/error_handler.py

import logging

class Notifier:
    def __init__(self, config):
        self.method = config.get('method', 'wechat')
        self.recipient = config.get('recipient', '')

    def notify(self, message):
        # 根据通知方式发送消息，这里以微信为例
        if self.method == 'wechat':
            self.send_wechat_message(self.recipient, message)
        else:
            logging.warning(f"未知的通知方法: {self.method}")

    def send_wechat_message(self, recipient, message):
        """
        实现微信消息发送逻辑
        """
        try:
            import itchat
            # 确保已登录
            if not itchat.check_login():
                logging.error("尚未登录微信，无法发送通知")
                return
            # 查找接收者的 UserName
            user = itchat.search_friends(name=recipient)
            if not user:
                user = itchat.search_chatrooms(name=recipient)
            if not user:
                logging.error(f"未找到接收者: {recipient}")
                # 增加日志列出所有好友和群聊名称
                friends = itchat.get_friends(update=True)
                logging.debug("好友列表:")
                for friend in friends:
                    logging.debug(f"好友: {friend['NickName']}")
                chatrooms = itchat.get_chatrooms(update=True)
                logging.debug("群聊列表:")
                for chatroom in chatrooms:
                    logging.debug(f"群聊: {chatroom['NickName']}")
                return
            user_name = user[0]['UserName']
            itchat.send(message, toUserName=user_name)
            logging.info(f"已发送通知消息给 {recipient}")
        except Exception as e:
            logging.error("发送通知消息时发生错误")

class ErrorHandler:
    def __init__(self, notifier, log_callback=None):
        self.notifier = notifier
        self.log_callback = log_callback

    def handle_exception(self, exception=None):
        # 仅记录简短的错误信息
        logging.error("网络异常")
        if self.log_callback:
            self.log_callback("网络异常")
        self.notifier.notify("网络异常")
