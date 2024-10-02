# tests/test_config_manager.py

import unittest
import os
import json
from src.config.config_manager import ConfigManager

class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.config_path = 'config.json'
        self.sample_config = {
            "wechat": {
                "monitor_groups": ["Group1", "Group2"]
            }
        }
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.sample_config, f)

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_load_config_success(self):
        config = ConfigManager.load_config(self.config_path)
        self.assertEqual(config, self.sample_config)

    def test_load_config_failure(self):
        with self.assertRaises(Exception):
            ConfigManager.load_config('non_existent_config.json')

if __name__ == '__main__':
    unittest.main()
