# main_gui.py

import os
import json
import logging
import logging.handlers  # 添加此行，导入 logging.handlers 模块
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox
from PIL import Image, ImageTk
import queue
from io import BytesIO
from pathlib import Path

from src.config.config_manager import ConfigManager
from src.itchat_module.itchat_handler import ItChatHandler
from src.message_handler import MessageHandler
from src.auto_click.auto_clicker import AutoClicker
from src.download_watcher import DownloadWatcher
from src.file_upload.uploader import Uploader
from src.error_handling.error_handler import ErrorHandler
from src.notification.notifier import Notifier
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
        self.auto_clicker = AutoClicker(self.error_handler)
        self.message_handler.set_auto_clicker(self.auto_clicker)
        self.uploader = Uploader(config['upload'], self.error_handler)

        # 绑定模块间关系
        self.itchat_handler.set_message_callback(self.message_handler.handle_message)

        # 初始化 DownloadWatcher
        self.setup_download_watcher()

        logging.info("WeChatApp 实例化成功")

        # 开始轮询二维码队列
        self.poll_qr_queue()

    def setup_logging(self):
        logging.info("设置日志系统")
        # 清空之前的日志处理器
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # 设置 RotatingFileHandler
        log_file = self.config['logging'].get('file', 'logs/app.log')
        log_level = self.config['logging'].get('level', 'INFO').upper()
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        rotating_handler = logging.handlers.RotatingFileHandler(  # 使用 logging.handlers
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
        download_path = self.config['download'].get('download_path', self.get_download_path())
        allowed_extensions = self.config['download'].get('allowed_extensions', ['.pdf', '.docx', '.xlsx'])
        self.download_watcher = DownloadWatcher(
            download_path=download_path,
            upload_callback=self.uploader.upload_file,
            allowed_extensions=allowed_extensions,
            stable_time=self.config['download'].get('stable_time', 5)
        )
        # 启动 DownloadWatcher 在独立的线程中
        threading.Thread(target=self.download_watcher.start, daemon=True).start()
        logging.info("DownloadWatcher 已启动并监控下载目录")

    @staticmethod
    def get_download_path():
        """
        获取用户的下载目录路径，支持 Windows、macOS 和 Linux。
        """
        return str(Path.home() / "Downloads")

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

        # 启动 WeChat 登录过程在一个独立的线程中，以防止 GUI 冻结
        threading.Thread(target=self.itchat_handler.login, daemon=True).start()

    def logout_wechat(self):
        logging.info("用户点击退出微信")
        self.log_message("用户点击退出微信")
        # 调用 ItChat 的 logout 方法
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
                # 转换为 PIL Image
                qr_image = Image.open(BytesIO(qrcode_bytes))
                # 调整大小以适应 GUI
                qr_image = qr_image.resize((300, 300), Image.LANCZOS)
                # 转换为 ImageTk
                self.qr_image = ImageTk.PhotoImage(qr_image)
                # 更新 Label
                self.qr_label.config(image=self.qr_image)
                logging.info("二维码已显示在 GUI 上")
                self.log_message("二维码已显示在 GUI 上")
        except Exception as e:
            logging.error(f"更新二维码时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

        # 每 100 毫秒检查一次队列
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

def main():
    # 加载配置文件
    config_path = 'config.json'
    if not os.path.exists(config_path):
        print(f"配置文件 {config_path} 不存在")
        return

    config = ConfigManager.load_config(config_path)

    # 初始化 Tkinter 主窗口
    root = tk.Tk()
    app = WeChatApp(root, config)

    # 绑定窗口关闭事件
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    # 运行 Tkinter 主循环
    root.mainloop()

if __name__ == "__main__":
    main()
