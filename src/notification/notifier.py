# src/notification/notifier.py

import logging
import itchat

class Notifier:
    def __init__(self, config):
        self.method = config.get('method')
        self.recipient_name = config.get('recipient')

    def send_notification(self, subject, message):
        if self.method == 'wechat':
            self.send_wechat(subject, message)
        else:
            logging.warning(f"未知的通知方法: {self.method}")

    def send_wechat(self, subject, message):
        try:
            # 确保已登录
            if not itchat.get_friends():
                logging.error("未登录微信，无法发送通知")
                return

            # 搜索好友
            friends = itchat.search_friends(name=self.recipient_name)
            if friends:
                userName = friends[0]['UserName']
                full_message = f"{subject}\n\n{message}"
                itchat.send(full_message, toUserName=userName)
                logging.info(f"微信通知已发送给 {self.recipient_name}")
            else:
                logging.error(f"未找到微信用户: {self.recipient_name}")
        except Exception as e:
            logging.error(f"发送微信通知失败: {e}")
