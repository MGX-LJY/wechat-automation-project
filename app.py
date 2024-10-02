# app.py

import logging  # 导入 logging 模块
import sys
import signal
import threading

from src.config.config_manager import ConfigManager
from src.itchat_module.itchat_handler import ItChatHandler
from src.message_handler import MessageHandler
from src.auto_click.auto_clicker import AutoClicker
from src.download_watcher import DownloadWatcher
from src.file_upload.uploader import Uploader
from src.logging_module.logger import setup_logging
from src.error_handling.error_handler import ErrorHandler
from src.notification.notifier import Notifier

def main():
    try:
        # 初始化日志
        setup_logging()
        logging.info("应用启动")

        # 加载配置
        config = ConfigManager.load_config('src/config.json')
        logging.info("配置文件加载成功")

        # 初始化通知模块
        notifier = Notifier(config['error_notification'])

        # 初始化错误处理
        error_handler = ErrorHandler(notifier)

        # 初始化各模块
        itchat_handler = ItChatHandler(config['wechat'], error_handler)
        # 先登录微信
        itchat_handler.login()

        # 初始化其他模块
        message_handler = MessageHandler(config['url'], error_handler)
        auto_clicker = AutoClicker(error_handler)
        uploader = Uploader(config['upload'], error_handler)

        # 初始化下载监控模块
        download_path = config['download'].get('download_path', '/Users/martinezdavid/Downloads')
        allowed_extensions = config['download'].get('allowed_extensions', ['.pdf', '.docx', '.xlsx'])
        download_watcher = DownloadWatcher(
            download_path,
            uploader.upload_file,
            allowed_extensions=allowed_extensions
        )

        # 绑定模块间关系
        itchat_handler.set_message_callback(message_handler.handle_message)
        message_handler.set_auto_clicker(auto_clicker)
        auto_clicker.set_download_watcher(download_watcher)

        # 启动下载监控
        watcher_thread = threading.Thread(target=download_watcher.start)
        watcher_thread.daemon = True
        watcher_thread.start()

        # 注册信号处理，确保程序退出时停止下载监控
        def signal_handler(sig, frame):
            logging.info('接收到退出信号，正在停止程序...')
            download_watcher.stop()
            sys.exit(0)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # 启动微信消息监听
        itchat_handler.run()
    except Exception as e:
        try:
            logging.critical(f"应用启动失败: {e}", exc_info=True)
        except NameError:
            # 如果 logging 未导入，则直接打印错误
            print(f"应用启动失败: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
