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
from enhanced_message_types import (
    EventType, EnhancedMessage, EventDataNormalizer,
    extract_user_id, extract_target_info, normalize_event
)
from blacklist_manager import blacklist_manager
from config import ENABLE_BLACKLIST, BLACKLIST_SHOW_REASON

# 配置日志
logger = logging.getLogger("event_handler")

# 从环境变量读取配置
ENABLE_AI_CHAT = os.environ.get("ENABLE_AI_CHAT", "true").lower() == "true"
AI_CHAT_MENTION_TRIGGER = os.environ.get("AI_CHAT_MENTION_TRIGGER", "true").lower() == "true"
ENFORCE_COMMAND_PREFIX = os.environ.get("ENFORCE_COMMAND_PREFIX", "true").lower() == "true"

class EventHandler:
    """
    事件处理器：处理QQ机器人的各类事件
    支持消息事件、机器人加入/退出群聊、用户添加/删除机器人等事件
    """
    
    def __init__(self):
        self.logger = logger
        # 注册事件处理方法的映射
        self.event_handlers = {
            # 消息事件 - 原有功能
            "AT_MESSAGE_CREATE": self.handle_at_message,
            "DIRECT_MESSAGE_CREATE": self.handle_direct_message,
            "C2C_MESSAGE_CREATE": self.handle_c2c_message,
            "GROUP_AT_MESSAGE_CREATE": self.handle_group_at_message,
            "READY": self.handle_ready,
            "RESUMED": self.handle_resumed,

            # 群组事件 - 新添加功能
            "GROUP_ADD_ROBOT": self.handle_group_add_robot,
            "GROUP_DEL_ROBOT": self.handle_group_del_robot,
            "GROUP_MSG_REJECT": self.handle_group_msg_reject,
            "GROUP_MSG_RECEIVE": self.handle_group_msg_receive,

            # 用户事件 - 新添加功能
            "FRIEND_ADD": self.handle_friend_add,
            "FRIEND_DEL": self.handle_friend_del,
            "C2C_MSG_REJECT": self.handle_c2c_msg_reject,
            "C2C_MSG_RECEIVE": self.handle_c2c_msg_receive,

            # Botpy扩展事件支持
            "MESSAGE_CREATE": self.handle_message_create,
            "MESSAGE_DELETE": self.handle_message_delete,
            "GUILD_CREATE": self.handle_guild_create,
            "GUILD_UPDATE": self.handle_guild_update,
            "GUILD_DELETE": self.handle_guild_delete,
            "GUILD_MEMBER_ADD": self.handle_guild_member_add,
            "GUILD_MEMBER_UPDATE": self.handle_guild_member_update,
            "GUILD_MEMBER_REMOVE": self.handle_guild_member_remove,
            "MESSAGE_REACTION_ADD": self.handle_message_reaction_add,
            "MESSAGE_REACTION_REMOVE": self.handle_message_reaction_remove,
            "INTERACTION_CREATE": self.handle_interaction_create,
            "MESSAGE_AUDIT_PASS": self.handle_message_audit_pass,
            "MESSAGE_AUDIT_REJECT": self.handle_message_audit_reject,
            "AUDIO_START": self.handle_audio_start,
            "AUDIO_FINISH": self.handle_audio_finish,
            "AUDIO_ON_MIC": self.handle_audio_on_mic,
            "AUDIO_OFF_MIC": self.handle_audio_off_mic
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

    def _format_expire_time(self, expire_time_str: str) -> str:
        """格式化过期时间为更易读的格式"""
        try:
            from datetime import datetime
            expire_time = datetime.fromisoformat(expire_time_str)
            now = datetime.now()

            # 计算剩余时间
            remaining = expire_time - now
            if remaining.total_seconds() <= 0:
                return "已过期"

            days = remaining.days
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            if days > 0:
                return f"{days}天{hours}小时后解封"
            elif hours > 0:
                return f"{hours}小时{minutes}分钟后解封"
            else:
                return f"{minutes}分钟后解封"
        except:
            return expire_time_str

    def _check_blacklist(self, event_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """检查用户或群组是否在黑名单中，返回(是否被屏蔽, 封禁原因)"""
        try:
            # 检查是否启用黑名单功能
            if not ENABLE_BLACKLIST:
                return False, None

            # 检查群组黑名单
            group_id = event_data.get("group_openid")
            if group_id:
                group_entry = blacklist_manager.get_entry(group_id)
                if group_entry and not group_entry.is_expired():
                    reason = f"🚫 该群组已被封禁\n📝 封禁原因：{group_entry.reason}"
                    if group_entry.expires_at:
                        expire_info = self._format_expire_time(group_entry.expires_at)
                        reason += f"\n⏰ {expire_info}"
                    else:
                        reason += f"\n⏰ 永久封禁"
                    self.logger.warning(f"群组 {group_id} 在黑名单中，拒绝处理 - {group_entry.reason}")
                    return True, reason

            # 检查用户黑名单
            user_id = self._get_user_id(event_data)
            if user_id:
                user_entry = blacklist_manager.get_entry(user_id)
                if user_entry and not user_entry.is_expired():
                    reason = f"🚫 您已被封禁，无法使用机器人\n📝 封禁原因：{user_entry.reason}"
                    if user_entry.expires_at:
                        expire_info = self._format_expire_time(user_entry.expires_at)
                        reason += f"\n⏰ {expire_info}"
                    else:
                        reason += f"\n⏰ 永久封禁"
                    self.logger.warning(f"用户 {user_id} 在黑名单中，拒绝处理 - {user_entry.reason}")
                    return True, reason

            return False, None

        except Exception as e:
            self.logger.error(f"检查黑名单时出错: {e}")
            return False, None

    def _get_channel_id(self, data):
        """从事件数据中提取频道/群组/用户ID，用于回复"""
        if "group_openid" in data:
            return data["group_openid"], True
        if "channel_id" in data:
             return data["channel_id"], False

        # 处理私聊消息 - 优先使用user_openid
        author = data.get("author", {})
        user_openid = author.get("user_openid") or author.get("id") or author.get("openid")
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

                event_type = event_data.get("type")
                await self._send_reply(target_id, message_id, is_group, event_type, response)

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

                event_type = event_data.get("type")
                await self._send_reply(target_id, message_id, is_group, event_type, response)

            except Exception as e:
                self.logger.error(f"发送AI回复时出错: {e}")
                self.logger.error(traceback.format_exc())

    async def handle_at_message(self, data):
        """处理频道@消息"""
        self.logger.info(f"收到@消息: {data}")
        # 设置事件类型，确保黑名单检查能正确识别
        data["type"] = "AT_MESSAGE_CREATE"
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
        # 设置事件类型，确保黑名单检查能正确识别
        data["type"] = "DIRECT_MESSAGE_CREATE"
        content = data.get("content", "")
        user_id = self._get_user_id(data)

        # 记录用户统计数据
        if user_id:
            stats_manager.add_user(user_id)

        await self._process_command(content, data, user_id)
        return True

    async def handle_c2c_message(self, data):
        """处理单聊(C2C)消息 - 实际上会被 handle_direct_message 接管"""
        self.logger.info(f"收到C2C消息 (将被转发给私聊处理): {data}")
        # 设置事件类型，确保黑名单检查能正确识别
        data["type"] = "C2C_MESSAGE_CREATE"
        await self.handle_direct_message(data)
        return True

    async def handle_group_at_message(self, data):
        """处理群聊@消息"""
        self.logger.info(f"收到群聊@消息: {data}")
        # 设置事件类型，确保黑名单检查能正确识别
        data["type"] = "GROUP_AT_MESSAGE_CREATE"
        content = data.get("content", "")
        user_id = self._get_user_id(data)
        group_openid = data.get("group_openid")
        
        # 记录用户和群组统计数据
        if user_id:
            stats_manager.add_user(user_id)
        if group_openid:
            stats_manager.add_group(group_openid)
            if user_id:
                stats_manager.add_user_to_group(group_openid, user_id)
        
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

    async def handle_ready(self, data):
        """处理准备就绪事件"""
        self.logger.info(f"机器人就绪: {data}")
        return True
    
    async def handle_resumed(self, data):
        """处理恢复连接事件"""
        self.logger.info("连接已恢复")
        return True

    async def _process_command(self, content, data, user_id=None):
        """处理命令，找到插件或特殊命令（如/help）则创建后台任务执行"""
        # 检查黑名单
        is_blocked, block_reason = self._check_blacklist(data)
        if is_blocked:
            self.logger.info(f"黑名单检查: 被阻止, 原因='{block_reason}', SHOW_REASON={BLACKLIST_SHOW_REASON}")

            # 可选择性地向用户发送封禁原因（仅在私聊或@消息时）
            event_type = data.get("type")
            self.logger.info(f"事件类型: {event_type}")

            if event_type in ["DIRECT_MESSAGE_CREATE", "C2C_MESSAGE_CREATE", "AT_MESSAGE_CREATE", "GROUP_AT_MESSAGE_CREATE"]:
                self.logger.info(f"事件类型匹配，检查发送条件: block_reason={bool(block_reason)}, BLACKLIST_SHOW_REASON={BLACKLIST_SHOW_REASON}")

                if block_reason and BLACKLIST_SHOW_REASON:
                    try:
                        message_id = data.get("id")
                        target_id, is_group = self._get_channel_id(data)
                        self.logger.info(f"获取目标ID: target_id='{target_id}', is_group={is_group}, message_id='{message_id}'")

                        if target_id:
                            # 等待发送完成
                            await self._send_reply(target_id, message_id, is_group, event_type, f"❌ {block_reason}")
                            self.logger.info(f"已发送封禁原因给 {target_id}")
                        else:
                            self.logger.warning("无法获取有效的target_id，跳过发送封禁原因")
                    except Exception as e:
                        self.logger.error(f"发送封禁原因时出错: {e}")
                        import traceback
                        self.logger.error(traceback.format_exc())
                else:
                    self.logger.info(f"跳过发送封禁原因: block_reason={bool(block_reason)}, BLACKLIST_SHOW_REASON={BLACKLIST_SHOW_REASON}")
            else:
                self.logger.info(f"事件类型不匹配，不发送封禁原因: {event_type}")

            return False  # 被黑名单阻止，不处理

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
        
        # 记录命令使用统计
        if plugin:
            group_openid = data.get("group_openid")
            stats_manager.log_command(plugin.command, user_id, group_openid)
            
        if plugin:
            # 找到插件，启动后台任务处理
            self.logger.info(f"为命令 '{command}' 找到插件 '{plugin.__class__.__name__}'，创建后台处理任务")
            asyncio.create_task(self._run_plugin_and_reply(plugin, params, user_id, data))
            return True # 表示已开始处理
        elif command.lower() == "/help":
            # 特殊处理 /help 命令
            self.logger.info("处理内置 /help 命令")
            response_to_send = plugin_manager.get_help()
            # 记录help命令使用
            stats_manager.log_command("help", user_id, data.get("group_openid"))
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

    def _is_private_message(self, event_type: Optional[str], target_id: str) -> bool:
        """判断是否为私聊消息"""
        # 明确的私聊事件类型
        if event_type in ["DIRECT_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"]:
            return True

        # 如果target_id看起来像用户openid（通常是长字符串），且不是频道ID格式
        if target_id and len(target_id) > 20 and not target_id.startswith("channel_"):
            return True

        return False

    async def _send_reply(self, target_id: str, message_id: Optional[str], is_group: bool, event_type: Optional[str], response: str):
        """统一的发送回复逻辑"""
        if not response or not target_id:
             self.logger.warning(f"无法发送回复: response='{response}', target_id='{target_id}'")
             return

        # 判断是否为私聊消息
        is_private = self._is_private_message(event_type, target_id)

        self.logger.info(f"准备发送回复: target_id={target_id}, message_id={message_id}, is_group={is_group}, is_private={is_private}, event_type={event_type}, response='{response[:50]}...'")

        try:
            if message_id: # 优先尝试回复原始消息
                if is_group:
                     await asyncio.to_thread(MessageSender.reply_group_message, target_id, message_id, "text", response)
                elif is_private:
                     await asyncio.to_thread(MessageSender.reply_private_message, target_id, message_id, response)
                else: # 处理频道内@消息等其他非群组、非私聊类型
                     await asyncio.to_thread(MessageSender.reply_message, target_id, message_id, "text", response, is_group=False)
            else: # 如果没有原始消息ID，直接发送
                self.logger.warning(f"发送回复时未找到原始消息ID，将直接发送。Target: {target_id}, Event Type: {event_type}")
                if is_group:
                     await asyncio.to_thread(MessageSender.send_group_message, target_id, "text", response)
                elif is_private:
                     await asyncio.to_thread(MessageSender.send_private_message, target_id, response)
                else: # 处理频道内@消息等其他非群组、非私聊类型
                     await asyncio.to_thread(MessageSender.send_message, target_id, "text", response, is_group=False)
            self.logger.info(f"已发送回复到 {target_id}")
        except Exception as e:
            self.logger.error(f"发送回复时出错: {e}")
            self.logger.error(traceback.format_exc())

    # 新添加的群组和用户事件处理方法
    async def handle_group_add_robot(self, event_data: Dict[str, Any]) -> bool:
        """处理机器人加入群聊事件"""
        self.logger.info(f"机器人被添加到群聊: {event_data}")
        
        group_openid = event_data.get("group_openid")
        op_member_openid = event_data.get("op_member_openid")
        timestamp = event_data.get("timestamp")
        
        if not group_openid:
            self.logger.error("缺少群组ID")
            return False
        
        return stats_manager.handle_group_add_robot(group_openid, op_member_openid, timestamp)
    
    async def handle_group_del_robot(self, event_data: Dict[str, Any]) -> bool:
        """处理机器人退出群聊事件"""
        self.logger.info(f"机器人被移出群聊: {event_data}")
        
        group_openid = event_data.get("group_openid")
        op_member_openid = event_data.get("op_member_openid")
        timestamp = event_data.get("timestamp")
        
        if not group_openid:
            self.logger.error("缺少群组ID")
            return False
        
        return stats_manager.handle_group_del_robot(group_openid, op_member_openid, timestamp)
    
    async def handle_group_msg_reject(self, event_data: Dict[str, Any]) -> bool:
        """处理群聊拒绝机器人主动消息事件"""
        self.logger.info(f"群聊拒绝机器人主动消息: {event_data}")
        
        group_openid = event_data.get("group_openid")
        if not group_openid:
            self.logger.error("缺少群组ID")
            return False
        
        group = stats_manager.get_group(group_openid)
        if group:
            group["can_send_proactive_msg"] = False
            stats_manager._save_data()
            return True
        return False
    
    async def handle_group_msg_receive(self, event_data: Dict[str, Any]) -> bool:
        """处理群聊接受机器人主动消息事件"""
        self.logger.info(f"群聊接受机器人主动消息: {event_data}")
        
        group_openid = event_data.get("group_openid")
        if not group_openid:
            self.logger.error("缺少群组ID")
            return False
        
        group = stats_manager.get_group(group_openid)
        if group:
            group["can_send_proactive_msg"] = True
            stats_manager._save_data()
            return True
        return False
    
    async def handle_friend_add(self, event_data: Dict[str, Any]) -> bool:
        """处理用户添加机器人事件"""
        self.logger.info(f"用户添加机器人: {event_data}")
        
        user_openid = event_data.get("openid")
        timestamp = event_data.get("timestamp")
        
        if not user_openid:
            self.logger.error("缺少用户ID")
            return False
        
        return stats_manager.handle_friend_add(user_openid, timestamp)
    
    async def handle_friend_del(self, event_data: Dict[str, Any]) -> bool:
        """处理用户删除机器人事件"""
        self.logger.info(f"用户删除机器人: {event_data}")
        
        user_openid = event_data.get("openid")
        timestamp = event_data.get("timestamp")
        
        if not user_openid:
            self.logger.error("缺少用户ID")
            return False
        
        return stats_manager.handle_friend_del(user_openid, timestamp)
    
    async def handle_c2c_msg_reject(self, event_data: Dict[str, Any]) -> bool:
        """处理拒绝机器人主动消息事件"""
        self.logger.info(f"用户拒绝机器人主动消息: {event_data}")
        
        user_openid = event_data.get("openid")
        if not user_openid:
            self.logger.error("缺少用户ID")
            return False
        
        user = stats_manager.get_user(user_openid)
        if user:
            user["can_send_proactive_msg"] = False
            stats_manager._save_data()
            return True
        return False
    
    async def handle_c2c_msg_receive(self, event_data: Dict[str, Any]) -> bool:
        """处理接受机器人主动消息事件"""
        self.logger.info(f"用户接受机器人主动消息: {event_data}")

        user_openid = event_data.get("openid")
        if not user_openid:
            self.logger.error("缺少用户ID")
            return False

        user = stats_manager.get_user(user_openid)
        if user:
            user["can_send_proactive_msg"] = True
            stats_manager._save_data()
            return True
        return False

    # Botpy扩展事件处理方法
    async def handle_message_create(self, event_data: Dict[str, Any]) -> bool:
        """处理消息创建事件（私域机器人）"""
        self.logger.info(f"收到消息创建事件: {event_data}")
        # 转换为AT_MESSAGE_CREATE事件处理
        return await self.handle_at_message(event_data)

    async def handle_message_delete(self, event_data: Dict[str, Any]) -> bool:
        """处理消息删除事件"""
        self.logger.info(f"消息被删除: {event_data}")
        return True

    async def handle_guild_create(self, event_data: Dict[str, Any]) -> bool:
        """处理频道创建事件"""
        self.logger.info(f"机器人加入频道: {event_data}")
        return True

    async def handle_guild_update(self, event_data: Dict[str, Any]) -> bool:
        """处理频道更新事件"""
        self.logger.info(f"频道信息更新: {event_data}")
        return True

    async def handle_guild_delete(self, event_data: Dict[str, Any]) -> bool:
        """处理频道删除事件"""
        self.logger.info(f"机器人退出频道: {event_data}")
        return True

    async def handle_guild_member_add(self, event_data: Dict[str, Any]) -> bool:
        """处理频道成员加入事件"""
        self.logger.info(f"频道成员加入: {event_data}")
        return True

    async def handle_guild_member_update(self, event_data: Dict[str, Any]) -> bool:
        """处理频道成员更新事件"""
        self.logger.info(f"频道成员信息更新: {event_data}")
        return True

    async def handle_guild_member_remove(self, event_data: Dict[str, Any]) -> bool:
        """处理频道成员移除事件"""
        self.logger.info(f"频道成员移除: {event_data}")
        return True

    async def handle_message_reaction_add(self, event_data: Dict[str, Any]) -> bool:
        """处理消息表情添加事件"""
        self.logger.info(f"消息表情添加: {event_data}")
        return True

    async def handle_message_reaction_remove(self, event_data: Dict[str, Any]) -> bool:
        """处理消息表情移除事件"""
        self.logger.info(f"消息表情移除: {event_data}")
        return True

    async def handle_interaction_create(self, event_data: Dict[str, Any]) -> bool:
        """处理交互事件"""
        self.logger.info(f"收到交互事件: {event_data}")
        return True

    async def handle_message_audit_pass(self, event_data: Dict[str, Any]) -> bool:
        """处理消息审核通过事件"""
        self.logger.info(f"消息审核通过: {event_data}")
        return True

    async def handle_message_audit_reject(self, event_data: Dict[str, Any]) -> bool:
        """处理消息审核拒绝事件"""
        self.logger.info(f"消息审核拒绝: {event_data}")
        return True

    async def handle_audio_start(self, event_data: Dict[str, Any]) -> bool:
        """处理音频开始事件"""
        self.logger.info(f"音频开始播放: {event_data}")
        return True

    async def handle_audio_finish(self, event_data: Dict[str, Any]) -> bool:
        """处理音频结束事件"""
        self.logger.info(f"音频播放结束: {event_data}")
        return True

    async def handle_audio_on_mic(self, event_data: Dict[str, Any]) -> bool:
        """处理上麦事件"""
        self.logger.info(f"用户上麦: {event_data}")
        return True

    async def handle_audio_off_mic(self, event_data: Dict[str, Any]) -> bool:
        """处理下麦事件"""
        self.logger.info(f"用户下麦: {event_data}")
        return True

# 创建全局实例
event_handler = EventHandler()