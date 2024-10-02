# src/config/config_manager.py

import json
import logging

class ConfigManager:
    @staticmethod
    def load_config(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logging.info("配置文件加载成功")
            return config
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            raise
