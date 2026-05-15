from plugins.base_plugin import BasePlugin
import logging
from auth_manager import auth_manager
from reply import Reply
from ui_builder import make_command_button, make_button_row, make_keyboard


class HiklqqbotMaintenancePlugin(BasePlugin):
    """维护模式管理插件，仅管理员可用"""

    def __init__(self):
        super().__init__(
            command="hiklqqbot_maintenance",
            description="设置或查看维护模式状态 (仅管理员可用)",
            is_builtin=True,
            category="管理",
            display_name="维护模式"
        )
        self.logger = logging.getLogger("plugin.hiklqqbot_maintenance")

    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs):
        if not auth_manager.is_admin(user_id):
            return "您没有权限执行此命令，请联系管理员"

        param = (params or "").strip().lower()

        # 写状态变化
        msg_lines = []
        if param == "on":
            auth_manager.set_maintenance_mode(True)
            msg_lines.append("✅ 维护模式已 **启用**，仅管理员可与机器人交互")
        elif param == "off":
            auth_manager.set_maintenance_mode(False)
            msg_lines.append("✅ 维护模式已 **禁用**，所有用户可与机器人交互")
        elif param and param not in ("on", "off"):
            msg_lines.append(f"❌ 参数无效: `{param}`，请使用 `on` 或 `off`")

        # 当前状态展示
        is_on = auth_manager.is_maintenance_mode()
        status_label = "🟢 已启用" if is_on else "⚪ 已禁用"
        msg_lines.append("")
        msg_lines.append("## 维护模式状态")
        msg_lines.append(f"当前: **{status_label}**")
        msg_lines.append("")

        # 开关按钮 (只显示反向操作)
        perm_users = [user_id] if user_id else None
        if is_on:
            toggle_btn = make_command_button(
                "off", "禁用维护", "/hiklqqbot_maintenance off",
                action_type=2, permission_user_ids=perm_users, style=0,
            )
        else:
            toggle_btn = make_command_button(
                "on", "启用维护", "/hiklqqbot_maintenance on",
                action_type=2, permission_user_ids=perm_users, style=1,
            )

        # 第二行: 跳转管理菜单 / 主菜单
        nav_buttons = [
            make_command_button(
                "admin_menu", "管理菜单", "/help 管理",
                action_type=2, permission_user_ids=perm_users, style=0,
            ),
            make_command_button(
                "home", "主菜单", "/help",
                action_type=2, permission_user_ids=perm_users, style=0,
            ),
        ]

        keyboard = make_keyboard([
            make_button_row([toggle_btn]),
            make_button_row(nav_buttons),
        ])

        return Reply(markdown="\n".join(msg_lines).strip(), keyboard=keyboard)
