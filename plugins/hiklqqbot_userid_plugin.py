from plugins.base_plugin import BasePlugin
import logging
from auth_manager import auth_manager
import base64

class HiklqqbotUseridPlugin(BasePlugin):
# 为了合规性对openID进行base64加密
    """
    用户ID查询插件，返回用户的ID
    """
    
    def __init__(self):
        super().__init__(
            command="hiklqqbot_userid", 
            description="查询您的用户ID）", 
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
            group_openid: 群组ID
            **kwargs: 其他额外参数
            
        Returns:
            str: 用户ID信息
        """
        self.logger.info(f"收到userid命令，用户ID: {user_id}, 群组ID: {group_openid}")
        
        if not user_id:
            return "无法获取您的用户ID"
        
        # 对用户ID进行base64加密
        encoded_user_id = base64.b64encode(user_id.encode('utf-8')).decode('utf-8')
        response = f"您的用户ID是: {encoded_user_id}"
        
        if group_openid:
            # 对群组ID进行base64加密
            encoded_group_id = base64.b64encode(group_openid.encode('utf-8')).decode('utf-8')
            response += f"\n当前群组ID是: {encoded_group_id}"
            
        return response 