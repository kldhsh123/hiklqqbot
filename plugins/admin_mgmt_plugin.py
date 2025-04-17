from plugins.base_plugin import BasePlugin
import logging
import json
import os
from auth_manager import auth_manager

class AdminMgmtPlugin(BasePlugin):
    """
    管理员管理插件，用于添加/删除/查看管理员
    """
    
    def __init__(self):
        super().__init__(
            command="/admin", 
            description="管理员管理：添加/删除/查看管理员", 
            is_builtin=False,
            hidden=False
        )
        self.logger = logging.getLogger("plugin.admin_mgmt")
        
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """
        处理管理员相关命令
        
        Args:
            params: 命令参数
            user_id: 用户ID，用于权限控制
            group_openid: 群组ID（不使用）
            **kwargs: 其他额外参数
            
        Returns:
            str: 处理结果
        """
        self.logger.info(f"收到管理员管理命令，参数: {params}, 用户: {user_id}")
        
        # 检查权限，仅允许当前管理员执行
        if not auth_manager.is_admin(user_id):
            return "您没有权限执行管理员命令"
        
        # 解析参数
        parts = params.strip().split()
        
        # 无参数时，显示当前管理员列表
        if not parts:
            admins = auth_manager.get_admins()
            if not admins:
                return "当前没有管理员"
            
            return "当前管理员列表：\n" + "\n".join([f"- {admin}" for admin in admins])
        
        # 获取操作和用户ID
        operation = parts[0].lower()
        
        # 添加管理员
        if operation == "add":
            if len(parts) < 2:
                return "请指定要添加的管理员ID，例如: /admin add 12345"
            
            target_id = parts[1]
            if auth_manager.is_admin(target_id):
                return f"用户 {target_id} 已经是管理员"
            
            auth_manager.add_admin(target_id)
            return f"已将用户 {target_id} 添加为管理员"
        
        # 删除管理员
        elif operation == "remove" or operation == "delete":
            if len(parts) < 2:
                return "请指定要删除的管理员ID，例如: /admin remove 12345"
            
            target_id = parts[1]
            if not auth_manager.is_admin(target_id):
                return f"用户 {target_id} 不是管理员"
            
            auth_manager.remove_admin(target_id)
            return f"已将用户 {target_id} 从管理员列表中移除"
        
        # 重新加载管理员列表
        elif operation == "reload":
            auth_manager.reload_admins()
            return "管理员列表已重新加载"
        
        # 未知操作
        else:
            return f"""无效的操作: {operation}
可用操作:
- add <用户ID>: 添加管理员
- remove <用户ID>: 删除管理员
- reload: 重新加载管理员列表
- 无参数: 显示当前管理员列表""" 