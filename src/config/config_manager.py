import json
import logging
import os


class ConfigManager:
    @staticmethod
    def load_config(config_path='config.json'):
        # 获取当前文件的目录（即 src/config/）
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 假设 config.json 位于项目根目录，向上跳转两级
        project_root = os.path.abspath(os.path.join(current_dir, '../../'))
        config_full_path = os.path.join(project_root, config_path)

        logging.info(f"Loading config from: {config_full_path}")
        print(f"Loading config from: {config_full_path}")  # 添加打印用于调试

        try:
            with open(config_full_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logging.info(f"配置文件加载成功: {config_full_path}")
            return config
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            raise FileNotFoundError(f"配置文件未找到或无法加载: {config_full_path}") from e
