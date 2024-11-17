# src/main.py

import logging
import signal
import sys
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.auto_download.auto_download import AutoDownloadManager
from src.config.config_manager import ConfigManager
from src.error_handling.error_handler import ErrorHandler
from src.file_upload.uploader import Uploader
from src.itchat_module.itchat_handler import ItChatHandler
from src.logging_module.logger import setup_logging
from src.notification.notifier import Notifier
from src.point_manager import PointManager


class ConfigChangeHandler(FileSystemEventHandler):
    def __init__(self, on_change_callback):
        super().__init__()
        self.on_change_callback = on_change_callback

    def on_modified(self, event):
        if Path(event.src_path).resolve() == ConfigManager.CONFIG_PATH.resolve():
            logging.info("检测到配置文件修改，重新加载配置")
            try:
                new_config = ConfigManager.load_config()
                self.on_change_callback(new_config)
            except Exception as e:
                logging.error(f"重新加载配置失败: {e}")


def main():
    try:
        # 1. 加载主配置文件（无需传递路径参数）
        main_config = ConfigManager.load_config()

        # 2. 设置日志
        setup_logging(main_config)
        logging.info("配置文件加载成功，日志已配置")

        # 3. 初始化通知模块
        notifier_config = main_config.get('error_notification', {})
        notifier = Notifier(notifier_config)
        logging.info("Notifier 初始化完成")

        # 4. 初始化错误处理
        error_handler = ErrorHandler(notifier)
        logging.info("ErrorHandler 初始化完成")

        # 5. 获取上传和下载的配置
        upload_config = main_config.get('upload', {})
        upload_error_notification_config = main_config.get('upload_error_notification', {})

        # 6. 初始化 PointManager
        point_manager = PointManager()
        logging.info("PointManager 初始化完成")

        # 7. 创建 Uploader 实例
        uploader = Uploader(
            upload_config=upload_config,
            error_notification_config=upload_error_notification_config,
            error_handler=error_handler,
            point_manager=point_manager
        )
        logging.info("Uploader 初始化完成")

        # 8. 初始化 AutoDownloadManager 并启动浏览器实例
        download_config = main_config.get('download', {})
        download_path = download_config.get(
            'download_path',
            Path(__file__).parent.parent / 'auto_download/Downloads'
        )
        auto_download_manager = AutoDownloadManager(
            uploader=uploader,
            notifier_config=notifier_config
        )
        logging.info("AutoDownloadManager 初始化完成")

        # 9. 初始化 ItChatHandler
        itchat_handler = ItChatHandler(
            error_handler=error_handler,
            notifier=notifier,
            browser_controller=auto_download_manager,
            point_manager=point_manager,
        )
        logging.info("ItChatHandler 初始化完成")

        # 10. 绑定 Uploader 到 ItChatHandler
        itchat_handler.set_uploader(uploader)
        logging.info("Uploader 已绑定到 ItChatHandler")

        # 11. 登录微信
        itchat_handler.login()
        logging.info("微信登录完成")

        # 12. 启动微信消息监听线程
        itchat_thread = threading.Thread(target=itchat_handler.run, daemon=True)
        itchat_thread.start()
        logging.info("微信消息监听线程已启动")

        # 13. 注册信号处理，确保程序退出时停止下载监控和登出微信
        def signal_handler(sig, frame):
            logging.info('接收到退出信号，正在停止程序...')
            itchat_handler.logout()
            uploader.stop()  # 停止 Uploader 的上传线程
            auto_download_manager.stop()  # 停止下载管理器
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # 14. 设置配置文件监控
        def on_config_change(new_config):
            logging.info("处理配置变化")
            # 更新日志配置
            setup_logging(new_config)

            # 更新 Uploader 配置
            uploader.update_config(new_config.get('upload', {}))

            # 更新 ItChatHandler 的配置
            itchat_handler.update_config(new_config)

            logging.info("配置变化已应用")

        event_handler = ConfigChangeHandler(on_config_change)
        observer = Observer()
        observer.schedule(event_handler, path=str(ConfigManager.CONFIG_PATH.parent), recursive=False)
        observer.start()
        logging.info("配置文件监控已启动")

        # 15. 主线程等待子线程
        itchat_thread.join()

    except Exception as e:
        try:
            logging.critical(f"应用启动失败: {e}", exc_info=True)
        except NameError:
            # 如果 logging 未导入，则直接打印错误
            print(f"应用启动失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
