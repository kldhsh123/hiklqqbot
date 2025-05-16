from abc import ABC, abstractmethod
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("base_plugin")

class BasePlugin(ABC):
    """
    插件基类，所有插件都应该继承这个类
    """
    
    def __init__(self, command: str, description: str, is_builtin: bool = False, hidden: bool = False, admin_only: bool = False):
        """
        初始化插件
        
        Args:
            command: 插件的命令名称
            description: 插件的描述信息
            is_builtin: 是否为内置插件
            hidden: 是否在命令列表中隐藏该插件
            admin_only: 是否仅管理员可用
        """
        self.command = command
        self.description = description
        self.is_builtin = is_builtin
        self.hidden = hidden
        self.admin_only = admin_only
        self.logger = logging.getLogger(f"plugin.{command}")
    
    @abstractmethod
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """
        处理命令的核心方法，需要子类实现
        
        Args:
            params: 命令参数
            user_id: 用户ID，用于权限控制
            group_openid: 群组ID
            **kwargs: 其他额外参数
            
        Returns:
            处理结果
        """
        pass
    
    def help(self) -> str:
        """
        获取插件的帮助信息
        
        Returns:
            帮助信息文本
        """
        admin_hint = " (仅管理员)" if self.admin_only else ""
        return f"{self.command} - {self.description}{admin_hint}" 