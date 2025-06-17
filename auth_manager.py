import os
import json
import logging
from typing import List, Set

logger = logging.getLogger("auth_manager")

class AuthManager:
    """
    权限管理系统，负责管理用户权限和维护模式
    """
    
    def __init__(self):
        self.admins: Set[str] = set()
        self.maintenance_mode = False
        self.auth_file = "admins.json"  # 管理员ID存储文件
        self.logger = logger
        self._load_admins()
    
    def _load_admins(self) -> None:
        """
        从文件加载管理员列表
        """
        try:
            if os.path.exists(self.auth_file):
                with open(self.auth_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.admins = set(data.get("admins", []))
                    self.logger.info(f"已加载 {len(self.admins)} 个管理员")
            else:
                self.logger.warning(f"管理员配置文件 {self.auth_file} 不存在，将使用空列表")
                # 创建空的管理员文件
                self._save_admins()
        except Exception as e:
            self.logger.error(f"加载管理员列表失败: {e}")
    
    def _save_admins(self) -> None:
        """
        保存管理员列表到文件
        """
        try:
            with open(self.auth_file, 'w', encoding='utf-8') as f:
                json.dump({"admins": list(self.admins)}, f, indent=2, ensure_ascii=False)
            self.logger.info(f"已保存 {len(self.admins)} 个管理员到文件")
        except Exception as e:
            self.logger.error(f"保存管理员列表失败: {e}")
    
    def reload_admins(self) -> None:
        """
        重新从文件加载管理员列表
        """
        self.logger.info("重新加载管理员列表...")
        self._load_admins()
        self.logger.info(f"管理员列表重新加载完成，共加载 {len(self.admins)} 个管理员")
    
    def add_admin(self, user_id: str) -> bool:
        """
        添加管理员
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否添加成功
        """
        if not user_id:
            return False
        
        if user_id in self.admins:
            return False
        
        self.admins.add(user_id)
        self._save_admins()
        return True
    
    def remove_admin(self, user_id: str) -> bool:
        """
        移除管理员
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否移除成功
        """
        if not user_id or user_id not in self.admins:
            return False
        
        self.admins.remove(user_id)
        self._save_admins()
        return True
    
    def is_admin(self, user_id: str) -> bool:
        """
        检查用户是否为管理员
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否为管理员
        """
        return user_id in self.admins
    
    def set_maintenance_mode(self, enabled: bool) -> None:
        """
        设置维护模式
        
        Args:
            enabled: 是否启用维护模式
        """
        self.maintenance_mode = enabled
        self.logger.info(f"维护模式已{'启用' if enabled else '禁用'}")
    
    def is_maintenance_mode(self) -> bool:
        """
        检查是否处于维护模式
        
        Returns:
            是否处于维护模式
        """
        return self.maintenance_mode
    
    def can_access(self, user_id: str) -> bool:
        """
        检查用户是否可以访问机器人
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否可以访问
        """
        # 如果是管理员，总是可以访问
        if self.is_admin(user_id):
            return True
        
        # 如果处于维护模式，只有管理员可以访问
        if self.maintenance_mode:
            return False
        
        # 不处于维护模式，所有用户都可以访问
        return True
    
    def get_admins(self) -> List[str]:
        """
        获取所有管理员ID
        
        Returns:
            管理员ID列表
        """
        return list(self.admins)

# 创建全局权限管理器实例
auth_manager = AuthManager() 