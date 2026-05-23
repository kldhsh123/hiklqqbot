import logging
import importlib
import pkgutil
import inspect
import json
import os
import sys
import math
from typing import Dict, List, Type, Optional, Tuple

from .base_plugin import BasePlugin
from auth_manager import auth_manager
from reply import Reply
from ui_builder import make_command_button, make_button_row, make_keyboard

# 菜单样式配置文件路径 (项目根目录)
MENU_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "menu_config.json")
MENU_INTRO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "menu_intro.json")

DEFAULT_MENU_CONFIG = {
    "root": {
        "header_md": "# 📖 帮助菜单\n\n{intro_block}",
        "footer_md": "\n> 点击上方文字进入对应分类",
        "show_buttons": True,
        "show_home_button": False,
    },
    "non_admin_category": {
        "header_md": "# 帮助 - {breadcrumb}\n\n{intro_block}",
        "before_commands_md": "## 命令 ({page}/{total_pages} 页, 共 {count} 个)\n",
        "footer_md": "\n> 发送 `/help` 返回主菜单",
        "columns": 3,
        "separator": "│",
        "show_description": False,
        "show_buttons": True,
        "show_home_button": True,
        "page_size": 12,
        "row_divider": "***",
    },
    "admin_category": {
        "header_md": "# 🔧 帮助 - 管理\n\n{intro_block}共 {count} 个命令，点击按钮执行：\n",
        "continuation_header_md": "# 🔧 帮助 - 管理 (续 {page})",
        "buttons_per_row": 3,
        "rows_per_msg_first": 4,
        "rows_per_msg_next": 5,
        "include_home_button": True,
    },
}

DEFAULT_MENU_CONFIG_FILE = {
    "_comment": "菜单排版配置 - 修改后需重启或重载插件生效",
    "_placeholders": "支持占位符: {breadcrumb}, {count}, {page}, {total_pages}, {intro}, {intro_block}",
    "root": {
        "_comment": "顶层 /help 菜单 - 完全自定义 markdown",
        **DEFAULT_MENU_CONFIG["root"],
    },
    "non_admin_category": {
        "_comment": "非管理分类: 命令网格排版, 中间竖线",
        **DEFAULT_MENU_CONFIG["non_admin_category"],
    },
    "admin_category": {
        "_comment": "管理分类: 全按钮模式, 塞不下分多条消息",
        **DEFAULT_MENU_CONFIG["admin_category"],
    },
}

DEFAULT_MENU_INTRO = {
    "root": "欢迎使用本机器人, 请选择一个分类查看可用命令：",
    "categories": {
        "管理": "这里是管理员命令入口。按钮对所有人可点，但实际执行仍会校验管理员权限。",
    },
}

DEFAULT_MENU_INTRO_FILE = {
    "_comment": "帮助菜单介绍文案配置 - 修改后需重启或重载插件生效",
    "_usage": "root 为顶层介绍; categories 的 key 为分类路径，如 管理 或 工具/媒体",
    "root": DEFAULT_MENU_INTRO["root"],
    "categories": DEFAULT_MENU_INTRO["categories"],
}


def _render_template(text: str, **kwargs) -> str:
    """渲染 markdown 模板, 替换 {key} 占位符。未匹配的占位符原样保留。"""
    if not text:
        return text
    try:
        # 用 format_map + defaultdict 容忍未知占位符
        class _SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"
        return text.format_map(_SafeDict(kwargs))
    except Exception:
        return text


def _load_menu_config() -> dict:
    """加载 menu_config.json, 失败时使用默认值"""
    try:
        if not os.path.exists(MENU_CONFIG_PATH):
            with open(MENU_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_MENU_CONFIG_FILE, f, ensure_ascii=False, indent=2)
            logging.getLogger("plugin_manager").info(
                f"menu_config.json 不存在，已自动生成默认配置: {MENU_CONFIG_PATH}"
            )

        with open(MENU_CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        # 深度合并: 用户配置覆盖默认
        merged = {k: dict(v) if isinstance(v, dict) else v for k, v in DEFAULT_MENU_CONFIG.items()}
        for k, v in user_config.items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                merged[k].update({sk: sv for sk, sv in v.items() if not sk.startswith("_")})
            else:
                merged[k] = v
        return merged
    except Exception as e:
        logging.getLogger("plugin_manager").error(f"加载 menu_config.json 失败, 使用默认配置: {e}")
    return DEFAULT_MENU_CONFIG


def _load_menu_intro() -> dict:
    """加载 menu_intro.json, 失败时使用默认值。"""
    try:
        if not os.path.exists(MENU_INTRO_PATH):
            with open(MENU_INTRO_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_MENU_INTRO_FILE, f, ensure_ascii=False, indent=2)
            logging.getLogger("plugin_manager").info(
                f"menu_intro.json 不存在，已自动生成默认配置: {MENU_INTRO_PATH}"
            )

        with open(MENU_INTRO_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)

        merged = {
            "root": DEFAULT_MENU_INTRO.get("root", ""),
            "categories": dict(DEFAULT_MENU_INTRO.get("categories", {})),
        }
        if isinstance(user_config, dict):
            root_intro = user_config.get("root")
            if isinstance(root_intro, str):
                merged["root"] = root_intro

            categories = user_config.get("categories")
            if isinstance(categories, dict):
                merged["categories"].update({
                    str(path): text
                    for path, text in categories.items()
                    if not str(path).startswith("_") and isinstance(text, str)
                })
        return merged
    except Exception as e:
        logging.getLogger("plugin_manager").error(f"加载 menu_intro.json 失败, 使用默认配置: {e}")
    return DEFAULT_MENU_INTRO

logger = logging.getLogger("plugin_manager")

# 从环境变量中读取是否启用命令前缀规范
ENFORCE_COMMAND_PREFIX = os.environ.get("ENFORCE_COMMAND_PREFIX", "true").lower() == "true"

class PluginManager:
    """
    插件管理器，负责加载和管理所有插件
    """
    
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self.logger = logger
        
    def load_plugins(self, plugin_package_name: str = "plugins") -> None:
        """
        从指定包中递归加载所有插件 (含子目录中的 Python 包)。

        - 子目录必须是 Python 包 (含 __init__.py) 才会被扫描
        - 跳过模块名 base_plugin / plugin_manager
        - 模块若定义 __all__ 且为空, 视为禁用, 跳过
        - 插件若未显式指定 category, 自动用其所在子目录路径作为 category
          (如 plugins/games/poker.py → 默认 category="games")
        - 顶层 plugins/ 下的插件保持原有默认值 ("其他")
        """
        self.logger.info(f"开始加载插件包: {plugin_package_name}")

        try:
            plugin_package = importlib.import_module(plugin_package_name)

            # walk_packages 递归遍历子包, prefix 用包名 + '.' 让 module_name 是全限定名
            iter_args = {
                "path": plugin_package.__path__,
                "prefix": f"{plugin_package_name}.",
            }
            for _, module_full_name, is_pkg in pkgutil.walk_packages(**iter_args):
                if is_pkg:
                    # 子包本身(__init__)跳过, 子包内的模块会被 walk_packages 继续遍历
                    continue
                # 提取末段模块名做过滤
                short_name = module_full_name.rsplit(".", 1)[-1]
                if short_name in ("base_plugin", "plugin_manager"):
                    continue

                try:
                    module = importlib.import_module(module_full_name)

                    # __all__ 显式空 → 禁用
                    if hasattr(module, "__all__") and len(getattr(module, "__all__")) == 0:
                        self.logger.info(f"模块 {module_full_name} 未导出任何内容，跳过")
                        continue

                    # 推导默认 category: 取子包路径 (plugins.games.poker → "games")
                    default_category = self._derive_default_category(plugin_package_name, module_full_name)

                    found_plugin = False
                    for _, obj in inspect.getmembers(module, inspect.isclass):
                        if (issubclass(obj, BasePlugin) and
                                obj is not BasePlugin and
                                obj.__module__ == module_full_name):
                            plugin = obj()
                            # 仅当插件未显式声明 category (即等于默认 "其他") 且来自子目录时, 用子目录作为 category
                            if default_category and plugin.category == "其他":
                                plugin.category = default_category
                            self.register_plugin(plugin)
                            found_plugin = True

                    if not found_plugin:
                        self.logger.debug(f"模块 {module_full_name} 中未找到插件类")

                except Exception as e:
                    self.logger.error(f"加载插件模块 {module_full_name} 失败: {e}")

            # 加载完成后清理重复命令
            self._clean_duplicate_commands()

            self.logger.info(f"插件加载完成，共注册 {len(self._unique_plugins())} 个插件实例 (含别名共 {len(self.plugins)} 个命令)")

        except Exception as e:
            self.logger.error(f"加载插件包 {plugin_package_name} 失败: {e}")

    def _derive_default_category(self, package_name: str, module_full_name: str) -> Optional[str]:
        """从模块全限定名推导默认 category。

        plugins.games.poker → "games"
        plugins.tools.media.image → "tools/media"
        plugins.foo (顶层) → None (不覆盖默认 "其他")
        """
        # 去掉顶层包名, 剩余路径 = 中间子包
        # plugins.games.poker → ["games", "poker"], 去掉末尾模块名 → ["games"]
        parts = module_full_name.split(".")
        if len(parts) <= 2:
            # plugins.foo: 顶层模块, 无子包
            return None
        # 去掉顶层包名(plugins) 和 末尾模块名(poker), 中间就是子包路径
        sub_parts = parts[1:-1]
        return "/".join(sub_parts) if sub_parts else None
        
    def _clean_duplicate_commands(self):
        """
        清理重复的命令和不规范的命令格式
        根据配置决定是否确保所有命令都以/开头，并处理重复命令
        多命令插件的所有命令都会被一并规范化, 共享同一 plugin 实例
        """
        self.logger.info("开始清理重复和非标准命令...")

        cleaned_plugins = {}
        duplicate_count = 0
        # 记录已规范化过 commands 列表的插件 (按 id 去重, 避免同一插件多个命令重复处理)
        normalized_plugin_ids = set()

        for cmd, plugin in list(self.plugins.items()):
            # 一次性规范化该插件的 commands 列表
            if id(plugin) not in normalized_plugin_ids:
                normalized_plugin_ids.add(id(plugin))
                if ENFORCE_COMMAND_PREFIX:
                    new_commands = []
                    for c in plugin.commands:
                        new_commands.append(c if c.startswith('/') else f'/{c}')
                    plugin.commands = new_commands
                    plugin.command = new_commands[0]

            # 计算该 cmd 规范化后的值
            if ENFORCE_COMMAND_PREFIX and not cmd.startswith('/'):
                new_cmd = f'/{cmd}'
                self.logger.warning(f"命令 {cmd} 不符合规范，已更正为 {new_cmd}")
                if new_cmd in cleaned_plugins and cleaned_plugins[new_cmd] is not plugin:
                    self.logger.warning(f"命令冲突: {cmd} 和 {new_cmd} 指向不同插件")
                    duplicate_count += 1
                    continue
                cleaned_plugins[new_cmd] = plugin
                if cmd in self.plugins:
                    del self.plugins[cmd]
            else:
                cleaned_plugins[cmd] = plugin

        self.plugins.clear()
        for cmd, plugin in cleaned_plugins.items():
            self.plugins[cmd] = plugin

        self.logger.info(f"命令清理完成。标准化 {len(cleaned_plugins)} 个命令，移除 {duplicate_count} 个重复命令。")

    def register_plugin(self, plugin: BasePlugin) -> None:
        """
        注册一个插件 (支持多命令: 遍历 plugin.commands 全部注册到 dict 指向同一实例)
        """
        # 规范化 commands 列表 (确保以 / 开头)
        normalized = []
        for c in plugin.commands:
            if ENFORCE_COMMAND_PREFIX and not c.startswith('/'):
                normalized.append(f'/{c}')
            else:
                normalized.append(c)
        plugin.commands = normalized
        plugin.command = normalized[0]  # 主命令同步更新

        aliases_log = f" (别名: {', '.join(normalized[1:])})" if len(normalized) > 1 else ""

        # 注册每个命令
        for command in normalized:
            # 移除不带前缀的同名版本 (兼容旧数据)
            plain_command = command.lstrip('/')
            if ENFORCE_COMMAND_PREFIX and plain_command in self.plugins:
                self.logger.warning(f"发现不带前缀的插件命令 {plain_command}，将被替换为 {command}")
                del self.plugins[plain_command]

            if command in self.plugins and self.plugins[command] is not plugin:
                self.logger.warning(f"插件命令 {command} 已存在，将被覆盖")

            self.plugins[command] = plugin

        self.logger.info(
            f"注册插件: {plugin.__class__.__name__}, 主命令: {plugin.command}{aliases_log}, "
            f"类型: {'内置' if plugin.is_builtin else '自定义'}"
        )
        
    def register_plugins_from_directory(self, directory: str = "plugins") -> None:
        """
        从指定目录加载所有插件
        
        Args:
            directory: 插件目录路径
        """
        self.logger.info(f"从目录'{directory}'加载插件...")
        
        # 确保目录存在
        if not os.path.exists(directory):
            self.logger.error(f"插件目录'{directory}'不存在")
            return
            
        # 获取所有插件文件
        plugin_files = [
            f[:-3] for f in os.listdir(directory) 
            if f.endswith(".py") and f != "__init__.py" and f != "base_plugin.py" and f != "plugin_manager.py"
        ]
        
        # 导入所有插件模块
        for plugin_file in plugin_files:
            try:
                # 构建模块名
                module_name = f"{directory}.{plugin_file}"
                if directory.startswith("."):
                    module_name = module_name[1:]
                
                # 导入模块
                module = importlib.import_module(module_name)
                
                # 查找模块中所有BasePlugin的子类
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and 
                        issubclass(obj, BasePlugin) and 
                        obj != BasePlugin):
                        
                        # 实例化并注册插件
                        plugin = obj()
                        self.register_plugin(plugin)
                        
            except Exception as e:
                self.logger.error(f"加载插件'{plugin_file}'失败: {e}")
                
    def get_plugin(self, command: str) -> Optional[BasePlugin]:
        """
        获取指定命令对应的插件
        
        Args:
            command: 插件命令
            
        Returns:
            对应的插件实例，如果不存在则返回None
        """
        return self.plugins.get(command)
        
    def _unique_plugins(self) -> List[BasePlugin]:
        """返回去重后的插件实例列表 (多命令插件在 dict 里有多个 key 但只算一次)"""
        seen = set()
        result = []
        for p in self.plugins.values():
            if id(p) not in seen:
                seen.add(id(p))
                result.append(p)
        return result

    def get_all_plugins(self) -> List[BasePlugin]:
        """
        获取所有已加载的插件

        Returns:
            所有插件实例的列表
        """
        return self._unique_plugins()

    def get_builtin_plugins(self) -> List[BasePlugin]:
        """
        获取所有内置插件

        Returns:
            所有内置插件实例的列表
        """
        return [plugin for plugin in self._unique_plugins() if plugin.is_builtin]

    def get_custom_plugins(self) -> List[BasePlugin]:
        """
        获取所有自定义插件

        Returns:
            所有自定义插件实例的列表
        """
        return [plugin for plugin in self._unique_plugins() if not plugin.is_builtin]
        
    def get_help(self, show_hidden: bool = False) -> str:
        """
        获取所有插件的帮助信息 (旧接口, 纯文本, 保留兼容)

        Args:
            show_hidden: 是否显示隐藏的插件

        Returns:
            帮助信息文本
        """
        if not self.plugins:
            return "没有可用的命令"
        
        # 分类插件
        builtin_plugins = []
        custom_plugins = []

        for plugin in self._unique_plugins():
            # 跳过隐藏插件
            if hasattr(plugin, 'hidden') and plugin.hidden and not show_hidden:
                continue

            if hasattr(plugin, 'is_builtin') and plugin.is_builtin:
                builtin_plugins.append(plugin)
            else:
                custom_plugins.append(plugin)
        
        # 构建帮助文本
        help_text = "可用命令列表:\n"
        
        if builtin_plugins:
            help_text += "\n系统命令:\n"
            for plugin in builtin_plugins:
                help_text += f"- {plugin.help()}\n"
                
        if custom_plugins:
            help_text += "\n自定义命令:\n"
            for plugin in custom_plugins:
                help_text += f"- {plugin.help()}\n"

        return help_text

    # ---------- 多级分类支持 ----------

    def _split_category(self, plugin: BasePlugin) -> List[str]:
        """把插件的 category 路径切片成层级列表。空段过滤。"""
        raw = (plugin.category or "其他").strip("/").strip()
        if not raw:
            return ["其他"]
        return [seg.strip() for seg in raw.split("/") if seg.strip()]

    def build_category_tree(self, show_hidden: bool = False) -> Dict:
        """构建嵌套分类树。

        返回结构: {分类名: {"_self": [plugin...], "_children": {子分类: {...}}}}
        """
        tree: Dict = {}
        for plugin in self._unique_plugins():
            if plugin.hidden and not show_hidden:
                continue
            path = self._split_category(plugin)
            cur = tree
            last = None
            for seg in path:
                cur = cur.setdefault(seg, {"_self": [], "_children": {}})
                last = cur
                cur = cur["_children"]
            if last is not None:
                last["_self"].append(plugin)
        return tree

    def _walk_tree(self, tree: Dict, path_segments: List[str]) -> Optional[Dict]:
        """按路径段在树中导航, 返回末层节点 {"_self": [...], "_children": {...}}。"""
        node = {"_children": tree, "_self": []}  # 虚拟根
        for seg in path_segments:
            children = node.get("_children", {})
            if seg not in children:
                return None
            node = children[seg]
        return node

    def get_help_rich(
        self,
        path: str = "",
        page: int = 1,
        caller_openid: Optional[str] = None,
        is_group: bool = False,
    ) -> Reply:
        """生成富帮助菜单 (单条 Reply, 兼容旧调用)。"""
        replies = self.get_help_replies(path=path, page=page, caller_openid=caller_openid, is_group=is_group)
        return replies[0] if replies else Reply(text="（无帮助内容）")

    def get_help_replies(
        self,
        path: str = "",
        page: int = 1,
        caller_openid: Optional[str] = None,
        is_group: bool = False,
    ) -> List[Reply]:
        """生成 markdown + 按钮的富帮助菜单, 可返回多条 Reply (按钮塞不下时分多条)。

        Args:
            path: 分类路径; 空表示顶层
            page: 页码 (仅命令列表会分页)
            caller_openid: 调用者 openid (保留兼容，当前不再用于限制帮助菜单按钮权限)
            is_group: 是否群聊场景 (影响 markdown 内点击文字标签选择)
        """
        from config import HELP_BUTTON_ACTION_TYPE

        menu_config = _load_menu_config()
        intro_config = _load_menu_intro()
        tree = self.build_category_tree(show_hidden=False)
        path_segments = [p for p in path.strip("/").split("/") if p.strip()] if path else []

        if not path_segments:
            return [self._render_root_help(
                tree, caller_openid, menu_config, HELP_BUTTON_ACTION_TYPE, is_group, intro_config,
            )]

        node = self._walk_tree(tree, path_segments)
        if not node:
            return [Reply(text=f"未找到分类: /{'/'.join(path_segments)}\n可发送 /help 查看所有分类")]

        # 管理分类: 全按钮模式 (塞不下分多条)
        if path_segments[0] == "管理":
            return self._render_admin_category(
                path_segments, node, caller_openid, menu_config, HELP_BUTTON_ACTION_TYPE, intro_config,
            )

        # 其他分类: markdown 左右两列排版
        return [self._render_category_help_md(
            path_segments, node, page, caller_openid, menu_config, HELP_BUTTON_ACTION_TYPE, is_group, intro_config,
        )]

    def _get_menu_intro(self, intro_config: dict, path_segments: List[str]) -> str:
        """获取当前路径的介绍文案。分类按最近的父路径回退。"""
        if not path_segments:
            return str(intro_config.get("root", "") or "")

        categories = intro_config.get("categories", {}) or {}
        for idx in range(len(path_segments), 0, -1):
            intro = categories.get("/".join(path_segments[:idx]))
            if isinstance(intro, str) and intro:
                return intro
        return ""

    def _build_help_template_ctx(
        self,
        *,
        path_segments: Optional[List[str]] = None,
        count: int = 0,
        page: int = 1,
        total_pages: int = 1,
        intro_config: Optional[dict] = None,
    ) -> Dict[str, object]:
        path_segments = path_segments or []
        intro = self._get_menu_intro(intro_config or {}, path_segments)
        return {
            "breadcrumb": " / ".join(path_segments),
            "count": count,
            "page": page,
            "total_pages": total_pages,
            "intro": intro,
            "intro_block": f"{intro}\n\n***\n\n" if intro else "",
        }

    def _render_root_help(self, tree: Dict, caller: Optional[str],
                          menu_config: dict, button_action_type: int,
                          is_group: bool = False,
                          intro_config: Optional[dict] = None) -> Reply:
        """顶层菜单: 用 root.header_md / footer_md 自由模板。"""
        cfg = menu_config.get("root", {})
        show_buttons = bool(cfg.get("show_buttons", True))

        categories = sorted(tree.keys())
        total_count = sum(self._count_plugins(tree[c]) for c in categories)
        ctx = self._build_help_template_ctx(count=total_count, intro_config=intro_config)

        parts: List[str] = []
        # header
        header = _render_template(cfg.get("header_md", ""), **ctx)
        if header:
            parts.append(header)

        # 分类条目 (固定渲染)
        if not categories:
            parts.append("（暂无可用命令）")
        else:
            for cat in categories:
                count = self._count_plugins(tree[cat])
                click = self._cmd_link(f"/help {cat}", show=f"查看「{cat}」", is_group=is_group)
                parts.append(f"- **{cat}** ({count} 个命令)  {click}")

        # footer
        footer = _render_template(cfg.get("footer_md", ""), **ctx)
        if footer:
            parts.append(footer)

        markdown = "\n".join(parts)

        keyboard = None
        if show_buttons and categories:
            rows, current_row = [], []
            for idx, cat in enumerate(categories[:15]):
                current_row.append(make_command_button(
                    button_id=f"cat_{idx}", label=cat, command=f"/help {cat}",
                    action_type=button_action_type, style=1,
                ))
                if len(current_row) == 3:
                    rows.append(make_button_row(current_row))
                    current_row = []
            if current_row:
                rows.append(make_button_row(current_row))
            if rows:
                keyboard = make_keyboard(rows)

        return Reply(markdown=markdown, keyboard=keyboard)

    # ---------- cmd-input / cmd-enter 标签 ----------

    def _cmd_link(self, command: str, show: Optional[str] = None,
                  is_group: bool = False, direct_send: bool = False) -> str:
        """生成 markdown 内可点击的命令链接。

        Args:
            command: 要触发的命令文本 (含 /)
            show: 显示文字 (默认显示命令本身)
            is_group: 是否群聊场景 (群聊只能用 cmd-input)
            direct_send: 是否要求点击直接发送 (单聊场景才有效)

        Returns:
            markdown 片段, 形如 '<qqbot-cmd-input text="%2Fhelp" show="点我" />'
        """
        from urllib.parse import quote
        encoded = quote(command, safe="")
        display = show or command
        # 群聊不支持 cmd-enter, 强制用 cmd-input; 单聊根据 direct_send 选择
        if not is_group and direct_send:
            return f'<qqbot-cmd-enter text="{encoded}" />'
        return f'<qqbot-cmd-input text="{encoded}" show="{display}" reference="false" />'

    # ---------- 管理分类: 全按钮模式 ----------

    def _render_admin_category(self, path_segments: List[str], node: Dict,
                                caller: Optional[str], menu_config: dict,
                                action_type: int,
                                intro_config: Optional[dict] = None) -> List[Reply]:
        """管理分类专属渲染: 全按钮模式, 塞不下分多条。"""
        cfg = menu_config.get("admin_category", {})
        BUTTONS_PER_ROW = int(cfg.get("buttons_per_row", 3))
        ROWS_FIRST = int(cfg.get("rows_per_msg_first", 4))
        ROWS_NEXT = int(cfg.get("rows_per_msg_next", 5))
        header_tpl = cfg.get("header_md", "# 帮助 - 管理\n\n共 {count} 个命令，点击按钮执行：\n")
        cont_header_tpl = cfg.get("continuation_header_md", "# 帮助 - 管理 (续 {page})")
        include_home = bool(cfg.get("include_home_button", True))

        plugins = self._collect_all_plugins(node)
        breadcrumb = " / ".join(path_segments)

        replies: List[Reply] = []
        idx = 0
        total = len(plugins)
        page_num = 0
        while idx < total:
            page_num += 1
            is_first = (page_num == 1)
            rows_budget = ROWS_FIRST if (is_first and include_home) else ROWS_NEXT
            buttons_budget = rows_budget * BUTTONS_PER_ROW

            chunk = plugins[idx:idx + buttons_budget]
            idx += len(chunk)

            rows, current_row = [], []
            for i, p in enumerate(chunk):
                current_row.append(make_command_button(
                    button_id=f"adm_{page_num}_{i}",
                    label=p.get_display_name(),
                    command=p.command,
                    action_type=action_type,
                    style=1,
                ))
                if len(current_row) == BUTTONS_PER_ROW:
                    rows.append(make_button_row(current_row))
                    current_row = []
            if current_row:
                rows.append(make_button_row(current_row))

            if is_first and include_home:
                rows.append(make_button_row([
                    make_command_button(
                        "home", "🏠 主菜单", "/help",
                        action_type=action_type, style=0,
                    ),
                ]))

            ctx = self._build_help_template_ctx(
                path_segments=path_segments,
                count=total,
                page=page_num,
                intro_config=intro_config,
            )
            if is_first:
                md = _render_template(header_tpl, **ctx)
            else:
                md = _render_template(cont_header_tpl, **ctx)

            replies.append(Reply(markdown=md, keyboard=make_keyboard(rows)))
        return replies if replies else [Reply(text="管理分类暂无命令")]

    def _collect_all_plugins(self, node: Dict) -> List[BasePlugin]:
        result = list(node.get("_self", []))
        for child in node.get("_children", {}).values():
            result.extend(self._collect_all_plugins(child))
        return result

    # ---------- 非管理分类: 左右两列排版 ----------

    def _render_category_help_md(
        self, path_segments: List[str], node: Dict, page: int,
        caller: Optional[str], menu_config: dict, button_action_type: int,
        is_group: bool,
        intro_config: Optional[dict] = None,
    ) -> Reply:
        """非管理分类: 命令网格排版 (默认 3 列) + 自由 md 模板。"""
        cfg = menu_config.get("non_admin_category", {})
        columns = max(1, int(cfg.get("columns", 3)))
        separator = cfg.get("separator", "│")
        show_description = bool(cfg.get("show_description", False))
        show_buttons = bool(cfg.get("show_buttons", True))
        show_home_button = bool(cfg.get("show_home_button", True))
        page_size = max(1, int(cfg.get("page_size", 12)))
        row_divider = cfg.get("row_divider", "***")
        header_tpl = cfg.get("header_md", "# 帮助 - {breadcrumb}\n")
        before_cmds_tpl = cfg.get("before_commands_md", "## 命令 ({page}/{total_pages} 页, 共 {count} 个)\n")
        footer_tpl = cfg.get("footer_md", "\n> 发送 `/help` 返回主菜单")

        breadcrumb = " / ".join(path_segments)
        children: Dict = node.get("_children", {}) or {}
        plugins: List[BasePlugin] = node.get("_self", []) or []

        # 分页
        total_pages = max(1, math.ceil(len(plugins) / page_size)) if plugins else 1
        page = max(1, min(page, total_pages))
        start = (page - 1) * page_size
        page_plugins = plugins[start:start + page_size]

        ctx = self._build_help_template_ctx(
            path_segments=path_segments,
            count=len(plugins),
            page=page,
            total_pages=total_pages,
            intro_config=intro_config,
        )
        parts: List[str] = []

        header = _render_template(header_tpl, **ctx)
        if header:
            parts.append(header)

        # 子分类
        if children:
            parts.append("## 子分类")
            for sub in sorted(children.keys()):
                sub_count = self._count_plugins(children[sub])
                click = self._cmd_link(f"/help {breadcrumb}/{sub}", show=f"打开「{sub}」", is_group=is_group)
                parts.append(f"- **{sub}** ({sub_count} 个命令)  {click}")
            parts.append("")
            if row_divider:
                parts.append(row_divider)

        if plugins:
            before_cmds = _render_template(before_cmds_tpl, **ctx)
            if before_cmds:
                parts.append(before_cmds)

            # 网格排版: 每 columns 个命令一行, 中间用 separator
            for i in range(0, len(page_plugins), columns):
                row_plugins = page_plugins[i:i + columns]
                cells = []
                for p in row_plugins:
                    name = p.get_display_name()
                    cell = self._cmd_link(p.command, show=name, is_group=is_group)
                    if show_description:
                        cell = f"{cell} ({p.description})"
                    cells.append(cell)
                # 关键: 单元数 == 1 时不用分隔符 (单独一行不加 │)
                if len(cells) == 1:
                    parts.append(cells[0])
                else:
                    parts.append(f" {separator} ".join(cells))
                if row_divider:
                    parts.append(row_divider)
        elif not children:
            parts.append("（此分类无命令）")

        footer = _render_template(footer_tpl, **ctx)
        if footer:
            parts.append(footer)

        # 按钮: 翻页 + 返回主菜单
        keyboard = None
        rows = []

        if show_buttons and total_pages > 1:
            nav_btns = []
            if page > 1:
                nav_btns.append(make_command_button(
                    "prev", "⬅ 上一页", f"/help {breadcrumb} {page - 1}",
                    action_type=button_action_type, style=0,
                ))
            if page < total_pages:
                nav_btns.append(make_command_button(
                    "next", "下一页 ➡", f"/help {breadcrumb} {page + 1}",
                    action_type=button_action_type, style=0,
                ))
            if nav_btns:
                rows.append(make_button_row(nav_btns))

        if show_home_button:
            rows.append(make_button_row([
                make_command_button(
                    "home", "🏠 返回主菜单", "/help",
                    action_type=button_action_type, style=1,
                ),
            ]))

        if rows:
            keyboard = make_keyboard(rows)

        return Reply(markdown="\n".join(parts), keyboard=keyboard)

    def _build_category_keyboard(
        self, path_segments: List[str], children: Dict,
        plugins: List[BasePlugin], page: int, total_pages: int,
        caller: Optional[str], action_type: int,
    ) -> Optional[Dict]:
        """构造分类页的按钮键盘。"""
        rows = []
        current_path = "/".join(path_segments)

        # Row 1-2: 子分类入口 (最多 6 个)
        if children:
            sub_buttons = []
            for idx, sub in enumerate(sorted(children.keys())[:6]):
                sub_path = f"{current_path}/{sub}"
                sub_buttons.append(make_command_button(
                    button_id=f"sub_{idx}",
                    label=sub,
                    command=f"/help {sub_path}",
                    action_type=action_type,
                    style=1,
                ))
            # 按每行3个切分
            for i in range(0, len(sub_buttons), 3):
                rows.append(make_button_row(sub_buttons[i:i + 3]))

        # Row: 翻页 (仅当总页数 > 1)
        if total_pages > 1:
            page_buttons = []
            if page > 1:
                page_buttons.append(make_command_button(
                    button_id="prev",
                    label=f"⬅ 上一页",
                    command=f"/help {current_path} {page - 1}",
                    action_type=action_type,
                    style=0,
                ))
            if page < total_pages:
                page_buttons.append(make_command_button(
                    button_id="next",
                    label=f"下一页 ➡",
                    command=f"/help {current_path} {page + 1}",
                    action_type=action_type,
                    style=0,
                ))
            if page_buttons:
                rows.append(make_button_row(page_buttons))

        # Row: 导航 (返回上级 + 主菜单)
        nav_buttons = []
        if len(path_segments) > 1:
            parent_path = "/".join(path_segments[:-1])
            nav_buttons.append(make_command_button(
                button_id="back",
                label=f"⬆ 返回 {path_segments[-2]}",
                command=f"/help {parent_path}",
                action_type=action_type,
                style=0,
            ))
        nav_buttons.append(make_command_button(
            button_id="home",
            label="🏠 主菜单",
            command="/help",
            action_type=action_type,
            style=0,
        ))
        rows.append(make_button_row(nav_buttons))

        return make_keyboard(rows[:5])  # QQ 最多 5 行

    def _count_plugins(self, node: Dict) -> int:
        """递归统计节点下所有插件数"""
        count = len(node.get("_self", []))
        for child in node.get("_children", {}).values():
            count += self._count_plugins(child)
        return count

    async def handle_command(self, command: str, params: str = "", user_id: str = None, **kwargs) -> str:
        """
        处理命令
        
        Args:
            command: 命令名称
            params: 命令参数
            user_id: 用户ID，用于权限控制
            **kwargs: 额外参数，如group_openid等
            
        Returns:
            处理结果
        """
        self.logger.info(f"处理命令: {command}, 参数: {params}, 用户ID: {user_id}, 额外参数: {kwargs}")
        
        # 检查维护模式
        if auth_manager.is_maintenance_mode() and not auth_manager.is_admin(user_id):
            return "机器人当前处于维护模式，仅管理员可用"
        
        # 根据配置处理命令前缀
        # 如果强制规范化打开，但命令不以/开头，自动添加/
        if ENFORCE_COMMAND_PREFIX and not command.startswith('/'):
            command = f'/{command}'
        
        plugin = self.get_plugin(command)
        if not plugin:
            # 如果找不到命令，且命令以/开头，尝试查找不带/的版本（兼容模式）
            if command.startswith('/') and not ENFORCE_COMMAND_PREFIX:
                plain_command = command[1:]
                plugin = self.get_plugin(plain_command)
            
            # 命令不存在，返回提示信息
            if not plugin:
                return f"未找到命令: {command}\n你可以通过 /help 获取可用命令列表"
        
        try:
            # 将额外参数传递给插件的handle方法
            return await plugin.handle(params, user_id, **kwargs)
        except Exception as e:
            error_msg = f"处理命令 {command} 时出错: {str(e)}"
            self.logger.error(error_msg)
            return f"执行命令出错: {str(e)}"

# 创建全局插件管理器实例
plugin_manager = PluginManager() 
