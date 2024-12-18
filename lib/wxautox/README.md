# wxautox 开发文档

**作者**：Cluic  
**更新日期**：2024-12-17  
**版本**：Plus Version 3.9.11.17.21  
**致**：6LSq5qKm5piv5Y+q54yr4Kmt

---

## 项目介绍

**wxautox** 是 **wxauto** 的增强版，基于 Python 开发，专为微信桌面客户端设计。它在保留 **wxauto** 所有功能的基础上，进一步完善和提升了用户体验与性能。**wxautox** 适用于需要更强大自动化能力的开发者和企业用户，提供了高级功能如朋友圈操作、消息免打扰、群管理、自动保存文件等。

## 目录

- [项目介绍](#项目介绍)
- [环境配置](#环境配置)
- [快速入门](#快速入门)
- [方法说明](#方法说明)
  - [1. 监听](#1-监听)
    - [1.1 添加监听对象 `AddListenChat`](#11-添加监听对象-addlistenchat)
    - [1.2 获取监听消息 `GetListenMessage`](#12-获取监听消息-getlistenmessage)
    - [1.3 移除监听对象 `RemoveListenChat`](#13-移除监听对象-removelistenchat)
    - [1.4 获取所有监听对象 `GetAllListenChat`](#14-获取所有监听对象-getalllistenchat)
    - [1.5 示例：创建一个消息回复机器人](#15-示例创建一个消息回复机器人)
  - [2. 发送消息](#2-发送消息)
    - [2.1 发送文字消息 `SendMsg`](#21-发送文字消息-sendmsg)
    - [2.2 发送打字机模式消息 `SendTypingText`](#22-发送打字机模式消息-sendtypingtext)
    - [2.3 发送图片/视频/文件消息 `SendFiles`](#23-发送图片视频文件消息-sendfiles)
    - [2.4 发送自定义表情包 `SendEmotion`](#24-发送自定义表情包-sendemotion)
    - [2.7 优化 `ChatWith` 方法](#27-优化-chatwith-方法)
    - [2.10 自动保存消息内的卡片链接 `parseurl` 参数](#210-自动保存消息内的卡片链接-parseurl-参数)
    - [2.11 获取当前聊天窗口详情 `CurrentChat` 方法增加 `details` 参数](#211-获取当前聊天窗口详情-currentchat-方法增加-details-参数)
  - [3. 获取消息](#3-获取消息)
    - [3.1 获取当前聊天窗口所有消息 `GetAllMessage`](#31-获取当前聊天窗口所有消息-getallmessage)
    - [3.2 加载更多历史消息 `LoadMoreMessage`](#32-加载更多历史消息-loadmoremessage)
    - [3.3 获取新消息](#33-获取新消息)
      - [3.3.1 获取主窗口新消息](#331-获取主窗口新消息)
      - [3.3.2 监听消息 `GetListenMessage`](#332-监听消息-getlistenmessage)
  - [4. 添加好友](#4-添加好友)
    - [4.1 发起好友申请 `AddNewFriend`](#41-发起好友申请-addnewfriend)
    - [4.2 接受好友请求](#42-接受好友请求)
      - [4.2.1 获取新的好友申请对象列表 `GetNewFriends`](#421-获取新的好友申请对象列表-getnewfriends)
      - [4.2.2 通过好友申请对象接受好友请求](#422-通过好友申请对象接受好友请求)
  - [5. 切换聊天窗口](#5-切换聊天窗口)
    - [5.1 切换到指定好友聊天框 `ChatWith`](#51-切换到指定好友聊天框-chatwith)
    - [5.2 切换微信主页面](#52-切换微信主页面)
      - [5.2.1 切换到聊天页面 `SwitchToChat`](#521-切换到聊天页面-switchtochat)
      - [5.2.2 切换到通讯录页面 `SwitchToContact`](#522-切换到通讯录页面-switchtocontact)
  - [6. 获取好友信息](#6-获取好友信息)
    - [6.1 获取粗略信息 `GetAllFriends`](#61-获取粗略信息-getallfriends)
    - [6.2 获取详细信息 `GetAllFriendDetails`](#62-获取详细信息-getallfrienddetails)
    - [6.3 获取所有好友详情 `GetFriendDetails`](#63-获取所有好友详情-getfrienddetails)
  - [7. 群管理](#7-群管理)
    - [7.1 邀请入群 `AddGroupMembers`](#71-邀请入群-addgroupmembers)
    - [7.2 修改群聊名、备注、群公告、我在本群的昵称 `ManageGroup`](#72-修改群聊名备注群公告我在本群的昵称-managegroup)
    - [7.3 获取群成员 `GetGroupMembers`](#73-获取群成员-getgroupmembers)
    - [7.4 发起群语音通话 `CallGroupMsg`](#74-发起群语音通话-callgroupmsg)
  - [8. 好友管理](#8-好友管理)
    - [8.1 修改好友备注、增加标签 `ManageFriend`](#81-修改好友备注增加标签-managefriend)
  - [9. 通知管理](#9-通知管理)
    - [9.1 消息免打扰 `MuteNotifications`](#91-消息免打扰-mutenotifications)
- [对象说明](#对象说明)
  - [1. 消息对象](#1-消息对象)
    - [1.1 系统消息](#11-系统消息)
    - [1.2 时间消息](#12-时间消息)
    - [1.3 撤回消息](#13-撤回消息)
    - [1.4 好友消息](#14-好友消息)
    - [1.5 自己的消息](#15-自己的消息)
  - [2. 聊天窗口对象](#2-聊天窗口对象)
  - [3. 会话对象](#3-会话对象)
  - [4. 朋友圈对象](#4-朋友圈对象)
    - [4.1 窗口对象](#41-窗口对象)
      - [4.1.1 获取朋友圈内容 `GetMoments`](#411-获取朋友圈内容-getmoments)
      - [4.1.2 刷新朋友圈 `Refresh`](#412-刷新朋友圈-refresh)
      - [4.1.3 关闭朋友圈 `Close`](#413-关闭朋友圈-close)
    - [4.2 消息对象](#42-消息对象)
      - [4.2.1 获取朋友圈内容](#421-获取朋友圈内容)
      - [4.2.2 获取朋友圈图片 `SaveImages`](#422-获取朋友圈图片-saveimages)
      - [4.2.3 获取好友信息 `sender_info`](#423-获取好友信息-sender_info)
      - [4.2.4 获取当前聊天页面详情 `details` 属性](#424-获取当前聊天页面详情-details-属性)
      - [4.2.5 解析卡片链接 `parse_url` 方法](#425-解析卡片链接-parse_url-方法)
- [文件管理对象](#文件管理对象)
  - [1. 文件窗口对象](#1-文件窗口对象)
    - [1.1 获取聊天对象名称](#11-获取聊天对象名称)
    - [1.2 获取聊天对象列表](#12-获取聊天对象列表)
    - [1.3 打开指定聊天会话 `ChatWithFile`](#13-打开指定聊天会话-chatwithfile)
    - [1.4 下载文件 `DownloadFiles`](#14-下载文件-downloadfiles)
  - [2. 文件管理方法](#2-文件管理方法)
- [其他对象](#其他对象)
  - [WeChatFiles 对象](#wechatfiles-对象)
- [新增功能](#新增功能)
- [更新日志](#更新日志)
- [常见问题](#常见问题)
- [反馈与支持](#反馈与支持)

---

## 环境配置

### 1. 系统要求

- **操作系统**：Windows 10、Windows 11 或 Windows Server 2016 及以上版本。
- **Python**：Python 3.7 及以上版本（不支持 Python 3.7.6 和 3.8.1）。

> **注意**：请确保 Python 版本不为 3.7.6 和 3.8.1，否则可能导致安装或运行失败。

### 2. 安装 wxautox

- **根据会员群的文件进行安装**

> **说明**：请从我们的会员微信群获取安装文件和相关安装指导，以确保正确安装 wxautox。

### 3. 微信版本要求

当前 wxautox 项目的默认分支适配微信版本为 **3.9.11.17**。请在使用前确认电脑上的微信客户端版本是否为该版本，版本不匹配可能会因 UI 差异导致部分功能无法正常调用。

> **注**：如果您的微信版本与默认分支兼容，无需过多担心版本问题。

---

## 快速入门

在本节中，我们将通过一个简单的示例，展示如何使用 wxautox 实现微信自动化操作。

### 3分钟快速实现微信自动化

#### 1. 获取微信对象

首先，导入 wxautox 并获取微信窗口对象：

```python
from wxautox import WeChat

# 获取微信窗口对象
wx = WeChat()
# 输出示例: 初始化成功，获取到已登录窗口：xxxx
```

> **注意**：请先登录 PC 微信客户端，再运行上述代码。

> **提示**：上述代码中定义了 `wx` 变量，后续文档中将直接使用该变量，无需重复定义。

#### 2. 创建一个简单的消息回复机器人

通过以下步骤，创建一个能够自动回复特定好友或群聊消息的机器人。

**步骤一**：设置监听列表，包含指定好友或群聊的昵称。

```python
listen_list = [
    '张三',
    '李四',
    '工作群A',
    '工作群B'
]
```

**步骤二**：添加监听对象，可选参数 `savepic` 决定是否保存新消息中的图片。

```python
for chat in listen_list:
    wx.AddListenChat(who=chat, savepic=True)
```

**步骤三**：持续监听消息，收到好友类型的消息后自动回复“收到”。

```python
import time

wait = 1  # 设置每隔1秒检查一次新消息

while True:
    msgs = wx.GetListenMessage()
    for chat in msgs:
        who = chat.who              # 获取聊天窗口名（人或群名）
        one_msgs = msgs.get(chat)   # 获取消息内容
        for msg in one_msgs:
            msgtype = msg.type       # 获取消息类型
            content = msg.content    # 获取消息内容
            print(f'【{who}】：{content}')
            
            if msgtype == 'friend':
                chat.SendMsg('收到')  # 回复“收到”
    time.sleep(wait)
```

> **成功提示**：恭喜您，已经成功实现了一个简单的微信机器人，能够自动回复消息！

---

## 方法说明

本节详细介绍 wxautox 提供的主要方法及其使用方法。

### 1. 监听

#### 1.1 添加监听对象 `AddListenChat`

**方法说明**：

`AddListenChat` 方法用于添加需要监听的聊天对象（好友或群聊），以便接收和处理新消息。

**参数说明**：

| 参数    | 类型    | 默认值 | 说明                                                         |
| ------- | ------- | ------ | ------------------------------------------------------------ |
| who     | `str`   | /      | 要监听的对象（好友或群聊）的名称                             |
| savepic | `bool`  | `False`| 是否保存新消息中的图片，`True` 保存，`False` 不保存           |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 设置监听列表
listen_list = [
    '张三',
    '李四',
    '工作群A',
    '工作群B'
]

# 添加监听对象，保存新消息图片
for chat in listen_list:
    wx.AddListenChat(who=chat, savepic=True)
```

#### 1.2 获取监听消息 `GetListenMessage`

**方法说明**：

`GetListenMessage` 方法用于获取所有监听对象的新消息。返回的数据类型为字典，键为监听对象，值为消息对象列表。

**参数说明**：

| 参数 | 类型 | 默认值 | 说明                       |
| ---- | ---- | ------ | -------------------------- |
| none | -    | -      | 当前方法不接受任何参数     |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 获取监听消息并处理
msgs = wx.GetListenMessage()
for chat in msgs:
    who = chat.who              # 获取聊天窗口名（人或群名）
    one_msgs = msgs.get(chat)   # 获取消息内容
    for msg in one_msgs:
        msgtype = msg.type       # 获取消息类型
        content = msg.content    # 获取消息内容
        print(f'【{who}】：{content}')
        
        if msgtype == 'friend':
            chat.SendMsg('收到')  # 回复“收到”
```

#### 1.3 移除监听对象 `RemoveListenChat`

**方法说明**：

`RemoveListenChat` 方法用于移除不再需要监听的聊天对象。

**参数说明**：

| 参数 | 类型  | 默认值 | 说明                       |
| ---- | ----- | ------ | -------------------------- |
| who  | `str` | /      | 要移除的监听对象名称       |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 移除不需要监听的对象
wx.RemoveListenChat(who='李四')
```

#### 1.4 获取所有监听对象 `GetAllListenChat`

**方法说明**：

`GetAllListenChat` 方法用于获取当前所有被监听的聊天对象列表。

**参数说明**：

| 参数 | 类型 | 默认值 | 说明 |
| ---- | ---- | ------ | ---- |
| none | -    | -      | 当前方法不接受任何参数 |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 获取所有监听对象
listen_chats = wx.GetAllListenChat()
print(listen_chats)
# 示例输出: ['张三', '工作群A', '工作群B']
```

#### 1.5 示例：创建一个消息回复机器人

以下示例代码展示了如何使用 wxautox 创建一个简单的消息回复机器人，能够自动回复特定好友或群聊的消息。

**示例代码**：

```python
from wxautox import WeChat
import time

wx = WeChat()

# 设置监听列表
listen_list = [
    '张三',
    '李四',
    '工作群A',
    '工作群B'
]

# 添加监听对象，保存新消息图片
for chat in listen_list:
    wx.AddListenChat(who=chat, savepic=True)

wait = 1  # 设置每隔1秒检查一次新消息

while True:
    msgs = wx.GetListenMessage()
    for chat in msgs:
        who = chat.who              # 获取聊天窗口名（人或群名）
        one_msgs = msgs.get(chat)   # 获取消息内容
        for msg in one_msgs:
            msgtype = msg.type       # 获取消息类型
            content = msg.content    # 获取消息内容
            print(f'【{who}】：{content}')
            
            if msgtype == 'friend':
                chat.SendMsg('收到')  # 回复“收到”
    time.sleep(wait)
```

> **说明**：
> - **步骤一**：定义需要监听的聊天对象列表。
> - **步骤二**：通过 `AddListenChat` 方法添加监听对象，并选择是否保存图片。
> - **步骤三**：使用一个无限循环不断调用 `GetListenMessage` 方法获取新消息，并根据消息类型自动回复。

---

### 2. 发送消息

#### 2.1 发送文字消息 `SendMsg`

**方法说明**：

`SendMsg` 方法用于发送文字消息。

**参数说明**：

| 参数   | 类型         | 默认值 | 说明                                                                 |
| ------ | ------------ | ------ | -------------------------------------------------------------------- |
| msg    | `str`        | /      | 要发送的文字内容                                                     |
| who    | `str`        | `None` | 要发送给的对象（好友或群聊），默认为当前打开的聊天窗口               |
| clear  | `bool`       | `True` | 是否清除原本聊天编辑框的内容                                       |
| at     | `list`/`str` | `None` | 要 @ 的人，可以是一个或多个人，例如："张三" 或 ["张三", "李四"]       |
| exact  | `bool`       | `False`| 是否精确匹配 `who`，默认 `False`                                   |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 发送消息给文件传输助手
msg = 'hello, wxautox!'
who = '文件传输助手'
wx.SendMsg(msg=msg, who=who)
```

**附带 @ 群好友的消息**

```python
from wxautox import WeChat

wx = WeChat()

msg = 'xxxxxxx，收到请回复！'
who = '工作群A'
at = ['张三', '李四']   # 要 @ 的人
wx.SendMsg(msg=msg, who=who, at=at)
```

#### 2.2 发送打字机模式消息 `SendTypingText`

**方法说明**：

`SendTypingText` 方法可模拟打字机模式逐字输入，行为更贴近人类。该方法还支持消息内 @ 群好友，不必像原来一样 @ 内容只能固定在文字内容前面。

**参数说明**：

| 参数   | 类型  | 默认值 | 说明                                                               |
| ------ | ----- | ------ | ------------------------------------------------------------------ |
| msg    | `str` | /      | 要发送的文本消息                                                   |
| who    | `str` | `None` | 要发送给的对象（好友或群聊），默认为当前打开的聊天窗口             |
| clear  | `bool`| `True` | 是否清除原本聊天编辑框的内容                                     |

**示例代码**：

```python
text = '''你好：
hello{@张三}你好{@李四}下午好

通知：xxxxxxx

再见'''
wx.SendTypingText(text)
```

![打字机模式示例](https://your-image-link.com/typing-mode.png) *(请根据实际链接修改)*

#### 2.3 发送图片/视频/文件消息 `SendFiles`

**方法说明**：

`SendFiles` 方法用于发送图片、视频或文件。

**参数说明**：

| 参数     | 类型          | 默认值 | 说明                                                                         |
| -------- | ------------- | ------ | ---------------------------------------------------------------------------- |
| filepath | `str` / `list`| /      | 指定文件路径，单个文件为 `str`，多个文件为 `list`                         |
| who      | `str`         | `None` | 要发送给的对象，默认为当前打开的聊天窗口                                 |
| exact    | `bool`        | `False`| 是否精确匹配 `who`，默认 `False`                                           |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 发送图片、文件和视频
files = [
    r'C:\Users\user\Desktop\1.jpg',   # 图片
    r'C:\Users\user\Desktop\2.txt',   # 文件
    r'C:\Users\user\Desktop\3.mp4'    # 视频
]

who = '文件传输助手'
wx.SendFiles(filepath=files, who=who)
```

#### 2.4 发送自定义表情包 `SendEmotion`

**方法说明**：

`SendEmotion` 方法用于发送自定义表情包。

**参数说明**：

| 参数          | 类型  | 默认值 | 说明                                                                                       |
| ------------- | ----- | ------ | ------------------------------------------------------------------------------------------ |
| emotion_index | `int` | /      | 要发送的索引值，从 0 开始。若 `emotion_index` 大于等于账号内自定义表情数量，则发送失败，返回 `False`，成功返回 `True` |
| who           | `str` | `None` | 要发送给的对象，默认为当前打开的聊天窗口                                             |
| exact         | `bool`| `False`| 是否精确匹配 `who`，默认 `False`                                                         |

**示例代码**：

```python
index = 0 
success = wx.SendEmotion(emotion_index=index) 
if success:
    print("表情发送成功")
else:
    print("表情发送失败")
```

#### 2.7 优化 `ChatWith` 方法

**方法说明**：

优化了 `ChatWith` 及各种发送消息的方法，增加 `exact` 参数，用于判断在搜索 `who` 时是否需要精准匹配，默认为 `False`，改为 `True` 则需要一字不差才进行发送。

**参数说明**：

| 参数    | 类型   | 默认值 | 说明                                   |
| ------- | ------ | ------ | -------------------------------------- |
| who     | `str`  | /      | 要打开的聊天窗口好友名；最好完整匹配，不完全匹配只会选取搜索框第一个 |
| timeout | `int`  | `2`    | 超时时间，默认 2 秒                     |
| exact   | `bool` | `False`| 是否精确匹配，默认 `False`             |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 精确匹配聊天窗口
who = '张三'
wx.ChatWith(who=who, exact=True)
```

#### 2.10 自动保存消息内的卡片链接 `parseurl` 参数

以下方法增加 `parseurl` 参数，用于自动解析消息内卡片消息的 URL 链接：

- `GetAllMessage`
- `GetListenMessage`
- `GetAllNewMessage`
- `GetNextNewMessage`
- `AddListenChat`

**示例代码**：

```python
msgs = wx.GetAllMessage(parseurl=True)
# 卡片链接解析后的格式为：
# "[wxautox卡片链接解析]https://xxxxxxx"
# [
#     ...
#     ['Time', '13:34'],
#     ['Self', '[wxautox卡片链接解析]https://mp.weixin.qq.com/s/x8ilebSF5_KYd0PloyZm-Q']
# ]
```

#### 2.11 获取当前聊天窗口详情 `CurrentChat` 方法增加 `details` 参数

**方法说明**：

`CurrentChat` 方法用于获取当前聊天窗口的详细信息。

**参数说明**：

| 参数    | 类型  | 默认值 | 说明                                      |
| ------- | ----- | ------ | ----------------------------------------- |
| details | `bool`| `False`| 是否获取详细信息，`True` 获取，`False` 不获取 |

**示例代码**：

```python
details = wx.CurrentChat(details=True)
print(details)
# 示例输出:
# {
#     'chat_type': 'group', 
#     'chat_name': 'wxautox四群', 
#     'group_member_count': 490
# }
```

**返回值说明**：

| 键                 | 说明                                                           |
| ------------------ | -------------------------------------------------------------- |
| id                 | 消息的 UI 控件提取到的 runtimeid，唯一，不用可忽略             |
| type               | 消息类型，`friend` 为其他人发的消息，`time` 时间消息，`sys` 系统消息，`self` 自己发的消息 |
| sender             | 消息发送人的昵称                                               |
| content            | 消息内容                                                       |
| sender_remark      | 消息发送人的备注，没有则为 `None`                              |
| chat_type          | 聊天类型，`group` 为群聊，`friend` 为好友聊天，`official` 为公众号 |
| chat_name          | 当前聊天对象名，群名或好友名                                     |
| group_member_count | 群聊人数，如果是群消息则有该参数                               |

---

### 3. 获取消息

#### 3.1 获取当前聊天窗口所有消息 `GetAllMessage`

**方法说明**：

`GetAllMessage` 方法用于获取当前聊天窗口的所有消息，返回消息对象列表。

**参数说明**：

| 参数      | 类型   | 默认值 | 说明                                     |
| --------- | ------ | ------ | ---------------------------------------- |
| savepic   | `bool` | `False` | 是否自动保存聊天图片                     |
| savefile  | `bool` | `False` | 是否自动保存聊天文件                     |
| savevoice | `bool` | `False` | 是否自动保存聊天语音转文字内容           |
| parseurl  | `bool` | `False` | 是否自动解析消息中的URL链接               |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 获取当前聊天窗口消息并保存图片、文件及语音转文字内容，并解析URL
msgs = wx.GetAllMessage(
    savepic=True,    # 保存图片
    savefile=True,   # 保存文件
    savevoice=True,  # 保存语音转文字内容
    parseurl=True    # 解析URL链接
)

# 输出消息内容
for msg in msgs:
    if msg.type == 'sys':
        print(f'【系统消息】{msg.content}')
    elif msg.type == 'friend':
        sender = msg.sender  # 可替换为 msg.sender_remark 获取备注名
        print(f'{sender.rjust(20)}：{msg.content}')
    elif msg.type == 'self':
        print(f'{msg.sender.ljust(20)}：{msg.content}')
    elif msg.type == 'time':
        print(f'\n【时间消息】{msg.time}')
    elif msg.type == 'recall':
        print(f'【撤回消息】{msg.content}')
```

> **注意**：自动保存文件功能在处理大文件时可能存在 BUG。

#### 3.2 加载更多历史消息 `LoadMoreMessage`

**方法说明**：

`LoadMoreMessage` 方法用于加载更多历史消息，需配合 `GetAllMessage` 方法使用，以获取更多历史消息。

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 加载更多历史消息
wx.LoadMoreMessage()

# 获取当前聊天窗口消息
msgs = wx.GetAllMessage()
# 根据需要自行构建消息处理逻辑
```

> **提示**：`LoadMoreMessage` 方法加载更多历史消息时，需确保当前聊天窗口存在历史消息，否则调用无效。

#### 3.3 获取新消息

##### 3.3.1 获取主窗口新消息

- **`GetAllNewMessage`**：获取所有新消息。
- **`GetNextNewMessage`**：获取下一条新消息。

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 获取所有新消息
msgs = wx.GetAllNewMessage()

# 获取下一条新消息
next_msg = wx.GetNextNewMessage()
```

> **注意**：`GetAllNewMessage` 和 `GetNextNewMessage` 返回的数据类型均为字典，结构如下：

```python
{
    '张三': [msg1, msg2, ...],
    '李四': [msg1, msg2, ...],
    ...
}
```

##### 3.3.2 监听消息 `GetListenMessage`

在调用 `AddListenChat` 方法添加监听对象后，通过 `GetListenMessage` 方法获取监听消息。

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 设置监听列表
listen_list = [
    '张三',
    '李四',
    '工作群A',
    '工作群B'
]

# 添加监听对象，保存新消息图片
for chat in listen_list:
    wx.AddListenChat(who=chat, savepic=True)

# 获取监听消息并回复
msgs = wx.GetListenMessage()
for chat in msgs:
    one_msgs = msgs.get(chat)  # 获取消息内容
    for msg in one_msgs:
        if msg.type == 'friend':
            sender = msg.sender  # 可替换为 msg.sender_remark 获取备注名
            print(f'{sender.rjust(20)}：{msg.content}')
            chat.SendMsg('收到')  # 回复“收到”
```

> **提示**：`GetListenMessage` 方法返回的是一个字典，键为监听对象，值为消息对象列表。

---

### 4. 添加好友

#### 4.1 发起好友申请 `AddNewFriend`

**方法说明**：

`AddNewFriend` 方法用于发起好友申请。

**参数说明**：

| 参数       | 类型        | 默认值            | 说明                                     |
| ---------- | ----------- | ----------------- | ---------------------------------------- |
| keywords   | `str`       | /                 | 微信号、手机号、QQ号                      |
| addmsg     | `str`       | `'你好，我是xxxx'` | 添加好友的消息                            |
| remark     | `str`       | `None`            | 备注名                                   |
| tags       | `list`      | `None`            | 标签列表，如 `['朋友', '同事']`             |
| permission | `str`       | `'朋友圈'`        | 权限设置，`'朋友圈'` 或 `'仅聊天'`        |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

keywords = '13800000000'      # 微信号、手机号、QQ号
addmsg = '你好，我是xxxx'      # 添加好友的消息
remark = '备注名字'            # 备注名，无则无需设置
tags = ['朋友', '同事']        # 标签列表

# 发起好友申请
wx.AddNewFriend(keywords, addmsg=addmsg, remark=remark, tags=tags, permission='朋友圈')
```

#### 4.2 接受好友请求

##### 4.2.1 获取新的好友申请对象列表 `GetNewFriends`

**方法说明**：

`GetNewFriends` 方法用于获取新的好友申请对象列表。

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

new_friends = wx.GetNewFriends()
# 示例输出:
# [<wxautox New Friends Element at 0x1e95fced080 (张三: 你好,我是xxx群的张三)>,
#  <wxautox New Friends Element at 0x1e95fced081 (李四: 你好,我是xxx群的李四)>]
```

##### 4.2.2 通过好友申请对象接受好友请求

**示例代码**：

```python
# 获取第一个可接受的新好友对象
new_friend1 = new_friends[0]

print(new_friend1.name)  # 获取好友申请昵称
# 输出: 张三

print(new_friend1.msg)   # 获取好友申请信息
# 输出: 你好,我是xxx群的张三

# 接受好友请求，并添加备注“备注张三”及标签“wxautox”
new_friend1.Accept(remark='备注张三', tags=['wxautox'])

# 切换回聊天页面
wx.SwitchToChat()
```

> **提示**：接受好友请求后，需调用 `SwitchToChat` 方法切换回聊天页面，否则无法使用其他聊天相关的方法。

---

### 5. 切换聊天窗口

#### 5.1 切换到指定好友聊天框 `ChatWith`

**方法说明**：

`ChatWith` 方法用于切换到指定好友或群聊的聊天窗口。

**参数说明**：

| 参数    | 类型   | 默认值 | 说明                                   |
| ------- | ------ | ------ | -------------------------------------- |
| who     | `str`  | /      | 要打开的聊天窗口好友名或群名           |
| timeout | `int`  | `2`    | 超时时间，默认 2 秒                     |
| exact   | `bool` | `False`| 是否精确匹配，默认 `False`             |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 切换到指定好友聊天框
who = '张三'
wx.ChatWith(who=who, exact=True)
```

#### 5.2 切换微信主页面

通过点击微信左侧黑色侧边栏的相应图标按钮，实现页面切换。

##### 5.2.1 切换到聊天页面 `SwitchToChat`

```python
from wxautox import WeChat

wx = WeChat()

# 切换到聊天页面
wx.SwitchToChat()
```

##### 5.2.2 切换到通讯录页面 `SwitchToContact`

```python
from wxautox import WeChat

wx = WeChat()

# 切换到通讯录页面
wx.SwitchToContact()
```

---

### 6. 获取好友信息

#### 6.1 获取粗略信息 `GetAllFriends`

**方法说明**：

`GetAllFriends` 方法用于获取所有好友的基本信息。

**参数说明**：

| 参数      | 类型   | 默认值 | 说明                                     |
| --------- | ------ | ------ | ---------------------------------------- |
| keywords  | `str`  | `None` | 搜索关键词，只返回包含关键词的好友列表   |
| speed     | `int`  | `5`    | 滚动速度，数值越大滚动越快，但可能遗漏，建议 1-5 |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

friend_infos = wx.GetAllFriends()
# 示例输出:
# [
#     {'nickname': '张三', 'remark': '张总', 'tags': None},
#     {'nickname': '李四', 'remark': None, 'tags': ['同事', '初中同学']},
#     {'nickname': '王五', 'remark': None, 'tags': None},
#     ...
# ]
```

> **注意**：该方法的运行时间取决于好友数量，约为每秒 6-8 个好友的速度。未经过大量测试，可能存在未知问题，如有问题请在微信群内反馈。

#### 6.2 获取详细信息 `GetAllFriendDetails`

**方法说明**：

`GetAllFriendDetails` 方法用于获取好友的详细信息。

**参数说明**：

| 参数    | 类型 | 默认值    | 说明                                                           |
| ------- | ---- | --------- | -------------------------------------------------------------- |
| n       | `int`| `None`    | 获取前 `n` 个好友的详细信息，默认为 `None`，即获取所有好友的详细信息 |
| timeout | `int`| `0xFFFFF` | 获取好友详细信息的超时时间，单位为秒                           |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 获取所有好友的详细信息
friend_details = wx.GetAllFriendDetails()

# 示例输出:
# [
#     {
#         '微信号：': 'abc123456',
#         '地区：': '上海 浦东新区',
#         '备注': '',
#         '标签': 'wxautox',
#         '共同群聊': '1个',
#         '来源': '通过扫一扫添加',
#         '昵称': '张三'
#     },
#     {
#         '备注': '',
#         '企业': '广州融创文旅城',
#         '实名': '***',
#         '官方商城': '🎫购滑雪票入口🎫',
#         '通知': '回复时间为工作日9点-18点',
#         '会员商城': '🏂热雪值兑换雪票🏂',
#         '冰箱赞滑': '👬申请冰箱主理人👭',
#         '全民滑雪': '购票赢黄金会籍',
#         '共同群聊': '1个',
#         '昵称': '广州大冰箱'
#     },
#     ...
# ]
```

> **注意**：
> - 该方法的运行时间较长，约为 0.5-1 秒获取一个好友的详细信息。若好友数量较多，可通过设置 `n` 或 `timeout` 参数以加快获取速度。
> - 若遇到企业微信的好友且处于已离职状态，可能会导致微信客户端卡死，需重启（此为微信客户端 BUG）。
> - 该方法未经过大量测试，可能存在未知问题，如有问题请在微信群内反馈。

#### 6.3 获取所有好友详情 `GetFriendDetails`

**方法说明**：

`GetFriendDetails` 方法用于获取所有好友的详细信息，类似于 `GetAllFriendDetails`，但提供了更高的灵活性和控制。

**参数说明**：

| 参数    | 类型 | 默认值    | 说明                                                           |
| ------- | ---- | --------- | -------------------------------------------------------------- |
| n       | `int`| `None`    | 获取前 `n` 个好友的详细信息，默认为 `None`，即获取所有好友的详细信息 |
| timeout | `int`| `0xFFFFF` | 获取好友详细信息的超时时间，单位为秒                           |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 获取所有好友的详细信息
friend_details = wx.GetFriendDetails()

# 示例输出:
# [
#     {
#         '微信号': 'abc123456',
#         '地区': '上海 浦东新区',
#         '备注': '',
#         '标签': 'wxautox',
#         '共同群聊': '1个',
#         '来源': '通过扫一扫添加',
#         '昵称': '张三'
#     },
#     {
#         '备注': '',
#         '企业': '广州融创文旅城',
#         '实名': '***',
#         '官方商城': '🎫购滑雪票入口🎫',
#         '通知': '回复时间为工作日9点-18点',
#         '会员商城': '🏂热雪值兑换雪票🏂',
#         '冰箱赞滑': '👬申请冰箱主理人👭',
#         '全民滑雪': '购票赢黄金会籍',
#         '共同群聊': '1个',
#         '昵称': '广州大冰箱'
#     },
#     ...
# ]
```

---

### 7. 群管理

#### 7.1 邀请入群 `AddGroupMembers`

**方法说明**：

`AddGroupMembers` 方法用于邀请好友加入群聊。

**参数说明**：

| 参数    | 类型   | 默认值 | 说明                                      |
| ------- | ------ | ------ | ----------------------------------------- |
| group   | `str`  | /      | 群名或者群备注名                          |
| members | `list` | /      | 成员列表，可以是昵称、备注名、微信号；最好是微信号或者唯一的备注名 |

**示例代码**：

```python
from wxautox import WeChat
import time

wx = WeChat()

targets = [
    '好友1',
    '好友2',
    '好友3'
]
group = 'wxautoxplus交流群'
wx.AddGroupMembers(group, targets)
```

#### 7.2 修改群聊名、备注、群公告、我在本群的昵称 `ManageGroup`

**方法说明**：

`ManageGroup` 方法用于修改群聊的名称、备注、公告以及个人在群内的昵称，或选择退出群聊。

**参数说明**：

| 参数     | 类型   | 默认值 | 说明                                           |
| -------- | ------ | ------ | ---------------------------------------------- |
| name     | `str`  | `None` | 修改群名称                                     |
| remark   | `str`  | `None` | 修改备注名                                     |
| myname   | `str`  | `None` | 修改我的群昵称                                 |
| notice   | `str`  | `None` | 修改群公告                                     |
| quit     | `bool` | `False`| 是否退出群，当该项为 `True` 时，其他参数无效    |

**示例代码**：

```python
remark = '工作群（不要发错）'
result = wx.ManageGroup(remark=remark)
# 返回值：dict
# {
#     'remark': True   # 如果未成功则为 False
# }
```

#### 7.3 获取群成员 `GetGroupMembers`

**方法说明**：

`GetGroupMembers` 方法用于获取当前群聊的成员列表。

**示例代码**：

```python
group = '工作群A'
members = wx.GetGroupMembers(group)
print(members)
# 示例输出: ['张三', '李四', '王五', ...]
```

#### 7.4 发起群语音通话 `CallGroupMsg`

**方法说明**：

`CallGroupMsg` 方法用于发起群语音通话。

**示例代码**：

```python
group = '工作群A'
wx.CallGroupMsg(group)
```

---

### 8. 好友管理

#### 8.1 修改好友备注、增加标签 `ManageFriend`

**方法说明**：

`ManageFriend` 方法用于修改好友的备注名及增加标签。

**参数说明**：

| 参数    | 类型   | 默认值 | 说明                             |
| ------- | ------ | ------ | -------------------------------- |
| remark  | `str`  | `None` | 修改备注名                       |
| tags    | `list` | `None` | 要增加的标签列表，如 `['朋友', '同事']` |

**示例代码**：

```python
remark = '张三'
tags = ['同事']
success = wx.ManageFriend(remark=remark, tags=tags)
# 返回值：bool，是否成功修改备注名或标签

if success:
    print("好友备注和标签修改成功")
else:
    print("好友备注和标签修改失败")
```

---

### 9. 通知管理

#### 9.1 消息免打扰 `MuteNotifications`

**方法说明**：

`MuteNotifications` 方法用于对当前聊天对象开启或关闭消息免打扰。

**参数说明**：

| 参数 | 类型   | 默认值 | 说明                                     |
| ---- | ------ | ------ | ---------------------------------------- |
| mute | `bool` | `True` | 对当前聊天对象开启或关闭消息免打扰，`True` 开启免打扰，`False` 关闭免打扰 |

**示例代码**：

```python
group = '工作群'
mute = True   # True 为开启免打扰，False 为关闭免打扰

# 先打开指定聊天窗口，再执行免打扰操作
wx.ChatWith(group)
wx.MuteNotifications(mute=mute)
```

---

## 对象说明

本节介绍 wxautox 中的主要对象及其属性和方法。

### 1. 消息对象

消息对象是通过调用 `GetAllMessage`、`GetListenMessage` 等方法返回的对象，包含了消息的所有信息，包括消息类型、内容、发送者等。消息类型主要包括系统消息、时间消息、撤回消息、好友消息和自己的消息。

#### 1.1 系统消息

**属性**：

| 属性名 | 类型                     | 说明                           |
| ------ | ------------------------ | ------------------------------ |
| type   | `str`                    | 消息类型，固定为 `sys`         |
| content| `str`                    | 消息内容                         |
| sender | `str`                    | 发送者，固定为 `SYS`             |
| info   | `list`                   | 原始消息信息，包含所有信息       |
| control| `uiautomation.Control`   | 消息的 UIAutomation 控件        |
| id     | `str`                    | 消息 ID                         |

**示例代码**：

```python
msgs = wx.GetAllMessage()
for msg in msgs:
    if msg.type == 'sys':
        print(f'【系统消息】{msg.content}')
```

#### 1.2 时间消息

**属性**：

| 属性名 | 类型                     | 说明                                   |
| ------ | ------------------------ | -------------------------------------- |
| type   | `str`                    | 消息类型，固定为 `time`                 |
| content| `str`                    | 消息内容                                 |
| sender | `str`                    | 发送者，固定为 `Time`                   |
| time   | `str`                    | 时间消息内容，格式为 `%Y-%m-%d %H:%M`    |
| info   | `list`                   | 原始消息信息，包含所有信息             |
| control| `uiautomation.Control`   | 消息的 UIAutomation 控件        |
| id     | `str`                    | 消息 ID                                 |

**示例代码**：

```python
msgs = wx.GetAllMessage()
for msg in msgs:
    if msg.type == 'time':
        print(f'【时间消息】{msg.time}')
```

#### 1.3 撤回消息

**属性**：

| 属性名 | 类型                     | 说明                                 |
| ------ | ------------------------ | ------------------------------------ |
| type   | `str`                    | 消息类型，固定为 `recall`             |
| content| `str`                    | 消息内容                               |
| sender | `str`                    | 发送者，固定为 `Recall`               |
| info   | `list`                   | 原始消息信息，包含所有信息           |
| control| `uiautomation.Control`   | 消息的 UIAutomation 控件        |
| id     | `str`                    | 消息 ID                               |

**示例代码**：

```python
msgs = wx.GetAllMessage()
for msg in msgs:
    if msg.type == 'recall':
        print(f'【撤回消息】{msg.content}')
```

#### 1.4 好友消息

**属性**：

| 属性名        | 类型                     | 说明                                     |
| ------------- | ------------------------ | ---------------------------------------- |
| type          | `str`                    | 消息类型，固定为 `friend`                 |
| content       | `str`                    | 消息内容                                 |
| sender        | `str`                    | 发送者                                   |
| sender_remark | `str`                    | 发送者备注名                             |
| info          | `list`                   | 原始消息信息，包含所有信息               |
| control       | `uiautomation.Control`   | 消息的 UIAutomation 控件        |
| id            | `str`                    | 消息 ID                                 |

**支持方法**：

| 方法名      | 说明                                                         |
| ----------- | ------------------------------------------------------------ |
| quote       | 引用消息进行回复，参数为回复内容 `str`                         |
| forward     | 转发消息，参数为好友名 `str`                                   |
| parse       | 解析合并消息内容，仅在合并转发消息时有效，返回列表             |
| add_friend  | 添加好友，参数包括 `addmsg`, `remark`, `tags`, `permission`   |

**示例代码**：

```python
msgs = wx.GetAllMessage()
for msg in msgs[::-1]:
    if msg.type == 'friend':
        sender = msg.sender  # 可替换为 msg.sender_remark 获取备注名
        print(f'{sender}：{msg.content}')
        msg.quote('回复消息')  # 引用消息进行回复
        # 添加好友示例
        msg.add_friend(addmsg='你好！', remark='新朋友', tags=['同事'], permission='仅聊天')
        break
```

#### 1.5 自己的消息

**属性**：

| 属性名 | 类型                     | 说明                           |
| ------ | ------------------------ | ------------------------------ |
| type   | `str`                    | 消息类型，固定为 `self`         |
| content| `str`                    | 消息内容                         |
| sender | `str`                    | 发送者                           |
| info   | `list`                   | 原始消息信息，包含所有信息       |
| control| `uiautomation.Control`   | 消息的 UIAutomation 控件        |
| id     | `str`                    | 消息 ID                         |

**支持方法**：

| 方法名 | 说明                                                         |
| ------ | ------------------------------------------------------------ |
| quote  | 引用消息进行回复，参数为回复内容 `str`                         |
| forward| 转发消息，参数为好友名 `str`                                   |
| parse  | 解析合并消息内容，仅在合并转发消息时有效，返回列表             |

**示例代码**：

```python
msgs = wx.GetAllMessage()
for msg in msgs[::-1]:
    if msg.type == 'self':
        print(f'{msg.sender}：{msg.content}')
        msg.quote('回复消息')  # 引用消息进行回复
        break
```

---

### 2. 聊天窗口对象

聊天窗口对象指在监听消息模式下打开的独立聊天窗口，用于管理该窗口的消息和发送操作。

**支持属性**：

| 属性名  | 类型                  | 说明                                     |
| ------- | --------------------- | ---------------------------------------- |
| who     | `str`                 | 当前聊天窗口的对象名                     |
| UiaAPI  | `uiautomation.Control`| 当前聊天窗口的 UIAutomation 控件         |
| editbox | `uiautomation.Control`| 当前聊天窗口输入框的 UIAutomation 控件   |

**支持方法**：

| 方法名           | 说明                                     |
| ---------------- | ---------------------------------------- |
| AtAll            | @所有人                                  |
| SendMsg          | 发送消息                                 |
| SendFiles        | 发送文件                                 |
| SendEmotion      | 发送自定义表情包                         |
| SendTypingText   | 发送打字机模式消息                       |
| GetAllMessage    | 获取所有消息                             |
| GetNewMessage    | 获取新消息                               |
| LoadMoreMessage  | 加载更多消息                             |
| GetGroupMembers  | 获取群成员                               |
| CallGroupMsg     | 发起群语音通话                           |
| ModifyGroupInfo  | 修改群聊信息（群名称、备注、公告等）       |

---

### 3. 会话对象

会话对象代表微信左侧的会话列表，用于获取会话相关的信息。

**支持属性**：

| 属性名  | 类型  | 说明                       |
| ------- | ----- | -------------------------- |
| name    | `str` | 会话对象名                 |
| time    | `str` | 最后一条消息的时间         |
| content | `str` | 最后一条消息的内容         |
| isnew   | `bool`| 是否有新消息               |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

sessions = wx.GetSession()

for session in sessions:
    print(f"============== 【{session.name}】 ==============")
    print(f"最后一条消息时间: {session.time}")
    print(f"最后一条消息内容: {session.content}")
    print(f"是否有新消息: {session.isnew}", end='\n\n')
```

---

### 4. 朋友圈对象

#### 4.1 窗口对象

朋友圈窗口对象指的是朋友圈的窗口对象，提供对朋友圈窗口的各种操作，如获取朋友圈内容、刷新、关闭等功能。

**获取朋友圈对象**：

```python
from wxautox import WeChat

wx = WeChat()
pyq = wx.Moments()   
# 打开朋友圈并获取朋友圈窗口对象
# （如果为 None 则说明您未开启朋友圈功能，需要在手机端设置）
```

**朋友圈窗口对象**

> 这里的 `pyq` 将在后续文档中用来指代朋友圈窗口对象，后续文档内不再重复定义。

##### 4.1.1 获取朋友圈内容 `GetMoments`

**方法说明**：

`GetMoments` 方法用于获取朋友圈内容。

**参数说明**：

| 参数      | 类型  | 默认值 | 说明                                                         |
| --------- | ----- | ------ | ------------------------------------------------------------ |
| next_page | `bool`| `False`| 是否翻页后再获取                                             |
| speed1    | `int` | `3`    | 翻页时的滚动速度，数值越大滚动越快，但可能导致遗漏，建议 3-10 之间 |
| speed2    | `int` | `1`    | 翻页最后时的速度，避免翻页过多导致遗漏，一般比 `speed1` 慢，建议 1-3   |

**示例代码**：

```python
# 获取当前页面的朋友圈内容
moments = pyq.GetMoments()

# 通过 `next_page` 参数获取下一页的朋友圈内容
moments_next = pyq.GetMoments(next_page=True)
```

获取到的 `moments` 是一个列表，列表中每个元素都是一个朋友圈对象。

##### 4.1.2 刷新朋友圈 `Refresh`

**方法说明**：

`Refresh` 方法用于刷新朋友圈。

**示例代码**：

```python
# 刷新朋友圈
pyq.Refresh()
```

##### 4.1.3 关闭朋友圈 `Close`

**方法说明**：

`Close` 方法用于关闭朋友圈窗口。

**示例代码**：

```python
# 关闭朋友圈
pyq.Close()
```

#### 4.2 消息对象

朋友圈消息对象指的是朋友圈中的每一条朋友圈，提供对朋友圈的各种操作，如获取朋友圈内容、点赞、评论等功能。

**获取朋友圈对象**：

```python
moments = pyq.GetMoments()

# 获取第一条朋友圈
moment = moments[0]
```

**朋友圈消息对象**

> 这里的 `moment` 将在后续文档中用来指代朋友圈消息对象，后续文档内不再重复定义。

##### 4.2.1 获取朋友圈内容

**示例代码**：

```python
# 获取朋友圈内容
info = moment.info
# 示例输出:
# {
#     'type': 'moment',            # 类型，分为 `朋友圈` 和 `广告`
#     'id': '4236572776458165',    # ID
#     'sender': '天天鲜花2号客服',   # 发送者
#     'content': '客订花束',        # 内容，就是朋友圈的文字内容，如果没有文字内容则为空字符串
#     'time': '4分钟前',            # 发送时间
#     'img_count': 3,              # 图片数量
#     'comments': [],              # 评论
#     'addr': '',                  # 发送位置
#     'likes': []                  # 点赞
# }
```

**访问属性**：

```python
print(moment.sender)    # '天天鲜花2号客服'
print(moment.content)   # '客订花束'
print(moment.time)      # '4分钟前'
# info 中所有的键值对都可以通过对象的属性来获取，就不一一列举了
```

##### 4.2.2 获取朋友圈图片 `SaveImages`

**方法说明**：

`SaveImages` 方法用于保存朋友圈中的图片到本地。

**参数说明**：

| 参数       | 类型          | 默认值 | 说明                                                             |
| ---------- | ------------- | ------ | ---------------------------------------------------------------- |
| save_index | `int` / `list`| `None` | 保存图片的索引，可以是一个整数或列表；如果为 `None` 则保存所有图片 |
| savepath   | `str`         | `None` | 绝对路径，包括文件名和后缀，例如："D:/Images/微信图片_xxxxxx.jpg"，如果为 `None` 则保存到默认路径 |

**示例代码**：

```python
# 获取朋友圈图片
images = moment.SaveImages()
# 示例输出:
# [
#     'D:/Images/微信图片_xxxxxx1.jpg',
#     'D:/Images/微信图片_xxxxxx2.jpg',
#     'D:/Images/微信图片_xxxxxx3.jpg',
#     ...
# ]
```

##### 4.2.3 获取好友信息 `sender_info`

**方法说明**：

通过消息对象获取好友（群好友）信息。

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()
msgs = wx.GetAllMessage()

# 获取最后一条消息，假设为好友发来的消息
msg = msgs[-1]

# 仅消息类型为 `friend` 的才有该方法
if msg.type == 'friend':
    sender_info = msg.sender_info()

# 示例输出:
# {
#     'nickname': '张三',
#     'id': '123456',
#     'remark': '同事张三',
#     'tags': '同事',
#     'source': '通过扫一扫添加',
#     'signature': '张三的个性签名'
# }
```

**返回值说明**：

| 键         | 说明                                     |
| ---------- | ---------------------------------------- |
| nickname   | 昵称                                     |
| id         | 消息的 UI 控件提取到的 runtimeid，唯一，不用可忽略 |
| remark     | 备注                                     |
| tags       | 标签                                     |
| source     | 来源                                     |
| signature  | 个性签名                                 |

##### 4.2.4 获取当前聊天页面详情 `details` 属性

**示例代码**：

```python
# 获取当前聊天窗口详情
details = wx.CurrentChat(details=True)
print(details)
# 示例输出:
# {
#     'chat_type': 'group', 
#     'chat_name': 'wxautox四群', 
#     'group_member_count': 490
# }
```

**返回值说明**：

| 键                 | 说明                                                           |
| ------------------ | -------------------------------------------------------------- |
| id                 | 消息的 UI 控件提取到的 runtimeid，唯一，不用可忽略             |
| type               | 消息类型，`friend` 为其他人发的消息，`time` 时间消息，`sys` 系统消息，`self` 自己发的消息 |
| sender             | 消息发送人的昵称                                               |
| content            | 消息内容                                                       |
| sender_remark      | 消息发送人的备注，没有则为 `None`                              |
| chat_type          | 聊天类型，`group` 为群聊，`friend` 为好友聊天，`official` 为公众号 |
| chat_name          | 当前聊天对象名，群名或好友名                                     |
| group_member_count | 群聊人数，如果是群消息则有该参数                               |

##### 4.2.5 解析卡片链接 `parse_url` 方法

**方法说明**：

`parse_url` 方法用于解析消息内的卡片链接，将其转换为可点击的 URL 格式。

**示例代码**：

```python
# 解析消息内的卡片链接
msgs = wx.GetAllMessage(parseurl=True)
# 示例输出:
# [
#     ...
#     ['Time', '13:34'],
#     ['Self', '[wxautox卡片链接解析]https://mp.weixin.qq.com/s/x8ilebSF5_KYd0PloyZm-Q']
# ]
```

---

## 文件管理对象

### 1. 文件窗口对象

文件管理对象用于管理和操作微信中的文件，如聊天文件、图片、视频等。

**支持属性**：

| 属性名       | 类型                | 说明                                     |
| ------------ | ------------------- | ---------------------------------------- |
| allfiles     | `ButtonControl`     | 全部文件按钮                             |
| recentfiles  | `ButtonControl`     | 最近使用按钮                             |
| whofiles     | `ButtonControl`     | 发送者按钮                               |
| chatfiles    | `ButtonControl`     | 聊天文件按钮                             |
| typefiles    | `ButtonControl`     | 类型按钮                                 |

**支持方法**：

| 方法名          | 说明                                     |
| --------------- | ---------------------------------------- |
| GetSessionName  | 获取聊天对象的名字                       |
| GetSessionList  | 获取当前聊天对象列表                     |
| ChatWithFile    | 打开指定聊天会话                         |
| DownloadFiles   | 下载指定聊天会话的文件                   |
| Close           | 关闭文件窗口                             |

#### 1.1 获取聊天对象名称

**方法说明**：

`GetSessionName` 方法用于获取聊天对象的名称。

**参数说明**：

| 参数        | 类型                        | 说明                       |
| ----------- | --------------------------- | -------------------------- |
| SessionItem | `uiautomation.ListItemControl` | 聊天对象控件             |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

session_name = wx.WeChatFiles().GetSessionName(session_item)
print(session_name)  # 输出聊天对象名
```

#### 1.2 获取聊天对象列表

**方法说明**：

`GetSessionList` 方法用于获取当前聊天列表中的所有聊天对象的名称。

**参数说明**：

| 参数  | 类型  | 默认值 | 说明                     |
| ----- | ----- | ------ | ------------------------ |
| reset | `bool`| `False`| 是否重置 `SessionItemList` |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

session_names = wx.WeChatFiles().GetSessionList()
print(session_names)  # 输出所有聊天对象名
```

#### 1.3 打开指定聊天会话 `ChatWithFile`

**方法说明**：

`ChatWithFile` 方法用于打开指定的聊天会话。

**参数说明**：

| 参数 | 类型 | 默认值 | 说明                       |
| ---- | ---- | ------ | -------------------------- |
| who  | `str`| /      | 要打开的聊天对象名         |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 打开指定聊天会话
who = '张三'
wx.WeChatFiles().ChatWithFile(who)
```

#### 1.4 下载文件 `DownloadFiles`

**方法说明**：

`DownloadFiles` 方法用于下载指定聊天会话中的文件。

**参数说明**：

| 参数      | 类型 | 默认值 | 说明                                     |
| --------- | ---- | ------ | ---------------------------------------- |
| who       | `str`| /      | 聊天对象名                               |
| amount    | `int`| /      | 下载的文件数量限制                       |
| deadline  | `str`| `None` | 截止日期限制                             |
| size      | `str`| `None` | 文件大小限制                             |

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 下载指定聊天会话中的文件
who = '工作群A'
amount = 10
deadline = '2024-12-01'
size = '10MB'

wx.WeChatFiles().DownloadFiles(who, amount, deadline, size)
```

### 2. 文件管理方法

文件管理对象提供了多种方法用于管理和操作微信中的文件，如获取聊天对象列表、下载文件等。

---

## 其他对象

### WeChatFiles 对象

`WeChatFiles` 对象用于管理微信中的文件，包括获取聊天对象的文件列表、下载文件等操作。

**示例代码**：

```python
from wxautox import WeChat

wx = WeChat()

# 获取所有聊天对象的文件列表
session_names = wx.WeChatFiles().GetSessionList()

# 下载特定聊天对象的文件
wx.WeChatFiles().DownloadFiles(who='张三', amount=5)
```

---

## 新增功能

### 1. 管理群聊 `ManageGroup`

- **新增方法**：`ManageGroup`
- **功能**：修改群聊的名称、备注、公告以及个人在群内的昵称，或选择退出群聊。

### 2. 管理好友 `ManageFriend`

- **新增方法**：`ManageFriend`
- **功能**：修改好友的备注名及增加标签。

### 3. 发送自定义表情包 `SendEmotion`

- **新增方法**：`SendEmotion`
- **功能**：发送自定义表情包。

### 4. 自动解析卡片链接

- **新增参数**：`parseurl` 在多个方法中新增，用于自动解析消息内卡片消息的 URL 链接。

### 5. 获取群成员 `GetGroupMembers`

- **新增方法**：`GetGroupMembers`
- **功能**：获取当前群聊的成员列表。

### 6. 发起群语音通话 `CallGroupMsg`

- **新增方法**：`CallGroupMsg`
- **功能**：发起群语音通话。

### 7. 文件管理对象 `WeChatFiles`

- **新增对象**：`WeChatFiles`
- **功能**：管理和操作微信中的文件，如聊天文件、图片、视频等。

---

## 更新日志

**版本**：Plus Version 3.9.11.17.21  
**更新日期**：2024-12-17

**更新内容**：

- 新增 `ManageGroup` 方法，支持修改群聊名称、备注、公告及个人昵称。
- 新增 `ManageFriend` 方法，支持修改好友备注和添加标签。
- 新增 `SendEmotion` 方法，支持发送自定义表情包。
- 在多个方法中新增 `parseurl` 参数，支持自动解析消息中的 URL 链接。
- 新增 `GetGroupMembers` 方法，支持获取当前群聊的成员列表。
- 新增 `CallGroupMsg` 方法，支持发起群语音通话。
- 新增 `WeChatFiles` 对象，支持文件管理和下载操作。

---

## 常见问题

### Q1：如何确保 wxautox 与微信版本兼容？

**答**：请确保您的微信客户端版本与 wxautox 支持的版本一致。目前 wxautox 支持微信版本 **3.9.11.17**。如果微信版本不匹配，可能会导致部分功能无法正常使用。

### Q2：发送文件时遇到问题怎么办？

**答**：发送文件时，请确保文件路径正确且文件存在。如果仍然遇到问题，请检查是否有足够的权限访问目标文件夹，或尝试减少一次发送的文件数量。

### Q3：自动保存文件功能存在 Bug，如何解决？

**答**：如果在使用自动保存文件功能时遇到 Bug，建议减少一次保存的文件数量，或手动保存必要的文件。同时，欢迎在微信群内反馈问题，我们将及时修复。

---

## 反馈与支持

如果您在使用 **wxautox** 时遇到任何问题，欢迎加入我们的微信群进行反馈和交流。我们会尽快响应并提供支持。

---

**免责声明**：本项目旨在提供微信自动化解决方案，使用过程中请遵守微信的相关使用条款和政策。开发者对使用本项目可能带来的任何后果自行承担责任。