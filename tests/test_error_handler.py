import os
import tempfile
import time
from multiprocessing import Process
from DrissionPage import Chromium, ChromiumOptions
from DataRecorder import Recorder

def collect(page, recorder, title):
    """用于采集的方法
    :param page: ChromiumTab 对象
    :param recorder: Recorder 记录器对象
    :param title: 类别标题
    :return: None
    """
    num = 1  # 当前采集页数
    while True:
        # 遍历所有标题元素
        elements = page.eles('.title.project-namespace-path')  # 修正选择器格式
        for i in elements:
            # 获取某页所有库名称，记录到记录器
            recorder.add_data((title, i.text, num))

        # 如果有下一页，点击翻页
        btn = page('@rel=next', timeout=2)
        if btn:
            btn.click(by_js=True)
            page.wait.load_start()
            num += 1
        else:
            break

    recorder.record()  # 把数据记录到文件

def start_browser_instance(url, title, instance_number):
    """创建并启动一个独立的 Chromium 浏览器实例，并导航到指定的 URL"""
    try:
        # 创建一个唯一的临时用户数据文件夹
        temp_dir = tempfile.mkdtemp(prefix=f"drissionpage_userdata_{instance_number}_")
        print(f"[实例 {instance_number}] 用户数据路径: {temp_dir}")

        # 创建独立的 ChromiumOptions 对象
        options = ChromiumOptions().auto_port()
        options.set_user_data_path(temp_dir)  # 设置独立的用户数据文件夹
        options.remove_extensions()  # 确保不加载任何扩展，包括广告屏蔽扩展

        # 初始化 Chromium 浏览器对象
        browser = Chromium(addr_or_opts=options)
        print(f"[实例 {instance_number}] 浏览器已启动。")

        # 获取最新标签页对象
        tab = browser.latest_tab

        # 导航到指定的 URL
        tab.get(url)
        print(f"[实例 {instance_number}] 已导航到 {url}")

        # 新建记录器对象
        recorder = Recorder(f'data_instance_{instance_number}.csv')

        # 启动采集
        collect(tab, recorder, title)

    except Exception as e:
        print(f"[实例 {instance_number}] 启动浏览器失败: {e}")

def main():
    # 要访问的主要内容 URL 和标题列表
    target_urls = [
        ("https://gitee.com/explore/ai", "AI"),
        ("https://gitee.com/explore/machine-learning", "机器学习"),
        ("https://gitee.com/explore/other-category", "其他类别")
    ]

    # 要打开的浏览器实例数量
    num_browsers = len(target_urls)  # 3

    # 存储进程对象
    processes = []

    for i in range(num_browsers):
        url, title = target_urls[i]
        instance_number = i + 1
        print(f"正在启动浏览器实例 {instance_number}/{num_browsers}，导航到 {url}...")
        p = Process(target=start_browser_instance, args=(url, title, instance_number))
        p.start()
        processes.append(p)
        time.sleep(2)  # 可根据需要调整启动间隔

    print("所有浏览器实例已启动并导航到目标网址。")

    try:
        # 等待所有进程完成
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("检测到中断信号，正在关闭所有浏览器实例...")
        for p in processes:
            p.terminate()
        print("所有浏览器实例已关闭。")

if __name__ == '__main__':
    main()
