# HiklQQBot 插件市场
> 我们期待您天马行空的想法，您可以前往 [HiklQQBot官网](https://hiklbot.kldhsh.top/) 通过向AI描述您的想法来生成插件

HiklQQBot 采用插件化设计，这里收集了可用的插件资源，便于快速扩展机器人功能。你可以直接使用这些插件，或者参考它们开发自己的功能。


## 如何提交插件

如果你开发了有用的插件并愿意分享，欢迎提交 Pull Request 添加到此列表中。提交格式如下：

```markdown
### 插件名称
- **作者**: 你的名字/GitHub用户名
- **仓库**: GitHub链接
- **描述**: 简短介绍插件的功能
- **命令**: 插件主要命令
- **安装**: 安装方法简述
```

## 社区插件

以下是社区贡献的插件，通过安装这些插件可以扩展机器人功能。

### 幸福工厂服务器工具箱
- **作者**: [Sakura](https://github.com/7ooki)
- **仓库**: [Satisfactory-QQbot](https://github.com/7ooki/Satisfactory-QQbot)
- **描述**: 幸福工厂服务器工具箱
- **命令**: /Factory
- **安装**: 放置于plugins文件夹内即可


### 秘密实验室服务器查询插件
- **作者**: [SL-114514NM](https://github.com/SL-114514NM)
- **仓库**: [HiklQQBot-CXServerPlugin](https://github.com/SL-114514NM/HiklQQBot-CXServerPlugin)
- **描述**: 查询绑定的SCP SL服务器信息，使用官方API
- **命令**: /绑定服务器,/CX
- **安装**: 放置于plugins文件夹内即可

## 内置插件

这些插件默认包含在hiklqqbot中，无需额外安装。

### 用户ID查询
- **作者**: [kldhsh123](https://github.com/kldhsh123)
- **仓库**: [HiklQQBot](https://github.com/kldhsh123/hiklqqbot)
- **描述**: 查询用户ID和群组ID (base64加密)
- **命令**: `/hiklqqbot_userid`
- **安装**: 内置插件，无需安装

### 管理员管理
- **作者**: [kldhsh123](https://github.com/kldhsh123)
- **仓库**: [HiklQQBot](https://github.com/kldhsh123/hiklqqbot)
- **描述**: 管理员用户的添加、删除和查看
- **命令**: `/hiklqqbot_admin`
- **安装**: 内置插件，无需安装

### 维护模式控制
- **作者**: [kldhsh123](https://github.com/kldhsh123)
- **仓库**: [HiklQQBot](https://github.com/kldhsh123/hiklqqbot)
- **描述**: 控制机器人的维护模式状态
- **命令**: `/hiklqqbot_maintenance`
- **安装**: 内置插件，无需安装

### 插件热重载
- **作者**: [kldhsh123](https://github.com/kldhsh123)
- **仓库**: [HiklQQBot](https://github.com/kldhsh123/hiklqqbot)
- **描述**: 无需重启机器人即可重新加载所有插件
- **命令**: `/hiklqqbot_reload`
- **安装**: 内置插件，无需安装

### 在线测试
- **作者**: [kldhsh123](https://github.com/kldhsh123)
- **仓库**: [HiklQQBot](https://github.com/kldhsh123/hiklqqbot)
- **描述**: 测试机器人是否在线及响应延迟
- **命令**: `/hiklqqbot_ping`
- **安装**: 内置插件，无需安装

## 功能插件

这些功能插件提供各种实用功能，已内置在QQGFBot中。


### 运势生成
- **作者**: [kldhsh123](https://github.com/kldhsh123)
- **仓库**: [HiklQQBot](https://github.com/kldhsh123/hiklqqbot)
- **描述**: 生成今日运势值和描述
- **命令**: `/运势`
- **安装**: 内置插件，无需安装
- **使用方法**:
  ```
  /运势          # 获取默认运势
  /运势 <主题>   # 获取特定主题的运势
  ```

### 简单响应
- **作者**: [kldhsh123](https://github.com/kldhsh123)
- **仓库**: [HiklQQBot](https://github.com/kldhsh123/hiklqqbot)
- **描述**: 简单的固定文本响应，示例插件
- **命令**: `/1`
- **安装**: 内置插件，无需安装

## 开发自己的插件

要开发自己的插件，只需要继承 `BasePlugin` 类并实现 `handle` 方法。详细步骤如下：

1. 在 `plugins` 目录创建新的 Python 文件
2. 继承 `BasePlugin` 类并实现必要的方法
3. 机器人启动时会自动加载您的插件

插件示例:

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

更多详细信息，请参考项目文档中的插件开发指南。

## 插件开发资源

以下资源可以帮助你开发优质的HiklQQBot插件：

- [QQ机器人官方文档](https://bot.q.qq.com/wiki/) - QQ官方机器人平台文档
- [Aiohttp文档](https://docs.aiohttp.org/) - 用于异步HTTP请求
- [Python异步编程](https://docs.python.org/zh-cn/3/library/asyncio.html) - Python官方异步编程指南

---

如有问题或建议，欢迎在GitHub Issues中提出或加入QQ交流群: 330316577 
