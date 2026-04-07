import asyncio
import importlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


class BlacklistPluginTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_blacklist_module = types.ModuleType("blacklist_manager")
        fake_blacklist_module.blacklist_manager = types.SimpleNamespace(
            add_user=MagicMock(return_value=True),
            add_group=MagicMock(return_value=True),
            remove_user=MagicMock(return_value=True),
            remove_group=MagicMock(return_value=True),
            list_users=MagicMock(return_value=[]),
            list_groups=MagicMock(return_value=[]),
            get_stats=MagicMock(return_value={"total": 0, "users": 0, "groups": 0, "temporary": 0}),
            get_entry=MagicMock(return_value=None),
            clear_all=MagicMock(return_value=0),
        )
        fake_blacklist_module.BlacklistType = type("BlacklistType", (), {})

        fake_auth_module = types.ModuleType("auth_manager")
        fake_auth_module.auth_manager = types.SimpleNamespace(
            is_admin=MagicMock(return_value=True),
        )

        sys.modules.pop("plugins.hiklqqbot_blacklist_plugin", None)
        with patch.dict(
            sys.modules,
            {
                "blacklist_manager": fake_blacklist_module,
                "auth_manager": fake_auth_module,
            },
        ):
            cls.module = importlib.import_module("plugins.hiklqqbot_blacklist_plugin")

        cls.fake_blacklist_manager = cls.module.blacklist_manager
        cls.fake_auth_manager = cls.module.auth_manager

    def setUp(self):
        self.plugin = self.module.HiklqqbotBlacklistPlugin()

        for method_name in (
            "add_user",
            "add_group",
            "remove_user",
            "remove_group",
            "list_users",
            "list_groups",
            "get_stats",
            "get_entry",
            "clear_all",
        ):
            method = getattr(self.fake_blacklist_manager, method_name)
            method.reset_mock()

        self.fake_blacklist_manager.add_user.return_value = True
        self.fake_blacklist_manager.add_group.return_value = True
        self.fake_blacklist_manager.remove_user.return_value = True
        self.fake_blacklist_manager.remove_group.return_value = True
        self.fake_blacklist_manager.list_users.return_value = []
        self.fake_blacklist_manager.list_groups.return_value = []
        self.fake_blacklist_manager.get_stats.return_value = {
            "total": 0,
            "users": 0,
            "groups": 0,
            "temporary": 0,
        }
        self.fake_blacklist_manager.get_entry.return_value = None
        self.fake_blacklist_manager.clear_all.return_value = 0

        self.fake_auth_manager.is_admin.reset_mock()
        self.fake_auth_manager.is_admin.return_value = True

    def run_handle(self, params: str, user_id: str = "admin") -> str:
        return asyncio.run(self.plugin.handle(params, user_id=user_id))

    def test_add_rejects_non_admin(self):
        self.fake_auth_manager.is_admin.return_value = False

        response = self.run_handle("add user user-1 spam messages", user_id="guest")

        self.fake_blacklist_manager.add_user.assert_not_called()
        self.assertIn("管理员", response)

    def test_add_user_keeps_multi_word_reason(self):
        response = self.run_handle("add user user-1 repeated spam messages")

        self.fake_blacklist_manager.add_user.assert_called_once_with(
            "user-1",
            "repeated spam messages",
            "admin",
            None,
        )
        self.assertIn("repeated spam messages", response)

    def test_add_user_parses_optional_expiration_from_last_token(self):
        response = self.run_handle("add user user-1 repeated spam messages 1d")

        self.fake_blacklist_manager.add_user.assert_called_once()
        call_args = self.fake_blacklist_manager.add_user.call_args[0]
        self.assertEqual(call_args[0], "user-1")
        self.assertEqual(call_args[1], "repeated spam messages")
        self.assertEqual(call_args[2], "admin")
        self.assertIsNotNone(call_args[3])
        self.assertIn("repeated spam messages", response)

    def test_add_user_treats_invalid_expiration_suffix_as_reason_text(self):
        response = self.run_handle("add user user-1 repeated spam never")

        self.fake_blacklist_manager.add_user.assert_called_once_with(
            "user-1",
            "repeated spam never",
            "admin",
            None,
        )
        self.assertIn("repeated spam never", response)

    def test_usage_messages_reference_full_command_name(self):
        self.fake_blacklist_manager.get_stats.return_value = {
            "total": 2,
            "users": 1,
            "groups": 1,
            "temporary": 0,
        }
        list_response = self.run_handle("list")
        info_response = self.run_handle("info")
        add_response = self.run_handle("add user user-1")

        self.assertIn("/hiklqqbot_blacklist", self.plugin._get_help_message())
        self.assertIn("/hiklqqbot_blacklist list users", list_response)
        self.assertIn("/hiklqqbot_blacklist info <ID>", info_response)
        self.assertIn("/hiklqqbot_blacklist add <user|group> <ID> <原因> [过期时间]", add_response)
        self.assertNotIn("`/blacklist", list_response)


if __name__ == "__main__":
    unittest.main()
