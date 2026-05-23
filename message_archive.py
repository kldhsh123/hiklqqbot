import json
import logging
import os
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Optional

from config import LOG_DIR


class MessageArchive:
    """按消息类型归档全量群消息原始内容。"""

    def __init__(self, log_dir: str = LOG_DIR):
        self.logger = logging.getLogger("message_archive")
        self.log_dir = log_dir
        self.command_dir = os.path.join(log_dir, "command_messages")
        self.other_dir = os.path.join(log_dir, "other_messages")
        self._lock = Lock()
        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(self.command_dir, exist_ok=True)
        os.makedirs(self.other_dir, exist_ok=True)

    def _get_file_path(self, category: str) -> str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        base_dir = self.command_dir if category == "command" else self.other_dir
        return os.path.join(base_dir, f"{date_str}.jsonl")

    def _build_entry(
        self,
        category: str,
        event_data: Dict[str, Any],
        user_id: Optional[str] = None,
        group_openid: Optional[str] = None,
        command: Optional[str] = None,
        invoked_command: Optional[str] = None,
        params: str = "",
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        author = event_data.get("author") or {}
        member = event_data.get("member") or {}
        return {
            "archived_at": datetime.now().isoformat(timespec="seconds"),
            "category": category,
            "reason": reason,
            "event_type": event_data.get("type"),
            "event_id": event_data.get("id"),
            "event_timestamp": event_data.get("timestamp"),
            "group_openid": group_openid or event_data.get("group_openid"),
            "channel_id": event_data.get("channel_id"),
            "guild_id": event_data.get("guild_id"),
            "user_id": user_id,
            "username": author.get("username"),
            "member_nick": member.get("nick"),
            "command": command,
            "invoked_command": invoked_command,
            "params": params,
            "raw_content": event_data.get("content", ""),
            "event_data": event_data,
        }

    def _append_entry(self, category: str, entry: Dict[str, Any]):
        try:
            self._ensure_dirs()
            file_path = self._get_file_path(category)
            line = json.dumps(entry, ensure_ascii=False, default=str)
            with self._lock:
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception as e:
            self.logger.error(f"写入消息归档失败: {e}")

    def log_command_message(
        self,
        event_data: Dict[str, Any],
        user_id: Optional[str] = None,
        group_openid: Optional[str] = None,
        command: Optional[str] = None,
        invoked_command: Optional[str] = None,
        params: str = "",
    ):
        entry = self._build_entry(
            "command",
            event_data,
            user_id=user_id,
            group_openid=group_openid,
            command=command,
            invoked_command=invoked_command,
            params=params,
        )
        self._append_entry("command", entry)

    def log_other_message(
        self,
        event_data: Dict[str, Any],
        user_id: Optional[str] = None,
        group_openid: Optional[str] = None,
        reason: Optional[str] = None,
        command: Optional[str] = None,
        invoked_command: Optional[str] = None,
        params: str = "",
    ):
        entry = self._build_entry(
            "other",
            event_data,
            user_id=user_id,
            group_openid=group_openid,
            command=command,
            invoked_command=invoked_command,
            params=params,
            reason=reason,
        )
        self._append_entry("other", entry)


message_archive = MessageArchive()
