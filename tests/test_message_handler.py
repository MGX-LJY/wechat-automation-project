from lib.wxautox.wxauto import WeChat

# 初始化微信对象
wx = WeChat(language='cn', debug=True)

# 获取所有消息
msgs = wx.GetAllMessage()

for msg in msgs:
    print(f"类型: {msg.type}")
    print(f"发送者: {msg.sender}")
    print(f"好友: {msg.friend}")
    print(f"群组: {msg.group}")
    print(f"内容: {msg.content}")
    print(f"消息ID: {msg.id}")
    print("-" * 20)

# 获取新消息
new_msgs = wx.GetListenMessage()

for chat, messages in new_msgs.items():
    print(f"聊天对象: {chat}")
    for msg in messages:
        print(f"类型: {msg.type}")
        print(f"发送者: {msg.sender}")
        print(f"好友: {msg.friend}")
        print(f"群组: {msg.group}")
        print(f"内容: {msg.content}")
        print(f"消息ID: {msg.id}")
        print("-" * 20)
