"""
黑名单管理器
管理用户和群组黑名单，提供添加、删除、查询等功能
"""

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from config import BLACKLIST_AUTO_SAVE, BLACKLIST_LOG_BLOCKED
from framework_db import framework_db


logger = logging.getLogger("blacklist_manager")

BLACKLIST_MIGRATION_KEY = "blacklist_relational_migrated_v1"


class BlacklistType(Enum):
    USER = "user"
    GROUP = "group"


@dataclass
class BlacklistEntry:
    id: str
    type: BlacklistType
    reason: str
    added_by: str
    added_time: str
    expires_at: Optional[str] = None

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            expire_time = datetime.fromisoformat(self.expires_at)
            return datetime.now() > expire_time
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlacklistEntry":
        payload = dict(data)
        payload["type"] = BlacklistType(payload["type"])
        return cls(**payload)


class BlacklistManager:
    def __init__(self, data_file: str = "blacklist.json", auto_save: bool = None):
        self.data_file = data_file
        self.auto_save = BLACKLIST_AUTO_SAVE if auto_save is None else auto_save
        self.log_blocked = BLACKLIST_LOG_BLOCKED
        self._lock = threading.RLock()
        self._migrate_if_needed()

    def _migrate_if_needed(self):
        if framework_db.meta_get_bool(BLACKLIST_MIGRATION_KEY, False):
            return

        legacy_entries = self._load_legacy_entries()
        count_row = framework_db.fetchone("SELECT COUNT(*) AS count FROM blacklist_entries")
        has_new_data = bool(count_row and int(count_row["count"]) > 0)

        if not legacy_entries and has_new_data:
            framework_db.meta_set(BLACKLIST_MIGRATION_KEY, True)
            return

        if not legacy_entries:
            framework_db.meta_set(BLACKLIST_MIGRATION_KEY, True)
            return

        self.logger.info(f"开始迁移黑名单数据到 sqlite: entries={len(legacy_entries)}")

        with framework_db.transaction() as conn:
            conn.execute("DELETE FROM blacklist_entries")
            for entry in legacy_entries:
                conn.execute(
                    """
                    INSERT INTO blacklist_entries(
                        target_id, target_type, reason, added_by, added_time, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        entry.type.value,
                        entry.reason,
                        entry.added_by,
                        entry.added_time,
                        entry.expires_at,
                    ),
                )
            conn.execute(
                """
                INSERT INTO schema_meta(key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (BLACKLIST_MIGRATION_KEY, "1"),
            )

        framework_db.cleanup_legacy_kv_namespaces(["blacklist"])
        self.logger.info(f"黑名单数据迁移完成: entries={len(legacy_entries)}")

    def _load_legacy_entries(self) -> List[BlacklistEntry]:
        raw_entries = framework_db.legacy_kv_get_namespace("blacklist")
        if raw_entries:
            entries: List[BlacklistEntry] = []
            for entry_data in raw_entries.values():
                try:
                    entries.append(BlacklistEntry.from_dict(entry_data))
                except Exception as e:
                    logger.error(f"读取旧 framework_kv 黑名单条目失败: {e}")
            if entries:
                logger.info(f"从旧 framework_kv 迁移 {len(entries)} 个黑名单条目")
                return entries

        if not os.path.exists(self.data_file):
            return []

        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries = []
            for entry_data in data.get("blacklist", []):
                try:
                    entries.append(BlacklistEntry.from_dict(entry_data))
                except Exception as e:
                    logger.error(f"读取旧 JSON 黑名单条目失败: {e}")
            if entries:
                logger.info(f"从旧 JSON 迁移 {len(entries)} 个黑名单条目")
            return entries
        except Exception as e:
            logger.error(f"读取旧黑名单文件失败: {e}")
            return []

    def _cleanup_expired(self):
        framework_db.execute(
            "DELETE FROM blacklist_entries WHERE expires_at IS NOT NULL AND expires_at < ?",
            (datetime.now().isoformat(),),
        )

    def _row_to_entry(self, row) -> BlacklistEntry:
        return BlacklistEntry(
            id=str(row["target_id"]),
            type=BlacklistType(str(row["target_type"])),
            reason=str(row["reason"]),
            added_by=str(row["added_by"]),
            added_time=str(row["added_time"]),
            expires_at=row["expires_at"],
        )

    def _add_entry(
        self,
        target_id: str,
        entry_type: BlacklistType,
        reason: str,
        added_by: str,
        expires_at: Optional[str] = None,
    ) -> bool:
        with self._lock:
            self._cleanup_expired()
            existing = framework_db.fetchone(
                "SELECT 1 FROM blacklist_entries WHERE target_id = ?",
                (target_id,),
            )
            if existing:
                logger.warning(f"{entry_type.value} {target_id} 已在黑名单中")
                return False

            framework_db.execute(
                """
                INSERT INTO blacklist_entries(
                    target_id, target_type, reason, added_by, added_time, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    target_id,
                    entry_type.value,
                    reason,
                    added_by,
                    datetime.now().isoformat(),
                    expires_at,
                ),
            )
            logger.info(f"已添加{entry_type.value}到黑名单: {target_id}, 原因: {reason}")
            return True

    def add_user(self, user_id: str, reason: str, added_by: str, expires_at: Optional[str] = None) -> bool:
        return self._add_entry(user_id, BlacklistType.USER, reason, added_by, expires_at)

    def add_group(self, group_id: str, reason: str, added_by: str, expires_at: Optional[str] = None) -> bool:
        return self._add_entry(group_id, BlacklistType.GROUP, reason, added_by, expires_at)

    def _remove_entry(self, target_id: str, entry_type: BlacklistType) -> bool:
        with self._lock:
            row = framework_db.fetchone(
                "SELECT target_type FROM blacklist_entries WHERE target_id = ?",
                (target_id,),
            )
            if not row:
                logger.warning(f"{entry_type.value} {target_id} 不在黑名单中")
                return False
            if str(row["target_type"]) != entry_type.value:
                logger.warning(f"类型不匹配: {target_id} 不是 {entry_type.value}")
                return False

            framework_db.execute("DELETE FROM blacklist_entries WHERE target_id = ?", (target_id,))
            logger.info(f"已从黑名单移除{entry_type.value}: {target_id}")
            return True

    def remove_user(self, user_id: str) -> bool:
        return self._remove_entry(user_id, BlacklistType.USER)

    def remove_group(self, group_id: str) -> bool:
        return self._remove_entry(group_id, BlacklistType.GROUP)

    def _is_blocked(self, target_id: str, entry_type: BlacklistType) -> bool:
        with self._lock:
            self._cleanup_expired()
            row = framework_db.fetchone(
                """
                SELECT target_id, target_type, reason, added_by, added_time, expires_at
                FROM blacklist_entries
                WHERE target_id = ? AND target_type = ?
                """,
                (target_id, entry_type.value),
            )
            if not row:
                return False

            if self.log_blocked:
                logger.info(f"已阻止{entry_type.value}访问: {target_id}, 原因: {row['reason']}")
            return True

    def is_user_blocked(self, user_id: str) -> bool:
        return self._is_blocked(user_id, BlacklistType.USER)

    def is_group_blocked(self, group_id: str) -> bool:
        return self._is_blocked(group_id, BlacklistType.GROUP)

    def get_entry(self, target_id: str) -> Optional[BlacklistEntry]:
        self._cleanup_expired()
        row = framework_db.fetchone(
            """
            SELECT target_id, target_type, reason, added_by, added_time, expires_at
            FROM blacklist_entries
            WHERE target_id = ?
            """,
            (target_id,),
        )
        return self._row_to_entry(row) if row else None

    def _list_entries(self, entry_type: BlacklistType) -> List[BlacklistEntry]:
        self._cleanup_expired()
        rows = framework_db.fetchall(
            """
            SELECT target_id, target_type, reason, added_by, added_time, expires_at
            FROM blacklist_entries
            WHERE target_type = ?
            ORDER BY added_time DESC
            """,
            (entry_type.value,),
        )
        return [self._row_to_entry(row) for row in rows]

    def list_users(self) -> List[BlacklistEntry]:
        return self._list_entries(BlacklistType.USER)

    def list_groups(self) -> List[BlacklistEntry]:
        return self._list_entries(BlacklistType.GROUP)

    def get_stats(self) -> Dict[str, int]:
        self._cleanup_expired()
        rows = framework_db.fetchall(
            "SELECT target_type, COUNT(*) AS count FROM blacklist_entries GROUP BY target_type"
        )
        by_type = {str(row["target_type"]): int(row["count"]) for row in rows}
        total = sum(by_type.values())
        temporary_row = framework_db.fetchone(
            "SELECT COUNT(*) AS count FROM blacklist_entries WHERE expires_at IS NOT NULL"
        )
        temporary = int(temporary_row["count"]) if temporary_row else 0
        return {
            "total": total,
            "users": by_type.get("user", 0),
            "groups": by_type.get("group", 0),
            "temporary": temporary,
        }

    def clear_all(self) -> int:
        with self._lock:
            row = framework_db.fetchone("SELECT COUNT(*) AS count FROM blacklist_entries")
            count = int(row["count"]) if row else 0
            framework_db.execute("DELETE FROM blacklist_entries")
            logger.info(f"已清空所有黑名单条目，共 {count} 个")
            return count

    def save(self):
        # 关系表模式为即时写入，这里保留兼容接口。
        self._cleanup_expired()


blacklist_manager = BlacklistManager()
