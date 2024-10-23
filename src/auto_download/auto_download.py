import os
import queue
import re
import time
import logging
import random
from concurrent.futures import ThreadPoolExecutor
import threading
from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage.errors import ContextLostError

BASE_DIR = os.path.dirname(__file__)
DOWNLOAD_DIR = '/Users/martinezdavid/Documents/MG/work/zxxkdownload'  # 设置下载路径
LOCK = threading.Lock()

class XKW:
    def __init__(self, thread=1, work=False, download_dir=None):
        self.thread = thread
        self.work = work
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
            logging.info(f"Initialized {self.thread} tabs for downloading.")
        except Exception as e:
            logging.error(f"初始化标签页时出错: {e}", exc_info=True)

    def listener(self, tab, download, url, retry=0, max_retries=3):
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
                    return
                elif "20600001" in item.url:
                    logging.warning("请求过于频繁，暂停1秒后重试。")
                    print("请求过于频繁，暂停1秒后重试。")
                    time.sleep(1)
                    self.listener(tab, download, url, retry=retry + 1, max_retries=max_retries)
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
                self.listener(tab, download, url, retry=retry + 1, max_retries=max_retries)
        except ContextLostError as e:
            logging.warning(f"页面上下文丢失，重试下载: {url}, 错误信息: {e}")
            print(f"页面上下文丢失，重试下载: {url}")
            time.sleep(5)
            self.listener(tab, download, url, retry=retry + 1, max_retries=max_retries)
        except Exception as e:
            logging.error(f"下载过程中出错: {e}", exc_info=True)
            print(f"下载过程中出错: {e}")
            # 出现异常，进行重试
            time.sleep(5)
            self.listener(tab, download, url, retry=retry + 1, max_retries=max_retries)

    def download(self, url):
        try:
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

            download_button = tab("#btnSoftDownload")  # 下载按钮
            if not download_button:
                logging.error(f"无法找到下载按钮，跳过URL: {url}")
                self.tabs.put(tab)
                return

            # 开始下载
            self.listener(tab, download_button, url)
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