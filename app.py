import json
import logging
import sys
import signal
import threading

from src.auto_click.auto_clicker import AutoClicker
from src.config.config_manager import ConfigManager
from src.itchat_module.itchat_handler import ItChatHandler, MessageHandler
from src.auto_download.auto_download import XKW  # 导入 XKW 类
from src.file_upload.uploader import Uploader
from src.logging_module.logger import setup_logging
from src.error_handling.error_handler import ErrorHandler
from src.notification.notifier import Notifier

def main():
    try:
        # 加载主配置文件
        main_config = ConfigManager.load_config('config.json')
        logging.info("配置文件加载成功")

        # 更新日志配置（如果 setup_logging 需要）
        setup_logging(main_config)
        logging.info("应用启动")

        # 初始化通知模块
        notifier_config = main_config.get('error_notification', {})
        notifier = Notifier(notifier_config)

        # 初始化错误处理
        error_handler = ErrorHandler(notifier)

        # 初始化 ItChatHandler
        itchat_handler = ItChatHandler(main_config['wechat'], error_handler)

        # 读取 counts.json 配置文件（使用不同的变量名以避免覆盖主配置）
        with open('counts.json', 'r', encoding='utf-8') as f:
            counts_config = json.load(f)
        logging.info("counts.json 配置文件加载成功")

        # 从 counts_config 中获取 upload 配置
        upload_config = counts_config.get('upload', {})
        error_notification_config = counts_config.get('error_notification', {})

        # 创建 Uploader 实例，确保传递所有必要参数
        uploader = Uploader(upload_config, error_notification_config, error_handler)
        logging.info("Uploader 初始化完成")

        # 初始化 XKW，传递 uploader
        download_path = counts_config.get('download', {}).get('download_path', '/Users/martinezdavid/Documents/MG/work/zxxkdownload')
        xkw = XKW(thread=3, work=True, download_dir=download_path, uploader=uploader)
        logging.info("XKW 初始化完成")

        # 绑定 XKW 到 ItChatHandler（通过 MessageHandler）
        itchat_handler.set_auto_clicker(xkw)
        logging.info("ItChatHandler 初始化完成并绑定 XKW")

        # 初始化自动点击器
        auto_clicker = AutoClicker(error_handler)

        # 获取监控的群组列表
        monitor_groups = main_config['wechat'].get('monitor_groups', [])

        # 初始化消息处理器，并传递 monitor_groups
        message_handler = MessageHandler(main_config.get('url', {}), error_handler, monitor_groups)
        logging.info("消息处理器初始化完成并绑定自动点击器")
        message_handler.set_auto_clicker(auto_clicker)

        # 设置 Uploader 到 ItChatHandler 和 XKW
        itchat_handler.set_uploader(uploader)
        xkw.uploader = uploader
        logging.info("Uploader 已绑定到 ItChatHandler 和 XKW")

        # 登录微信
        itchat_handler.login()

        # 启动微信消息监听线程
        itchat_thread = threading.Thread(target=itchat_handler.run, daemon=True)
        itchat_thread.start()
        logging.info("微信消息监听线程已启动")

        # 注册信号处理，确保程序退出时停止下载监控
        def signal_handler(sig, frame):
            logging.info('接收到退出信号，正在停止程序...')
            xkw.work = False  # 停止 XKW 的运行循环
            itchat_handler.logout()
            uploader.shutdown()  # 关闭 Uploader
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # 主线程等待子线程
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
