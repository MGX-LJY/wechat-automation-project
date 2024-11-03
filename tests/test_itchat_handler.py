# test_itchat.py
from lib import itchat
from lib.itchat.content import TEXT, SHARING

@itchat.msg_register([TEXT, SHARING], isGroupChat=True)
def handle_group(msg):
    print(f"接收到群组消息: {msg['Content']} 来自群组: {msg['User']['NickName']}")

@itchat.msg_register([TEXT, SHARING], isGroupChat=False)
def handle_individual(msg):
    print(f"接收到个人消息: {msg['Content']} 来自: {msg['User']['NickName']}")

def main():
    itchat.auto_login(hotReload=True)
    itchat.run()

if __name__ == "__main__":
    main()
