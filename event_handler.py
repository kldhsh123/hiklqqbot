import json
import logging
import re
from plugins.plugin_manager import plugin_manager
import asyncio
from message import MessageSender
from auth_manager import auth_manager

# 配置日志
logger = logging.getLogger("event_handler")

class EventHandler:
    """事件处理器"""
    
    def __init__(self):
        self.logger = logger
        # 注册事件处理方法的映射
        self.event_handlers = {
            "AT_MESSAGE_CREATE": self.handle_at_message,
            "DIRECT_MESSAGE_CREATE": self.handle_direct_message,
            "C2C_MESSAGE_CREATE": self.handle_c2c_message,
            "GROUP_AT_MESSAGE_CREATE": self.handle_group_at_message,
            "GROUP_MSG_REJECT": self.handle_group_msg_reject,
            "GROUP_MSG_RECEIVE": self.handle_group_msg_receive,
            "READY": self.handle_ready,
            "RESUMED": self.handle_resumed,
        }
    
    async def handle_event(self, event_type, event_data):
        """处理事件分发"""
        self.logger.info(f"收到事件: {event_type}")
        
        # 寻找对应的处理方法
        handler = self.event_handlers.get(event_type)
        if handler:
            try:
                return await handler(event_data)
            except Exception as e:
                self.logger.error(f"处理事件 {event_type} 时发生错误: {e}")
                return False
        else:
            self.logger.info(f"暂未支持的事件类型: {event_type}")
            return False
    
    def _get_user_id(self, data):
        """从事件数据中提取用户ID"""
        # 获取作者信息
        author = data.get("author", {})
        # 尝试获取ID
        user_id = author.get("id")
        
        # 如果没有找到，尝试其他可能的字段
        if not user_id:
            user_id = data.get("openid") or data.get("user", {}).get("openid")
        
        return user_id
    
    async def handle_at_message(self, data):
        """处理频道@消息"""
        self.logger.info(f"收到@消息: {data}")
        # 提取消息内容
        content = data.get("content", "")
        user_id = self._get_user_id(data)
        return await self._process_command(content, data, user_id)
    
    async def handle_direct_message(self, data):
        """处理私聊消息"""
        self.logger.info(f"收到私聊消息: {data}")
        # 提取消息内容
        content = data.get("content", "")
        user_id = self._get_user_id(data)
        return await self._process_command(content, data, user_id)
    
    async def handle_c2c_message(self, data):
        """处理单聊(C2C)消息"""
        self.logger.info(f"收到私聊消息: {data}")
        
        # 提取消息内容和发送者信息
        content = data.get("content", "")
        openid = data.get("author", {}).get("id") or data.get("openid")
        message_id = data.get("id")
        user_id = self._get_user_id(data)
        
        if not openid:
            self.logger.error("无法获取发送者openid，无法回复消息")
            return False
        
        # 处理命令并获取回复内容
        response = await self._process_command(content, data, user_id)
        
        # 发送回复
        if response:
            try:
                if message_id:
                    # 回复特定消息
                    MessageSender.reply_message(openid, message_id, "text", response, False)
                else:
                    # 直接发送消息
                    MessageSender.send_message(openid, "text", response, False)
                self.logger.info(f"已回复私聊消息: {response}")
            except Exception as e:
                self.logger.error(f"发送私聊回复失败: {e}")
        
        return response
    
    async def handle_group_at_message(self, data):
        """处理群聊@消息"""
        self.logger.info(f"收到群聊@消息: {data}")
        # 提取消息内容
        content = data.get("content", "")
        user_id = self._get_user_id(data)
        
        # 获取群ID和消息ID，用于回复
        group_openid = data.get("group_openid")
        message_id = data.get("id")
        
        # 处理命令并获取回复内容
        response = await self._process_command(content, data, user_id)
        
        # 如果有回复内容，发送到群聊
        if response and group_openid:
            try:
                # 发送消息回复
                MessageSender.reply_group_message(
                    group_openid, 
                    message_id, 
                    "text", 
                    response
                )
                self.logger.info(f"已回复群聊消息: {response}")
            except Exception as e:
                self.logger.error(f"发送群聊回复失败: {e}")
        
        return response
    
    async def handle_group_msg_reject(self, data):
        """处理群聊拒绝机器人主动消息事件"""
        self.logger.info(f"群聊拒绝机器人主动消息: {data}")
        return True
    
    async def handle_group_msg_receive(self, data):
        """处理群聊接受机器人主动消息事件"""
        self.logger.info(f"群聊接受机器人主动消息: {data}")
        return True
    
    async def handle_ready(self, data):
        """处理准备就绪事件"""
        self.logger.info(f"机器人就绪: {data}")
        return True
    
    async def handle_resumed(self, data):
        """处理恢复连接事件"""
        self.logger.info("连接已恢复")
        return True
    
    async def _process_command(self, content, data, user_id=None):
        """处理命令"""
        # 提取@消息中的实际命令内容 (移除@机器人的部分)
        clean_content = re.sub(r'<@!\d+>', '', content).strip()
        
        # 如果空消息，直接返回帮助信息
        if not clean_content:
            return plugin_manager.get_help()
        
        # 检查维护模式
        if auth_manager.is_maintenance_mode() and not auth_manager.is_admin(user_id):
            return "机器人当前处于维护模式，仅管理员可用"
        
        # 分割命令和参数
        parts = clean_content.strip().split(' ', 1)
        command = parts[0]
        params = parts[1] if len(parts) > 1 else ""
        
        # 检查命令格式，必须以/开头
        if not command.startswith('/'):
            return f"命令必须以/开头，例如: /{command}"
        
        # 处理命令
        try:
            # 提取群ID信息
            group_openid = data.get("group_openid")
            # 传递完整事件数据
            return await plugin_manager.handle_command(command, params, user_id, group_openid=group_openid, event_data=data)
        except Exception as e:
            self.logger.error(f"处理命令时出错: {e}")
            return f"处理命令时出错: {e}"

# 创建事件处理器实例
event_handler = EventHandler() 