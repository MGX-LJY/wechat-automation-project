# src/itchat_module/itchat_handler.py

import logging
import os
from lib import itchat
from lib.itchat.content import TEXT, ATTACHMENT
import time
import queue
from PIL import Image
from io import BytesIO


class ItChatHandler:
    def __init__(self, config, error_handler, log_callback=None, qr_queue=None):
        self.monitor_groups = config.get('monitor_groups', [])
        self.error_handler = error_handler
        self.message_callback = None
        self.qr_path = config.get('login_qr_path', 'qr.png')
        self.log_callback = log_callback
        self.max_retries = config.get('itchat', {}).get('qr_check', {}).get('max_retries', 5)
        self.retry_interval = config.get('itchat', {}).get('qr_check', {}).get('retry_interval', 2)
        self.qr_queue = qr_queue  # Queue to send QR code data to GUI

    def set_message_callback(self, callback):
        self.message_callback = callback

    def login(self):
        retries = 0
        while retries < self.max_retries:
            try:
                # 删除旧的会话文件
                session_file = 'itchat.pkl'
                if os.path.exists(session_file):
                    os.remove(session_file)
                    logging.info(f"已删除旧的会话文件: {session_file}")
                    if self.log_callback:
                        self.log_callback(f"已删除旧的会话文件: {session_file}")

                itchat.auto_login(
                    hotReload=False,  # 禁用 Hot Reload
                    enableCmdQR=False,
                    qrCallback=self.save_qr
                )
                logging.info("微信登录成功")
                if self.log_callback:
                    self.log_callback("微信登录成功")
                return  # 登录成功，退出方法
            except Exception as e:
                retries += 1
                logging.error(f"登录失败，第 {retries} 次尝试。错误: {e}")
                if self.log_callback:
                    self.log_callback(f"登录失败，第 {retries} 次尝试。错误: {e}")
                self.error_handler.handle_exception(e)
                time.sleep(self.retry_interval)

        logging.critical("多次登录失败，应用启动失败。")
        if self.log_callback:
            self.log_callback("多次登录失败，应用启动失败。")
        raise Exception("多次登录失败，应用启动失败。")

    def run(self):
        # 注册文本和附件消息的处理函数
        @itchat.msg_register([TEXT, ATTACHMENT], isGroupChat=True)
        def handle_group_messages(msg):
            try:
                group_name = msg['User']['NickName']
                logging.debug(f"收到群组消息，群名: {group_name}")
                if group_name in self.monitor_groups:
                    logging.info(f"来自群组 {group_name} 的消息: {msg['Content']}")
                    if self.message_callback:
                        self.message_callback(msg)
            except Exception as e:
                logging.error(f"处理群组消息时发生错误: {e}")
                if self.log_callback:
                    self.log_callback(f"处理群组消息时发生错误: {e}")
                self.error_handler.handle_exception(e)

        try:
            itchat.run()
        except Exception as e:
            logging.critical(f"ItChat 运行时发生致命错误: {e}")
            if self.log_callback:
                self.log_callback(f"ItChat 运行时发生致命错误: {e}")
            self.error_handler.handle_exception(e)

    def save_qr(self, uuid=None, status='0', qrcode=None):
        """
        保存二维码到指定路径，并在首次登录时显示二维码。
        """
        if qrcode:
            try:
                # 保存二维码图片到指定路径
                with open(self.qr_path, 'wb') as f:
                    f.write(qrcode)
                logging.info(f"二维码已保存到 {self.qr_path}")
                if self.log_callback:
                    self.log_callback(f"二维码已保存到 {self.qr_path}")

                # 将二维码图片数据放入队列以供GUI显示
                if self.qr_queue:
                    self.qr_queue.put(qrcode)

            except Exception as e:
                logging.error(f"保存二维码时发生错误: {e}")
                self.error_handler.handle_exception(e)
