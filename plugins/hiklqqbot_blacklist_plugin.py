"""
黑名单管理插件
提供黑名单的添加、删除、查询等管理功能
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List
from urllib.parse import quote
from plugins.base_plugin import BasePlugin
from blacklist_manager import blacklist_manager, BlacklistType
from auth_manager import auth_manager
from reply import Reply
from ui_builder import make_command_button, make_button_row, make_keyboard


def _cmd_input(text: str, show: str) -> str:
    return f'<qqbot-cmd-input text="{quote(text, safe="")}" show="{show}" reference="false" />'


logger = logging.getLogger("hiklqqbot_blacklist_plugin")

class HiklqqbotBlacklistPlugin(BasePlugin):
    """黑名单管理插件"""

    def __init__(self):
        super().__init__(
            command="hiklqqbot_blacklist",
            description="管理用户和群组黑名单",
            is_builtin=True,
            hidden=False,
            category="管理",
            display_name="黑名单"
        )
        self.logger = logging.getLogger("plugin.hiklqqbot_blacklist")
        self.name = "黑名单管理"
        self.version = "1.0.0"
        self.author = "HiklQQBot"

    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs):
        """处理黑名单命令 - BasePlugin要求的抽象方法"""
        if not auth_manager.is_admin(user_id):
            return "❌ 此命令需要管理员权限"

        if not params:
            return self._build_menu_reply(user_id)

        parts = params.split()
        action = parts[0].lower()

        try:
            if action == "add":
                result = await self._handle_add(parts[1:], user_id)
            elif action == "remove":
                result = await self._handle_remove(parts[1:])
            elif action == "list":
                result = await self._handle_list(parts[1:])
            elif action == "info":
                result = await self._handle_info(parts[1:])
            elif action == "clear":
                result = await self._handle_clear(parts[1:])
            elif action in ("help", "menu"):
                return self._build_menu_reply(user_id)
            else:
                return self._build_menu_reply(user_id)
            # 子命令结果统一附加快捷面板
            return self._attach_quick_actions(result, user_id)
        except Exception as e:
            self.logger.error(f"处理黑名单命令时出错: {e}")
            return f"❌ 处理命令时出错: {str(e)}"

    def _attach_quick_actions(self, text_result, user_id: str) -> Reply:
        """把子命令的字符串输出包装成带快捷按钮的 Reply"""
        if isinstance(text_result, Reply):
            return text_result
        text = str(text_result or "")
        # 末尾追加快捷命令文字
        md_lines = [text, "", "---", "", "**快捷操作**", "",
                    f"{_cmd_input('/hiklqqbot_blacklist list', '全部列表')} │ "
                    f"{_cmd_input('/hiklqqbot_blacklist list users', '用户黑名单')} │ "
                    f"{_cmd_input('/hiklqqbot_blacklist list groups', '群组黑名单')}",
                    "***",
                    f"{_cmd_input('/hiklqqbot_blacklist add user ', '加用户…')} │ "
                    f"{_cmd_input('/hiklqqbot_blacklist remove user ', '移除用户…')} │ "
                    f"{_cmd_input('/hiklqqbot_blacklist info ', '查详情…')}",
                    "***",
                    f"{_cmd_input('/hiklqqbot_blacklist help', '黑名单菜单')}"]
        perm_users = [user_id] if user_id else None
        keyboard = make_keyboard([
            make_button_row([
                make_command_button("bl_menu", "黑名单菜单", "/hiklqqbot_blacklist",
                                     action_type=2, permission_user_ids=perm_users, style=1),
                make_command_button("admin_menu", "管理菜单", "/help 管理",
                                     action_type=2, permission_user_ids=perm_users, style=0),
                make_command_button("home", "主菜单", "/help",
                                     action_type=2, permission_user_ids=perm_users, style=0),
            ]),
        ])
        return Reply(markdown="\n".join(md_lines), keyboard=keyboard)

    def _build_menu_reply(self, user_id: str) -> Reply:
        """黑名单菜单: markdown 命令清单 + 快捷按钮"""
        lines = [
            "# 🚫 黑名单管理",
            "",
            "**查询**",
            "",
            f"{_cmd_input('/hiklqqbot_blacklist list', '全部黑名单')} │ {_cmd_input('/hiklqqbot_blacklist list users', '用户黑名单')}",
            "***",
            f"{_cmd_input('/hiklqqbot_blacklist list groups', '群组黑名单')} │ {_cmd_input('/hiklqqbot_blacklist info ', '查条目详情…')}",
            "***",
            "",
            "**添加** (输入模板, 自行补全参数)",
            "",
            f"{_cmd_input('/hiklqqbot_blacklist add user ', '加用户…')} │ {_cmd_input('/hiklqqbot_blacklist add group ', '加群组…')}",
            "***",
            "",
            "**移除 / 清空**",
            "",
            f"{_cmd_input('/hiklqqbot_blacklist remove user ', '移除用户…')} │ {_cmd_input('/hiklqqbot_blacklist remove group ', '移除群组…')}",
            "***",
            f"{_cmd_input('/hiklqqbot_blacklist clear users', '清空用户')} │ {_cmd_input('/hiklqqbot_blacklist clear groups', '清空群组')}",
            "***",
            "",
            "> 过期时间格式: `1h` `1d` `1w` `1m`",
        ]
        perm_users = [user_id] if user_id else None
        keyboard = make_keyboard([
            make_button_row([
                make_command_button("list", "全部列表", "/hiklqqbot_blacklist list",
                                     action_type=2, permission_user_ids=perm_users, style=1),
                make_command_button("admin_menu", "管理菜单", "/help 管理",
                                     action_type=2, permission_user_ids=perm_users, style=0),
                make_command_button("home", "主菜单", "/help",
                                     action_type=2, permission_user_ids=perm_users, style=0),
            ]),
        ])
        return Reply(markdown="\n".join(lines), keyboard=keyboard)

    def _get_help_message(self) -> str:
        """旧接口保留 (向后兼容), 现在等价于 _build_menu_reply 的文本版"""
        return ("📋 黑名单管理命令帮助\n\n"
                "• /hiklqqbot_blacklist add user <ID> <原因> [过期]\n"
                "• /hiklqqbot_blacklist add group <ID> <原因> [过期]\n"
                "• /hiklqqbot_blacklist remove user|group <ID>\n"
                "• /hiklqqbot_blacklist list [users|groups]\n"
                "• /hiklqqbot_blacklist info <ID>\n"
                "• /hiklqqbot_blacklist clear all|users|groups\n\n"
                "过期时间: 1h, 1d, 1w, 1m")
    
    async def _handle_add(self, args: List[str], admin_id: str) -> str:
        """处理添加命令"""
        if len(args) < 3:
            return "❌ 参数不足\n用法: `/hiklqqbot_blacklist add <user|group> <ID> <原因> [过期时间]`"

        target_type = args[0].lower()
        target_id = args[1]
        expires_at = None
        reason_parts = args[2:]

        # 仅将最后一个 token 识别为可选的过期时间，其余内容都属于原因文本。
        if len(reason_parts) > 1:
            last_token = reason_parts[-1]
            parsed_expire_time = self._parse_expire_time(last_token)
            if parsed_expire_time is not None:
                expires_at = parsed_expire_time
                reason_parts = reason_parts[:-1]
            elif self._looks_like_expire_token(last_token):
                return (
                    "❌ 过期时间格式无效，请使用: 1h(小时)、1d(天)、1w(周)、1m(月)"
                )

        reason = " ".join(reason_parts).strip()
        if not reason:
            return "❌ 参数不足\n用法: `/hiklqqbot_blacklist add <user|group> <ID> <原因> [过期时间]`"
        
        if target_type == "user":
            success = blacklist_manager.add_user(target_id, reason, admin_id, expires_at)
            if success:
                expire_info = f"，过期时间: {expires_at}" if expires_at else "（永久）"
                return f"✅ 已将用户 `{target_id}` 添加到黑名单\n原因: {reason}{expire_info}"
            else:
                return f"❌ 用户 `{target_id}` 已在黑名单中"
                
        elif target_type == "group":
            success = blacklist_manager.add_group(target_id, reason, admin_id, expires_at)
            if success:
                expire_info = f"，过期时间: {expires_at}" if expires_at else "（永久）"
                return f"✅ 已将群组 `{target_id}` 添加到黑名单\n原因: {reason}{expire_info}"
            else:
                return f"❌ 群组 `{target_id}` 已在黑名单中"
        else:
            return "❌ 无效的类型，请使用 `user` 或 `group`"
    
    async def _handle_remove(self, args: List[str]) -> str:
        """处理移除命令"""
        if len(args) < 2:
            return "❌ 参数不足\n用法: `/hiklqqbot_blacklist remove <user|group> <ID>`"
        
        target_type = args[0].lower()
        target_id = args[1]
        
        if target_type == "user":
            success = blacklist_manager.remove_user(target_id)
            if success:
                return f"✅ 已将用户 `{target_id}` 从黑名单移除"
            else:
                return f"❌ 用户 `{target_id}` 不在黑名单中"
                
        elif target_type == "group":
            success = blacklist_manager.remove_group(target_id)
            if success:
                return f"✅ 已将群组 `{target_id}` 从黑名单移除"
            else:
                return f"❌ 群组 `{target_id}` 不在黑名单中"
        else:
            return "❌ 无效的类型，请使用 `user` 或 `group`"
    
    async def _handle_list(self, args: List[str]) -> str:
        """处理列表命令"""
        list_type = args[0].lower() if args else "all"
        
        if list_type == "users":
            entries = blacklist_manager.list_users()
            if not entries:
                return "📋 用户黑名单为空"
            
            result = "📋 用户黑名单:\n\n"
            for entry in entries:
                expire_info = f" (过期: {entry.expires_at})" if entry.expires_at else " (永久)"
                result += f"• `{entry.id}`{expire_info}\n  原因: {entry.reason}\n  添加者: {entry.added_by}\n  时间: {entry.added_time}\n\n"
            return result.strip()
            
        elif list_type == "groups":
            entries = blacklist_manager.list_groups()
            if not entries:
                return "📋 群组黑名单为空"
            
            result = "📋 群组黑名单:\n\n"
            for entry in entries:
                expire_info = f" (过期: {entry.expires_at})" if entry.expires_at else " (永久)"
                result += f"• `{entry.id}`{expire_info}\n  原因: {entry.reason}\n  添加者: {entry.added_by}\n  时间: {entry.added_time}\n\n"
            return result.strip()
            
        else:  # all
            stats = blacklist_manager.get_stats()
            if stats['total'] == 0:
                return "📋 黑名单为空"
            
            result = f"📋 黑名单统计:\n\n"
            result += f"• 总计: {stats['total']} 个条目\n"
            result += f"• 用户: {stats['users']} 个\n"
            result += f"• 群组: {stats['groups']} 个\n"
            result += f"• 临时: {stats['temporary']} 个\n\n"
            result += "使用 `/hiklqqbot_blacklist list users` 或 `/hiklqqbot_blacklist list groups` 查看详细列表"
            return result
    
    async def _handle_info(self, args: List[str]) -> str:
        """处理信息查询命令"""
        if not args:
            return "❌ 请提供要查询的ID\n用法: `/hiklqqbot_blacklist info <ID>`"
        
        target_id = args[0]
        entry = blacklist_manager.get_entry(target_id)
        
        if not entry:
            return f"❌ 未找到ID `{target_id}` 的黑名单记录"
        
        expire_info = f"过期时间: {entry.expires_at}" if entry.expires_at else "永久有效"
        expired_status = " (已过期)" if entry.is_expired() else ""
        
        result = f"📋 黑名单详情:\n\n"
        result += f"• ID: `{entry.id}`\n"
        result += f"• 类型: {entry.type.value}\n"
        result += f"• 原因: {entry.reason}\n"
        result += f"• 添加者: {entry.added_by}\n"
        result += f"• 添加时间: {entry.added_time}\n"
        result += f"• {expire_info}{expired_status}"
        
        return result
    
    async def _handle_clear(self, args: List[str]) -> str:
        """处理清空命令"""
        if not args:
            return "❌ 请指定清空类型\n用法: `/hiklqqbot_blacklist clear <all|users|groups>`"
        
        clear_type = args[0].lower()
        
        if clear_type == "all":
            count = blacklist_manager.clear_all()
            return f"✅ 已清空所有黑名单，共移除 {count} 个条目"
            
        elif clear_type == "users":
            users = blacklist_manager.list_users()
            count = 0
            for user in users:
                if blacklist_manager.remove_user(user.id):
                    count += 1
            return f"✅ 已清空用户黑名单，共移除 {count} 个条目"
            
        elif clear_type == "groups":
            groups = blacklist_manager.list_groups()
            count = 0
            for group in groups:
                if blacklist_manager.remove_group(group.id):
                    count += 1
            return f"✅ 已清空群组黑名单，共移除 {count} 个条目"
        else:
            return "❌ 无效的清空类型，请使用 `all`、`users` 或 `groups`"
    
    def _parse_expire_time(self, time_str: str) -> str:
        """解析过期时间字符串"""
        try:
            if not time_str:
                return None
            
            time_str = time_str.lower()
            now = datetime.now()
            
            if time_str.endswith('h'):
                hours = int(time_str[:-1])
                expire_time = now + timedelta(hours=hours)
            elif time_str.endswith('d'):
                days = int(time_str[:-1])
                expire_time = now + timedelta(days=days)
            elif time_str.endswith('w'):
                weeks = int(time_str[:-1])
                expire_time = now + timedelta(weeks=weeks)
            elif time_str.endswith('m'):
                months = int(time_str[:-1])
                expire_time = now + timedelta(days=months * 30)  # 近似计算
            else:
                return None
            
            return expire_time.isoformat()
            
        except (ValueError, IndexError):
            return None

    def _looks_like_expire_token(self, token: str) -> bool:
        """判断 token 是否看起来像过期时间参数。"""
        if not token:
            return False
        return bool(re.match(r"^\d+[a-zA-Z]+$", token))
