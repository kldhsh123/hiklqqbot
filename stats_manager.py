import json
import logging
import os
import time
import random
import string
from typing import Dict, List, Set, Optional, Tuple
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
        self.id_mappings_file = os.path.join(data_dir, "id_mappings.json")
        self.time_stats_file = os.path.join(data_dir, "time_stats.json")
        
        # 数据结构
        self.groups = {}  # {group_id: {"join_time": time, "members": [user_ids], ...}}
        self.users = {}   # {user_id: {"first_seen": time, ...}}
        self.usage_stats = {
            "commands": {},  # {command_name: count}
            "groups": {},    # {group_id: message_count}
            "users": {},     # {user_id: message_count}
            "total_messages": 0
        }
        
        # ID映射结构 - 新增
        self.id_mappings = {
            "users": {},  # {real_id: display_id}
            "groups": {}  # {real_id: display_id}
        }
        
        # 时间段统计结构 - 新增
        self.time_stats = {
            "daily": {},   # {date_str: {commands: {}, groups: {}, users: {}, total: 0}}
            "weekly": {},  # {week_str: {commands: {}, groups: {}, users: {}, total: 0}}
            "monthly": {}  # {month_str: {commands: {}, groups: {}, users: {}, total: 0}}
        }
        
        # 加载数据
        self._load_data()
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
            
            # 加载ID映射 - 新增
            if os.path.exists(self.id_mappings_file):
                with open(self.id_mappings_file, "r", encoding="utf-8") as f:
                    self.id_mappings = json.load(f)
            
            # 加载时间段统计 - 新增
            if os.path.exists(self.time_stats_file):
                with open(self.time_stats_file, "r", encoding="utf-8") as f:
                    self.time_stats = json.load(f)
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
            
            # 保存ID映射 - 新增
            with open(self.id_mappings_file, "w", encoding="utf-8") as f:
                json.dump(self.id_mappings, f, ensure_ascii=False, indent=2)
            
            # 保存时间段统计 - 新增
            with open(self.time_stats_file, "w", encoding="utf-8") as f:
                json.dump(self.time_stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存统计数据失败: {e}")
    
    # ID映射相关方法 - 新增
    def _generate_display_id(self, id_type: str) -> str:
        """生成唯一的展示ID"""
        prefix = "U" if id_type == "users" else "G"
        while True:
            # 生成6位数字ID
            random_id = ''.join(random.choices(string.digits, k=6))
            display_id = f"{prefix}{random_id}"
            
            # 确保ID不重复
            is_unique = True
            for real_id, disp_id in self.id_mappings[id_type].items():
                if disp_id == display_id:
                    is_unique = False
                    break
            
            if is_unique:
                return display_id
    
    def get_display_id(self, real_id: str, id_type: str) -> str:
        """获取展示ID，如果不存在则生成一个"""
        if id_type not in ["users", "groups"]:
            self.logger.error(f"无效的ID类型: {id_type}")
            return "未知ID"
        
        if real_id not in self.id_mappings[id_type]:
            display_id = self._generate_display_id(id_type)
            self.id_mappings[id_type][real_id] = display_id
            self._save_data()
            self.logger.debug(f"为{id_type[:-1]} {real_id} 生成展示ID: {display_id}")
            return display_id
        
        return self.id_mappings[id_type][real_id]
    
    def get_user_display_id(self, user_openid: str) -> str:
        """获取用户的展示ID"""
        return self.get_display_id(user_openid, "users")
    
    def get_group_display_id(self, group_openid: str) -> str:
        """获取群组的展示ID"""
        return self.get_display_id(group_openid, "groups")
    
    def get_real_id(self, display_id: str) -> Tuple[Optional[str], Optional[str]]:
        """通过展示ID查找真实ID
        
        Returns:
            Tuple[real_id, id_type]: 真实ID和类型("users"或"groups")
        """
        # 先检查用户映射
        for real_id, disp_id in self.id_mappings["users"].items():
            if disp_id == display_id:
                return real_id, "users"
        
        # 再检查群组映射
        for real_id, disp_id in self.id_mappings["groups"].items():
            if disp_id == display_id:
                return real_id, "groups"
        
        return None, None
    
    # 时间相关辅助方法 - 新增
    def _get_time_keys(self, timestamp: Optional[float] = None) -> Tuple[str, str, str]:
        """获取时间戳对应的日/周/月键名"""
        if timestamp is None:
            timestamp = time.time()
        
        dt = datetime.fromtimestamp(timestamp)
        
        # 日期格式：YYYY-MM-DD
        daily_key = dt.strftime("%Y-%m-%d")
        
        # 周格式：YYYY-WW (年-周数)
        weekly_key = f"{dt.year}-W{dt.strftime('%W')}"
        
        # 月份格式：YYYY-MM
        monthly_key = dt.strftime("%Y-%m")
        
        return daily_key, weekly_key, monthly_key
    
    def _ensure_time_stats_structure(self, time_key: str, time_type: str):
        """确保时间段统计结构存在"""
        if time_key not in self.time_stats[time_type]:
            self.time_stats[time_type][time_key] = {
                "commands": {},
                "groups": {},
                "users": {},
                "total": 0
            }
    
    # 群组相关方法
    def add_group(self, group_openid: str, name: str = None, op_member_openid: str = None):
        """添加或更新群组信息"""
        current_time = time.time()
        
        if group_openid not in self.groups:
            self.groups[group_openid] = {
                "join_time": current_time,
                "members": [],
                "last_active": current_time,
                "added_by": op_member_openid
            }
            self.logger.info(f"添加新群组: {group_openid}")
        else:
            self.groups[group_openid]["last_active"] = current_time
        
        # 确保群组有展示ID - 新增
        self.get_group_display_id(group_openid)
        
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
            # 更新群组的成员列表
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
        is_updated = False
        
        # 从群组的成员列表中移除用户
        if group_openid in self.groups and user_openid in self.groups[group_openid]["members"]:
            self.groups[group_openid]["members"].remove(user_openid)
            self.logger.debug(f"从群组 {group_openid} 移除用户 {user_openid}")
            is_updated = True
        
        # 从用户的群组列表中移除群组
        if user_openid in self.users and "groups" in self.users[user_openid]:
            if group_openid in self.users[user_openid]["groups"]:
                self.users[user_openid]["groups"].remove(group_openid)
                self.logger.debug(f"从用户 {user_openid} 的群组列表中移除群组 {group_openid}")
                is_updated = True
        
        if is_updated:
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
                "first_seen": current_time,
                "last_active": current_time,
                "groups": []
            }
            self.logger.info(f"添加新用户: {user_openid}")
        else:
            self.users[user_openid]["last_active"] = current_time
            if avatar:
                self.users[user_openid]["avatar"] = avatar
        
        # 确保用户有展示ID - 新增
        self.get_user_display_id(user_openid)
        
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
        current_time = time.time()
        
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
        
        # 更新时间段统计 - 新增
        daily_key, weekly_key, monthly_key = self._get_time_keys(current_time)
        
        # 更新日统计
        self._ensure_time_stats_structure(daily_key, "daily")
        daily_stats = self.time_stats["daily"][daily_key]
        
        if command not in daily_stats["commands"]:
            daily_stats["commands"][command] = 0
        daily_stats["commands"][command] += 1
        
        if user_openid:
            if user_openid not in daily_stats["users"]:
                daily_stats["users"][user_openid] = 0
            daily_stats["users"][user_openid] += 1
        
        if group_openid:
            if group_openid not in daily_stats["groups"]:
                daily_stats["groups"][group_openid] = 0
            daily_stats["groups"][group_openid] += 1
        
        daily_stats["total"] += 1
        
        # 更新周统计
        self._ensure_time_stats_structure(weekly_key, "weekly")
        weekly_stats = self.time_stats["weekly"][weekly_key]
        
        if command not in weekly_stats["commands"]:
            weekly_stats["commands"][command] = 0
        weekly_stats["commands"][command] += 1
        
        if user_openid:
            if user_openid not in weekly_stats["users"]:
                weekly_stats["users"][user_openid] = 0
            weekly_stats["users"][user_openid] += 1
        
        if group_openid:
            if group_openid not in weekly_stats["groups"]:
                weekly_stats["groups"][group_openid] = 0
            weekly_stats["groups"][group_openid] += 1
        
        weekly_stats["total"] += 1
        
        # 更新月统计
        self._ensure_time_stats_structure(monthly_key, "monthly")
        monthly_stats = self.time_stats["monthly"][monthly_key]
        
        if command not in monthly_stats["commands"]:
            monthly_stats["commands"][command] = 0
        monthly_stats["commands"][command] += 1
        
        if user_openid:
            if user_openid not in monthly_stats["users"]:
                monthly_stats["users"][user_openid] = 0
            monthly_stats["users"][user_openid] += 1
        
        if group_openid:
            if group_openid not in monthly_stats["groups"]:
                monthly_stats["groups"][group_openid] = 0
            monthly_stats["groups"][group_openid] += 1
        
        monthly_stats["total"] += 1
        
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
    
    # 时间段统计方法 - 新增
    def get_daily_stats(self, date_str: Optional[str] = None) -> dict:
        """获取指定日期的统计数据，默认为今天"""
        if date_str is None:
            date_str, _, _ = self._get_time_keys()
        
        return self.time_stats["daily"].get(date_str, {
            "commands": {},
            "groups": {},
            "users": {},
            "total": 0
        })
    
    def get_weekly_stats(self, week_str: Optional[str] = None) -> dict:
        """获取指定周的统计数据，默认为本周"""
        if week_str is None:
            _, week_str, _ = self._get_time_keys()
        
        return self.time_stats["weekly"].get(week_str, {
            "commands": {},
            "groups": {},
            "users": {},
            "total": 0
        })
    
    def get_monthly_stats(self, month_str: Optional[str] = None) -> dict:
        """获取指定月的统计数据，默认为本月"""
        if month_str is None:
            _, _, month_str = self._get_time_keys()
        
        return self.time_stats["monthly"].get(month_str, {
            "commands": {},
            "groups": {},
            "users": {},
            "total": 0
        })
    
    # 事件响应方法
    def handle_group_add_robot(self, group_openid: str, op_member_openid: str, timestamp: int):
        """处理机器人加入群聊事件"""
        # 添加或更新群组信息
        self.add_group(group_openid, op_member_openid=op_member_openid)
        
        # 如果有操作者信息，添加该用户并建立用户-群组关联
        if op_member_openid:
            # 添加用户
            self.add_user(op_member_openid)
            
            # 建立双向关联
            self.add_user_to_group(group_openid, op_member_openid)
        
        return True
    
    def handle_group_del_robot(self, group_openid: str, op_member_openid: str, timestamp: int):
        """处理机器人退出群聊事件"""
        return self.remove_group(group_openid)
    
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