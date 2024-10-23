# app.py

import logging
import sys
import signal
import threading

from src.config.config_manager import ConfigManager
from src.itchat_module.itchat_handler import ItChatHandler
from src.auto_download.auto_download import XKW  # 导入 XKW 类
from src.file_upload.uploader import Uploader
from src.logging_module.logger import setup_logging
from src.error_handling.error_handler import ErrorHandler
from src.notification.notifier import Notifier


def main():
    try:
        # 加载配置
        config = ConfigManager.load_config('config.json')
        logging.info("配置文件加载成功")

        # 初始化日志
        setup_logging(config)
        logging.info("日志系统初始化成功")
        logging.info("应用启动")

        # 初始化通知模块
        notifier_config = config.get('error_notification', {})
        notifier = Notifier(notifier_config)

        # 初始化错误处理
        error_handler = ErrorHandler(notifier)

        # 初始化 ItChatHandler
        itchat_handler = ItChatHandler(config['wechat'], error_handler)

        # 初始化 XKW（自动下载模块），暂时不传递 uploader
        download_path = config['download'].get('download_path', '/Users/martinezdavid/Documents/MG/work/zxxkdownload')
        xkw = XKW(thread=3, work=True, download_dir=download_path)

        # 绑定 XKW 到 ItChatHandler（通过 MessageHandler）
        itchat_handler.set_auto_clicker(xkw)
        logging.info("ItChatHandler 初始化完成并绑定 XKW")

        # 登录微信
        itchat_handler.login()

        # 登录成功后，再初始化 Uploader
        uploader = Uploader(config['upload'], config['error_notification'], error_handler)

        # 设置 Uploader 到 ItChatHandler 和 XKW
        itchat_handler.set_uploader(uploader)
        xkw.uploader = uploader
        logging.info("Uploader 已绑定到 ItChatHandler 和 XKW")

        # 启动微信消息监听线程
        itchat_thread = threading.Thread(target=itchat_handler.run, daemon=True)
        itchat_thread.start()

        # 注册信号处理，确保程序退出时停止下载监控
        def signal_handler(sig, frame):
            logging.info('接收到退出信号，正在停止程序...')
            xkw.work = False  # 停止 XKW 的运行循环
            itchat_handler.logout()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # 主线程保持运行
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
