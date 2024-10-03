# test_auto_clicker.py

import logging
import time
from src.auto_click.auto_clicker import AutoClicker
from src.error_handling.error_handler import ErrorHandler
from src.notification.notifier import Notifier

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# 创建 Notifier 实例（假设您有一个 Notifier 类）
notifier = Notifier({
    "method": "console"  # 这里使用控制台通知，便于测试
})

# 创建 ErrorHandler 实例
error_handler = ErrorHandler(notifier)

# 创建 AutoClicker 实例
auto_clicker = AutoClicker(error_handler)

# 添加测试URL
test_urls = [
    "https://www.example.com/page1",
    "https://www.example.com/page2",
    "https://www.example.com/page3",
    "https://www.example.com/page4",
    "https://www.example.com/page5",
    "https://www.example.com/page6",
    "https://www.example.com/page7",
    "https://www.example.com/page8",
    "https://www.example.com/page9",
]

auto_clicker.add_urls(test_urls)

# 主线程保持运行，等待处理完成
try:
    while auto_clicker.processing:
        time.sleep(1)
    logging.info("测试完成，程序退出")
except KeyboardInterrupt:
    logging.info("手动终止测试")
