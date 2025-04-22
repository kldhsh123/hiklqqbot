"""
QQ机器人插件包
"""

__version__ = "1.0.0"

"""
插件系统，允许轻松添加新功能
"""

# plugins 包初始化

# 内置核心插件列表
BUILTIN_PLUGINS = [
    "ping_plugin",  # ping测试插件
    "admin_plugin",  # 管理员权限插件
    "reload_plugin",  # 热重载插件
]

# 其他插件列表
EXTENSION_PLUGINS = [
    "fortune_plugin",  # 运势插件
]

# 导出所有插件
__all__ = BUILTIN_PLUGINS + EXTENSION_PLUGINS 