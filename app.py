# src/main.py

import logging
import signal
import sys
import threading
from pathlib import Path
from src.auto_download.auto_download import XKW
from src.config.config_manager import ConfigManager
from src.error_handling.error_handler import ErrorHandler
from src.file_upload.uploader import Uploader
from src.itchat_module.itchat_handler import ItChatHandler
from src.logging_module.logger import setup_logging
from src.notification.notifier import Notifier
from src.point_manager import PointManager  # 新增导入

def main():
    try:
        # 1. 加载主配置文件
        main_config = ConfigManager.load_config('config.json')

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

        # 5. 从主配置中获取 upload 和 download 的配置
        upload_config = main_config.get('upload', {})
        upload_error_notification_config = main_config.get('upload_error_notification', {})

        # 6. 初始化 PointManager
        point_manager = PointManager()
        logging.info("PointManager 初始化完成")

        # 7. 创建 Uploader 实例，传递 PointManager
        uploader = Uploader(upload_config, upload_error_notification_config, error_handler, point_manager=point_manager)
        logging.info("Uploader 初始化完成")

        # 8. 初始化 XKW（浏览器控制器）并使用相对路径
        download_config = main_config.get('download', {})
        download_path = download_config.get(
            'download_path',
            Path(__file__).parent.parent / 'auto_download/Downloads'
        )
        xkw = XKW(thread=5, work=True, download_dir=str(download_path), uploader=uploader)
        logging.info("XKW 初始化完成")

        # 9. 初始化 ItChatHandler，并传递 Notifier 和管理员列表
        wechat_config = main_config.get('wechat', {})
        admins = wechat_config.get('admins', [])  # 获取管理员列表

        itchat_handler = ItChatHandler(
            config=wechat_config,
            error_handler=error_handler,
            notifier=notifier,
            browser_controller=xkw,
            point_manager=point_manager,
        )
        logging.info("ItChatHandler 初始化完成")

        # 10. 绑定 Uploader 和 AutoClicker 到 ItChatHandler
        itchat_handler.set_uploader(uploader)
        itchat_handler.set_auto_clicker(xkw)
        logging.info("Uploader 和 AutoClicker 已绑定到 ItChatHandler")

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
            xkw.work = False  # 停止 XKW 的运行循环
            itchat_handler.logout()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # 14. 主线程等待子线程
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
