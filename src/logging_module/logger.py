# src/logging_module/logger.py

import logging
import os

class SimpleErrorFilter(logging.Filter):
    def filter(self, record):
        # 检测是否为特定异常
        if 'ProxyError' in record.getMessage():
            record.msg = "网络异常"
            record.args = ()
        return True

def setup_logging():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file = os.path.join(log_dir, "app.log")

    logging.basicConfig(
        level=logging.INFO,  # 设置全局日志级别为 INFO
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.info("日志系统初始化成功")

    # 设置第三方库的日志级别为 ERROR，减少详细日志输出
    logging.getLogger('requests').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('itchat').setLevel(logging.ERROR)

    # 添加自定义过滤器到根记录器
    logging.getLogger().addFilter(SimpleErrorFilter())
