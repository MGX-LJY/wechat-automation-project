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
        # 访问主页
        self.tab.get('https://www.zxxk.com/')
        iframes = self.tab.get_frames()
        iframe = self.tab.ele('tag:iframe@@id=login_iframe')  # 修改为实际iframe的选择器
        avatar = target_iframe.ele('a.user-btn')
        target_iframe.actions.move_to('a.user-btn').click('a.dl-quit.fr')
        self.tab.actions.move_to('a.user-btn').click('a.dl-quit.fr')


if __name__ == '__main__':
    # 实例化登录类
    xkw = XkwLogin()
    # 执行退出
    xkw.logout()
