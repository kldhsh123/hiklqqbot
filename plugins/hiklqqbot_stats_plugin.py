import logging
from typing import Dict, List, Optional, Any
from plugins.base_plugin import BasePlugin
from auth_manager import auth_manager
from stats_manager import stats_manager
import time
from datetime import datetime, timedelta

class HiklqqbotStatsPlugin(BasePlugin):
    """
    统计信息查询插件，提供对机器人群组和用户统计的查询功能（仅管理员可用）
    """

    def __init__(self):
        super().__init__(
            command="stats",
            description="统计信息查询 | 用法: /stats [groups|users|events|summary] | 仅管理员可用",
            is_builtin=True,
            admin_only=True  # 设置为仅管理员可用
        )
        self.logger = logging.getLogger("plugin.stats")
        self.logger.info("统计插件已初始化")
        
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """
        处理统计命令
        
        Args:
            params: 命令参数，可以是 groups, users, events, summary 等
            user_id: 用户ID
            group_openid: 群组ID（如果是群消息）
            
        Returns:
            统计信息文本
        """
        try:
            # 再次检查用户权限，确保只有管理员能查看统计 
            # (因为admin_only已经在BasePlugin中处理，这个检查实际上是多余的，但保留它以增加安全性)
            if not auth_manager.is_admin(user_id):
                return "此命令仅管理员可用"
            
            # 解析子命令
            parts = params.strip().split(maxsplit=1)
            subcmd = parts[0].lower() if parts else "summary"
            
            # 根据子命令执行相应的统计功能
            if subcmd == "groups":
                return await self._get_groups_stats(True)
            elif subcmd == "users":
                return await self._get_users_stats(True)
            elif subcmd == "events":
                return await self._get_events_stats(True, parts[1] if len(parts) > 1 else None)
            elif subcmd == "summary":
                return await self._get_summary_stats()
            elif subcmd == "help":
                return self._get_help_text(True)
            elif subcmd == "group" and len(parts) > 1:
                return await self._get_group_detail(parts[1])
            elif subcmd == "user" and len(parts) > 1:
                return await self._get_user_detail(parts[1])
            else:
                return "未知的统计子命令。使用 /stats help 查看帮助。"
                
        except Exception as e:
            self.logger.error(f"处理统计命令时出错: {e}")
            return f"处理统计命令时出错: {str(e)}"
            
    async def _get_groups_stats(self, is_admin: bool) -> str:
        """获取群组统计信息"""
        active_groups = stats_manager.get_active_groups()
        all_groups = stats_manager.get_all_groups()
        
        # 计算7天内活跃的群组
        seven_days_ago = int(time.time()) - 7 * 24 * 60 * 60
        active_groups_7d = sum(1 for info in all_groups.values() 
                             if info.get("last_active_time", 0) > seven_days_ago and 
                             not info.get("removed", False))
        
        result = [
            "【群组统计信息】",
            f"总群组数: {len(all_groups)}",
            f"当前活跃群组: {len(active_groups)}",
            f"7天内活跃群组: {active_groups_7d}"
        ]
        
        # 如果是管理员，显示更多详细信息
        if is_admin:
            # 计算最近加入的5个群组
            recent_groups = sorted(
                [(gid, info) for gid, info in all_groups.items() if not info.get("removed", False)],
                key=lambda x: x[1].get("join_time", 0),
                reverse=True
            )[:5]
            
            if recent_groups:
                result.append("\n最近加入的群组:")
                for group_id, info in recent_groups:
                    join_time = info.get("join_time", 0)
                    join_time_str = datetime.fromtimestamp(join_time).strftime("%Y-%m-%d %H:%M") if join_time else "未知"
                    group_name = info.get("name", "未知群名")
                    result.append(f"- {group_name}({group_id}): {join_time_str}")
            
            # 计算成员最多的5个群组
            largest_groups = sorted(
                [(gid, len(stats_manager.get_group_users(gid))) for gid in active_groups],
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            if largest_groups:
                result.append("\n成员最多的群组:")
                for group_id, member_count in largest_groups:
                    group_info = all_groups.get(group_id, {})
                    group_name = group_info.get("name", "未知群名")
                    result.append(f"- {group_name}({group_id}): {member_count}人")
                    
        return "\n".join(result)
    
    async def _get_users_stats(self, is_admin: bool) -> str:
        """获取用户统计信息"""
        all_users = stats_manager.get_all_users()
        
        # 计算7天内活跃的用户
        seven_days_ago = int(time.time()) - 7 * 24 * 60 * 60
        active_users_7d = sum(1 for info in all_users.values() 
                            if info.get("last_active_time", 0) > seven_days_ago)
                            
        # 计算好友数
        friends_count = sum(1 for info in all_users.values() 
                         if info.get("is_friend", False))
        
        result = [
            "【用户统计信息】",
            f"总用户数: {len(all_users)}",
            f"7天内活跃用户: {active_users_7d}",
            f"好友数: {friends_count}"
        ]
        
        # 如果是管理员，显示更多详细信息
        if is_admin:
            # 计算最近活跃的5个用户
            recent_users = sorted(
                all_users.items(),
                key=lambda x: x[1].get("last_active_time", 0),
                reverse=True
            )[:5]
            
            if recent_users:
                result.append("\n最近活跃的用户:")
                for user_id, info in recent_users:
                    active_time = info.get("last_active_time", 0)
                    active_time_str = datetime.fromtimestamp(active_time).strftime("%Y-%m-%d %H:%M") if active_time else "未知"
                    user_name = info.get("name", "未知用户")
                    result.append(f"- {user_name}({user_id}): {active_time_str}")
                    
            # 计算加入群组最多的5个用户
            user_group_counts = {}
            for user_id in all_users:
                user_group_counts[user_id] = len(stats_manager.get_user_groups(user_id))
            
            top_users = sorted(
                user_group_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            if top_users:
                result.append("\n加入群组最多的用户:")
                for user_id, group_count in top_users:
                    user_info = all_users.get(user_id, {})
                    user_name = user_info.get("name", "未知用户")
                    result.append(f"- {user_name}({user_id}): {group_count}个群组")
                    
        return "\n".join(result)
    
    async def _get_events_stats(self, is_admin: bool, event_type: Optional[str] = None) -> str:
        """获取事件统计信息"""
        event_counts = stats_manager.get_event_count()
        
        if event_type and event_type != "all" and is_admin:
            # 显示特定类型的事件详情
            events = stats_manager.get_events(event_type, limit=10)
            
            if not events:
                return f"未找到类型为 {event_type} 的事件记录"
                
            result = [f"【事件统计 - {event_type}】", f"共有记录: {len(events)}"]
            
            for event in events:
                timestamp = event.get("timestamp", "未知时间")
                data = event.get("data", {})
                data_str = ", ".join(f"{k}={v}" for k, v in data.items())
                result.append(f"- {timestamp}: {data_str}")
                
            return "\n".join(result)
        
        # 统计总体事件数量
        total_events = sum(event_counts.values())
        
        result = [
            "【事件统计信息】",
            f"总事件数: {total_events}"
        ]
        
        # 显示各类事件数量
        sorted_events = sorted(
            event_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 普通用户只显示部分常见事件
        if not is_admin:
            common_events = {
                "GROUP_AT_MESSAGE_CREATE": "群聊@消息",
                "DIRECT_MESSAGE_CREATE": "私聊消息",
                "GROUP_ADD_ROBOT": "机器人加群",
                "GROUP_DEL_ROBOT": "机器人退群",
                "FRIEND_ADD": "添加好友"
            }
            
            result.append("\n常见事件统计:")
            for event_type, desc in common_events.items():
                count = event_counts.get(event_type, 0)
                result.append(f"- {desc}: {count}次")
        else:
            # 管理员显示所有事件类型及数量
            result.append("\n所有事件统计:")
            for event_type, count in sorted_events:
                result.append(f"- {event_type}: {count}次")
            
            result.append("\n使用 /stats events <事件类型> 查看特定事件的详情")
            
        return "\n".join(result)
    
    async def _get_summary_stats(self) -> str:
        """获取统计摘要信息"""
        summary = stats_manager.get_stats_summary()
        
        # 计算当前时间
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        
        # 事件统计
        event_counts = summary["event_counts"]
        
        # 计算今日消息数（近似值）
        today_start = int(datetime.combine(now.date(), datetime.min.time()).timestamp())
        today_events = stats_manager.get_events("GROUP_AT_MESSAGE_CREATE", limit=1000)
        today_messages = sum(1 for e in today_events if e.get("time", 0) >= today_start)
        
        today_direct = stats_manager.get_events("DIRECT_MESSAGE_CREATE", limit=1000)
        today_direct_messages = sum(1 for e in today_direct if e.get("time", 0) >= today_start)
        
        result = [
            f"【统计摘要 - {today}】",
            f"群组: {summary['active_groups']}/{summary['total_groups']} (活跃/总数)",
            f"用户: {summary['active_users_7d']}/{summary['total_users']} (7天活跃/总数)",
            f"今日消息: {today_messages}条群聊, {today_direct_messages}条私聊",
            f"累计事件: {summary['events_total']}条"
        ]
        
        # 计算最近的事件
        recent_important = []
        for event_type in ["GROUP_ADD_ROBOT", "GROUP_DEL_ROBOT", "FRIEND_ADD", "FRIEND_DEL"]:
            events = stats_manager.get_events(event_type, limit=3)
            for event in events:
                recent_important.append((event.get("time", 0), event_type, event))
        
        # 取最近的5个重要事件
        recent_important.sort(key=lambda x: x[0], reverse=True)
        if recent_important[:5]:
            result.append("\n最近重要事件:")
            for _, event_type, event in recent_important[:5]:
                event_time = event.get("timestamp", "未知")
                data = event.get("data", {})
                
                if event_type == "GROUP_ADD_ROBOT":
                    group_id = data.get("group_id", "未知")
                    group_info = stats_manager.get_group(group_id) or {}
                    group_name = group_info.get("name", "未知群组")
                    result.append(f"- 机器人加入群组: {group_name}({group_id}) 于 {event_time}")
                
                elif event_type == "GROUP_DEL_ROBOT":
                    group_id = data.get("group_id", "未知")
                    group_info = stats_manager.get_group(group_id) or {}
                    group_name = group_info.get("name", "未知群组")
                    result.append(f"- 机器人退出群组: {group_name}({group_id}) 于 {event_time}")
                
                elif event_type == "FRIEND_ADD":
                    user_id = data.get("user_id", "未知")
                    user_info = stats_manager.get_user(user_id) or {}
                    user_name = user_info.get("name", "未知用户")
                    result.append(f"- 新增好友: {user_name}({user_id}) 于 {event_time}")
                
                elif event_type == "FRIEND_DEL":
                    user_id = data.get("user_id", "未知")
                    user_info = stats_manager.get_user(user_id) or {}
                    user_name = user_info.get("name", "未知用户")
                    result.append(f"- 好友删除: {user_name}({user_id}) 于 {event_time}")
        
        return "\n".join(result)
    
    async def _get_group_detail(self, group_id: str) -> str:
        """获取群组详细信息"""
        group_info = stats_manager.get_group(group_id)
        if not group_info:
            return f"未找到群组 {group_id} 的信息"
        
        group_name = group_info.get("name", "未知群名")
        join_time = group_info.get("join_time", 0)
        join_time_str = datetime.fromtimestamp(join_time).strftime("%Y-%m-%d %H:%M:%S") if join_time else "未知"
        
        last_active = group_info.get("last_active_time", 0)
        last_active_str = datetime.fromtimestamp(last_active).strftime("%Y-%m-%d %H:%M:%S") if last_active else "未知"
        
        is_removed = group_info.get("removed", False)
        status = "已退出" if is_removed else "活跃中"
        
        users = stats_manager.get_group_users(group_id)
        
        result = [
            f"【群组详情 - {group_name}】",
            f"群组ID: {group_id}",
            f"状态: {status}",
            f"加入时间: {join_time_str}",
            f"最后活跃: {last_active_str}",
            f"成员数: {len(users)}"
        ]
        
        # 如果群已退出，显示退出信息
        if is_removed:
            remove_time = group_info.get("remove_time", 0)
            remove_time_str = datetime.fromtimestamp(remove_time).strftime("%Y-%m-%d %H:%M:%S") if remove_time else "未知"
            remove_reason = group_info.get("remove_reason", "未知原因")
            result.append(f"退出时间: {remove_time_str}")
            result.append(f"退出原因: {remove_reason}")
        
        # 显示允许接收主动消息状态
        allow_messages = group_info.get("allow_active_messages")
        if allow_messages is not None:
            result.append(f"允许主动消息: {'是' if allow_messages else '否'}")
        
        # 显示其他元数据信息
        for key, value in group_info.items():
            if key not in ["name", "join_time", "last_active_time", "removed", "remove_time", 
                          "remove_reason", "allow_active_messages"]:
                result.append(f"{key}: {value}")
        
        # 添加最近的群组事件
        group_events = []
        for event_type in ["GROUP_AT_MESSAGE_CREATE"]:
            events = stats_manager.get_events(event_type, limit=100)
            for event in events:
                data = event.get("data", {})
                if data.get("group_id") == group_id:
                    group_events.append((event.get("time", 0), event_type, event))
        
        # 取最近的5个群组事件
        group_events.sort(key=lambda x: x[0], reverse=True)
        if group_events[:5]:
            result.append("\n最近群组事件:")
            for _, event_type, event in group_events[:5]:
                event_time = event.get("timestamp", "未知")
                data = event.get("data", {})
                user_id = data.get("user_id", "未知")
                result.append(f"- {event_type} 于 {event_time} 由 {user_id}")
        
        return "\n".join(result)
    
    async def _get_user_detail(self, user_id: str) -> str:
        """获取用户详细信息"""
        user_info = stats_manager.get_user(user_id)
        if not user_info:
            return f"未找到用户 {user_id} 的信息"
        
        user_name = user_info.get("name", "未知用户")
        first_seen = user_info.get("first_seen", 0)
        first_seen_str = datetime.fromtimestamp(first_seen).strftime("%Y-%m-%d %H:%M:%S") if first_seen else "未知"
        
        last_active = user_info.get("last_active_time", 0)
        last_active_str = datetime.fromtimestamp(last_active).strftime("%Y-%m-%d %H:%M:%S") if last_active else "未知"
        
        is_friend = user_info.get("is_friend", False)
        status = "好友" if is_friend else "非好友"
        
        groups = stats_manager.get_user_groups(user_id)
        
        result = [
            f"【用户详情 - {user_name}】",
            f"用户ID: {user_id}",
            f"状态: {status}",
            f"首次见到: {first_seen_str}",
            f"最后活跃: {last_active_str}",
            f"加入群组数: {len(groups)}"
        ]
        
        # 如果是好友，显示添加时间
        if is_friend:
            add_time = user_info.get("friend_add_time", 0)
            add_time_str = datetime.fromtimestamp(add_time).strftime("%Y-%m-%d %H:%M:%S") if add_time else "未知"
            result.append(f"成为好友时间: {add_time_str}")
        
        # 显示允许接收主动消息状态
        allow_messages = user_info.get("allow_active_messages")
        if allow_messages is not None:
            result.append(f"允许主动消息: {'是' if allow_messages else '否'}")
        
        # 显示其他元数据信息
        for key, value in user_info.items():
            if key not in ["name", "first_seen", "last_active_time", "is_friend", 
                          "friend_add_time", "allow_active_messages"]:
                result.append(f"{key}: {value}")
        
        # 显示用户加入的群组
        if groups:
            result.append("\n加入的群组:")
            for group_id in groups[:5]:  # 只显示前5个
                group_info = stats_manager.get_group(group_id) or {}
                group_name = group_info.get("name", "未知群组")
                result.append(f"- {group_name}({group_id})")
            
            if len(groups) > 5:
                result.append(f"... 等共 {len(groups)} 个群组")
        
        # 添加最近的用户事件
        user_events = []
        for event_type in ["DIRECT_MESSAGE_CREATE", "GROUP_AT_MESSAGE_CREATE"]:
            events = stats_manager.get_events(event_type, limit=100)
            for event in events:
                data = event.get("data", {})
                if data.get("user_id") == user_id:
                    user_events.append((event.get("time", 0), event_type, event))
        
        # 取最近的5个用户事件
        user_events.sort(key=lambda x: x[0], reverse=True)
        if user_events[:5]:
            result.append("\n最近用户事件:")
            for _, event_type, event in user_events[:5]:
                event_time = event.get("timestamp", "未知")
                result.append(f"- {event_type} 于 {event_time}")
        
        return "\n".join(result)
    
    def _get_help_text(self, is_admin: bool) -> str:
        """获取帮助文本"""
        result = [
            "【统计插件帮助】",
            "用法: /stats [子命令] [参数]",
            "",
            "可用子命令:",
            "- summary: 显示统计摘要信息（默认）",
            "- groups: 显示群组统计信息",
            "- users: 显示用户统计信息",
            "- events: 显示事件统计信息"
        ]
        
        if is_admin:
            result.extend([
                "",
                "管理员专用命令:",
                "- group <群ID>: 显示特定群组的详细信息",
                "- user <用户ID>: 显示特定用户的详细信息",
                "- events <事件类型>: 显示特定类型事件的详情",
                "  例如: /stats events GROUP_ADD_ROBOT"
            ])
            
        return "\n".join(result) 