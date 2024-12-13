# src/uploader/uploader.py

import os
import logging
import threading
import queue
import time
from typing import Optional, List, Dict
from lib.wxautox.wxauto import WeChat
from src.point_manager import PointManager


class Uploader:
    def __init__(self, upload_config: Dict, error_notification_config: Dict, error_handler, point_manager: Optional[PointManager] = None):
        self.target_groups = upload_config.get('target_groups', [])
        self.target_individuals = upload_config.get('target_individuals', [])
        self.upload_config = upload_config
        self.processed_soft_ids = set()
        self.error_handler = error_handler
        self.max_retries = 3
        self.retry_delay = 5

        self.lock = threading.Lock()  # 确保线程安全

        # 维护 soft_id 到 recipient 和 sender 映射
        self.softid_to_recipient = {}
        self.softid_to_sender = {}  # 用于维护 soft_id 到发送者昵称的映射
        self.softid_to_group_type = {}  # 新增：维护 soft_id 到 group_type 的映射

        # 获取错误通知接收者
        self.error_recipient = error_notification_config.get('recipient')

        # 初始化上传任务队列
        self.upload_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.upload_thread = threading.Thread(target=self.process_uploads, daemon=True)
        self.upload_thread.start()
        logging.info("上传任务处理线程已启动")

        # 初始化文件删除队列和线程
        self.delete_queue = queue.Queue()
        self.delete_thread = threading.Thread(target=self.process_file_deletion, daemon=True)
        self.delete_thread.start()
        logging.info("文件删除线程已启动")

        # 初始化 wxauto WeChat 实例
        self.wx = WeChat()
        self.initialize_wechat()
        logging.info("wxauto WeChat 实例已初始化")

        # 初始化 PointManager
        self.point_manager = point_manager if point_manager else PointManager()
        logging.info("PointManager 已初始化")

    def add_file_to_delete(self, file_path):
        """将待删除的文件路径添加到删除队列"""
        self.delete_queue.put(file_path)
        logging.info(f"文件已添加到删除队列：{file_path}")

    def process_file_deletion(self):
        """处理文件删除的线程"""
        while not self.stop_event.is_set():
            try:
                file_path = self.delete_queue.get(timeout=1)
                time.sleep(30)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logging.info(f"已删除文件：{file_path}")
                else:
                    logging.warning(f"文件不存在，无法删除：{file_path}")
                self.delete_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"删除文件时发生错误：{e}", exc_info=True)
                self.error_handler.handle_exception(e)

    def update_config(self, new_upload_config):
        self.upload_config = new_upload_config
        logging.info("Uploader 配置已更新")

    def initialize_wechat(self):
        """
        确保微信客户端已运行，并切换到主页面。
        """
        self.wx.SwitchToChat()
        logging.info("已切换到微信聊天页面")
        time.sleep(1)  # 等待界面切换完成

    def upload_group_id(self, recipient_name: str, soft_id: str, sender_nickname: str = None, recipient_type: str = 'group', group_type: str = None):
        """
        接收群组或个人名称和 soft_id，并维护映射关系。
        recipient_type: 'group' 或 'individual'
        group_type: 'whole' 或 'non-whole'，仅当 recipient_type 为 'group' 时有效
        """
        with self.lock:
            # 维护 soft_id 到 recipient_name 的映射
            self.softid_to_recipient[soft_id] = recipient_name
            logging.info(f"映射 soft_id {soft_id} 到接收者 '{recipient_name}'")

            if sender_nickname:
                self.softid_to_sender[soft_id] = sender_nickname
                logging.info(f"映射 soft_id {soft_id} 到发送者 '{sender_nickname}'")

            if recipient_type == 'group':
                if group_type:
                    # 根据 group_type 确定是否为整体群组
                    is_whole = (group_type == 'whole')
                    self.point_manager.ensure_group(recipient_name, is_whole=is_whole)
                else:
                    # 默认设为整体群组
                    self.point_manager.ensure_group(recipient_name, is_whole=True)
                # 新增：维护 soft_id 到 group_type 的映射
                self.softid_to_group_type[soft_id] = group_type if group_type else 'whole'
            elif recipient_type == 'individual':
                # 使用新添加的 add_recipient 方法
                add_result = self.point_manager.add_recipient(recipient_name, initial_points=100)
                logging.info(add_result)
            if sender_nickname and recipient_type == 'group':
                self.point_manager.ensure_user(recipient_name, sender_nickname)

    def rename_file_with_id(self, file_path: str, soft_id: str) -> Optional[str]:
        """
        将文件名修改为 [soft_id]原文件名，如果已经重命名过，则不重复修改。
        """
        directory, original_filename = os.path.split(file_path)
        # 检查文件名是否已经包含 [soft_id] 前缀
        if original_filename.startswith(f"[{soft_id}]"):
            logging.info(f"文件 {file_path} 已经包含 soft_id 前缀，跳过重命名。")
            return file_path  # 已经重命名过，直接返回原路径

        new_filename = f"[{soft_id}]{original_filename}"
        new_file_path = os.path.join(directory, new_filename)

        if os.path.exists(new_file_path):
            logging.warning(f"目标文件 {new_file_path} 已存在，无法重命名 {file_path}")
            return None  # 返回 None 表示重命名失败

        try:
            os.rename(file_path, new_file_path)
            logging.info(f"已将文件 {file_path} 重命名为 {new_file_path}")
            return new_file_path
        except Exception as e:
            logging.error(f"重命名文件时发生错误：{e}", exc_info=True)
            self.error_handler.handle_exception(e)
            return None

    def add_upload_task(self, file_path: str, soft_id: str, recipient_type: str = 'group'):
        """
        添加上传任务前，先将文件重命名为 [soft_id]文件名。
        recipient_type: 'group' 或 'individual'
        """
        renamed_file_path = self.rename_file_with_id(file_path, soft_id)
        if renamed_file_path:
            with self.lock:
                self.processed_soft_ids.add(soft_id)
            self.upload_queue.put((renamed_file_path, soft_id, recipient_type))
            logging.info(f"添加上传任务: {renamed_file_path}, soft_id: {soft_id}, recipient_type: {recipient_type}")
        else:
            logging.error(f"文件重命名失败，无法添加上传任务: {file_path}, soft_id: {soft_id}")

    def process_uploads(self):
        """
        处理上传队列中的任务，支持批量发送。
        """
        recipient_tasks = {}
        last_send_time = time.time()
        batch_interval = 5  # 批量发送的时间间隔，单位：秒

        while not self.stop_event.is_set():
            try:
                # 从队列中获取任务
                file_path, soft_id, recipient_type = self.upload_queue.get(timeout=1)
                with self.lock:
                    recipient_name = self.softid_to_recipient.get(soft_id)
                    sender_nickname = self.softid_to_sender.get(soft_id)
                    group_type = self.softid_to_group_type.get(soft_id)

                if not recipient_name:
                    logging.error(f"未找到 soft_id {soft_id} 对应的接收者。")
                    continue

                # 将任务添加到 recipient_tasks 中
                if recipient_name not in recipient_tasks:
                    recipient_tasks[recipient_name] = []
                recipient_tasks[recipient_name].append({
                    'file_path': file_path,
                    'soft_id': soft_id,
                    'recipient_type': recipient_type,
                    'sender_nickname': sender_nickname,
                    'group_type': group_type
                })
                self.upload_queue.task_done()

                # 检查是否需要批量发送
                current_time = time.time()
                if (current_time - last_send_time >= batch_interval) or \
                        any(len(tasks) >= self.upload_config.get('batch_size', 5) for tasks in
                            recipient_tasks.values()):
                    # 批量发送
                    for recipient_name, tasks in recipient_tasks.items():
                        self.upload_files(recipient_name, tasks)
                    # 清空 recipient_tasks
                    recipient_tasks.clear()
                    last_send_time = current_time

            except queue.Empty:
                # 队列为空，检查是否有待发送的任务
                current_time = time.time()
                if recipient_tasks and (current_time - last_send_time >= batch_interval):
                    for recipient_name, tasks in recipient_tasks.items():
                        self.upload_files(recipient_name, tasks)
                    recipient_tasks.clear()
                    last_send_time = current_time
                continue
            except Exception as e:
                logging.error(f"处理上传任务时出错：{e}", exc_info=True)
                self.error_handler.handle_exception(e)

    def upload_files(self, recipient_name, tasks):
        try:
            max_total_retries = self.max_retries * 2  # 允许最多双倍的重试次数
            attempt = 1
            while attempt <= max_total_retries:
                try:
                    if attempt == self.max_retries + 1:
                        # 在初始 max_retries 次尝试后，重新激活聊天窗口
                        self.wx.ChatWith(who=recipient_name)
                        logging.info(f"重新激活接收者 '{recipient_name}' 的聊天窗口")
                        time.sleep(0.5)  # 等待窗口激活完成

                    logging.info(
                        f"正在上传文件至接收者：{recipient_name}，文件数：{len(tasks)}，尝试次数：{attempt}")
                    for task in tasks:
                        file_path = task['file_path']
                        self.wx.SendFiles(filepath=file_path, who=recipient_name)
                        logging.info(f"已上传文件：{file_path}")
                        # 扣除积分并处理文件删除
                        self.deduct_points(
                            recipient_name=recipient_name,
                            sender_nickname=task['sender_nickname'],
                            recipient_type=task['recipient_type'],
                            group_type=task['group_type']
                        )
                        # 将文件路径添加到删除队列
                        self.add_file_to_delete(file_path)

                        # 记录下载事件
                        link = f"file://{os.path.abspath(file_path)}"  # 根据实际情况生成链接
                        recipient_type = 'whole_group' if task['group_type'] == 'whole' else 'non_whole_group' if task[
                                                                                                                      'group_type'] == 'non-whole' else 'individual'
                        self.point_manager.log_download(
                            recipient_type=recipient_type,
                            recipient_name=recipient_name,
                            link=link
                        )

                    break  # 上传成功，退出循环
                except Exception as e:
                    if attempt < max_total_retries:
                        logging.warning(f"上传失败，稍后重试... (尝试次数：{attempt}) - 错误：{e}")
                        time.sleep(self.retry_delay)
                        attempt += 1
                    else:
                        logging.error(f"上传失败 (接收者: {recipient_name}) - 错误：{e}")
                        self.error_handler.handle_exception(e)
                        break
        except Exception as e:
            logging.error(f"批量上传文件时发生错误 (接收者: {recipient_name}) - 错误：{e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def deduct_points(self, recipient_name: str, sender_nickname: Optional[str] = None, recipient_type: str = 'group', group_type: Optional[str] = None):
        """
        扣除积分。
        """
        try:
            if recipient_type == 'group':
                # 检查群组类型
                if not group_type:
                    # 如果 group_type 未提供，尝试从数据库获取
                    group_info = self.point_manager.get_group_info(recipient_name)
                    if group_info:
                        group_type = 'whole' if group_info['is_whole'] else 'non-whole'
                    else:
                        logging.error(f"群组 '{recipient_name}' 信息未找到，无法扣除积分。")
                        return

                if group_type == 'whole':
                    # 整体性群组，从群组中扣除积分
                    success = self.point_manager.deduct_whole_group_points(recipient_name, points=1)
                    if success:
                        logging.info(f"已从整体性群组 '{recipient_name}' 中扣除积分。")
                    else:
                        logging.warning(f"从整体性群组 '{recipient_name}' 中扣除积分失败。")
                elif group_type == 'non-whole':
                    # 非整体性群组，从发送者中扣除积分
                    if sender_nickname:
                        success = self.point_manager.deduct_user_points(recipient_name, sender_nickname, points=1)
                        if success:
                            logging.info(f"已从非整体性群组 '{recipient_name}' 的成员 '{sender_nickname}' 中扣除积分。")
                        else:
                            logging.warning(f"从非整体性群组 '{recipient_name}' 的成员 '{sender_nickname}' 中扣除积分失败。")
                    else:
                        logging.error("缺少发送者昵称，无法从非整体性群组成员中扣除积分。")
                else:
                    logging.error(f"未知的群组类型 '{group_type}'，无法扣除积分。")
            elif recipient_type == 'individual':
                # 个人用户，从个人接收者中扣除积分
                success = self.point_manager.deduct_recipient_points(recipient_name, points=1)
                if success:
                    logging.info(f"已从个人接收者 '{recipient_name}' 中扣除积分。")
                else:
                    logging.warning(f"从个人接收者 '{recipient_name}' 中扣除积分失败。")
        except Exception as e:
            logging.error(f"扣除积分时发生错误：{e}", exc_info=True)
            self.error_handler.handle_exception(e)

    def add_recipient(self, recipient_name: str, initial_count: int) -> str:
        """
        添加一个新的接收者（群组或个人）。
        """
        return self.point_manager.add_recipient(recipient_name, initial_points=initial_count)

    def delete_recipient(self, recipient_name: str) -> str:
        """
        删除一个接收者（群组或个人）。
        """
        success = self.point_manager.delete_recipient(recipient_name)
        if success:
            return f"接收者 '{recipient_name}' 已删除。"
        else:
            return f"接收者 '{recipient_name}' 删除失败或不存在。"

    def update_remaining_count(self, recipient_name: str, count_change: int) -> str:
        """
        更新接收者（群组或个人）的剩余积分。
        """
        success = self.point_manager.update_recipient_points(recipient_name, count_change)
        if success:
            return f"接收者 '{recipient_name}' 的剩余积分已更新，变化量为 {count_change}。"
        else:
            return f"接收者 '{recipient_name}' 的积分更新失败。"

    def get_recipient_info(self, recipient_name: str) -> Optional[dict]:
        """
        获取指定接收者（群组或个人）的信息。
        """
        return self.point_manager.get_recipient_info(recipient_name)

    def get_all_recipients(self) -> List[str]:
        """
        获取所有接收者（群组或个人）的名称列表。
        """
        return self.point_manager.get_all_recipients()

    def stop(self):
        """停止上传线程并清理资源。"""
        self.stop_event.set()
        self.upload_thread.join()
        self.delete_thread.join()  # 确保文件删除线程正常关闭
        self.point_manager.close()
        logging.info("Uploader 已停止并清理资源")

    def __del__(self):
        self.stop()
