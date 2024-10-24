# src/auto_download/auto_download.py

import os
import queue
import re
import time
import logging
import random
from concurrent.futures import ThreadPoolExecutor
import threading
from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage.errors import ContextLostError, PageDisconnectedError
from src.file_upload.uploader import Uploader
from bs4 import BeautifulSoup


BASE_DIR = os.path.dirname(__file__)
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'Downloads') # 配置下载路径
LOCK = threading.Lock()

class XKW:
    def __init__(self, thread=1, work=False, download_dir=None, uploader=None):
        self.thread = thread
        self.work = work
        self.uploader = uploader  # 接收 Uploader 实例
        self.tabs = queue.Queue()
        self.task = queue.Queue()
        self.co = ChromiumOptions()
        # self.co.headless()  # 不打开浏览器窗口，需要先登录然后再开启无浏览器模式
        self.co.no_imgs()  # 不加载图片
        self.co.set_download_path(download_dir or DOWNLOAD_DIR)  # 设置下载路径
        # self.co.set_argument('--no-sandbox')  # 无沙盒模式
        self.page = ChromiumPage(self.co)

        logging.info(f"ChromiumPage initialized with address: {self.page.address}")
        self.url = "https://www.zxxk.com/soft/{xid}.html"
        self.dls_url = "https://www.zxxk.com/soft/softdownload?softid={xid}"
        self.suffix = {
            "iconfont icon-word-3": "docx",
            "iconfont icon-ppt-3": "pptx",
            "iconfont icon-excel-3": "xlsx",
            "iconfont icon-pdf-3": "pdf",
            "iconfont icon-rar-3": "rar",
            "iconfont icon-zip-3": "zip",
            "iconfont icon-txt-3": "txt",
            "iconfont icon-mp3-3": "mp3",
            "iconfont icon-mp4-3": "mp4",
            "iconfont icon-flv-3": "flv",
            "iconfont icon-swf-3": "swf",
            "iconfont icon-wma-3": "wma",
            "iconfont icon-wmv-3": "wmv",
            "iconfont icon-avi-3": "avi",
            "iconfont icon-rm-3": "rm",
            "iconfont icon-rmvb-3": "rmvb",
            "iconfont icon-mkv-3": "mkv",
            "iconfont icon-mov-3": "mov",
            "iconfont icon-3gp-3": "3gp",
            "iconfont icon-mpg-3": "mpg",
            "iconfont icon-mpeg-3": "mpeg",
            "iconfont icon-asf-3": "asf",
            "iconfont icon-asx-3": "asx",
            "iconfont icon-wpl-3": "wpl",
            "iconfont icon-torrent-3": "torrent",
            "iconfont icon-exe-3": "exe",
            "iconfont icon-dll-3": "dll",
            "iconfont icon-sys-3": "sys",
            "iconfont icon-bat-3": "bat",
            "iconfont icon-com-3": "com",
            "iconfont icon-scr-3": "scr",
            "iconfont icon-vbs-3": "vbs",
            "iconfont icon-js-3": "js",
            "iconfont icon-css-3": "css",
            "iconfont icon-html-3": "html",
            "iconfont icon-iso-3": "iso",
        }
        self.make_tabs()
        if self.work:
            self.manager = threading.Thread(target=self.run, daemon=True)
            self.manager.start()
            logging.info("XKW manager thread started.")

    def close_tabs(self, tabs):
        for tab in tabs:
            try:
                tab.close()
                logging.debug("Closed a browser tab.")
            except Exception as e:
                logging.error(f"关闭标签页时出错: {e}", exc_info=True)

    def get_tab(self):
        try:
            tab = self.tabs.get(timeout=5)
            return tab
        except queue.Empty:
            logging.error("没有可用的浏览器标签页。")
            return None

    def make_tabs(self):
        try:
            tabs = self.page.get_tabs()
            logging.debug(f"Current tabs: {tabs}")
            while len(tabs) < self.thread:
                self.page.new_tab()
                tabs = self.page.get_tabs()
                logging.debug(f"Added new tab. Total tabs: {len(tabs)}")
            if len(tabs) > self.thread:
                self.close_tabs(tabs[self.thread:])
                tabs = self.page.get_tabs()[:self.thread]
            for tab in tabs:
                self.tabs.put(tab)
            logging.info(f"初始化 {self.thread} 个标签页用于下载。")
        except Exception as e:
            logging.error(f"初始化标签页时出错: {e}", exc_info=True)

    def download_file(self, tab, soft_id):
        """
        执行下载操作
        """
        try:
            download_url = self.dls_url.format(xid=soft_id)
            tab.get(download_url)
            # 等待下载按钮出现并点击
            download_button = tab.ele('css selector', '.btn-download')
            if download_button:
                download_button.click()
                logging.info(f"已点击下载按钮，soft_id: {soft_id}")
                # 等待下载完成（您可能需要根据实际情况调整）
                time.sleep(5)
                return True
            else:
                logging.error(f"未找到下载按钮，soft_id: {soft_id}")
                return False
        except Exception as e:
            logging.error(f"下载文件时发生错误: {e}", exc_info=True)
            return False

    def match_downloaded_file(self, title, suffix):
        """
        在下载目录中匹配下载的文件
        """
        try:
            download_dir = self.co.download_path
            for file_name in os.listdir(download_dir):
                if title in file_name and file_name.endswith(suffix):
                    file_path = os.path.join(download_dir, file_name)
                    logging.info(f"匹配到下载的文件: {file_path}")
                    return file_path
            logging.error(f"未能找到匹配的下载文件: {title}.{suffix}")
            return None
        except Exception as e:
            logging.error(f"匹配下载文件时发生错误: {e}", exc_info=True)
            return None

    def extract_id_and_title(self, tab, url):
        """
        从页面中提取 soft_id 和标题
        """
        try:
            # 检查标签页是否有效
            if not tab.is_connected:
                logging.warning("标签页已关闭，重新获取标签页")
                tab = self.get_tab()

            tab.get(url)
            # 等待页面加载完成
            tab.wait_load(10)

            # 获取页面 HTML
            page_html = tab.html
            soup = BeautifulSoup(page_html, 'html.parser')

            # 尝试从 <h1 class="res-title clearfix"> 中获取标题
            h1 = soup.find('h1', class_='res-title clearfix')
            if h1:
                # 优先从 h1 的 'title' 属性中获取标题
                title = h1.get('title', '').strip()
                if not title:
                    # 如果没有 'title' 属性，从 h1 的文本内容中获取标题
                    title = h1.get_text(separator=' ', strip=True)
                    logging.info(f"从 h1 标签文本中获取到标题: {title}")
                else:
                    logging.info(f"从 h1 标签的 'title' 属性中获取到标题: {title}")
            else:
                logging.error(f"无法从页面中找到 h1.res-title 标签，URL: {url}")
                return None, None

            # 从 URL 中提取 soft_id
            match = re.search(r'/soft/(\d+)\.html', url)
            if match:
                soft_id = match.group(1)
                logging.info(f"从 URL 中提取到 soft_id: {soft_id}")
            else:
                logging.error(f"无法从 URL 中提取 soft_id，跳过 URL: {url}")
                return None, None

            return soft_id, title.strip()

        except PageDisconnectedError as e:
            logging.error(f"页面连接断开，重新获取标签页。错误: {e}")
            # 重新获取标签页
            tab = self.get_tab()
            return self.extract_id_and_title(tab, url)

        except Exception as e:
            logging.error(f"提取 ID 和标题时出错: {e}", exc_info=True)
            return None, None

    def listener(self, tab, download, url, title, suffix, soft_id, retry=0, max_retries=3):
        if retry > max_retries:
            logging.error(f"超过最大重试次数，下载失败: {url}")
            print("超过最大重试次数，下载失败。")
            return
        logging.info(f"开始下载 {url}, 重试次数: {retry}")
        print("开始下载", url)
        try:
            tab.listen.start(True, method="GET")
            download.click(by_js=True)
            print("clicked")
            for item in tab.listen.steps(timeout=5):
                if item.url.startswith("https://files.zxxk.com/?mkey="):
                    # 停止页面加载
                    tab.listen.stop()
                    tab.stop_loading()
                    logging.info(f"下载链接获取成功: {item.url}")
                    print(item.url)

                    # 匹配下载的文件
                    file_path = self.match_downloaded_file(title, suffix)
                    if file_path and os.path.exists(file_path):
                        filename = os.path.basename(file_path)
                        logging.info(f"下载完成文件: {filename}, ID: {soft_id}")

                        # 将 file_path + soft_id 传递给 Uploader
                        if self.uploader:
                            self.uploader.upload_file(file_path, soft_id)
                        else:
                            logging.warning("Uploader 未设置，无法上传文件信息。")
                    else:
                        logging.error(f"文件路径无效或文件不存在: {file_path}")

                    return
                elif "20600001" in item.url:
                    logging.warning("请求过于频繁，暂停1秒后重试。")
                    print("请求过于频繁，暂停1秒后重试。")
                    time.sleep(1)
                    self.listener(tab, download, url, title, suffix, soft_id, retry=retry + 1, max_retries=max_retries)
                    return
            else:
                # 等待页面加载完成
                time.sleep(2)
                iframe = tab.get_frame('#layui-layer-iframe100002')
                if iframe:
                    a = iframe("t:a@@class=balance-payment-btn@@text()=确认")
                    if a:
                        a.click()
                        logging.info("点击确认按钮成功。")
                        print("点击确认按钮成功。")
                        return
                # 如果未找到确认按钮，进行重试
                logging.warning(f"下载失败，尝试重新下载: {url}, 当前重试次数: {retry}")
                print("下载失败 重新下载中", url)
                time.sleep(5)  # 重试前等待5秒
                self.listener(tab, download, url, title, suffix, soft_id, retry=retry + 1, max_retries=max_retries)
        except ContextLostError as e:
            logging.warning(f"页面上下文丢失，重试下载: {url}, 错误信息: {e}")
            print(f"页面上下文丢失，重试下载: {url}")
            time.sleep(5)
            self.listener(tab, download, url, title, suffix, soft_id, retry=retry + 1, max_retries=max_retries)
        except Exception as e:
            logging.error(f"下载过程中出错: {e}", exc_info=True)
            print(f"下载过程中出错: {e}")
            # 出现异常，进行重试
            time.sleep(5)
            self.listener(tab, download, url, retry=retry + 1, max_retries=max_retries)

    def download(self, url):
        try:
            import random  # 确保导入 random 模块
            # 随机延迟1到3秒，防止请求过于频繁
            delay = random.uniform(1, 3)
            time.sleep(delay)

            tab = self.tabs.get(timeout=30)  # 设置超时避免阻塞
            logging.info(f"获取到一个标签页用于下载: {tab}")
            tab.get(url)
            h1 = tab.s_ele("t:h1@@class=res-title clearfix")
            if not h1:
                logging.error(f"无法找到标题元素，跳过URL: {url}")
                self.tabs.put(tab)
                return

            suffix_element = h1.child("t:i@@class^iconfont")
            if not suffix_element:
                logging.warning(f"无法找到后缀元素，使用默认后缀 'docx'。")
                suffix = "docx"
            else:
                class_name = suffix_element.attr("class").strip()
                suffix = self.suffix.get(class_name, "docx")

            title_element = h1.child("t:span")
            if not title_element:
                logging.warning(f"无法找到标题文本，使用默认标题。")
                title = "未命名"
            else:
                title = title_element.text.strip()

            # 从 URL 中提取 soft_id
            match = re.search(r'/soft/(\d+)\.html', url)
            if match:
                soft_id = match.group(1)
                logging.info(f"从 URL 中提取到 soft_id: {soft_id}")
            else:
                logging.error(f"无法从 URL 中提取 soft_id，跳过 URL: {url}")
                self.tabs.put(tab)
                return

            download_button = tab("#btnSoftDownload")  # 下载按钮
            if not download_button:
                logging.error(f"无法找到下载按钮，跳过URL: {url}")
                self.tabs.put(tab)
                return

            # 开始下载
            success = self.listener(tab, download_button, url, title, suffix, soft_id)
            if success:
                # 匹配下载的文件
                file_path = self.match_downloaded_file(title, suffix)
                if not file_path:
                    logging.error(f"匹配下载的文件失败，跳过 URL: {url}")
                else:
                    # 将文件路径和 soft_id 传递给上传模块
                    if self.uploader:
                        self.uploader.add_upload_task(file_path, soft_id)
                        logging.info(f"已将文件 {file_path} 和 soft_id {soft_id} 添加到上传任务队列。")
                    else:
                        logging.warning("Uploader 未设置，无法传递上传任务。")
            else:
                logging.error(f"下载失败，跳过 URL: {url}")
        except queue.Empty:
            logging.warning("任务队列为空，等待新任务。")
        except Exception as e:
            logging.error(f"下载过程中出错: {e}", exc_info=True)
            # 在发生异常时，确保 tab 被放回队列
            if 'tab' in locals():
                self.tabs.put(tab)
        finally:
            if 'tab' in locals():
                self.tabs.put(tab)

    def run(self):
        with ThreadPoolExecutor(max_workers=self.thread) as executor:
            futures = []
            while self.work:
                try:
                    url = self.task.get(timeout=5)  # 等待新任务
                    if url is None:
                        logging.info("接收到退出信号，停止下载管理。")
                        break
                    future = executor.submit(self.download, url)
                    futures.append(future)
                    logging.info(f"已提交下载任务到线程池: {url}")
                except queue.Empty:
                    continue  # 没有任务，继续等待
                except Exception as e:
                    logging.error(f"任务分发时出错: {e}", exc_info=True)
            # 等待所有任务完成
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"下载任务中出现未捕获的异常: {e}", exc_info=True)

    def add_task(self, url):
        self.task.put(url)