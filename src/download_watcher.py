# src/download_watcher.py

import os
import logging
import time
import threading
from watchdog.observers.polling import PollingObserver  # 使用 PollingObserver
from watchdog.events import FileSystemEventHandler
import traceback

class DownloadEventHandler(FileSystemEventHandler):
    def __init__(self, upload_callback, allowed_extensions=None, temporary_extensions=None, stable_time=5):
        super().__init__()
        self.upload_callback = upload_callback
        self.allowed_extensions = allowed_extensions or [
            '.pdf', '.docx', '.doc', '.xlsx',
            '.ppt', '.pptx',
            '.zip', '.rar', '.7z',
            '.mp4', '.avi', '.mkv',
            '.mp3', '.wav', '.aac',
            '.tar', '.gz', '.bz2',
            '.mov', '.flv', '.wmv'
        ]
        self.temporary_extensions = temporary_extensions or [
            '.crdownload', '.part', '.tmp', '.download'
        ]
        self.stable_time = stable_time  # 文件大小稳定的等待时间，单位：秒
        self.files_in_progress = {}

    def on_any_event(self, event):
        # 捕捉所有类型的事件并记录
        if not event.is_directory:
            event_type = event.event_type
            file_path = event.src_path
            logging.debug(f"捕捉到事件: {event_type} - 文件路径: {file_path}")

    def on_created(self, event):
        if not event.is_directory:
            file_path = event.src_path
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()

            if ext in self.temporary_extensions:
                logging.debug(f"忽略临时文件创建: {file_path}")
                return

            if ext not in self.allowed_extensions:
                logging.debug(f"文件 {file_path} 不在允许的类型中，跳过")
                return

            logging.info(f"检测到新文件: {file_path}")
            # 启动一个线程来监控文件稳定性
            threading.Thread(target=self._wait_for_file_stable, args=(file_path,), daemon=True).start()

    def on_moved(self, event):
        if not event.is_directory:
            src_path = event.src_path
            dest_path = event.dest_path
            logging.debug(f"文件移动事件: 从 {src_path} 到 {dest_path}")

            _, ext = os.path.splitext(dest_path)
            ext = ext.lower()

            if ext in self.temporary_extensions:
                logging.debug(f"忽略临时文件移动: {dest_path}")
                return

            if ext not in self.allowed_extensions:
                logging.debug(f"文件 {dest_path} 不在允许的类型中，跳过")
                return

            logging.info(f"检测到移动后的新文件: {dest_path}")
            threading.Thread(target=self._wait_for_file_stable, args=(dest_path,), daemon=True).start()

    def on_modified(self, event):
        if not event.is_directory:
            file_path = event.src_path
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()

            if ext in self.temporary_extensions:
                logging.debug(f"忽略临时文件修改: {file_path}")
                return

            if ext not in self.allowed_extensions:
                logging.debug(f"文件 {file_path} 不在允许的类型中，跳过")
                return

            # 如果文件已经在监控中，更新最后修改时间
            if file_path in self.files_in_progress:
                self.files_in_progress[file_path] = time.time()
                logging.debug(f"更新文件监控时间: {file_path}")

    def _wait_for_file_stable(self, file_path):
        logging.debug(f"开始监控文件稳定性: {file_path}")
        self.files_in_progress[file_path] = time.time()

        while True:
            current_time = time.time()
            last_modified = self.files_in_progress.get(file_path, current_time)
            if current_time - last_modified > self.stable_time:
                # 文件已稳定
                del self.files_in_progress[file_path]
                logging.info(f"文件下载完成且稳定: {file_path}")
                self.upload_callback(file_path)
                break
            time.sleep(1)  # 每秒检查一次

class DownloadWatcher:
    def __init__(self, download_path, upload_callback, allowed_extensions=None, temporary_extensions=None, stable_time=5):
        self.download_path = os.path.abspath(download_path)
        self.upload_callback = upload_callback
        self.allowed_extensions = allowed_extensions or [
            '.pdf', '.docx', '.xlsx',
            '.ppt', '.pptx',
            '.zip', '.rar', '.7z',
            '.mp4', '.avi', '.mkv',
            '.mp3', '.wav', '.aac',
            '.tar', '.gz', '.bz2',
            '.mov', '.flv', '.wmv'
        ]
        self.temporary_extensions = temporary_extensions or [
            '.crdownload', '.part', '.tmp', '.download'
        ]
        self.stable_time = stable_time
        self.observer = PollingObserver()  # 使用 PollingObserver
        self.event_handler = DownloadEventHandler(
            self.upload_callback,
            allowed_extensions=self.allowed_extensions,
            temporary_extensions=self.temporary_extensions,
            stable_time=self.stable_time
        )

    def start(self):
        try:
            self.observer.schedule(
                self.event_handler,
                self.download_path,
                recursive=False
            )
            self.observer.start()
            logging.info(f"开始监控下载目录: {self.download_path}")
            # 保持线程运行
            while True:
                time.sleep(1)
        except Exception as e:
            logging.error(f"无法启动下载监控: {e}", exc_info=True)
            self.observer.stop()
        finally:
            self.observer.join()

    def stop(self):
        self.observer.stop()
        self.observer.join()
        logging.info("停止监控下载目录")
