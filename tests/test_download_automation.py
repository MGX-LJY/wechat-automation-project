import time

from DrissionPage import Chromium


class XkwLogin:
    def __init__(self):
        # 创建浏览器对象，并获取最新的标签页对象
        self.browser = Chromium()
        self.tab = self.browser.latest_tab

    def login(self, username, password):
        try:
            # 访问登录页面
            self.tab.get('https://sso.zxxk.com/login')

            # 点击“账户密码/验证码登录”按钮
            self.tab.ele('tag:button@@class=another@@text():账户密码/验证码登录').click()

            # 输入用户名和密码
            self.tab.ele('#username').input(username)
            self.tab.ele('#password').input(password)

            # 点击登录按钮
            self.tab.ele('#accountLoginBtn').click()

        except TimeoutError:
            print('页面加载超时，请检查网络连接。')
        except Exception as e:
            print(f'登录过程中出现错误：{e}')

    def logout(self):
        try:
            # 等待 '我的' 元素出现并将鼠标移动到其上方
            my_element = self.tab.ele('text:我的', timeout=10)
            my_element.hover()
            time.sleep(1)  # 等待下拉菜单显示

            # 等待 '退出' 元素出现并点击
            logout_element = self.tab.ele('text:退出', timeout=10)
            logout_element.click()

        except Exception as e:
            print(f'退出过程中出现错误：{e}')


if __name__ == '__main__':
    # 实例化登录类
    xkw = XkwLogin()
    # 执行退出
    xkw.logout()
