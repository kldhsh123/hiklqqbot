"""
Botpy SDK集成适配器
提供botpy客户端与现有框架的集成支持
"""

import asyncio
import logging
import sys
import os
from typing import Optional, Dict, Any, List
from config import (
    BOT_APPID, BOT_APPSECRET, USE_BOTPY_CLIENT, 
    BOTPY_INTENTS, BOTPY_LOG_LEVEL, BOTPY_TIMEOUT, BOTPY_IS_SANDBOX
)

# 动态导入botpy模块
try:
    # 添加botpy路径到sys.path
    botpy_path = os.path.join(os.path.dirname(__file__), 'botpy')
    if botpy_path not in sys.path:
        sys.path.insert(0, botpy_path)
    
    import botpy
    from botpy import logging as botpy_logging
    from botpy.message import Message, DirectMessage, GroupMessage, C2CMessage
    from botpy.flags import Intents
    BOTPY_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Botpy SDK不可用: {e}")
    BOTPY_AVAILABLE = False
    botpy = None
    Message = DirectMessage = GroupMessage = C2CMessage = None
    Intents = None

logger = logging.getLogger("botpy_integration")

class BotpyEventAdapter:
    """Botpy事件适配器，将botpy事件转换为现有框架事件格式"""
    
    def __init__(self, event_handler):
        self.event_handler = event_handler
        
    def convert_message_to_event_data(self, message) -> Dict[str, Any]:
        """将botpy消息对象转换为现有框架的事件数据格式"""
        if isinstance(message, Message):
            # 频道消息
            return {
                "id": message.id,
                "content": message.content,
                "channel_id": message.channel_id,
                "guild_id": message.guild_id,
                "author": {
                    "id": message.author.id,
                    "username": message.author.username,
                    "avatar": message.author.avatar,
                    "bot": message.author.bot
                },
                "timestamp": message.timestamp,
                "type": "AT_MESSAGE_CREATE"
            }
        elif isinstance(message, DirectMessage):
            # 私聊消息
            return {
                "id": message.id,
                "content": message.content,
                "channel_id": message.channel_id,
                "guild_id": message.guild_id,
                "author": {
                    "id": message.author.id,
                    "username": message.author.username,
                    "avatar": message.author.avatar
                },
                "timestamp": message.timestamp,
                "type": "DIRECT_MESSAGE_CREATE"
            }
        elif isinstance(message, GroupMessage):
            # 群聊消息
            return {
                "id": message.id,
                "content": message.content,
                "group_openid": message.group_openid,
                "author": {
                    "member_openid": message.author.member_openid
                },
                "timestamp": message.timestamp,
                "type": "GROUP_AT_MESSAGE_CREATE"
            }
        elif isinstance(message, C2CMessage):
            # C2C消息
            return {
                "id": message.id,
                "content": message.content,
                "author": {
                    "user_openid": message.author.user_openid
                },
                "timestamp": message.timestamp,
                "type": "C2C_MESSAGE_CREATE"
            }
        else:
            logger.warning(f"未知的消息类型: {type(message)}")
            return {}

class BotpyClient(botpy.Client if BOTPY_AVAILABLE else object):
    """Botpy客户端适配器"""
    
    def __init__(self, event_handler):
        if not BOTPY_AVAILABLE:
            raise ImportError("Botpy SDK不可用，无法创建BotpyClient")
            
        # 解析intents配置
        intents = self._parse_intents(BOTPY_INTENTS)
        
        super().__init__(
            intents=intents,
            timeout=BOTPY_TIMEOUT,
            is_sandbox=BOTPY_IS_SANDBOX,
            log_level=getattr(logging, BOTPY_LOG_LEVEL.upper(), logging.INFO)
        )
        
        self.event_adapter = BotpyEventAdapter(event_handler)
        self.event_handler = event_handler
        
    def _parse_intents(self, intents_str: str) -> Intents:
        """解析intents配置字符串"""
        intents = Intents.none()
        
        intent_mapping = {
            'public_messages': 'public_messages',
            'public_guild_messages': 'public_guild_messages', 
            'guild_messages': 'guild_messages',
            'direct_message': 'direct_message',
            'guild_message_reactions': 'guild_message_reactions',
            'guilds': 'guilds',
            'guild_members': 'guild_members',
            'interaction': 'interaction',
            'message_audit': 'message_audit',
            'forums': 'forums',
            'audio_action': 'audio_action',
            'audio_or_live_channel_member': 'audio_or_live_channel_member',
            'open_forum_event': 'open_forum_event'
        }
        
        for intent_name in intents_str.split(','):
            intent_name = intent_name.strip()
            if intent_name in intent_mapping:
                setattr(intents, intent_mapping[intent_name], True)
                logger.info(f"启用intent: {intent_name}")
            else:
                logger.warning(f"未知的intent: {intent_name}")
                
        return intents
    
    async def on_ready(self):
        """机器人准备就绪"""
        logger.info(f"Botpy客户端已就绪: {self.robot.name}")
        await self.event_handler.handle_event("READY", {
            "robot": {
                "name": self.robot.name,
                "id": self.robot.id
            }
        })
    
    async def on_at_message_create(self, message: Message):
        """处理@消息"""
        event_data = self.event_adapter.convert_message_to_event_data(message)
        await self.event_handler.handle_event("AT_MESSAGE_CREATE", event_data)
    
    async def on_direct_message_create(self, message: DirectMessage):
        """处理私聊消息"""
        event_data = self.event_adapter.convert_message_to_event_data(message)
        await self.event_handler.handle_event("DIRECT_MESSAGE_CREATE", event_data)
    
    async def on_group_at_message_create(self, message: GroupMessage):
        """处理群聊@消息"""
        event_data = self.event_adapter.convert_message_to_event_data(message)
        await self.event_handler.handle_event("GROUP_AT_MESSAGE_CREATE", event_data)
    
    async def on_c2c_message_create(self, message: C2CMessage):
        """处理C2C消息"""
        event_data = self.event_adapter.convert_message_to_event_data(message)
        await self.event_handler.handle_event("C2C_MESSAGE_CREATE", event_data)
    
    # 群组管理事件
    async def on_group_add_robot(self, data):
        """机器人加入群聊"""
        await self.event_handler.handle_event("GROUP_ADD_ROBOT", data)
    
    async def on_group_del_robot(self, data):
        """机器人退出群聊"""
        await self.event_handler.handle_event("GROUP_DEL_ROBOT", data)
    
    async def on_group_msg_reject(self, data):
        """群聊拒绝机器人主动消息"""
        await self.event_handler.handle_event("GROUP_MSG_REJECT", data)
    
    async def on_group_msg_receive(self, data):
        """群聊接受机器人主动消息"""
        await self.event_handler.handle_event("GROUP_MSG_RECEIVE", data)
    
    # 用户管理事件
    async def on_friend_add(self, data):
        """用户添加机器人"""
        await self.event_handler.handle_event("FRIEND_ADD", data)
    
    async def on_friend_del(self, data):
        """用户删除机器人"""
        await self.event_handler.handle_event("FRIEND_DEL", data)
    
    async def on_c2c_msg_reject(self, data):
        """用户拒绝机器人主动消息"""
        await self.event_handler.handle_event("C2C_MSG_REJECT", data)
    
    async def on_c2c_msg_receive(self, data):
        """用户接受机器人主动消息"""
        await self.event_handler.handle_event("C2C_MSG_RECEIVE", data)

def create_botpy_client(event_handler):
    """创建botpy客户端实例"""
    if not BOTPY_AVAILABLE:
        raise ImportError("Botpy SDK不可用")
    
    if not USE_BOTPY_CLIENT:
        logger.info("Botpy客户端未启用")
        return None
        
    logger.info("创建Botpy客户端...")
    return BotpyClient(event_handler)

async def start_botpy_client(event_handler):
    """启动botpy客户端"""
    if not BOTPY_AVAILABLE:
        raise ImportError("Botpy SDK不可用")
        
    client = create_botpy_client(event_handler)
    if not client:
        return
        
    logger.info("启动Botpy客户端...")
    try:
        async with client:
            await client.start(BOT_APPID, BOT_APPSECRET)
    except Exception as e:
        logger.error(f"Botpy客户端运行失败: {e}")
        raise
