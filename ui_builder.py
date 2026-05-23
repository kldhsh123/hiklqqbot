"""按钮 / 键盘构造工具。

只关心数据结构, 不发请求。返回的 dict 可直接作为 Reply.keyboard 字段, 或塞进消息 payload 的 keyboard 字段。

action_type:
- 1 = 后端回调 (点击不发消息, 触发 INTERACTION_CREATE 事件)
- 2 = 发送型 (点击直接发送 data 到聊天框, enter 仅单聊有效)

permission:
- 不传 permission_user_ids 时 → permission.type=2 (所有人可点)
- 传 permission_user_ids 时 → permission.type=0 + specify_user_ids

注意: permission.type=1 是 QQ 群/频道的"管理者", 不是机器人 admin。
想要"仅机器人 admin 可点", 用 make_admin_button() (内部把当前 admins 列表灌入 specify_user_ids)。
"""

from typing import List, Optional, Dict, Any


def make_command_button(
    button_id: str,
    label: str,
    command: str,
    *,
    action_type: int = 2,
    permission_user_ids: Optional[List[str]] = None,
    style: int = 0,
    visited_label: Optional[str] = None,
    unsupport_tips: str = "当前版本不支持此按钮",
) -> Dict[str, Any]:
    """构造单个命令按钮。

    Args:
        button_id: 按钮唯一标识 (同一消息内不重复)
        label: 显示文本
        command: 点击触发的命令 (如 "/help 管理")
        action_type: 2=发送到聊天框 (enter 仅单聊有效), 1=后端回调
        permission_user_ids: 若提供, 只这些 openid 可点击
        style: 0=灰色线框, 1=蓝色线框
        visited_label: 点击后显示的文本 (默认与 label 相同)
    """
    permission: Dict[str, Any]
    if permission_user_ids:
        permission = {"type": 0, "specify_user_ids": list(permission_user_ids)}
    else:
        permission = {"type": 2}

    return {
        "id": str(button_id),
        "render_data": {
            "label": label,
            "visited_label": visited_label or label,
            "style": style,
        },
        "action": {
            "type": action_type,
            "permission": permission,
            "data": command,
            "unsupport_tips": unsupport_tips,
        },
    }


def make_admin_button(
    button_id: str,
    label: str,
    command: str,
    *,
    action_type: int = 2,
    style: int = 0,
    visited_label: Optional[str] = None,
) -> Dict[str, Any]:
    """构造仅机器人管理员可点的按钮。

    自动从 auth_manager 拉取当前 admin 列表填入 specify_user_ids。
    与 QQ 群/频道管理者无关 (permission.type=1 是后者, 这里用 type=0 显式列表)。
    """
    from auth_manager import auth_manager
    admin_ids = auth_manager.get_admins()
    return make_command_button(
        button_id, label, command,
        action_type=action_type,
        permission_user_ids=admin_ids if admin_ids else None,
        style=style,
        visited_label=visited_label,
    )


def make_group_admin_button(
    button_id: str,
    label: str,
    command: str,
    *,
    action_type: int = 2,
    style: int = 0,
    visited_label: Optional[str] = None,
    unsupport_tips: str = "仅群/频道管理员可点击",
) -> Dict[str, Any]:
    """构造仅 QQ 群/频道管理者可点的按钮 (permission.type=1)。

    这是 QQ 平台层面的"群主/管理员"权限, 由 QQ 客户端判断, 与机器人 admin 列表无关。
    适合做"仅群管理可见的危险操作"等场景, 如踢人、禁言、群公告等命令快捷入口。
    """
    return {
        "id": str(button_id),
        "render_data": {
            "label": label,
            "visited_label": visited_label or label,
            "style": style,
        },
        "action": {
            "type": action_type,
            "permission": {"type": 1},
            "data": command,
            "unsupport_tips": unsupport_tips,
        },
    }


def make_button_row(buttons: List[Dict[str, Any]]) -> Dict[str, Any]:
    """单行最多 5 个按钮 (超出 QQ 不显示)。"""
    return {"buttons": buttons[:5]}


def make_keyboard(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """最多 5 行 (超出 QQ 不显示)。返回完整 keyboard payload, 含 content 包裹。"""
    return {"content": {"rows": rows[:5]}}
