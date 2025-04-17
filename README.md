# HiklQQBot

HiklQQBot 是一个基于 Python 的 QQ 官方机器人框架，支持 WebSocket 和 Webhook 两种通信方式。本框架由 AI 辅助完成大部分编写，具有插件化设计，易于扩展和使用。

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)]()

## 特性

- 🔌 **双模通信**: 支持 WebSocket 和 Webhook 两种通信方式，可通过配置文件轻松切换
- 🧩 **插件化设计**: 基于插件的模块化设计，便于扩展新功能
- 📦 **开箱即用**: 内置多个示例插件，快速开始使用
- 🔐 **权限系统**: 支持管理员权限控制和维护模式
- 📝 **详细日志**: 完善的日志记录系统，便于调试和问题排查
- ⚡ **异步处理**: 使用 Python 异步特性，提高性能和并发处理能力

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
# 机器人凭据 (从QQ机器人开放平台获取)
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

## 内置功能

HiklQQBot 内置了以下插件：

### 系统插件

- `PingPlugin`: 检测机器人在线状态，发送 "hiklqqbot_ping" 会收到 "pong" 和时间戳
- `UserIdPlugin`: 获取用户ID，用于管理员权限设置，命令为 "hiklqqbot_userid"
- `AdminMgmtPlugin`: 管理员管理，添加/移除管理员，命令为 "hiklqqbot_admin"
- `MaintenancePlugin`: 维护模式控制，仅管理员可用，命令为 "hiklqqbot_maintenance"

### 自定义插件

- `FortunePlugin`: 随机生成运势值，发送 "运势" 获取今日运势
- `SimpleResponsePlugin`: 简单的固定文本响应，发送 "1" 会收到 "2" 的响应

## 命令使用指南

### 基础命令

| 命令 | 格式 | 描述 |
| --- | --- | --- |
| 运势 | 运势 [主题] | 获取今日运势值(1-100)和相应描述，可选择特定主题 |
| 1 | /1 | 返回固定回复"2" |
| hiklqqbot_ping | /hiklqqbot_ping | 测试机器人是否在线，返回pong和当前时间 |

### 系统命令

| 命令 | 格式 | 描述 |
| --- | --- | --- |
| hiklqqbot_userid | /hiklqqbot_userid | 获取您的用户ID，用于权限设置 |
| hiklqqbot_admin | /hiklqqbot_admin list | 列出所有管理员 |
| hiklqqbot_admin | /hiklqqbot_admin add <用户ID> | 添加管理员（仅现有管理员可用） |
| hiklqqbot_admin | /hiklqqbot_admin remove <用户ID> | 移除管理员（仅现有管理员可用） |
| hiklqqbot_maintenance | /hiklqqbot_maintenance | 查看维护模式状态（仅管理员可用） |
| hiklqqbot_maintenance | /hiklqqbot_maintenance on/off | 开启/关闭维护模式（仅管理员可用） |

### 消息格式

- 群聊中使用命令：@机器人 命令 [参数]
- 私聊中使用命令：直接发送"命令 [参数]"

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

如需了解如何开发自己的插件，请参考 [插件开发文档](PLUGIN_DEV.md)。

HiklQQBot 使用插件化设计，便于扩展新功能：

1. 在 `plugins` 目录创建新的 Python 文件
2. 继承 `BasePlugin` 类并实现 `handle` 方法
3. 插件会自动加载，无需额外注册

插件示例:

```python
from plugins.base_plugin import BasePlugin

class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__(
            command="mycmd",
            description="我的自定义命令",
            is_builtin=False,  # 是否为内置插件
            hidden=False  # 是否在命令列表中隐藏
        )
        
    async def handle(self, params: str, user_id: str = None) -> str:
        if not params:
            return "请提供参数"
        return f"收到参数: {params}，来自用户: {user_id}"
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
