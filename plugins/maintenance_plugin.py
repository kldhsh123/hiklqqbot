from plugins.base_plugin import BasePlugin
import logging
from auth_manager import auth_manager

class MaintenancePlugin(BasePlugin):
    """
    维护模式切换插件
    """
    
    def __init__(self):
        super().__init__(
            command="maintenance", 
            description="切换维护模式，仅管理员可用",
            is_builtin=False,
            hidden=True
        )
        self.logger = logging.getLogger("plugin.maintenance")
    
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """
        处理维护模式命令
        
        Args:
            params: 命令参数，on/off
            user_id: 用户ID，用于权限控制
            group_openid: 群组ID（不使用）
            **kwargs: 其他额外参数
            
        Returns:
            str: 处理结果
        """
        self.logger.info(f"收到维护模式切换命令，参数: {params}, 用户: {user_id}")
        
        # 检查权限，仅允许管理员执行
        if not auth_manager.is_admin(user_id):
            return "您没有权限执行此命令"
        
        # 解析参数
        if params.lower() == "on":
            auth_manager.set_maintenance_mode(True)
            return "维护模式已开启，仅管理员可使用机器人"
        elif params.lower() == "off":
            auth_manager.set_maintenance_mode(False)
            return "维护模式已关闭，所有用户可正常使用机器人"
        else:
            # 返回当前状态
            status = "开启" if auth_manager.is_maintenance_mode() else "关闭"
            return f"当前维护模式: {status}\n使用 maintenance on/off 来切换状态" 