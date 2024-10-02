# tests/test_logger.py

import unittest
import os
import json
from src.logging_module.logger import setup_logging
import logging

class TestLogger(unittest.TestCase):
    def setUp(self):
        self.config_path = 'config.json'
        # 创建一个临时配置文件
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump({
                "logging": {
                    "level": "DEBUG",
                    "file": "logs/test_app.log"
                }
            }, f)

    def tearDown(self):
        # 删除临时日志文件和配置文件
        if os.path.exists('logs/test_app.log'):
            os.remove('logs/test_app.log')
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_setup_logging(self):
        setup_logging(self.config_path)
        logging.debug("这是一个调试日志")
        logging.info("这是一个信息日志")

        with open('logs/test_app.log', 'r', encoding='utf-8') as f:
            logs = f.read()
            self.assertIn("这是一个调试日志", logs)
            self.assertIn("这是一个信息日志", logs)

if __name__ == '__main__':
    unittest.main()
