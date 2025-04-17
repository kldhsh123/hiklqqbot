from plugins.base_plugin import BasePlugin
import logging
import time

class HiklqqbotPingPlugin(BasePlugin):
    """
    Ping命令插件，用于测试机器人是否在线以及响应速度
    """
    
    def __init__(self):
        super().__init__(command="/hiklqqbot_ping", description="测试机器人是否在线", is_builtin=True)
        self.logger = logging.getLogger("plugin.ping")
    
    async def handle(self, params: str, user_id: str = None) -> str:
        """
        处理ping命令，返回pong和当前时间戳
        
        Args:
            params: 命令参数（不使用）
            user_id: 用户ID（不使用）
            
        Returns:
            str: pong响应
        """
        self.logger.info("收到ping命令")
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        return f"pong! (响应时间: {current_time})" 