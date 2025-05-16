from plugins.base_plugin import BasePlugin
from stats_manager import stats_manager
from auth_manager import auth_manager
import logging
import json
from datetime import datetime
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
            "- hiklqqbot_stats group <群ID>: 显示指定群组的详细信息\n"
            "- hiklqqbot_stats user <用户ID>: 显示指定用户的详细信息\n"
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
                join_time = datetime.fromtimestamp(group_info.get("join_time", 0))
                last_active = datetime.fromtimestamp(group_info.get("last_active", 0))
                member_count = len(group_info.get("members", []))
                
                result += f"{i}. 群ID: {group_id}\n"
                result += f"   名称: {group_info.get('name', '群组')}\n"
                result += f"   成员: {member_count} 人\n"
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
                first_seen = datetime.fromtimestamp(user_info.get("first_seen", 0))
                last_active = datetime.fromtimestamp(user_info.get("last_active", 0))
                
                result += f"{i}. 用户ID: {user_id}\n"
                result += f"   名称: {user_info.get('name', '名称')}\n"
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
            active_groups = stats_manager.get_most_active_groups(5)
            
            # 最活跃用户
            active_users = stats_manager.get_most_active_users(5)
            
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
                group_info = stats_manager.get_group(group_id)
                group_name = group_info.get("name", "名称") if group_info else "名称"
                result += f"{i}. {group_name} ({group_id}): {count} 条消息\n"
            
            result += "\n最活跃用户 (Top 5):\n"
            for i, (user_id, count) in enumerate(active_users, 1):
                user_info = stats_manager.get_user(user_id)
                user_name = user_info.get("name", "名称") if user_info else "名称"
                result += f"{i}. {user_name} ({user_id}): {count} 条消息\n"
            
            return result
        except Exception as e:
            self.logger.error(f"获取命令使用统计时出错: {e}")
            return f"获取命令使用统计时出错: {str(e)}"
    
    async def _handle_group_info(self, params: str) -> str:
        """显示指定群组的详细信息"""
        if not params:
            return "请提供群组ID，例如: hiklqqbot_stats group <群ID>"
        
        group_id = params.strip()
        group_info = stats_manager.get_group(group_id)
        
        if not group_info:
            return f"未找到群组: {group_id}"
        
        try:
            result = f"群组详细信息 ({group_id}):\n\n"
            
            # 基本信息
            result += f"名称: {group_info.get('name', '名称')}\n"
            join_time = datetime.fromtimestamp(group_info.get("join_time", 0))
            result += f"加入时间: {join_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            last_active = datetime.fromtimestamp(group_info.get("last_active", 0))
            result += f"最后活跃: {last_active.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            # 添加者信息
            added_by = group_info.get("added_by")
            if added_by:
                adder_info = stats_manager.get_user(added_by)
                adder_name = adder_info.get("name", "名称") if adder_info else "名称"
                result += f"添加者: {adder_name} ({added_by})\n"
            
            # 成员信息
            members = group_info.get("members", [])
            result += f"\n成员数量: {len(members)}\n"
            
            # 显示部分成员信息
            if members:
                result += "\n成员列表 (最多显示10个):\n"
                for i, member_id in enumerate(members[:10], 1):
                    member_info = stats_manager.get_user(member_id)
                    member_name = member_info.get("name", "名称") if member_info else "名称"
                    result += f"{i}. {member_name} ({member_id})\n"
                
                if len(members) > 10:
                    result += f"...以及其他 {len(members) - 10} 名成员"
            
            return result
        except Exception as e:
            self.logger.error(f"获取群组信息时出错: {e}")
            return f"获取群组信息时出错: {str(e)}"
    
    async def _handle_user_info(self, params: str) -> str:
        """显示指定用户的详细信息"""
        if not params:
            return "请提供用户ID，例如: hiklqqbot_stats user <用户ID>"
        
        user_id = params.strip()
        user_info = stats_manager.get_user(user_id)
        
        if not user_info:
            return f"未找到用户: {user_id}"
        
        try:
            result = f"用户详细信息 ({user_id}):\n\n"
            
            # 基本信息
            result += f"名称: {user_info.get('name', '名称')}\n"
            
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
            
            # 群组信息
            user_groups = user_info.get("groups", [])
            result += f"\n所在群组数: {len(user_groups)}\n"
            
            if user_groups:
                result += "\n所在群组列表:\n"
                for i, group_id in enumerate(user_groups[:5], 1):
                    group_info = stats_manager.get_group(group_id)
                    group_name = group_info.get("name", "名称") if group_info else "名称"
                    result += f"{i}. {group_name} ({group_id})\n"
                
                if len(user_groups) > 5:
                    result += f"...以及其他 {len(user_groups) - 5} 个群组"
            
            return result
        except Exception as e:
            self.logger.error(f"获取用户信息时出错: {e}")
            return f"获取用户信息时出错: {str(e)}" 