import asyncio
from playwright.async_api import async_playwright, Page, Download
import logging
import os
import sys
from src.config.config_manager import ConfigManager

# 动态添加项目根目录到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(level=logging.INFO, filename='auto_download.log',
                    format='%(asctime)s - %(levelname)s - %(message)s')


class PlaywrightAutoDownloader:
    def __init__(self, config_path='config.json'):
        # 加载配置
        self.config = ConfigManager.load_config(config_path)

        self.accounts = self.config['accounts']
        self.account_index = 0
        self.download_path = self.config['download']['download_path']

        # 确保下载路径存在
        os.makedirs(self.download_path, exist_ok=True)

        self.browser_type = self.config['download'].get('browser', 'chromium')
        self.headless = self.config['download'].get('headless', True)
        self.max_retries = self.config.get('max_retries', 3)
        self.page_close_delay = self.config.get('page_close_delay', 300)  # 5分钟
        self.error_handling_count = 0
        self.max_error_handling = self.config.get('max_error_handling', 5)
        self.allowed_extensions = self.config['download'].get('allowed_extensions', [])
        self.temporary_extensions = self.config['download'].get('temporary_extensions', [])
        self.stable_time = self.config['download'].get('stable_time', 5)  # 稳定时间（分钟）

    async def run(self, url):
        async with async_playwright() as p:
            browser = await self.launch_browser(p)
            try:
                context = await browser.new_context(
                    accept_downloads=True,
                    downloads_path=self.download_path  # 设置下载路径
                )
            except TypeError as e:
                logging.error(f"初始化浏览器上下文时出错: {e}")
                raise
            page = await context.new_page()
            await page.goto(url)
            await self.process_download(page)
            # 等待页面关闭的定时器
            asyncio.create_task(self.auto_close_page(page))
            await self.monitor_page(page)
            await browser.close()

    async def launch_browser(self, p):
        if self.browser_type == 'chromium':
            return await p.chromium.launch(headless=self.headless)
        elif self.browser_type == 'firefox':
            return await p.firefox.launch(headless=self.headless)
        elif self.browser_type == 'webkit':
            return await p.webkit.launch(headless=self.headless)
        else:
            logging.error(f"不支持的浏览器类型: {self.browser_type}")
            raise ValueError(f"不支持的浏览器类型: {self.browser_type}")

    async def process_download(self, page: Page):
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                download_button = await page.query_selector(self.config['selectors']['download_button'])
                if not download_button:
                    raise Exception("未找到下载按钮。")

                # 监听下载事件并点击下载按钮
                async with page.expect_download() as download_info:
                    await download_button.click()
                download: Download = await download_info.value

                # 获取下载的建议文件名
                suggested_filename = download.suggested_filename
                logging.info(f"开始下载文件: {suggested_filename}")

                # 验证文件扩展名
                _, ext = os.path.splitext(suggested_filename)
                if ext.lower() not in self.allowed_extensions:
                    logging.warning(f"不允许的文件类型: {ext}，下载将被取消。")
                    await download.cancel()
                    raise Exception(f"不允许的文件类型: {ext}")

                # 获取下载文件的路径
                download_file_path = await download.path()
                logging.info(f"文件已下载到: {download_file_path}")

                # 或者，您可以将文件保存到指定路径
                # target_path = os.path.join(self.download_path, suggested_filename)
                # await download.save_as(target_path)
                # logging.info(f"文件已保存到: {target_path}")

                # 如果下载成功，退出循环
                return
            except Exception as e:
                logging.error(f"下载过程出现异常: {e}")
                self.error_handling_count += 1
                if self.error_handling_count >= self.max_error_handling:
                    logging.error("已达到最大错误处理次数，切换账号。")
                    await self.switch_account(page)
                    self.error_handling_count = 0
                retry_count += 1
                logging.info(f"重试下载，当前重试次数: {retry_count}")
        logging.error("下载失败，超过最大重试次数。")

    async def handle_iframe_and_confirm(self, page: Page):
        IFRAME_SELECTOR = self.config['selectors']['iframe']
        CONFIRM_BUTTON_SELECTOR = self.config['selectors']['confirm_button']
        try:
            await page.wait_for_selector(IFRAME_SELECTOR, timeout=10000)
            iframe_element = await page.query_selector(IFRAME_SELECTOR)
            if iframe_element:
                iframe = await iframe_element.content_frame()
                if iframe:
                    confirm_button = await iframe.query_selector(CONFIRM_BUTTON_SELECTOR)
                    if confirm_button:
                        await confirm_button.click()
                        logging.info("点击确认按钮，下载启动。")
                        return True
            return False
        except Exception as e:
            logging.error(f"处理 iframe 出现异常: {e}")
            return False

    async def switch_account(self, page: Page):
        LOGOUT_BUTTON_SELECTOR = self.config['selectors']['logout_button']
        LOGIN_BUTTON_SELECTOR = self.config['selectors']['login_button']
        USERNAME_INPUT_SELECTOR = self.config['selectors']['username_input']
        PASSWORD_INPUT_SELECTOR = self.config['selectors']['password_input']
        LOGIN_SUBMIT_BUTTON_SELECTOR = self.config['selectors']['login_submit_button']

        # 点击退出按钮
        logout_button = await page.query_selector(LOGOUT_BUTTON_SELECTOR)
        if logout_button:
            await logout_button.click()
            logging.info("点击退出按钮。")
            await page.wait_for_timeout(2000)
        else:
            logging.warning("未找到退出按钮，可能已退出。")

        # 点击登录按钮
        login_button = await page.query_selector(LOGIN_BUTTON_SELECTOR)
        if login_button:
            await login_button.click()
            logging.info("点击登录按钮。")
            await page.wait_for_selector(USERNAME_INPUT_SELECTOR, timeout=10000)
        else:
            logging.error("未找到登录按钮。")
            return

        # 填写登录信息
        account = self.accounts[self.account_index]
        await page.fill(USERNAME_INPUT_SELECTOR, account['username'])
        await page.fill(PASSWORD_INPUT_SELECTOR, account['password'])
        await page.click(LOGIN_SUBMIT_BUTTON_SELECTOR)
        logging.info(f"使用账号 {account['username']} 尝试登录。")

        # 更新账号索引
        self.account_index = (self.account_index + 1) % len(self.accounts)

        # 等待登录完成
        await page.wait_for_timeout(5000)

    async def auto_close_page(self, page: Page):
        await asyncio.sleep(self.page_close_delay)
        logging.info("5分钟已到，自动关闭页面。")
        await page.close()

    async def monitor_page(self, page: Page):
        try:
            await page.wait_for_close()
            logging.info("页面已关闭。")
        except Exception as e:
            logging.error(f"监控页面时出现异常: {e}")

    def start(self, url):
        try:
            asyncio.run(self.run(url))
        except FileNotFoundError as e:
            logging.error(e)
            print(e)
            sys.exit(1)


# 使用示例
if __name__ == "__main__":
    downloader = PlaywrightAutoDownloader(config_path='config.json')
    target_url = 'https://www.zxxk.com/some-download-page'
    downloader.start(target_url)
