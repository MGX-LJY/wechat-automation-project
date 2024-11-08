# src/config/config_manager.py

import json
import logging
from pathlib import Path
from threading import Lock

class ConfigManager:
    CONFIG_PATH = Path(__file__).parent / 'config.json'
    _config = {}
    _lock = Lock()
    _callbacks = []

    @classmethod
    def load_config(cls):
        """加载配置文件"""
        try:
            with cls.CONFIG_PATH.open('r', encoding='utf-8') as f:
                cls._config = json.load(f)
            logging.info("配置文件加载成功")
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            raise e

    @classmethod
    def get_config(cls):
        """获取当前配置"""
        with cls._lock:
            return cls._config

    @classmethod
    def save_config(cls, config):
        """保存配置文件并触发回调"""
        try:
            with cls.CONFIG_PATH.open('w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            logging.info("配置文件保存成功")
            cls._config = config
            cls._trigger_callbacks()
        except Exception as e:
            logging.error(f"保存配置文件失败: {e}")
            raise e

    @classmethod
    def register_callback(cls, callback):
        """注册配置变化的回调函数"""
        with cls._lock:
            cls._callbacks.append(callback)

    @classmethod
    def _trigger_callbacks(cls):
        """触发所有注册的回调函数"""
        for callback in cls._callbacks:
            try:
                callback(cls._config)
            except Exception as e:
                logging.error(f"配置回调函数执行失败: {e}")
