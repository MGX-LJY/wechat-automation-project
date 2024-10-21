## `error_handler.py` 模块概述

`error_handler.py` 模块提供了一个统一的异常处理机制，通过记录日志和发送通知，确保系统在发生错误时能够及时响应并告知相关人员。该模块与 `Notifier` 类集成，能够将异常信息发送到预定的通知渠道（如微信群组、邮件等）。

### 类：`ErrorHandler`

#### 主要职责
- **统一异常处理**：集中处理系统中捕捉到的异常，确保错误信息被正确记录和通知。
- **日志记录**：将简短和详细的异常信息记录到日志系统中，便于后续排查。
- **发送通知**：通过 `Notifier` 类将异常信息发送到指定的通知渠道，确保相关人员能够及时获知系统异常。

#### 初始化方法：`__init__(self, notifier: Notifier, log_callback=None)`

```python
def __init__(self, notifier: Notifier, log_callback=None):
    self.notifier = notifier
    self.log_callback = log_callback
```

- **参数说明**:
  - `notifier` (`Notifier` 实例): 用于发送通知的实例，负责将异常信息传递到预定的通知渠道。
  - `log_callback` (可选): 日志回调函数，用于将简短的错误信息传递给外部组件（如GUI），实现实时日志显示。

- **初始化内容**:
  - 保存 `Notifier` 实例，用于后续发送通知。
  - 保存 `log_callback` 函数，如果提供，则在处理异常时调用。

#### 方法：`handle_exception(self, exception=None)`

```python
def handle_exception(self, exception=None):
    # 仅记录简短的错误信息
    logging.error("网络异常")
    if self.log_callback:
        self.log_callback("网络异常")
    self.notifier.notify("网络异常")
    if exception:
        self.send_exception_details(exception)
```

- **功能**: 处理捕捉到的异常，记录简短的错误信息，并发送通知。如果提供了具体的异常对象，还会记录和发送详细的异常信息。
- **参数**:
  - `exception` (可选): 捕捉到的异常对象，用于记录详细的异常信息。

- **逻辑步骤**:
  1. **记录简短错误信息**: 使用 `logging.error` 记录一条简短的错误消息 `"网络异常"`。
  2. **调用日志回调**: 如果提供了 `log_callback`，则调用该回调函数传递简短的错误信息。
  3. **发送通知**: 使用 `Notifier` 实例调用 `notify` 方法发送简短的错误消息。
  4. **记录详细异常信息**: 如果提供了异常对象，则调用 `send_exception_details` 方法记录和发送详细的异常信息。

#### 方法：`send_exception_details(self, exception)`

```python
def send_exception_details(self, exception):
    # 记录详细的异常信息
    exception_details = ''.join(traceback.format_exception(None, exception, exception.__traceback__))
    logging.error(f"详细异常信息: {exception_details}")
    self.notifier.notify(f"详细异常信息: {exception_details}")
```

- **功能**: 记录并发送详细的异常信息，包括堆栈跟踪，便于快速定位和修复问题。
- **参数**:
  - `exception`: 捕捉到的异常对象，用于生成详细的异常信息。

- **逻辑步骤**:
  1. **格式化异常信息**: 使用 `traceback.format_exception` 将异常对象格式化为详细的异常信息字符串。
  2. **记录详细异常信息**: 使用 `logging.error` 记录格式化后的详细异常信息。
  3. **发送详细通知**: 使用 `Notifier` 实例调用 `notify` 方法发送详细的异常信息。

### 模块内部工作流程

1. **初始化**:
   - 创建 `ErrorHandler` 实例，传入 `Notifier` 实例和可选的 `log_callback` 函数。
   
2. **异常处理**:
   - 当系统中捕捉到异常时，调用 `handle_exception` 方法。
   - 记录简短的错误信息，并通过 `log_callback` 和 `Notifier` 发送通知。
   - 如果提供了具体的异常对象，进一步记录和发送详细的异常信息。

3. **日志与通知**:
   - **日志记录**: 使用 `logging` 模块记录错误信息，包含简短和详细两种级别。
   - **通知发送**: 通过 `Notifier` 类将错误信息发送到指定的通知渠道，确保相关人员能够及时获知并响应系统异常。

### 与其他模块的交互

- **`Notifier`**:
  - `ErrorHandler` 依赖于 `Notifier` 类来发送异常通知。`Notifier` 负责将异常信息传递到预定的通知渠道，如微信群组、邮件等。

- **`log_callback`**:
  - `ErrorHandler` 可以通过 `log_callback` 将简短的错误信息传递给外部组件（如GUI），实现实时的日志显示和用户反馈。

### 示例用法

```python
# 假设有一个 Notifier 实例和可选的日志回调函数
notifier = Notifier(config)
log_callback = lambda msg: print(f"LOG: {msg}")  # 简单的日志回调

# 创建 ErrorHandler 实例
error_handler = ErrorHandler(notifier=notifier, log_callback=log_callback)

# 在系统中捕捉到异常时调用
try:
    # 可能抛出异常的代码
    risky_operation()
except Exception as e:
    error_handler.handle_exception(e)
```

---

## 总结

`error_handler.py` 模块通过 `ErrorHandler` 类，提供了一个统一且高效的异常处理机制。其设计重点包括：

- **统一异常处理**: 集中处理系统中所有捕捉到的异常，确保错误信息被正确记录和通知。
- **日志记录**: 分层次记录简短和详细的异常信息，便于快速排查问题。
- **通知机制**: 通过 `Notifier` 类将异常信息发送到预定的通知渠道，确保相关人员能够及时响应。
- **模块化设计**: 与 `Notifier` 和外部日志回调函数协作，实现低耦合、高内聚的系统结构。
- **灵活性**: 支持通过 `log_callback` 将日志信息传递给外部组件，如图形用户界面（GUI），增强系统的可观察性。

通过以上设计，`ErrorHandler` 能够有效提升系统的稳定性和可维护性，确保在发生异常时，能够及时记录和通知，帮助开发者快速定位和解决问题。如果有进一步的问题或需要更多详细信息，欢迎随时提问！