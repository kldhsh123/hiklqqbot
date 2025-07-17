"""
黑名单管理器
管理用户和群组黑名单，提供添加、删除、查询等功能
"""

import json
import logging
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, asdict
from enum import Enum
from config import ENABLE_BLACKLIST, BLACKLIST_AUTO_SAVE, BLACKLIST_LOG_BLOCKED

logger = logging.getLogger("blacklist_manager")

class BlacklistType(Enum):
    """黑名单类型"""
    USER = "user"
    GROUP = "group"

@dataclass
class BlacklistEntry:
    """黑名单条目"""
    id: str                    # 用户ID或群组ID
    type: BlacklistType        # 黑名单类型
    reason: str               # 加入黑名单的原因
    added_by: str             # 添加者ID
    added_time: str           # 添加时间
    expires_at: Optional[str] = None  # 过期时间（可选）
    
    def is_expired(self) -> bool:
        """检查是否已过期"""
        if not self.expires_at:
            return False
        try:
            from datetime import datetime
            expire_time = datetime.fromisoformat(self.expires_at)
            return datetime.now() > expire_time
        except:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['type'] = self.type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BlacklistEntry':
        """从字典创建"""
        data['type'] = BlacklistType(data['type'])
        return cls(**data)

class BlacklistManager:
    """黑名单管理器"""
    
    def __init__(self, data_file: str = "blacklist.json", auto_save: bool = None):
        self.data_file = data_file
        self.auto_save = auto_save if auto_save is not None else BLACKLIST_AUTO_SAVE
        self._lock = threading.RLock()
        self._blacklist: Dict[str, BlacklistEntry] = {}
        self._load_data()

        # 配置选项
        self.log_blocked = BLACKLIST_LOG_BLOCKED
        
    def _load_data(self):
        """加载黑名单数据"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for entry_data in data.get('blacklist', []):
                    try:
                        entry = BlacklistEntry.from_dict(entry_data)
                        self._blacklist[entry.id] = entry
                    except Exception as e:
                        logger.error(f"加载黑名单条目失败: {e}")
                        
                logger.info(f"已加载 {len(self._blacklist)} 个黑名单条目")
            else:
                logger.info("黑名单文件不存在，创建新的黑名单")
                self._save_data()
                
        except Exception as e:
            logger.error(f"加载黑名单数据失败: {e}")
            self._blacklist = {}
    
    def _save_data(self):
        """保存黑名单数据"""
        try:
            # 清理过期条目
            self._cleanup_expired()
            
            data = {
                'version': '1.0',
                'last_updated': datetime.now().isoformat(),
                'blacklist': [entry.to_dict() for entry in self._blacklist.values()]
            }
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"已保存 {len(self._blacklist)} 个黑名单条目")
            
        except Exception as e:
            logger.error(f"保存黑名单数据失败: {e}")
    
    def _cleanup_expired(self):
        """清理过期的黑名单条目"""
        expired_ids = []
        for entry_id, entry in self._blacklist.items():
            if entry.is_expired():
                expired_ids.append(entry_id)
        
        for entry_id in expired_ids:
            del self._blacklist[entry_id]
            logger.info(f"已清理过期黑名单条目: {entry_id}")
    
    def add_user(self, user_id: str, reason: str, added_by: str, expires_at: Optional[str] = None) -> bool:
        """添加用户到黑名单"""
        return self._add_entry(user_id, BlacklistType.USER, reason, added_by, expires_at)
    
    def add_group(self, group_id: str, reason: str, added_by: str, expires_at: Optional[str] = None) -> bool:
        """添加群组到黑名单"""
        return self._add_entry(group_id, BlacklistType.GROUP, reason, added_by, expires_at)
    
    def _add_entry(self, target_id: str, entry_type: BlacklistType, reason: str, added_by: str, expires_at: Optional[str] = None) -> bool:
        """添加黑名单条目"""
        with self._lock:
            if target_id in self._blacklist:
                logger.warning(f"{entry_type.value} {target_id} 已在黑名单中")
                return False
            
            entry = BlacklistEntry(
                id=target_id,
                type=entry_type,
                reason=reason,
                added_by=added_by,
                added_time=datetime.now().isoformat(),
                expires_at=expires_at
            )
            
            self._blacklist[target_id] = entry
            
            if self.auto_save:
                self._save_data()
            
            logger.info(f"已添加{entry_type.value}到黑名单: {target_id}, 原因: {reason}")
            return True
    
    def remove_user(self, user_id: str) -> bool:
        """从黑名单移除用户"""
        return self._remove_entry(user_id, BlacklistType.USER)
    
    def remove_group(self, group_id: str) -> bool:
        """从黑名单移除群组"""
        return self._remove_entry(group_id, BlacklistType.GROUP)
    
    def _remove_entry(self, target_id: str, entry_type: BlacklistType) -> bool:
        """移除黑名单条目"""
        with self._lock:
            if target_id not in self._blacklist:
                logger.warning(f"{entry_type.value} {target_id} 不在黑名单中")
                return False
            
            entry = self._blacklist[target_id]
            if entry.type != entry_type:
                logger.warning(f"类型不匹配: {target_id} 是 {entry.type.value}，不是 {entry_type.value}")
                return False
            
            del self._blacklist[target_id]
            
            if self.auto_save:
                self._save_data()
            
            logger.info(f"已从黑名单移除{entry_type.value}: {target_id}")
            return True
    
    def is_user_blocked(self, user_id: str) -> bool:
        """检查用户是否被屏蔽"""
        return self._is_blocked(user_id, BlacklistType.USER)
    
    def is_group_blocked(self, group_id: str) -> bool:
        """检查群组是否被屏蔽"""
        return self._is_blocked(group_id, BlacklistType.GROUP)
    
    def _is_blocked(self, target_id: str, entry_type: BlacklistType) -> bool:
        """检查是否被屏蔽"""
        with self._lock:
            if target_id not in self._blacklist:
                return False
            
            entry = self._blacklist[target_id]
            
            # 检查类型匹配
            if entry.type != entry_type:
                return False
            
            # 检查是否过期
            if entry.is_expired():
                # 自动清理过期条目
                del self._blacklist[target_id]
                if self.auto_save:
                    self._save_data()
                return False
            
            if self.log_blocked:
                logger.info(f"已阻止{entry_type.value}访问: {target_id}, 原因: {entry.reason}")
            
            return True
    
    def get_entry(self, target_id: str) -> Optional[BlacklistEntry]:
        """获取黑名单条目"""
        with self._lock:
            return self._blacklist.get(target_id)
    
    def list_users(self) -> List[BlacklistEntry]:
        """列出所有被屏蔽的用户"""
        return self._list_entries(BlacklistType.USER)
    
    def list_groups(self) -> List[BlacklistEntry]:
        """列出所有被屏蔽的群组"""
        return self._list_entries(BlacklistType.GROUP)
    
    def _list_entries(self, entry_type: BlacklistType) -> List[BlacklistEntry]:
        """列出指定类型的黑名单条目"""
        with self._lock:
            self._cleanup_expired()
            return [entry for entry in self._blacklist.values() if entry.type == entry_type]
    
    def get_stats(self) -> Dict[str, int]:
        """获取黑名单统计信息"""
        with self._lock:
            self._cleanup_expired()
            stats = {
                'total': len(self._blacklist),
                'users': len([e for e in self._blacklist.values() if e.type == BlacklistType.USER]),
                'groups': len([e for e in self._blacklist.values() if e.type == BlacklistType.GROUP]),
                'temporary': len([e for e in self._blacklist.values() if e.expires_at])
            }
            return stats
    
    def clear_all(self) -> int:
        """清空所有黑名单条目"""
        with self._lock:
            count = len(self._blacklist)
            self._blacklist.clear()
            
            if self.auto_save:
                self._save_data()
            
            logger.info(f"已清空所有黑名单条目，共 {count} 个")
            return count
    
    def save(self):
        """手动保存数据"""
        with self._lock:
            self._save_data()

# 创建全局实例
blacklist_manager = BlacklistManager()
