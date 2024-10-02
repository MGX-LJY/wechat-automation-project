# src/browser_automation/download_automation.py

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import logging
import time
import os

class DownloadAutomation:
    def __init__(self, config, error_handler):
        self.browser = config.get('browser', 'chrome').lower()
        self.download_path = config.get('download_path', './downloads')
        self.script_path = config.get('auto_download_script', 'scripts/auto_download_script.py')
        self.error_handler = error_handler
        self.driver = None
        self.uploader = None  # Reference to Uploader
        self.setup_browser()

    def setup_browser(self):
        try:
            # 确保下载目录存在
            os.makedirs(self.download_path, exist_ok=True)

            chrome_options = Options()
            prefs = {
                "download.default_directory": os.path.abspath(self.download_path),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            }
            chrome_options.add_experimental_option("prefs", prefs)
            chrome_options.add_argument("--headless")  # 无头模式，可根据需求调整
            self.driver = webdriver.Chrome(options=chrome_options)
            logging.info("浏览器自动下载模块初始化成功")
        except Exception as e:
            self.error_handler.handle_exception(e)

    def set_uploader(self, uploader):
        self.uploader = uploader

    def start_download(self, url):
        try:
            logging.info(f"开始下载: {url}")
            self.driver.get(url)
            # 等待下载完成，可以根据具体情况调整等待时间
            time.sleep(10)
            logging.info(f"下载完成: {url}")

            # 查找下载的文件并上传
            downloaded_file = self.get_latest_file()
            if downloaded_file and self.uploader:
                self.uploader.upload_file(downloaded_file)
        except Exception as e:
            self.error_handler.handle_exception(e)

    def get_latest_file(self):
        try:
            files = os.listdir(self.download_path)
            files = [os.path.join(self.download_path, f) for f in files]
            files = [f for f in files if os.path.isfile(f)]
            if not files:
                logging.warning("下载目录为空")
                return None
            latest_file = max(files, key=os.path.getmtime)
            logging.info(f"最新下载文件: {latest_file}")
            return latest_file
        except Exception as e:
            self.error_handler.handle_exception(e)
            return None

    def close(self):
        if self.driver:
            self.driver.quit()
            logging.info("浏览器已关闭")
