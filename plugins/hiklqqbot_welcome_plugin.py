import logging
from typing import Any, Dict

from plugins.base_plugin import BasePlugin


class HiklqqbotWelcomePlugin(BasePlugin):
    """群成员加入/退出提示插件。"""

    event_types = ("GROUP_MEMBER_ADD", "GROUP_MEMBER_REMOVE")

    def __init__(self):
        super().__init__(
            command="hiklqqbot_welcome",
            description="群成员加入/退出提示",
            is_builtin=True,
            hidden=True,
            category="管理",
            display_name="欢迎提示",
        )
        self.logger = logging.getLogger("plugin.hiklqqbot_welcome")

    async def handle(
        self, params: str, user_id: str = None, group_openid: str = None, **kwargs
    ) -> str:
        return "群成员加入/退出提示插件正在运行"

    async def on_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        group_openid = event_data.get("group_openid")
        member_openid = event_data.get("member_openid")
        if not group_openid or not member_openid:
            self.logger.warning(f"成员事件缺少 group_openid/member_openid: {event_data}")
            return

        member_name = (
            event_data.get("member_name")
            or event_data.get("username")
            or member_openid[:12]
        )

        if event_type == "GROUP_MEMBER_ADD":
            content = f"欢迎新人 {member_name} 入群~ 🎉"
        elif event_type == "GROUP_MEMBER_REMOVE":
            content = f"{member_name} 已退出群聊，江湖再见~ 👋"
        else:
            return

        await self.send_text(group_openid, content, is_group=True)
        self.logger.info(f"已向群 {group_openid[:16]}... 发送成员事件提示: {content[:50]}...")
