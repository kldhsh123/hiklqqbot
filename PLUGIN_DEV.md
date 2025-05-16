# HiklQQBot 插件开发文档
> 我们期待您天马行空的想法，您可以前往 [HiklQQBot官网](https://hiklbot.kldhsh.top/) 通过向AI描述您的想法来生成插件

本文档将指导您如何为 HiklQQBot 框架开发自定义插件。HiklQQBot 采用插件化设计，使您能够轻松扩展机器人的功能。

## 目录

- [插件基础概念](#插件基础概念)
- [创建第一个插件](#创建第一个插件)
- [插件生命周期](#插件生命周期)
- [注册插件](#注册插件)
- [命令规范化](#命令规范化)
- [消息发送](#消息发送)
- [进阶功能](#进阶功能)
- [最佳实践](#最佳实践)
- [常见问题解答](#常见问题解答)

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

- `command`: 触发插件的命令名称（内置插件应以"hiklqqbot_"为前缀）
- `description`: 插件的描述信息
- `is_builtin`: (可选) 是否为内置插件，影响在帮助信息中的分类，默认为 False
- `hidden`: (可选) 是否在命令列表中隐藏此插件，默认为 False

```python
def __init__(self):
    super().__init__(
        command="mycommand",  # 自定义插件命令
        # 或 command="hiklqqbot_mycommand",  # 内置插件命令
        description="这是我的插件描述",
        is_builtin=False,  # True表示内置插件
        hidden=False       # True表示在命令列表中隐藏
    )
    # 自定义初始化逻辑
```

### 命令处理

当用户发送与插件命令匹配的消息时，插件的 `handle` 方法将被调用。此方法必须是异步的，并且接收以下参数：

- `params`: 命令后的参数文本
- `user_id`: 发送命令的用户ID，用于权限控制
- `group_openid`: 群组ID，标识消息来源的群（如果是群消息）
- `**kwargs`: 其他额外参数，包括完整的事件数据

```python
async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
    # 处理命令逻辑
    return "命令处理结果"
```

## 注册插件

创建插件后，您需要将其注册到插件管理器中.

### 方法1：自动加载

HiklQQBot 支持自动加载插件，只需确保您的插件文件放在 `plugins` 目录下，并且命名遵循插件命名规范。

主程序默认会自动加载插件：

```python
# 在 main.py 中
plugin_manager.load_plugins("plugins")
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

HiklQQBot 支持发送多种类型的消息，包括群聊消息、频道消息和私聊消息。

### 发送私聊消息

您可以使用 `MessageSender` 类在插件中发送私聊消息：

```python
from message import MessageSender

class MyPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        # 发送普通文本私聊消息
        MessageSender.send_private_message(
            user_openid=user_id,  # 接收消息的用户openid
            message_content="这是一条私聊消息"
        )
        
        # 发送带按钮的私聊消息
        keyboard = {
            "buttons": [
                {"id": "1", "text": "选项1"},
                {"id": "2", "text": "选项2"}
            ]
        }
        MessageSender.send_private_message(
            user_openid=user_id,
            message_content="请选择一个选项",
            keyboard=keyboard
        )
        
        return "消息已发送"
```

### 回复私聊消息

您可以回复用户发送的私聊消息：

```python
from message import MessageSender

class MyPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        # 获取原消息ID（通常从事件数据中获取）
        original_msg_id = kwargs.get("message", {}).get("id")
        
        if original_msg_id:
            # 回复用户的消息
            MessageSender.reply_private_message(
                user_openid=user_id,
                message_id=original_msg_id,
                message_content="这是对您消息的回复"
            )
            return "已回复"
        else:
            return "找不到原始消息ID"
```

### 消息限制说明

根据QQ机器人平台规则，消息发送存在以下限制：

- **私聊消息**：
  - 主动消息每月每位用户最多4条
  - 被动消息（回复类）有效期为60分钟，每条消息最多回复5次

- **群聊消息**：
  - 主动消息每月每个群最多4条
  - 被动消息（回复类）有效期为5分钟，每条消息最多回复5次

为了避免触发限制，建议优先使用被动消息（回复用户的消息），并合理管理消息频率。

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

**A**: 您可以使用全局变量、单例模式或外部存储（如数据库）来共享数据。

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

### Q: 如何编写支持交互式对话的插件？

**A**: 当前框架主要支持基于命令的单次交互。如需支持多轮对话，您需要在插件中维护对话状态，并实现自己的状态管理逻辑。

---

如有其他问题，请提交 issue 。 
