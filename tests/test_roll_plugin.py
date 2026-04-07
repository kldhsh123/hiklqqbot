import asyncio
import unittest
from unittest.mock import patch

from plugins.roll_plugin import RollPlugin


class RollPluginTestCase(unittest.TestCase):
    def setUp(self):
        self.plugin = RollPlugin()

    def run_handle(self, params: str) -> str:
        return asyncio.run(self.plugin.handle(params, user_id="test-user"))

    @patch("plugins.roll_plugin.random.randint", return_value=42)
    def test_default_roll(self, mocked_randint):
        response = self.run_handle("")

        self.assertEqual(response, "🎲 1d100 = 42 = 42")
        mocked_randint.assert_called_once_with(1, 100)

    @patch("plugins.roll_plugin.random.randint", side_effect=[4, 2])
    def test_roll_with_modifier_and_spaces(self, mocked_randint):
        response = self.run_handle("2d6 + 3")

        self.assertEqual(response, "🎲 2d6+3 = [4, 2] + 3 = 9")
        self.assertEqual(mocked_randint.call_count, 2)

    def test_invalid_format(self):
        response = self.run_handle("abc")

        self.assertEqual(response, "格式错误。示例：/roll、/roll d20、/roll 2d6+3")

    def test_count_limit(self):
        response = self.run_handle("21d6")

        self.assertEqual(response, "骰子数量需在 1-20 之间")


if __name__ == "__main__":
    unittest.main()
