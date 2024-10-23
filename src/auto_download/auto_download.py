import os
import queue
import re
import time
from concurrent.futures import ThreadPoolExecutor
import threading
from DrissionPage import ChromiumPage,ChromiumOptions

BASE_DIR = os.path.dirname(__file__)
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'Downloads') # 配置下载路径
LOCK = threading.Lock()

class XKW:
    def __init__(self,thread=1,work=False):
        self.thread=thread
        self.work=work
        self.tabs = queue.Queue()
        self.task = queue.Queue()
        self.co = ChromiumOptions()
        # self.co.headless() # 不打开浏览器窗口 需要先登录 然后再开启 无浏览器模式
        self.co.no_imgs() # 不加载图片
        self.co.set_download_path(DOWNLOAD_DIR)# 设置下载路径
        # self.co.set_argument('--no-sandbox')  # 无沙盒模式
        self.page = ChromiumPage(self.co)

        print(self.page.address)
        self.data = self.loads_data()
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
            self.manager = threading.Thread(target=self.run)
            self.manager.start()

    def close_tabs(self,tabs):
        for tab in tabs:
            tab.close()

    def make_tabs(self):
        tabs = self.page.get_tabs()
        print("tabs",tabs)
        if len(tabs) < self.thread:
            self.page.new_tab()
            self.make_tabs()
        elif len(tabs) > self.thread:
            self.close_tabs(tabs[self.thread:])
        else:
            for tab in tabs:
                self.tabs.put(tab)

    def loads_data(self):
        with open("aa.txt", 'r',encoding='utf-8') as f:
            data = f.read()
            l = re.findall('(https://www.zxxk.com/soft/\d+.html)', data)
        return l

    def listener(self,tab,download,url):
        print("开始下载", url)
        tab.listen.start(True, method="GET")
        download.click(by_js=True)
        print("clicked")
        for item in tab.listen.steps(timeout=5):
            if item.url.startswith("https://files.zxxk.com/?mkey="):
                # 停止页面加载
                tab.listen.stop()
                tab.stop_loading()
                print(item.url)
                break
        else:
            print("下载失败 重新下载中", url)
            iframe = tab.get_frame('#layui-layer-iframe100002')
            if iframe:
                a= iframe("t:a@@class=balance-payment-btn@@text()=确认")
                tab.listen.start(True, method="GET")
                self.listener(a,url)
            else:
                if tab.url.startswith("https://www.zxxk.com/soft/softdownload?softid="):
                    print("已经完成了")
                else:
                    self.listener(download,url)
                    print("未知错误 重新下载中")


    def download(self, url):
        tab = self.tabs.get()
        tab.get(url)
        tab.stop_loading()
        h1 = tab.s_ele("t:h1@@class=res-title clearfix")
        suffix = h1.child("t:i@@class^iconfont")
        class_name = suffix.attr("class").strip()
        # print(self.suffix.get(class_name,"docx"))
        title = h1.child("t:span")
        # print(title.text)
        download = tab("#btnSoftDownload") #下载按钮

        # with LOCK:
        self.listener(tab,download,url)
        self.tabs.put(tab)

    def run(self):
        with ThreadPoolExecutor(max_workers=self.thread) as t:
            if self.work:
                url = self.task.get()
                t.submit(self.download, url)
            else:
                for url in self.data:
                    t.submit(self.download,url)
        # input("输入任意键退出") # 等待输入任意键退出 程序退出后 不会给软件命名 等待下载完成后再推出程序

    def add_task(self,url):
        self.task.put(url)


if __name__ == '__main__':
    # 测试使用  使用aa.txt文件中的链接进行下载
    xkw = XKW(thread=3,work=False)
    xkw.run()
    # 正常工作 使用一下 需要调用 add_task 方法添加任务
    # xkw = XKW(thread=3,work=True)
    # xkw.add_task("https://www.zxxk.com/soft/1000000000.html")
