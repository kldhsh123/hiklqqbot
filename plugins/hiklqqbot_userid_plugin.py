from plugins.base_plugin import BasePlugin
import logging
from auth_manager import auth_manager
import base64
import uuid
import json
import os
import time
from typing import Dict, Any

class HiklqqbotUseridPlugin(BasePlugin):
    """
    用户ID查询插件，生成唯一标识符并记录用户信息
    """
    
    def __init__(self):
        super().__init__(
            command="hiklqqbot_userid", 
            description="获取您的唯一标识符", 
            is_builtin=True,
            hidden=False
        )
        self.logger = logging.getLogger("plugin.userid")
        
        # 确保数据目录存在
        self.data_dir = "data/user_records"
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 用户记录文件路径
        self.records_file = os.path.join(self.data_dir, "user_records.json")
        
        # 加载现有记录
        self.user_records = self._load_records()
        
    def _load_records(self) -> Dict[str, Any]:
        """加载用户记录"""
        if os.path.exists(self.records_file):
            try:
                with open(self.records_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"加载用户记录失败: {str(e)}")
        return {}
        
    def _save_records(self) -> bool:
        """保存用户记录"""
        try:
            with open(self.records_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_records, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"保存用户记录失败: {str(e)}")
            return False
            
    def _generate_unique_id(self) -> str:
        """生成唯一标识符"""
        # 生成UUID并取前12位作为标识符
        return str(uuid.uuid4())[:12]
    
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """
        处理userid命令，生成唯一标识符并记录用户信息
        
        Args:
            params: 命令参数（不使用）
            user_id: 用户ID
            group_openid: 群组ID
            **kwargs: 其他额外参数
            
        Returns:
            str: 唯一标识符信息
        """
        self.logger.info(f"收到userid命令，用户ID: {user_id}, 群组ID: {group_openid}")
        
        if not user_id:
            return "无法获取您的用户信息"
            
        # 解析参数
        params = params.strip()
        
        # 管理员查询功能
        if params.startswith("query") and auth_manager.is_admin(user_id):
            query_parts = params.split(maxsplit=1)
            if len(query_parts) < 2:
                return "请提供要查询的唯一标识符: hiklqqbot_userid query <唯一标识符>"
                
            query_id = query_parts[1].strip()
            
            # 查询记录
            if query_id in self.user_records:
                record = self.user_records[query_id]
                response = f"标识符 {query_id} 的信息:\n"
                response += f"用户ID: {record['user_id']}\n"
                response += f"群组ID: {record['group_id']}\n"
                response += f"记录时间: {record['date_time']}"
                return response
            else:
                return f"未找到标识符为 {query_id} 的记录"
                
        # 管理员列出最近记录
        elif params == "list" and auth_manager.is_admin(user_id):
            # 获取最近的10条记录
            recent_records = sorted(
                self.user_records.values(), 
                key=lambda x: x.get('timestamp', 0), 
                reverse=True
            )[:10]
            
            if not recent_records:
                return "没有找到任何记录"
                
            response = "最近的10条用户记录:\n"
            for idx, record in enumerate(recent_records, 1):
                response += f"{idx}. 标识符: {record['unique_id']} | 时间: {record['date_time']}\n"
            
            response += "\n可使用 'hiklqqbot_userid query <标识符>' 查询详细信息"
            return response
            
        # 管理员帮助
        elif params == "help" and auth_manager.is_admin(user_id):
            return """hiklqqbot_userid 命令帮助:
- hiklqqbot_userid: 生成并获取您的唯一标识符
- hiklqqbot_userid query <标识符>: (管理员) 查询指定标识符的用户信息
- hiklqqbot_userid list: (管理员) 列出最近10条记录
- hiklqqbot_userid help: 显示此帮助信息"""
        
        # 普通用户帮助
        elif params == "help":
            return """hiklqqbot_userid 命令帮助:
- hiklqqbot_userid: 生成并获取您的唯一标识符
- hiklqqbot_userid help: 显示此帮助信息"""
        
        # 生成唯一标识符
        unique_id = self._generate_unique_id()
        
        # 记录用户信息
        record = {
            "user_id": user_id,
            "group_id": group_openid if group_openid else "",
            "timestamp": int(time.time()),
            "date_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "unique_id": unique_id
        }
        
        # 添加到记录中
        self.user_records[unique_id] = record
        
        # 保存记录
        if self._save_records():
            self.logger.info(f"已记录用户 {user_id} 的信息，唯一标识符: {unique_id}")
        else:
            self.logger.warning(f"记录用户 {user_id} 的信息失败")
        
        # 返回唯一标识符
        response = f"您的唯一标识符是: {unique_id}"
        response += "\n该标识符已与您的账号关联，请妥善保管"
        
        return response 