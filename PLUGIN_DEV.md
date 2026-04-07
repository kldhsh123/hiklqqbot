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
- [数据统计系统](#数据统计系统)
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

### 发送富媒体消息

HiklQQBot 支持发送图片、视频、语音等富媒体内容到私聊：

```python
from message import MessageSender

class MyPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        # 发送图片消息
        try:
            MessageSender.send_private_image_message(
                user_openid=user_id,
                image_url="https://example.com/image.jpg",  # 图片URL (PNG/JPG格式)
                content="这是一张图片",  # 可选的文本内容
                srv_send_msg=False  # false=两步发送模式，true=直接发送模式
            )
        except Exception as e:
            return f"发送图片失败: {str(e)}"

        # 发送视频消息
        try:
            MessageSender.send_private_video_message(
                user_openid=user_id,
                video_url="https://example.com/video.mp4",  # 视频URL (MP4格式)
                content="这是一个视频",
                srv_send_msg=False
            )
        except Exception as e:
            return f"发送视频失败: {str(e)}"

        # 发送语音消息
        try:
            MessageSender.send_private_audio_message(
                user_openid=user_id,
                audio_url="https://example.com/audio.silk",  # 语音URL (SILK格式)
                content="这是一段语音",
                srv_send_msg=False
            )
        except Exception as e:
            return f"发送语音失败: {str(e)}"

        return "富媒体消息发送成功"
```

**富媒体发送模式说明：**

- `srv_send_msg=False` (推荐): 两步发送模式，先上传媒体文件获取file_info，再发送消息。不占用主动消息频次。
- `srv_send_msg=True`: 直接发送模式，会直接发送到目标端，但会占用主动消息频次，超频会失败。

**支持的媒体格式：**
- 图片：PNG/JPG
- 视频：MP4
- 语音：SILK
- 文件：暂不开放

### 群聊富媒体消息

HiklQQBot 同样支持在群聊中发送富媒体消息：

```python
from message import MessageSender

class MyGroupMediaPlugin(BasePlugin):
    def __init__(self):
        super().__init__(command="group_media", description="群聊富媒体发送示例")

    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        if not group_openid:
            return "❌ 此命令只能在群聊中使用"

        # 解析参数：media_type url [content]
        parts = params.strip().split()
        if len(parts) < 2:
            return "❌ 用法: group_media <类型> <URL> [文本内容]\n类型: image/video/audio"

        media_type = parts[0].lower()
        media_url = parts[1]
        content = " ".join(parts[2:]) if len(parts) > 2 else ""

        try:
            if media_type == "image":
                # 群聊图片发送
                result = MessageSender.send_message(
                    channel_id=group_openid,
                    message_type=7,  # 富媒体类型
                    message_content={
                        "content": content,
                        "msg_type": 7,
                        "media": {"file_info": media_url}  # 简化示例，实际需要先上传
                    },
                    is_group=True
                )
            elif media_type == "video":
                # 群聊视频发送
                result = MessageSender.send_message(
                    channel_id=group_openid,
                    message_type=7,
                    message_content={
                        "content": content,
                        "msg_type": 7,
                        "media": {"file_info": media_url}
                    },
                    is_group=True
                )
            else:
                return f"❌ 不支持的媒体类型: {media_type}"

            return f"✅ {media_type}消息发送成功"

        except Exception as e:
            self.logger.error(f"群聊富媒体发送失败: {str(e)}")
            return f"❌ 发送失败: {str(e)}"
```

### 高级富媒体处理

#### 1. 文件上传管理

对于需要先上传文件的场景，可以使用底层的上传API：

```python
from message import MessageSender

class AdvancedMediaPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        # 第一步：上传媒体文件
        try:
            upload_result = MessageSender.upload_private_media(
                user_openid=user_id,
                file_type=1,  # 1=图片, 2=视频, 3=语音
                url="https://example.com/my-image.jpg",
                srv_send_msg=False  # 不直接发送，获取file_info
            )

            # 检查上传结果
            if "file_info" not in upload_result:
                return "❌ 文件上传失败"

            # 第二步：使用file_info发送消息
            media_info = {
                "file_info": upload_result["file_info"]
            }

            MessageSender.send_private_message(
                user_openid=user_id,
                message_content="这是上传的图片",
                message_type=7,  # 富媒体类型
                media=media_info
            )

            return "✅ 文件上传并发送成功"

        except Exception as e:
            return f"❌ 处理失败: {str(e)}"
```

#### 2. 批量富媒体发送

```python
import asyncio
from typing import List, Dict

class BatchMediaPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        # 批量发送多个媒体文件
        media_list = [
            {"type": 1, "url": "https://example.com/image1.jpg", "content": "图片1"},
            {"type": 2, "url": "https://example.com/video1.mp4", "content": "视频1"},
            {"type": 1, "url": "https://example.com/image2.jpg", "content": "图片2"},
        ]

        success_count = 0
        failed_count = 0

        for media in media_list:
            try:
                # 异步发送，避免阻塞
                await asyncio.sleep(0.5)  # 避免频率限制

                if media["type"] == 1:  # 图片
                    MessageSender.send_private_image_message(
                        user_openid=user_id,
                        image_url=media["url"],
                        content=media["content"]
                    )
                elif media["type"] == 2:  # 视频
                    MessageSender.send_private_video_message(
                        user_openid=user_id,
                        video_url=media["url"],
                        content=media["content"]
                    )

                success_count += 1

            except Exception as e:
                self.logger.error(f"发送媒体失败: {media['url']}, 错误: {str(e)}")
                failed_count += 1

        return f"✅ 批量发送完成: 成功{success_count}个, 失败{failed_count}个"
```

#### 3. 媒体文件验证

```python
import requests
from urllib.parse import urlparse

class MediaValidatorPlugin(BasePlugin):
    def validate_media_url(self, url: str, expected_type: str) -> tuple[bool, str]:
        """
        验证媒体URL的有效性

        Args:
            url: 媒体文件URL
            expected_type: 期望的文件类型 (image/video/audio)

        Returns:
            tuple: (是否有效, 错误信息)
        """
        try:
            # 检查URL格式
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, "无效的URL格式"

            # 检查文件扩展名
            valid_extensions = {
                "image": [".jpg", ".jpeg", ".png"],
                "video": [".mp4"],
                "audio": [".silk"]
            }

            if expected_type in valid_extensions:
                url_lower = url.lower()
                if not any(url_lower.endswith(ext) for ext in valid_extensions[expected_type]):
                    return False, f"不支持的{expected_type}格式"

            # 检查文件是否可访问（可选）
            try:
                response = requests.head(url, timeout=5)
                if response.status_code != 200:
                    return False, f"文件不可访问，状态码: {response.status_code}"
            except requests.RequestException:
                return False, "文件访问检查失败"

            return True, ""

        except Exception as e:
            return False, f"验证过程出错: {str(e)}"

    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        parts = params.strip().split()
        if len(parts) < 2:
            return "❌ 用法: validate_media <类型> <URL>"

        media_type = parts[0]
        media_url = parts[1]

        # 验证媒体文件
        is_valid, error_msg = self.validate_media_url(media_url, media_type)

        if not is_valid:
            return f"❌ 媒体文件验证失败: {error_msg}"

        # 验证通过，发送媒体
        try:
            if media_type == "image":
                MessageSender.send_private_image_message(
                    user_openid=user_id,
                    image_url=media_url,
                    content="验证通过的图片"
                )
            elif media_type == "video":
                MessageSender.send_private_video_message(
                    user_openid=user_id,
                    video_url=media_url,
                    content="验证通过的视频"
                )
            elif media_type == "audio":
                MessageSender.send_private_audio_message(
                    user_openid=user_id,
                    audio_url=media_url,
                    content="验证通过的语音"
                )

            return "✅ 媒体文件验证并发送成功"

        except Exception as e:
            return f"❌ 发送失败: {str(e)}"
```

### 富媒体发送最佳实践

#### 1. 错误处理

```python
class RobustMediaPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        try:
            # 尝试发送富媒体
            result = MessageSender.send_private_image_message(
                user_openid=user_id,
                image_url="https://example.com/image.jpg",
                content="测试图片"
            )

            return "✅ 发送成功"

        except requests.exceptions.Timeout:
            return "❌ 请求超时，请稍后重试"
        except requests.exceptions.ConnectionError:
            return "❌ 网络连接失败"
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                return "❌ 发送频率过高，请稍后重试"
            elif e.response.status_code == 403:
                return "❌ 权限不足或Token无效"
            else:
                return f"❌ HTTP错误: {e.response.status_code}"
        except Exception as e:
            self.logger.error(f"富媒体发送异常: {str(e)}", exc_info=True)
            return f"❌ 发送失败: {str(e)}"
```

#### 2. 性能优化

```python
import time
from typing import Dict

class OptimizedMediaPlugin(BasePlugin):
    def __init__(self):
        super().__init__(command="opt_media", description="优化的富媒体发送")
        self.upload_cache: Dict[str, Dict] = {}  # URL -> upload_result缓存
        self.cache_ttl = 3600  # 缓存1小时

    def get_cached_upload(self, url: str) -> Dict:
        """获取缓存的上传结果"""
        if url in self.upload_cache:
            cached_data, timestamp = self.upload_cache[url]
            if time.time() - timestamp < self.cache_ttl:
                return cached_data
            else:
                # 缓存过期，删除
                del self.upload_cache[url]
        return None

    def cache_upload_result(self, url: str, result: Dict):
        """缓存上传结果"""
        self.upload_cache[url] = (result, time.time())

    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        image_url = "https://example.com/image.jpg"

        # 检查缓存
        cached_result = self.get_cached_upload(image_url)

        if cached_result:
            # 使用缓存的file_info
            media_info = {"file_info": cached_result["file_info"]}
            MessageSender.send_private_message(
                user_openid=user_id,
                message_content="缓存的图片",
                message_type=7,
                media=media_info
            )
            return "✅ 使用缓存发送成功"
        else:
            # 上传新文件
            upload_result = MessageSender.upload_private_media(
                user_openid=user_id,
                file_type=1,
                url=image_url,
                srv_send_msg=False
            )

            # 缓存结果
            self.cache_upload_result(image_url, upload_result)

            # 发送消息
            media_info = {"file_info": upload_result["file_info"]}
            MessageSender.send_private_message(
                user_openid=user_id,
                message_content="新上传的图片",
                message_type=7,
                media=media_info
            )
            return "✅ 上传并发送成功"
```

### 富媒体发送调试指南

#### 常见问题和解决方案

**1. 文件上传失败**

```python
class DebugMediaPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        try:
            upload_result = MessageSender.upload_private_media(
                user_openid=user_id,
                file_type=1,
                url="https://example.com/image.jpg",
                srv_send_msg=False
            )

            # 调试信息
            self.logger.info(f"上传结果: {upload_result}")

            # 检查必要字段
            if "file_info" not in upload_result:
                return f"❌ 上传失败，缺少file_info字段: {upload_result}"

            if "ttl" in upload_result and upload_result["ttl"] == 0:
                self.logger.warning("文件TTL为0，可能长期有效")

            return f"✅ 上传成功: {upload_result['file_uuid']}"

        except Exception as e:
            # 详细错误日志
            self.logger.error(f"上传失败详情: {str(e)}", exc_info=True)
            return f"❌ 上传失败: {str(e)}"
```

**2. 消息发送失败**

```python
class MessageDebugPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        try:
            # 启用详细日志
            import logging
            logging.getLogger("message").setLevel(logging.DEBUG)

            result = MessageSender.send_private_image_message(
                user_openid=user_id,
                image_url="https://example.com/image.jpg",
                content="调试图片"
            )

            # 检查响应
            if isinstance(result, dict):
                if "id" in result:
                    return f"✅ 发送成功，消息ID: {result['id']}"
                else:
                    return f"⚠️ 发送可能成功，但响应异常: {result}"

            return f"✅ 发送完成: {result}"

        except Exception as e:
            # 分析错误类型
            error_msg = str(e)
            if "403" in error_msg:
                return "❌ 权限错误：检查Bot权限和Token有效性"
            elif "429" in error_msg:
                return "❌ 频率限制：请降低发送频率"
            elif "400" in error_msg:
                return "❌ 请求参数错误：检查URL和参数格式"
            elif "timeout" in error_msg.lower():
                return "❌ 请求超时：检查网络连接和文件大小"
            else:
                return f"❌ 未知错误: {error_msg}"
```

**3. 文件格式验证**

```python
import mimetypes
import requests

class FormatValidatorPlugin(BasePlugin):
    def check_file_format(self, url: str, expected_type: str) -> tuple[bool, str]:
        """检查文件格式是否符合要求"""
        try:
            # 检查URL扩展名
            url_lower = url.lower()

            format_map = {
                "image": [".jpg", ".jpeg", ".png"],
                "video": [".mp4"],
                "audio": [".silk"]
            }

            if expected_type not in format_map:
                return False, f"不支持的类型: {expected_type}"

            valid_exts = format_map[expected_type]
            if not any(url_lower.endswith(ext) for ext in valid_exts):
                return False, f"文件扩展名不符合要求，支持: {', '.join(valid_exts)}"

            # 检查MIME类型（可选）
            try:
                response = requests.head(url, timeout=5)
                content_type = response.headers.get('content-type', '').lower()

                if expected_type == "image" and not content_type.startswith('image/'):
                    return False, f"MIME类型不匹配: {content_type}"
                elif expected_type == "video" and not content_type.startswith('video/'):
                    return False, f"MIME类型不匹配: {content_type}"

            except requests.RequestException:
                # 网络检查失败，但不阻止发送
                pass

            return True, "格式验证通过"

        except Exception as e:
            return False, f"格式检查异常: {str(e)}"

    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        if not params:
            return "❌ 请提供文件URL"

        url = params.strip()

        # 检查图片格式
        is_valid, msg = self.check_file_format(url, "image")

        if not is_valid:
            return f"❌ {msg}"

        # 格式正确，尝试发送
        try:
            MessageSender.send_private_image_message(
                user_openid=user_id,
                image_url=url,
                content="格式验证通过的图片"
            )
            return f"✅ {msg}，发送成功"

        except Exception as e:
            return f"❌ 格式正确但发送失败: {str(e)}"
```

#### 调试技巧

**1. 启用详细日志**

```python
import logging

class VerboseMediaPlugin(BasePlugin):
    def __init__(self):
        super().__init__(command="verbose_media", description="详细日志的富媒体发送")

        # 设置详细日志级别
        logging.getLogger("message").setLevel(logging.DEBUG)
        logging.getLogger("auth").setLevel(logging.DEBUG)

        # 添加控制台输出
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)

    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        self.logger.info(f"开始处理富媒体发送请求: {params}")
        self.logger.info(f"用户ID: {user_id}")

        try:
            result = MessageSender.send_private_image_message(
                user_openid=user_id,
                image_url="https://example.com/debug.jpg",
                content="调试模式图片"
            )

            self.logger.info(f"发送结果: {result}")
            return "✅ 详细日志模式发送完成，请查看控制台输出"

        except Exception as e:
            self.logger.error(f"发送失败: {str(e)}", exc_info=True)
            return f"❌ 发送失败，详细信息请查看日志"
```

**2. 测试连通性**

```python
import requests
import time

class ConnectivityTestPlugin(BasePlugin):
    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        test_results = []

        # 测试API连通性
        try:
            start_time = time.time()
            response = requests.get("https://api.sgroup.qq.com", timeout=5)
            end_time = time.time()

            test_results.append(f"✅ API服务器连通性: {response.status_code} ({end_time-start_time:.2f}s)")
        except Exception as e:
            test_results.append(f"❌ API服务器连通性: {str(e)}")

        # 测试文件服务器连通性
        test_url = "https://example.com/test.jpg"
        try:
            start_time = time.time()
            response = requests.head(test_url, timeout=5)
            end_time = time.time()

            test_results.append(f"✅ 文件服务器连通性: {response.status_code} ({end_time-start_time:.2f}s)")
        except Exception as e:
            test_results.append(f"❌ 文件服务器连通性: {str(e)}")

        # 测试Token有效性
        try:
            from auth import auth_manager
            token = auth_manager.get_access_token()
            test_results.append(f"✅ Token获取: 成功 (长度: {len(token)})")
        except Exception as e:
            test_results.append(f"❌ Token获取: {str(e)}")

        return "🔍 连通性测试结果:\n" + "\n".join(test_results)
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
