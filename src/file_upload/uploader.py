# src/file_upload/uploader.py

import os
import json
import logging
import datetime
from lib import itchat
import threading
import time

class Uploader:
    def __init__(self, upload_config, error_notification_config, error_handler):
        self.target_groups = upload_config.get('target_groups', [])
        self.default_recipient = upload_config.get('default_recipient', '李老师呀')  # 添加默认接收者
        self.error_handler = error_handler
        self.group_usernames = self._fetch_group_usernames()
        self.max_retries = 3  # 最大重试次数
        self.retry_delay = 5  # 重试间隔时间（秒）
        self.alert_size = 25 * 1024 * 1024  # 25MB的阈值

        # 计数器配置文件路径
        self.counts_file = upload_config.get('counts_file', 'counts.json')

        # 从计数器配置文件中加载计数器数据
        self.load_counters()

        # 维护 soft_id 到 recipient（群组或个人）的映射
        self.softid_to_recipient = {}
        self.lock = threading.Lock()  # 添加锁以确保线程安全

        # 获取默认接收者的 UserName（可以是个人或群组）
        self.default_recipient_username = self._fetch_user_or_group_username(self.default_recipient)

        # 获取错误通知的个人账号 UserName
        self.error_recipient = error_notification_config.get('recipient')
        self.error_recipient_username = self._fetch_friend_username(self.error_recipient)

        # 保留每日通知系统，不需要修改
        notification_thread = threading.Thread(target=self.notification_scheduler, daemon=True)
        notification_thread.start()
        logging.info("每日通知调度线程已启动")

        # 确保 itchat 已登录
        if not itchat.check_login():
            logging.info("ItChat 未登录，开始登录...")
            itchat.auto_login(hotReload=True)  # 自动登录，保持会话

    def _fetch_friend_username(self, friend_name):
        """
        获取好友的 UserName
        """
        if not friend_name:
            logging.error("未在配置中找到 error_recipient")
            return None

        friends = itchat.search_friends(name=friend_name)
        if not friends:
            # 打印所有好友的名字以供调试
            all_friends = itchat.get_friends(update=True)
            all_friend_names = [friend['NickName'] for friend in all_friends]
            logging.error(f"未找到好友: {friend_name}. 当前好友列表: {all_friend_names}")
            return None

        user_name = friends[0]['UserName']
        logging.info(f"找到好友 '{friend_name}' 的 UserName: {user_name}")
        return user_name

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
                # 打印所有群组的名字以供调试
                all_groups = itchat.get_chatrooms(update=True)
                all_group_names = [group['NickName'] for group in all_groups]
                logging.error(f"未找到群组: {group_name}. 当前群组列表: {all_group_names}")
                group_usernames[group_name] = None  # 防止后续上传时找不到群组
        return group_usernames

    def _fetch_user_or_group_username(self, name):
        """
        获取好友或群组的 UserName
        """
        # 尝试作为好友查找
        friends = itchat.search_friends(name=name)
        if friends:
            user_name = friends[0]['UserName']
            logging.info(f"找到好友 '{name}' 的 UserName: {user_name}")
            return user_name

        # 尝试作为群组查找
        groups = itchat.search_chatrooms(name=name)
        if groups:
            user_name = groups[0]['UserName']
            logging.info(f"找到群组 '{name}' 的 UserName: {user_name}")
            return user_name

        # 未找到
        logging.error(f"未找到好友或群组: {name}")
        return None

    def upload_group_id(self, recipient_name, soft_id):
        """
        接收群组或个人名称和 soft_id，并维护 soft_id 到 recipient_name 的映射
        """
        try:
            user_name = self._fetch_user_or_group_username(recipient_name)
            if not user_name:
                logging.error(f"接收者 '{recipient_name}' 的 UserName 未找到，无法映射。")
                return

            with self.lock:
                # 维护 soft_id 到 recipient_name 的映射
                self.softid_to_recipient[soft_id] = recipient_name
                logging.info(f"映射 soft_id {soft_id} 到接收者 '{recipient_name}'")
        except Exception as e:
            logging.error("维护 soft_id 到接收者映射时发生错误", exc_info=True)
            self.error_handler.handle_exception(e)

    def upload_file(self, file_path, soft_id):
        """
        根据 soft_id 查找接收者并上传文件
        """
        try:
            with self.lock:
                recipient_name = self.softid_to_recipient.get(soft_id)

            if not recipient_name:
                recipient_name = self.default_recipient
                logging.info(f"未找到 soft_id {soft_id} 对应的接收者，使用默认接收者 '{recipient_name}'")

            user_name = self._fetch_user_or_group_username(recipient_name)
            if not user_name:
                logging.error(f"接收者 '{recipient_name}' 的 UserName 未找到，无法上传文件。")
                return

            # 检查文件大小
            file_size = os.path.getsize(file_path)
            if file_size > self.alert_size:
                logging.warning(f"文件 {file_path} 大小超过25MB，发送提醒消息。")
                self.send_large_file_message(file_path, user_name)
                return  # 不进行上传

            # 上传文件
            for attempt in range(1, self.max_retries + 1):
                try:
                    logging.info(f"正在上传文件: {file_path} 至接收者: {recipient_name}，尝试次数: {attempt}")
                    itchat.send_file(file_path, toUserName=user_name)
                    logging.info(f"文件已上传至接收者: {recipient_name}")
                    time.sleep(1)  # 添加短暂的延迟，避免触发微信速率限制
                    return  # 上传成功，退出函数
                except Exception as e:
                    if attempt < self.max_retries:
                        logging.warning("上传失败，网络问题，稍后重试...")
                        time.sleep(self.retry_delay)
                    else:
                        logging.error("上传失败，网络问题")
                        self.error_handler.handle_exception(e)

        except Exception as e:
            logging.error("上传文件时发生错误", exc_info=True)
            self.error_handler.handle_exception(e)

    def send_large_file_message(self, file_path, user_name):
        """
        发送超过25MB的文件上传提醒消息到指定群组或个人账号。
        """
        try:
            filename = os.path.basename(file_path)
            message = f"{filename} 文件过大，无法通过微信发送。请使用其他方式传输。"

            itchat.send(message, toUserName=user_name)
            logging.info(f"发送提醒消息到接收者: {user_name} - {message}")
        except Exception as e:
            logging.error("发送提醒消息时发生网络问题", exc_info=True)
            self.error_handler.handle_exception(e)

    def load_counters(self):
        """
        从计数器配置文件中加载计数器数据
        """
        if os.path.exists(self.counts_file):
            try:
                with open(self.counts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.remaining_count = data.get('remaining_count', 711)
                    self.daily_download_counts = {
                        datetime.datetime.strptime(k, '%Y-%m-%d').date(): v
                        for k, v in data.get('daily_download_counts', {}).items()
                    }
                    logging.info("计数器数据已从配置文件加载")
            except Exception as e:
                logging.error(f"加载计数器配置文件时发生错误：{e}")
                # 如果加载失败，使用默认值
                self.remaining_count = 711
                self.daily_download_counts = {}
        else:
            logging.info("未找到计数器配置文件，使用默认计数器值")
            self.remaining_count = 711
            self.daily_download_counts = {}

    def save_counters(self):
        """
        将计数器数据保存到计数器配置文件
        """
        try:
            data = {
                'remaining_count': self.remaining_count,
                'daily_download_counts': {
                    k.strftime('%Y-%m-%d'): v for k, v in self.daily_download_counts.items()
                }
            }
            with open(self.counts_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logging.info("计数器数据已保存到配置文件")
        except Exception as e:
            logging.error(f"保存计数器配置文件时发生错误：{e}")

    def deduct_and_record(self):
        """
        扣除一份资料并记录下载量
        """
        now = datetime.datetime.now()
        download_date = self.get_download_date(now)

        # 更新每日下载量
        if download_date not in self.daily_download_counts:
            self.daily_download_counts[download_date] = 0
        self.daily_download_counts[download_date] += 1

        # 扣除剩余量
        self.remaining_count -= 1
        if self.remaining_count < 0:
            self.remaining_count = 0  # 确保不为负数

        logging.info(f"扣除一份资料。日期：{download_date}，下载量：{self.daily_download_counts[download_date]}，剩余量：{self.remaining_count}")

        # 保存计数器数据
        self.save_counters()

    def get_download_date(self, now):
        """
        根据当前时间获取下载计入的日期
        """
        cutoff_time = now.replace(hour=22, minute=30, second=0, microsecond=0)
        if now >= cutoff_time:
            # 10点半以后算作第二天的下载量
            return (now + datetime.timedelta(days=1)).date()
        else:
            # 10点半之前算作当天的下载量
            return now.date()

    # 保留每日通知系统，不需要修改
    def notification_scheduler(self):
        """
        定时器，每天晚上10点半发送通知
        """
        while True:
            now = datetime.datetime.now()
            next_notification_time = now.replace(hour=22, minute=30, second=0, microsecond=0)
            if now >= next_notification_time:
                # 如果当前时间已过10点半，定时到明天的10点半
                next_notification_time += datetime.timedelta(days=1)
            time_to_wait = (next_notification_time - now).total_seconds()
            hours, remainder = divmod(time_to_wait, 3600)
            minutes, seconds = divmod(remainder, 60)
            logging.info(f"等待 {int(hours)} 小时 {int(minutes)} 分钟 {int(seconds)} 秒后发送每日通知。")
            time.sleep(time_to_wait)
            self.send_daily_notification()

    def send_daily_notification(self):
        """
        发送每日下载量和剩余量的通知
        """
        now = datetime.datetime.now()
        # 获取要报告的日期（即当前日期的前一天，如果现在是10点半后，则报告当天的）
        report_date = self.get_download_date(now - datetime.timedelta(seconds=1))

        # 获取该日期的下载量
        download_count = self.daily_download_counts.get(report_date, 0)
        message = f"今天下载量是 {download_count}，剩余量是 {self.remaining_count}"

        # 发送到个人账号
        if self.error_recipient_username:
            try:
                itchat.send(message, toUserName=self.error_recipient_username)
                logging.info(f"发送每日通知到个人账号 '{self.error_recipient}': {message}")
            except Exception as e:
                logging.error("发送每日通知到个人账号时发生网络问题", exc_info=True)
                self.error_handler.handle_exception(e)

        # 发送完通知后，重置该日期的下载量
        if report_date in self.daily_download_counts:
            del self.daily_download_counts[report_date]

        # 保存计数器数据
        self.save_counters()