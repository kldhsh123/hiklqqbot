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
from message_archive import message_archive
from enhanced_message_types import (
    EventType, EnhancedMessage, EventDataNormalizer,
    extract_user_id, extract_target_info, normalize_event
)
from blacklist_manager import blacklist_manager
from config import (
    ENABLE_BLACKLIST, BLACKLIST_SHOW_REASON, API_BASE_URL,
    HELP_BUTTON_ACTION_TYPE, FULL_MESSAGE_MODE,
)
from reply import Reply
from ui_builder import make_button_row, make_command_button, make_keyboard

# 配置日志
logger = logging.getLogger("event_handler")

# 从环境变量读取配置
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
            "GROUP_MESSAGE_CREATE": self.handle_group_message,
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

            # 频道/扩展事件支持
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
        user_id = author.get("user_openid") or author.get("id")
        if not user_id:
            user_id = author.get("openid")
        if not user_id:
             user_id = data.get("user", {}).get("openid")
        if not user_id:
            user_id = data.get("openid")
        return user_id

    def _get_executor_user_id(self, data: Dict[str, Any]) -> Optional[str]:
        """提取当前执行命令/点击按钮的用户 ID，用于 markdown @。"""
        interaction_data = data.get("data", {}) or {}
        resolved = interaction_data.get("resolved", {}) or {}
        return (
            resolved.get("user_id")
            or data.get("group_member_openid")
            or data.get("user_openid")
            or self._get_user_id(data)
        )

    def _is_full_group_message_event(self, event_type: Optional[str]) -> bool:
        """判断是否为已授权群的全量消息事件。"""
        return event_type == "GROUP_MESSAGE_CREATE"

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

    def _build_help_shortcut_reply(self, title: str, body: str, user_id: Optional[str] = None) -> Reply:
        """构造带 /help 按钮的提示回复。"""
        keyboard = make_keyboard([
            make_button_row([
                make_command_button(
                    "help_shortcut",
                    "/help",
                    "/help",
                    action_type=HELP_BUTTON_ACTION_TYPE,
                    style=1,
                )
            ])
        ])
        parts = [f"## {title}"]
        if body:
            parts.append(body)
        return Reply(markdown="\n\n".join(parts), keyboard=keyboard)

    async def _send_event_response(self, event_data: Dict[str, Any], response: Any, msg_seq: int = 1) -> bool:
        """根据响应类型发送事件回复。"""
        if not response:
            return False

        message_id = event_data.get("id")
        target_id, is_group = self._get_channel_id(event_data)
        if not target_id:
            self.logger.error(f"无法确定回复目标，事件数据: {event_data}")
            return False

        event_type = event_data.get("type")
        responses = response if isinstance(response, list) else [response]
        sent = False

        for idx, item in enumerate(responses, start=msg_seq):
            if not item:
                continue

            reply = item if isinstance(item, Reply) else Reply(text=str(item))
            await self._send_rich_reply(
                target_id, message_id, is_group, event_type, reply, event_data, msg_seq=idx
            )
            sent = True

        return sent

    async def _run_plugin_and_reply(self, plugin, params: str, user_id: str, event_data: dict, invoked_command: str = None):
        """在后台运行插件并处理回复"""
        response = None
        group_openid = event_data.get("group_openid")
        event_type = event_data.get("type")
        is_full_group_message = self._is_full_group_message_event(event_type)
        try:
            response = await plugin.handle(
                params, user_id,
                group_openid=group_openid,
                event_data=event_data,
                invoked_command=invoked_command or plugin.command,
            )
            stats_manager.log_command(plugin.command, user_id, group_openid)
            if is_full_group_message:
                message_archive.log_command_message(
                    event_data,
                    user_id=user_id,
                    group_openid=group_openid,
                    command=plugin.command,
                    invoked_command=invoked_command or plugin.command,
                    params=params,
                )
        except Exception as e:
            self.logger.error(f"插件 {plugin.command} 处理命令时出错: {e}")
            self.logger.error(traceback.format_exc())
            response = f"处理命令 {plugin.command} 时出现内部错误。"
            if is_full_group_message:
                stats_manager.log_other_message(user_id, group_openid)
                message_archive.log_other_message(
                    event_data,
                    user_id=user_id,
                    group_openid=group_openid,
                    reason="plugin_error",
                    command=plugin.command,
                    invoked_command=invoked_command or plugin.command,
                    params=params,
                )

        if not response:
            return

        try:
            await self._send_event_response(event_data, response)
        except Exception as e:
            self.logger.error(f"发送回复时出错: {e}")
            self.logger.error(traceback.format_exc())

    async def handle_at_message(self, data):
        """处理频道@消息"""
        self.logger.info(f"收到@消息: {data}")
        # 设置事件类型，确保黑名单检查能正确识别
        data["type"] = "AT_MESSAGE_CREATE"
        content = data.get("content", "")
        user_id = self._get_user_id(data)
        username = (data.get("author") or {}).get("username")
        if user_id:
            stats_manager.add_user(user_id, name=username)

        clean_content = re.sub(r'<@!\d+>', '', content).strip()
        clean_content = re.sub(r'@[\w\u4e00-\u9fa5]+\s*', '', clean_content).strip()

        await self._process_command(content, data, user_id)
        return True

    async def handle_direct_message(self, data):
        """处理私聊消息 (包括C2C)"""
        self.logger.info(f"收到私聊/C2C消息: {data}")
        # 设置事件类型，确保黑名单检查能正确识别
        data["type"] = "DIRECT_MESSAGE_CREATE"
        content = data.get("content", "")
        user_id = self._get_user_id(data)
        username = (data.get("author") or {}).get("username")

        # 记录用户统计数据
        if user_id:
            stats_manager.add_user(user_id, name=username)

        await self._process_command(content, data, user_id)
        return True

    async def handle_c2c_message(self, data):
        """处理单聊(C2C)消息 - 实际上会被 handle_direct_message 接管"""
        self.logger.info(f"收到C2C消息 (将被转发给私聊处理): {data}")
        # 设置事件类型，确保黑名单检查能正确识别
        data["type"] = "C2C_MESSAGE_CREATE"
        await self.handle_direct_message(data)
        return True

    async def _handle_group_message_common(self, data: Dict[str, Any], event_type: str):
        """处理群聊消息（全量群消息或群聊@消息）的公共逻辑。"""
        data["type"] = event_type
        content = data.get("content", "")
        user_id = self._get_user_id(data)
        username = (data.get("author") or {}).get("username")
        group_openid = data.get("group_openid")

        # 记录用户和群组统计数据
        if user_id:
            stats_manager.add_user(user_id, name=username)
        if group_openid:
            stats_manager.add_group(group_openid)
            if user_id:
                stats_manager.add_user_to_group(group_openid, user_id)
        
        clean_content = re.sub(r'<@!\d+>', '', content).strip()
        clean_content = re.sub(r'@[\w\u4e00-\u9fa5]+\s*', '', clean_content).strip()

        await self._process_command(content, data, user_id)
        return True

    async def handle_group_message(self, data):
        """处理已授权全量群消息。"""
        self.logger.info(f"收到群聊消息: {data}")
        return await self._handle_group_message_common(data, "GROUP_MESSAGE_CREATE")

    async def handle_group_at_message(self, data):
        """处理群聊@消息"""
        self.logger.info(f"收到群聊@消息: {data}")
        await self._handle_group_message_common(data, "GROUP_AT_MESSAGE_CREATE")
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
        event_type = data.get("type")
        group_openid = data.get("group_openid")
        is_full_group_message = self._is_full_group_message_event(event_type)

        def log_other_message_if_needed(reason: str, command: str = None, params_text: str = ""):
            if not is_full_group_message:
                return
            stats_manager.log_other_message(user_id, group_openid)
            message_archive.log_other_message(
                data,
                user_id=user_id,
                group_openid=group_openid,
                reason=reason,
                command=command,
                invoked_command=command,
                params=params_text,
            )

        # 检查黑名单
        is_blocked, block_reason = self._check_blacklist(data)
        if is_blocked:
            self.logger.info(f"黑名单检查: 被阻止, 原因='{block_reason}', SHOW_REASON={BLACKLIST_SHOW_REASON}")
            log_other_message_if_needed("blacklisted")

            # 可选择性地向用户发送封禁原因（仅在私聊或@消息时）
            self.logger.info(f"事件类型: {event_type}")

            if event_type in [
                "DIRECT_MESSAGE_CREATE", "C2C_MESSAGE_CREATE",
                "AT_MESSAGE_CREATE", "GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE",
            ]:
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
        is_at_message = event_type in ["AT_MESSAGE_CREATE", "GROUP_AT_MESSAGE_CREATE"]
        is_direct_message = event_type in ["DIRECT_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"]
        suppress_invalid_feedback = FULL_MESSAGE_MODE and is_full_group_message

        # 如果不是@消息、私聊消息，且内容不以/开头，则忽略 (避免处理普通群聊消息)
        if not is_at_message and not is_direct_message and not clean_content.startswith('/'):
             self.logger.debug(f"忽略非 / 开头的普通群/频道消息: {clean_content[:50]}...")
             log_other_message_if_needed("non_command_message")
             return False # 表明未处理

        # 处理空内容的情况
        if not clean_content:
            log_other_message_if_needed("empty_message")
            # 只在 @消息 或 私聊 时回复提示
            if is_at_message or is_direct_message:
                response = self._build_help_shortcut_reply(
                    "有什么事嘛？",
                    "点击下方按钮查看可用命令。",
                    user_id=user_id,
                )
                target_id, _ = self._get_channel_id(data)
                if target_id:
                    async def send_empty_reply():
                        try:
                            await self._send_event_response(data, response)
                        except Exception as e:
                            self.logger.error(f"发送空命令提示时出错: {e}")
                            self.logger.error(traceback.format_exc())
                    asyncio.create_task(send_empty_reply())
                    return True
            return False # 其他情况（如空内容的普通群消息）不处理

        # 检查维护模式
        if auth_manager.is_maintenance_mode() and not auth_manager.is_admin(user_id):
            log_other_message_if_needed("maintenance_blocked")
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
        
        # 检查命令前缀和私聊的特殊处理
        if ENFORCE_COMMAND_PREFIX and not command.startswith('/') and not is_direct_message and not is_at_message:
             self.logger.debug(f"忽略非 / 开头的普通群/频道消息 (强制前缀): {command}")
             log_other_message_if_needed("non_prefixed_message", command=command, params_text=params)
             return False # 不处理普通消息
        elif is_direct_message and not command.startswith('/'):
             log_other_message_if_needed("missing_prefix", command=command, params_text=params)
             response = self._build_help_shortcut_reply(
                 "命令必须以 / 开头",
                 "请在命令前加上 `/`，或点击下方按钮查看可用命令。",
                 user_id=user_id,
             )
             target_id, _ = self._get_channel_id(data)
             if target_id:
                  async def send_prefix_reply():
                       try:
                           await self._send_event_response(data, response)
                       except Exception as e:
                            self.logger.error(f"发送命令前缀提示时出错: {e}")
                            self.logger.error(traceback.format_exc())
                  asyncio.create_task(send_prefix_reply())
                  return True
             return False
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
            # 找到插件，启动后台任务处理 (传入实际触发的命令名, 便于多命令插件分辨)
            self.logger.info(f"为命令 '{command}' 找到插件 '{plugin.__class__.__name__}'，创建后台处理任务")
            asyncio.create_task(self._run_plugin_and_reply(plugin, params, user_id, data, invoked_command=command))
            return True # 表示已开始处理
        elif command.lower() == "/help":
            # 特殊处理 /help 命令 - 使用富回复 (markdown + 按钮)
            self.logger.info(f"处理内置 /help 命令, 参数='{params}'")
            stats_manager.log_command("help", user_id, data.get("group_openid"))
            if is_full_group_message:
                message_archive.log_command_message(
                    data,
                    user_id=user_id,
                    group_openid=group_openid,
                    command="help",
                    invoked_command=command,
                    params=params,
                )
            # 解析参数: "管理 2" → path="管理", page=2
            help_path = ""
            help_page = 1
            if params.strip():
                tokens = params.strip().split()
                if len(tokens) > 1 and tokens[-1].isdigit():
                    help_page = int(tokens[-1])
                    help_path = " ".join(tokens[:-1])
                else:
                    help_path = params.strip()

            # 确定回复目标
            message_id = data.get("id")
            target_id, is_group = self._get_channel_id(data)
            if not target_id:
                return False

            help_replies = plugin_manager.get_help_replies(
                path=help_path, page=help_page,
                caller_openid=user_id, is_group=is_group,
            )

            async def send_help_replies():
                for idx, reply in enumerate(help_replies):
                    try:
                        # 第一条用原 message_id 做被动回复, 后续用 msg_seq 递增
                        await self._send_rich_reply(
                            target_id, message_id, is_group, event_type,
                            reply, data, msg_seq=idx + 1,
                        )
                    except Exception as e:
                        self.logger.error(f"发送 /help 第 {idx+1} 条出错: {e}")
                        self.logger.error(traceback.format_exc())
            asyncio.create_task(send_help_replies())
            return True
        else:
            # 未找到插件，也不是 /help
            self.logger.warning(f"未找到命令 '{command}'")
            log_other_message_if_needed("unknown_command", command=command, params_text=params)
            if suppress_invalid_feedback:
                return False
            response_to_send = self._build_help_shortcut_reply(
                "未找到命令",
                f"无法识别 `{command}`。\n\n点击下方按钮查看可用命令。",
                user_id=user_id,
            )

        # 如果有直接响应需要发送 (help 或 not found)
        if response_to_send:
            target_id, _ = self._get_channel_id(data)
            if target_id:
                async def send_direct_reply():
                    try:
                        await self._send_event_response(data, response_to_send)
                        self.logger.info(f"已发送直接回复到 {target_id} (Help/Not Found)")
                    except Exception as e:
                        self.logger.error(f"发送直接回复 (Help/Not Found) 时出错: {e}")
                        self.logger.error(traceback.format_exc())
                asyncio.create_task(send_direct_reply())
                return True
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

    async def _send_rich_reply(self, target_id: str, message_id: Optional[str],
                                is_group: bool, event_type: Optional[str],
                                reply: Reply, event_data: Dict[str, Any],
                                msg_seq: int = 1):
        """渲染 Reply 对象并发送 (走 messages 接口直发, 支持 markdown/keyboard/media)"""
        if reply.is_empty():
            self.logger.warning("Reply 对象为空, 跳过发送")
            return

        import requests
        from auth import auth_manager as _auth

        # 构造 URL
        is_private = self._is_private_message(event_type, target_id)
        if is_group:
            api_url = f"{API_BASE_URL}/v2/groups/{target_id}/messages"
        elif is_private:
            api_url = f"{API_BASE_URL}/v2/users/{target_id}/messages"
        else:
            # 频道 @消息走另一条路径, 不支持 markdown/按钮, 退化为纯文本
            await self._send_reply(target_id, message_id, is_group, event_type,
                                    reply.markdown or reply.text or "(消息)")
            return

        # 构造 payload
        ws_event_id = event_data.get("_ws_event_id") if (not message_id and msg_seq == 1) else None
        payload = reply.to_payload(
            message_id=message_id,
            event_id=ws_event_id,
            msg_seq=msg_seq,
            mention_user_id=self._get_executor_user_id(event_data),
        )

        try:
            headers = _auth.get_auth_header(use_bot_token=True)
            self.logger.info(f"发送富回复: POST {api_url} msg_type={payload.get('msg_type')} msg_seq={msg_seq}")
            resp = await asyncio.to_thread(requests.post, api_url, json=payload, headers=headers)
            self.logger.info(f"响应 {resp.status_code}: {resp.text[:300]}")
            if resp.status_code != 200:
                self.logger.error(f"富回复失败: {resp.text}")
        except Exception as e:
            self.logger.error(f"富回复发送异常: {e}")
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

    # 频道/扩展事件处理方法
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
        """处理交互事件（主要处理按钮 action.type=1 的后端回调）

        事件数据结构示例:
        {
            "id": "interaction_id",
            "chat_type": 0/1/2,         # 0=群 1=频道 2=单聊
            "type": 11,                  # 按钮场景
            "data": {
                "type": 11,
                "resolved": {
                    "button_data": "/help",
                    "button_id": "1",
                    "user_id": "openid"
                }
            },
            "group_openid": "xxx",       # 群聊时
            ...
        }
        """
        self.logger.info(f"收到交互事件: {event_data}")

        data = event_data.get("data", {}) or {}
        resolved = data.get("resolved", {}) or {}
        button_data = resolved.get("button_data", "")
        button_id = resolved.get("button_id", "")
        clicker_user_id = (
            resolved.get("user_id")
            or event_data.get("group_member_openid")
            or event_data.get("user_openid")
            or ""
        )
        interaction_id = event_data.get("id")
        # 真正用于被动消息 event_id 的是 WebSocket dispatch 顶层 id, 而非 interaction 自己的 id
        ws_event_id = event_data.get("_ws_event_id") or interaction_id
        # chat_type: 0=频道, 1=群聊, 2=单聊
        chat_type = event_data.get("chat_type")
        group_openid = event_data.get("group_openid")

        self.logger.info(
            f"按钮回调: button_id={button_id}, data='{button_data}', "
            f"user={clicker_user_id}, chat_type={chat_type}, group={group_openid}"
        )

        # 必须立即 ACK, 否则 QQ 客户端会一直 loading 直到超时
        if interaction_id:
            asyncio.create_task(self._ack_interaction(interaction_id, code=0))

        if not button_data:
            return True

        # 把 button_data 当成命令处理
        cmd_text = button_data.strip()
        parts = cmd_text.split(' ', 1)
        cmd = parts[0]
        params = parts[1] if len(parts) > 1 else ""

        # 查找插件
        plugin = plugin_manager.get_plugin(cmd)
        if not plugin and cmd.startswith('/'):
            plugin = plugin_manager.get_plugin(cmd[1:])

        # 执行命令
        response = None
        try:
            if plugin:
                response = await plugin.handle(
                    params, clicker_user_id,
                    group_openid=group_openid, event_data=event_data,
                    invoked_command=cmd,
                )
            elif cmd.lower() == "/help":
                # /help 走富回复 (可能是多条)
                help_path = ""
                help_page = 1
                if params.strip():
                    tokens = params.strip().split()
                    if len(tokens) > 1 and tokens[-1].isdigit():
                        help_page = int(tokens[-1])
                        help_path = " ".join(tokens[:-1])
                    else:
                        help_path = params.strip()
                # 按钮回调里判断 group/single (chat_type=0 群, 1 频道, 2 单聊)
                is_grp = bool(group_openid)
                response = plugin_manager.get_help_replies(
                    path=help_path, page=help_page,
                    caller_openid=clicker_user_id, is_group=is_grp,
                )
            else:
                response = self._build_help_shortcut_reply(
                    "未找到命令",
                    f"无法识别 `{cmd}`。\n\n点击下方按钮查看可用命令。",
                    user_id=clicker_user_id,
                )
        except Exception as e:
            self.logger.error(f"按钮回调执行命令异常: {e}")
            self.logger.error(traceback.format_exc())
            response = f"执行命令出错: {e}"

        if not response:
            return True

        # 发送回响应。按钮交互没有 message_id, 用 event_id 绑定前置事件作为被动消息
        try:
            # Reply 富回复 vs 字符串响应
            # 解析 API URL (按钮回调没有 message_id, 一律走 event_id 通道)
            if group_openid:
                api_url = f"{API_BASE_URL}/v2/groups/{group_openid}/messages"
            elif clicker_user_id:
                api_url = f"{API_BASE_URL}/v2/users/{clicker_user_id}/messages"
            else:
                self.logger.warning("按钮回调无法确定回复目标")
                return True

            import requests
            from auth import auth_manager as _auth
            headers = _auth.get_auth_header(use_bot_token=True)

            # 统一成 List[Reply] / List[str] 处理
            responses = response if isinstance(response, list) else [response]
            for idx, item in enumerate(responses):
                if isinstance(item, Reply):
                    # 按钮回调没有 message_id, 走 event_id; 多条时 event_id 只能用一次
                    # 后续条目使用主动消息(放弃 event_id 绑定)
                    use_event_id = ws_event_id if idx == 0 else None
                    payload = item.to_payload(event_id=use_event_id, mention_user_id=clicker_user_id)
                    self.logger.info(f"按钮回调富回复 #{idx+1}: POST {api_url} msg_type={payload.get('msg_type')}")
                    resp = await asyncio.to_thread(requests.post, api_url, json=payload, headers=headers)
                    self.logger.info(f"响应 {resp.status_code}: {resp.text[:300]}")
                else:
                    # 字符串响应
                    text = str(item)
                    use_event_id = ws_event_id if idx == 0 else None
                    await asyncio.to_thread(
                        self._send_interaction_reply, api_url, use_event_id, text
                    )
        except Exception as e:
            self.logger.error(f"按钮回调响应发送失败: {e}")
            self.logger.error(traceback.format_exc())

        return True

    def _send_interaction_reply(self, api_url: str, event_id: str, content: str):
        """按钮回调专用: 用 event_id 发送被动文本消息"""
        import requests
        from auth import auth_manager as _auth
        headers = _auth.get_auth_header(use_bot_token=True)
        data = {
            "msg_type": 0,
            "content": content,
        }
        if event_id:
            data["event_id"] = event_id
        self.logger.info(f"按钮回调响应: POST {api_url} data={data}")
        resp = requests.post(api_url, headers=headers, json=data)
        self.logger.info(f"响应 {resp.status_code}: {resp.text}")
        if resp.status_code != 200:
            raise Exception(f"API {resp.status_code}: {resp.text}")
        return resp.json()

    async def _ack_interaction(self, interaction_id: str, code: int = 0):
        """ACK 按钮交互事件 (否则客户端 loading 直到超时)

        code: 0=成功, 1=失败, 2=频繁, 3=重复, 4=无权限, 5=仅管理员
        """
        import requests
        from auth import auth_manager as _auth
        try:
            url = f"{API_BASE_URL}/interactions/{interaction_id}"
            headers = _auth.get_auth_header(use_bot_token=True)
            self.logger.info(f"ACK interaction: PUT {url} code={code}")
            resp = await asyncio.to_thread(
                requests.put, url, json={"code": code}, headers=headers
            )
            self.logger.info(f"ACK 响应 {resp.status_code}: {resp.text[:200]}")
            if resp.status_code != 200:
                self.logger.warning(f"ACK 失败: {resp.text}")
        except Exception as e:
            self.logger.error(f"ACK interaction 异常: {e}")

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
