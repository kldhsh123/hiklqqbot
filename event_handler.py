import json
import logging
import re
import os
from plugins.plugin_manager import plugin_manager
import asyncio
from message import MessageSender
from auth_manager import auth_manager
import traceback
from typing import Optional, Dict, Any
from stats_manager import stats_manager

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
            # 新增QQ官方事件处理
            "GROUP_ADD_ROBOT": self.handle_group_add_robot,
            "GROUP_DEL_ROBOT": self.handle_group_del_robot,
            "FRIEND_ADD": self.handle_friend_add,
            "FRIEND_DEL": self.handle_friend_del,
            "C2C_MSG_REJECT": self.handle_c2c_msg_reject,
            "C2C_MSG_RECEIVE": self.handle_c2c_msg_receive,
        }
        
        # AI聊天插件实例（仅当功能启用时）
        self.ai_chat_plugin = None
        self._load_ai_plugin_if_needed()
        
        # 初始化统计管理器的自动保存功能
        asyncio.create_task(stats_manager.start_auto_save())

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
        
        # 记录事件到统计系统
        await self._record_event_stats(event_type, event_data)
        
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
            # 记录未处理的事件类型
            await stats_manager.add_event(f"UNHANDLED_{event_type}", event_data)
            return False
    
    async def _record_event_stats(self, event_type: str, event_data: Dict[str, Any]):
        """记录事件到统计系统"""
        try:
            # 记录原始事件
            await stats_manager.add_event(event_type, event_data)
            
            # 根据事件类型进行特殊处理
            if event_type == "GROUP_AT_MESSAGE_CREATE" or event_type == "AT_MESSAGE_CREATE":
                # 提取发送者信息
                user_id = self._get_user_id(event_data)
                if user_id:
                    # 提取更多用户信息（如头像、昵称等）
                    user_metadata = self._extract_user_metadata(event_data)
                    await stats_manager.add_user(user_id, metadata=user_metadata)
                
                # 提取群组信息
                group_id = event_data.get("group_openid")
                if group_id:
                    # 提取群组元数据
                    group_metadata = self._extract_group_metadata(event_data)
                    # 更新群组活跃时间
                    await stats_manager.add_group(group_id, metadata=group_metadata)
                    
                    # 如果有用户ID，建立用户和群组的关系
                    if user_id:
                        await stats_manager.add_user_to_group(group_id, user_id)
            
            elif event_type == "DIRECT_MESSAGE_CREATE" or event_type == "C2C_MESSAGE_CREATE":
                # 提取发送者信息
                user_id = self._get_user_id(event_data)
                if user_id:
                    # 提取更多用户信息
                    user_metadata = self._extract_user_metadata(event_data)
                    await stats_manager.add_user(user_id, metadata=user_metadata)
        except Exception as e:
            self.logger.error(f"记录事件统计时出错: {e}")
            self.logger.error(traceback.format_exc())

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
        group_id = data.get("group_openid")
        op_member_openid = data.get("op_member_openid")
        
        if group_id:
            # 更新群组状态
            if op_member_openid:
                # 将操作者记录为用户
                await stats_manager.add_user(op_member_openid)
                
            # 更新群组信息，标记为拒绝主动消息
            group_info = stats_manager.get_group(group_id)
            if group_info:
                await stats_manager.add_group(
                    group_id,
                    metadata={"allow_active_messages": False}
                )
        
        return True
    
    async def handle_group_msg_receive(self, data):
        """处理群聊接受机器人主动消息事件"""
        self.logger.info(f"群聊接受机器人主动消息: {data}")
        group_id = data.get("group_openid")
        op_member_openid = data.get("op_member_openid")
        
        if group_id:
            # 更新群组状态
            if op_member_openid:
                # 将操作者记录为用户
                await stats_manager.add_user(op_member_openid)
                
            # 更新群组信息，标记为接受主动消息
            await stats_manager.add_group(
                group_id,
                metadata={"allow_active_messages": True}
            )
        
        return True
    
    async def handle_ready(self, data):
        """处理READY事件"""
        self.logger.info(f"收到READY事件: {data}")
        # 记录机器人上线事件
        await stats_manager.add_event("BOT_ONLINE", {
            "time": data.get("session_id", "unknown")
        })
        return True
    
    async def handle_resumed(self, data):
        """处理RESUMED事件"""
        self.logger.info(f"收到RESUMED事件: {data}")
        # 记录机器人恢复连接事件
        await stats_manager.add_event("BOT_RESUMED", {
            "data": data
        })
        return True
    
    async def _process_command(self, content, data, user_id=None):
        """处理命令，找到插件或特殊命令（如/help）则创建后台任务执行"""
        clean_content = re.sub(r'<@!\d+>', '', content).strip()
        event_type = data.get("type")
        is_at_message = event_type in ["AT_MESSAGE_CREATE", "GROUP_AT_MESSAGE_CREATE"]
        is_direct_message = event_type in ["DIRECT_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"]

        # 如果不是@消息、私聊消息，且内容不以/开头，则忽略 (避免处理普通群聊消息)
        if not is_at_message and not is_direct_message and not clean_content.startswith('/'):
             self.logger.debug(f"忽略非 / 开头的普通群/频道消息: {clean_content[:50]}...")
             return False # 表明未处理

        # 处理空内容的情况
        if not clean_content:
            # 只在 @消息 或 私聊 时回复提示
            if is_at_message or is_direct_message:
                response = "有什么事嘛？你可以通过 /help 获取可用命令列表"
                message_id = data.get("id")
                target_id, is_group = self._get_channel_id(data)
                if target_id:
                     async def send_empty_reply(): # 修改函数名避免冲突
                          try:
                               # 使用统一的回复逻辑
                               await self._send_reply(target_id, message_id, is_group, event_type, response)
                          except Exception as e:
                               self.logger.error(f"发送空命令提示时出错: {e}")
                               self.logger.error(traceback.format_exc())
                     asyncio.create_task(send_empty_reply())
                     return True # 表明已处理 (开始发送回复)
            return False # 其他情况（如空内容的普通群消息）不处理

        # 检查维护模式
        if auth_manager.is_maintenance_mode() and not auth_manager.is_admin(user_id):
            response = "机器人当前处于维护模式，仅管理员可用"
            message_id = data.get("id")
            target_id, is_group = self._get_channel_id(data)
            if target_id:
                 async def send_maint_reply():
                      try:
                          await self._send_reply(target_id, message_id, is_group, event_type, response)
                      except Exception as e:
                           self.logger.error(f"发送维护模式提示时出错: {e}")
                           self.logger.error(traceback.format_exc())
                 asyncio.create_task(send_maint_reply())
                 return True # 表明已处理
            return False # 无法发送回复则认为未处理

        # 分割命令和参数
        parts = clean_content.strip().split(' ', 1)
        command_raw = parts[0]
        params = parts[1] if len(parts) > 1 else ""
        
        command = command_raw
        
        # 检查命令前缀和私聊的特殊处理 (结合AI启用状态)
        if ENFORCE_COMMAND_PREFIX and not command.startswith('/') and not is_direct_message and not is_at_message:
             self.logger.debug(f"忽略非 / 开头的普通群/频道消息 (强制前缀): {command}")
             return False # 不处理普通消息
        elif is_direct_message and not command.startswith('/'):
             # 私聊时，如果AI未启用，且未使用 / 前缀，则提示需要加 /
             if not ENABLE_AI_CHAT:
                  response = f"命令必须以/开头\n你可以通过 /help 获取可用命令列表"
                  message_id = data.get("id")
                  target_id, is_group = self._get_channel_id(data) # is_group 应为 False
                  if target_id:
                       async def send_prefix_reply():
                            try:
                                await self._send_reply(target_id, message_id, is_group, event_type, response)
                            except Exception as e:
                                 self.logger.error(f"发送命令前缀提示时出错: {e}")
                                 self.logger.error(traceback.format_exc())
                       asyncio.create_task(send_prefix_reply())
                       return True # 已处理 (发送提示)
                  return False # 无法发送提示
             # 如果AI启用，私聊时非 / 开头的消息可能触发AI (如果AI插件逻辑支持)
             # 这里不直接处理，交给后续的插件查找逻辑 (或者AI插件的特殊处理)
             pass 
        # 如果强制前缀，但命令没加/ (主要针对非私聊非@的情况，上面已处理)
        # elif ENFORCE_COMMAND_PREFIX and not command.startswith('/'):
        #     command = f'/{command}' # 强制加上 / - 这段逻辑似乎被上面的条件覆盖了，暂且注释

        # --- 修改开始: 统一处理流程 ---
        
        # 尝试查找插件
        plugin = plugin_manager.get_plugin(command)
        # 如果找不到带 / 的，并且不强制前缀，尝试找不带 / 的 (兼容旧插件或用户习惯)
        if not plugin and command.startswith('/') and not ENFORCE_COMMAND_PREFIX:
             plugin = plugin_manager.get_plugin(command[1:])
        
        response_to_send = None # 用于存储需要直接发送的响应 (help 或 not found)
        
        if plugin:
            # 找到插件，启动后台任务处理
            self.logger.info(f"为命令 '{command}' 找到插件 '{plugin.__class__.__name__}'，创建后台处理任务")
            asyncio.create_task(self._run_plugin_and_reply(plugin, params, user_id, data))
            return True # 表示已开始处理
        elif command.lower() == "/help":
            # 特殊处理 /help 命令
            self.logger.info("处理内置 /help 命令")
            response_to_send = plugin_manager.get_help()
        else:
            # 未找到插件，也不是 /help
             self.logger.warning(f"未找到命令 '{command}'")
             response_to_send = f"未找到命令\n你可以通过 /help 获取可用命令列表"

        # 如果有直接响应需要发送 (help 或 not found)
        if response_to_send:
            message_id = data.get("id")
            target_id, is_group = self._get_channel_id(data)
            if target_id:
                 # 使用后台任务发送响应
                 async def send_direct_reply(response_text):
                      try:
                          await self._send_reply(target_id, message_id, is_group, event_type, response_text)
                          self.logger.info(f"已发送直接回复到 {target_id} (Help/Not Found)")
                      except Exception as e:
                           self.logger.error(f"发送直接回复 (Help/Not Found) 时出错: {e}")
                           self.logger.error(traceback.format_exc())
                 asyncio.create_task(send_direct_reply(response_to_send))
                 return True # 表示已开始处理 (发送回复)
            else:
                 # 无法确定回复目标
                 self.logger.error(f"无法为命令 '{command}' 的直接响应确定回复目标")
                 return False # 表示处理失败

        # 如果既没找到插件，也不是/help，也没能发送'Not Found'回复，则返回False
        return False
        # --- 修改结束 ---

    async def _send_reply(self, target_id: str, message_id: Optional[str], is_group: bool, event_type: Optional[str], response: str):
        """统一的发送回复逻辑"""
        if not response or not target_id:
             self.logger.warning(f"无法发送回复: response='{response}', target_id='{target_id}'")
             return

        self.logger.info(f"准备发送回复: target_id={target_id}, message_id={message_id}, is_group={is_group}, event_type={event_type}, response='{response[:50]}...'")

        try:
            if message_id: # 优先尝试回复原始消息
                if is_group:
                     await asyncio.to_thread(MessageSender.reply_group_message, target_id, message_id, "text", response)
                elif event_type == "DIRECT_MESSAGE_CREATE" or event_type == "C2C_MESSAGE_CREATE":
                     await asyncio.to_thread(MessageSender.reply_private_message, target_id, message_id, response)
                else: # 处理频道内@消息等其他非群组、非私聊类型
                     await asyncio.to_thread(MessageSender.reply_message, target_id, message_id, "text", response, is_group=False)
            else: # 如果没有原始消息ID，直接发送
                self.logger.warning(f"发送回复时未找到原始消息ID，将直接发送。Target: {target_id}, Event Type: {event_type}")
                if is_group:
                     await asyncio.to_thread(MessageSender.send_group_message, target_id, "text", response)
                elif event_type == "DIRECT_MESSAGE_CREATE" or event_type == "C2C_MESSAGE_CREATE":
                     await asyncio.to_thread(MessageSender.send_private_message, target_id, response)
                else: # 处理频道内@消息等其他非群组、非私聊类型
                     await asyncio.to_thread(MessageSender.send_message, target_id, "text", response, is_group=False)
            self.logger.info(f"已发送回复到 {target_id}")
        except Exception as e:
            self.logger.error(f"发送回复时出错: {e}")
            self.logger.error(traceback.format_exc())

    # 以下是新增的事件处理方法
    
    async def handle_group_add_robot(self, data):
        """处理机器人被添加到群聊事件"""
        self.logger.info(f"机器人被添加到群聊: {data}")
        group_id = data.get("group_openid")
        op_member_openid = data.get("op_member_openid")
        timestamp = data.get("timestamp")
        
        if group_id:
            # 记录群组信息
            metadata = {"join_timestamp": timestamp} if timestamp else {}
            
            # 添加群组到统计
            await stats_manager.add_group(
                group_id,
                added_by=op_member_openid,
                metadata=metadata
            )
            
            # 如果有操作者，记录用户信息
            if op_member_openid:
                await stats_manager.add_user(op_member_openid)
                # 建立用户与群组的关系
                await stats_manager.add_user_to_group(group_id, op_member_openid)
                
            # 尝试向群组发送欢迎消息
            try:
                welcome_msg = "感谢邀请我加入本群！我是一个QQ机器人，发送 /help 可查看我的功能列表。"
                await asyncio.to_thread(MessageSender.send_group_message, group_id, "text", welcome_msg)
                self.logger.info(f"已向群组 {group_id} 发送欢迎消息")
            except Exception as e:
                self.logger.error(f"发送欢迎消息失败: {e}")
        
        return True
    
    async def handle_group_del_robot(self, data):
        """处理机器人被移出群聊事件"""
        self.logger.info(f"机器人被移出群聊: {data}")
        group_id = data.get("group_openid")
        op_member_openid = data.get("op_member_openid")
        timestamp = data.get("timestamp")
        
        if group_id:
            # 记录移除原因
            reason = "被管理员移除"
            if op_member_openid:
                reason += f"（操作者: {op_member_openid}）"
            
            # 更新群组状态
            await stats_manager.remove_group(
                group_id,
                reason=reason,
                removed_by=op_member_openid
            )
            
            # 如果有操作者，记录用户信息
            if op_member_openid:
                await stats_manager.add_user(op_member_openid)
        
        return True
    
    async def handle_friend_add(self, data):
        """处理用户添加机器人好友事件"""
        self.logger.info(f"用户添加机器人好友: {data}")
        user_id = data.get("openid")
        timestamp = data.get("timestamp")
        
        if user_id:
            # 记录用户信息
            metadata = {
                "is_friend": True,
                "friend_add_time": timestamp
            }
            
            await stats_manager.add_user(user_id, metadata=metadata)
            
            # 尝试向用户发送欢迎消息
            try:
                welcome_msg = "你好！很高兴认识你。我是一个QQ机器人，发送 /help 可查看我的功能列表。"
                await asyncio.to_thread(MessageSender.send_private_message, user_id, welcome_msg)
                self.logger.info(f"已向用户 {user_id} 发送欢迎消息")
            except Exception as e:
                self.logger.error(f"发送欢迎消息失败: {e}")
        
        return True
    
    async def handle_friend_del(self, data):
        """处理用户删除机器人好友事件"""
        self.logger.info(f"用户删除机器人好友: {data}")
        user_id = data.get("openid")
        timestamp = data.get("timestamp")
        
        if user_id:
            # 更新用户状态
            user_info = stats_manager.get_user(user_id)
            if user_info:
                metadata = {
                    "is_friend": False,
                    "friend_del_time": timestamp
                }
                await stats_manager.add_user(user_id, metadata=metadata)
        
        return True
    
    async def handle_c2c_msg_reject(self, data):
        """处理用户拒绝机器人主动消息事件"""
        self.logger.info(f"用户拒绝机器人主动消息: {data}")
        user_id = data.get("openid")
        timestamp = data.get("timestamp")
        
        if user_id:
            # 更新用户状态
            metadata = {
                "allow_active_messages": False,
                "reject_time": timestamp
            }
            await stats_manager.add_user(user_id, metadata=metadata)
        
        return True
    
    async def handle_c2c_msg_receive(self, data):
        """处理用户接受机器人主动消息事件"""
        self.logger.info(f"用户接受机器人主动消息: {data}")
        user_id = data.get("openid")
        timestamp = data.get("timestamp")
        
        if user_id:
            # 更新用户状态
            metadata = {
                "allow_active_messages": True,
                "receive_time": timestamp
            }
            await stats_manager.add_user(user_id, metadata=metadata)
        
        return True

    def _extract_user_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从事件数据中提取用户元数据
        
        Args:
            data: 事件数据
            
        Returns:
            用户元数据字典
        """
        metadata = {}
        
        # 从author字段提取信息
        author = data.get("author", {})
        if author:
            # 提取用户名
            if "username" in author:
                metadata["name"] = author["username"]
            
            # 提取头像URL
            if "avatar" in author:
                metadata["avatar"] = author["avatar"]
                
            # 提取是否为机器人
            if "bot" in author:
                metadata["is_bot"] = author["bot"]
        
        # 从user字段提取信息
        user = data.get("user", {})
        if user:
            # 提取用户名
            if "username" in user and "name" not in metadata:
                metadata["name"] = user["username"]
            
            # 提取头像URL
            if "avatar" in user and "avatar" not in metadata:
                metadata["avatar"] = user["avatar"]
        
        # 从member字段提取信息（群成员）
        member = data.get("member", {})
        if member:
            # 提取用户昵称
            if "nick" in member and "name" not in metadata:
                metadata["name"] = member["nick"]
                
            # 提取头像URL
            if "avatar" in member and "avatar" not in metadata:
                metadata["avatar"] = member["avatar"]
                
            # 提取加入时间
            if "joined_at" in member:
                metadata["joined_at"] = member["joined_at"]
        
        return metadata
        
    def _extract_group_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从事件数据中提取群组元数据
        
        Args:
            data: 事件数据
            
        Returns:
            群组元数据字典
        """
        metadata = {}
        
        # 提取群组名称
        if "group_name" in data:
            metadata["name"] = data["group_name"]
            
        # 提取群组头像
        if "group_avatar" in data:
            metadata["avatar"] = data["group_avatar"]
            
        # 从频道数据提取信息
        channel = data.get("channel", {})
        if channel:
            # 提取频道名称
            if "name" in channel and "name" not in metadata:
                metadata["name"] = channel["name"]
        
        return metadata

# 创建事件处理器实例
event_handler = EventHandler()