import json
import logging
from pathlib import Path

class ConfigManager:
    # 定义配置文件的固定路径
    CONFIG_PATH = Path(__file__).parent / 'config.json'

    @staticmethod
    def load_config():
        """加载固定路径的配置文件"""
        try:
            with open(ConfigManager.CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logging.info("配置文件加载成功")
            return config
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            raise e

    @staticmethod
    def save_config(config):
        """保存到固定路径的配置文件"""
        try:
            with open(ConfigManager.CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            logging.info("配置文件保存成功")
        except Exception as e:
            logging.error(f"保存配置文件失败: {e}")
            raise e