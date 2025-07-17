"""
增强的消息类型定义
支持botpy消息对象和现有框架消息格式的统一处理
"""

import logging
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("enhanced_message_types")

class MessageType(Enum):
    """消息类型枚举"""
    TEXT = 0
    IMAGE = 1
    MARKDOWN = 2
    ARK = 3
    EMBED = 4
    FILE = 7
    MEDIA = 7  # 富媒体，与FILE相同

class EventType(Enum):
    """事件类型枚举"""
    # 消息事件
    AT_MESSAGE_CREATE = "AT_MESSAGE_CREATE"
    DIRECT_MESSAGE_CREATE = "DIRECT_MESSAGE_CREATE"
    GROUP_AT_MESSAGE_CREATE = "GROUP_AT_MESSAGE_CREATE"
    C2C_MESSAGE_CREATE = "C2C_MESSAGE_CREATE"
    
    # 系统事件
    READY = "READY"
    RESUMED = "RESUMED"
    
    # 群组管理事件
    GROUP_ADD_ROBOT = "GROUP_ADD_ROBOT"
    GROUP_DEL_ROBOT = "GROUP_DEL_ROBOT"
    GROUP_MSG_REJECT = "GROUP_MSG_REJECT"
    GROUP_MSG_RECEIVE = "GROUP_MSG_RECEIVE"
    
    # 用户管理事件
    FRIEND_ADD = "FRIEND_ADD"
    FRIEND_DEL = "FRIEND_DEL"
    C2C_MSG_REJECT = "C2C_MSG_REJECT"
    C2C_MSG_RECEIVE = "C2C_MSG_RECEIVE"

@dataclass
class EnhancedUser:
    """增强的用户信息"""
    id: Optional[str] = None
    username: Optional[str] = None
    avatar: Optional[str] = None
    bot: Optional[bool] = None
    openid: Optional[str] = None
    user_openid: Optional[str] = None
    member_openid: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedUser':
        """从字典创建用户对象"""
        return cls(
            id=data.get("id"),
            username=data.get("username"),
            avatar=data.get("avatar"),
            bot=data.get("bot"),
            openid=data.get("openid"),
            user_openid=data.get("user_openid"),
            member_openid=data.get("member_openid")
        )
    
    def get_user_id(self) -> Optional[str]:
        """获取用户ID，优先级：id > user_openid > member_openid > openid"""
        return self.id or self.user_openid or self.member_openid or self.openid

@dataclass
class EnhancedMessage:
    """增强的消息对象"""
    id: Optional[str] = None
    content: Optional[str] = None
    author: Optional[EnhancedUser] = None
    channel_id: Optional[str] = None
    guild_id: Optional[str] = None
    group_openid: Optional[str] = None
    timestamp: Optional[str] = None
    event_type: Optional[EventType] = None
    message_type: Optional[MessageType] = None
    attachments: Optional[list] = None
    mentions: Optional[list] = None
    
    @classmethod
    def from_event_data(cls, event_data: Dict[str, Any], event_type: str) -> 'EnhancedMessage':
        """从事件数据创建消息对象"""
        author_data = event_data.get("author", {})
        author = EnhancedUser.from_dict(author_data) if author_data else None
        
        return cls(
            id=event_data.get("id"),
            content=event_data.get("content"),
            author=author,
            channel_id=event_data.get("channel_id"),
            guild_id=event_data.get("guild_id"),
            group_openid=event_data.get("group_openid"),
            timestamp=event_data.get("timestamp"),
            event_type=EventType(event_type) if event_type in [e.value for e in EventType] else None,
            message_type=MessageType(event_data.get("msg_type", 0)),
            attachments=event_data.get("attachments", []),
            mentions=event_data.get("mentions", [])
        )
    
    def is_group_message(self) -> bool:
        """判断是否为群聊消息"""
        return self.group_openid is not None
    
    def is_private_message(self) -> bool:
        """判断是否为私聊消息"""
        return self.event_type in [EventType.DIRECT_MESSAGE_CREATE, EventType.C2C_MESSAGE_CREATE]
    
    def is_at_message(self) -> bool:
        """判断是否为@消息"""
        return self.event_type in [EventType.AT_MESSAGE_CREATE, EventType.GROUP_AT_MESSAGE_CREATE]
    
    def get_reply_target(self) -> tuple[Optional[str], bool]:
        """获取回复目标，返回(target_id, is_group)"""
        if self.group_openid:
            return self.group_openid, True
        elif self.channel_id:
            return self.channel_id, False
        elif self.author and self.author.get_user_id():
            return self.author.get_user_id(), False
        return None, False

class MessageBuilder:
    """增强的消息构建器"""
    
    @staticmethod
    def build_text_message(content: str) -> Dict[str, Any]:
        """构建文本消息"""
        return {
            "content": content,
            "msg_type": MessageType.TEXT.value
        }
    
    @staticmethod
    def build_markdown_message(content: str, markdown: Dict[str, Any]) -> Dict[str, Any]:
        """构建Markdown消息"""
        return {
            "content": content,
            "msg_type": MessageType.MARKDOWN.value,
            "markdown": markdown
        }
    
    @staticmethod
    def build_image_message(url: str) -> Dict[str, Any]:
        """构建图片消息"""
        return {
            "msg_type": MessageType.IMAGE.value,
            "image": url
        }
    
    @staticmethod
    def build_file_message(file_info: Dict[str, Any]) -> Dict[str, Any]:
        """构建文件消息"""
        return {
            "msg_type": MessageType.FILE.value,
            "media": file_info
        }
    
    @staticmethod
    def build_keyboard_message(content: str, keyboard: Dict[str, Any]) -> Dict[str, Any]:
        """构建带按钮的消息"""
        return {
            "content": content,
            "msg_type": MessageType.TEXT.value,
            "keyboard": keyboard
        }
    
    @staticmethod
    def build_ark_message(ark: Dict[str, Any]) -> Dict[str, Any]:
        """构建ARK消息"""
        return {
            "msg_type": MessageType.ARK.value,
            "ark": ark
        }

class EventDataNormalizer:
    """事件数据标准化器"""
    
    @staticmethod
    def normalize_event_data(event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化事件数据格式"""
        normalized = event_data.copy()
        normalized["type"] = event_type
        
        # 标准化用户信息
        if "author" in normalized:
            author = normalized["author"]
            if isinstance(author, dict):
                # 确保用户信息包含所有可能的ID字段
                user_id = author.get("id") or author.get("user_openid") or author.get("member_openid") or author.get("openid")
                if user_id and "id" not in author:
                    author["id"] = user_id
        
        # 标准化时间戳
        if "timestamp" in normalized and normalized["timestamp"]:
            # 确保时间戳格式一致
            pass
        
        return normalized
    
    @staticmethod
    def extract_user_id(event_data: Dict[str, Any]) -> Optional[str]:
        """从事件数据中提取用户ID"""
        author = event_data.get("author", {})
        user_id = author.get("id")
        if not user_id:
            user_id = author.get("openid")
        if not user_id:
            user_id = author.get("user_openid")
        if not user_id:
            user_id = author.get("member_openid")
        if not user_id:
            user_id = event_data.get("user", {}).get("openid")
        if not user_id:
            user_id = event_data.get("openid")
        return user_id
    
    @staticmethod
    def extract_target_info(event_data: Dict[str, Any]) -> tuple[Optional[str], bool]:
        """从事件数据中提取目标信息，返回(target_id, is_group)"""
        if "group_openid" in event_data:
            return event_data["group_openid"], True
        if "channel_id" in event_data:
            return event_data["channel_id"], False
        
        # 对于私聊消息，使用用户ID作为目标
        user_id = EventDataNormalizer.extract_user_id(event_data)
        if user_id:
            return user_id, False
        
        return None, False

# 导出的工具函数
def create_enhanced_message(event_data: Dict[str, Any], event_type: str) -> EnhancedMessage:
    """创建增强消息对象"""
    return EnhancedMessage.from_event_data(event_data, event_type)

def normalize_event(event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """标准化事件数据"""
    return EventDataNormalizer.normalize_event_data(event_type, event_data)

def extract_user_id(event_data: Dict[str, Any]) -> Optional[str]:
    """提取用户ID"""
    return EventDataNormalizer.extract_user_id(event_data)

def extract_target_info(event_data: Dict[str, Any]) -> tuple[Optional[str], bool]:
    """提取目标信息"""
    return EventDataNormalizer.extract_target_info(event_data)
