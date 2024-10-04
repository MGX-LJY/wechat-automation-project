import logging
import os
from logging.handlers import TimedRotatingFileHandler

class SimpleErrorFilter(logging.Filter):
    def filter(self, record):
        # 检测是否为特定网络异常，过滤掉这些日志
        if any(keyword in record.getMessage() for keyword in ['ProxyError', 'MaxRetryError', 'RemoteDisconnected']):
            return False  # 返回 False 表示过滤掉这条日志
        return True

def setup_logging():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file = os.path.join(log_dir, "app.log")

    # 使用 TimedRotatingFileHandler 实现每日日志轮转
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",      # 每天午夜进行轮转
        interval=1,           # 时间间隔为 1（单位由 when 参数决定）
        backupCount=7,        # 保留最近 7 天的日志，防止日志冗余
        encoding='utf-8'
    )
    file_handler.suffix = "%Y-%m-%d"  # 添加日期后缀，方便管理

    logging.basicConfig(
        level=logging.INFO,  # 设置全局日志级别为 INFO
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            file_handler,
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