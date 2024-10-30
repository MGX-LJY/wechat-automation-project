# src/file_upload/uploader.py

import os
import json
import logging
import datetime
from wxauto import Wechat
import threading
import time
import queue

class Uploader:
    def __init__(self, upload_config, error_notification_config, error_handler):
        self.target_groups = upload_config.get('target_groups', [])
        self.target_individuals = upload_config.get('target_individuals', [])
        self.processed_soft_ids = set()
        self.error_handler = error_handler
        self.group_names = self.target_groups
        self.individual_names = self.target_individuals
        self.max_retries = 3
        self.retry_delay = 5

        # 计数器配置文件路径
        self.counts_file = upload_config.get('counts_file', 'counts.json')

        # 从计数器配置文件中加载计数器数据
        self.load_counters()

        # 维护 soft_id 到 recipient（群组或个人）的映射
        self.softid_to_recipient = {}
        self.lock = threading.Lock()  # 添加锁以确保线程安全

        # 获取错误通知的个人账号名称
        self.error_recipient = error_notification_config.get('recipient')

        # 初始化上传任务队列
        self.upload_queue = queue.Queue()
        self.upload_thread = threading.Thread(target=self.process_uploads, daemon=True)
        self.upload_thread.start()
        logging.info("上传任务处理线程已启动")

        # 保留每日通知系统
        notification_thread = threading.Thread(target=self.notification_scheduler, daemon=True)
        notification_thread.start()
        logging.info("每日通知调度线程已启动")

        # 初始化 wxauto WeChat 实例
        self.wx = Wechat()
        self.initialize_wechat()
        logging.info("wxauto WeChat 实例已初始化")

        # 确保微信已运行
        if not self.wx.IsWechatRunning():
            logging.error("微信客户端未运行。请确保微信已启动并登录。")
            raise RuntimeError("微信客户端未运行。请确保微信已启动并登录。")

    def initialize_wechat(self):
        """
        确保微信客户端已运行，并切换到主页面
        """
        try:
            self.wx.SwitchToChat()
            logging.info("已切换到微信聊天页面")
            time.sleep(1)  # 等待界面切换完成
        except Exception as e:
            logging.error(f"初始化微信界面时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def _fetch_user_or_group_name(self, name):
        """
        确认接收者名称是否在目标列表中
        """
        if name in self.group_names or name in self.individual_names:
            return name
        else:
            logging.error(f"接收者 '{name}' 不在目标群组或个人列表中。")
            return None

    def upload_group_id(self, recipient_name, soft_id):
        """
        接收群组或个人名称和 soft_id，并维护 soft_id 到 recipient_name 的映射
        """
        try:
            user_name = self._fetch_user_or_group_name(recipient_name)
            if not user_name:
                logging.error(f"接收者 '{recipient_name}' 的名称未找到，无法映射。")
                return

            with self.lock:
                # 维护 soft_id 到 recipient_name 的映射
                self.softid_to_recipient[soft_id] = recipient_name
                logging.info(f"映射 soft_id {soft_id} 到接收者 '{recipient_name}'")
        except Exception as e:
            logging.error("维护 soft_id 到接收者映射时发生错误", exc_info=True)
            self.error_handler.handle_exception(e)

    def add_upload_task(self, file_path, soft_id):
        with self.lock:
            self.processed_soft_ids.add(soft_id)
        self.upload_queue.put((file_path, soft_id))
        logging.info(f"添加上传任务: {file_path}, soft_id: {soft_id}")

    def process_uploads(self):
        """
        处理上传队列中的任务
        """
        while True:
            try:
                file_path, soft_id = self.upload_queue.get()
                self.upload_file(file_path, soft_id)
                self.upload_queue.task_done()
            except Exception as e:
                logging.error(f"处理上传任务时出错: {e}", exc_info=True)
                self.error_handler.handle_exception(e)

    def upload_file(self, file_path, soft_id):
        try:
            if not os.path.exists(file_path):
                logging.error(f"文件不存在，无法上传: {file_path}")
                return

            with self.lock:
                recipient_name = self.softid_to_recipient.get(soft_id)

            if not recipient_name:
                logging.error(f"未找到 soft_id {soft_id} 对应的接收者。")
                return

            # 确认接收者存在
            if recipient_name in self.group_names:
                user_name = recipient_name
            else:
                user_name = recipient_name

            # 切换到指定的聊天窗口
            try:
                self.wx.ChatWith(who=user_name)
                logging.info(f"切换到接收者 '{user_name}' 的聊天窗口")
                time.sleep(1)  # 等待界面切换完成
            except Exception as e:
                logging.error(f"切换聊天窗口失败: {e}", exc_info=True)
                self.error_handler.handle_exception(e)
                return

            # 发送文件
            for attempt in range(1, self.max_retries + 1):
                try:
                    logging.info(f"正在上传文件: {file_path} 至接收者: {user_name} (soft_id: {soft_id})，尝试次数: {attempt}")
                    self.wx.SendFiles(filepath=file_path, who=user_name)
                    logging.info(f"文件已上传至接收者: {user_name} (soft_id: {soft_id})")
                    time.sleep(1)  # 添加短暂的延迟，避免触发微信速率限制

                    # 文件上传成功后删除文件
                    self.delete_file(file_path)

                    # 扣除并记录下载量
                    self.deduct_and_record(user_name)

                    return  # 上传成功，退出函数
                except Exception as e:
                    if attempt < self.max_retries:
                        logging.warning(f"上传失败，网络问题，稍后重试... (尝试次数: {attempt}) - 错误: {e}")
                        time.sleep(self.retry_delay)
                    else:
                        logging.error(f"上传失败，网络问题 (soft_id: {soft_id}) - 错误: {e}")
                        self.error_handler.handle_exception(e)
                        # 上传失败后不删除文件，以便后续重试或手动处理
        except Exception as e:
            logging.error(f"上传文件时发生错误 (soft_id: {soft_id}, file_path: {file_path}) - 错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def delete_file(self, file_path):
        """
        删除指定的文件
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"删除文件: {file_path}")
            else:
                logging.warning(f"尝试删除的文件不存在: {file_path}")
        except Exception as e:
            logging.error(f"删除文件 {file_path} 时发生错误: {e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def load_counters(self):
        """
        从计数器配置文件中加载计数器数据
        """
        if os.path.exists(self.counts_file):
            try:
                with open(self.counts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 初始化 recipients 数据结构
                    self.recipients_counters = data.get('recipients', {})
                    # 将日期字符串转换为 date 对象
                    for recipient, counters in self.recipients_counters.items():
                        counters['daily_download_counts'] = {
                            datetime.datetime.strptime(k, '%Y-%m-%d').date(): v
                            for k, v in counters.get('daily_download_counts', {}).items()
                        }
                    logging.info("计数器数据已从配置文件加载")
            except Exception as e:
                logging.error(f"加载计数器配置文件时发生错误：{e}")
                # 如果加载失败，初始化为空
                self.recipients_counters = {}
        else:
            logging.info("未找到计数器配置文件，使用默认计数器值")
            self.recipients_counters = {}

    def save_counters(self):
        """
        将计数器数据保存到计数器配置文件
        """
        try:
            data = {
                'recipients': {
                    recipient: {
                        'remaining_count': counters.get('remaining_count', 711),
                        'daily_download_counts': {
                            k.strftime('%Y-%m-%d'): v for k, v in counters.get('daily_download_counts', {}).items()
                        }
                    }
                    for recipient, counters in self.recipients_counters.items()
                }
            }
            with open(self.counts_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logging.info("计数器数据已保存到配置文件")
        except Exception as e:
            logging.error(f"保存计数器配置文件时发生错误：{e}")

    def deduct_and_record(self, recipient_name):
        """
        扣除一份资料并记录下载量
        """
        now = datetime.datetime.now()
        download_date = self.get_download_date(now)

        with self.lock:
            # 初始化接收者的计数器数据
            if recipient_name not in self.recipients_counters:
                self.recipients_counters[recipient_name] = {
                    'remaining_count': 711,
                    'daily_download_counts': {}
                }

            counters = self.recipients_counters[recipient_name]

            # 更新每日下载量
            if download_date not in counters['daily_download_counts']:
                counters['daily_download_counts'][download_date] = 0
            counters['daily_download_counts'][download_date] += 1

            # 扣除剩余量
            counters['remaining_count'] -= 1
            if counters['remaining_count'] < 0:
                counters['remaining_count'] = 0  # 确保不为负数

            logging.info(
                f"扣除一份资料。接收者：{recipient_name}，日期：{download_date}，下载量：{counters['daily_download_counts'][download_date]}，剩余量：{counters['remaining_count']}"
            )

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

        with self.lock:
            for recipient_name, counters in self.recipients_counters.items():
                # 获取该日期的下载量
                download_count = counters['daily_download_counts'].get(report_date, 0)
                message = f"今天下载量是 {download_count}，剩余量是 {counters['remaining_count']}"

                # 发送到群组或个人账号
                try:
                    self.wx.ChatWith(who=recipient_name)
                    time.sleep(1)  # 等待界面切换完成
                    self.wx.SendMsg(msg=message, who=recipient_name)
                    logging.info(f"发送每日通知到接收者 '{recipient_name}': {message}")
                except Exception as e:
                    logging.error(f"发送每日通知到接收者 '{recipient_name}' 时发生网络问题", exc_info=True)
                    self.error_handler.handle_exception(e)

                # 发送完通知后，重置该日期的下载量
                if report_date in counters['daily_download_counts']:
                    del counters['daily_download_counts'][report_date]

            # 保存计数器数据
            self.save_counters()
