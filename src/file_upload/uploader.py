import os
import logging
from lib import itchat  # 确保使用修改后的 itchat
import threading
import time

class Uploader:
    def __init__(self, config, error_handler):
        self.target_groups = config.get('target_groups', [])
        self.error_handler = error_handler
        self.group_usernames = self._fetch_group_usernames()
        self.max_retries = 3  # 最大重试次数
        self.retry_delay = 5  # 重试间隔时间（秒）
        self.max_size = 50 * 1024 * 1024  # 假设企业微信支持上传50MB文件
        self.alert_size = 25 * 1024 * 1024  # 25MB的阈值

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
        上传文件的线程函数，直接上传完整文件
        """
        try:
            if not os.path.exists(file_path):
                logging.warning(f"文件不存在: {file_path}")
                return

            # 等待文件大小稳定
            self.wait_for_file_stability(file_path)

            file_size = os.path.getsize(file_path)

            # 检查文件大小是否超过限制
            if file_size > self.max_size:
                logging.warning(f"文件大小 {file_size} 字节超过限制的 {self.max_size} 字节，无法上传。")
                return

            # 检查是否需要发送超过25MB的提醒消息
            if file_size > self.alert_size:
                self.send_large_file_message(file_path)

            # 文件符合上传条件，直接上传
            for group_name, user_name in self.group_usernames.items():
                if not user_name:
                    logging.error(f"群组 '{group_name}' 的 UserName 未找到，跳过上传")
                    continue
                self._upload_chunk_with_retry(file_path, user_name)
        except Exception:
            logging.error("上传文件时发生网络问题")
            self.error_handler.handle_exception()

    def _upload_chunk_with_retry(self, file_path, user_name):
        """
        带有重试机制的文件上传
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                logging.info(f"正在上传文件: {file_path} 至群组: {user_name}，尝试次数: {attempt}")
                itchat.send_file(file_path, toUserName=user_name)
                logging.info(f"文件已上传至群组: {user_name}")
                time.sleep(1)  # 添加短暂的延迟，避免触发微信速率限制
                return  # 上传成功，退出函数
            except Exception:
                if attempt < self.max_retries:
                    logging.warning("上传失败，网络问题，稍后重试...")
                    time.sleep(self.retry_delay)
                else:
                    logging.error("上传失败，网络问题")
                    self.error_handler.handle_exception()

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
        """
        try:
            filename = os.path.basename(file_path)
            message = f"{filename} 超过25MB，晚上统一上传，急需的话@李老师"

            for group_name, user_name in self.group_usernames.items():
                if not user_name:
                    logging.error(f"群组 '{group_name}' 的 UserName 未找到，无法发送提醒消息")
                    continue
                try:
                    itchat.send(message, toUserName=user_name)
                    logging.info(f"发送提醒消息到群组 '{group_name}': {message}")
                except Exception:
                    logging.error("发送提醒消息时发生网络问题")
                    self.error_handler.handle_exception()
        except Exception:
            logging.error("发送提醒消息时发生网络问题")
            self.error_handler.handle_exception()
