import json
import logging
import os
import time
from typing import Dict, List, Set, Optional
from datetime import datetime

class StatsManager:
    """
    统计管理器：记录和管理机器人的统计数据
    包括群组、用户、消息等信息
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(StatsManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self, data_dir: str = "data"):
        if self.initialized:
            return
            
        self.logger = logging.getLogger("stats_manager")
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        self.groups_file = os.path.join(data_dir, "groups.json")
        self.users_file = os.path.join(data_dir, "users.json")
        self.stats_file = os.path.join(data_dir, "usage_stats.json")
        
        # 数据结构
        self.groups = {}  # {group_id: {"name": name, "join_time": time, "members": [user_ids], ...}}
        self.users = {}   # {user_id: {"name": name, "avatar": url, "first_seen": time, ...}}
        self.usage_stats = {
            "commands": {},  # {command_name: count}
            "groups": {},    # {group_id: message_count}
            "users": {},     # {user_id: message_count}
            "total_messages": 0
        }
        
        # 加载数据
        self._load_data()
        
        # 同步用户和群组数据
        self._sync_group_user_data()
        
        self.initialized = True
        
    def _load_data(self):
        """从文件加载数据"""
        try:
            if os.path.exists(self.groups_file):
                with open(self.groups_file, "r", encoding="utf-8") as f:
                    self.groups = json.load(f)
            
            if os.path.exists(self.users_file):
                with open(self.users_file, "r", encoding="utf-8") as f:
                    self.users = json.load(f)
                    
            if os.path.exists(self.stats_file):
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    self.usage_stats = json.load(f)
        except Exception as e:
            self.logger.error(f"加载统计数据失败: {e}")
    
    def _save_data(self):
        """保存数据到文件"""
        try:
            with open(self.groups_file, "w", encoding="utf-8") as f:
                json.dump(self.groups, f, ensure_ascii=False, indent=2)
            
            with open(self.users_file, "w", encoding="utf-8") as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
                
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(self.usage_stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存统计数据失败: {e}")
    
    def _sync_group_user_data(self):
        """同步群组成员和用户群组列表数据"""
        self.logger.info("开始同步群组和用户数据...")
        changes_made = False
        
        # 遍历所有群组
        for group_id, group_info in self.groups.items():
            members = group_info.get("members", [])
            
            # 遍历每个群组的成员
            for member_id in members:
                if member_id in self.users:
                    # 确保用户有groups字段
                    if "groups" not in self.users[member_id]:
                        self.users[member_id]["groups"] = []
                    
                    # 将群组添加到用户的groups列表（如果不存在）
                    if group_id not in self.users[member_id]["groups"]:
                        self.users[member_id]["groups"].append(group_id)
                        self.logger.debug(f"将群组 {group_id} 添加到用户 {member_id} 的群组列表")
                        changes_made = True
        
        # 遍历所有用户
        for user_id, user_info in self.users.items():
            user_groups = user_info.get("groups", [])
            
            # 确保所有用户都有groups字段
            if "groups" not in user_info:
                user_info["groups"] = []
                changes_made = True
            
            # 遍历用户的每个群组
            for group_id in list(user_groups):  # 使用列表副本，因为可能会在循环中修改
                # 检查群组是否存在
                if group_id not in self.groups:
                    # 如果群组不存在，从用户的groups列表中移除
                    user_info["groups"].remove(group_id)
                    self.logger.debug(f"从用户 {user_id} 的群组列表中移除不存在的群组 {group_id}")
                    changes_made = True
                    continue
                
                # 检查用户是否在群组的成员列表中
                if user_id not in self.groups[group_id].get("members", []):
                    # 如果用户不在群组的成员列表中，将其添加
                    if "members" not in self.groups[group_id]:
                        self.groups[group_id]["members"] = []
                    self.groups[group_id]["members"].append(user_id)
                    self.logger.debug(f"将用户 {user_id} 添加到群组 {group_id} 的成员列表")
                    changes_made = True
        
        if changes_made:
            self.logger.info("数据同步完成，发现并修复了不一致")
            self._save_data()
        else:
            self.logger.info("数据同步完成，未发现不一致")
    
    # 群组相关方法
    def add_group(self, group_openid: str, name: str = None, op_member_openid: str = None):
        """添加或更新群组信息"""
        current_time = time.time()
        
        if group_openid not in self.groups:
            self.groups[group_openid] = {
                "name": name or "群组",
                "join_time": current_time,
                "members": [],
                "last_active": current_time,
                "added_by": op_member_openid
            }
            self.logger.info(f"添加新群组: {group_openid}")
        else:
            self.groups[group_openid]["last_active"] = current_time
            if name:
                self.groups[group_openid]["name"] = name
        
        self._save_data()
        return self.groups[group_openid]
    
    def remove_group(self, group_openid: str):
        """移除群组"""
        if group_openid in self.groups:
            del self.groups[group_openid]
            self.logger.info(f"移除群组: {group_openid}")
            self._save_data()
            return True
        return False
    
    def get_group(self, group_openid: str) -> Optional[dict]:
        """获取群组信息"""
        return self.groups.get(group_openid)
    
    def get_all_groups(self) -> Dict[str, dict]:
        """获取所有群组信息"""
        return self.groups
    
    def add_user_to_group(self, group_openid: str, user_openid: str):
        """将用户添加到群组成员列表"""
        if group_openid in self.groups:
            if user_openid not in self.groups[group_openid]["members"]:
                self.groups[group_openid]["members"].append(user_openid)
                self.logger.debug(f"将用户 {user_openid} 添加到群组 {group_openid}")
                
                # 同时更新用户的群组列表
                if user_openid in self.users:
                    if "groups" not in self.users[user_openid]:
                        self.users[user_openid]["groups"] = []
                    if group_openid not in self.users[user_openid]["groups"]:
                        self.users[user_openid]["groups"].append(group_openid)
                        self.logger.debug(f"将群组 {group_openid} 添加到用户 {user_openid} 的群组列表")
                
                self._save_data()
                return True
        return False
    
    def remove_user_from_group(self, group_openid: str, user_openid: str):
        """从群组成员列表中移除用户"""
        if group_openid in self.groups and user_openid in self.groups[group_openid]["members"]:
            self.groups[group_openid]["members"].remove(user_openid)
            self.logger.debug(f"从群组 {group_openid} 移除用户 {user_openid}")
            
            # 同时从用户的群组列表中移除该群组
            if user_openid in self.users and "groups" in self.users[user_openid]:
                if group_openid in self.users[user_openid]["groups"]:
                    self.users[user_openid]["groups"].remove(group_openid)
                    self.logger.debug(f"从用户 {user_openid} 的群组列表中移除群组 {group_openid}")
            
            self._save_data()
            return True
        return False
    
    def get_group_members(self, group_openid: str) -> List[str]:
        """获取群组所有成员ID"""
        if group_openid in self.groups:
            return self.groups[group_openid]["members"]
        return []
    
    # 用户相关方法
    def add_user(self, user_openid: str, name: str = None, avatar: str = None):
        """添加或更新用户信息"""
        current_time = time.time()
        
        if user_openid not in self.users:
            self.users[user_openid] = {
                "name": name or "用户",
                "avatar": avatar,
                "first_seen": current_time,
                "last_active": current_time,
                "groups": []
            }
            self.logger.info(f"添加新用户: {user_openid}")
        else:
            self.users[user_openid]["last_active"] = current_time
            if name:
                self.users[user_openid]["name"] = name
            if avatar:
                self.users[user_openid]["avatar"] = avatar
            # 确保用户有groups字段
            if "groups" not in self.users[user_openid]:
                self.users[user_openid]["groups"] = []
        
        self._save_data()
        return self.users[user_openid]
    
    def get_user(self, user_openid: str) -> Optional[dict]:
        """获取用户信息"""
        return self.users.get(user_openid)
    
    def get_all_users(self) -> Dict[str, dict]:
        """获取所有用户信息"""
        return self.users
    
    def update_user_avatar(self, user_openid: str, avatar_url: str):
        """更新用户头像"""
        if user_openid in self.users:
            self.users[user_openid]["avatar"] = avatar_url
            self._save_data()
            return True
        return False
    
    # 统计相关方法
    def log_command(self, command: str, user_openid: str = None, group_openid: str = None):
        """记录命令使用"""
        # 更新命令计数
        if command not in self.usage_stats["commands"]:
            self.usage_stats["commands"][command] = 0
        self.usage_stats["commands"][command] += 1
        
        # 更新用户和群组活跃度
        if user_openid:
            if user_openid not in self.usage_stats["users"]:
                self.usage_stats["users"][user_openid] = 0
            self.usage_stats["users"][user_openid] += 1
            
        if group_openid:
            if group_openid not in self.usage_stats["groups"]:
                self.usage_stats["groups"][group_openid] = 0
            self.usage_stats["groups"][group_openid] += 1
        
        self.usage_stats["total_messages"] += 1
        self._save_data()
    
    def get_command_stats(self) -> Dict[str, int]:
        """获取命令使用统计"""
        return self.usage_stats["commands"]
    
    def get_most_active_groups(self, limit: int = 10) -> List[tuple]:
        """获取最活跃的群组"""
        groups = [(gid, count) for gid, count in self.usage_stats["groups"].items()]
        return sorted(groups, key=lambda x: x[1], reverse=True)[:limit]
    
    def get_most_active_users(self, limit: int = 10) -> List[tuple]:
        """获取最活跃的用户"""
        users = [(uid, count) for uid, count in self.usage_stats["users"].items()]
        return sorted(users, key=lambda x: x[1], reverse=True)[:limit]
    
    # 事件响应方法
    def handle_group_add_robot(self, group_openid: str, op_member_openid: str, timestamp: int):
        """处理机器人加入群聊事件"""
        self.add_group(group_openid, op_member_openid=op_member_openid)
        if op_member_openid:
            self.add_user(op_member_openid)
            self.add_user_to_group(group_openid, op_member_openid)
        return True
    
    def handle_group_del_robot(self, group_openid: str, op_member_openid: str, timestamp: int):
        """处理机器人退出群聊事件"""
        # 获取群组成员，然后再移除群组
        members = self.get_group_members(group_openid).copy() if group_openid in self.groups else []
        
        # 从所有群成员的群组列表中移除该群组
        for member_id in members:
            if member_id in self.users and "groups" in self.users[member_id]:
                if group_openid in self.users[member_id]["groups"]:
                    self.users[member_id]["groups"].remove(group_openid)
                    self.logger.debug(f"从用户 {member_id} 的群组列表中移除群组 {group_openid}")
        
        # 移除群组
        if group_openid in self.groups:
            del self.groups[group_openid]
            self.logger.info(f"移除群组: {group_openid}")
            self._save_data()
            return True
        return False
    
    def handle_friend_add(self, user_openid: str, timestamp: int):
        """处理用户添加机器人事件"""
        self.add_user(user_openid)
        return True
    
    def handle_friend_del(self, user_openid: str, timestamp: int):
        """处理用户删除机器人事件"""
        if user_openid in self.users:
            # 不完全删除用户数据，只标记状态
            self.users[user_openid]["is_friend"] = False
            self._save_data()
            return True
        return False

# 创建全局实例
stats_manager = StatsManager() 