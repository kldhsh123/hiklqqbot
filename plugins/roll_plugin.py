import logging
import random
import re

from plugins.base_plugin import BasePlugin


ROLL_PATTERN = re.compile(r"^(\d*)d(\d+)([+-]\d+)?$")


class RollPlugin(BasePlugin):
    def __init__(self):
        super().__init__(
            command="roll",
            description="掷骰子，支持 NdM 和修正值，例如 /roll d20 或 /roll 2d6+3",
            is_builtin=False,
        )
        self.logger = logging.getLogger("plugin.roll")
        self.default_count = 1
        self.default_sides = 100
        self.max_count = 20
        self.max_sides = 1000
        self.max_modifier = 100000

    def _parse_expression(self, params: str) -> tuple[str, int, int, int]:
        normalized = "".join(params.lower().split())
        if not normalized:
            return "1d100", self.default_count, self.default_sides, 0

        match = ROLL_PATTERN.fullmatch(normalized)
        if not match:
            raise ValueError("格式错误。示例：/roll、/roll d20、/roll 2d6+3")

        count_text, sides_text, modifier_text = match.groups()
        count = int(count_text) if count_text else 1
        sides = int(sides_text)
        modifier = int(modifier_text) if modifier_text else 0

        if not 1 <= count <= self.max_count:
            raise ValueError(f"骰子数量需在 1-{self.max_count} 之间")

        if not 2 <= sides <= self.max_sides:
            raise ValueError(f"骰子面数需在 2-{self.max_sides} 之间")

        if abs(modifier) > self.max_modifier:
            raise ValueError(f"修正值绝对值不能超过 {self.max_modifier}")

        expression = f"{count}d{sides}"
        if modifier:
            expression += f"{modifier:+d}"

        return expression, count, sides, modifier

    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        self.logger.info(f"收到 roll 命令，参数: {params}, 用户ID: {user_id}")

        try:
            expression, count, sides, modifier = self._parse_expression(params)
        except ValueError as exc:
            self.logger.warning(f"roll 命令参数无效: {params}")
            return str(exc)

        rolls = [random.randint(1, sides) for _ in range(count)]
        subtotal = sum(rolls)
        total = subtotal + modifier

        if count == 1:
            base_text = str(rolls[0])
        else:
            base_text = f"[{', '.join(str(roll) for roll in rolls)}]"

        if modifier > 0:
            detail = f"{base_text} + {modifier}"
        elif modifier < 0:
            detail = f"{base_text} - {abs(modifier)}"
        else:
            detail = base_text

        return f"🎲 {expression} = {detail} = {total}"
