import os
import logging
import datetime
from wxauto.wxauto import WeChat
import threading
import time
import queue
import sqlite3
from typing import Optional, List, Dict


class Uploader:
    def __init__(self, upload_config: Dict, error_notification_config: Dict, error_handler):
        self.target_groups = upload_config.get('target_groups', [])
        self.target_individuals = upload_config.get('target_individuals', [])
        self.processed_soft_ids = set()
        self.error_handler = error_handler
        self.group_names = self.target_groups
        self.individual_names = self.target_individuals
        self.max_retries = 3
        self.retry_delay = 5

        # 数据库配置
        self.db_path = upload_config.get('database_path', 'counters.db')
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.initialize_database()
        logging.info("SQLite 数据库已初始化")

        # 维护 soft_id 到 recipient 映射
        self.softid_to_recipient = {}
        self.lock = threading.Lock()  # 确保线程安全

        # 获取错误通知接收者
        self.error_recipient = error_notification_config.get('recipient')

        # 初始化上传任务队列
        self.upload_queue = queue.Queue()
        self.upload_thread = threading.Thread(target=self.process_uploads, daemon=True)
        self.upload_thread.start()
        logging.info("上传任务处理线程已启动")

        # 启动每日通知调度器
        notification_thread = threading.Thread(target=self.notification_scheduler, daemon=True)
        notification_thread.start()
        logging.info("每日通知调度线程已启动")

        # 初始化 wxauto WeChat 实例
        self.wx = WeChat()
        self.initialize_wechat()
        logging.info("wxauto WeChat 实例已初始化")

    def initialize_database(self):
        """
        如果表不存在，则创建它们。
        """
        try:
            # 创建 recipients 表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS recipients (
                    name TEXT PRIMARY KEY,
                    remaining_count INTEGER DEFAULT 711
                )
            ''')

            # 创建 daily_downloads 表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_downloads (
                    recipient_name TEXT,
                    download_date DATE,
                    download_count INTEGER DEFAULT 0,
                    PRIMARY KEY (recipient_name, download_date),
                    FOREIGN KEY (recipient_name) REFERENCES recipients(name)
                )
            ''')

            self.conn.commit()
            logging.info("数据库表已创建或已存在")
        except Exception as e:
            logging.error(f"初始化数据库时出错：{e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def initialize_wechat(self):
        """
        确保微信客户端已运行，并切换到主页面。
        """
        try:
            self.wx.SwitchToChat()
            logging.info("已切换到微信聊天页面")
            time.sleep(1)  # 等待界面切换完成
        except Exception as e:
            logging.error(f"初始化微信界面时发生错误：{e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def _fetch_user_or_group_name(self, name: str) -> Optional[str]:
        """
        确认接收者名称是否在目标列表中。
        """
        if name in self.group_names or name in self.individual_names:
            return name
        else:
            logging.error(f"接收者 '{name}' 不在目标群组或个人列表中。")
            return None

    def upload_group_id(self, recipient_name: str, soft_id: str):
        """
        接收群组或个人名称和 soft_id，并维护映射关系。
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

                # 确保接收者存在于数据库中
                self.cursor.execute('''
                    INSERT OR IGNORE INTO recipients (name, remaining_count)
                    VALUES (?, 711)
                ''', (recipient_name,))
                self.conn.commit()
        except Exception as e:
            logging.error("维护 soft_id 到接收者映射时发生错误", exc_info=True)
            self.error_handler.handle_exception(e)

    def add_upload_task(self, file_path: str, soft_id: str):
        with self.lock:
            self.processed_soft_ids.add(soft_id)
        self.upload_queue.put((file_path, soft_id))
        logging.info(f"添加上传任务: {file_path}, soft_id: {soft_id}")

    def process_uploads(self):
        """
        处理上传队列中的任务。
        """
        while True:
            try:
                file_path, soft_id = self.upload_queue.get()
                self.upload_file(file_path, soft_id)
                self.upload_queue.task_done()
            except Exception as e:
                logging.error(f"处理上传任务时出错：{e}", exc_info=True)
                self.error_handler.handle_exception(e)

    def upload_file(self, file_path: str, soft_id: str):
        try:
            if not os.path.exists(file_path):
                logging.error(f"文件不存在，无法上传：{file_path}")
                return

            with self.lock:
                recipient_name = self.softid_to_recipient.get(soft_id)

            if not recipient_name:
                logging.error(f"未找到 soft_id {soft_id} 对应的接收者。")
                return

            # 确认接收者存在
            user_name = recipient_name  # 因为已经确认在目标列表中，无需再次判断

            # 切换到指定的聊天窗口
            try:
                self.wx.ChatWith(who=user_name)
                logging.info(f"切换到接收者 '{user_name}' 的聊天窗口")
                time.sleep(1)  # 等待界面切换完成
            except Exception as e:
                logging.error(f"切换聊天窗口失败：{e}", exc_info=True)
                self.error_handler.handle_exception(e)
                return

            # 发送文件，带重试机制
            for attempt in range(1, self.max_retries + 1):
                try:
                    logging.info(
                        f"正在上传文件：{file_path} 至接收者：{user_name} (soft_id: {soft_id})，尝试次数：{attempt}")
                    self.wx.SendFiles(filepath=file_path, who=user_name)
                    logging.info(f"文件已上传至接收者：{user_name} (soft_id: {soft_id})")
                    time.sleep(1)  # 添加短暂的延迟，避免触发微信速率限制

                    # 文件上传成功后删除文件
                    self.delete_file(file_path)

                    # 扣除并记录下载量
                    self.deduct_and_record(user_name)

                    return  # 上传成功，退出函数
                except Exception as e:
                    if attempt < self.max_retries:
                        logging.warning(f"上传失败，网络问题，稍后重试... (尝试次数：{attempt}) - 错误：{e}")
                        time.sleep(self.retry_delay)
                    else:
                        logging.error(f"上传失败，网络问题 (soft_id: {soft_id}) - 错误：{e}")
                        self.error_handler.handle_exception(e)
                        # 上传失败后不删除文件，以便后续重试或手动处理
        except Exception as e:
            logging.error(f"上传文件时发生错误 (soft_id: {soft_id}, file_path: {file_path}) - 错误：{e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def delete_file(self, file_path: str):
        """
        删除指定的文件。
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"删除文件：{file_path}")
            else:
                logging.warning(f"尝试删除的文件不存在：{file_path}")
        except Exception as e:
            logging.error(f"删除文件 {file_path} 时发生错误：{e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def deduct_and_record(self, recipient_name: str):
        """
        扣除一次下载量并在数据库中记录。
        """
        now = datetime.datetime.now()
        download_date = self.get_download_date(now)

        with self.lock:
            try:
                # 确保接收者存在于 recipients 表中
                self.cursor.execute('''
                    INSERT OR IGNORE INTO recipients (name, remaining_count)
                    VALUES (?, 711)
                ''', (recipient_name,))

                # 扣除剩余次数
                self.cursor.execute('''
                    UPDATE recipients
                    SET remaining_count = remaining_count - 1
                    WHERE name = ? AND remaining_count > 0
                ''', (recipient_name,))

                # 记录下载次数
                self.cursor.execute('''
                    INSERT INTO daily_downloads (recipient_name, download_date, download_count)
                    VALUES (?, ?, 1)
                    ON CONFLICT(recipient_name, download_date) DO UPDATE SET
                        download_count = download_count + 1
                ''', (recipient_name, download_date))

                self.conn.commit()

                # 获取更新后的剩余次数和下载次数
                self.cursor.execute('''
                    SELECT remaining_count FROM recipients WHERE name = ?
                ''', (recipient_name,))
                remaining = self.cursor.fetchone()[0]

                self.cursor.execute('''
                    SELECT download_count FROM daily_downloads
                    WHERE recipient_name = ? AND download_date = ?
                ''', (recipient_name, download_date))
                download = self.cursor.fetchone()[0]

                logging.info(
                    f"扣除一次下载量。接收者：{recipient_name}，日期：{download_date}，下载量：{download}，剩余量：{remaining}"
                )
            except Exception as e:
                logging.error(f"扣除并记录时出错：{e}", exc_info=True)
                self.error_handler.handle_exception(e)

    def get_download_date(self, now: datetime.datetime) -> datetime.date:
        """
        根据当前时间获取下载计入的日期。
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
        定时器，每天晚上10点半发送通知。
        """
        while True:
            try:
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
            except Exception as e:
                logging.error(f"通知调度器发生错误：{e}", exc_info=True)
                self.error_handler.handle_exception(e)
                # 在发生异常后，继续循环
                time.sleep(60)

    def send_daily_notification(self):
        """
        发送每日下载量和剩余量的通知。
        """
        now = datetime.datetime.now()
        # 获取报告日期（即当前日期的前一天，如果现在是10点半后，则报告当天的）
        report_date = self.get_download_date(now - datetime.timedelta(seconds=1))

        with self.lock:
            try:
                # 获取所有接收者
                self.cursor.execute('SELECT name, remaining_count FROM recipients')
                recipients = self.cursor.fetchall()

                for recipient_name, remaining_count in recipients:
                    # 获取报告日期的下载次数
                    self.cursor.execute('''
                        SELECT download_count FROM daily_downloads
                        WHERE recipient_name = ? AND download_date = ?
                    ''', (recipient_name, report_date))
                    result = self.cursor.fetchone()
                    download_count = result[0] if result else 0

                    message = f"今天下载量是 {download_count}，剩余量是 {remaining_count}"

                    # 通过微信发送消息
                    try:
                        self.wx.ChatWith(who=recipient_name)
                        time.sleep(1)  # 等待界面切换完成
                        self.wx.SendMsg(msg=message, who=recipient_name)
                        logging.info(f"发送每日通知到接收者 '{recipient_name}'：{message}")
                    except Exception as e:
                        logging.error(f"发送每日通知到接收者 '{recipient_name}' 时发生错误：{e}", exc_info=True)
                        self.error_handler.handle_exception(e)

                    # 重置当天的下载次数
                    self.cursor.execute('''
                        DELETE FROM daily_downloads
                        WHERE recipient_name = ? AND download_date = ?
                    ''', (recipient_name, report_date))

                self.conn.commit()
                logging.info("每日通知已发送并重置下载计数")
            except Exception as e:
                logging.error(f"发送每日通知时出错：{e}", exc_info=True)
                self.error_handler.handle_exception(e)

    # 新增的方法以支持管理员命令

    def add_recipient(self, recipient_name: str, initial_count: int) -> str:
        """
        添加一个新的接收者。
        """
        try:
            with self.lock:
                self.cursor.execute('''
                    INSERT INTO recipients (name, remaining_count)
                    VALUES (?, ?)
                ''', (recipient_name, initial_count))
                self.conn.commit()
            return f"接收者 '{recipient_name}' 已添加，初始剩余次数为 {initial_count}。"
        except sqlite3.IntegrityError:
            return f"接收者 '{recipient_name}' 已存在。"
        except Exception as e:
            logging.error(f"添加接收者时出错: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return f"添加接收者时发生错误: {e}"

    def delete_recipient(self, recipient_name: str) -> str:
        """
        删除一个接收者。
        """
        try:
            with self.lock:
                self.cursor.execute('''
                    DELETE FROM recipients WHERE name = ?
                ''', (recipient_name,))
                if self.cursor.rowcount == 0:
                    return f"接收者 '{recipient_name}' 不存在。"
                self.conn.commit()
            return f"接收者 '{recipient_name}' 已删除。"
        except Exception as e:
            logging.error(f"删除接收者时出错: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return f"删除接收者时发生错误: {e}"

    def update_remaining_count(self, recipient_name: str, count_change: int) -> str:
        """
        更新接收者的剩余次数。
        """
        try:
            with self.lock:
                self.cursor.execute('''
                    UPDATE recipients
                    SET remaining_count = remaining_count + ?
                    WHERE name = ?
                ''', (count_change, recipient_name))
                if self.cursor.rowcount == 0:
                    return f"接收者 '{recipient_name}' 不存在。"
                self.conn.commit()
            return f"接收者 '{recipient_name}' 的剩余次数已更新，变化量为 {count_change}。"
        except Exception as e:
            logging.error(f"更新剩余次数时出错: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return f"更新剩余次数时发生错误: {e}"

    def get_recipient_info(self, recipient_name: str) -> Optional[dict]:
        """
        获取指定接收者的信息。
        """
        try:
            with self.lock:
                self.cursor.execute('''
                    SELECT name, remaining_count FROM recipients WHERE name = ?
                ''', (recipient_name,))
                row = self.cursor.fetchone()
                if row:
                    return {'name': row[0], 'remaining_count': row[1]}
                else:
                    return None
        except Exception as e:
            logging.error(f"获取接收者信息时出错: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return None

    def get_all_recipients(self) -> List[str]:
        """
        获取所有接收者的名称列表。
        """
        try:
            with self.lock:
                self.cursor.execute('''
                    SELECT name FROM recipients
                ''')
                rows = self.cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logging.error(f"获取所有接收者时出错: {e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return []

    def __del__(self):
        try:
            self.conn.close()
            logging.info("SQLite 数据库连接已关闭")
        except Exception as e:
            logging.error(f"关闭数据库连接时出错：{e}", exc_info=True)
            self.error_handler.handle_exception(e)
