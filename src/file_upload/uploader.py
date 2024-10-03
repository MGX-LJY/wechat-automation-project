# src/file_upload/uploader.py

import os
import logging
from lib import itchat  # 确保使用修改后的 itchat
import threading
import time

class Uploader:
    def __init__(self, config, error_handler, cloud_uploader=None):
        self.target_groups = config.get('target_groups', [])
        self.error_handler = error_handler
        self.cloud_uploader = cloud_uploader  # 传入云上传器实例
        self.group_usernames = self._fetch_group_usernames()

    def _fetch_group_usernames(self):
        """
        获取目标群组的 UserName
        """
        group_usernames = {}
        for group_name in self.target_groups:
            groups = itchat.search_chatrooms(name=group_name)
            if groups:
                group_usernames[group_name] = groups[0]['UserName']
                logging.info(f"找到群组 '{group_name}' 的 UserName: {groups[0]['UserName']}")
            else:
                logging.error(f"未找到群组: {group_name}")
                group_usernames[group_name] = None  # 防止后续上传时找不到群组
        return group_usernames

    def upload_file(self, file_path):
        """
        启动一个新线程来上传文件，避免阻塞
        """
        upload_thread = threading.Thread(target=self._upload_file_thread, args=(file_path,))
        upload_thread.start()

    def _upload_file_thread(self, file_path):
        """
        上传文件的线程函数，直接上传完整文件或使用云存储
        """
        try:
            if not os.path.exists(file_path):
                logging.warning(f"文件不存在: {file_path}")
                return

            # 等待文件大小稳定
            self.wait_for_file_stability(file_path)

            file_size = os.path.getsize(file_path)
            max_size = 50 * 1024 * 1024  # 假设企业微信支持上传50MB文件
            alert_size = 25 * 1024 * 1024  # 25MB的阈值

            # 检查是否需要发送超过25MB的提醒消息
            if file_size > alert_size:
                self.send_large_file_message(file_path)

            if file_size > max_size:
                logging.warning(f"文件大小 {file_size} 字节 超过企业微信限制的 {max_size} 字节。")
                if self.cloud_uploader:
                    # 上传到云存储并分享链接
                    shared_link = self.cloud_uploader.upload_to_drive(file_path)
                    if shared_link:
                        self.cloud_uploader.share_link_to_wechat_group(shared_link, self.group_usernames)
                else:
                    logging.error("未配置云上传器，无法分享文件链接。")
            else:
                # 文件较小，直接上传
                for group_name, user_name in self.group_usernames.items():
                    if not user_name:
                        logging.error(f"群组 '{group_name}' 的 UserName 未找到，跳过上传")
                        continue
                    self._upload_chunk(file_path, user_name)
        except Exception as e:
            logging.error(f"上传文件时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def _upload_chunk(self, file_path, user_name):
        """
        上传完整文件
        """
        try:
            logging.info(f"正在上传文件: {file_path} 至群组: {user_name}")
            itchat.send_file(file_path, toUserName=user_name)
            logging.info(f"文件已上传至群组: {user_name}")
            time.sleep(1)  # 添加短暂的延迟，避免触发微信速率限制
        except Exception as e:
            logging.error(f"上传失败: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def wait_for_file_stability(self, file_path, stable_time=5):
        """
        等待文件大小稳定
        """
        previous_size = -1
        while True:
            try:
                current_size = os.path.getsize(file_path)
            except FileNotFoundError:
                logging.warning(f"文件不存在: {file_path}")
                return
            if current_size == previous_size:
                break
            previous_size = current_size
            logging.debug(f"等待文件稳定中: {file_path}, 当前大小: {current_size} 字节")
            time.sleep(stable_time)

        logging.info(f"文件已稳定: {file_path}, 准备上传")

    def send_large_file_message(self, file_path):
        """
        发送超过25MB的文件上传提醒消息到所有目标群组。

        :param file_path: 要上传的文件路径。
        """
        try:
            filename = os.path.basename(file_path)
            message = f"{filename} 超过25MB 晚上统一上传，急需的话@李老师"

            for group_name, user_name in self.group_usernames.items():
                if not user_name:
                    logging.error(f"群组 '{group_name}' 的 UserName 未找到，无法发送提醒消息")
                    continue
                try:
                    itchat.send(message, toUserName=user_name)
                    logging.info(f"发送提醒消息到群组 '{group_name}': {message}")
                except Exception as e:
                    logging.error(f"发送消息到群组 '{group_name}' 失败: {e}", exc_info=True)
                    self.error_handler.handle_exception(e)
        except Exception as e:
            logging.error(f"发送超过25MB提醒消息时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
