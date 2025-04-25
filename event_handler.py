import json
import logging
import re
import os
from plugins.plugin_manager import plugin_manager
import asyncio
from message import MessageSender
from auth_manager import auth_manager

# 配置日志
logger = logging.getLogger("event_handler")

# 从环境变量读取配置
ENABLE_AI_CHAT = os.environ.get("ENABLE_AI_CHAT", "true").lower() == "true"
AI_CHAT_MENTION_TRIGGER = os.environ.get("AI_CHAT_MENTION_TRIGGER", "true").lower() == "true"
ENFORCE_COMMAND_PREFIX = os.environ.get("ENFORCE_COMMAND_PREFIX", "true").lower() == "true"

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
        
        # AI聊天插件实例（仅当功能启用时）
        self.ai_chat_plugin = None
        if ENABLE_AI_CHAT and AI_CHAT_MENTION_TRIGGER:
            try:
                # 先检查模块是否存在，避免导入不存在的模块
                import importlib.util
                spec = importlib.util.find_spec('plugins.hiklqqbot_ai_chat_plugin')
                if spec is not None:
                    # 模块存在，尝试导入
                    from plugins import hiklqqbot_ai_chat_plugin
                    
                    # 检查是否定义了AIChatPlugin并在__all__中导出
                    if hasattr(hiklqqbot_ai_chat_plugin, '__all__') and 'AIChatPlugin' in getattr(hiklqqbot_ai_chat_plugin, '__all__'):
                        if hasattr(hiklqqbot_ai_chat_plugin, 'AIChatPlugin'):
                            self.ai_chat_plugin = hiklqqbot_ai_chat_plugin.AIChatPlugin()
                            self.logger.info("已加载AI聊天插件，@机器人将触发AI对话")
                        else:
                            self.logger.info("AI聊天插件模块存在但未定义AIChatPlugin类")
                    else:
                        self.logger.info("AI聊天插件未在__all__中导出，不加载")
                else:
                    self.logger.info("未找到AI聊天插件模块，功能未启用")
            except Exception as e:
                self.logger.error(f"加载AI聊天插件失败: {e}")
    
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
        
        # 输出关键信息便于调试
        clean_content = re.sub(r'<@!\d+>', '', content).strip() 
        clean_content = re.sub(r'@[\w\u4e00-\u9fa5]+\s*', '', clean_content).strip()
        
        # 仅当AI功能开启时才尝试使用AI处理
        if ENABLE_AI_CHAT and AI_CHAT_MENTION_TRIGGER:
            self.logger.info(f"@消息处理前: 原始内容=[{content}], 清理后=[{clean_content}], AI插件状态={self.ai_chat_plugin is not None}")
            
            # 明确打印各个条件的判断结果
            is_content_valid = bool(clean_content)
            is_not_command = not clean_content.startswith('/')
            is_plugin_loaded = self.ai_chat_plugin is not None
            
            self.logger.info(f"AI启用=True, @触发=True, 前缀强制={ENFORCE_COMMAND_PREFIX}, 内容有效={is_content_valid}, 非命令={is_not_command}, 插件加载={is_plugin_loaded}")
            
            try:
                # 只要不是以/开头的消息，都当作AI聊天处理
                if clean_content and not clean_content.startswith('/'):
                    self.logger.info(f"使用AI聊天处理@消息: [{clean_content}]")
                    
                    # 如果插件未加载，尝试重新加载
                    if not self.ai_chat_plugin:
                        try:
                            # 先检查模块是否存在
                            import importlib.util
                            spec = importlib.util.find_spec('plugins.hiklqqbot_ai_chat_plugin')
                            if spec is not None:
                                # 模块存在，尝试导入
                                from plugins import hiklqqbot_ai_chat_plugin
                                
                                # 检查是否定义了AIChatPlugin并在__all__中导出
                                if hasattr(hiklqqbot_ai_chat_plugin, '__all__') and 'AIChatPlugin' in getattr(hiklqqbot_ai_chat_plugin, '__all__'):
                                    if hasattr(hiklqqbot_ai_chat_plugin, 'AIChatPlugin'):
                                        self.ai_chat_plugin = hiklqqbot_ai_chat_plugin.AIChatPlugin()
                                        self.logger.info("已重新加载AI聊天插件")
                                    else:
                                        self.logger.warning("AI聊天插件模块存在但未定义AIChatPlugin类")
                                else:
                                    self.logger.info("AI聊天插件未在__all__中导出，不加载")
                            else:
                                self.logger.info("未找到AI聊天插件模块，功能未启用")
                        except Exception as e:
                            self.logger.error(f"加载AI聊天插件失败: {e}")
                    
                    if self.ai_chat_plugin:
                        data["type"] = "AT_MESSAGE_CREATE"  # 确保事件类型正确
                        # 直接传入原始数据，让插件自己提取内容
                        response = await self.ai_chat_plugin.handle_at_message(data, user_id)
                        return response
                    else:
                        self.logger.error("AI聊天插件未加载，无法处理@聊天消息")
            except Exception as e:
                self.logger.error(f"AI聊天处理异常: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
        
        # 否则使用常规命令处理流程
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
        
        # 清理消息内容
        clean_content = re.sub(r'<@!\d+>', '', content).strip()
        clean_content = re.sub(r'@[\w\u4e00-\u9fa5]+\s*', '', clean_content).strip()
        
        # 仅当AI功能开启时才尝试使用AI处理
        if ENABLE_AI_CHAT and AI_CHAT_MENTION_TRIGGER:
            self.logger.info(f"群@消息处理前: 原始内容=[{content}], 清理后=[{clean_content}], AI插件状态={self.ai_chat_plugin is not None}")
            
            # 明确打印各个条件的判断结果
            is_content_valid = bool(clean_content)
            is_not_command = not clean_content.startswith('/')
            is_plugin_loaded = self.ai_chat_plugin is not None
            
            self.logger.info(f"AI启用=True, @触发=True, 前缀强制={ENFORCE_COMMAND_PREFIX}, 内容有效={is_content_valid}, 非命令={is_not_command}, 插件加载={is_plugin_loaded}")
            
            try:
                # 只要不是以/开头的消息，都当作AI聊天处理
                if clean_content and not clean_content.startswith('/'):
                    self.logger.info(f"使用AI聊天处理群@消息: [{clean_content}]")
                    
                    # 如果插件未加载，尝试重新加载
                    if not self.ai_chat_plugin:
                        try:
                            # 先检查模块是否存在
                            import importlib.util
                            spec = importlib.util.find_spec('plugins.hiklqqbot_ai_chat_plugin')
                            if spec is not None:
                                # 模块存在，尝试导入
                                from plugins import hiklqqbot_ai_chat_plugin
                                
                                # 检查是否定义了AIChatPlugin并在__all__中导出
                                if hasattr(hiklqqbot_ai_chat_plugin, '__all__') and 'AIChatPlugin' in getattr(hiklqqbot_ai_chat_plugin, '__all__'):
                                    if hasattr(hiklqqbot_ai_chat_plugin, 'AIChatPlugin'):
                                        self.ai_chat_plugin = hiklqqbot_ai_chat_plugin.AIChatPlugin()
                                        self.logger.info("已重新加载AI聊天插件")
                                    else:
                                        self.logger.warning("AI聊天插件模块存在但未定义AIChatPlugin类")
                                else:
                                    self.logger.info("AI聊天插件未在__all__中导出，不加载")
                            else:
                                self.logger.info("未找到AI聊天插件模块，功能未启用")
                        except Exception as e:
                            self.logger.error(f"加载AI聊天插件失败: {e}")
                    
                    if self.ai_chat_plugin:
                        # 将事件类型添加到数据中
                        data["type"] = "GROUP_AT_MESSAGE_CREATE"
                        # 直接传入原始数据，让插件自己提取内容
                        response = await self.ai_chat_plugin.handle_at_message(data, user_id)
                        
                        # 发送回复
                        if response and group_openid and message_id:
                            try:
                                MessageSender.reply_group_message(
                                    group_openid, 
                                    message_id, 
                                    "text", 
                                    response
                                )
                                self.logger.info(f"已回复群聊AI消息: {response}")
                            except Exception as e:
                                self.logger.error(f"发送群聊AI回复失败: {e}")
                        
                        return response
                    else:
                        self.logger.error("AI聊天插件未加载，无法处理群@聊天消息")
            except Exception as e:
                self.logger.error(f"AI聊天处理异常: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
        
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
        
        # 如果空消息，直接返回提示信息
        if not clean_content:
            return "有什么事嘛？你可以通过 /help 获取可用命令列表"
        
        # 检查维护模式
        if auth_manager.is_maintenance_mode() and not auth_manager.is_admin(user_id):
            return "机器人当前处于维护模式，仅管理员可用"
        
        # 分割命令和参数
        parts = clean_content.strip().split(' ', 1)
        command = parts[0]
        params = parts[1] if len(parts) > 1 else ""
        
        # 检查命令是否为help
        if command.lower() == "/help":
            return plugin_manager.get_help()
            
        # 检查命令格式，必须以/开头
        if ENFORCE_COMMAND_PREFIX and not command.startswith('/'):
            # 仅在AI聊天启用时提示可以直接聊天
            if ENABLE_AI_CHAT and AI_CHAT_MENTION_TRIGGER:
                return f"您似乎想使用命令，命令必须以/开头，例如: /{command}\n或者您可以直接和我聊天，我会用AI回答您"
            else:
                return f"命令必须以/开头，例如: /{command}\n你可以通过 /help 获取可用命令列表"
        
        # 处理命令
        try:
            # 提取群ID信息
            group_openid = data.get("group_openid")
            
            # 如果命令不以/开头且启用了命令规范化，添加/前缀
            if ENFORCE_COMMAND_PREFIX and not command.startswith('/'):
                command = f"/{command}"
                
            # 传递完整事件数据
            plugin = plugin_manager.get_plugin(command)
            if not plugin:
                # 命令不存在，返回提示信息
                return f"未找到命令\n你可以通过 /help 获取可用命令列表"
            
            return await plugin.handle(params, user_id, group_openid=group_openid, event_data=data)
        except Exception as e:
            self.logger.error(f"处理命令时出错: {e}")
            return f"处理命令时出错: {e}"

# 创建事件处理器实例
event_handler = EventHandler()
