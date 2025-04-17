from .base_plugin import BasePlugin

class HiklqqbotUseridPlugin(BasePlugin):
    """
    获取用户ID和群ID的插件
    """
    
    def __init__(self):
        super().__init__(command="/hiklqqbot_userid", description="获取您的用户ID和群ID", is_builtin=True)
    
    async def handle(self, params: str, user_id: str = None, **kwargs) -> str:
        """
        获取用户ID和群ID
        
        Args:
            params: 命令参数（不使用）
            user_id: 用户ID
            **kwargs: 其他参数，可能包含群ID等信息
            
        Returns:
            用户ID和群ID信息
        """
        response = []
        
        # 获取用户ID
        if not user_id:
            response.append("无法获取您的用户ID，请确保在私聊或@机器人时使用此命令")
        else:
            response.append(f"您的用户ID是: {user_id}")
        
        # 获取群ID
        group_id = kwargs.get('group_openid') if kwargs else None
        if group_id:
            response.append(f"当前群ID是: {group_id}")
        else:
            response.append("当前不是在群聊中，无法获取群ID")
            
        return "\n".join(response) 