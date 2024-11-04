# src/logging_module.py
import logging
import os
from datetime import datetime, timedelta, timezone
from logging import Formatter, StreamHandler
import requests
from urllib3.exceptions import ProxyError as UrllibProxyError, MaxRetryError
from http.client import RemoteDisconnected


class ReplaceNetworkErrorFilter(logging.Filter):
    """
    日志过滤器，用于将与网络相关的错误日志消息替换为“网络问题”。
    """
    def filter(self, record):
        # 检查日志记录中是否包含异常信息
        if record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info
            # 检查是否是 ProxyError、MaxRetryError 或 RemoteDisconnected
            if isinstance(exc_value, (requests.exceptions.ProxyError,
                                      UrllibProxyError,
                                      MaxRetryError,
                                      RemoteDisconnected)):
                # 替换日志消息
                record.msg = '网络问题'
                # 保留 record.exc_info 以确保异常处理正常
        else:
            # 如果没有异常信息，检查消息中是否包含特定关键词
            if any(keyword in record.getMessage() for keyword in ['ProxyError', 'MaxRetryError', 'RemoteDisconnected']):
                record.msg = '网络问题'
        return True  # 继续处理所有日志记录


class DateBasedFileHandler(logging.Handler):
    def __init__(self, log_dir, backup_days=30, encoding='utf-8'):
        super().__init__()
        self.log_dir = log_dir
        self.backup_days = backup_days
        self.encoding = encoding
        os.makedirs(self.log_dir, exist_ok=True)
        self.current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')  # 使用时区感知的UTC时间
        self.log_file = os.path.join(self.log_dir, f"{self.current_date}.log")
        self.file_handler = logging.FileHandler(self.log_file, encoding=self.encoding)
        self.file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

        # 添加新的替换网络错误的过滤器
        self.replace_network_filter = ReplaceNetworkErrorFilter()
        self.file_handler.addFilter(self.replace_network_filter)

    def emit(self, record):
        new_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')  # 使用时区感知的UTC时间
        if new_date != self.current_date:
            self.file_handler.close()
            self.current_date = new_date
            self.log_file = os.path.join(self.log_dir, f"{self.current_date}.log")
            self.file_handler = logging.FileHandler(self.log_file, encoding=self.encoding)
            self.file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            self.file_handler.addFilter(self.replace_network_filter)
            self.cleanup_old_logs()
        self.file_handler.emit(record)

    def cleanup_old_logs(self):
        """删除超过backup_days天的日志文件"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.backup_days)
        for filename in os.listdir(self.log_dir):
            if filename.endswith('.log'):
                try:
                    date_str = filename.rstrip('.log')
                    file_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                    if file_date < cutoff_date:
                        os.remove(os.path.join(self.log_dir, filename))
                        logging.debug(f"删除旧日志文件: {filename}")
                except ValueError:
                    # 文件名不符合日期格式，跳过
                    logging.warning(f"跳过不符合日期格式的日志文件: {filename}")

    def setLevel(self, level):
        self.file_handler.setLevel(level)

    def setFormatter(self, fmt):
        self.file_handler.setFormatter(fmt)

    def close(self):
        self.file_handler.close()
        super().close()


def setup_logging(config: dict) -> logging.Logger:
    """
    初始化日志系统
    :param config: 配置字典，包含日志相关配置
    """
    log_dir = config.get('logging', {}).get('directory', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # 创建日志记录器
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.get('logging', {}).get('level', 'INFO').upper(), logging.INFO))

    # 日志格式
    formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 获取并确保 backup_count 是整数
    backup_count = config.get('logging', {}).get('backup_count', 30)
    if not isinstance(backup_count, int):
        try:
            backup_count = int(backup_count)
        except (ValueError, TypeError):
            logging.warning(f"Invalid backup_count '{backup_count}' in config. Using default value 30.")
            backup_count = 30  # 默认值

    # 获取并确保 encoding 是 str 或 None
    encoding = config.get('logging', {}).get('encoding', 'utf-8')
    if isinstance(encoding, str):
        if encoding.lower() == 'none':
            encoding = None
    else:
        logging.warning(f"Invalid encoding '{encoding}' in config. Using default 'utf-8'.")
        encoding = 'utf-8'

    # 文件处理器：DateBasedFileHandler 实现每天日志文件以日期命名，并保留最近30天的日志
    try:
        file_handler = DateBasedFileHandler(
            log_dir=log_dir,
            backup_days=backup_count,
            encoding=encoding
        )
    except Exception as e:
        logging.error(f"Failed to initialize DateBasedFileHandler: {e}")
        raise

    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, config.get('logging', {}).get('file_level', 'INFO').upper(), logging.INFO))
    logger.addHandler(file_handler)

    # 控制台处理器
    console_level = config.get('logging', {}).get('console_level', 'DEBUG').upper()
    console_level = getattr(logging, console_level, logging.DEBUG)
    console_handler = StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(console_level)

    # 添加新的替换网络错误的过滤器到控制台处理器
    replace_network_filter = ReplaceNetworkErrorFilter()
    console_handler.addFilter(replace_network_filter)

    logger.addHandler(console_handler)

    logging.info("日志系统初始化成功")

    # 设置第三方库的日志级别为 ERROR，减少详细日志输出
    third_party_libs = config.get('logging', {}).get('third_party_libs', ['requests', 'urllib3', 'itchat'])
    third_party_level = getattr(logging, config.get('logging', {}).get('third_party_libs_level', 'ERROR').upper(),
                                logging.ERROR)
    for lib in third_party_libs:
        logging.getLogger(lib).setLevel(third_party_level)

    return logger
