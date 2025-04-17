from plugins.base_plugin import BasePlugin
import logging

class HiklqqbotUseridPlugin(BasePlugin):
    """
    用户ID查询插件，返回用户的ID
    """
    
    def __init__(self):
        super().__init__(
            command="/hiklqqbot_userid", 
            description="查询您的用户ID", 
            is_builtin=True,
            hidden=False
        )
        self.logger = logging.getLogger("plugin.hiklqqbot_userid")
    
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """
        处理userid命令，返回用户的ID
        
        Args:
            params: 命令参数（不使用）
            user_id: 用户ID
            group_openid: 群组ID（不使用）
            **kwargs: 其他额外参数
            
        Returns:
            str: 用户ID信息
        """
        self.logger.info(f"收到userid命令，用户ID: {user_id}")
        
        if not user_id:
            return "无法获取您的用户ID"
        
        return f"您的用户ID是: {user_id}\n可用于设置管理员等需要用户ID的操作" 