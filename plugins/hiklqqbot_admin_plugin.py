from plugins.base_plugin import BasePlugin
import logging
from auth_manager import auth_manager
from reply import Reply
from ui_builder import make_command_button, make_button_row, make_keyboard


class HiklqqbotAdminPlugin(BasePlugin):
    """管理员管理插件，用于添加/删除/查看管理员"""

    def __init__(self):
        super().__init__(
            command="hiklqqbot_admin",
            description="管理员管理：添加/删除/查看管理员",
            is_builtin=True,
            hidden=False,
            category="管理",
            display_name="管理员"
        )
        self.logger = logging.getLogger("plugin.admin")

    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs):
        self.logger.info(f"收到管理员管理命令，参数: {params}, 用户: {user_id}")

        current_admins = auth_manager.get_admins()

        # 引导首位管理员
        if not current_admins and user_id:
            self.logger.info(f"没有管理员注册，将用户 {user_id} 设置为第一个管理员")
            auth_manager.add_admin(user_id)
            return self._list_reply(user_id, prefix=f"✅ 您已被设置为**第一个管理员**\n")

        # 权限校验
        if not auth_manager.is_admin(user_id):
            return "您没有权限执行管理员命令"

        parts = (params or "").strip().split()

        # 无参数: 列表 + 快捷面板
        if not parts:
            return self._list_reply(user_id)

        operation = parts[0].lower()

        # add
        if operation == "add":
            if len(parts) < 2:
                return "请指定要添加的管理员ID，例如: /hiklqqbot_admin add 12345"
            target_id = parts[1]
            if auth_manager.is_admin(target_id):
                return f"用户 {target_id} 已经是管理员"
            auth_manager.add_admin(target_id)
            return self._list_reply(user_id, prefix=f"✅ 已将 `{target_id}` 添加为管理员\n")

        # remove / delete
        if operation in ("remove", "delete"):
            if len(parts) < 2:
                return "请指定要删除的管理员ID，例如: /hiklqqbot_admin remove 12345"
            target_id = parts[1]
            if not auth_manager.is_admin(target_id):
                return f"用户 {target_id} 不是管理员"
            auth_manager.remove_admin(target_id)
            return self._list_reply(user_id, prefix=f"✅ 已移除管理员 `{target_id}`\n")

        # reload
        if operation == "reload":
            auth_manager.reload_admins()
            return self._list_reply(user_id, prefix="✅ 管理员列表已重新加载\n")

        return (
            f"❌ 无效的操作: `{operation}`\n"
            "可用: `add <ID>` / `remove <ID>` / `reload` / 无参数显示列表"
        )

    def _list_reply(self, user_id: str, prefix: str = "") -> Reply:
        """构造管理员列表的富回复 (含快捷命令 + 管理菜单按钮)"""
        admins = auth_manager.get_admins()
        lines = []
        if prefix:
            lines.append(prefix)
        lines.append("## 管理员列表")
        if not admins:
            lines.append("（暂无管理员）")
        else:
            for a in admins:
                marker = "👑 " if a == user_id else "- "
                lines.append(f"{marker}`{a}`")
        lines.append("")
        lines.append("### 快捷操作")
        # md 内可点击的命令模板
        add_link = self._cmd_template_link(f"/hiklqqbot_admin add ", "添加管理员…")
        remove_link = self._cmd_template_link(f"/hiklqqbot_admin remove ", "移除管理员…")
        reload_link = self._cmd_link_input("/hiklqqbot_admin reload", "重载列表")
        lines.append(f"{add_link} │ {remove_link} │ {reload_link}")
        lines.append("")

        perm_users = [user_id] if user_id else None
        keyboard = make_keyboard([
            make_button_row([
                make_command_button("admin_menu", "管理菜单", "/help 管理",
                                     action_type=2, permission_user_ids=perm_users, style=1),
                make_command_button("home", "主菜单", "/help",
                                     action_type=2, permission_user_ids=perm_users, style=0),
                make_command_button("reload", "重载", "/hiklqqbot_admin reload",
                                     action_type=2, permission_user_ids=perm_users, style=0),
            ]),
        ])

        return Reply(markdown="\n".join(lines), keyboard=keyboard)

    def _cmd_template_link(self, prefix_cmd: str, show: str) -> str:
        """填充式命令模板: 点击后命令前缀填入输入框, 用户继续输入参数"""
        from urllib.parse import quote
        return f'<qqbot-cmd-input text="{quote(prefix_cmd, safe="")}" show="{show}" reference="false" />'

    def _cmd_link_input(self, cmd: str, show: str) -> str:
        from urllib.parse import quote
        return f'<qqbot-cmd-input text="{quote(cmd, safe="")}" show="{show}" reference="false" />'
