from .base_plugin import BasePlugin
from auth_manager import auth_manager

class HiklqqbotAdminPlugin(BasePlugin):
    """
    管理员管理插件，用于添加和删除管理员
    """
    
    def __init__(self):
        super().__init__(
            command="/hiklqqbot_admin", 
            description="管理员管理 (仅管理员可用)", 
            is_builtin=True
        )
    
    async def handle(self, params: str, user_id: str = None) -> str:
        """
        管理员管理命令处理
        
        命令格式:
        - /hiklqqbot_admin list: 列出所有管理员
        - /hiklqqbot_admin add <user_id>: 添加管理员
        - /hiklqqbot_admin remove <user_id>: 移除管理员
        
        Args:
            params: 命令参数
            user_id: 用户ID
            
        Returns:
            处理结果
        """
        # 检查是否是管理员
        if not auth_manager.is_admin(user_id):
            # 如果没有管理员，第一个使用此命令的人成为管理员
            if not auth_manager.get_admins():
                auth_manager.add_admin(user_id)
                return f"您已成为系统的第一个管理员 (ID: {user_id})"
            return "您没有权限执行此命令，请联系管理员"
        
        # 参数检查
        if not params:
            return "参数不足，请指定操作: list, add, remove"
        
        parts = params.strip().split()
        operation = parts[0].lower()
        
        # 处理不同操作
        if operation == "list":
            admins = auth_manager.get_admins()
            if not admins:
                return "当前没有管理员"
            return "管理员列表:\n" + "\n".join(admins)
            
        elif operation == "add":
            if len(parts) < 2:
                return "请指定要添加的用户ID"
            
            target_id = parts[1]
            if auth_manager.add_admin(target_id):
                return f"已添加管理员: {target_id}"
            else:
                return f"添加管理员失败，可能该用户已是管理员"
                
        elif operation == "remove":
            if len(parts) < 2:
                return "请指定要移除的用户ID"
            
            target_id = parts[1]
            if target_id == user_id:
                return "不能移除自己的管理员权限"
                
            if auth_manager.remove_admin(target_id):
                return f"已移除管理员: {target_id}"
            else:
                return f"移除管理员失败，可能该用户不是管理员"
                
        else:
            return f"未知操作: {operation}，支持的操作: list, add, remove" 