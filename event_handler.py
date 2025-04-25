import json
import logging
import re
import os
from plugins.plugin_manager import plugin_manager
import asyncio
from message import MessageSender
from auth_manager import auth_manager
import traceback

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
        self._load_ai_plugin_if_needed()

    def _load_ai_plugin_if_needed(self):
        """尝试加载AI聊天插件"""
        if ENABLE_AI_CHAT and AI_CHAT_MENTION_TRIGGER and not self.ai_chat_plugin:
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
                            self.logger.warning("AI聊天插件模块存在但未定义AIChatPlugin类")
                    else:
                        self.logger.info("AI聊天插件未在__all__中导出，不加载")
                else:
                    self.logger.info("未找到AI聊天插件模块，功能未启用")
            except Exception as e:
                self.logger.error(f"加载AI聊天插件失败: {e}")
                self.ai_chat_plugin = None
    
    async def handle_event(self, event_type, event_data):
        """处理事件分发"""
        self.logger.info(f"收到事件: {event_type}")
        
        # 特殊处理 C2C 事件，如果 DIRECT_MESSAGE_CREATE 能处理就用它
        if event_type == "C2C_MESSAGE_CREATE" and "DIRECT_MESSAGE_CREATE" in self.event_handlers:
             event_type = "DIRECT_MESSAGE_CREATE"

        handler = self.event_handlers.get(event_type)
        if handler:
            try:
                # handle_event 现在只负责分发，不再处理回复
                await handler(event_data)
                return True
            except Exception as e:
                self.logger.error(f"处理事件 {event_type} 时发生错误: {e}")
                self.logger.error(traceback.format_exc())
                return False
        else:
            self.logger.info(f"暂未支持的事件类型: {event_type}")
            return False
    
    def _get_user_id(self, data):
        """从事件数据中提取用户ID (优先author.id，然后是openid)"""
        author = data.get("author", {})
        user_id = author.get("id")
        if not user_id:
            user_id = author.get("openid")
        if not user_id:
             user_id = data.get("user", {}).get("openid")
        if not user_id:
            user_id = data.get("openid")
        return user_id

    def _get_channel_id(self, data):
        """从事件数据中提取频道/群组/用户ID，用于回复"""
        if "group_openid" in data:
            return data["group_openid"], True
        if "channel_id" in data:
             return data["channel_id"], False
        author = data.get("author", {})
        user_openid = author.get("id") or author.get("openid")
        if user_openid:
            return user_openid, False
        return None, False

    async def _run_plugin_and_reply(self, plugin, params: str, user_id: str, event_data: dict):
        """在后台运行插件并处理回复"""
        response = None
        try:
            group_openid = event_data.get("group_openid")
            response = await plugin.handle(params, user_id, group_openid=group_openid, event_data=event_data)
        except Exception as e:
            self.logger.error(f"插件 {plugin.command} 处理命令时出错: {e}")
            self.logger.error(traceback.format_exc())
            response = f"处理命令 {plugin.command} 时出现内部错误。"

        if response:
            try:
                message_id = event_data.get("id")
                target_id, is_group = self._get_channel_id(event_data)

                if not target_id:
                    self.logger.error(f"无法确定回复目标，事件数据: {event_data}")
                    return

                self.logger.info(f"准备回复消息: target_id={target_id}, message_id={message_id}, is_group={is_group}, response='{response[:50]}...'")

                if message_id:
                    if is_group:
                        await asyncio.to_thread(MessageSender.reply_group_message, target_id, message_id, "text", response)
                    else:
                        event_type = event_data.get("type")
                        if event_type == "DIRECT_MESSAGE_CREATE" or event_type == "C2C_MESSAGE_CREATE":
                             await asyncio.to_thread(MessageSender.reply_private_message, target_id, message_id, response)
                        else:
                             await asyncio.to_thread(MessageSender.reply_message, target_id, message_id, "text", response, is_group=False)
                else:
                    if is_group:
                        await asyncio.to_thread(MessageSender.send_group_message, target_id, "text", response)
                    else:
                        event_type = event_data.get("type")
                        if event_type == "DIRECT_MESSAGE_CREATE" or event_type == "C2C_MESSAGE_CREATE":
                            await asyncio.to_thread(MessageSender.send_private_message, target_id, response)
                        else:
                            await asyncio.to_thread(MessageSender.send_message, target_id, "text", response, is_group=False)

                self.logger.info(f"已发送回复到 {target_id}")

            except Exception as e:
                self.logger.error(f"发送回复时出错: {e}")
                self.logger.error(traceback.format_exc())

    async def _run_ai_chat_and_reply(self, event_data: dict, user_id: str):
        """在后台运行AI聊天插件并处理回复"""
        response = None
        if not self.ai_chat_plugin:
            self.logger.error("AI聊天插件未加载，无法处理AI回复")
            return

        try:
            response = await self.ai_chat_plugin.handle_at_message(event_data, user_id)
        except Exception as e:
            self.logger.error(f"AI聊天插件处理时出错: {e}")
            self.logger.error(traceback.format_exc())
            response = "AI思考时遇到了一些麻烦..."

        if response:
            try:
                message_id = event_data.get("id")
                target_id, is_group = self._get_channel_id(event_data)

                if not target_id:
                    self.logger.error(f"无法确定AI回复目标，事件数据: {event_data}")
                    return

                self.logger.info(f"准备发送AI回复: target_id={target_id}, message_id={message_id}, is_group={is_group}, response='{response[:50]}...'")

                if message_id:
                    if is_group:
                         await asyncio.to_thread(MessageSender.reply_group_message, target_id, message_id, "text", response)
                    else:
                         event_type = event_data.get("type")
                         if event_type == "DIRECT_MESSAGE_CREATE" or event_type == "C2C_MESSAGE_CREATE":
                              await asyncio.to_thread(MessageSender.reply_private_message, target_id, message_id, response)
                         else:
                              await asyncio.to_thread(MessageSender.reply_message, target_id, message_id, "text", response, is_group=False)
                else:
                    self.logger.warning(f"AI回复时未找到原始消息ID，将直接发送。事件: {event_data}")
                    if is_group:
                        await asyncio.to_thread(MessageSender.send_group_message, target_id, "text", response)
                    else:
                        event_type = event_data.get("type")
                        if event_type == "DIRECT_MESSAGE_CREATE" or event_type == "C2C_MESSAGE_CREATE":
                             await asyncio.to_thread(MessageSender.send_private_message, target_id, response)
                        else:
                             await asyncio.to_thread(MessageSender.send_message, target_id, "text", response, is_group=False)

                self.logger.info(f"已发送AI回复到 {target_id}")

            except Exception as e:
                self.logger.error(f"发送AI回复时出错: {e}")
                self.logger.error(traceback.format_exc())

    async def handle_at_message(self, data):
        """处理频道@消息"""
        self.logger.info(f"收到@消息: {data}")
        content = data.get("content", "")
        user_id = self._get_user_id(data)

        clean_content = re.sub(r'<@!\d+>', '', content).strip()
        clean_content = re.sub(r'@[\w\u4e00-\u9fa5]+\s*', '', clean_content).strip()

        if ENABLE_AI_CHAT and AI_CHAT_MENTION_TRIGGER:
            self._load_ai_plugin_if_needed()
            if clean_content and not clean_content.startswith('/') and self.ai_chat_plugin:
                self.logger.info(f"检测到AI聊天触发 (频道@): [{clean_content}]")
                asyncio.create_task(self._run_ai_chat_and_reply(data, user_id))
                return True
            elif not self.ai_chat_plugin and clean_content and not clean_content.startswith('/'):
                 self.logger.warning("AI聊天触发，但插件未加载。")

        await self._process_command(content, data, user_id)
        return True

    async def handle_direct_message(self, data):
        """处理私聊消息 (包括C2C)"""
        self.logger.info(f"收到私聊/C2C消息: {data}")
        content = data.get("content", "")
        user_id = self._get_user_id(data)

        await self._process_command(content, data, user_id)
        return True

    async def handle_c2c_message(self, data):
        """处理单聊(C2C)消息 - 实际上会被 handle_direct_message 接管"""
        self.logger.info(f"收到C2C消息 (将被转发给私聊处理): {data}")
        await self.handle_direct_message(data)
        return True

    async def handle_group_at_message(self, data):
        """处理群聊@消息"""
        self.logger.info(f"收到群聊@消息: {data}")
        content = data.get("content", "")
        user_id = self._get_user_id(data)
        
        clean_content = re.sub(r'<@!\d+>', '', content).strip()
        clean_content = re.sub(r'@[\w\u4e00-\u9fa5]+\s*', '', clean_content).strip()

        if ENABLE_AI_CHAT and AI_CHAT_MENTION_TRIGGER:
            self._load_ai_plugin_if_needed()
            if clean_content and not clean_content.startswith('/') and self.ai_chat_plugin:
                self.logger.info(f"检测到AI聊天触发 (群聊@): [{clean_content}]")
                data["type"] = "GROUP_AT_MESSAGE_CREATE"
                asyncio.create_task(self._run_ai_chat_and_reply(data, user_id))
                return True
            elif not self.ai_chat_plugin and clean_content and not clean_content.startswith('/'):
                 self.logger.warning("AI聊天触发(群聊)，但插件未加载。")

        await self._process_command(content, data, user_id)
        return True

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
        """处理命令，找到插件则创建后台任务执行"""
        clean_content = re.sub(r'<@!\d+>', '', content).strip()
        event_type = data.get("type")
        is_at_message = event_type in ["AT_MESSAGE_CREATE", "GROUP_AT_MESSAGE_CREATE"]
        is_direct_message = event_type in ["DIRECT_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"]

        if not is_at_message and not is_direct_message and not clean_content.startswith('/'):
             return False

        if not clean_content:
            if is_at_message or is_direct_message:
                response = "有什么事嘛？你可以通过 /help 获取可用命令列表"
                message_id = data.get("id")
                target_id, is_group = self._get_channel_id(data)
                if target_id:
                     async def send_simple_reply():
                          try:
                               if message_id:
                                    if is_group: await asyncio.to_thread(MessageSender.reply_group_message, target_id, message_id, "text", response)
                                    else: await asyncio.to_thread(MessageSender.reply_private_message, target_id, message_id, response)
                               else:
                                    if is_group: await asyncio.to_thread(MessageSender.send_group_message, target_id, "text", response)
                                    else: await asyncio.to_thread(MessageSender.send_private_message, target_id, response)
                          except Exception as e:
                               self.logger.error(f"发送空命令提示时出错: {e}")
                     asyncio.create_task(send_simple_reply())
                     return True
            return False

        if auth_manager.is_maintenance_mode() and not auth_manager.is_admin(user_id):
            response = "机器人当前处于维护模式，仅管理员可用"
            message_id = data.get("id")
            target_id, is_group = self._get_channel_id(data)
            if target_id:
                 async def send_maint_reply():
                      try:
                           if message_id:
                                if is_group: await asyncio.to_thread(MessageSender.reply_group_message, target_id, message_id, "text", response)
                                else: await asyncio.to_thread(MessageSender.reply_private_message, target_id, message_id, response)
                           else:
                                if is_group: await asyncio.to_thread(MessageSender.send_group_message, target_id, "text", response)
                                else: await asyncio.to_thread(MessageSender.send_private_message, target_id, response)
                      except Exception as e:
                           self.logger.error(f"发送维护模式提示时出错: {e}")
                 asyncio.create_task(send_maint_reply())
                 return True
            return False

        parts = clean_content.strip().split(' ', 1)
        command_raw = parts[0]
        params = parts[1] if len(parts) > 1 else ""
        
        command = command_raw
        if ENFORCE_COMMAND_PREFIX and not command.startswith('/') and not is_direct_message and not is_at_message:
             self.logger.debug(f"忽略非 / 开头的普通群消息: {command}")
             return False
        elif is_direct_message and not command.startswith('/'):
             if not ENABLE_AI_CHAT:
                  response = f"命令必须以/开头，例如: /{command}\n你可以通过 /help 获取可用命令列表"
                  message_id = data.get("id")
                  target_id, _ = self._get_channel_id(data)
                  if target_id:
                       async def send_prefix_reply():
                            try:
                                 if message_id: await asyncio.to_thread(MessageSender.reply_private_message, target_id, message_id, response)
                                 else: await asyncio.to_thread(MessageSender.send_private_message, target_id, response)
                            except Exception as e:
                                 self.logger.error(f"发送命令前缀提示时出错: {e}")
                       asyncio.create_task(send_prefix_reply())
                       return True
                  return False

        plugin = plugin_manager.get_plugin(command)
        if not plugin and command.startswith('/'):
             plugin = plugin_manager.get_plugin(command[1:])

        if plugin:
            self.logger.info(f"为命令 '{command}' 创建后台处理任务")
            asyncio.create_task(self._run_plugin_and_reply(plugin, params, user_id, data))
            return True
        else:
            response = f"未找到命令 '{command}'\n你可以通过 /help 获取可用命令列表"
            message_id = data.get("id")
            target_id, is_group = self._get_channel_id(data)
            if target_id:
                 async def send_notfound_reply():
                      try:
                           if message_id:
                                if is_group: await asyncio.to_thread(MessageSender.reply_group_message, target_id, message_id, "text", response)
                                else: await asyncio.to_thread(MessageSender.reply_private_message, target_id, message_id, response)
                           else:
                                if is_group: await asyncio.to_thread(MessageSender.send_group_message, target_id, "text", response)
                                else: await asyncio.to_thread(MessageSender.send_private_message, target_id, response)
                      except Exception as e:
                           self.logger.error(f"发送未找到命令提示时出错: {e}")
                 asyncio.create_task(send_notfound_reply())
                 return True
            return False

# 创建事件处理器实例
event_handler = EventHandler()