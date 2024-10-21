## `auto_clicker.py` 模块概述

`auto_clicker.py` 模块负责自动化处理提取到的URL链接，包括批量打开链接、管理浏览器会话以及控制浏览器的关闭。该模块通过队列管理URL，分批次打开链接，并在达到一定数量后关闭浏览器，确保系统的稳定性和效率。

### 类：`AutoClicker`

#### 主要职责
- **管理URL队列**：接收并存储待处理的URL链接。
- **批量处理URL**：按配置的批次大小和时间间隔打开URL。
- **控制浏览器**：在处理一定数量的URL后，自动关闭浏览器并重新打开指定页面。
- **异常处理**：捕捉并处理在URL处理过程中发生的异常，确保系统稳定运行。

#### 初始化方法：`__init__(self, error_handler, batch_size=4, wait_time=60, collect_timeout=5, close_after_count=8, close_wait_time=900)`

```python
def __init__(self, error_handler, batch_size=4, wait_time=60, collect_timeout=5, close_after_count=8, close_wait_time=900):
    """
    初始化 AutoClicker。

    :param error_handler: 用于处理异常的 ErrorHandler 实例。
    :param batch_size: 每批处理的URL数量。
    :param wait_time: 每批之间的等待时间（秒）。
    :param collect_timeout: 收集批次URL的超时时间（秒）。
    :param close_after_count: 达到此计数后关闭浏览器。
    :param close_wait_time: 达到计数后等待的时间（秒）。
    """
    self.error_handler = error_handler
    self.url_queue = Queue()
    self.batch_size = batch_size
    self.wait_time = wait_time
    self.collect_timeout = collect_timeout
    self.close_after_count = close_after_count
    self.close_wait_time = close_wait_time

    self.opened_count = 0
    self.timer_running = False
    self.count_lock = threading.Lock()

    # 启动处理线程
    self.processing_thread = threading.Thread(target=self.process_queue, daemon=True)
    self.processing_thread.start()
    logging.info("AutoClicker 初始化完成，处理线程已启动。")

    # 下载完成回调
    self.downloads_completed = threading.Event()
```

- **参数说明**:
  - `error_handler`: 异常处理器实例，用于处理运行中的错误。
  - `batch_size`: 每批处理的URL数量，默认为4。
  - `wait_time`: 每批之间的等待时间（秒），默认为60秒。
  - `collect_timeout`: 收集批次URL的超时时间（秒），默认为5秒。
  - `close_after_count`: 达到此计数后关闭浏览器，默认为8。
  - `close_wait_time`: 达到计数后等待的时间（秒），默认为900秒（15分钟）。

- **初始化内容**:
  - 创建一个URL队列 `url_queue` 用于存储待处理的URL。
  - 初始化计数器 `opened_count` 和锁 `count_lock`。
  - 启动一个守护线程 `processing_thread`，用于处理URL队列。
  - 初始化下载完成的事件 `downloads_completed`。

#### 方法：`add_urls(self, urls)`

```python
def add_urls(self, urls):
    """
    添加多个URL到队列中。

    :param urls: 要添加的URL列表。
    """
    for url in urls:
        self.url_queue.put(url)
        logging.debug(f"添加URL到队列: {url}")

    # 记录当前剩余批次数量
    remaining_batches = self.get_remaining_batches()
    logging.info(f"当前剩余批次数量: {remaining_batches}")
```

- **功能**: 将多个URL添加到处理队列中，并记录当前队列中剩余的批次数量。
- **参数**:
  - `urls`: 要添加的URL列表。

#### 方法：`process_queue(self)`

```python
def process_queue(self):
    """
    处理URL队列，分批打开链接。
    """
    try:
        logging.info("开始处理URL队列")
        while True:
            batch = []
            start_time = time.time()
            while len(batch) < self.batch_size and (time.time() - start_time) < self.collect_timeout:
                try:
                    remaining_time = self.collect_timeout - (time.time() - start_time)
                    if remaining_time <= 0:
                        break
                    url = self.url_queue.get(timeout=remaining_time)
                    batch.append(url)
                except Empty:
                    break  # 超时未获取到URL，结束本批处理

            if batch:
                logging.info(f"开始处理一批链接，共 {len(batch)} 个")
                for url in batch:
                    self.open_url(url)

                # 在处理完当前批次后，检查是否需要等待
                if not self.url_queue.empty():
                    logging.info(f"等待 {self.wait_time} 秒后继续处理下一批链接")
                    time.sleep(self.wait_time)
                else:
                    logging.info("当前队列处理完毕，无需等待。")
            else:
                # 队列为空时不记录日志，避免日志充斥
                time.sleep(5)
    except Exception as e:
        logging.error(f"处理URL队列时发生错误: {e}", exc_info=True)
        self.error_handler.handle_exception(e)
```

- **功能**: 持续监控并处理URL队列，按批次打开链接，并根据配置的参数控制处理节奏。
- **逻辑步骤**:
  1. 初始化一个空批次列表 `batch`。
  2. 在 `collect_timeout` 时间内，尽可能多地从队列中获取URL，直到达到 `batch_size`。
  3. 如果有URL在批次中，逐一调用 `open_url` 方法打开。
  4. 如果队列中还有剩余URL，等待 `wait_time` 秒后继续处理下一批。
  5. 如果队列为空，短暂休眠5秒后继续检查。

#### 方法：`open_url(self, url)`

```python
def open_url(self, url):
    """
    打开指定的 URL，并进行计数控制。

    :param url: 要打开的 URL。
    """
    try:
        logging.info(f"打开URL: {url}")
        subprocess.run(['open', '-a', 'Safari', url], check=True)
        time.sleep(2)  # 等待Safari打开标签页，防止过快打开

        # 更新已打开的URL计数
        self.increment_count()
    except subprocess.CalledProcessError as e:
        logging.error(f"打开URL时发生错误: {e}", exc_info=True)
        self.error_handler.handle_exception(e)
    except Exception as e:
        logging.error(f"打开URL时发生未知错误: {e}", exc_info=True)
        self.error_handler.handle_exception(e)
```

- **功能**: 使用系统命令打开指定的URL（默认使用Safari浏览器），并在成功后更新已打开URL的计数。
- **参数**:
  - `url`: 要打开的URL。

#### 方法：`increment_count(self)`

```python
def increment_count(self):
    """
    增加已打开URL的计数，并在达到阈值时启动计时器关闭浏览器。
    """
    with self.count_lock:
        self.opened_count += 1
        logging.debug(f"已打开的URL数量: {self.opened_count}")

        if self.opened_count >= self.close_after_count and not self.timer_running:
            self.timer_running = True
            logging.info(f"已打开 {self.close_after_count} 个链接，启动计时器将在 {self.close_wait_time} 秒后关闭浏览器")
            timer_thread = threading.Thread(target=self.close_timer, daemon=True)
            timer_thread.start()
```

- **功能**: 增加已打开URL的计数，当计数达到 `close_after_count` 时，启动一个计时器以在 `close_wait_time` 秒后关闭浏览器。
- **逻辑步骤**:
  1. 使用锁 `count_lock` 确保线程安全地更新计数器 `opened_count`。
  2. 检查是否达到关闭浏览器的阈值且计时器尚未运行。
  3. 如果条件满足，设置 `timer_running` 为 `True` 并启动 `close_timer` 线程。

#### 方法：`close_timer(self)`

```python
def close_timer(self):
    """
    等待指定时间后关闭浏览器，并打开指定链接。
    """
    try:
        logging.info(f"计时器启动，等待 {self.close_wait_time} 秒后关闭浏览器")
        time.sleep(self.close_wait_time)
        self.close_safari()
        self.open_zxxk_page()  # 打开指定链接
    except Exception as e:
        logging.error(f"计时器运行时发生错误: {e}", exc_info=True)
        self.error_handler.handle_exception(e)
    finally:
        with self.count_lock:
            self.opened_count = 0
            self.timer_running = False
            logging.debug("计数器已重置，计时器状态已关闭")
```

- **功能**: 在等待 `close_wait_time` 秒后，关闭Safari浏览器并打开指定的页面（`https://www.zxxk.com`）。
- **逻辑步骤**:
  1. 等待 `close_wait_time` 秒。
  2. 调用 `close_safari` 方法关闭Safari浏览器。
  3. 调用 `open_zxxk_page` 方法打开指定的链接。
  4. 重置计数器和计时器状态。

#### 方法：`close_safari(self)`

```python
def close_safari(self):
    """
    关闭 Safari 浏览器，并确保其已完全关闭。
    """
    try:
        logging.info("尝试关闭 Safari 浏览器")
        subprocess.run(['osascript', '-e', 'tell application "Safari" to quit'], check=True)
        self.wait_until_safari_closed(timeout=10)
        logging.info("Safari 已成功关闭")
    except subprocess.CalledProcessError as e:
        logging.error(f"关闭 Safari 失败: {e}", exc_info=True)
        self.error_handler.handle_exception(e)
    except Exception as e:
        logging.error(f"关闭 Safari 时发生错误: {e}", exc_info=True)
        self.error_handler.handle_exception(e)
```

- **功能**: 使用AppleScript命令关闭Safari浏览器，并确保其已完全关闭。
- **逻辑步骤**:
  1. 使用 `osascript` 命令发送关闭Safari的指令。
  2. 调用 `wait_until_safari_closed` 方法确认Safari已关闭。
  3. 记录关闭结果。

#### 方法：`wait_until_safari_closed(self, timeout=10)`

```python
def wait_until_safari_closed(self, timeout=10):
    """
    等待 Safari 完全关闭。

    :param timeout: 最大等待时间（秒）。
    """
    start_time = time.time()
    while True:
        # 使用 'pgrep' 检查 Safari 是否在运行
        result = subprocess.run(['pgrep', 'Safari'], capture_output=True, text=True)
        if result.returncode != 0:
            # Safari 未运行
            break
        if time.time() - start_time > timeout:
            logging.warning("等待 Safari 关闭超时。")
            break
        time.sleep(0.5)
```

- **功能**: 检查Safari浏览器是否已关闭，最多等待指定的超时时间。
- **参数**:
  - `timeout`: 最大等待时间（秒），默认为10秒。

#### 方法：`open_zxxk_page(self)`

```python
def open_zxxk_page(self):
    """
    打开指定的 Safari 标签页以 https://www.zxxk.com。
    """
    try:
        logging.info("使用 'open' 命令打开 https://www.zxxk.com")
        subprocess.run(['open', '-a', 'Safari', 'https://www.zxxk.com'], check=True)
        time.sleep(2)  # 等待 Safari 打开标签页
        logging.info("https://www.zxxk.com 已成功打开")
    except subprocess.CalledProcessError as e:
        logging.error(f"打开 https://www.zxxk.com 时发生错误: {e}", exc_info=True)
        self.error_handler.handle_exception(e)
    except Exception as e:
        logging.error(f"打开 https://www.zxxk.com 时发生未知错误: {e}", exc_info=True)
        self.error_handler.handle_exception(e)
```

- **功能**: 使用系统命令打开指定的URL（`https://www.zxxk.com`）在Safari浏览器中。
- **逻辑步骤**:
  1. 使用 `open` 命令启动Safari并打开指定页面。
  2. 等待2秒以确保页面已打开。
  3. 记录打开结果。

#### 方法：`on_download_complete(self, file_path)`

```python
def on_download_complete(self, file_path):
    """
    下载完成的回调方法。

    :param file_path: 下载完成的文件路径。
    """
    logging.info(f"下载完成: {file_path}")
    # 根据需要执行上传或其他操作
    # 例如，上传文件到群组或处理文件
    # self.upload_file(file_path)
```

- **功能**: 处理下载完成后的回调，可以根据需求执行上传或其他操作。
- **参数**:
  - `file_path`: 下载完成的文件路径。

#### 方法：`get_remaining_batches(self)`

```python
def get_remaining_batches(self):
    """
    计算当前队列中剩余的批次数量。

    :return: 剩余批次数量。
    """
    with self.count_lock:
        queue_size = self.url_queue.qsize()
        remaining_batches = (queue_size + self.batch_size - 1) // self.batch_size  # 向上取整
        return remaining_batches
```

- **功能**: 计算当前URL队列中剩余的批次数量。
- **返回**: 剩余批次数量（整数）。

#### 方法：`wait_for_file_stability(self, file_path, stable_time=5)`

```python
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
```

- **功能**: 确保文件下载完成，文件大小在 `stable_time` 秒内保持不变。
- **参数**:
  - `file_path`: 文件路径。
  - `stable_time`: 文件大小稳定的等待时间（秒），默认为5秒。

#### 方法：`send_large_file_message(self, file_path)`

```python
def send_large_file_message(self, file_path):
    """
    发送超过25MB的文件上传提醒消息到所有目标群组。
    """
    try:
        filename = os.path.basename(file_path)
        message = f"{filename} 文件过大,急需的话@李老师呀,长时间没有回复打电话 15131531853"

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
```

- **功能**: 当文件大小超过25MB时，发送提醒消息到所有目标群组，提示文件过大无法上传。
- **参数**:
  - `file_path`: 文件路径。

#### 方法：`load_counters(self)`

```python
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
```

- **功能**: 从配置文件加载计数器数据，包括剩余下载量和每日下载量。
- **逻辑步骤**:
  1. 检查计数器文件是否存在。
  2. 如果存在，读取并解析JSON数据，更新 `remaining_count` 和 `daily_download_counts`。
  3. 如果读取失败或文件不存在，使用默认值。

#### 方法：`save_counters(self)`

```python
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
```

- **功能**: 将当前的计数器数据保存到配置文件，以便持久化存储。
- **逻辑步骤**:
  1. 构建包含 `remaining_count` 和 `daily_download_counts` 的字典。
  2. 将字典序列化为JSON并写入配置文件。
  3. 记录保存结果。

#### 方法：`deduct_and_record(self)`

```python
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
```

- **功能**: 扣除下载配额并记录当天的下载量。
- **逻辑步骤**:
  1. 获取当前日期，考虑到截止时间（22:30）。
  2. 更新当天的下载量。
  3. 扣减剩余下载量，确保不为负数。
  4. 保存更新后的计数器数据。

#### 方法：`get_download_date(self, now)`

```python
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
```

- **功能**: 根据当前时间判断下载记录应计入哪一天。
- **参数**:
  - `now`: 当前时间的 `datetime` 对象。
- **逻辑步骤**:
  - 如果当前时间已过22:30，则将下载计入第二天。
  - 否则，计入当天。

#### 方法：`notification_scheduler(self)`

```python
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
```

- **功能**: 每天晚上10点半发送下载量和剩余量的通知。
- **逻辑步骤**:
  1. 计算下一次通知的时间（当天或次日22:30）。
  2. 计算等待时间并休眠。
  3. 休眠结束后，调用 `send_daily_notification` 发送通知。

#### 方法：`send_daily_notification(self)`

```python
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

    for group_name, user_name in self.group_usernames.items():
        if not user_name:
            logging.error(f"群组 '{group_name}' 的 UserName 未找到，无法发送每日通知")
            continue
        try:
            itchat.send(message, toUserName=user_name)
            logging.info(f"发送每日通知到群组 '{group_name}': {message}")
        except Exception as e:
            logging.error("发送每日通知时发生网络问题", exc_info=True)
            self.error_handler.handle_exception(e)

     # 发送完通知后，重置该日期的下载量
    if report_date in self.daily_download_counts:
        del self.daily_download_counts[report_date]

    # 保存计数器数据
    self.save_counters()
```

- **功能**: 发送当天的下载量和剩余下载量到所有目标群组，并重置当天的下载记录。
- **逻辑步骤**:
  1. 获取需要报告的日期（考虑截止时间）。
  2. 构建通知消息。
  3. 发送消息到每个目标群组。
  4. 重置当天的下载量。
  5. 保存更新后的计数器数据。

### 模块内部工作流程

1. **初始化**:
   - 创建 `AutoClicker` 实例，传入异常处理器和其他配置参数。
   - 启动后台线程 `processing_thread`，持续处理URL队列。
   - 启动每日通知的定时器线程 `notification_scheduler`。

2. **添加URL**:
   - 调用 `add_urls` 方法，将新的URL添加到队列中。

3. **处理URL队列**:
   - `process_queue` 方法持续运行，按批次从队列中获取URL并调用 `open_url` 打开。
   - 每批处理完成后，根据配置的 `wait_time` 决定是否等待后继续处理下一批。

4. **打开URL**:
   - 使用系统命令打开Safari浏览器并访问指定URL。
   - 更新已打开URL的计数，并在达到阈值时启动关闭浏览器的计时器。

5. **关闭浏览器**:
   - 在计时器触发后，调用 `close_safari` 方法关闭Safari。
   - 使用系统命令打开指定的页面（`https://www.zxxk.com`）。

6. **计数管理**:
   - 扣除下载配额并记录每日下载量。
   - 通过 `load_counters` 和 `save_counters` 方法管理计数器数据的持久化。

7. **每日通知**:
   - 每天晚上10点半，通过 `send_daily_notification` 方法发送下载量和剩余量的通知到目标群组。

8. **异常处理**:
   - 在所有关键操作中捕捉异常，并通过 `error_handler` 进行处理，确保系统的稳定性。

### 与其他模块的交互

- **`ErrorHandler`**:
  - 处理在URL处理过程中发生的任何异常，确保系统稳定运行。

- **`MessageHandler`**:
  - 通过 `add_urls` 方法接收从消息中提取的有效URL。

- **`ItChatHandler`**:
  - 不直接交互，但通过 `MessageHandler` 间接提供URL进行处理。

### 示例用法

```python
# 假设有一个异常处理器
error_handler = ErrorHandler()

# 创建 AutoClicker 实例
auto_clicker = AutoClicker(
    error_handler=error_handler,
    batch_size=4,
    wait_time=60,
    collect_timeout=5,
    close_after_count=8,
    close_wait_time=900
)

# 添加URL到AutoClicker
urls_to_process = [
    'https://example.com/file1',
    'https://example.com/file2',
    'https://example.com/file3',
    'https://example.com/file4'
]
auto_clicker.add_urls(urls_to_process)

# 假设下载完成后调用
downloaded_file_path = '/path/to/downloaded/file1'
auto_clicker.on_download_complete(downloaded_file_path)
```

---

## 总结

`auto_clicker.py` 模块通过 `AutoClicker` 类，提供了自动化处理URL链接的核心功能。其设计重点包括：

- **队列管理**：使用线程安全的队列 `url_queue` 管理待处理的URL。
- **批量处理**：按配置的批次大小和时间间隔处理URL，确保系统高效运行。
- **浏览器控制**：在处理一定数量的URL后，自动关闭浏览器以释放资源，并重新打开指定页面。
- **计数管理**：管理下载配额和每日下载量，确保系统按照预定的限制运行。
- **每日通知**：定时发送下载量和剩余量的通知，帮助用户了解系统状态。
- **异常处理**：全面捕捉和处理可能发生的异常，确保系统的稳定性和可靠性。
- **模块化设计**：通过与 `MessageHandler` 和 `ErrorHandler` 等模块的协作，实现低耦合、高内聚的系统结构。

通过以上设计，`AutoClicker` 能够高效、可靠地处理来自消息的URL链接，自动化完成打开和管理浏览器的任务，提升整体系统的自动化水平。如果有进一步的问题或需要更多详细信息，欢迎随时提问！