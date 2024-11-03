# test_itchat.py
import logging

from lib import itchat
from lib.itchat.content import TEXT, SHARING

@itchat.msg_register([TEXT, SHARING], isGroupChat=True)
def handle_group(msg):
    print(f"接收到群组消息: {msg['Content']} 来自群组: {msg['User']['NickName']}")
    logging.debug(f"完整的消息对象: {msg}")

@itchat.msg_register([TEXT, SHARING], isGroupChat=False)
def handle_individual(msg):
    print(f"接收到个人消息: {msg['Content']} 来自: {msg['User']['NickName']}")
    logging.debug(f"完整的消息对象: {msg}")

def main():
    itchat.auto_login(hotReload=True)
    itchat.run()

if __name__ == "__main__":
    main()
