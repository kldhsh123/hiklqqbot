from .base_plugin import BasePlugin
from auth_manager import auth_manager

class HiklqqbotMaintenancePlugin(BasePlugin):
    """
    维护模式管理插件，仅管理员可用
    """
    
    def __init__(self):
        super().__init__(
            command="/hiklqqbot_maintenance", 
            description="设置或查看维护模式状态 (仅管理员可用)", 
            is_builtin=True
        )
    
    async def handle(self, params: str, user_id: str = None) -> str:
        """
        设置或查询维护模式
        
        Args:
            params: 命令参数 (on/off)
            user_id: 用户ID
            
        Returns:
            处理结果
        """
        # 检查是否是管理员
        if not auth_manager.is_admin(user_id):
            return "您没有权限执行此命令，请联系管理员"
        
        # 如果没有参数，返回当前状态
        if not params:
            status = "已启用" if auth_manager.is_maintenance_mode() else "已禁用"
            return f"当前维护模式状态: {status}"
        
        # 处理参数
        param = params.strip().lower()
        if param == "on":
            auth_manager.set_maintenance_mode(True)
            return "维护模式已启用，仅管理员可与机器人交互"
        elif param == "off":
            auth_manager.set_maintenance_mode(False)
            return "维护模式已禁用，所有用户可与机器人交互"
        else:
            return "参数无效，请使用 on 或 off" 