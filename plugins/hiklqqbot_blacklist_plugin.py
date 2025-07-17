"""
黑名单管理插件
提供黑名单的添加、删除、查询等管理功能
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from plugins.base_plugin import BasePlugin
from blacklist_manager import blacklist_manager, BlacklistType
from auth_manager import auth_manager

logger = logging.getLogger("hiklqqbot_blacklist_plugin")

class HiklqqbotBlacklistPlugin(BasePlugin):
    """黑名单管理插件"""

    def __init__(self):
        super().__init__(
            command="hiklqqbot_blacklist",
            description="管理用户和群组黑名单",
            is_builtin=True,
            hidden=False
        )
        self.logger = logging.getLogger("plugin.hiklqqbot_blacklist")
        self.name = "黑名单管理"
        self.version = "1.0.0"
        self.author = "HiklQQBot"

    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """处理黑名单命令 - BasePlugin要求的抽象方法"""
        # 检查管理员权限
        if not auth_manager.is_admin(user_id):
            return "❌ 此命令需要管理员权限"

        # 解析参数
        if not params:
            return self._get_help_message()

        parts = params.split()
        action = parts[0].lower()

        try:
            if action == "add":
                return await self._handle_add(parts[1:], user_id)
            elif action == "remove":
                return await self._handle_remove(parts[1:])
            elif action == "list":
                return await self._handle_list(parts[1:])
            elif action == "info":
                return await self._handle_info(parts[1:])
            elif action == "clear":
                return await self._handle_clear(parts[1:])
            else:
                return self._get_help_message()

        except Exception as e:
            self.logger.error(f"处理黑名单命令时出错: {e}")
            return f"❌ 处理命令时出错: {str(e)}"
    
    def _get_help_message(self) -> str:
        """获取帮助信息"""
        return """📋 黑名单管理命令帮助

**添加到黑名单:**
• `/hiklqqbot_blacklist add user <用户ID> <原因>` - 添加用户到黑名单
• `/hiklqqbot_blacklist add group <群组ID> <原因>` - 添加群组到黑名单
• `/hiklqqbot_blacklist add user <用户ID> <原因> <过期时间>` - 添加临时黑名单

**从黑名单移除:**
• `/hiklqqbot_blacklist remove user <用户ID>` - 移除用户黑名单
• `/hiklqqbot_blacklist remove group <群组ID>` - 移除群组黑名单

**查询黑名单:**
• `/hiklqqbot_blacklist list` - 查看所有黑名单
• `/hiklqqbot_blacklist list users` - 查看用户黑名单
• `/hiklqqbot_blacklist list groups` - 查看群组黑名单
• `/hiklqqbot_blacklist info <ID>` - 查看指定条目详情

**管理黑名单:**
• `/hiklqqbot_blacklist clear all` - 清空所有黑名单
• `/hiklqqbot_blacklist clear users` - 清空用户黑名单
• `/hiklqqbot_blacklist clear groups` - 清空群组黑名单

**过期时间格式:** 1h(小时), 1d(天), 1w(周), 1m(月)"""
    
    async def _handle_add(self, args: List[str], admin_id: str) -> str:
        """处理添加命令"""
        if len(args) < 3:
            return "❌ 参数不足\n用法: `/blacklist add <user|group> <ID> <原因> [过期时间]`"
        
        target_type = args[0].lower()
        target_id = args[1]
        reason = args[2]
        expires_at = None
        
        # 解析过期时间
        if len(args) > 3:
            expires_at = self._parse_expire_time(args[3])
            if expires_at is None:
                return "❌ 无效的过期时间格式\n支持格式: 1h(小时), 1d(天), 1w(周), 1m(月)"
        
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
            return "❌ 参数不足\n用法: `/blacklist remove <user|group> <ID>`"
        
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
            result += "使用 `/blacklist list users` 或 `/blacklist list groups` 查看详细列表"
            return result
    
    async def _handle_info(self, args: List[str]) -> str:
        """处理信息查询命令"""
        if not args:
            return "❌ 请提供要查询的ID\n用法: `/blacklist info <ID>`"
        
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
            return "❌ 请指定清空类型\n用法: `/blacklist clear <all|users|groups>`"
        
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
