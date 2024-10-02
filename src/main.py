# src/main.py

import os
import json
import logging
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox
from PIL import Image, ImageTk  # 确保 Pillow 已升级至 >=10.0.0
import queue
from io import BytesIO
from pathlib import Path
from lib import itchat
from lib.itchat.content import TEXT, ATTACHMENT

from download_watcher import DownloadWatcher
from logging.handlers import RotatingFileHandler

class ItChatHandler:
    def __init__(self, wechat_config, error_handler, log_callback, qr_queue):
        self.wechat_config = wechat_config
        self.error_handler = error_handler
        self.log_callback = log_callback
        self.qr_queue = qr_queue
        self.login_event = threading.Event()

    def login(self):
        try:
            logging.info("Ready to login.")
            self.log_callback("Ready to login.")
            itchat.auto_login(enableCmdQR=False, hotReload=True, qrCallback=self.qr_callback)
            logging.info("登录成功")
            self.log_callback("登录成功")
            self.login_event.set()
        except Exception as e:
            logging.error(f"登录微信时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def qr_callback(self, uuid, status, qrcode):
        if status == '0':
            # 正在生成二维码
            logging.info("Getting uuid of QR code.")
            self.log_callback("Getting uuid of QR code.")
        elif status == '1':
            # 二维码已下载
            logging.info("Downloading QR code.")
            self.log_callback("Downloading QR code.")
        elif status == '2':
            # 二维码已生成并保存
            logging.info("二维码已生成，准备保存到文件")
            self.log_callback("二维码已生成，准备保存到文件")
            # Decode base64 QR code
            try:
                qr_image_data = base64.b64decode(qrcode)
                with open(self.wechat_config.get('login_qr_path', 'qr.png'), 'wb') as f:
                    f.write(qr_image_data)
                logging.info("二维码已保存到文件")
                self.log_callback("二维码已保存到文件")
                # 将二维码图像数据发送到GUI队列
                self.qr_queue.put(qr_image_data)
            except Exception as e:
                logging.error(f"处理QR码时发生错误: {e}", exc_info=True)
                self.error_handler.handle_exception(e)

    def logout(self):
        try:
            itchat.logout()
            logging.info("微信已退出")
            self.log_callback("微信已退出")
        except Exception as e:
            logging.error(f"退出微信时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

class MessageHandler:
    def __init__(self, url_config, error_handler, monitor_groups):
        self.url_config = url_config
        self.error_handler = error_handler
        self.monitor_groups = monitor_groups  # 添加监控群组
        self.auto_clicker = None  # 将在后续设置

    def set_auto_clicker(self, auto_clicker):
        self.auto_clicker = auto_clicker

    def handle_message(self, msg):
        try:
            # 只处理来自监控群组的消息
            from_user = msg['FromUserName']
            chatroom = itchat.search_chatrooms(userName=from_user)
            if not chatroom:
                return
            group_name = chatroom.get('NickName', '')
            if group_name not in self.monitor_groups:
                return

            content = msg.get('Text', '')
            import re
            urls = re.findall(self.url_config.get('regex', r"https?://[^\s#]+"), content)
            logging.info(f"从消息中提取到的URL: {urls}")
            for url in urls:
                if self.url_config.get('validation', False):
                    # 在此添加URL验证逻辑
                    if self.validate_url(url):
                        if self.auto_clicker:
                            self.auto_clicker.open_url(url)
                else:
                    if self.auto_clicker:
                        self.auto_clicker.open_url(url)
        except Exception as e:
            logging.error(f"处理消息时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def validate_url(self, url):
        # 简单的URL验证示例，可以根据需要扩展
        return url.startswith("http")

class AutoClicker:
    def __init__(self, error_handler):
        self.error_handler = error_handler

    def open_url(self, url):
        try:
            import webbrowser
            webbrowser.open(url)
            logging.info(f"已打开URL: {url}")
        except Exception as e:
            logging.error(f"打开URL {url} 时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

class ErrorHandler:
    def __init__(self, notifier, log_callback):
        self.notifier = notifier
        self.log_callback = log_callback

    def handle_exception(self, exception):
        # 记录异常日志
        logging.error("捕捉到异常", exc_info=True)
        # 发送通知
        self.notifier.notify(f"系统异常: {str(exception)}")

class Notifier:
    def __init__(self, config):
        self.method = config.get('method', 'wechat')
        self.recipient = config.get('recipient', '')

    def notify(self, message):
        try:
            if self.method == 'wechat':
                if itchat.check_login():
                    itchat.send(message, toUserName=self.recipient)
                else:
                    logging.error("微信未登录，无法发送通知")
            elif self.method == 'email':
                # 可以扩展其他通知方式，如邮件
                pass
            else:
                logging.error(f"未知的通知方法: {self.method}")
        except Exception as e:
            logging.error(f"发送通知时发生错误: {e}", exc_info=True)

class WeChatApp:
    def __init__(self, root, config):
        logging.info("初始化 WeChatApp 类")
        self.root = root
        self.config = config
        self.root.title("WeChat Automation Project")
        self.root.geometry("800x700")

        # 创建队列用于接收二维码数据
        self.qr_queue = queue.Queue()

        # 设置日志区域
        self.log_area = scrolledtext.ScrolledText(
            self.root, state='disabled', height=20
        )
        self.log_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # 设置二维码显示区域
        self.qr_label = tk.Label(self.root)
        self.qr_label.pack(pady=10)

        # 设置按钮区域
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)

        self.login_button = tk.Button(
            button_frame, text="登录微信", command=self.login_wechat, width=15
        )
        self.login_button.pack(side=tk.LEFT, padx=5)

        self.logout_button = tk.Button(
            button_frame, text="退出微信", command=self.logout_wechat, width=15, state='disabled'
        )
        self.logout_button.pack(side=tk.LEFT, padx=5)

        # 初始化日志记录到GUI
        self.setup_logging()

        # 初始化组件
        self.notifier = Notifier(config.get('error_notification', {}))
        self.error_handler = ErrorHandler(self.notifier, self.log_message)
        self.itchat_handler = ItChatHandler(
            config['wechat'], self.error_handler, self.log_message, self.qr_queue
        )
        monitor_groups = config['wechat'].get('monitor_groups', [])
        self.message_handler = MessageHandler(
            config['url'], self.error_handler, monitor_groups
        )
        self.auto_clicker = AutoClicker(self.error_handler)  # 传递 error_handler 参数
        self.message_handler.set_auto_clicker(self.auto_clicker)

        # 注册消息处理回调
        itchat.msg_register(
            [itchat.content.TEXT, itchat.content.PICTURE, itchat.content.ATTACHMENT]
        )(self.message_handler.handle_message)

        # 初始化 DownloadWatcher 并设置到 upload_callback
        self.setup_download_watcher()

        logging.info("WeChatApp 实例化成功")

        # Start the QR code polling
        self.poll_qr_queue()

    def setup_logging(self):
        logging.info("设置日志系统")
        # 清空之前的日志处理器
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # 设置RotatingFileHandler
        log_file = self.config['logging'].get('file', 'logs/app.log')
        log_level = self.config['logging'].get('level', 'INFO').upper()
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        rotating_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8'
        )
        rotating_handler.setLevel(getattr(logging, log_level, logging.INFO))
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        rotating_handler.setFormatter(formatter)

        # 设置基本配置
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                rotating_handler,
                logging.StreamHandler()
            ]
        )

        # 添加自定义日志处理器以显示在GUI
        gui_handler = GuiLogHandler(self.log_message)
        logging.getLogger().addHandler(gui_handler)

        logging.info("日志系统初始化成功")
        logging.info("应用启动")
        self.log_message("日志系统初始化成功")
        self.log_message("应用启动")

    def setup_download_watcher(self):
        download_path = self.get_download_path()
        self.download_watcher = DownloadWatcher(
            download_path=download_path,
            upload_callback=self.upload_callback,
            allowed_extensions=self.config['download'].get('allowed_extensions'),
            temporary_extensions=self.config['download'].get('temporary_extensions'),
            stable_time=self.config['download'].get('stable_time', 5)
        )
        # 启动 DownloadWatcher 在独立的线程中
        threading.Thread(target=self.download_watcher.start, daemon=True).start()
        logging.info("DownloadWatcher 已启动并监控下载目录")

    @staticmethod
    def get_download_path():
        """
        获取用户的下载目录路径，支持Windows、macOS和Linux。
        """
        return str(Path.home() / "Downloads")

    def upload_callback(self, file_path):
        """
        处理下载完成的文件。
        直接调用 itchat 发送文件到微信群组。
        """
        logging.info(f"处理下载完成的文件: {file_path}")
        try:
            # 确保微信已经登录
            if not itchat.check_login():
                logging.error("微信未登录，无法上传文件")
                self.log_message("微信未登录，无法上传文件")
                return

            target_groups = self.config['upload'].get('target_groups', [])
            if not target_groups:
                logging.error("未配置目标群组，无法上传文件")
                self.log_message("未配置目标群组，无法上传文件")
                return

            for group_name in target_groups:
                chatrooms = itchat.search_chatrooms(name=group_name)
                if chatrooms:
                    chatroom = chatrooms[0]
                    itchat.send_file(file_path, toUserName=chatroom['UserName'])
                    logging.info(f"文件已发送到群组: {group_name}")
                    self.log_message(f"文件已发送到群组: {group_name}")
                else:
                    logging.error(f"未找到群组: {group_name}")
                    self.log_message(f"未找到群组: {group_name}")
        except Exception as e:
            logging.error(f"上传文件 {file_path} 时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def log_message(self, message):
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, message + '\n')
        self.log_area.configure(state='disabled')
        self.log_area.yview(tk.END)  # 自动滚动到最新日志

    def login_wechat(self):
        logging.info("用户点击登录微信")
        self.log_message("用户点击登录微信")
        # 禁用登录按钮，启用退出按钮
        self.login_button.config(state='disabled')
        self.logout_button.config(state='normal')

        # 启动ItChat登录过程在一个独立的线程中，以防止GUI冻结
        threading.Thread(target=self.itchat_handler.login, daemon=True).start()

    def logout_wechat(self):
        logging.info("用户点击退出微信")
        self.log_message("用户点击退出微信")
        # 调用ItChat的logout方法
        try:
            self.itchat_handler.logout()
        except Exception as e:
            logging.error(f"退出微信时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

        # 清除二维码显示
        self.qr_label.config(image='')
        self.qr_image = None  # 释放对图片的引用

        # 更新按钮状态
        self.login_button.config(state='normal')
        self.logout_button.config(state='disabled')

    def poll_qr_queue(self):
        """
        定期检查二维码队列并更新二维码显示
        """
        try:
            while not self.qr_queue.empty():
                qrcode_bytes = self.qr_queue.get_nowait()
                logging.debug("收到二维码数据，开始处理")
                # 转换为PIL Image
                qr_image = Image.open(BytesIO(qrcode_bytes))
                # 调整大小以适应GUI
                qr_image = qr_image.resize((300, 300), Image.LANCZOS)
                # 转换为ImageTk
                self.qr_image = ImageTk.PhotoImage(qr_image)
                # 更新Label
                self.qr_label.config(image=self.qr_image)
                logging.info("二维码已显示在GUI上")
        except Exception as e:
            logging.error(f"更新二维码时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

        # 每100毫秒检查一次队列
        self.root.after(100, self.poll_qr_queue)

    def on_closing(self):
        if messagebox.askokcancel("退出", "您确定要退出吗？"):
            try:
                self.itchat_handler.logout()
            except:
                pass
            self.root.destroy()

class GuiLogHandler(logging.Handler):
    def __init__(self, log_callback):
        super().__init__()
        self.log_callback = log_callback

    def emit(self, record):
        log_entry = self.format(record)
        self.log_callback(log_entry)

class WeChatAppWrapper:
    def __init__(self, root, config):
        self.app = WeChatApp(root, config)

def main():
    logging.info("启动主程序")
    # 加载配置文件
    config_path = 'config.json'
    if not os.path.exists(config_path):
        print(f"配置文件 {config_path} 不存在")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        logging.info("配置文件加载成功")

    # 初始化Tkinter主窗口
    root = tk.Tk()
    app_wrapper = WeChatAppWrapper(root, config)

    # 绑定窗口关闭事件
    root.protocol("WM_DELETE_WINDOW", app_wrapper.app.on_closing)

    # 运行Tkinter主循环
    root.mainloop()

if __name__ == "__main__":
    main()
