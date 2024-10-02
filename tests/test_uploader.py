# tests/test_uploader.py

import unittest
import os
from unittest.mock import MagicMock
from src.file_upload.uploader import Uploader

class TestUploader(unittest.TestCase):
    def setUp(self):
        self.config = {
            "target_groups": ["🐠【学虎】课件下载"]
        }
        self.error_handler = MagicMock()
        self.uploader = Uploader(self.config, self.error_handler)

    def test_upload_file_nonexistent(self):
        with self.assertLogs(level='WARNING') as log:
            self.uploader.upload_file("nonexistent_file.txt")
            self.assertIn("文件不存在: nonexistent_file.txt", log.output[0])

    def test_upload_file_success(self):
        # 创建一个临时文件
        temp_file = "temp_test_file.txt"
        with open(temp_file, 'w') as f:
            f.write("Test content")

        # Mock itchat.send_file
        import itchat
        itchat.send_file = MagicMock()

        self.uploader.upload_file(temp_file)
        itchat.send_file.assert_called_with(temp_file, toUserName="🐠【学虎】课件下载")

        # 删除临时文件
        os.remove(temp_file)

if __name__ == '__main__':
    unittest.main()
