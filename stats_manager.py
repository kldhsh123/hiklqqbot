import json
import logging
import os
import random
import sqlite3
import string
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from config import STATS_MAX_MONTHS
from framework_db import framework_db


logger = logging.getLogger("stats_manager")

STATS_MIGRATION_KEY = "stats_relational_migrated_v1"
LEGACY_STATS_NAMESPACES = [
    "stats.groups",
    "stats.users",
    "stats.meta",
    "stats.id_mappings.users",
    "stats.id_mappings.groups",
    "stats.time.daily",
    "stats.time.weekly",
    "stats.time.monthly",
]


class StatsManager:
    """
    统计管理器：记录和管理机器人的统计数据
    包括群组、用户、消息等信息
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(StatsManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self, data_dir: str = "data"):
        if self.initialized:
            return

        self.logger = logger
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        self.groups_file = os.path.join(data_dir, "groups.json")
        self.users_file = os.path.join(data_dir, "users.json")
        self.stats_file = os.path.join(data_dir, "usage_stats.json")
        self.id_mappings_file = os.path.join(data_dir, "id_mappings.json")
        self.time_stats_file = os.path.join(data_dir, "time_stats.json")

        self._migrate_if_needed()
        self.cleanup_time_stats()
        self.initialized = True

    @property
    def usage_stats(self) -> Dict:
        return self.get_usage_stats()

    def _create_usage_stats(self) -> Dict:
        return {
            "commands": {},
            "groups": {},
            "users": {},
            "total_messages": 0,
            "command_messages": 0,
            "other_messages": 0,
            "command_groups": {},
            "command_users": {},
            "other_groups": {},
            "other_users": {},
        }

    def _create_time_bucket(self) -> Dict:
        return {
            "commands": {},
            "groups": {},
            "users": {},
            "total": 0,
            "command_messages": 0,
            "other_messages": 0,
            "command_groups": {},
            "command_users": {},
            "other_groups": {},
            "other_users": {},
        }

    def _merge_counter_dict(self, target: Dict, source: Dict):
        if not isinstance(source, dict):
            return
        for key, value in source.items():
            try:
                target[str(key)] = int(value)
            except (TypeError, ValueError):
                continue

    def _normalize_usage_stats(self, raw_stats: Optional[Dict]) -> Dict:
        normalized = self._create_usage_stats()
        if not isinstance(raw_stats, dict):
            return normalized

        for key in (
            "commands",
            "groups",
            "users",
            "command_groups",
            "command_users",
            "other_groups",
            "other_users",
        ):
            self._merge_counter_dict(normalized[key], raw_stats.get(key, {}))

        for key in ("total_messages", "command_messages", "other_messages"):
            try:
                normalized[key] = int(raw_stats.get(key, normalized[key]))
            except (TypeError, ValueError):
                pass

        if normalized["command_messages"] == 0 and normalized["other_messages"] == 0:
            normalized["command_messages"] = normalized["total_messages"]
            normalized["command_groups"] = dict(normalized["groups"])
            normalized["command_users"] = dict(normalized["users"])

        normalized["total_messages"] = (
            normalized["command_messages"] + normalized["other_messages"]
        )
        return normalized

    def _normalize_time_bucket(self, raw_bucket: Optional[Dict]) -> Dict:
        normalized = self._create_time_bucket()
        if not isinstance(raw_bucket, dict):
            return normalized

        for key in (
            "commands",
            "groups",
            "users",
            "command_groups",
            "command_users",
            "other_groups",
            "other_users",
        ):
            self._merge_counter_dict(normalized[key], raw_bucket.get(key, {}))

        for key in ("total", "command_messages", "other_messages"):
            try:
                normalized[key] = int(raw_bucket.get(key, normalized[key]))
            except (TypeError, ValueError):
                pass

        if normalized["command_messages"] == 0 and normalized["other_messages"] == 0:
            normalized["command_messages"] = normalized["total"]
            normalized["command_groups"] = dict(normalized["groups"])
            normalized["command_users"] = dict(normalized["users"])

        normalized["total"] = normalized["command_messages"] + normalized["other_messages"]
        return normalized

    def _normalize_time_stats(self, raw_stats: Optional[Dict]) -> Dict:
        normalized = {"daily": {}, "weekly": {}, "monthly": {}}
        if not isinstance(raw_stats, dict):
            return normalized

        for time_type in ("daily", "weekly", "monthly"):
            buckets = raw_stats.get(time_type, {})
            if not isinstance(buckets, dict):
                continue
            for time_key, bucket in buckets.items():
                normalized[time_type][str(time_key)] = self._normalize_time_bucket(bucket)

        return normalized

    def _coerce_timestamp(self, value, default: Optional[float] = None) -> float:
        if default is None:
            default = time.time()
        try:
            number = float(value)
            return number if number > 0 else default
        except (TypeError, ValueError):
            return default

    def _bool_to_int(self, value, default: bool = True) -> int:
        if value is None:
            return 1 if default else 0
        return 1 if bool(value) else 0

    def _has_relational_data(self) -> bool:
        tables = (
            "stats_users",
            "stats_groups",
            "stats_group_members",
            "display_id_mappings",
            "command_usage",
            "entity_usage",
            "time_usage",
        )
        for table in tables:
            row = framework_db.fetchone(f"SELECT COUNT(*) AS count FROM {table}")
            if row and int(row["count"]) > 0:
                return True
        return False

    def _load_legacy_source(self) -> Optional[Dict]:
        kv_groups = framework_db.legacy_kv_get_namespace("stats.groups")
        kv_users = framework_db.legacy_kv_get_namespace("stats.users")
        kv_usage_stats = framework_db.legacy_kv_get("stats.meta", "usage_stats")
        kv_user_mappings = framework_db.legacy_kv_get_namespace("stats.id_mappings.users")
        kv_group_mappings = framework_db.legacy_kv_get_namespace("stats.id_mappings.groups")
        kv_daily = framework_db.legacy_kv_get_namespace("stats.time.daily")
        kv_weekly = framework_db.legacy_kv_get_namespace("stats.time.weekly")
        kv_monthly = framework_db.legacy_kv_get_namespace("stats.time.monthly")

        has_kv = any(
            [
                kv_groups,
                kv_users,
                kv_usage_stats,
                kv_user_mappings,
                kv_group_mappings,
                kv_daily,
                kv_weekly,
                kv_monthly,
            ]
        )

        if has_kv:
            self.logger.info("检测到旧 framework_kv 统计数据，开始迁移")
            return {
                "groups": kv_groups or {},
                "users": kv_users or {},
                "usage_stats": self._normalize_usage_stats(kv_usage_stats),
                "id_mappings": {
                    "users": kv_user_mappings or {},
                    "groups": kv_group_mappings or {},
                },
                "time_stats": self._normalize_time_stats(
                    {
                        "daily": kv_daily or {},
                        "weekly": kv_weekly or {},
                        "monthly": kv_monthly or {},
                    }
                ),
            }

        groups = {}
        users = {}
        usage_stats = self._create_usage_stats()
        id_mappings = {"users": {}, "groups": {}}
        time_stats = {"daily": {}, "weekly": {}, "monthly": {}}

        try:
            if os.path.exists(self.groups_file):
                with open(self.groups_file, "r", encoding="utf-8") as f:
                    groups = json.load(f)
            if os.path.exists(self.users_file):
                with open(self.users_file, "r", encoding="utf-8") as f:
                    users = json.load(f)
            if os.path.exists(self.stats_file):
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    usage_stats = self._normalize_usage_stats(json.load(f))
            if os.path.exists(self.id_mappings_file):
                with open(self.id_mappings_file, "r", encoding="utf-8") as f:
                    raw_mappings = json.load(f)
                    if isinstance(raw_mappings, dict):
                        id_mappings = {
                            "users": dict(raw_mappings.get("users", {})),
                            "groups": dict(raw_mappings.get("groups", {})),
                        }
            if os.path.exists(self.time_stats_file):
                with open(self.time_stats_file, "r", encoding="utf-8") as f:
                    time_stats = self._normalize_time_stats(json.load(f))
        except Exception as e:
            self.logger.error(f"读取旧 JSON 统计数据失败: {e}")

        has_json = any(
            [
                groups,
                users,
                usage_stats["total_messages"],
                id_mappings["users"],
                id_mappings["groups"],
                time_stats["daily"],
                time_stats["weekly"],
                time_stats["monthly"],
            ]
        )
        if not has_json:
            return None

        self.logger.info("检测到旧 JSON 统计数据，开始迁移")
        return {
            "groups": groups,
            "users": users,
            "usage_stats": usage_stats,
            "id_mappings": id_mappings,
            "time_stats": time_stats,
        }

    def _clear_stats_tables(self, conn: sqlite3.Connection):
        tables = [
            "stats_user_name_history",
            "stats_group_name_history",
            "stats_group_members",
            "stats_users",
            "stats_groups",
            "display_id_mappings",
            "command_usage",
            "entity_usage",
            "time_command_usage",
            "time_entity_usage",
            "time_usage",
        ]
        for table in tables:
            conn.execute(f"DELETE FROM {table}")
        conn.execute(
            """
            UPDATE usage_summary
            SET total_messages = 0, command_messages = 0, other_messages = 0
            WHERE id = 1
            """
        )

    def _migrate_if_needed(self):
        if framework_db.meta_get_bool(STATS_MIGRATION_KEY, False):
            return

        source = self._load_legacy_source()
        if source is None and self._has_relational_data():
            framework_db.meta_set(STATS_MIGRATION_KEY, True)
            return

        if source is None:
            framework_db.meta_set(STATS_MIGRATION_KEY, True)
            return

        groups = source.get("groups", {}) if isinstance(source.get("groups"), dict) else {}
        users = source.get("users", {}) if isinstance(source.get("users"), dict) else {}
        usage_stats = self._normalize_usage_stats(source.get("usage_stats"))
        time_stats = self._normalize_time_stats(source.get("time_stats"))
        membership_count = 0
        for group_info in groups.values():
            if isinstance(group_info, dict):
                membership_count += len(group_info.get("members") or [])
        self.logger.info(
            "开始迁移统计数据到 sqlite: "
            f"users={len(users)}, groups={len(groups)}, "
            f"group_members={membership_count}, commands={len(usage_stats.get('commands', {}))}, "
            f"daily={len(time_stats.get('daily', {}))}, "
            f"weekly={len(time_stats.get('weekly', {}))}, "
            f"monthly={len(time_stats.get('monthly', {}))}"
        )

        self._migrate_source_to_relational(source)
        framework_db.meta_set(STATS_MIGRATION_KEY, True)
        framework_db.cleanup_legacy_kv_namespaces(LEGACY_STATS_NAMESPACES)
        self.logger.info(
            "统计数据迁移完成: "
            f"users={len(users)}, groups={len(groups)}, "
            f"group_members={membership_count}, total_messages={usage_stats.get('total_messages', 0)}, "
            f"commands={len(usage_stats.get('commands', {}))}"
        )

    def _migrate_source_to_relational(self, source: Dict):
        groups = source.get("groups", {}) if isinstance(source.get("groups"), dict) else {}
        users = source.get("users", {}) if isinstance(source.get("users"), dict) else {}
        usage_stats = self._normalize_usage_stats(source.get("usage_stats"))
        id_mappings = source.get("id_mappings", {})
        time_stats = self._normalize_time_stats(source.get("time_stats"))
        now = time.time()

        memberships: Dict[tuple[str, str], float] = {}

        user_rows: Dict[str, Dict] = {}
        for user_openid, user_info in users.items():
            if not isinstance(user_info, dict):
                user_info = {}
            first_seen = self._coerce_timestamp(user_info.get("first_seen"), now)
            last_active = self._coerce_timestamp(user_info.get("last_active"), first_seen)
            user_rows[str(user_openid)] = {
                "first_seen": first_seen,
                "last_active": last_active,
                "username": user_info.get("username"),
                "avatar": user_info.get("avatar"),
                "is_friend": self._bool_to_int(user_info.get("is_friend"), True),
                "can_send_proactive_msg": self._bool_to_int(
                    user_info.get("can_send_proactive_msg"), True
                ),
                "groups": list(user_info.get("groups") or []),
                "username_history": list(user_info.get("username_history") or []),
            }

        group_rows: Dict[str, Dict] = {}
        for group_openid, group_info in groups.items():
            if not isinstance(group_info, dict):
                group_info = {}
            join_time = self._coerce_timestamp(group_info.get("join_time"), now)
            last_active = self._coerce_timestamp(group_info.get("last_active"), join_time)
            group_rows[str(group_openid)] = {
                "join_time": join_time,
                "last_active": last_active,
                "added_by": group_info.get("added_by"),
                "group_name": group_info.get("group_name"),
                "can_send_proactive_msg": self._bool_to_int(
                    group_info.get("can_send_proactive_msg"), True
                ),
                "members": list(group_info.get("members") or []),
                "group_name_history": list(group_info.get("group_name_history") or []),
            }

        for group_openid, group_info in group_rows.items():
            joined_at = group_info["join_time"]
            for user_openid in group_info["members"]:
                memberships[(group_openid, str(user_openid))] = joined_at

        for user_openid, user_info in user_rows.items():
            joined_at = user_info["first_seen"]
            for group_openid in user_info["groups"]:
                memberships.setdefault((str(group_openid), user_openid), joined_at)

        for group_openid, user_openid in list(memberships.keys()):
            if group_openid not in group_rows:
                group_rows[group_openid] = {
                    "join_time": now,
                    "last_active": now,
                    "added_by": None,
                    "group_name": None,
                    "can_send_proactive_msg": 1,
                    "members": [],
                    "group_name_history": [],
                }
            if user_openid not in user_rows:
                user_rows[user_openid] = {
                    "first_seen": now,
                    "last_active": now,
                    "username": None,
                    "avatar": None,
                    "is_friend": 1,
                    "can_send_proactive_msg": 1,
                    "groups": [],
                    "username_history": [],
                }

        with framework_db.transaction() as conn:
            self._clear_stats_tables(conn)

            for user_openid, user_info in user_rows.items():
                conn.execute(
                    """
                    INSERT INTO stats_users(
                        user_openid, first_seen, last_active, username, avatar,
                        is_friend, can_send_proactive_msg
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_openid,
                        user_info["first_seen"],
                        user_info["last_active"],
                        user_info["username"],
                        user_info["avatar"],
                        user_info["is_friend"],
                        user_info["can_send_proactive_msg"],
                    ),
                )
                self._insert_name_history_rows(
                    conn,
                    "stats_user_name_history",
                    "user_openid",
                    user_openid,
                    user_info["username"],
                    user_info["first_seen"],
                    user_info["last_active"],
                    user_info["username_history"],
                )

            for group_openid, group_info in group_rows.items():
                conn.execute(
                    """
                    INSERT INTO stats_groups(
                        group_openid, join_time, last_active, added_by, group_name,
                        can_send_proactive_msg
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        group_openid,
                        group_info["join_time"],
                        group_info["last_active"],
                        group_info["added_by"],
                        group_info["group_name"],
                        group_info["can_send_proactive_msg"],
                    ),
                )
                self._insert_name_history_rows(
                    conn,
                    "stats_group_name_history",
                    "group_openid",
                    group_openid,
                    group_info["group_name"],
                    group_info["join_time"],
                    group_info["last_active"],
                    group_info["group_name_history"],
                )

            for (group_openid, user_openid), joined_at in memberships.items():
                conn.execute(
                    """
                    INSERT INTO stats_group_members(group_openid, user_openid, joined_at)
                    VALUES (?, ?, ?)
                    """,
                    (group_openid, user_openid, joined_at),
                )

            for real_id, display_id in (id_mappings.get("users") or {}).items():
                conn.execute(
                    """
                    INSERT INTO display_id_mappings(id_type, real_id, display_id)
                    VALUES ('users', ?, ?)
                    """,
                    (str(real_id), str(display_id)),
                )
            for real_id, display_id in (id_mappings.get("groups") or {}).items():
                conn.execute(
                    """
                    INSERT INTO display_id_mappings(id_type, real_id, display_id)
                    VALUES ('groups', ?, ?)
                    """,
                    (str(real_id), str(display_id)),
                )

            conn.execute(
                """
                UPDATE usage_summary
                SET total_messages = ?, command_messages = ?, other_messages = ?
                WHERE id = 1
                """,
                (
                    usage_stats["total_messages"],
                    usage_stats["command_messages"],
                    usage_stats["other_messages"],
                ),
            )

            for command, count in usage_stats.get("commands", {}).items():
                conn.execute(
                    "INSERT INTO command_usage(command, count) VALUES (?, ?)",
                    (str(command), int(count)),
                )

            for row in self._build_entity_usage_rows(
                usage_stats.get("users", {}),
                usage_stats.get("command_users", {}),
                usage_stats.get("other_users", {}),
                "user",
            ):
                conn.execute(
                    """
                    INSERT INTO entity_usage(
                        entity_type, entity_id, total_messages, command_messages, other_messages
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    row,
                )

            for row in self._build_entity_usage_rows(
                usage_stats.get("groups", {}),
                usage_stats.get("command_groups", {}),
                usage_stats.get("other_groups", {}),
                "group",
            ):
                conn.execute(
                    """
                    INSERT INTO entity_usage(
                        entity_type, entity_id, total_messages, command_messages, other_messages
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    row,
                )

            for period_type in ("daily", "weekly", "monthly"):
                for period_key, bucket in time_stats.get(period_type, {}).items():
                    conn.execute(
                        """
                        INSERT INTO time_usage(
                            period_type, period_key, total_messages, command_messages, other_messages
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            period_type,
                            str(period_key),
                            int(bucket.get("total", 0)),
                            int(bucket.get("command_messages", 0)),
                            int(bucket.get("other_messages", 0)),
                        ),
                    )

                    for command, count in bucket.get("commands", {}).items():
                        conn.execute(
                            """
                            INSERT INTO time_command_usage(period_type, period_key, command, count)
                            VALUES (?, ?, ?, ?)
                            """,
                            (period_type, str(period_key), str(command), int(count)),
                        )

                    for row in self._build_time_entity_usage_rows(
                        period_type,
                        str(period_key),
                        bucket.get("users", {}),
                        bucket.get("command_users", {}),
                        bucket.get("other_users", {}),
                        "user",
                    ):
                        conn.execute(
                            """
                            INSERT INTO time_entity_usage(
                                period_type, period_key, entity_type, entity_id,
                                total_messages, command_messages, other_messages
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            row,
                        )

                    for row in self._build_time_entity_usage_rows(
                        period_type,
                        str(period_key),
                        bucket.get("groups", {}),
                        bucket.get("command_groups", {}),
                        bucket.get("other_groups", {}),
                        "group",
                    ):
                        conn.execute(
                            """
                            INSERT INTO time_entity_usage(
                                period_type, period_key, entity_type, entity_id,
                                total_messages, command_messages, other_messages
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            row,
                        )

    def _insert_name_history_rows(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        foreign_key: str,
        owner_id: str,
        current_name: Optional[str],
        fallback_first_seen: float,
        fallback_last_active: float,
        history_rows: List[dict],
    ):
        inserted = False
        for row in history_rows:
            if not isinstance(row, dict):
                continue
            name = row.get("name")
            if not name:
                continue
            first_seen = self._coerce_timestamp(row.get("first_seen"), fallback_first_seen)
            last_active = self._coerce_timestamp(row.get("last_active"), first_seen)
            conn.execute(
                f"""
                INSERT INTO {table_name}({foreign_key}, name, first_seen, last_active)
                VALUES (?, ?, ?, ?)
                """,
                (owner_id, str(name), first_seen, last_active),
            )
            inserted = True

        if not inserted and current_name:
            conn.execute(
                f"""
                INSERT INTO {table_name}({foreign_key}, name, first_seen, last_active)
                VALUES (?, ?, ?, ?)
                """,
                (owner_id, str(current_name), fallback_first_seen, fallback_last_active),
            )

    def _build_entity_usage_rows(
        self,
        total_map: Dict,
        command_map: Dict,
        other_map: Dict,
        entity_type: str,
    ) -> list[tuple]:
        keys = {str(key) for key in total_map.keys()} | {
            str(key) for key in command_map.keys()
        } | {str(key) for key in other_map.keys()}
        rows = []
        for entity_id in keys:
            total = int(total_map.get(entity_id, 0))
            command_total = int(command_map.get(entity_id, 0))
            other_total = int(other_map.get(entity_id, 0))
            if total == 0:
                total = command_total + other_total
            rows.append((entity_type, entity_id, total, command_total, other_total))
        return rows

    def _build_time_entity_usage_rows(
        self,
        period_type: str,
        period_key: str,
        total_map: Dict,
        command_map: Dict,
        other_map: Dict,
        entity_type: str,
    ) -> list[tuple]:
        rows = []
        for entity_row in self._build_entity_usage_rows(
            total_map, command_map, other_map, entity_type
        ):
            rows.append((period_type, period_key, *entity_row))
        return rows

    def _row_to_user_dict(self, row, groups: Optional[List[str]] = None) -> Dict:
        data = {
            "first_seen": float(row["first_seen"]),
            "last_active": float(row["last_active"]),
            "groups": groups or [],
            "is_friend": bool(row["is_friend"]),
            "can_send_proactive_msg": bool(row["can_send_proactive_msg"]),
        }
        if row["username"] is not None:
            data["username"] = row["username"]
        if row["avatar"] is not None:
            data["avatar"] = row["avatar"]
        return data

    def _row_to_group_dict(self, row, members: Optional[List[str]] = None) -> Dict:
        data = {
            "join_time": float(row["join_time"]),
            "last_active": float(row["last_active"]),
            "members": members or [],
            "can_send_proactive_msg": bool(row["can_send_proactive_msg"]),
        }
        if row["added_by"] is not None:
            data["added_by"] = row["added_by"]
        if row["group_name"] is not None:
            data["group_name"] = row["group_name"]
        return data

    def _get_membership_map_by_group(self) -> Dict[str, List[str]]:
        rows = framework_db.fetchall(
            """
            SELECT group_openid, user_openid
            FROM stats_group_members
            ORDER BY group_openid, user_openid
            """
        )
        mapping: Dict[str, List[str]] = {}
        for row in rows:
            mapping.setdefault(str(row["group_openid"]), []).append(str(row["user_openid"]))
        return mapping

    def _get_membership_map_by_user(self) -> Dict[str, List[str]]:
        rows = framework_db.fetchall(
            """
            SELECT user_openid, group_openid
            FROM stats_group_members
            ORDER BY user_openid, group_openid
            """
        )
        mapping: Dict[str, List[str]] = {}
        for row in rows:
            mapping.setdefault(str(row["user_openid"]), []).append(str(row["group_openid"]))
        return mapping

    def _get_groups_for_user(self, user_openid: str) -> List[str]:
        rows = framework_db.fetchall(
            """
            SELECT group_openid
            FROM stats_group_members
            WHERE user_openid = ?
            ORDER BY group_openid
            """,
            (user_openid,),
        )
        return [str(row["group_openid"]) for row in rows]

    def _generate_display_id(self, id_type: str) -> str:
        prefix = "U" if id_type == "users" else "G"
        while True:
            random_id = "".join(random.choices(string.digits, k=6))
            yield f"{prefix}{random_id}"

    def get_display_id(self, real_id: str, id_type: str) -> str:
        if id_type not in ("users", "groups"):
            self.logger.error(f"无效的ID类型: {id_type}")
            return "未知ID"

        row = framework_db.fetchone(
            """
            SELECT display_id
            FROM display_id_mappings
            WHERE id_type = ? AND real_id = ?
            """,
            (id_type, real_id),
        )
        if row:
            return str(row["display_id"])

        for display_id in self._generate_display_id(id_type):
            try:
                framework_db.execute(
                    """
                    INSERT INTO display_id_mappings(id_type, real_id, display_id)
                    VALUES (?, ?, ?)
                    """,
                    (id_type, real_id, display_id),
                )
                return display_id
            except sqlite3.IntegrityError:
                continue

        return "未知ID"

    def get_user_display_id(self, user_openid: str) -> str:
        return self.get_display_id(user_openid, "users")

    def get_group_display_id(self, group_openid: str) -> str:
        return self.get_display_id(group_openid, "groups")

    def get_real_id(self, display_id: str) -> Tuple[Optional[str], Optional[str]]:
        row = framework_db.fetchone(
            """
            SELECT real_id, id_type
            FROM display_id_mappings
            WHERE display_id = ?
            """,
            (display_id,),
        )
        if not row:
            return None, None
        return str(row["real_id"]), str(row["id_type"])

    def _get_time_keys(self, timestamp: Optional[float] = None) -> Tuple[str, str, str]:
        if timestamp is None:
            timestamp = time.time()
        dt = datetime.fromtimestamp(timestamp)
        return (
            dt.strftime("%Y-%m-%d"),
            f"{dt.year}-W{dt.strftime('%W')}",
            dt.strftime("%Y-%m"),
        )

    def add_group(self, group_openid: str, name: str = None, op_member_openid: str = None):
        current_time = time.time()
        with framework_db.transaction() as conn:
            row = conn.execute(
                """
                SELECT group_openid, join_time, last_active, added_by, group_name, can_send_proactive_msg
                FROM stats_groups
                WHERE group_openid = ?
                """,
                (group_openid,),
            ).fetchone()

            if row is None:
                conn.execute(
                    """
                    INSERT INTO stats_groups(
                        group_openid, join_time, last_active, added_by, group_name, can_send_proactive_msg
                    ) VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (group_openid, current_time, current_time, op_member_openid, name),
                )
                if name:
                    conn.execute(
                        """
                        INSERT INTO stats_group_name_history(group_openid, name, first_seen, last_active)
                        VALUES (?, ?, ?, ?)
                        """,
                        (group_openid, name, current_time, current_time),
                    )
                self.logger.info(f"添加新群组: {group_openid} (name={name})")
            else:
                conn.execute(
                    "UPDATE stats_groups SET last_active = ? WHERE group_openid = ?",
                    (current_time, group_openid),
                )
                if name:
                    self._update_group_name_history(conn, group_openid, name, current_time)

        self.get_group_display_id(group_openid)
        return self.get_group(group_openid)

    def remove_group(self, group_openid: str):
        row = framework_db.fetchone(
            "SELECT 1 FROM stats_groups WHERE group_openid = ?",
            (group_openid,),
        )
        if not row:
            return False

        with framework_db.transaction() as conn:
            conn.execute("DELETE FROM stats_group_members WHERE group_openid = ?", (group_openid,))
            conn.execute("DELETE FROM stats_group_name_history WHERE group_openid = ?", (group_openid,))
            conn.execute("DELETE FROM stats_groups WHERE group_openid = ?", (group_openid,))
        self.logger.info(f"移除群组: {group_openid}")
        return True

    def get_group(self, group_openid: str) -> Optional[dict]:
        row = framework_db.fetchone(
            """
            SELECT group_openid, join_time, last_active, added_by, group_name, can_send_proactive_msg
            FROM stats_groups
            WHERE group_openid = ?
            """,
            (group_openid,),
        )
        if not row:
            return None
        return self._row_to_group_dict(row, self.get_group_members(group_openid))

    def get_all_groups(self) -> Dict[str, dict]:
        rows = framework_db.fetchall(
            """
            SELECT group_openid, join_time, last_active, added_by, group_name, can_send_proactive_msg
            FROM stats_groups
            """
        )
        members_map = self._get_membership_map_by_group()
        return {
            str(row["group_openid"]): self._row_to_group_dict(
                row,
                members_map.get(str(row["group_openid"]), []),
            )
            for row in rows
        }

    def add_user_to_group(self, group_openid: str, user_openid: str):
        group = framework_db.fetchone(
            "SELECT 1 FROM stats_groups WHERE group_openid = ?",
            (group_openid,),
        )
        if not group:
            return False

        row = framework_db.fetchone(
            """
            SELECT 1
            FROM stats_group_members
            WHERE group_openid = ? AND user_openid = ?
            """,
            (group_openid, user_openid),
        )
        if row:
            return False

        joined_at = time.time()
        framework_db.execute(
            """
            INSERT INTO stats_group_members(group_openid, user_openid, joined_at)
            VALUES (?, ?, ?)
            """,
            (group_openid, user_openid, joined_at),
        )
        self.logger.debug(f"将用户 {user_openid} 添加到群组 {group_openid}")
        return True

    def remove_user_from_group(self, group_openid: str, user_openid: str):
        row = framework_db.fetchone(
            """
            SELECT 1
            FROM stats_group_members
            WHERE group_openid = ? AND user_openid = ?
            """,
            (group_openid, user_openid),
        )
        if not row:
            return False

        framework_db.execute(
            "DELETE FROM stats_group_members WHERE group_openid = ? AND user_openid = ?",
            (group_openid, user_openid),
        )
        self.logger.debug(f"从群组 {group_openid} 移除用户 {user_openid}")
        return True

    def get_group_members(self, group_openid: str) -> List[str]:
        rows = framework_db.fetchall(
            """
            SELECT user_openid
            FROM stats_group_members
            WHERE group_openid = ?
            ORDER BY user_openid
            """,
            (group_openid,),
        )
        return [str(row["user_openid"]) for row in rows]

    def add_user(self, user_openid: str, name: str = None, avatar: str = None):
        current_time = time.time()
        with framework_db.transaction() as conn:
            row = conn.execute(
                """
                SELECT user_openid, first_seen, last_active, username, avatar, is_friend, can_send_proactive_msg
                FROM stats_users
                WHERE user_openid = ?
                """,
                (user_openid,),
            ).fetchone()

            if row is None:
                conn.execute(
                    """
                    INSERT INTO stats_users(
                        user_openid, first_seen, last_active, username, avatar, is_friend, can_send_proactive_msg
                    ) VALUES (?, ?, ?, ?, ?, 1, 1)
                    """,
                    (user_openid, current_time, current_time, name, avatar),
                )
                if name:
                    conn.execute(
                        """
                        INSERT INTO stats_user_name_history(user_openid, name, first_seen, last_active)
                        VALUES (?, ?, ?, ?)
                        """,
                        (user_openid, name, current_time, current_time),
                    )
                self.logger.info(f"添加新用户: {user_openid} (username={name})")
            else:
                conn.execute(
                    "UPDATE stats_users SET last_active = ? WHERE user_openid = ?",
                    (current_time, user_openid),
                )
                if avatar:
                    conn.execute(
                        "UPDATE stats_users SET avatar = ? WHERE user_openid = ?",
                        (avatar, user_openid),
                    )
                if name:
                    self._update_user_name_history(conn, user_openid, name, current_time)

        self.get_user_display_id(user_openid)
        return self.get_user(user_openid)

    def _update_user_name_history(
        self, conn: sqlite3.Connection, user_openid: str, new_name: str, now: float
    ):
        current_row = conn.execute(
            "SELECT username FROM stats_users WHERE user_openid = ?",
            (user_openid,),
        ).fetchone()
        current_name = current_row["username"] if current_row else None

        if current_name == new_name:
            updated = conn.execute(
                """
                UPDATE stats_user_name_history
                SET last_active = ?
                WHERE id = (
                    SELECT id FROM stats_user_name_history
                    WHERE user_openid = ?
                    ORDER BY first_seen DESC, id DESC
                    LIMIT 1
                )
                """,
                (now, user_openid),
            )
            if updated.rowcount == 0:
                conn.execute(
                    """
                    INSERT INTO stats_user_name_history(user_openid, name, first_seen, last_active)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_openid, new_name, now, now),
                )
            return

        conn.execute(
            """
            INSERT INTO stats_user_name_history(user_openid, name, first_seen, last_active)
            VALUES (?, ?, ?, ?)
            """,
            (user_openid, new_name, now, now),
        )
        conn.execute(
            "UPDATE stats_users SET username = ? WHERE user_openid = ?",
            (new_name, user_openid),
        )

    def _update_group_name_history(
        self, conn: sqlite3.Connection, group_openid: str, new_name: str, now: float
    ):
        current_row = conn.execute(
            "SELECT group_name FROM stats_groups WHERE group_openid = ?",
            (group_openid,),
        ).fetchone()
        current_name = current_row["group_name"] if current_row else None

        if current_name == new_name:
            updated = conn.execute(
                """
                UPDATE stats_group_name_history
                SET last_active = ?
                WHERE id = (
                    SELECT id FROM stats_group_name_history
                    WHERE group_openid = ?
                    ORDER BY first_seen DESC, id DESC
                    LIMIT 1
                )
                """,
                (now, group_openid),
            )
            if updated.rowcount == 0:
                conn.execute(
                    """
                    INSERT INTO stats_group_name_history(group_openid, name, first_seen, last_active)
                    VALUES (?, ?, ?, ?)
                    """,
                    (group_openid, new_name, now, now),
                )
            return

        conn.execute(
            """
            INSERT INTO stats_group_name_history(group_openid, name, first_seen, last_active)
            VALUES (?, ?, ?, ?)
            """,
            (group_openid, new_name, now, now),
        )
        conn.execute(
            "UPDATE stats_groups SET group_name = ? WHERE group_openid = ?",
            (new_name, group_openid),
        )

    def get_username(self, user_openid: str) -> Optional[str]:
        row = framework_db.fetchone(
            "SELECT username FROM stats_users WHERE user_openid = ?",
            (user_openid,),
        )
        return row["username"] if row and row["username"] is not None else None

    def get_username_history(self, user_openid: str) -> List[dict]:
        rows = framework_db.fetchall(
            """
            SELECT name, first_seen, last_active
            FROM stats_user_name_history
            WHERE user_openid = ?
            ORDER BY first_seen ASC, id ASC
            """,
            (user_openid,),
        )
        return [
            {
                "name": row["name"],
                "first_seen": float(row["first_seen"]),
                "last_active": float(row["last_active"]),
            }
            for row in rows
        ]

    def get_groupname(self, group_openid: str) -> Optional[str]:
        row = framework_db.fetchone(
            "SELECT group_name FROM stats_groups WHERE group_openid = ?",
            (group_openid,),
        )
        return row["group_name"] if row and row["group_name"] is not None else None

    def get_groupname_history(self, group_openid: str) -> List[dict]:
        rows = framework_db.fetchall(
            """
            SELECT name, first_seen, last_active
            FROM stats_group_name_history
            WHERE group_openid = ?
            ORDER BY first_seen ASC, id ASC
            """,
            (group_openid,),
        )
        return [
            {
                "name": row["name"],
                "first_seen": float(row["first_seen"]),
                "last_active": float(row["last_active"]),
            }
            for row in rows
        ]

    def get_user(self, user_openid: str) -> Optional[dict]:
        row = framework_db.fetchone(
            """
            SELECT user_openid, first_seen, last_active, username, avatar, is_friend, can_send_proactive_msg
            FROM stats_users
            WHERE user_openid = ?
            """,
            (user_openid,),
        )
        if not row:
            return None
        groups = self._get_groups_for_user(user_openid)
        return self._row_to_user_dict(row, groups)

    def get_all_users(self) -> Dict[str, dict]:
        rows = framework_db.fetchall(
            """
            SELECT user_openid, first_seen, last_active, username, avatar, is_friend, can_send_proactive_msg
            FROM stats_users
            """
        )
        groups_map = self._get_membership_map_by_user()
        return {
            str(row["user_openid"]): self._row_to_user_dict(
                row,
                groups_map.get(str(row["user_openid"]), []),
            )
            for row in rows
        }

    def update_user_avatar(self, user_openid: str, avatar_url: str):
        row = framework_db.fetchone(
            "SELECT 1 FROM stats_users WHERE user_openid = ?",
            (user_openid,),
        )
        if not row:
            return False
        framework_db.execute(
            "UPDATE stats_users SET avatar = ? WHERE user_openid = ?",
            (avatar_url, user_openid),
        )
        return True

    def set_group_proactive_message_permission(self, group_openid: str, enabled: bool) -> bool:
        row = framework_db.fetchone(
            "SELECT 1 FROM stats_groups WHERE group_openid = ?",
            (group_openid,),
        )
        if not row:
            return False
        framework_db.execute(
            "UPDATE stats_groups SET can_send_proactive_msg = ? WHERE group_openid = ?",
            (1 if enabled else 0, group_openid),
        )
        return True

    def set_user_proactive_message_permission(self, user_openid: str, enabled: bool) -> bool:
        row = framework_db.fetchone(
            "SELECT 1 FROM stats_users WHERE user_openid = ?",
            (user_openid,),
        )
        if not row:
            return False
        framework_db.execute(
            "UPDATE stats_users SET can_send_proactive_msg = ? WHERE user_openid = ?",
            (1 if enabled else 0, user_openid),
        )
        return True

    def _increment_entity_usage(
        self, conn: sqlite3.Connection, entity_type: str, entity_id: Optional[str], message_type: str
    ):
        if not entity_id:
            return
        command_inc = 1 if message_type == "command" else 0
        other_inc = 1 if message_type == "other" else 0
        conn.execute(
            """
            INSERT INTO entity_usage(
                entity_type, entity_id, total_messages, command_messages, other_messages
            ) VALUES (?, ?, 1, ?, ?)
            ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                total_messages = entity_usage.total_messages + 1,
                command_messages = entity_usage.command_messages + excluded.command_messages,
                other_messages = entity_usage.other_messages + excluded.other_messages
            """,
            (entity_type, entity_id, command_inc, other_inc),
        )

    def _increment_time_usage(
        self, conn: sqlite3.Connection, period_type: str, period_key: str, message_type: str
    ):
        command_inc = 1 if message_type == "command" else 0
        other_inc = 1 if message_type == "other" else 0
        conn.execute(
            """
            INSERT INTO time_usage(
                period_type, period_key, total_messages, command_messages, other_messages
            ) VALUES (?, ?, 1, ?, ?)
            ON CONFLICT(period_type, period_key) DO UPDATE SET
                total_messages = time_usage.total_messages + 1,
                command_messages = time_usage.command_messages + excluded.command_messages,
                other_messages = time_usage.other_messages + excluded.other_messages
            """,
            (period_type, period_key, command_inc, other_inc),
        )

    def _increment_time_entity_usage(
        self,
        conn: sqlite3.Connection,
        period_type: str,
        period_key: str,
        entity_type: str,
        entity_id: Optional[str],
        message_type: str,
    ):
        if not entity_id:
            return
        command_inc = 1 if message_type == "command" else 0
        other_inc = 1 if message_type == "other" else 0
        conn.execute(
            """
            INSERT INTO time_entity_usage(
                period_type, period_key, entity_type, entity_id,
                total_messages, command_messages, other_messages
            ) VALUES (?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(period_type, period_key, entity_type, entity_id) DO UPDATE SET
                total_messages = time_entity_usage.total_messages + 1,
                command_messages = time_entity_usage.command_messages + excluded.command_messages,
                other_messages = time_entity_usage.other_messages + excluded.other_messages
            """,
            (period_type, period_key, entity_type, entity_id, command_inc, other_inc),
        )

    def log_message(
        self,
        message_type: str,
        user_openid: str = None,
        group_openid: str = None,
        command: str = None,
    ):
        if message_type not in ("command", "other"):
            self.logger.warning(f"未知消息类型: {message_type}")
            return

        current_time = time.time()
        daily_key, weekly_key, monthly_key = self._get_time_keys(current_time)

        with framework_db.transaction() as conn:
            is_new_month = conn.execute(
                """
                SELECT 1
                FROM time_usage
                WHERE period_type = 'monthly' AND period_key = ?
                """,
                (monthly_key,),
            ).fetchone() is None

            command_inc = 1 if message_type == "command" else 0
            other_inc = 1 if message_type == "other" else 0
            conn.execute(
                """
                UPDATE usage_summary
                SET total_messages = total_messages + 1,
                    command_messages = command_messages + ?,
                    other_messages = other_messages + ?
                WHERE id = 1
                """,
                (command_inc, other_inc),
            )

            if message_type == "command" and command:
                conn.execute(
                    """
                    INSERT INTO command_usage(command, count)
                    VALUES (?, 1)
                    ON CONFLICT(command) DO UPDATE SET
                        count = command_usage.count + 1
                    """,
                    (command,),
                )

            self._increment_entity_usage(conn, "user", user_openid, message_type)
            self._increment_entity_usage(conn, "group", group_openid, message_type)

            for period_type, period_key in (
                ("daily", daily_key),
                ("weekly", weekly_key),
                ("monthly", monthly_key),
            ):
                self._increment_time_usage(conn, period_type, period_key, message_type)
                self._increment_time_entity_usage(
                    conn, period_type, period_key, "user", user_openid, message_type
                )
                self._increment_time_entity_usage(
                    conn, period_type, period_key, "group", group_openid, message_type
                )

                if message_type == "command" and command:
                    conn.execute(
                        """
                        INSERT INTO time_command_usage(period_type, period_key, command, count)
                        VALUES (?, ?, ?, 1)
                        ON CONFLICT(period_type, period_key, command) DO UPDATE SET
                            count = time_command_usage.count + 1
                        """,
                        (period_type, period_key, command),
                    )

            if is_new_month:
                self._cleanup_time_stats_conn(conn)

    def log_command(self, command: str, user_openid: str = None, group_openid: str = None):
        self.log_message("command", user_openid=user_openid, group_openid=group_openid, command=command)

    def log_other_message(self, user_openid: str = None, group_openid: str = None):
        self.log_message("other", user_openid=user_openid, group_openid=group_openid)

    def get_usage_stats(self) -> Dict:
        stats = self._create_usage_stats()
        row = framework_db.fetchone(
            """
            SELECT total_messages, command_messages, other_messages
            FROM usage_summary
            WHERE id = 1
            """
        )
        if row:
            stats["total_messages"] = int(row["total_messages"])
            stats["command_messages"] = int(row["command_messages"])
            stats["other_messages"] = int(row["other_messages"])

        for row in framework_db.fetchall("SELECT command, count FROM command_usage"):
            stats["commands"][str(row["command"])] = int(row["count"])

        for row in framework_db.fetchall(
            """
            SELECT entity_type, entity_id, total_messages, command_messages, other_messages
            FROM entity_usage
            """
        ):
            entity_id = str(row["entity_id"])
            if str(row["entity_type"]) == "user":
                stats["users"][entity_id] = int(row["total_messages"])
                stats["command_users"][entity_id] = int(row["command_messages"])
                stats["other_users"][entity_id] = int(row["other_messages"])
            else:
                stats["groups"][entity_id] = int(row["total_messages"])
                stats["command_groups"][entity_id] = int(row["command_messages"])
                stats["other_groups"][entity_id] = int(row["other_messages"])

        return stats

    def get_command_stats(self) -> Dict[str, int]:
        rows = framework_db.fetchall("SELECT command, count FROM command_usage")
        return {str(row["command"]): int(row["count"]) for row in rows}

    def get_most_active_groups(self, limit: int = 10) -> List[tuple]:
        rows = framework_db.fetchall(
            """
            SELECT entity_id, total_messages
            FROM entity_usage
            WHERE entity_type = 'group'
            ORDER BY total_messages DESC, entity_id ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [(str(row["entity_id"]), int(row["total_messages"])) for row in rows]

    def get_most_active_users(self, limit: int = 10) -> List[tuple]:
        rows = framework_db.fetchall(
            """
            SELECT entity_id, total_messages
            FROM entity_usage
            WHERE entity_type = 'user'
            ORDER BY total_messages DESC, entity_id ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [(str(row["entity_id"]), int(row["total_messages"])) for row in rows]

    def _get_period_stats(self, period_type: str, period_key: str) -> dict:
        stats = self._create_time_bucket()
        row = framework_db.fetchone(
            """
            SELECT total_messages, command_messages, other_messages
            FROM time_usage
            WHERE period_type = ? AND period_key = ?
            """,
            (period_type, period_key),
        )
        if not row:
            return stats

        stats["total"] = int(row["total_messages"])
        stats["command_messages"] = int(row["command_messages"])
        stats["other_messages"] = int(row["other_messages"])

        for command_row in framework_db.fetchall(
            """
            SELECT command, count
            FROM time_command_usage
            WHERE period_type = ? AND period_key = ?
            """,
            (period_type, period_key),
        ):
            stats["commands"][str(command_row["command"])] = int(command_row["count"])

        for entity_row in framework_db.fetchall(
            """
            SELECT entity_type, entity_id, total_messages, command_messages, other_messages
            FROM time_entity_usage
            WHERE period_type = ? AND period_key = ?
            """,
            (period_type, period_key),
        ):
            entity_id = str(entity_row["entity_id"])
            if str(entity_row["entity_type"]) == "user":
                stats["users"][entity_id] = int(entity_row["total_messages"])
                stats["command_users"][entity_id] = int(entity_row["command_messages"])
                stats["other_users"][entity_id] = int(entity_row["other_messages"])
            else:
                stats["groups"][entity_id] = int(entity_row["total_messages"])
                stats["command_groups"][entity_id] = int(entity_row["command_messages"])
                stats["other_groups"][entity_id] = int(entity_row["other_messages"])

        return stats

    def get_daily_stats(self, date_str: Optional[str] = None) -> dict:
        if date_str is None:
            date_str, _, _ = self._get_time_keys()
        return self._get_period_stats("daily", date_str)

    def get_weekly_stats(self, week_str: Optional[str] = None) -> dict:
        if week_str is None:
            _, week_str, _ = self._get_time_keys()
        return self._get_period_stats("weekly", week_str)

    def get_monthly_stats(self, month_str: Optional[str] = None) -> dict:
        if month_str is None:
            _, _, month_str = self._get_time_keys()
        return self._get_period_stats("monthly", month_str)

    def _cleanup_time_stats_conn(self, conn: sqlite3.Connection):
        rows = conn.execute(
            """
            SELECT period_key
            FROM time_usage
            WHERE period_type = 'monthly'
            ORDER BY period_key DESC
            """
        ).fetchall()
        if len(rows) <= STATS_MAX_MONTHS:
            return

        stale_keys = [str(row["period_key"]) for row in rows[STATS_MAX_MONTHS:]]
        for stale_key in stale_keys:
            conn.execute(
                "DELETE FROM time_usage WHERE period_type = 'monthly' AND period_key = ?",
                (stale_key,),
            )
            conn.execute(
                "DELETE FROM time_command_usage WHERE period_type = 'monthly' AND period_key = ?",
                (stale_key,),
            )
            conn.execute(
                "DELETE FROM time_entity_usage WHERE period_type = 'monthly' AND period_key = ?",
                (stale_key,),
            )

    def cleanup_time_stats(self):
        try:
            with framework_db.transaction() as conn:
                self._cleanup_time_stats_conn(conn)
        except Exception as e:
            self.logger.error(f"清理时间统计数据失败: {e}")

    def handle_group_add_robot(self, group_openid: str, op_member_openid: str, timestamp: int):
        self.add_group(group_openid, op_member_openid=op_member_openid)
        if op_member_openid:
            self.add_user(op_member_openid)
            self.add_user_to_group(group_openid, op_member_openid)
        return True

    def handle_group_del_robot(self, group_openid: str, op_member_openid: str, timestamp: int):
        return self.remove_group(group_openid)

    def handle_friend_add(self, user_openid: str, timestamp: int):
        self.add_user(user_openid)
        framework_db.execute(
            "UPDATE stats_users SET is_friend = 1 WHERE user_openid = ?",
            (user_openid,),
        )
        return True

    def handle_friend_del(self, user_openid: str, timestamp: int):
        row = framework_db.fetchone(
            "SELECT 1 FROM stats_users WHERE user_openid = ?",
            (user_openid,),
        )
        if not row:
            return False
        framework_db.execute(
            "UPDATE stats_users SET is_friend = 0 WHERE user_openid = ?",
            (user_openid,),
        )
        return True

    def _save_data(self):
        # 关系表模式为即时写入，这里保留兼容接口。
        return None


stats_manager = StatsManager()
