from abc import ABC, abstractmethod
import asyncio
import base64
import logging
import os
from typing import Any, Dict, List, Optional, Union

import requests

from reply import Reply

logger = logging.getLogger("base_plugin")


class BasePlugin(ABC):
    """插件基类。

    框架便利方法 (子类继承即可用, 无需 import):
        at_user(openid)              - 返回 @用户 标签
        get_avatar_url(openid)       - 返回用户头像 URL
        async upload_image(...)      - 上传图片到 QQ 服务器, 返回 file_info
        async send_text(...)         - 发送纯文本
        async send_markdown(...)     - 发送 markdown (可带按钮)
        async send_image(...)        - 一站式发图 (自动上传)
        async reply_with(reply, event_data)  - 用 Reply 对象自动推断目标并发送

    handle() 可返回 str (纯文本) 或 Reply 对象, 框架会自动渲染。
    """

    def __init__(
        self,
        command,
        description: str,
        is_builtin: bool = False,
        hidden: bool = False,
        category: Optional[str] = None,
        display_name: Optional[str] = None,
    ):
        """
        Args:
            command: 触发命令名, 可以是单字符串 (如 "foo") 或字符串列表 (如 ["foo", "f"])
                     多命令时第一个为主命令 (用于 /help 显示), 其余为别名, 全部共享 handle()
                     插件可通过 kwargs['invoked_command'] 知道本次是哪个命令触发的
            description: 命令描述
            is_builtin: 是否内置插件
            hidden: 是否在 /help 隐藏
            category: 分类路径, 用 "/" 分隔层级 (如 "管理/用户")
                     未指定时默认 "其他"; 若插件在子目录中, 自动用子目录名作为默认 category
            display_name: /help 菜单中显示的中文简称, 未指定时回退到主命令
        """
        # 支持单命令或命令列表
        if isinstance(command, (list, tuple)):
            if not command:
                raise ValueError("command 列表不能为空")
            self.commands: List[str] = [str(c) for c in command]
        else:
            self.commands = [str(command)]
        # 主命令 (兼容旧接口)
        self.command: str = self.commands[0]

        self.description = description
        self.is_builtin = is_builtin
        self.hidden = hidden
        # 默认分类: "其他" (内置插件如需归入"管理"等需显式指定)
        self.category = category or "其他"
        self.display_name = display_name  # 可能为 None
        self.logger = logging.getLogger(f"plugin.{self.command}")

    def get_display_name(self) -> str:
        """返回 /help 显示用的友好名称, 未定义 display_name 时回退到 command"""
        return self.display_name or self.command

    # ---------- 权限快捷方法 ----------

    def is_admin(self, user_id: Optional[str]) -> bool:
        """当前用户是否机器人 admin (复用 auth_manager.is_admin)"""
        from auth_manager import auth_manager
        return bool(user_id) and auth_manager.is_admin(user_id)

    def check_user_allowed(self, user_id: Optional[str], allowed_user_ids: List[str]) -> bool:
        """命令是否对指定用户列表开放 (空列表 = 不限制)"""
        if not allowed_user_ids:
            return True
        return bool(user_id) and user_id in allowed_user_ids

    def check_group_allowed(self, group_openid: Optional[str], allowed_group_ids: List[str]) -> bool:
        """命令是否对指定群列表开放 (空列表 = 不限制)"""
        if not allowed_group_ids:
            return True
        return bool(group_openid) and group_openid in allowed_group_ids

    def require_admin(self, user_id: Optional[str], error_msg: str = "您没有权限执行此命令") -> Optional[str]:
        """便利拦截方法: 在 handle() 开头调用, 非管理员返回错误信息

        用法:
            err = self.require_admin(user_id)
            if err: return err
            # ... 正常逻辑
        """
        if not self.is_admin(user_id):
            return error_msg
        return None

    def require_users(self, user_id: Optional[str], allowed_user_ids: List[str],
                       error_msg: str = "您没有权限执行此命令") -> Optional[str]:
        """便利拦截: 限定调用用户白名单"""
        if not self.check_user_allowed(user_id, allowed_user_ids):
            return error_msg
        return None

    def require_groups(self, group_openid: Optional[str], allowed_group_ids: List[str],
                        error_msg: str = "本命令在此群不可用") -> Optional[str]:
        """便利拦截: 限定群白名单 (私聊场景该限制不生效)"""
        if group_openid is None:
            return None  # 私聊不受群限制约束
        if not self.check_group_allowed(group_openid, allowed_group_ids):
            return error_msg
        return None

    @abstractmethod
    async def handle(
        self, params: str, user_id: str = None, group_openid: str = None, **kwargs
    ) -> Union[str, Reply, List[Union[str, Reply]], None]:
        """处理命令。

        返回:
            str: 作为纯文本回复
            Reply: 富回复 (markdown/按钮/媒体)
            List[str | Reply]: 多条消息按顺序发送
            None: 不发送回复 (插件已自行发送)
        """
        pass

    def help(self) -> str:
        return f"{self.command} - {self.description}"

    # ---------- 框架便利方法 ----------

    def at_user(self, openid: str) -> str:
        """返回 @用户 标签 (可用于 text/markdown content)"""
        return f'<qqbot-at-user id="{openid}" />'

    def get_avatar_url(self, openid: str) -> str:
        """返回用户头像 URL (q.qlogo.cn, QQ 域, 可直接在 markdown 内嵌)"""
        from config import BOT_APPID
        return f"https://q.qlogo.cn/qqapp/{BOT_APPID}/{openid}/640"

    # ---------- 异步 HTTP 工具 ----------

    def _api_base(self):
        from config import API_BASE_URL
        return API_BASE_URL

    def _auth_headers(self):
        from auth import auth_manager
        return auth_manager.get_auth_header(use_bot_token=True)

    def _messages_url(self, target_id: str, is_group: bool) -> str:
        base = self._api_base()
        if is_group:
            return f"{base}/v2/groups/{target_id}/messages"
        return f"{base}/v2/users/{target_id}/messages"

    def _files_url(self, target_id: str, is_group: bool) -> str:
        base = self._api_base()
        if is_group:
            return f"{base}/v2/groups/{target_id}/files"
        return f"{base}/v2/users/{target_id}/files"

    def _do_post(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """同步 POST (在线程池中调用)。"""
        headers = self._auth_headers()
        # 日志中 base64 字段做长度占位
        log_data = {
            k: (f"<base64 {len(v)} chars>" if k == "file_data" and isinstance(v, str) else v)
            for k, v in data.items()
        }
        self.logger.info(f"POST {url} data={log_data}")
        resp = requests.post(url, headers=headers, json=data)
        self.logger.info(f"响应 {resp.status_code}: {resp.text[:300]}")
        if resp.status_code != 200:
            raise Exception(f"API {resp.status_code}: {resp.text}")
        return resp.json()

    async def upload_image(
        self,
        target_id: str,
        is_group: bool,
        *,
        url: Optional[str] = None,
        file_path: Optional[str] = None,
        file_data_b64: Optional[str] = None,
    ) -> str:
        """上传图片到 QQ 服务器, 返回 file_info 字符串。

        三选一参数 (优先级 file_data_b64 > file_path > url):
            url: 公网图片 URL
            file_path: 本地文件路径 (自动读取并 base64)
            file_data_b64: 已 base64 编码的图片数据
        """
        if file_path and not file_data_b64:
            with open(file_path, "rb") as f:
                file_data_b64 = base64.b64encode(f.read()).decode("utf-8")

        if not (url or file_data_b64):
            raise ValueError("upload_image 至少需要 url 或 file_path 或 file_data_b64")

        api_url = self._files_url(target_id, is_group)
        data: Dict[str, Any] = {"file_type": 1, "srv_send_msg": False}
        if file_data_b64:
            data["file_data"] = file_data_b64
        if url:
            data["url"] = url

        result = await asyncio.to_thread(self._do_post, api_url, data)
        file_info = result.get("file_info")
        if not file_info:
            raise Exception(f"上传后未返回 file_info: {result}")
        return file_info

    async def send_text(
        self,
        target_id: str,
        content: str,
        *,
        is_group: bool = False,
        message_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """发送纯文本消息。"""
        data: Dict[str, Any] = {"msg_type": 0, "content": content}
        if message_id:
            data["msg_id"] = message_id
        if event_id:
            data["event_id"] = event_id
        return await asyncio.to_thread(self._do_post, self._messages_url(target_id, is_group), data)

    async def send_markdown(
        self,
        target_id: str,
        md_content: str,
        *,
        keyboard: Optional[Dict[str, Any]] = None,
        is_group: bool = False,
        message_id: Optional[str] = None,
        event_id: Optional[str] = None,
        msg_seq: int = 1,
    ) -> Dict[str, Any]:
        """发送 markdown 消息, 可选附加按钮。"""
        data: Dict[str, Any] = {
            "msg_type": 2,
            "content": " ",
            "markdown": {"content": md_content},
        }
        if keyboard:
            data["keyboard"] = keyboard
        if message_id:
            data["msg_id"] = message_id
            data["msg_seq"] = msg_seq
        if event_id:
            data["event_id"] = event_id
        return await asyncio.to_thread(self._do_post, self._messages_url(target_id, is_group), data)

    async def send_image(
        self,
        target_id: str,
        *,
        url: Optional[str] = None,
        file_path: Optional[str] = None,
        file_data_b64: Optional[str] = None,
        content: str = "",
        is_group: bool = False,
        message_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """一站式发图: 自动上传 + 发送富媒体消息。"""
        file_info = await self.upload_image(
            target_id, is_group, url=url, file_path=file_path, file_data_b64=file_data_b64
        )
        data: Dict[str, Any] = {
            "msg_type": 7,
            "content": content,
            "media": {"file_info": file_info},
        }
        if message_id:
            data["msg_id"] = message_id
        if event_id:
            data["event_id"] = event_id
        return await asyncio.to_thread(self._do_post, self._messages_url(target_id, is_group), data)

    async def reply_with(
        self, reply: Reply, event_data: Dict[str, Any], msg_seq: int = 1
    ) -> Optional[Dict[str, Any]]:
        """根据 event_data 自动推断目标, 发送 Reply 对象。

        适合插件想直接发送多条消息时使用。
        """
        if reply.is_empty():
            return None
        target_id, target_kind = self._resolve_target_from_event(event_data)
        if not target_id:
            self.logger.warning("reply_with: 无法从 event_data 推断目标")
            return None

        message_id, event_id = self._resolve_reply_binding_from_event(event_data)

        # 频道消息不走 v2/groups 或 v2/users，且 markdown/按钮会退化为纯文本。
        if target_kind == "channel":
            from message import MessageSender

            text = reply.markdown or reply.text or "(消息)"
            if message_id:
                return await asyncio.to_thread(
                    MessageSender.reply_message, target_id, message_id, "text", text, False
                )
            return await asyncio.to_thread(
                MessageSender.send_message, target_id, "text", text, False
            )

        payload = reply.to_payload(message_id=message_id, event_id=event_id, msg_seq=msg_seq)
        return await asyncio.to_thread(
            self._do_post, self._messages_url(target_id, target_kind == "group"), payload
        )

    def _resolve_target_from_event(self, event_data: Dict[str, Any]):
        """从事件数据推断 (target_id, target_kind)。"""
        group_openid = event_data.get("group_openid")
        if group_openid:
            return group_openid, "group"
        channel_id = event_data.get("channel_id")
        if channel_id:
            return channel_id, "channel"
        author = event_data.get("author", {}) or {}
        user_openid = (
            author.get("user_openid")
            or author.get("id")
            or author.get("openid")
            or event_data.get("openid")
            or event_data.get("group_member_openid")
        )
        if user_openid:
            return user_openid, "private"
        return None, None

    def _resolve_reply_binding_from_event(self, event_data: Dict[str, Any]):
        """从事件数据推断被动消息绑定字段。"""
        if event_data.get("type") == "INTERACTION_CREATE":
            return None, event_data.get("_ws_event_id") or event_data.get("id")
        return event_data.get("id"), event_data.get("_ws_event_id")
