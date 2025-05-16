import json
import os
import logging
import time
import asyncio
from typing import Dict, List, Set, Optional, Any, Union
from datetime import datetime

logger = logging.getLogger("stats_manager")

class StatsManager:
    """
    统计管理器，记录机器人加入的群组、用户和每个群组的用户信息
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """单例模式获取实例"""
        if cls._instance is None:
            cls._instance = StatsManager()
        return cls._instance
    
    def __init__(self):
        """初始化统计管理器"""
        self.logger = logger
        self.logger.info("初始化统计管理器")
        
        # 数据目录
        self.data_dir = "data/stats"
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 数据文件路径
        self.groups_file = os.path.join(self.data_dir, "groups.json")
        self.users_file = os.path.join(self.data_dir, "users.json")
        self.group_users_file = os.path.join(self.data_dir, "group_users.json")
        self.events_file = os.path.join(self.data_dir, "events.json")
        
        # 初始化数据结构
        self.groups = {}  # {group_id: {"name": "群名", "join_time": timestamp, ...}}
        self.users = {}   # {user_id: {"name": "用户名", "first_seen": timestamp, ...}}
        self.group_users = {}  # {group_id: {user_id1, user_id2, ...}}
        self.events = []  # [{type: "事件类型", time: timestamp, data: {...}}]
        
        # 事件计数器
        self.event_counts = {}  # {event_type: count}
        
        # 加载数据
        self._load_data()
        
        # 初始化自动保存任务
        self._auto_save_task = None
        
        # 设置锁，防止并发写入
        self._lock = asyncio.Lock()
    
    def _load_data(self):
        """加载统计数据"""
        try:
            # 加载群组数据
            if os.path.exists(self.groups_file):
                with open(self.groups_file, 'r', encoding='utf-8') as f:
                    self.groups = json.load(f)
                self.logger.info(f"已加载 {len(self.groups)} 个群组数据")
            
            # 加载用户数据
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    self.users = json.load(f)
                self.logger.info(f"已加载 {len(self.users)} 个用户数据")
            
            # 加载群组用户关系数据
            if os.path.exists(self.group_users_file):
                with open(self.group_users_file, 'r', encoding='utf-8') as f:
                    # JSON不支持集合，需要转换回来
                    group_users_dict = json.load(f)
                    self.group_users = {group_id: set(users) for group_id, users in group_users_dict.items()}
                self.logger.info(f"已加载 {len(self.group_users)} 个群组的用户关系数据")
            
            # 加载事件数据
            if os.path.exists(self.events_file):
                with open(self.events_file, 'r', encoding='utf-8') as f:
                    self.events = json.load(f)
                self.logger.info(f"已加载 {len(self.events)} 条事件记录")
                
                # 更新事件计数
                for event in self.events:
                    event_type = event.get("type")
                    if event_type:
                        self.event_counts[event_type] = self.event_counts.get(event_type, 0) + 1
        
        except Exception as e:
            self.logger.error(f"加载统计数据失败: {e}")
    
    def _save_data(self):
        """保存统计数据"""
        try:
            # 保存群组数据
            with open(self.groups_file, 'w', encoding='utf-8') as f:
                json.dump(self.groups, f, ensure_ascii=False, indent=2)
            
            # 保存用户数据
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            
            # 保存群组用户关系数据（转换集合为列表）
            group_users_dict = {group_id: list(users) for group_id, users in self.group_users.items()}
            with open(self.group_users_file, 'w', encoding='utf-8') as f:
                json.dump(group_users_dict, f, ensure_ascii=False, indent=2)
            
            # 保存事件数据（只保留最近1000条）
            with open(self.events_file, 'w', encoding='utf-8') as f:
                json.dump(self.events[-1000:], f, ensure_ascii=False, indent=2)
            
            self.logger.info("已保存统计数据")
        
        except Exception as e:
            self.logger.error(f"保存统计数据失败: {e}")
    
    async def start_auto_save(self, interval: int = 300):
        """启动自动保存任务"""
        if self._auto_save_task is not None:
            self._auto_save_task.cancel()
        
        async def auto_save_loop():
            while True:
                await asyncio.sleep(interval)
                await self.save_data_async()
        
        self._auto_save_task = asyncio.create_task(auto_save_loop())
        self.logger.info(f"已启动自动保存任务，间隔 {interval} 秒")
    
    async def save_data_async(self):
        """异步保存数据"""
        async with self._lock:
            await asyncio.to_thread(self._save_data)
    
    async def add_group(self, group_id: str, group_name: Optional[str] = None, 
                       added_by: Optional[str] = None, metadata: Optional[Dict] = None):
        """
        添加或更新群组信息
        
        Args:
            group_id: 群组ID
            group_name: 群组名称
            added_by: 添加机器人的用户ID
            metadata: 其他元数据
        """
        async with self._lock:
            current_time = int(time.time())
            
            # 如果是新群组，记录添加时间
            if group_id not in self.groups:
                self.groups[group_id] = {
                    "join_time": current_time,
                    "last_active_time": current_time
                }
                
                # 记录事件
                await self.add_event("GROUP_ADD", {
                    "group_id": group_id,
                    "added_by": added_by
                })
            else:
                # 更新最后活跃时间
                self.groups[group_id]["last_active_time"] = current_time
            
            # 更新群组信息
            if group_name:
                self.groups[group_id]["name"] = group_name
            
            # 添加其他元数据
            if metadata:
                for key, value in metadata.items():
                    self.groups[group_id][key] = value
            
            # 确保群组在用户关系中存在
            if group_id not in self.group_users:
                self.group_users[group_id] = set()
            
            self.logger.info(f"已添加/更新群组 {group_id}")
    
    async def remove_group(self, group_id: str, reason: Optional[str] = None, 
                          removed_by: Optional[str] = None):
        """
        移除群组
        
        Args:
            group_id: 群组ID
            reason: 移除原因
            removed_by: 移除机器人的用户ID
        """
        async with self._lock:
            if group_id in self.groups:
                # 保留在历史记录中，但标记为已移除
                self.groups[group_id]["removed"] = True
                self.groups[group_id]["remove_time"] = int(time.time())
                if reason:
                    self.groups[group_id]["remove_reason"] = reason
                if removed_by:
                    self.groups[group_id]["removed_by"] = removed_by
                
                # 记录事件
                await self.add_event("GROUP_REMOVE", {
                    "group_id": group_id,
                    "reason": reason,
                    "removed_by": removed_by
                })
                
                self.logger.info(f"已标记群组 {group_id} 为已移除")
            else:
                self.logger.warning(f"尝试移除不存在的群组 {group_id}")
    
    async def add_user(self, user_id: str, user_name: Optional[str] = None, 
                      metadata: Optional[Dict] = None):
        """
        添加或更新用户信息
        
        Args:
            user_id: 用户ID
            user_name: 用户名
            metadata: 其他元数据
        """
        async with self._lock:
            current_time = int(time.time())
            
            # 如果是新用户，记录首次见到时间
            if user_id not in self.users:
                self.users[user_id] = {
                    "first_seen": current_time,
                    "last_active_time": current_time
                }
                
                # 记录事件
                await self.add_event("USER_ADD", {
                    "user_id": user_id
                })
            else:
                # 更新最后活跃时间
                self.users[user_id]["last_active_time"] = current_time
            
            # 更新用户信息
            if user_name:
                self.users[user_id]["name"] = user_name
            
            # 添加其他元数据
            if metadata:
                for key, value in metadata.items():
                    self.users[user_id][key] = value
            
            self.logger.info(f"已添加/更新用户 {user_id}")
    
    async def add_user_to_group(self, group_id: str, user_id: str):
        """
        将用户添加到群组
        
        Args:
            group_id: 群组ID
            user_id: 用户ID
        """
        async with self._lock:
            # 确保群组和用户都存在
            if group_id not in self.groups:
                await self.add_group(group_id)
            
            if user_id not in self.users:
                await self.add_user(user_id)
            
            # 确保群组在用户关系中存在
            if group_id not in self.group_users:
                self.group_users[group_id] = set()
            
            # 添加用户到群组
            if user_id not in self.group_users[group_id]:
                self.group_users[group_id].add(user_id)
                
                # 记录事件
                await self.add_event("USER_JOIN_GROUP", {
                    "group_id": group_id,
                    "user_id": user_id
                })
                
                self.logger.info(f"已将用户 {user_id} 添加到群组 {group_id}")
    
    async def remove_user_from_group(self, group_id: str, user_id: str):
        """
        从群组中移除用户
        
        Args:
            group_id: 群组ID
            user_id: 用户ID
        """
        async with self._lock:
            if group_id in self.group_users and user_id in self.group_users[group_id]:
                self.group_users[group_id].remove(user_id)
                
                # 记录事件
                await self.add_event("USER_LEAVE_GROUP", {
                    "group_id": group_id,
                    "user_id": user_id
                })
                
                self.logger.info(f"已从群组 {group_id} 移除用户 {user_id}")
            else:
                self.logger.warning(f"尝试从不存在的关系中移除用户 {user_id} (群组 {group_id})")
    
    async def add_event(self, event_type: str, event_data: Dict):
        """
        记录事件
        
        Args:
            event_type: 事件类型
            event_data: 事件数据
        """
        async with self._lock:
            current_time = int(time.time())
            
            # 创建事件记录
            event = {
                "type": event_type,
                "time": current_time,
                "timestamp": datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S'),
                "data": event_data
            }
            
            # 添加到事件列表
            self.events.append(event)
            
            # 更新事件计数
            self.event_counts[event_type] = self.event_counts.get(event_type, 0) + 1
            
            # 如果事件太多，裁剪一下
            if len(self.events) > 2000:
                self.events = self.events[-1000:]
            
            self.logger.info(f"已记录事件 {event_type}")
    
    # ======== 查询方法 ========
    
    def get_group(self, group_id: str) -> Optional[Dict]:
        """获取群组信息"""
        return self.groups.get(group_id)
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """获取用户信息"""
        return self.users.get(user_id)
    
    def get_group_users(self, group_id: str) -> List[str]:
        """获取群组中的用户列表"""
        return list(self.group_users.get(group_id, set()))
    
    def get_user_groups(self, user_id: str) -> List[str]:
        """获取用户所在的群组列表"""
        return [group_id for group_id, users in self.group_users.items() 
                if user_id in users]
    
    def get_all_groups(self) -> Dict[str, Dict]:
        """获取所有群组信息"""
        return self.groups
    
    def get_all_users(self) -> Dict[str, Dict]:
        """获取所有用户信息"""
        return self.users
    
    def get_active_groups(self) -> Dict[str, Dict]:
        """获取活跃的群组（未被移除的）"""
        return {group_id: info for group_id, info in self.groups.items()
                if not info.get("removed", False)}
    
    def get_events(self, event_type: Optional[str] = None, 
                  limit: int = 100) -> List[Dict]:
        """
        获取事件记录
        
        Args:
            event_type: 事件类型过滤，None表示所有类型
            limit: 返回的最大记录数量
            
        Returns:
            事件记录列表
        """
        if event_type:
            filtered_events = [e for e in self.events if e["type"] == event_type]
            return filtered_events[-limit:]
        else:
            return self.events[-limit:]
    
    def get_event_count(self, event_type: Optional[str] = None) -> Union[int, Dict[str, int]]:
        """
        获取事件计数
        
        Args:
            event_type: 事件类型，None表示返回所有类型的计数
            
        Returns:
            事件计数或计数字典
        """
        if event_type:
            return self.event_counts.get(event_type, 0)
        else:
            return self.event_counts.copy()
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """
        获取统计摘要
        
        Returns:
            统计摘要字典
        """
        active_groups = len(self.get_active_groups())
        total_groups = len(self.groups)
        total_users = len(self.users)
        
        # 计算过去7天内活跃的群组和用户
        seven_days_ago = int(time.time()) - 7 * 24 * 60 * 60
        active_groups_7d = sum(1 for info in self.groups.values() 
                             if info.get("last_active_time", 0) > seven_days_ago and 
                             not info.get("removed", False))
        active_users_7d = sum(1 for info in self.users.values() 
                            if info.get("last_active_time", 0) > seven_days_ago)
        
        return {
            "total_groups": total_groups,
            "active_groups": active_groups,
            "active_groups_7d": active_groups_7d,
            "total_users": total_users,
            "active_users_7d": active_users_7d,
            "events_total": sum(self.event_counts.values()),
            "event_counts": self.event_counts
        }

# 创建单例实例
stats_manager = StatsManager.get_instance() 