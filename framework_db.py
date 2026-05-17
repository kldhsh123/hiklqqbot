import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterable, Optional

from config import FRAMEWORK_DB_PATH


logger = logging.getLogger("framework_db")


class FrameworkDatabase:
    """框架内部 sqlite3 访问层。"""

    def __init__(self, db_path: str = FRAMEWORK_DB_PATH):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_connection()
        self._ensure_schema()

    def _ensure_connection(self):
        if self._conn is not None:
            return

        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA temp_store=MEMORY")
            self._conn.execute("PRAGMA busy_timeout=5000")

    def _ensure_schema(self):
        schema = """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS admins (
            user_id TEXT PRIMARY KEY,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS maintenance_state (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            enabled INTEGER NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS blacklist_entries (
            target_id TEXT PRIMARY KEY,
            target_type TEXT NOT NULL CHECK(target_type IN ('user', 'group')),
            reason TEXT NOT NULL,
            added_by TEXT NOT NULL,
            added_time TEXT NOT NULL,
            expires_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_blacklist_type ON blacklist_entries(target_type);

        CREATE TABLE IF NOT EXISTS stats_users (
            user_openid TEXT PRIMARY KEY,
            first_seen REAL NOT NULL,
            last_active REAL NOT NULL,
            username TEXT,
            avatar TEXT,
            is_friend INTEGER NOT NULL DEFAULT 1,
            can_send_proactive_msg INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_stats_users_last_active ON stats_users(last_active DESC);

        CREATE TABLE IF NOT EXISTS stats_user_name_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_openid TEXT NOT NULL,
            name TEXT NOT NULL,
            first_seen REAL NOT NULL,
            last_active REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_stats_user_name_history
            ON stats_user_name_history(user_openid, first_seen DESC);

        CREATE TABLE IF NOT EXISTS stats_groups (
            group_openid TEXT PRIMARY KEY,
            join_time REAL NOT NULL,
            last_active REAL NOT NULL,
            added_by TEXT,
            group_name TEXT,
            can_send_proactive_msg INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_stats_groups_last_active ON stats_groups(last_active DESC);

        CREATE TABLE IF NOT EXISTS stats_group_name_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_openid TEXT NOT NULL,
            name TEXT NOT NULL,
            first_seen REAL NOT NULL,
            last_active REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_stats_group_name_history
            ON stats_group_name_history(group_openid, first_seen DESC);

        CREATE TABLE IF NOT EXISTS stats_group_members (
            group_openid TEXT NOT NULL,
            user_openid TEXT NOT NULL,
            joined_at REAL NOT NULL,
            PRIMARY KEY (group_openid, user_openid)
        );
        CREATE INDEX IF NOT EXISTS idx_stats_group_members_group
            ON stats_group_members(group_openid, user_openid);
        CREATE INDEX IF NOT EXISTS idx_stats_group_members_user
            ON stats_group_members(user_openid, group_openid);

        CREATE TABLE IF NOT EXISTS display_id_mappings (
            id_type TEXT NOT NULL CHECK(id_type IN ('users', 'groups')),
            real_id TEXT NOT NULL,
            display_id TEXT NOT NULL,
            PRIMARY KEY (id_type, real_id),
            UNIQUE(display_id)
        );
        CREATE INDEX IF NOT EXISTS idx_display_id_lookup ON display_id_mappings(display_id);

        CREATE TABLE IF NOT EXISTS usage_summary (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            total_messages INTEGER NOT NULL DEFAULT 0,
            command_messages INTEGER NOT NULL DEFAULT 0,
            other_messages INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS command_usage (
            command TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS entity_usage (
            entity_type TEXT NOT NULL CHECK(entity_type IN ('user', 'group')),
            entity_id TEXT NOT NULL,
            total_messages INTEGER NOT NULL DEFAULT 0,
            command_messages INTEGER NOT NULL DEFAULT 0,
            other_messages INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (entity_type, entity_id)
        );
        CREATE INDEX IF NOT EXISTS idx_entity_usage_total
            ON entity_usage(entity_type, total_messages DESC);

        CREATE TABLE IF NOT EXISTS time_usage (
            period_type TEXT NOT NULL CHECK(period_type IN ('daily', 'weekly', 'monthly')),
            period_key TEXT NOT NULL,
            total_messages INTEGER NOT NULL DEFAULT 0,
            command_messages INTEGER NOT NULL DEFAULT 0,
            other_messages INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (period_type, period_key)
        );
        CREATE INDEX IF NOT EXISTS idx_time_usage_period
            ON time_usage(period_type, period_key);

        CREATE TABLE IF NOT EXISTS time_command_usage (
            period_type TEXT NOT NULL CHECK(period_type IN ('daily', 'weekly', 'monthly')),
            period_key TEXT NOT NULL,
            command TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (period_type, period_key, command)
        );
        CREATE INDEX IF NOT EXISTS idx_time_command_usage_lookup
            ON time_command_usage(period_type, period_key, count DESC);

        CREATE TABLE IF NOT EXISTS time_entity_usage (
            period_type TEXT NOT NULL CHECK(period_type IN ('daily', 'weekly', 'monthly')),
            period_key TEXT NOT NULL,
            entity_type TEXT NOT NULL CHECK(entity_type IN ('user', 'group')),
            entity_id TEXT NOT NULL,
            total_messages INTEGER NOT NULL DEFAULT 0,
            command_messages INTEGER NOT NULL DEFAULT 0,
            other_messages INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (period_type, period_key, entity_type, entity_id)
        );
        CREATE INDEX IF NOT EXISTS idx_time_entity_usage_lookup
            ON time_entity_usage(period_type, period_key, entity_type, total_messages DESC);
        """

        with self._lock, self._conn:
            self._conn.executescript(schema)
            self._conn.execute(
                """
                INSERT INTO maintenance_state(id, enabled, updated_at)
                VALUES (1, 0, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (time.time(),),
            )
            self._conn.execute(
                """
                INSERT INTO usage_summary(id, total_messages, command_messages, other_messages)
                VALUES (1, 0, 0, 0)
                ON CONFLICT(id) DO NOTHING
                """
            )

    @contextmanager
    def transaction(self):
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def execute(self, sql: str, params: Iterable[Any] = ()):
        with self._lock, self._conn:
            return self._conn.execute(sql, tuple(params))

    def executemany(self, sql: str, seq_of_params: Iterable[Iterable[Any]]):
        with self._lock, self._conn:
            return self._conn.executemany(sql, list(seq_of_params))

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, tuple(params)).fetchone()

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, tuple(params)).fetchall()

    def table_exists(self, table_name: str) -> bool:
        row = self.fetchone(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        )
        return row is not None

    def meta_get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.fetchone("SELECT value FROM schema_meta WHERE key = ?", (key,))
        return row["value"] if row else default

    def meta_get_bool(self, key: str, default: bool = False) -> bool:
        value = self.meta_get(key)
        if value is None:
            return default
        return str(value).lower() in {"1", "true", "yes", "on"}

    def meta_set(self, key: str, value: Any):
        self.execute(
            """
            INSERT INTO schema_meta(key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, str(value)),
        )

    def legacy_kv_get(self, namespace: str, key: str, default: Any = None) -> Any:
        if not self.table_exists("framework_kv"):
            return default
        row = self.fetchone(
            "SELECT payload FROM framework_kv WHERE namespace = ? AND key = ?",
            (namespace, key),
        )
        if not row:
            return default
        try:
            return json.loads(row["payload"])
        except json.JSONDecodeError:
            logger.error(f"读取旧 framework_kv 失败: namespace={namespace}, key={key}")
            return default

    def legacy_kv_get_namespace(self, namespace: str) -> Dict[str, Any]:
        if not self.table_exists("framework_kv"):
            return {}
        rows = self.fetchall(
            "SELECT key, payload FROM framework_kv WHERE namespace = ?",
            (namespace,),
        )
        result: Dict[str, Any] = {}
        for row in rows:
            try:
                result[row["key"]] = json.loads(row["payload"])
            except json.JSONDecodeError:
                logger.error(f"读取旧 framework_kv 条目失败: namespace={namespace}, key={row['key']}")
        return result

    def cleanup_legacy_kv_namespaces(self, namespaces: list[str]):
        if not namespaces or not self.table_exists("framework_kv"):
            return
        with self.transaction() as conn:
            for namespace in namespaces:
                conn.execute("DELETE FROM framework_kv WHERE namespace = ?", (namespace,))
            remaining = conn.execute("SELECT COUNT(*) AS count FROM framework_kv").fetchone()
            if remaining and int(remaining["count"]) == 0:
                conn.execute("DROP TABLE framework_kv")


framework_db = FrameworkDatabase()
