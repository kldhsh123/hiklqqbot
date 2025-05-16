# HiklQQBot

HiklQQBot 是一个基于 Python 的 QQ 官方机器人框架，支持 WebSocket 和 Webhook 两种通信方式。本框架由 AI 辅助完成大部分编写，具有插件化设计，易于扩展和使用。  
qq交流群:330316577

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)]()

## 功能特点

- 支持多种通信模式：WebSocket和Webhook
- 插件系统：简单易用的插件开发框架
- 权限管理：设置管理员权限控制特定命令
- 命令处理：自动解析和处理群聊和私聊命令
- 消息发送：支持文本、图片等多种消息类型
- AI聊天：可集成OpenAI或其他兼容API的AI对话功能
- 私聊支持：支持通过私聊与机器人交互
- 统计系统：记录群组、用户和事件数据，提供详细统计信息
- 完整的QQ机器人事件支持：包括群聊、私聊、加好友、入群等事件

## 特性

- 🔌 **双模通信**: 支持 WebSocket 和 Webhook 两种通信方式，可通过配置文件轻松切换
- 🧩 **插件化设计**: 基于插件的模块化设计，便于扩展新功能
- 📦 **开箱即用**: 内置多个示例插件，快速开始使用
- 🔐 **权限系统**: 支持管理员权限控制和维护模式
- 📝 **详细日志**: 完善的日志记录系统，便于调试和问题排查
- ⚡ **异步处理**: 使用 Python 异步特性，提高性能和并发处理能力

## 插件市场
> 我们期待您天马行空的想法，您可以前往 [HiklQQBot官网](https://hiklbot.kldhsh.top/) 通过向AI描述您的想法来生成插件

HiklQQBot 提供了丰富的插件生态系统，让你可以轻松扩展机器人功能：

🔍 [浏览插件市场](PLUGINS.md) - 查看所有可用插件、GitHub仓库链接和安装指南

你也可以[贡献自己的插件](PLUGINS.md#如何提交插件)，分享给社区使用！


## 安装

### 系统要求

- Python 3.7 或更高版本
- 推荐使用虚拟环境

### 步骤

1. 克隆仓库到本地

```bash
git clone https://github.com/kldhsh123/hiklqqbot.git
cd hiklqqbot
```

2. 创建并激活虚拟环境 (可选但推荐)

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

3. 安装依赖包

```bash
pip install -r requirements.txt
```

4. 配置环境变量

```bash
# 复制示例配置文件
cp .env.example .env
# 编辑 .env 文件，填写您的机器人凭据和配置
```

## 配置

1. 打开 `.env` 文件，填写以下信息：

```
#v1.0.3
BOT_APPID=你的机器人AppID
BOT_APPSECRET=你的机器人AppSecret
BOT_TOKEN=你的机器人Token

# 通信模式: "webhook" 或 "websocket"
COMM_MODE=websocket

# Webhook相关设置（仅在COMM_MODE=webhook时使用）
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8080
WEBHOOK_PATH=/webhook/callback
# 如果使用内网穿透，请填写公网URL，否则留空
WEBHOOK_FULL_URL=https://example.com/webhook/callback

# 命令规范化设置：设置为true时，所有命令必须以/开头；设置为false时，允许不带/前缀的命令
ENFORCE_COMMAND_PREFIX=true
```

2. 如果使用 Webhook 模式，需要确保安装了相关依赖：

```bash
pip install pynacl
# 或者
pip install ed25519
```

## 运行

启动机器人：

```bash
python main.py
```

机器人启动后会自动加载所有插件，并根据配置文件选择通信模式。

## 通信模式

### WebSocket 模式

WebSocket 模式是最简单的接入方式，机器人会主动连接到 QQ 机器人网关，建立长连接接收事件。

**优点**:
- 设置简单，无需公网 IP
- 无需额外配置即可直接使用

**缺点**:
- 需要维护心跳和重连机制
- QQ 官方计划在 2024 年底前逐步下线此模式（直到2025/4/17任然可以使用）

### Webhook 模式

Webhook 模式需要提供一个可以被 QQ 机器人平台访问的 URL，用于接收事件推送。

**优点**:
- 不需要维护连接状态
- 官方推荐的长期稳定接入方式

**缺点**:
- 需要公网 IP 或域名，或者使用内网穿透工具
- 配置稍复杂

#### Webhook 配置步骤

1. 在 `.env` 文件中设置 `COMM_MODE=webhook`
2. 配置 webhook 相关参数
3. 如果没有公网 IP，使用 ngrok 等工具进行内网穿透：
   ```bash
   ngrok http 8080
   ```
4. 将获得的公网 URL 填入 QQ 机器人管理后台的回调地址中

## 权限系统

HiklQQBot 内置了简单而有效的权限管理系统：

### 管理员权限

- 首次使用 `/hiklqqbot_admin` 命令的用户将自动成为第一个管理员
- 管理员可以添加和删除其他管理员
- 管理员信息保存在 `admins.json` 文件中

### 维护模式

- 管理员可以通过 `/hiklqqbot_maintenance on` 命令开启维护模式
- 维护模式下，只有管理员可以使用机器人，其他用户的命令将被拒绝
- 适用于机器人维护、更新或临时禁用的场景

### 获取用户ID

- 用户可以通过 `/hiklqqbot_userid` 命令获取自己的用户ID
- 管理员可以使用此ID添加其他用户为管理员

## 插件开发

HiklQQBot 使用插件化设计，便于扩展新功能。要开发自己的插件：

1. 在 `plugins` 目录创建新的 Python 文件
2. 继承 `BasePlugin` 类并实现 `handle` 方法
3. 插件会自动加载，无需额外注册

插件开发资源：
- [完整插件市场和开发指南](PLUGINS.md)
- [插件开发详细文档](PLUGIN_DEV.md)

简单插件示例:

```python
from plugins.base_plugin import BasePlugin

class MyCustomPlugin(BasePlugin):
    def __init__(self):
        super().__init__(
            command="/mycmd",  # 命令前缀
            description="我的自定义命令",  # 描述
            is_builtin=False,  # 是否内置
            hidden=False  # 是否在帮助中隐藏
        )
        
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        # 实现您的命令逻辑
        if not params:
            return "请提供参数"
        return f"收到参数: {params}"
```

## 常见问题

1. **安装依赖失败**
   - 尝试使用 `pip install --upgrade pip` 更新 pip
   - 对于编译依赖问题，Windows 用户可能需要安装 Visual C++ Build Tools

2. **无法收到事件**
   - 检查网络连接
   - 确认 AppID、AppSecret 和 Token 是否正确
   - Webhook 模式下，确认回调地址是否可以从外网访问

3. **机器人不响应命令**
   - 检查日志中是否收到了事件
   - 确认命令格式是否正确
   - 确认插件是否已正确注册

## 许可证

GPL-3.0 license

## 鸣谢

- 本项目的核心框架由 AI 辅助完成
- [QQ机器人官方文档](https://bot.q.qq.com/wiki/)
- 所有贡献者和提出建议的人

## 联系方式

如有问题或建议，欢迎提交 issue 或联系我们。 

## 支持的事件列表

HiklQQBot支持以下QQ官方事件：

- `GROUP_AT_MESSAGE_CREATE`: 群聊@机器人消息
- `DIRECT_MESSAGE_CREATE`: 私聊消息
- `C2C_MESSAGE_CREATE`: 单聊消息 
- `GROUP_ADD_ROBOT`: 机器人被添加到群聊
- `GROUP_DEL_ROBOT`: 机器人被移出群聊
- `GROUP_MSG_REJECT`: 群聊拒绝机器人主动消息
- `GROUP_MSG_RECEIVE`: 群聊接受机器人主动消息
- `FRIEND_ADD`: 用户添加机器人好友
- `FRIEND_DEL`: 用户删除机器人好友
- `C2C_MSG_REJECT`: 用户拒绝机器人主动消息
- `C2C_MSG_RECEIVE`: 用户接受机器人主动消息
- `READY`: 机器人就绪事件
- `RESUMED`: 连接恢复事件

## 统计系统

HiklQQBot包含一个强大的统计系统，用于记录和分析机器人的使用情况：

### 统计的数据

- **群组统计**：记录机器人加入的所有群组信息，包括加入时间、活跃状态等
- **用户统计**：记录所有与机器人互动的用户信息
- **群组-用户关系**：记录每个群组中的用户数据
- **事件统计**：记录所有事件类型和数量

### 统计命令

使用 `/stats` 命令可以查看统计信息：

- `/stats summary` - 显示统计摘要（默认）
- `/stats groups` - 显示群组统计
- `/stats users` - 显示用户统计
- `/stats events` - 显示事件统计

管理员可使用更多高级命令：

- `/stats group <群ID>` - 显示特定群组详情
- `/stats user <用户ID>` - 显示特定用户详情
- `/stats events <事件类型>` - 显示特定事件类型的详情

### 插件API

插件可以通过统计管理器访问统计数据：

```python
from stats_manager import stats_manager

# 获取群组信息
group_info = stats_manager.get_group(group_id)

# 获取用户信息
user_info = stats_manager.get_user(user_id)

# 获取群组中的所有用户
users_in_group = stats_manager.get_group_users(group_id)

# 获取统计摘要
summary = stats_manager.get_stats_summary()
``` 
