from plugins.base_plugin import BasePlugin
from stats_manager import stats_manager
from auth_manager import auth_manager
import logging
import json
from datetime import datetime, timedelta
import time

class HiklqqbotStatsPlugin(BasePlugin):
    """
    统计数据管理插件：用于查看和管理机器人的统计数据
    仅限管理员使用
    """
    
    def __init__(self):
        super().__init__(
            command="hiklqqbot_stats", 
            description="查看机器人统计数据 (仅管理员)",
            is_builtin=True,
            hidden=False
        )
        self.logger = logging.getLogger("plugin.hiklqqbot_stats")
        
        # 子命令处理函数映射
        self.subcommands = {
            "groups": self._handle_groups,
            "users": self._handle_users,
            "usage": self._handle_usage,
            "group": self._handle_group_info,
            "user": self._handle_user_info,
            "daily": self._handle_daily_stats,
            "weekly": self._handle_weekly_stats,
            "monthly": self._handle_monthly_stats,
            "lookup": self._handle_id_lookup,
            "help": self._handle_help
        }
    
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """
        处理统计命令
        
        格式: hiklqqbot_stats <子命令> [参数]
        """
        # 只允许管理员使用
        if not auth_manager.is_admin(user_id):
            return "权限不足，此命令仅限管理员使用"
        
        # 解析子命令和参数
        parts = params.strip().split(maxsplit=1)
        subcommand = parts[0].lower() if parts else "help"
        subparams = parts[1] if len(parts) > 1 else ""
        
        # 如果没有子命令，显示帮助
        if not subcommand:
            return await self._handle_help(subparams)
        
        # 执行对应的子命令处理函数
        handler = self.subcommands.get(subcommand)
        if handler:
            return await handler(subparams)
        else:
            return f"未知的子命令: {subcommand}\n输入 'hiklqqbot_stats help' 获取帮助"
    
    async def _handle_help(self, params: str) -> str:
        """显示帮助信息"""
        help_text = (
            "统计数据管理命令 (仅限管理员)\n\n"
            "可用子命令:\n"
            "- hiklqqbot_stats groups [limit=10]: 显示所有群组列表\n"
            "- hiklqqbot_stats users [limit=10]: 显示所有用户列表\n"
            "- hiklqqbot_stats usage: 显示命令使用统计\n"
            "- hiklqqbot_stats group <群展示ID>: 显示指定群组的详细信息\n"
            "- hiklqqbot_stats user <用户展示ID>: 显示指定用户的详细信息\n"
            "- hiklqqbot_stats daily [日期=今天]: 显示指定日期的统计数据 (格式: YYYY-MM-DD)\n"
            "- hiklqqbot_stats weekly [周=本周]: 显示指定周的统计数据 (格式: YYYY-WNN)\n"
            "- hiklqqbot_stats monthly [月份=本月]: 显示指定月份的统计数据 (格式: YYYY-MM)\n"
            "- hiklqqbot_stats lookup <展示ID>: 查询展示ID对应的真实ID\n"
            "- hiklqqbot_stats help: 显示此帮助信息"
        )
        return help_text
    
    async def _handle_groups(self, params: str) -> str:
        """显示群组列表"""
        try:
            limit = 10
            if params:
                limit = int(params.strip())
            
            groups = stats_manager.get_all_groups()
            if not groups:
                return "当前没有记录的群组"
            
            # 按最后活跃时间排序
            sorted_groups = sorted(
                groups.items(), 
                key=lambda x: x[1].get("last_active", 0), 
                reverse=True
            )[:limit]
            
            result = f"群组列表 (总计: {len(groups)}, 显示: {min(limit, len(groups))}):\n\n"
            
            for i, (group_id, group_info) in enumerate(sorted_groups, 1):
                # 使用展示ID代替真实ID
                display_id = stats_manager.get_group_display_id(group_id)
                join_time = datetime.fromtimestamp(group_info.get("join_time", 0))
                last_active = datetime.fromtimestamp(group_info.get("last_active", 0))
                member_count = len(group_info.get("members", []))
                
                result += f"{i}. 群ID: {display_id}\n"
                result += f"   成员数: {member_count} 人\n"
                result += f"   加入时间: {join_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                result += f"   最后活跃: {last_active.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            return result
        except Exception as e:
            self.logger.error(f"获取群组列表时出错: {e}")
            return f"获取群组列表时出错: {str(e)}"
    
    async def _handle_users(self, params: str) -> str:
        """显示用户列表"""
        try:
            limit = 10
            if params:
                limit = int(params.strip())
            
            users = stats_manager.get_all_users()
            if not users:
                return "当前没有记录的用户"
            
            # 按最后活跃时间排序
            sorted_users = sorted(
                users.items(), 
                key=lambda x: x[1].get("last_active", 0), 
                reverse=True
            )[:limit]
            
            result = f"用户列表 (总计: {len(users)}, 显示: {min(limit, len(users))}):\n\n"
            
            for i, (user_id, user_info) in enumerate(sorted_users, 1):
                # 使用展示ID代替真实ID
                display_id = stats_manager.get_user_display_id(user_id)
                first_seen = datetime.fromtimestamp(user_info.get("first_seen", 0))
                last_active = datetime.fromtimestamp(user_info.get("last_active", 0))
                
                result += f"{i}. 用户ID: {display_id}\n"
                result += f"   首次见到: {first_seen.strftime('%Y-%m-%d %H:%M:%S')}\n"
                result += f"   最后活跃: {last_active.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            return result
        except Exception as e:
            self.logger.error(f"获取用户列表时出错: {e}")
            return f"获取用户列表时出错: {str(e)}"
    
    async def _handle_usage(self, params: str) -> str:
        """显示命令使用统计"""
        try:
            usage_stats = stats_manager.usage_stats
            
            # 命令使用统计
            command_stats = usage_stats.get("commands", {})
            sorted_commands = sorted(
                command_stats.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
            
            # 最活跃群组
            active_groups_raw = stats_manager.get_most_active_groups(5)
            active_groups = [(stats_manager.get_group_display_id(gid), count) for gid, count in active_groups_raw]
            
            # 最活跃用户
            active_users_raw = stats_manager.get_most_active_users(5)
            active_users = [(stats_manager.get_user_display_id(uid), count) for uid, count in active_users_raw]
            
            result = "命令使用统计:\n\n"
            
            # 总体统计
            result += f"总消息数: {usage_stats.get('total_messages', 0)}\n"
            result += f"总命令数: {sum(command_stats.values())}\n"
            result += f"记录群组数: {len(stats_manager.get_all_groups())}\n"
            result += f"记录用户数: {len(stats_manager.get_all_users())}\n\n"
            
            # 最常用命令
            result += "最常用命令 (Top 10):\n"
            for i, (cmd, count) in enumerate(sorted_commands, 1):
                result += f"{i}. {cmd}: {count} 次\n"
            
            result += "\n最活跃群组 (Top 5):\n"
            for i, (group_id, count) in enumerate(active_groups, 1):
                result += f"{i}. 群ID: {group_id}: {count} 条消息\n"
            
            result += "\n最活跃用户 (Top 5):\n"
            for i, (user_id, count) in enumerate(active_users, 1):
                result += f"{i}. 用户ID: {user_id}: {count} 条消息\n"
            
            return result
        except Exception as e:
            self.logger.error(f"获取命令使用统计时出错: {e}")
            return f"获取命令使用统计时出错: {str(e)}"
    
    async def _handle_group_info(self, params: str) -> str:
        """显示指定群组的详细信息"""
        if not params:
            return "请提供群组展示ID，例如: hiklqqbot_stats group G123456"
        
        display_id = params.strip()
        
        # 通过展示ID查询真实ID
        real_id, id_type = stats_manager.get_real_id(display_id)
        if not real_id or id_type != "groups":
            return f"未找到群组: {display_id}"
        
        group_info = stats_manager.get_group(real_id)
        if not group_info:
            return f"未找到群组: {display_id}"
        
        try:
            result = f"群组详细信息 ({display_id}):\n\n"
            
            # 基本信息
            join_time = datetime.fromtimestamp(group_info.get("join_time", 0))
            result += f"加入时间: {join_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            last_active = datetime.fromtimestamp(group_info.get("last_active", 0))
            result += f"最后活跃: {last_active.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            # 添加者信息
            added_by = group_info.get("added_by")
            if added_by:
                added_by_display = stats_manager.get_user_display_id(added_by)
                result += f"添加者ID: {added_by_display}\n"
            
            # 成员信息
            members = group_info.get("members", [])
            result += f"\n成员数量: {len(members)}\n"
            
            # 显示部分成员信息 - 使用展示ID
            if members:
                result += "\n成员ID列表 (最多显示10个):\n"
                for i, member_id in enumerate(members[:10], 1):
                    member_display = stats_manager.get_user_display_id(member_id)
                    result += f"{i}. {member_display}\n"
                
                if len(members) > 10:
                    result += f"...以及其他 {len(members) - 10} 名成员"
            
            return result
        except Exception as e:
            self.logger.error(f"获取群组信息时出错: {e}")
            return f"获取群组信息时出错: {str(e)}"
    
    async def _handle_user_info(self, params: str) -> str:
        """显示指定用户的详细信息"""
        if not params:
            return "请提供用户展示ID，例如: hiklqqbot_stats user U123456"
        
        display_id = params.strip()
        
        # 通过展示ID查询真实ID
        real_id, id_type = stats_manager.get_real_id(display_id)
        if not real_id or id_type != "users":
            return f"未找到用户: {display_id}"
        
        user_info = stats_manager.get_user(real_id)
        if not user_info:
            return f"未找到用户: {display_id}"
        
        try:
            result = f"用户详细信息 ({display_id}):\n\n"
            
            # 基本信息
            first_seen = datetime.fromtimestamp(user_info.get("first_seen", 0))
            result += f"首次见到: {first_seen.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            last_active = datetime.fromtimestamp(user_info.get("last_active", 0))
            result += f"最后活跃: {last_active.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            # 头像信息
            avatar = user_info.get("avatar")
            if avatar:
                result += f"头像URL: {avatar}\n"
            
            # 用户状态
            is_friend = user_info.get("is_friend", True)
            result += f"好友状态: {'是' if is_friend else '否'}\n"
            
            can_send_msg = user_info.get("can_send_proactive_msg", True)
            result += f"可发送主动消息: {'是' if can_send_msg else '否'}\n"
            
            # 群组信息 - 使用展示ID
            user_groups = user_info.get("groups", [])
            result += f"\n所在群组数: {len(user_groups)}\n"
            
            if user_groups:
                result += "\n所在群组ID列表:\n"
                for i, group_id in enumerate(user_groups[:5], 1):
                    group_display = stats_manager.get_group_display_id(group_id)
                    result += f"{i}. {group_display}\n"
                
                if len(user_groups) > 5:
                    result += f"...以及其他 {len(user_groups) - 5} 个群组"
            
            return result
        except Exception as e:
            self.logger.error(f"获取用户信息时出错: {e}")
            return f"获取用户信息时出错: {str(e)}"
            
    async def _handle_daily_stats(self, params: str) -> str:
        """处理日统计数据"""
        try:
            date_str = params.strip() if params else None
            if date_str:
                try:
                    # 验证日期格式
                    datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    return "日期格式错误，请使用 YYYY-MM-DD 格式，例如: hiklqqbot_stats daily 2023-05-01"
            
            daily_stats = stats_manager.get_daily_stats(date_str)
            date_display = date_str or datetime.now().strftime("%Y-%m-%d")
            
            if not daily_stats or daily_stats["total"] == 0:
                return f"日期 {date_display} 没有统计数据"
            
            result = f"日统计数据 ({date_display}):\n\n"
            
            # 总体统计
            result += f"总消息数: {daily_stats['total']}\n\n"
            
            # 命令统计
            command_stats = daily_stats.get("commands", {})
            if command_stats:
                sorted_commands = sorted(
                    command_stats.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5]
                
                result += "最常用命令 (Top 5):\n"
                for i, (cmd, count) in enumerate(sorted_commands, 1):
                    result += f"{i}. {cmd}: {count} 次\n"
                result += "\n"
            
            # 活跃群组
            group_stats = daily_stats.get("groups", {})
            if group_stats:
                sorted_groups = sorted(
                    group_stats.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5]
                
                result += "最活跃群组 (Top 5):\n"
                for i, (group_id, count) in enumerate(sorted_groups, 1):
                    group_display = stats_manager.get_group_display_id(group_id)
                    result += f"{i}. 群ID: {group_display}: {count} 条消息\n"
                result += "\n"
            
            # 活跃用户
            user_stats = daily_stats.get("users", {})
            if user_stats:
                sorted_users = sorted(
                    user_stats.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5]
                
                result += "最活跃用户 (Top 5):\n"
                for i, (user_id, count) in enumerate(sorted_users, 1):
                    user_display = stats_manager.get_user_display_id(user_id)
                    result += f"{i}. 用户ID: {user_display}: {count} 条消息\n"
            
            return result
        except Exception as e:
            self.logger.error(f"获取日统计数据时出错: {e}")
            return f"获取日统计数据时出错: {str(e)}"
    
    async def _handle_weekly_stats(self, params: str) -> str:
        """处理周统计数据"""
        try:
            week_str = params.strip() if params else None
            if week_str:
                if not (week_str.startswith("20") and "-W" in week_str):
                    return "周格式错误，请使用 YYYY-WNN 格式，例如: hiklqqbot_stats weekly 2023-W01"
            
            weekly_stats = stats_manager.get_weekly_stats(week_str)
            week_display = week_str or f"{datetime.now().year}-W{datetime.now().strftime('%W')}"
            
            if not weekly_stats or weekly_stats["total"] == 0:
                return f"周 {week_display} 没有统计数据"
            
            result = f"周统计数据 ({week_display}):\n\n"
            
            # 总体统计
            result += f"总消息数: {weekly_stats['total']}\n\n"
            
            # 命令统计
            command_stats = weekly_stats.get("commands", {})
            if command_stats:
                sorted_commands = sorted(
                    command_stats.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5]
                
                result += "最常用命令 (Top 5):\n"
                for i, (cmd, count) in enumerate(sorted_commands, 1):
                    result += f"{i}. {cmd}: {count} 次\n"
                result += "\n"
            
            # 活跃群组
            group_stats = weekly_stats.get("groups", {})
            if group_stats:
                sorted_groups = sorted(
                    group_stats.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5]
                
                result += "最活跃群组 (Top 5):\n"
                for i, (group_id, count) in enumerate(sorted_groups, 1):
                    group_display = stats_manager.get_group_display_id(group_id)
                    result += f"{i}. 群ID: {group_display}: {count} 条消息\n"
                result += "\n"
            
            # 活跃用户
            user_stats = weekly_stats.get("users", {})
            if user_stats:
                sorted_users = sorted(
                    user_stats.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5]
                
                result += "最活跃用户 (Top 5):\n"
                for i, (user_id, count) in enumerate(sorted_users, 1):
                    user_display = stats_manager.get_user_display_id(user_id)
                    result += f"{i}. 用户ID: {user_display}: {count} 条消息\n"
            
            return result
        except Exception as e:
            self.logger.error(f"获取周统计数据时出错: {e}")
            return f"获取周统计数据时出错: {str(e)}"
    
    async def _handle_monthly_stats(self, params: str) -> str:
        """处理月统计数据"""
        try:
            month_str = params.strip() if params else None
            if month_str:
                try:
                    # 验证月份格式
                    datetime.strptime(month_str + "-01", "%Y-%m-%d")
                except ValueError:
                    return "月份格式错误，请使用 YYYY-MM 格式，例如: hiklqqbot_stats monthly 2023-05"
            
            monthly_stats = stats_manager.get_monthly_stats(month_str)
            month_display = month_str or datetime.now().strftime("%Y-%m")
            
            if not monthly_stats or monthly_stats["total"] == 0:
                return f"月份 {month_display} 没有统计数据"
            
            result = f"月统计数据 ({month_display}):\n\n"
            
            # 总体统计
            result += f"总消息数: {monthly_stats['total']}\n\n"
            
            # 命令统计
            command_stats = monthly_stats.get("commands", {})
            if command_stats:
                sorted_commands = sorted(
                    command_stats.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5]
                
                result += "最常用命令 (Top 5):\n"
                for i, (cmd, count) in enumerate(sorted_commands, 1):
                    result += f"{i}. {cmd}: {count} 次\n"
                result += "\n"
            
            # 活跃群组
            group_stats = monthly_stats.get("groups", {})
            if group_stats:
                sorted_groups = sorted(
                    group_stats.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5]
                
                result += "最活跃群组 (Top 5):\n"
                for i, (group_id, count) in enumerate(sorted_groups, 1):
                    group_display = stats_manager.get_group_display_id(group_id)
                    result += f"{i}. 群ID: {group_display}: {count} 条消息\n"
                result += "\n"
            
            # 活跃用户
            user_stats = monthly_stats.get("users", {})
            if user_stats:
                sorted_users = sorted(
                    user_stats.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5]
                
                result += "最活跃用户 (Top 5):\n"
                for i, (user_id, count) in enumerate(sorted_users, 1):
                    user_display = stats_manager.get_user_display_id(user_id)
                    result += f"{i}. 用户ID: {user_display}: {count} 条消息\n"
            
            return result
        except Exception as e:
            self.logger.error(f"获取月统计数据时出错: {e}")
            return f"获取月统计数据时出错: {str(e)}"
    
    async def _handle_id_lookup(self, params: str) -> str:
        """查询展示ID对应的真实ID"""
        if not params:
            return "请提供要查询的展示ID，例如: hiklqqbot_stats lookup U123456"
        
        display_id = params.strip()
        real_id, id_type = stats_manager.get_real_id(display_id)
        
        if not real_id:
            return f"未找到展示ID: {display_id} 对应的实体"
        
        id_type_name = "用户" if id_type == "users" else "群组"
        return f"展示ID: {display_id}\n实际ID: {real_id}\n类型: {id_type_name}" 