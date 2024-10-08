# src/notification/notifier.py

import logging
import itchat

class Notifier:
    def __init__(self, config):
        self.method = config.get('method', 'wechat')
        self.recipient = config.get('recipient', '')

    def notify(self, message):
        if self.method == 'wechat':
            self.send_wechat(message)
        else:
            logging.warning(f"未知的通知方法: {self.method}")

    def send_wechat(self, message):
        try:
            # 确保已登录
            if not itchat.check_login():
                logging.error("尚未登录微信，无法发送通知")
                return

            # 查找接收者的 UserName
            user = itchat.search_friends(name=self.recipient)
            if not user:
                user = itchat.search_chatrooms(name=self.recipient)
            if not user:
                logging.error(f"未找到接收者: {self.recipient}")
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
            logging.info(f"已发送通知消息给 {self.recipient}")
        except Exception as e:
            logging.error(f"发送通知消息时发生错误: {e}")
