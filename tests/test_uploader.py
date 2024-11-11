# -*- coding: utf-8 -*-
"""
DrissionPage 启动脚本示例
功能：
- 启动 Chromium 浏览器
- 访问指定的 URL
- 定位并打印 <em>独家</em> 和 <em>教辅</em> 元素的信息
- 关闭浏览器

作者：MartinezDavid
日期：2024-04-27
"""

from DrissionPage import ChromiumPage
import time

def main():
    # 创建 ChromiumPage 对象，启动 Chromium 浏览器
    page = ChromiumPage()  # headless=False 显示浏览器窗口，True 则无界面模式

    try:
        # 访问指定的网页
        url = 'https://www.zxxk.com/soft/41296818.html'
        print(f"正在访问网页：{url}")
        page.get(url)

        # 方法一：直接定位文本为“独家”的 <em> 元素
        print("尝试定位 <em>独家</em> 元素...")
        ele_dujia = page.ele('tag:em@text()=独家')

        # 方法二：直接定位文本为“教辅”的 <em> 元素
        print("尝试定位 <em>教辅</em> 元素...")
        ele_jiaofu = page.ele('tag:em@text()=教辅')

        # 检查是否成功定位，并打印结果
        if ele_dujia.text == "独家":
            print('成功定位到 <em>独家</em> 元素')
            print(f'元素文本内容：{ele_dujia.text}')
        else:
            print('未能定位到 <em>独家</em> 元素')

        if ele_jiaofu.text == "教辅":
            print('成功定位到 <em>教辅</em> 元素')
            print(f'元素文本内容：{ele_jiaofu.text}')
        else:
            print('未能定位到 <em>教辅</em> 元素')

        # 额外示例：同时定位多个 <em> 元素
        print("尝试同时定位所有 <em>独家</em> 和 <em>教辅</em> 元素...")
        eles = page.eles('tag:em@|text()=独家@|text()=教辅')
        print(f"找到 {len(eles)} 个符合条件的 <em> 元素：")
        for idx, ele in enumerate(eles, start=1):
            print(f"  {idx}. 文本内容：{ele.text}")

    except Exception as e:
        print(f"发生错误：{e}")
    finally:
        # 等待几秒钟以便查看浏览器中的结果（可选）
        print("等待 5 秒后关闭浏览器...")
        time.sleep(5)

        # 关闭浏览器
        page.close()
        print("浏览器已关闭。")

if __name__ == "__main__":
    main()
