from lib.wxautox.wxauto import WeChat

# 初始化微信对象
wx = WeChat(language='cn', debug=True)

# 获取所有消息
msgs = wx.GetAllMessage()
msg = msgs1[-1]

msg.details