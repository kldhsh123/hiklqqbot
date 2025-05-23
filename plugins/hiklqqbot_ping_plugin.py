from plugins.base_plugin import BasePlugin
import logging
import time
from auth_manager import auth_manager

class HiklqqbotPingPlugin(BasePlugin):
    """
    Ping命令插件，用于测试机器人是否在线以及响应速度
    """
    
    def __init__(self):
        super().__init__(command="hiklqqbot_ping", description="测试机器人是否在线 (仅管理员可用)", is_builtin=True)
        self.logger = logging.getLogger("plugin.ping")
    
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """
        处理ping命令，返回pong和当前时间戳
        
        Args:
            params: 命令参数（不使用）
            user_id: 用户ID
            group_openid: 群组ID（不使用）
            **kwargs: 其他参数
            
        Returns:
            str: pong响应
        """
        self.logger.info("收到ping命令")
        
        # 检查用户是否是管理员
        if not auth_manager.is_admin(user_id):
            return "您没有权限执行此命令，请联系管理员"
            
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        return f"pong! (响应时间: {current_time})" 