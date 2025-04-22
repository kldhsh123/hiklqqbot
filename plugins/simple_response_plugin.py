from plugins.base_plugin import BasePlugin
import logging

class SimpleResponsePlugin(BasePlugin):
    """
    简单的响应插件，输入1返回2
    """
    
    def __init__(self):
        super().__init__(command="1", description="输入/1返回2", is_builtin=False)
        self.logger = logging.getLogger("plugin.simple_response")
    
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """
        处理1命令，返回2
        
        Args:
            params: 命令参数（不使用）
            user_id: 用户ID（不使用）
            group_openid: 群组ID（不使用）
            **kwargs: 其他额外参数
            
        Returns:
            响应结果
        """
        self.logger.info("收到1命令，返回2")
        return "2" 