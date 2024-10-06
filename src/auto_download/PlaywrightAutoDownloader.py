import asyncio
from playwright.async_api import async_playwright, Page, Download
import logging
import os
import sys
import time

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
        self.headless = self.config['download'].get('headless', False)  # 设置为 False 以启用可视化
        self.max_retries = self.config.get('max_retries', 3)
        self.page_close_delay = self.config.get('page_close_delay', 300)  # 5分钟
        self.script_timeout = self.config.get('script_timeout', 20)  # 20秒
        self.error_check_interval = self.config.get('error_check_interval', 10)  # 10秒
        self.max_error_handling = self.config.get('max_error_handling', 5)
        self.allowed_extensions = self.config['download'].get('allowed_extensions', [])
        self.temporary_extensions = self.config['download'].get('temporary_extensions', [])
        self.stable_time = self.config['download'].get('stable_time', 5)  # 稳定时间（分钟）

        self.error_handling_count = 0
        self.state = {
            'errorCount': 0,
            'downloadStarted': False,
            'accountIndex': 0,
            'refreshTimeout': None,
            'closeTimeout': None,
            'errorCheckInterval': None,
        }

    async def run(self, url):
        async with async_playwright() as p:
            browser = await self.launch_browser(p)
            try:
                context = await browser.new_context(
                    accept_downloads=True
                )
            except TypeError as e:
                logging.error(f"初始化浏览器上下文时出错: {e}")
                raise

            page = await context.new_page()
            await page.goto(url)
            await page.wait_for_load_state('networkidle')  # 等待页面加载完成

            # 开启20秒的脚本超时计时
            asyncio.create_task(self.script_timeout_handler(page))

            # 开启5分钟自动关闭计时
            asyncio.create_task(self.auto_close_page(page))

            # 开启错误检查定时器
            self.state['errorCheckInterval'] = asyncio.create_task(self.handle_error_periodically(page))

            await self.process_download(page)
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

    async def script_timeout_handler(self, page: Page):
        await asyncio.sleep(self.script_timeout)
        if not self.state['downloadStarted']:
            logging.info('脚本未能在20秒内正常运行，刷新页面。')
            await page.reload()

    async def auto_close_page(self, page: Page):
        await asyncio.sleep(self.page_close_delay)
        logging.info("5分钟已到，自动关闭页面。")
        await page.close()

    async def handle_error_periodically(self, page: Page):
        while not self.state['downloadStarted']:
            await asyncio.sleep(self.error_check_interval)
            await self.handle_error(page)

    async def monitor_page(self, page: Page):
        try:
            await page.wait_for_close()
            logging.info("页面已关闭。")
        except Exception as e:
            logging.error(f"监控页面时出现异常: {e}")

    async def process_download(self, page: Page, retry=0):
        if self.state['downloadStarted']:
            return

        try:
            # 等待并选择可见的下载按钮
            await page.wait_for_selector(self.config['selectors']['download_button'], timeout=20000)
            download_buttons = page.locator(self.config['selectors']['download_button']).filter(state="visible")

            if download_buttons.count() == 0:
                # 尝试在 iframe 内查找
                iframe_selector = self.config['selectors'].get('iframe')
                if iframe_selector:
                    iframe_element = await page.query_selector(iframe_selector)
                    if iframe_element:
                        iframe = await iframe_element.content_frame()
                        if iframe:
                            download_buttons = iframe.locator(self.config['selectors']['download_button']).filter(state="visible")
                            if download_buttons.count() > 0:
                                download_button = download_buttons.first()
                                await download_button.scroll_into_view_if_needed()  # 滚动到可见区域
                                await download_button.click()

                                # 监听下载事件
                                async with iframe.expect_download() as download_info:
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

                                # 保存文件到指定路径
                                target_path = os.path.join(self.download_path, suggested_filename)
                                await download.save_as(target_path)
                                logging.info(f"文件已保存到: {target_path}")

                                # 下载成功，更新状态
                                self.state['downloadStarted'] = True
                                # 停止其他任务
                                if self.state['refreshTimeout']:
                                    self.state['refreshTimeout'].cancel()
                                if self.state['errorCheckInterval']:
                                    self.state['errorCheckInterval'].cancel()

                                # 关闭页面
                                asyncio.create_task(self.auto_close_page(page))
                                return
            raise Exception("未找到可见的下载按钮。")

        except Exception as e:
            logging.error(f"下载过程出现异常: {e}")
            # 截图当前页面以便调试
            screenshot_path = os.path.join(self.download_path, f"screenshot_{int(time.time())}.png")
            await page.screenshot(path=screenshot_path)
            logging.info(f"已保存页面截图: {screenshot_path}")

            self.error_handling_count += 1
            if self.error_handling_count >= self.max_error_handling:
                logging.error("已达到最大错误处理次数，切换账号。")
                await self.switch_account(page)
                self.error_handling_count = 0
            elif retry < self.max_retries:
                logging.info(f"重试下载，当前重试次数: {retry + 1}")
                await asyncio.sleep(self.config['click_interval'] / 1000)  # 转换为秒
                await self.process_download(page, retry + 1)
            else:
                logging.error("下载失败，超过最大重试次数。")

    async def handle_error(self, page: Page):
        if self.state['downloadStarted']:
            return

        try:
            # 处理限制对话框
            limit_dialog = page.locator(self.config['selectors']['limitDialog'])
            if await limit_dialog.is_visible():
                limit_confirm = limit_dialog.locator(self.config['selectors']['limitConfirmBtn'])
                if await limit_confirm.is_visible():
                    await self.click_button(page, limit_confirm, '下载次数上限提示框确认按钮')
                    await self.switch_account(page)
                return

            # 处理错误提示框
            error_boxes = page.locator(self.config['selectors']['errorBox'])
            for i in range(await error_boxes.count()):
                box = error_boxes.nth(i)
                if await box.is_visible():
                    close_btn = box.locator(self.config['selectors']['errorCloseBtn'])
                    if await close_btn.is_visible():
                        await self.click_button(page, close_btn, '错误提示框关闭按钮')
                        self.state['errorCount'] += 1
                        logging.info('已关闭错误提示框。')

            if self.state['errorCount'] < self.max_error_handling:
                logging.info('尝试重新下载。')
                await self.process_download(page)
            else:
                logging.info('达到最大错误处理次数，停止操作。')
                # 这里可以选择进一步的操作，如发送通知等
        except Exception as e:
            logging.error(f"处理错误提示框时出现异常: {e}")

    async def click_button(self, page: Page, button, button_type: str):
        try:
            await button.scroll_into_view_if_needed()
            await button.click()
            logging.info(f"{button_type}已点击。")
        except Exception as e:
            logging.error(f"点击{button_type}时出错: {e}")

    async def switch_account(self, page: Page):
        logging.info('切换账号。')

        # 点击退出按钮
        logout_btn = page.locator(self.config['selectors']['logoutBtn'])
        if await logout_btn.is_visible():
            await self.click_button(page, logout_btn, '退出按钮')
            await asyncio.sleep(self.config['click_interval'] / 1000)  # 转换为秒
        else:
            logging.warning('未找到退出按钮，可能已退出。')

        # 点击登录按钮
        login_btn = page.locator(self.config['selectors']['loginBtn'])
        if await login_btn.is_visible():
            await self.click_button(page, login_btn, '登录按钮')
            await page.wait_for_selector(self.config['selectors']['username'], timeout=10000)
        else:
            logging.error('未找到登录按钮。')
            return

        # 填写登录信息
        account = self.accounts[self.account_index]
        username_input = page.locator(self.config['selectors']['username'])
        password_input = page.locator(self.config['selectors']['password'])
        login_submit = page.locator(self.config['selectors']['loginSubmit'])

        if await username_input.is_visible() and await password_input.is_visible() and await login_submit.is_visible():
            await username_input.fill(account['username'])
            await password_input.fill(account['password'])
            await self.click_button(page, login_submit, '登录提交按钮')
            logging.info(f"已尝试使用账号 {account['username']} 登录。")
            self.account_index = (self.account_index + 1) % len(self.accounts)
            await asyncio.sleep(self.config['click_interval'] / 1000)  # 转换为秒
            await self.process_download(page)
        else:
            logging.error('登录表单元素未找到。')

    async def start(self, url):
        await self.run(url)

# 使用示例
if __name__ == "__main__":
    downloader = PlaywrightAutoDownloader(config_path='config.json')
    target_url = 'https://m.zxxk.com/soft/47755796.html'
    asyncio.run(downloader.start(target_url))
