## `itchat_handler.py` 模块概述

`itchat_handler.py` 模块主要负责与微信的交互，包括登录、监听群组消息、处理二维码登录以及登出操作。它使用 `ItChat` 库实现微信自动化功能，是微信自动化上传系统的核心部分。

### 类：`ItChatHandler`

#### 主要职责
- **登录微信**：通过二维码扫描登录微信。
- **监听群组消息**：监控指定的微信群组，并将接收到的消息传递给回调函数处理。
- **处理二维码**：生成并展示登录二维码，支持将二维码发送到GUI界面。
- **登出微信**：安全退出微信会话。

#### 初始化方法：`__init__(self, config, error_handler, log_callback=None, qr_queue=None)`
- **参数**:
  - `config`: 配置字典，包含监控群组、二维码路径等。
  - `error_handler`: 异常处理器，用于处理运行中的错误。
  - `log_callback` (可选): 日志回调函数，用于将日志信息传递给外部（如GUI）。
  - `qr_queue` (可选): 队列，用于发送二维码数据到GUI。

- **初始化内容**:
  - 设置需要监控的群组列表。
  - 配置二维码保存路径、重试次数及间隔。
  - 初始化登录事件，用于标识登录状态。

#### 方法：`set_message_callback(self, callback)`
- **功能**: 设置处理接收到消息的回调函数。
- **参数**:
  - `callback`: 一个函数，当接收到符合条件的消息时调用。

#### 方法：`login(self)`
- **功能**: 尝试登录微信，支持多次重试。
- **逻辑**:
  1. 删除旧的会话文件以确保新登录。
  2. 调用 `itchat.auto_login` 进行登录，禁用热重载。
  3. 如果登录成功，记录日志并设置登录事件。
  4. 登录失败时，按照配置的重试次数和间隔重试，最终抛出异常。

#### 方法：`run(self)`
- **功能**: 启动微信消息监听循环。
- **逻辑**:
  1. 注册群组消息（文本和附件）的处理函数。
  2. 使用装饰器 `@itchat.msg_register` 监听群组消息。
  3. 当接收到消息时，检查是否在监控的群组列表中，如果是则调用 `message_callback` 处理。
  4. 启动 `itchat.run()` 以开始监听。

#### 方法：`qr_callback(self, uuid, status, qrcode)`
- **功能**: 处理二维码生成和登录状态的回调。
- **参数**:
  - `uuid`: 唯一标识符。
  - `status`: 当前二维码状态（如生成、已扫描、登录成功）。
  - `qrcode`: 二维码的图像数据。

- **逻辑**:
  1. 根据 `status` 判断当前二维码状态。
  2. 状态 `'0'` 时，保存并展示二维码，发送到GUI队列。
  3. 状态 `'201'` 时，提示用户在手机上确认登录。
  4. 状态 `'200'` 时，标识登录成功。
  5. 其他状态记录警告日志。

#### 方法：`logout(self)`
- **功能**: 安全登出微信。
- **逻辑**:
  1. 调用 `itchat.logout()` 退出微信会话。
  2. 记录登出日志。

### 模块内部工作流程

1. **初始化**:
   - 创建 `ItChatHandler` 实例，传入配置和处理器。
   
2. **登录**:
   - 调用 `login()` 方法，生成并展示二维码，等待用户扫描。
   
3. **消息监听**:
   - 调用 `run()` 方法，开始监听群组消息。
   - 当接收到消息时，若来自监控群组，则通过回调函数处理。

4. **登出**:
   - 调用 `logout()` 方法，安全退出微信。

### 错误处理与日志

- **异常捕捉**: 所有关键操作均包裹在 `try-except` 块中，捕捉并处理异常。
- **日志记录**: 使用 `logging` 模块记录信息、错误和警告。
- **通知**: 通过 `log_callback` 将日志信息传递给外部组件（如GUI），确保实时反馈。

### 与其他模块的交互

- **`error_handler`**: 处理捕捉到的异常，确保系统稳定。
- **`message_callback`**: 处理接收到的群组消息，通常传递给 `MessageHandler` 模块。
- **`log_callback`**: 将日志信息传递给外部组件，如GUI界面。
- **`qr_queue`**: 将二维码数据发送到GUI，以便用户扫描登录。

---

## 示例用法

```python
# 假设有一个配置字典和异常处理器
config = {
    "monitor_groups": ["目标群组1", "目标群组2"],
    "login_qr_path": "qr.png",
    "itchat": {
        "qr_check": {
            "max_retries": 3,
            "retry_interval": 5
        }
    }
}
error_handler = ErrorHandler()
log_callback = lambda msg: print(f"LOG: {msg}")  # 简单的日志回调

# 创建 ItChatHandler 实例
itchat_handler = ItChatHandler(config, error_handler, log_callback=log_callback)

# 设置消息处理回调
def handle_message(msg):
    print(f"收到消息: {msg['Content']}")

itchat_handler.set_message_callback(handle_message)

# 登录并运行
itchat_handler.login()
itchat_handler.run()