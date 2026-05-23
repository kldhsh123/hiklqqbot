import json
import logging
import os
import time
from typing import List, Set

from framework_db import framework_db


logger = logging.getLogger("auth_manager")

AUTH_MIGRATION_KEY = "auth_relational_migrated_v1"


class AuthManager:
    """
    权限管理系统，负责管理用户权限和维护模式
    """

    def __init__(self):
        self.admins: Set[str] = set()
        self.maintenance_mode = False
        self.auth_file = "admins.json"
        self.maintenance_file = "maintenance.json"
        self.logger = logger

        self._migrate_if_needed()
        self.reload_admins()
        self._reload_maintenance()

    def _migrate_if_needed(self):
        if framework_db.meta_get_bool(AUTH_MIGRATION_KEY, False):
            return

        legacy_admins = self._load_legacy_admins()
        legacy_maintenance = self._load_legacy_maintenance()
        has_legacy = legacy_admins is not None or legacy_maintenance is not None

        current_admin_count = framework_db.fetchone(
            "SELECT COUNT(*) AS count FROM admins"
        )
        current_admin_count = int(current_admin_count["count"]) if current_admin_count else 0
        current_maintenance = framework_db.fetchone(
            "SELECT enabled FROM maintenance_state WHERE id = 1"
        )
        has_new_data = current_admin_count > 0 or (
            current_maintenance is not None and bool(current_maintenance["enabled"])
        )

        if not has_legacy and has_new_data:
            framework_db.meta_set(AUTH_MIGRATION_KEY, True)
            return

        if not has_legacy:
            framework_db.meta_set(AUTH_MIGRATION_KEY, True)
            return

        admin_count = len(set(legacy_admins or []))
        maintenance_enabled = bool(legacy_maintenance) if legacy_maintenance is not None else False
        self.logger.info(
            f"开始迁移权限数据到 sqlite: admins={admin_count}, maintenance={maintenance_enabled}"
        )

        with framework_db.transaction() as conn:
            conn.execute("DELETE FROM admins")
            for admin_id in sorted(set(legacy_admins or [])):
                conn.execute(
                    "INSERT INTO admins(user_id, created_at) VALUES (?, ?)",
                    (admin_id, time.time()),
                )

            enabled = bool(legacy_maintenance) if legacy_maintenance is not None else False
            conn.execute(
                """
                INSERT INTO maintenance_state(id, enabled, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (1 if enabled else 0, time.time()),
            )
            conn.execute(
                """
                INSERT INTO schema_meta(key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (AUTH_MIGRATION_KEY, "1"),
            )

        framework_db.cleanup_legacy_kv_namespaces(["auth"])
        self.logger.info(
            f"权限数据迁移完成: admins={admin_count}, maintenance={maintenance_enabled}"
        )

    def _load_legacy_admins(self):
        legacy = framework_db.legacy_kv_get("auth", "admins")
        if isinstance(legacy, dict):
            admins = legacy.get("admins")
            if isinstance(admins, list):
                self.logger.info(f"从旧 framework_kv 读取到 {len(admins)} 个管理员")
                return [str(item) for item in admins if item]

        if os.path.exists(self.auth_file):
            try:
                with open(self.auth_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                admins = data.get("admins", [])
                if isinstance(admins, list):
                    self.logger.info(f"从旧 JSON 读取到 {len(admins)} 个管理员")
                    return [str(item) for item in admins if item]
            except Exception as e:
                self.logger.error(f"读取旧管理员配置失败: {e}")
        return None

    def _load_legacy_maintenance(self):
        legacy = framework_db.legacy_kv_get("auth", "maintenance")
        if isinstance(legacy, dict) and "maintenance_mode" in legacy:
            self.logger.info("从旧 framework_kv 读取维护模式状态")
            return bool(legacy.get("maintenance_mode", False))

        if os.path.exists(self.maintenance_file):
            try:
                with open(self.maintenance_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.logger.info("从旧 JSON 读取维护模式状态")
                return bool(data.get("maintenance_mode", False))
            except Exception as e:
                self.logger.error(f"读取旧维护模式配置失败: {e}")
        return None

    def _reload_maintenance(self):
        row = framework_db.fetchone(
            "SELECT enabled FROM maintenance_state WHERE id = 1"
        )
        self.maintenance_mode = bool(row["enabled"]) if row else False

    def _save_admins(self) -> None:
        try:
            with framework_db.transaction() as conn:
                conn.execute("DELETE FROM admins")
                now = time.time()
                for admin_id in sorted(self.admins):
                    conn.execute(
                        "INSERT INTO admins(user_id, created_at) VALUES (?, ?)",
                        (admin_id, now),
                    )
            self.logger.info(f"已保存 {len(self.admins)} 个管理员到 sqlite")
        except Exception as e:
            self.logger.error(f"保存管理员列表失败: {e}")

    def reload_admins(self) -> None:
        self.logger.info("重新加载管理员列表...")
        rows = framework_db.fetchall("SELECT user_id FROM admins ORDER BY user_id")
        self.admins = {str(row["user_id"]) for row in rows}
        self.logger.info(f"管理员列表重新加载完成，共加载 {len(self.admins)} 个管理员")

    def add_admin(self, user_id: str) -> bool:
        if not user_id or user_id in self.admins:
            return False
        self.admins.add(user_id)
        self._save_admins()
        return True

    def remove_admin(self, user_id: str) -> bool:
        if not user_id or user_id not in self.admins:
            return False
        self.admins.remove(user_id)
        self._save_admins()
        return True

    def is_admin(self, user_id: str) -> bool:
        return user_id in self.admins

    def set_maintenance_mode(self, enabled: bool) -> None:
        self.maintenance_mode = enabled
        try:
            framework_db.execute(
                """
                INSERT INTO maintenance_state(id, enabled, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (1 if enabled else 0, time.time()),
            )
            self.logger.info(f"维护模式已{'启用' if enabled else '禁用'}")
        except Exception as e:
            self.logger.error(f"保存维护模式状态失败: {e}")

    def is_maintenance_mode(self) -> bool:
        return self.maintenance_mode

    def can_access(self, user_id: str) -> bool:
        if self.is_admin(user_id):
            return True
        if self.maintenance_mode:
            return False
        return True

    def get_admins(self) -> List[str]:
        return sorted(self.admins)


auth_manager = AuthManager()
