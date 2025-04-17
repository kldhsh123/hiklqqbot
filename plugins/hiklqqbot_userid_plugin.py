from .base_plugin import BasePlugin

class HiklqqbotUseridPlugin(BasePlugin):
    """
    获取用户ID的插件
    """
    
    def __init__(self):
        super().__init__(command="/hiklqqbot_userid", description="获取您的用户ID", is_builtin=True)
    
    async def handle(self, params: str, user_id: str = None) -> str:
        """
        获取用户ID
        
        Args:
            params: 命令参数（不使用）
            user_id: 用户ID
            
        Returns:
            用户ID信息
        """
        if not user_id:
            return "无法获取您的用户ID，请确保在私聊或@机器人时使用此命令"
        
        return f"您的用户ID是: {user_id}" 