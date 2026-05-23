from plugins.base_plugin import BasePlugin
import logging
import time


class HiklqqbotPingPlugin(BasePlugin):
    """Ping 命令: 测试机器人在线和响应速度 """

    def __init__(self):
        super().__init__(
            command="hiklqqbot_ping",
            description="测试机器人是否在线",
            is_builtin=True,
            display_name="Ping",
        )
        self.logger = logging.getLogger("plugin.ping")

    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        self.logger.info("收到ping命令")
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        return f"pong! (响应时间: {current_time})"
