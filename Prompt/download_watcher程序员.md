## `download_watcher.py` 模块概述

`download_watcher.py` 模块负责监控指定的下载目录，检测新下载的文件，并在文件下载完成且稳定后触发上传流程。该模块使用 `watchdog` 库来监听文件系统事件，确保系统能够及时响应新文件的生成和完成下载。

### 类：`DownloadEventHandler`

#### 主要职责
- **监听文件系统事件**：捕捉文件的创建、移动和修改事件。
- **过滤文件类型**：仅处理允许的文件扩展名，忽略临时文件和不相关的文件。
- **监控文件稳定性**：确保文件在一定时间内大小保持不变，确认下载完成。
- **触发上传回调**：当文件稳定后，调用上传回调函数处理文件。

#### 初始化方法：`__init__(self, upload_callback, allowed_extensions=None, temporary_extensions=None, stable_time=5)`

```python
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
```

- **参数说明**:
  - `upload_callback`: 文件稳定后调用的回调函数，用于处理上传操作。
  - `allowed_extensions`: 允许处理的文件扩展名列表，默认为常见的文档、压缩包和多媒体格式。
  - `temporary_extensions`: 临时文件扩展名列表，用于识别未完成下载的文件。
  - `stable_time`: 文件大小保持不变的等待时间（秒），确保下载完成。

- **初始化内容**:
  - 设置允许和临时文件的扩展名。
  - 初始化一个字典 `files_in_progress` 用于跟踪正在监控的文件及其最后修改时间。

#### 方法：`on_any_event(self, event)`

```python
def on_any_event(self, event):
    # 捕捉所有类型的事件并记录
    if not event.is_directory:
        event_type = event.event_type
        file_path = event.src_path
        logging.debug(f"捕捉到事件: {event_type} - 文件路径: {file_path}")
```

- **功能**: 捕捉所有文件系统事件（创建、移动、修改等），并记录事件类型和文件路径。
- **逻辑步骤**:
  1. 检查事件是否为文件（非目录）。
  2. 记录事件类型和文件路径的调试日志。

#### 方法：`on_created(self, event)`

```python
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
```

- **功能**: 处理文件创建事件，筛选符合条件的文件，并启动监控线程以检测文件稳定性。
- **逻辑步骤**:
  1. 获取文件路径和扩展名。
  2. 忽略临时文件和不在允许列表中的文件。
  3. 记录检测到新文件的日志。
  4. 启动后台线程 `_wait_for_file_stable` 监控文件是否稳定。

#### 方法：`on_moved(self, event)`

```python
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
```

- **功能**: 处理文件移动事件，筛选符合条件的目标文件，并启动监控线程。
- **逻辑步骤**:
  1. 获取源路径和目标路径。
  2. 忽略临时文件和不在允许列表中的文件。
  3. 记录检测到移动后新文件的日志。
  4. 启动后台线程 `_wait_for_file_stable` 监控文件是否稳定。

#### 方法：`on_modified(self, event)`

```python
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
```

- **功能**: 处理文件修改事件，更新正在监控文件的最后修改时间，以确保文件稳定性检查的准确性。
- **逻辑步骤**:
  1. 获取文件路径和扩展名。
  2. 忽略临时文件和不在允许列表中的文件。
  3. 如果文件正在监控中，更新其最后修改时间。

#### 方法：`_wait_for_file_stable(self, file_path)`

```python
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
```

- **功能**: 确保文件在一定时间内大小保持不变，确认下载完成后触发上传回调。
- **逻辑步骤**:
  1. 记录文件开始监控的时间。
  2. 持续检查文件的最后修改时间。
  3. 如果当前时间与最后修改时间的差值超过 `stable_time`，认为文件已稳定。
  4. 从监控字典中移除文件，并调用 `upload_callback` 处理文件。
  5. 每秒检查一次文件是否稳定。

### 类：`DownloadWatcher`

#### 主要职责
- **设置监控目录**：指定需要监控的下载目录。
- **启动和停止监控**：控制监控进程的启动和停止。
- **集成事件处理器**：使用 `DownloadEventHandler` 处理文件系统事件。

#### 初始化方法：`__init__(self, download_path, upload_callback, allowed_extensions=None, temporary_extensions=None, stable_time=5)`

```python
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
```

- **参数说明**:
  - `download_path`: 需要监控的下载目录路径。
  - `upload_callback`: 文件稳定后调用的回调函数，用于处理上传操作。
  - `allowed_extensions`: 允许处理的文件扩展名列表。
  - `temporary_extensions`: 临时文件扩展名列表，用于识别未完成下载的文件。
  - `stable_time`: 文件大小保持不变的等待时间（秒）。

- **初始化内容**:
  - 设置监控目录的绝对路径。
  - 配置允许和临时文件的扩展名。
  - 创建 `DownloadEventHandler` 实例，并传入上传回调和文件过滤配置。
  - 使用 `PollingObserver` 作为观察者来监听文件系统事件。

#### 方法：`start(self)`

```python
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
```

- **功能**: 启动下载目录的监控，并保持主线程运行以持续监听事件。
- **逻辑步骤**:
  1. 使用 `observer.schedule` 方法将事件处理器绑定到下载目录。
  2. 启动观察者。
  3. 记录开始监控的日志。
  4. 通过无限循环保持主线程运行，确保监控持续进行。
  5. 如果发生异常，停止观察者并记录错误日志。

#### 方法：`stop(self)`

```python
def stop(self):
    self.observer.stop()
    self.observer.join()
    logging.info("停止监控下载目录")
```

- **功能**: 停止下载目录的监控，确保观察者线程被正确关闭。
- **逻辑步骤**:
  1. 调用 `observer.stop()` 停止观察者。
  2. 调用 `observer.join()` 等待观察者线程结束。
  3. 记录停止监控的日志。

### 模块内部工作流程

1. **初始化**:
   - 创建 `DownloadWatcher` 实例，传入下载目录路径、上传回调函数及文件过滤配置。
   - `DownloadWatcher` 初始化时，创建并配置 `DownloadEventHandler`。

2. **启动监控**:
   - 调用 `start()` 方法，启动 `PollingObserver` 监听下载目录。
   - 观察者开始捕捉文件系统事件，并由 `DownloadEventHandler` 处理。

3. **处理文件事件**:
   - **文件创建** (`on_created`):
     - 检查文件类型，忽略临时文件和不允许的文件。
     - 对符合条件的文件，启动后台线程监控文件稳定性。
   - **文件移动** (`on_moved`):
     - 检查目标文件类型，忽略临时文件和不允许的文件。
     - 对符合条件的文件，启动后台线程监控文件稳定性。
   - **文件修改** (`on_modified`):
     - 如果文件正在监控中，更新其最后修改时间。

4. **监控文件稳定性**:
   - 后台线程 `_wait_for_file_stable` 定期检查文件的最后修改时间。
   - 如果文件在 `stable_time` 秒内未被修改，认为下载完成且稳定。
   - 调用 `upload_callback` 处理稳定的文件。

5. **上传文件**:
   - `upload_callback` 通常指向 `Uploader` 模块的上传方法，将稳定的文件进行上传处理。

6. **停止监控**:
   - 调用 `stop()` 方法，停止观察者并终止监控。

### 与其他模块的交互

- **`Uploader`**:
  - `DownloadWatcher` 通过 `upload_callback` 将稳定的下载文件路径传递给 `Uploader` 进行上传处理。

- **`ErrorHandler`**:
  - 在文件事件处理和稳定性监控过程中，如果发生异常，`DownloadEventHandler` 会调用 `error_handler.handle_exception(e)` 进行统一的异常处理，确保系统稳定性。

### 示例用法

```python
# 假设有一个上传回调函数和异常处理器
def upload_callback(file_path):
    uploader.upload_file(file_path)

error_handler = ErrorHandler()

# 创建 DownloadWatcher 实例
download_watcher = DownloadWatcher(
    download_path='/path/to/downloads',
    upload_callback=upload_callback,
    allowed_extensions=[
        '.pdf', '.docx', '.xlsx',
        '.ppt', '.pptx',
        '.zip', '.rar', '.7z',
        '.mp4', '.avi', '.mkv',
        '.mp3', '.wav', '.aac',
        '.tar', '.gz', '.bz2',
        '.mov', '.flv', '.wmv'
    ],
    temporary_extensions=[
        '.crdownload', '.part', '.tmp', '.download'
    ],
    stable_time=5
)

# 启动下载监控
download_watcher.start()
```

---

## 总结

`download_watcher.py` 模块通过 `DownloadWatcher` 和 `DownloadEventHandler` 类，提供了监控下载目录并处理新下载文件的核心功能。其设计重点包括：

- **文件系统事件监听**：使用 `watchdog` 库捕捉文件创建、移动和修改事件。
- **文件类型过滤**：仅处理允许的文件类型，忽略临时文件和不相关的文件。
- **文件稳定性检测**：确保文件在指定时间内大小保持不变，确认下载完成。
- **上传回调机制**：文件稳定后，通过回调函数将文件路径传递给 `Uploader` 模块进行上传。
- **异常处理**：全面捕捉和处理可能发生的异常，确保系统的稳定性和可靠性。
- **模块化设计**：与 `Uploader` 和 `ErrorHandler` 等模块协作，实现低耦合、高内聚的系统结构。

通过以上设计，`download_watcher.py` 能够高效、可靠地监控下载目录，及时处理新下载的文件，并将其上传到指定的微信群组，提升整体系统的自动化水平。如果有进一步的问题或需要更多详细信息，欢迎随时提问！