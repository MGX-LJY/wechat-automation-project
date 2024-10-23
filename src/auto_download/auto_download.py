import os
import queue
import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from DrissionPage import ChromiumPage, ChromiumOptions

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
        # self.co.headless() # 不打开浏览器窗口 需要先登录 然后再开启 无浏览器模式
        self.co.no_imgs()  # 不加载图片
        self.co.set_download_path(DOWNLOAD_DIR)  # 设置下载路径
        # self.co.set_argument('--no-sandbox')  # 无沙盒模式
        self.page = ChromiumPage(self.co)

        logging.info(f"ChromiumPage initialized with address: {self.page.address}")
        self.url = "https://www.zxxk.com/soft/{xid}.html"
        self.dls_url = "https://www.zxxk.com/soft/softdownload?softid={xid}"
        self.suffix = {
            "iconfont icon-word-3":"docx",
            "iconfont icon-ppt-3":"pptx",
            "iconfont icon-excel-3":"xlsx",
            "iconfont icon-pdf-3":"pdf",
            "iconfont icon-rar-3":"rar",
            "iconfont icon-zip-3":"zip",
            "iconfont icon-txt-3":"txt",
            "iconfont icon-mp3-3":"mp3",
            "iconfont icon-mp4-3":"mp4",
            "iconfont icon-flv-3":"flv",
            "iconfont icon-swf-3":"swf",
            "iconfont icon-wma-3":"wma",
            "iconfont icon-wmv-3":"wmv",
            "iconfont icon-avi-3":"avi",
            "iconfont icon-rm-3":"rm",
            "iconfont icon-rmvb-3":"rmvb",
            "iconfont icon-mkv-3":"mkv",
            "iconfont icon-mov-3":"mov",
            "iconfont icon-3gp-3":"3gp",
            "iconfont icon-mpg-3":"mpg",
            "iconfont icon-mpeg-3":"mpeg",
            "iconfont icon-asf-3":"asf",
            "iconfont icon-asx-3":"asx",
            "iconfont icon-wpl-3":"wpl",
            "iconfont icon-torrent-3":"torrent",
            "iconfont icon-exe-3":"exe",
            "iconfont icon-dll-3":"dll",
            "iconfont icon-sys-3":"sys",
            "iconfont icon-bat-3":"bat",
            "iconfont icon-com-3":"com",
            "iconfont icon-scr-3":"scr",
            "iconfont icon-vbs-3":"vbs",
            "iconfont icon-js-3":"js",
            "iconfont icon-css-3":"css",
            "iconfont icon-html-3":"html",
            "iconfont icon-iso-3":"iso",
        }
        self.make_tabs()
        if work:
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

    def listener(self, tab, download, url):
        try:
            logging.info(f"开始下载: {url}")
            tab.listen.start(True, method="GET")
            download.click(by_js=True)
            logging.debug("Clicked download button.")

            for item in tab.listen.steps(timeout=15):  # 增加超时时间
                if item.url.startswith("https://files.zxxk.com/?mkey="):
                    # 停止页面加载
                    tab.listen.stop()
                    tab.stop_loading()
                    logging.info(f"下载链接获取成功: {item.url}")
                    break
            else:
                logging.warning(f"下载失败，尝试重新下载: {url}")
                iframe = tab.get_frame('#layui-layer-iframe100002')
                if iframe:
                    a = iframe("t:a@@class=balance-payment-btn@@text()=确认")
                    if a:
                        self.listener(a, url)
                    else:
                        logging.error("无法找到确认按钮，跳过下载。")
                else:
                    if tab.url.startswith("https://www.zxxk.com/soft/softdownload?softid="):
                        logging.info("下载已完成或无需重复下载。")
                    else:
                        self.listener(download, url)
                        logging.warning("未知错误，尝试重新下载。")
        except Exception as e:
            logging.error(f"监听下载时出错: {e}", exc_info=True)

    def download(self, url):
        try:
            tab = self.tabs.get(timeout=30)  # 设置超时避免阻塞
            logging.debug(f"获取到一个标签页用于下载: {tab}")
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

            self.listener(tab, download_button, url)
        except queue.Empty:
            logging.warning("任务队列为空，等待新任务。")
        except Exception as e:
            logging.error(f"下载过程中出错: {e}", exc_info=True)
        finally:
            self.tabs.put(tab)

    def run(self):
        with ThreadPoolExecutor(max_workers=self.thread) as executor:
            futures = []
            while True:
                try:
                    url = self.task.get(timeout=5)  # 等待新任务
                    if url is None:
                        logging.info("接收到退出信号，停止下载管理。")
                        break
                    future = executor.submit(self.download, url)
                    futures.append(future)
                except queue.Empty:
                    if not self.work:
                        logging.info("不再接受新任务，等待当前任务完成。")
                        break
                except Exception as e:
                    logging.error(f"任务分发时出错: {e}", exc_info=True)

            # 等待所有提交的任务完成
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"任务执行时出错: {e}", exc_info=True)

    def add_task(self, url):
        self.task.put(url)

    def stop(self):
        """
        停止下载管理，发送退出信号。
        """
        self.task.put(None)
        if self.manager.is_alive():
            self.manager.join()
        self.close_tabs(list(self.tabs.queue))
        self.page.close()