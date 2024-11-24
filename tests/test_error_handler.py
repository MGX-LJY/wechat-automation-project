# test_group_messages.py

from lib import itchat
from lib.itchat.content import (
    TEXT, MAP, CARD, NOTE, SHARING, PICTURE, RECORDING, ATTACHMENT, VIDEO
)
import logging
from PIL import Image
from io import BytesIO

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # 设置为 DEBUG 级别以获取详细日志
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def qr_callback(uuid, status, qrcode):
    """
    处理二维码回调，保存并显示二维码图像
    """
    logging.info(f"QR callback - UUID: {uuid}, Status: {status}")
    if status == '0':
        # 状态 0 表示需要展示二维码
        qr_path = 'qr.png'
        with open(qr_path, 'wb') as f:
            f.write(qrcode)
        logging.info(f"二维码已保存到 {qr_path}")
        # 显示二维码图像
        try:
            Image.open(BytesIO(qrcode)).show(title="微信登录二维码")
        except Exception as e:
            logging.error(f"显示二维码时出错: {e}")
    elif status == '201':
        # 状态 201 表示已扫描二维码，等待确认
        logging.info("二维码已扫描，请在手机上确认登录。")
    elif status == '200':
        # 状态 200 表示登录成功
        logging.info("登录成功")
    else:
        logging.warning(f"未知的QR回调状态: {status}")

# 注册处理所有类型的群组消息
@itchat.msg_register(
    [TEXT, MAP, CARD, NOTE, SHARING, PICTURE, RECORDING, ATTACHMENT, VIDEO],
    isGroupChat=True
)
def handle_group_message(msg):
    """
    处理所有群组消息的回调函数，并直接显示完整的消息内容
    """
    try:
        logging.info("收到群消息：")
        logging.info(msg)  # 直接记录完整的消息字典
        logging.info("-" * 50)
    except Exception as e:
        logging.error(f"处理群消息时出错: {e}")

def main():
    logging.info("正在登录微信...")
    itchat.auto_login(
        hotReload=True,
        enableCmdQR=False,
        qrCallback=qr_callback
    )
    logging.info("登录成功，开始监听群消息...")
    itchat.run()

if __name__ == "__main__":
    main()
