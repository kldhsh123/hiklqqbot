# HiklQQBot 插件开发文档

本文档将指导您如何为 HiklQQBot 框架开发自定义插件。HiklQQBot 采用插件化设计，使您能够轻松扩展机器人的功能。

## 目录

- [插件基础概念](#插件基础概念)
- [创建第一个插件](#创建第一个插件)
- [插件生命周期](#插件生命周期)
- [注册插件](#注册插件)
- [命令规范化](#命令规范化)
- [消息发送](#消息发送)
- [Markdown 与按钮速查](#markdown-与按钮速查)
- [数据统计系统](#数据统计系统)
- [进阶功能](#进阶功能)
- [最佳实践](#最佳实践)
- [常见问题解答](#常见问题解答)
- [框架新特性（v2 重构）](#框架新特性v2-重构) — Reply 对象 / 多级分类 / 自定义菜单 / ACK 机制等

## 插件基础概念

在 HiklQQBot 中，插件是独立的 Python 模块，它们继承自 `BasePlugin` 基类，并实现特定的方法来处理命令。每个插件负责一组相关的功能，通过命令触发。

### 插件类型

HiklQQBot 插件分为两类：

1. **内置插件**：系统自带插件，命令前缀为"hiklqqbot_"，例如"hiklqqbot_admin"
2. **自定义插件**：用户开发的插件，无特定前缀要求

### 插件结构

每个插件必须：

1. 继承 `BasePlugin` 基类
2. 在初始化时提供命令名称、描述等参数
3. 实现 `handle` 方法来处理命令

## 创建第一个插件

让我们创建一个简单的插件，当用户发送 "echo" 命令时，机器人将回复相同的内容。

1. 在 `plugins` 目录下创建新文件 `echo_plugin.py`：

```python
from plugins.base_plugin import BasePlugin
import logging

class EchoPlugin(BasePlugin):
    """
    简单的回声插件，复述用户的输入
    """
    
    def __init__(self):
        super().__init__(
            command="echo", 
            description="复述你的消息",
            is_builtin=False,  # 不是内置插件
            hidden=False       # 不在命令列表中隐藏
        )
        self.logger = logging.getLogger("plugin.echo")
    
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """
        处理echo命令
        
        Args:
            params: 用户输入的文本
            user_id: 用户ID，用于权限控制
            group_openid: 群组ID，标识消息来源的群
            **kwargs: 其他额外参数，包括完整的事件数据
            
        Returns:
            str: 相同的文本
        """
        self.logger.info(f"收到echo命令，参数: {params}, 用户ID: {user_id}")
        
        if not params:
            return "请输入要复述的内容，例如: echo 你好世界"
        
        return params
```

> 注意：如果要创建内置插件，命令名称应该以"hiklqqbot_"开头，例如"hiklqqbot_echo"。

## 插件生命周期

### 初始化

插件在初始化时必须调用父类的 `__init__` 方法，并提供以下参数：

| 参数 | 必填 | 说明 |
|---|---|---|
| `command` | ✅ | 触发命令名，**支持单字符串或字符串列表**（多个命令共享同一 `handle()`） |
| `description` | ✅ | 命令描述，会出现在 `/help` 旧版纯文本菜单里 |
| `is_builtin` | ❌ | 是否内置插件，默认 `False` |
| `hidden` | ❌ | 是否在 `/help` 中隐藏，默认 `False` |
| `category` | ❌ | **分类路径**，用 `/` 分隔多级（如 `"工具/媒体"`），默认 `"其他"`；若插件在子目录中，自动以子目录路径为默认 |
| `display_name` | ❌ | **`/help` 菜单中显示的中文友好名**，未指定时回退到主命令 |

```python
def __init__(self):
    super().__init__(
        command="welcome",                # 命令名
        description="欢迎新成员加群",     # 命令描述
        category="工具/社交",             # 分类（支持多级）
        display_name="欢迎",              # 菜单显示名（中文简称）
        is_builtin=False,
        hidden=False,
    )
```

**关于 `category`**：

- 用 `/` 分隔多级路径，例如 `"工具/媒体/图片"` 会渲染为三级嵌套
- 特殊值 `"管理"`：plugin_manager 会用**全按钮模式**渲染该分类菜单（每命令一个按钮，塞不下分多条）
- 其他分类用 **md 网格 + 点击文字** 模式（默认 3 列）
- 未指定时默认 `"其他"`

**关于 `display_name`**：

- 出现在 `/help` 菜单的按钮文字和 markdown 点击文字 `show=` 属性中
- 推荐用 2-4 个中文字，例如 `"维护模式"` / `"运势"` / `"掷骰"`
- 未指定时 fallback 到 `command`（如 `hiklqqbot_admin`）

**多命令 / 别名**：

`command` 字段可以是字符串列表，多个命令共享同一个 `handle()` 实现（典型场景：长命令 + 短别名、中英文别名）。

```python
def __init__(self):
    super().__init__(
        command=["weather", "wt", "天气"],  # 主命令 + 别名, 第 1 个用于 /help 显示
        description="查询天气",
        display_name="天气",
    )

async def handle(self, params, user_id=None, group_openid=None, **kwargs):
    invoked = kwargs.get("invoked_command")  # 实际被触发的命令名（含 / 前缀）
    self.logger.info(f"用户用 {invoked} 触发了天气命令")
    return "..."
```

- 三个命令 `/weather` `/wt` `/天气` 都会触发本插件
- `/help` 菜单只显示主命令（第一个），别名作为隐藏入口
- `kwargs['invoked_command']` 给插件分辨用户用了哪个命令名调用

### 命令处理

当用户发送与插件命令匹配的消息时，插件的 `handle` 方法将被调用。此方法必须是异步的，并且接收以下参数：

- `params`: 命令后的参数文本
- `user_id`: 发送命令的用户ID，用于权限控制
- `group_openid`: 群组ID，标识消息来源的群（如果是群消息）
- `**kwargs`: 其他额外参数，最常用的是 `event_data` (完整事件数据)

```python
async def handle(self, params: str, user_id: str = None,
                  group_openid: str = None, **kwargs):
    # 处理命令逻辑
    return "命令处理结果"
```

**`handle()` 可以返回 4 种类型**：

| 返回 | 含义 |
|---|---|
| `str` | 作为纯文本回复（最简单，向后兼容） |
| `Reply` 对象 | 富回复（markdown / 按钮 / 富媒体），见后文 |
| `List[Reply]` | 多条消息按顺序发送 |
| `None` | 不发送（插件已自行用 `await self.send_xxx(...)` 处理） |

## 注册插件

创建插件后，您需要将其注册到插件管理器中.

### 方法1：自动加载

HiklQQBot 支持自动加载插件，只需确保您的插件文件放在 `plugins` 目录下，并且命名遵循插件命名规范。

主程序默认会自动加载插件：

```python
# 在 main.py 中
plugin_manager.load_plugins("plugins")
```

### 方法2：子目录分类组织

`load_plugins` **递归扫描所有 Python 子包**，方便按功能分组组织插件。子目录需要包含 `__init__.py` 才会被识别为 Python 包。

```
plugins/
├── __init__.py
├── hiklqqbot_ping_plugin.py        # 顶层插件 → 默认 category="其他"
├── games/                           # 子目录 = Python 包
│   ├── __init__.py                  # 必须有 (可以空)
│   ├── poker_plugin.py              # 默认 category="games"
│   └── chess_plugin.py              # 默认 category="games"
├── tools/
│   ├── __init__.py
│   └── media/
│       ├── __init__.py
│       └── imgtool_plugin.py        # 默认 category="tools/media"
└── 管理/
    ├── __init__.py
    └── moderate_plugin.py           # 默认 category="管理" (中文目录名也可)
```

**子目录名自动作为默认 category**：

- 顶层 `plugins/foo.py` → 默认 `category="其他"`
- `plugins/games/foo.py` → 默认 `category="games"`
- `plugins/tools/media/foo.py` → 默认 `category="tools/media"`

**插件代码里显式声明的 `category` 优先**，子目录推导只在插件未指定时生效：

```python
# plugins/games/poker.py
class PokerPlugin(BasePlugin):
    def __init__(self):
        super().__init__(
            command="poker", description="扑克游戏",
            # 不写 category → 自动等于 "games"
            # 写了 category="休闲/扑克" → 用 "休闲/扑克" 不被覆盖
        )
```

## 命令规范化

HiklQQBot 支持命令规范化功能，可以通过配置决定是否强制所有命令都以"/"开头。

### 配置说明

在 `.env` 文件中，您可以通过 `ENFORCE_COMMAND_PREFIX` 配置项来控制命令规范化行为：

```
# 命令规范化设置：设置为true时，所有命令必须以/开头；设置为false时，允许不带/前缀的命令
ENFORCE_COMMAND_PREFIX=true
```

- 当 `ENFORCE_COMMAND_PREFIX=true`（默认值）时：
  - 所有命令都会被强制添加"/"前缀
  - 用户可以使用 `/命令` 或 `命令` 两种形式调用，框架会自动规范化
  - 插件注册时不需要手动添加"/"前缀，框架会自动处理

- 当 `ENFORCE_COMMAND_PREFIX=false` 时：
  - 命令可以不带"/"前缀
  - 系统会同时保留带前缀和不带前缀的命令版本
  - 开发者需要注意避免命令冲突

### 最佳实践

无论 `ENFORCE_COMMAND_PREFIX` 如何设置，我们建议开发者在定义插件时始终使用不带"/"的命令名称，让框架来处理前缀的添加：

```python
def __init__(self):
    super().__init__(
        command="mycommand",  # 不需要手动添加/前缀
        description="我的插件描述"
    )
```

这样可以确保您的插件在不同的配置下都能正常工作。

## 消息发送

HiklQQBot 提供了三层消息发送 API，按推荐顺序使用：

| 层级 | 方式 | 适用场景 |
|---|---|---|
| **推荐** | 在 `handle()` 中返回 `Reply` 对象 / `str` / `List[Reply]` | 99% 的命令回复场景，框架自动处理被动消息绑定 |
| **便利** | 在插件内 `await self.send_xxx(...)` 主动发送 | 一个命令需要发多条 / 提前发 / 流式回复时 |
| **底层** | 直接 `MessageSender.xxx(...)` | 需要自定义 payload 或不走插件流程 |

### 返回 Reply（推荐）

```python
from reply import Reply
from ui_builder import make_command_button, make_button_row, make_keyboard

class MyPlugin(BasePlugin):
    async def handle(self, params, user_id=None, group_openid=None, **kwargs):
        # 纯文本
        return "Hello!"

        # 或 markdown
        return Reply(markdown="# 标题\n这是 **粗体**")

        # 或 markdown + 按钮
        return Reply(
            markdown=f"你好 {self.at_user(user_id)}",
            keyboard=make_keyboard([
                make_button_row([
                    make_command_button("1", "查看帮助", "/help"),
                ])
            ])
        )

        # 或多条消息
        return [
            Reply(markdown="第一条"),
            Reply(markdown="第二条"),
        ]
```

`Reply` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `text` | str | 纯文本内容 (`msg_type=0`)，与 markdown 互斥 |
| `markdown` | str | markdown 内容 (`msg_type=2`)，可与 keyboard 同时使用 |
| `keyboard` | dict | 完整 keyboard payload，仅在 markdown 下显示 |
| `media_file_info` | str | 富媒体 file_info（设置时 `msg_type=7`，覆盖前两者） |

框架发送 markdown 时会默认在开头补一个 `@执行命令的人`；如果你的 markdown 已经以 `<qqbot-at-user ... />` 开头，则不会重复追加。

### Markdown 与按钮速查

大多数插件交互界面都可以归结为一件事：返回 `Reply(markdown=..., keyboard=...)`。建议按下面的顺序写：

1. 先写 markdown 主体内容
2. 再用 `ui_builder` 组装按钮
3. 最后把两者一起放进 `Reply`

```python
from urllib.parse import quote

from reply import Reply
from ui_builder import make_command_button, make_button_row, make_keyboard

async def handle(self, params, user_id=None, group_openid=None, **kwargs):
    md = (
        f"# 欢迎 {self.at_user(user_id)}\n\n"
        "下面给你两个常用入口：\n\n"
        f'- 点击文字预填命令：<qqbot-cmd-input text="{quote("/help", safe="")}" show="打开帮助" reference="false" />\n'
        f'- 点击文字直接查看统计：<qqbot-cmd-input text="{quote("/stats", safe="")}" show="查看统计" reference="false" />'
    )

    keyboard = make_keyboard([
        make_button_row([
            make_command_button("help", "/help", "/help",
                                permission_user_ids=[user_id], style=1),
            make_command_button("stats", "/stats", "/stats",
                                permission_user_ids=[user_id]),
        ]),
    ])

    return Reply(markdown=md, keyboard=keyboard)
```

常用规则：

- `keyboard` 只有和 `markdown` 一起返回时才会显示
- 频道 `@` 消息不支持这套富回复时，框架会自动退化为纯文本
- 群聊里 `action_type=2` 只会把命令填进输入框；想“点一下就执行”，请改用 `action_type=1`
- 想限制只有触发者自己能点按钮，传 `permission_user_ids=[user_id]`
- 一个命令要发多条富回复时，直接返回 `List[Reply]`

常见 Markdown 片段：

| 需求 | 写法 |
|---|---|
| 一级标题 | `# 标题` |
| 粗体 | `**重点内容**` |
| 分隔线 | `***` |
| 引用提示 | `> 这是提示文字` |
| @用户 | `f"你好 {self.at_user(user_id)}"` |
| 点击填入命令 | `<qqbot-cmd-input text="..." show="..." reference="false" />` |
| 单聊直接发送命令 | `<qqbot-cmd-enter text="..." />` |
| 内嵌图片 | `![alt #200px #200px](https://q.qlogo.cn/...)` |

### BasePlugin 异步发送方法

继承 `BasePlugin` 即可直接 `self.xxx()` 调用，无需 import 任何东西：

| 方法 | 用途 |
|---|---|
| `await self.send_text(target_id, content, *, is_group, message_id, event_id)` | 发文本 |
| `await self.send_markdown(target_id, md, *, keyboard, is_group, message_id, event_id)` | 发 markdown（可带按钮） |
| `await self.send_image(target_id, *, url=, file_path=, file_data_b64=, content, is_group, message_id)` | **一站式发图**（自动上传 + 发送富媒体） |
| `await self.upload_image(target_id, is_group, *, url=, file_path=, file_data_b64=)` | 单独上传图片返回 `file_info` |
| `await self.reply_with(reply, event_data)` | 用 Reply 对象自动推断目标并发送 |

### 发送图片（富媒体消息）

QQ V2 富媒体上传支持两种数据源：**公网 URL** 或 **base64 二进制**。一站式方法自动处理上传 + 发送：

```python
async def handle(self, params, user_id=None, group_openid=None, **kwargs):
    target_id = group_openid or user_id
    is_group = bool(group_openid)
    message_id = kwargs.get("event_data", {}).get("id")

    # 用公网 URL 发图
    await self.send_image(
        target_id,
        url="https://example.com/img.jpg",
        content="带文字的图片",
        is_group=is_group,
        message_id=message_id,
    )

    # 用本地文件发图（自动 base64 编码上传）
    await self.send_image(
        target_id,
        file_path="data/avatar.jpg",
        is_group=is_group,
        message_id=message_id,
    )

    # 已有 base64 字符串
    await self.send_image(
        target_id,
        file_data_b64=my_b64_string,
        is_group=is_group,
        message_id=message_id,
    )

    return None  # 已自行发送，不再返回回复
```

如果想分两步处理（先上传，再决定发送时机或发到多个目标）：

```python
file_info = await self.upload_image(
    target_id, is_group=True, file_path="data/avatar.jpg"
)
# file_info 可在同一 scene (群/单聊) 内复用发送到多个目标
# 注意：群上传的 file_info 只能发群，单聊上传的只能发单聊
```

**file_info 有效期**：通常较短（几分钟到几小时），过期后需重新上传。

### Markdown 内嵌图片

markdown 可以用图片语法内嵌图片：

```python
md = f"# 测试\n\n![alt #200px #200px]({image_url})"
return Reply(markdown=md)
```

注意：
- markdown 内的图片 URL 必须是 QQ 域 / 受信任域（如 `q.qlogo.cn`、`gchat.qpic.cn`）
- 任意公网图床 URL 可能被 QQ 拦截，返回 `40034028`
- 图片尺寸用 `#宽px #高px` 后缀控制（可省略）

### 头像 URL

```python
avatar_url = self.get_avatar_url(user_id)
# 等价于 https://q.qlogo.cn/qqapp/{BOT_APPID}/{user_id}/640
# 这是 QQ 域，可直接在 markdown 内嵌
```

### @ 用户

```python
content = f"你好 {self.at_user(user_id)}"
# 等价于 f'你好 <qqbot-at-user id="{user_id}" />'
```

支持在 markdown / text 消息中使用。**纯文本消息不允许任意外链 URL**（会被 `40034028` 拦截），所以 @ 配合头像图片必须用 markdown 模式。

### Markdown 内可点击命令

QQ markdown 支持两个特殊标签让文字可点击：

| 标签 | 行为 | 群聊 | 单聊 |
|---|---|---|---|
| `<qqbot-cmd-input text="..." show="..." />` | 点击**填入输入框**，用户按发送 | ✅ | ✅ |
| `<qqbot-cmd-enter text="..." />` | 点击**直接发送** | ❌ | ✅ |

`text` 字段必须 URL 编码：

```python
from urllib.parse import quote
md = f'点击查询: <qqbot-cmd-input text="{quote("/stats users", safe="")}" show="用户列表" />'
return Reply(markdown=md)
```

### 按钮 keyboard

`ui_builder` 提供三个工厂函数：

```python
from ui_builder import (
    make_command_button, make_admin_button, make_group_admin_button,
    make_button_row, make_keyboard,
)

keyboard = make_keyboard([
    make_button_row([
        # 所有人可点
        make_command_button("1", "查看帮助", "/help"),
        # 仅指定 openid 可点
        make_command_button("2", "我的", "/me",
                            permission_user_ids=[user_id]),
    ]),
    make_button_row([
        # 仅机器人 admin 可点（自动取 auth_manager 列表）
        make_admin_button("3", "管理面板", "/help 管理"),
        # 仅 QQ 群/频道管理员可点（QQ 客户端判断）
        make_group_admin_button("4", "禁言", "/mute"),
    ]),
])
```

**`make_command_button` 参数**：

| 参数 | 说明 |
|---|---|
| `action_type` | `2`=发送型（点击发命令到聊天）；`1`=回调型（点击不发消息，触发 INTERACTION_CREATE） |
| `permission_user_ids` | 非空时仅这些 openid 可点（自动 permission.type=0 + specify_user_ids） |
| `style` | `0`=灰色，`1`=蓝色 |
| `visited_label` | 点击后显示的文字（默认与 label 相同） |

**`make_admin_button` 与 `make_group_admin_button` 的区别**：

| Helper | 谁可以点 | 实现原理 |
|---|---|---|
| `make_admin_button` | **机器人管理员**（即 `auth_manager.get_admins()` 列表里的 openid） | permission.type=0 + 把所有 admin 灌入 specify_user_ids |
| `make_group_admin_button` | **QQ 群主/管理员**（由 QQ 客户端判断，与机器人无关） | permission.type=1 |

⚠ **不要混淆**：QQ 平台的 `permission.type=1` 是群/频道的 QQ 管理者，**不是**机器人的 admin 列表。

### 群聊 vs 单聊场景的按钮差异

| 场景 | `action_type=2` 点击行为 | `action_type=1` (回调) |
|---|---|---|
| 单聊 | 直接发送命令 | ✅ 触发 INTERACTION_CREATE |
| 群聊 | **仅填入输入框**（QQ 限制） | ✅ 触发 INTERACTION_CREATE |

如果要在群聊里实现"点击直接执行"，请用 `action_type=1` 回调（框架已自动处理 ACK，避免客户端 loading）。

### 私聊富媒体直发 (srv_send_msg=True)

如果你想跳过"先上传再发送"两步，直接让 QQ 服务器在上传后立即发给用户（占用主动消息频次）：

```python
# 仅单聊，且会占用主动消息频次
MessageSender.upload_private_media(
    user_openid=user_id, file_type=1, url=image_url, srv_send_msg=True
)
```

### MessageSender 低层 API

如果框架便利方法不够用（如需自定义消息结构），可直接调 `MessageSender`：

```python
from message import MessageSender

# 文本消息
MessageSender.send_message(target_id, "text", "hello", is_group=True)

# 富媒体消息
MessageSender.send_message(target_id, 7, {
    "msg_type": 7,
    "content": "",
    "media": {"file_info": file_info},
}, is_group=True)

# 私聊富媒体一站式
MessageSender.send_private_image_message(user_openid, image_url, content="说明文字")
```

完整方法列表见 `message.py:MessageSender`。

### 消息频率限制

QQ 平台对**主动消息** 的发送权限已被收回

**被动消息**（绑定到一个 `msg_id` 或 `event_id`）不受限制。框架在以下场景自动绑定：

| 场景 | 自动绑定的字段 |
|---|---|
| `handle()` 返回的 Reply | `msg_id`（来自当前命令消息） |
| 按钮回调响应（INTERACTION_CREATE） | `event_id`（来自 dispatch 包顶层 id） |
| 群成员加入等事件响应 | `event_id` |

只要在合理路径上使用框架，几乎不会触发主动消息限制。

## 数据统计系统

HiklQQBot 框架内置了数据统计系统，用于记录和管理机器人的统计数据，包括群组、用户和消息等信息。插件开发者可以使用这些数据来增强功能。

### 统计系统的功能

统计系统主要包括以下功能：

1. 记录机器人加入/退出的群组信息
2. 记录用户信息
3. 记录消息和命令使用统计
4. 支持查询群组成员、用户信息等

### 在插件中使用统计系统

要在插件中使用统计系统，首先需要导入 `stats_manager`：

```python
from stats_manager import stats_manager
```

#### 获取用户信息

```python
class MyPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        # 获取用户信息
        user_info = stats_manager.get_user(user_id)
        if user_info:
            user_name = user_info.get("name", "未知用户")
            user_avatar = user_info.get("avatar")
            return f"你好，{user_name}！"
        else:
            return "未找到用户信息"
```

#### 获取群组信息和群组成员

```python
class GroupInfoPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        if not group_openid:
            return "此命令只能在群聊中使用"
        
        # 获取群组信息
        group_info = stats_manager.get_group(group_openid)
        if not group_info:
            return "未找到群组信息"
        
        # 获取群组成员ID列表
        member_ids = stats_manager.get_group_members(group_openid)
        
        result = f"群组名称: {group_info.get('name', '未知')}\n"
        result += f"成员数量: {len(member_ids)}\n\n"
        
        # 获取前5名成员信息
        result += "成员列表 (前5名):\n"
        for i, member_id in enumerate(member_ids[:5], 1):
            member_info = stats_manager.get_user(member_id)
            member_name = member_info.get("name", "未知") if member_info else "未知"
            result += f"{i}. {member_name} ({member_id})\n"
        
        if len(member_ids) > 5:
            result += f"...以及其他 {len(member_ids)-5} 名成员"
        
        return result
```

#### 记录命令使用情况

```python
class CustomPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        # 记录命令使用
        stats_manager.log_command(self.command, user_id, group_openid)
        
        # 处理命令...
        return "命令已处理"
```

### 统计数据结构

统计系统维护以下主要数据结构：

#### 群组数据

```python
{
    "group_id1": {
        "join_time": 1234567890,  # 时间戳
        "last_active": 1234567890,
        "members": ["user_id1", "user_id2", ...],
        "added_by": "user_id",
    },
    "group_id2": { ... }
}
```

#### 用户数据

```python
{
    "user_id1": {
        "name": "用户名称",
        "first_seen": 1234567890,  # 时间戳
        "last_active": 1234567890,
        "groups": ["group_id1", "group_id2", ...],
    },
    "user_id2": { ... }
}
```

#### 使用统计数据

```python
{
    "commands": {
        "command1": 10,  # 使用次数
        "command2": 5
    },
    "groups": {
        "group_id1": 15,  # 消息数
        "group_id2": 8
    },
    "users": {
        "user_id1": 20,  # 消息数
        "user_id2": 12
    },
    "total_messages": 100
}
```

### 统计系统API参考

#### 群组相关方法

- `stats_manager.add_group(group_openid, name=None, op_member_openid=None)`: 添加或更新群组信息
- `stats_manager.remove_group(group_openid)`: 移除群组
- `stats_manager.get_group(group_openid)`: 获取群组信息
- `stats_manager.get_all_groups()`: 获取所有群组信息
- `stats_manager.add_user_to_group(group_openid, user_openid)`: 将用户添加到群组
- `stats_manager.remove_user_from_group(group_openid, user_openid)`: 从群组移除用户
- `stats_manager.get_group_members(group_openid)`: 获取群组所有成员ID

#### 用户相关方法

- `stats_manager.add_user(user_openid, name=None, avatar=None)`: 添加或更新用户信息
- `stats_manager.get_user(user_openid)`: 获取用户信息
- `stats_manager.get_all_users()`: 获取所有用户信息

#### 统计相关方法

- `stats_manager.log_command(command, user_openid=None, group_openid=None)`: 记录命令使用
- `stats_manager.get_command_stats()`: 获取命令使用统计
- `stats_manager.get_most_active_groups(limit=10)`: 获取最活跃的群组
- `stats_manager.get_most_active_users(limit=10)`: 获取最活跃的用户

### 使用内置统计插件

框架提供了内置的统计管理插件，命令为 `hiklqqbot_stats`，仅供管理员使用，可以查看群组、用户和命令使用的统计数据。

可用的子命令包括：

- `hiklqqbot_stats groups [limit=10]`: 显示所有群组列表
- `hiklqqbot_stats users [limit=10]`: 显示所有用户列表
- `hiklqqbot_stats usage`: 显示命令使用统计
- `hiklqqbot_stats group <群ID>`: 显示指定群组的详细信息
- `hiklqqbot_stats user <用户ID>`: 显示指定用户的详细信息
- `hiklqqbot_stats help`: 显示帮助信息

### QQ平台事件支持

统计系统会自动处理以下QQ平台事件：

- `GROUP_ADD_ROBOT`: 机器人加入群聊
- `GROUP_DEL_ROBOT`: 机器人退出群聊
- `GROUP_MSG_REJECT`: 群聊拒绝机器人主动消息
- `GROUP_MSG_RECEIVE`: 群聊接受机器人主动消息
- `FRIEND_ADD`: 用户添加机器人
- `FRIEND_DEL`: 用户删除机器人
- `C2C_MSG_REJECT`: 拒绝机器人主动消息
- `C2C_MSG_RECEIVE`: 接受机器人主动消息

这些事件会自动更新统计数据，您不需要手动处理。

## 进阶功能

### 使用权限系统

框架内置了权限管理系统，您可以在插件中使用它来限制某些命令只能由管理员执行：

```python
from plugins.base_plugin import BasePlugin
from auth_manager import auth_manager

class AdminOnlyPlugin(BasePlugin):
    def __init__(self):
        super().__init__("admin_cmd", "仅管理员可用的命令", is_builtin=True)
    
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        # 检查用户是否是管理员
        if not auth_manager.is_admin(user_id):
            return "您没有权限执行此命令"
        
        # 管理员专属功能
        return "欢迎管理员使用此功能"
```

### 隐藏命令

有些插件可能不希望在帮助列表中显示，可以通过设置 `hidden=True` 来隐藏：

```python
def __init__(self):
    super().__init__(
        command="secret", 
        description="隐藏命令", 
        hidden=True
    )
```

### 存储数据

如果您的插件需要存储数据，可以在插件类中添加状态变量：

```python
class CounterPlugin(BasePlugin):
    def __init__(self):
        super().__init__("count", "计数器插件")
        self.counters = {}  # 用户计数器
    
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        user_id = user_id or "global"
        if user_id not in self.counters:
            self.counters[user_id] = 0
        self.counters[user_id] += 1
        return f"计数器: {self.counters[user_id]}"
```

注意：此处存储的数据仅在内存中保存，机器人重启后会丢失。对于持久化存储，建议使用数据库或文件。

### 使用外部 API

插件可以调用外部 API 来提供更多功能：

```python
import aiohttp
from plugins.base_plugin import BasePlugin

class WeatherPlugin(BasePlugin):
    def __init__(self):
        super().__init__("天气", "查询指定城市的天气信息")
        self.api_key = "您的API密钥"
    
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        if not params:
            return "请提供城市名称，例如: 天气 北京"
        
        city = params.strip()
        
        async with aiohttp.ClientSession() as session:
            url = f"https://api.example.com/weather?city={city}&key={self.api_key}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # 处理数据并返回结果
                    return f"{city}天气: {data['weather']}, 温度: {data['temperature']}°C"
                else:
                    return f"获取天气信息失败，错误码: {response.status}"
```

## 最佳实践

### 1. 使用异步编程

HiklQQBot 使用异步编程模型，确保您的插件充分利用异步特性，特别是 I/O 操作如网络请求和文件操作。

```python
# 推荐
async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

# 不推荐
def sync_request(url):
    import requests
    return requests.get(url).text  # 会阻塞事件循环
```

### 2. 添加适当的错误处理

确保您的插件能够优雅地处理错误，不要让异常导致整个机器人崩溃。

```python
async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
    try:
        # 可能出错的代码
        result = await self.do_something_risky(params)
        return result
    except Exception as e:
        self.logger.error(f"处理命令时出错: {e}")
        return f"处理命令时出错: {str(e)}"
```

### 3. 使用日志记录

使用日志记录插件的活动，便于调试和问题追踪。

```python
def __init__(self):
    super().__init__("mycommand", "我的插件")
    self.logger = logging.getLogger("plugin.mycommand")

async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
    self.logger.info(f"收到命令，参数: {params}")
    # 处理逻辑
    self.logger.debug("处理详情: ...")
    return result
```

### 4. 文档化您的插件

为您的插件添加详细的文档，包括参数说明和用法示例。

```python
class DocumentedPlugin(BasePlugin):
    """
    一个有完整文档的示例插件
    
    该插件演示了如何正确地文档化插件代码，包括类、方法和参数的说明。
    """
    
    def __init__(self):
        """初始化插件，设置命令名称和描述"""
        super().__init__(
            command="doc", 
            description="文档示例插件",
            is_builtin=False
        )
    
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """
        处理doc命令
        
        Args:
            params: 命令参数，格式为 <参数1> <参数2>
                   参数1: 第一个参数的说明
                   参数2: 第二个参数的说明
            user_id: 用户ID，用于权限控制
            group_openid: 群组ID，标识消息来源的群
            **kwargs: 其他额外参数，包括完整的事件数据
        
        Returns:
            str: 处理结果
        
        示例:
            doc hello world - 将返回对 "hello world" 的处理结果
        """
        # 处理逻辑
        return result
```

### 1. 遵循命名规范

- 内置插件的命令名称应以"hiklqqbot_"开头
- 自定义插件可以使用任意命令名称，但应避免与内置插件名称冲突

## 常见问题解答

### Q: 插件加载失败怎么办？

**A**: 检查以下几点：
1. 确保插件类继承自 `BasePlugin`
2. 确保实现了 `handle` 方法
3. 检查语法错误
4. 查看日志获取更多信息

### Q: 如何在插件之间共享数据？

**A**: 您可以使用全局变量、单例模式或外部存储（如数据库）来共享数据。此外，您还可以使用统计系统（`stats_manager`）来存储和共享一些常用数据。

### Q: 我的插件可以处理多个命令吗？

**A**: 每个插件实例只能处理一个命令。如果您需要处理多个相关命令，可以创建多个插件实例或使用子命令模式：

```python
async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
    parts = params.split(maxsplit=1)
    subcommand = parts[0] if parts else ""
    subparams = parts[1] if len(parts) > 1 else ""
    
    if subcommand == "add":
        return self.handle_add(subparams)
    elif subcommand == "remove":
        return self.handle_remove(subparams)
    else:
        return "未知的子命令，可用: add, remove"
```

### Q: 如何获取群组中的所有用户？

**A**: 您可以使用统计系统提供的 `get_group_members` 方法：

```python
async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
    if not group_openid:
        return "此命令只能在群聊中使用"
    
    member_ids = stats_manager.get_group_members(group_openid)
    return f"群组成员数: {len(member_ids)}"
```

### Q: 如何编写支持交互式对话的插件？

**A**: 当前框架主要支持基于命令的单次交互。如需支持多轮对话，您需要在插件中维护对话状态，并实现自己的状态管理逻辑。

---

## 认证机制说明

### Token类型和用途

HiklQQBot 使用两种不同的Token：

1. **APP_ACCESS_TOKEN (动态Token)**
   - 用途：所有API调用的认证
   - 获取方式：通过BOT_APPID和BOT_APPSECRET动态获取
   - 有效期：通常7200秒，框架自动刷新
   - 格式：`QQBot {access_token}`

2. **BOT_TOKEN (静态Token)**
   - 用途：仅用于Webhook模式的签名验证
   - 获取方式：从QQ机器人管理后台获取
   - 有效期：长期有效，除非手动重置

### 插件中的认证

插件开发者**无需**直接处理Token认证，框架已经自动处理：

```python
from message import MessageSender

class MyPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        # 直接调用，框架自动处理认证
        MessageSender.send_private_message(
            user_openid=user_id,
            message_content="消息内容"
        )
        return "发送成功"
```

框架的`auth_manager`会自动：
- 获取和刷新APP_ACCESS_TOKEN
- 在API请求中添加正确的认证头
- 处理Token过期和重试逻辑

## 错误处理和最佳实践

### 1. 异常处理

始终使用try-catch处理可能的异常：

```python
class MyPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        try:
            # 可能失败的操作
            result = MessageSender.send_private_message(
                user_openid=user_id,
                message_content="测试消息"
            )
            return "✅ 操作成功"
        except Exception as e:
            self.logger.error(f"操作失败: {str(e)}")
            return f"❌ 操作失败: {str(e)}"
```

### 2. 参数验证

验证用户输入的参数：

```python
async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
    # 参数验证
    if not params or not params.strip():
        return "❌ 请提供必要的参数"

    parts = params.strip().split()
    if len(parts) < 2:
        return "❌ 参数不足，需要至少2个参数"

    # 验证URL格式
    url = parts[1]
    if not url.startswith(('http://', 'https://')):
        return "❌ 请提供有效的URL"

    # 继续处理...
```

### 3. 权限控制

合理使用权限控制：

```python
from auth_manager import auth_manager

class MyPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        # 检查管理员权限
        if not auth_manager.is_admin(user_id):
            return "❌ 此命令仅限管理员使用"

        # 检查维护模式
        if not auth_manager.can_access(user_id):
            return "🔧 系统正在维护中，请稍后再试"

        # 继续处理...
```

### 4. 日志记录

使用适当的日志级别：

```python
import logging

class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__(command="my_plugin", description="我的插件")
        self.logger = logging.getLogger("plugin.my_plugin")

    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        self.logger.info(f"用户 {user_id} 执行命令: {params}")

        try:
            # 处理逻辑
            result = self.do_something(params)
            self.logger.info(f"命令执行成功: {result}")
            return result
        except Exception as e:
            self.logger.error(f"命令执行失败: {str(e)}", exc_info=True)
            return f"❌ 执行失败: {str(e)}"
```

### 5. 性能优化

- **避免阻塞操作**：使用异步方法处理耗时操作
- **缓存结果**：对于重复计算的结果进行缓存
- **限制频率**：避免过于频繁的API调用

```python
import asyncio
import time
from typing import Dict

class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__(command="my_plugin", description="我的插件")
        self.cache: Dict[str, tuple] = {}  # 缓存: {key: (result, timestamp)}
        self.cache_ttl = 300  # 缓存5分钟

    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        # 检查缓存
        cache_key = f"{user_id}:{params}"
        if cache_key in self.cache:
            result, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return f"📋 (缓存) {result}"

        # 异步处理
        try:
            result = await self.async_process(params)
            # 更新缓存
            self.cache[cache_key] = (result, time.time())
            return result
        except Exception as e:
            return f"❌ 处理失败: {str(e)}"

    async def async_process(self, params: str) -> str:
        # 模拟异步操作
        await asyncio.sleep(0.1)
        return f"处理结果: {params}"
```

## 总结

通过本指南，您应该能够：

1. 理解 HiklQQBot 的插件架构
2. 创建自己的插件
3. 处理各种类型的消息和事件（包括富媒体消息）
4. 理解认证机制和Token使用
5. 实现权限控制和错误处理
6. 遵循最佳实践和性能优化

如果您在开发过程中遇到问题，请查看现有插件的实现或提交 Issue。

---

如有其他问题，请提交 issue 。

---

# 框架进阶能力（v2 重构补充）

前面的"消息发送"章节涵盖了 Reply / 按钮 / cmd-input 等核心能力。本节是补充的进阶能力。

## 1. 权限快捷方法

`BasePlugin` 提供权限拦截 helper：

| 方法 | 用途 |
|---|---|
| `self.is_admin(user_id)` | 是否机器人管理员 |
| `self.require_admin(user_id, error_msg="...")` | 拦截非管理员，返回错误字符串或 `None` |
| `self.require_users(user_id, allowed_ids, error_msg)` | 限定用户白名单 |
| `self.require_groups(group_openid, allowed_ids, error_msg)` | 限定群白名单（私聊不受限） |
| `self.check_user_allowed(user_id, allowed_ids)` | 纯 bool 判断 |
| `self.check_group_allowed(group_openid, allowed_ids)` | 纯 bool 判断 |

```python
async def handle(self, params, user_id=None, group_openid=None, **kwargs):
    # 仅管理员可用
    err = self.require_admin(user_id)
    if err: return err

    # 仅限白名单群
    err = self.require_groups(group_openid, ["GROUP_ABC", "GROUP_XYZ"])
    if err: return err

    return "通过权限检查"
```

## 2. menu_config.json 自定义菜单

项目根目录 `menu_config.json` 完全自定义 `/help` 菜单的 markdown 模板和排版。
介绍文案单独放在 `menu_intro.json`，再通过模板变量插入到菜单里：

```json
{
  "root": {
    "header_md": "# 📖 帮助菜单\n\n{intro_block}",
    "footer_md": "\n> 点击上方文字进入对应分类",
    "show_buttons": true
  },
  "non_admin_category": {
    "header_md": "# 帮助 - {breadcrumb}\n\n{intro_block}",
    "before_commands_md": "## 命令 ({page}/{total_pages} 页, 共 {count} 个)\n",
    "footer_md": "\n> 发送 `/help` 返回主菜单",
    "columns": 3,
    "separator": "│",
    "page_size": 12,
    "row_divider": "***",
    "show_buttons": true,
    "show_home_button": true
  },
  "admin_category": {
    "header_md": "# 🔧 帮助 - 管理\n\n{intro_block}共 {count} 个命令，点击按钮执行：\n",
    "continuation_header_md": "# 🔧 帮助 - 管理 (续 {page})",
    "buttons_per_row": 3,
    "rows_per_msg_first": 4,
    "rows_per_msg_next": 5,
    "include_home_button": true
  }
}
```

`menu_intro.json` 示例：

```json
{
  "root": "欢迎使用本机器人, 请选择一个分类查看可用命令：",
  "categories": {
    "管理": "这里是管理员命令入口。按钮对所有人可点，但实际执行仍会校验管理员权限。",
    "工具/媒体": "这里放的是图片、音频、文件等相关命令。"
  }
}
```

补充说明：

- 如果项目根目录没有 `menu_intro.json`，框架会在第一次渲染 `/help` 时自动生成默认文件
- `categories` 的 key 支持**子菜单完整路径**，例如 `工具/媒体`、`工具/媒体/图片`
- 查找介绍文案时会优先匹配最具体的路径；如果当前子菜单没写，会自动回退到最近的父级路径
- 例如进入 `工具/媒体/图片` 时，会按 `工具/媒体/图片` → `工具/媒体` → `工具` 的顺序查找介绍

**所有 `*_md` 字段都是用户可写的 markdown 模板**，支持以下占位符：

| 占位符 | 含义 |
|---|---|
| `{breadcrumb}` | 当前分类路径（如 `工具 / 媒体`） |
| `{count}` | 命令总数 |
| `{page}` | 当前页码 |
| `{total_pages}` | 总页数 |
| `{intro}` | 当前菜单对应的介绍文案 |
| `{intro_block}` | 仅在有介绍文案时输出的段落块（已自动补好空行和 `***` 分隔线） |

未识别的占位符原样保留。

**特殊渲染规则**：

- 顶级 `root`：固定渲染分类列表（每个分类一行 + 点击文字），开头/结尾的 markdown 由 `header_md` / `footer_md` 自定义
- `non_admin_category`：默认 3 列网格 + 中间竖线 + 行分隔符，单命令行不加竖线
- `admin_category`：**完全用按钮渲染**（每命令一个按钮），塞不下自动分多条消息
- 帮助菜单按钮默认所有人都可点击，不再限制为“发送 `/help` 的那个人”

## 3. 统计与用户名 API

`stats_manager.add_user(openid, name=None)` 会记录用户名并维护历史：

```python
from stats_manager import stats_manager

stats_manager.get_username(openid)         # 当前用户名
stats_manager.get_username_history(openid) # [{name, first_seen, last_active}, ...]
stats_manager.get_groupname(openid)        # 当前群名（QQ V2 群事件无此字段，预留）
stats_manager.get_groupname_history(openid)
```

事件 `author.username` 会在 `handle_at_message` / `handle_direct_message` / `handle_group_at_message` 中**自动**喂给 stats_manager，插件无需关心。

## 4. INTERACTION_CREATE 自动 ACK

按钮回调（`action_type=1`）必须在收到 INTERACTION_CREATE 事件后调用 `PUT /interactions/{id}` 回应，否则 QQ 客户端会一直显示 loading 直到超时。

框架在 `event_handler.handle_interaction_create` 入口**已自动**调用 ACK（code=0），开发者无需关心。

如需自定义状态码（如表达"权限不足"，让客户端显示特定提示）：

```python
# code: 0=成功, 1=失败, 2=频繁, 3=重复, 4=无权限, 5=仅管理员
await event_handler._ack_interaction(interaction_id, code=4)
```

## 5. 完整示例：富回复 + 权限 + 按钮 + 头像

```python
from plugins.base_plugin import BasePlugin
from stats_manager import stats_manager
from reply import Reply
from ui_builder import (
    make_command_button, make_admin_button, make_group_admin_button,
    make_button_row, make_keyboard,
)


class WelcomePlugin(BasePlugin):
    ALLOWED_GROUPS = ["GROUP_ABC123"]

    def __init__(self):
        super().__init__(
            command="welcome",
            description="欢迎新成员",
            category="工具",
            display_name="欢迎",
        )

    async def handle(self, params, user_id=None, group_openid=None, **kwargs):
        # 限定群可用
        err = self.require_groups(group_openid, self.ALLOWED_GROUPS)
        if err: return err

        avatar = self.get_avatar_url(user_id)
        username = stats_manager.get_username(user_id) or "新朋友"

        md = (
            f"# 欢迎 {self.at_user(user_id)}\n\n"
            f"![avatar #150px #150px]({avatar})\n\n"
            f"**{username}** 你好！点击下方按钮开始探索"
        )
        keyboard = make_keyboard([
            make_button_row([
                make_command_button("help", "查看帮助", "/help",
                                     permission_user_ids=[user_id], style=1),
            ]),
            make_button_row([
                make_admin_button("admin_panel", "管理面板", "/help 管理"),
                make_group_admin_button("mute", "禁言", "/mute"),
            ]),
        ])
        return Reply(markdown=md, keyboard=keyboard)
```

---

如有其他问题，请提交 issue 。
