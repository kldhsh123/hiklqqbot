import logging
import importlib
import pkgutil
import inspect
import os
import sys
from typing import Dict, List, Type, Optional

from .base_plugin import BasePlugin
from auth_manager import auth_manager

logger = logging.getLogger("plugin_manager")

class PluginManager:
    """
    插件管理器，负责加载和管理所有插件
    """
    
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self.logger = logger
        
    def load_plugins(self, plugin_package_name: str = "plugins") -> None:
        """
        从指定包中加载所有插件
        
        Args:
            plugin_package_name: 插件包名称
        """
        self.logger.info(f"开始加载插件，包名: {plugin_package_name}")
        
        try:
            plugin_package = importlib.import_module(plugin_package_name)
            
            # 遍历包中的所有模块
            for _, module_name, is_pkg in pkgutil.iter_modules(plugin_package.__path__):
                if is_pkg or module_name in ["base_plugin", "plugin_manager"]:
                    continue
                
                try:
                    # 导入模块
                    module_path = f"{plugin_package_name}.{module_name}"
                    module = importlib.import_module(module_path)
                    
                    # 查找模块中的插件类
                    for _, obj in inspect.getmembers(module, inspect.isclass):
                        if (issubclass(obj, BasePlugin) and 
                            obj is not BasePlugin and 
                            obj.__module__ == module_path):
                            
                            # 实例化插件并注册
                            plugin = obj()
                            self.register_plugin(plugin)
                            
                except Exception as e:
                    self.logger.error(f"加载插件模块 {module_name} 失败: {str(e)}")
            
            # 加载完成后清理重复命令
            self._clean_duplicate_commands()
            
            self.logger.info(f"插件加载完成，共加载 {len(self.plugins)} 个插件")
            
        except Exception as e:
            self.logger.error(f"加载插件包 {plugin_package_name} 失败: {str(e)}")
        
    def _clean_duplicate_commands(self):
        """
        清理重复的命令和不规范的命令格式
        确保所有命令都以/开头，且不存在重复命令
        """
        self.logger.info("开始清理重复和非标准命令...")
        
        # 收集所有插件标准化后的命令
        cleaned_plugins = {}
        duplicate_count = 0
        
        for cmd, plugin in list(self.plugins.items()):
            # 确保命令以/开头
            if not cmd.startswith('/'):
                new_cmd = f'/{cmd}'
                self.logger.warning(f"命令 {cmd} 不符合规范，已更正为 {new_cmd}")
                plugin.command = new_cmd  # 更新插件内部命令属性
                
                # 如果新命令已存在，记录冲突
                if new_cmd in cleaned_plugins:
                    self.logger.warning(f"命令冲突: {cmd} 和 {new_cmd} 指向不同插件")
                    duplicate_count += 1
                    continue  # 跳过这个冲突的命令
                    
                # 添加标准化的命令
                cleaned_plugins[new_cmd] = plugin
                
                # 删除原始非标准命令
                if cmd in self.plugins:
                    del self.plugins[cmd]
            else:
                # 命令已符合规范，直接添加
                cleaned_plugins[cmd] = plugin
        
        # 更新插件列表
        self.plugins.clear()
        for cmd, plugin in cleaned_plugins.items():
            self.plugins[cmd] = plugin
            
        self.logger.info(f"命令清理完成。标准化 {len(cleaned_plugins)} 个命令，移除 {duplicate_count} 个重复命令。")
        
    def register_plugin(self, plugin: BasePlugin) -> None:
        """
        注册一个插件
        
        Args:
            plugin: 插件实例
        """
        # 标准化命令名称（确保以/开头）
        command = plugin.command
        if not command.startswith('/'):
            command = f'/{command}'
            # 更新插件内部的命令属性
            plugin.command = command
        
        # 检查是否存在同名的不带前缀版本
        base_name = command.lstrip('/')
        plain_command = base_name  # 不带前缀的版本
        
        # 如果存在不带前缀的版本，移除它
        if plain_command in self.plugins:
            self.logger.warning(f"发现不带前缀的插件命令 {plain_command}，将被替换为 {command}")
            del self.plugins[plain_command]
        
        # 如果命令已存在，记录警告
        if command in self.plugins:
            self.logger.warning(f"插件命令 {command} 已存在，将被覆盖")
        
        # 注册标准化后的命令
        self.plugins[command] = plugin
        self.logger.info(f"注册插件: {plugin.__class__.__name__}, 命令: {command}, 类型: {'内置' if plugin.is_builtin else '自定义'}")
        
        
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
        
    def get_all_plugins(self) -> List[BasePlugin]:
        """
        获取所有已加载的插件
        
        Returns:
            所有插件实例的列表
        """
        return list(self.plugins.values())
        
    def get_builtin_plugins(self) -> List[BasePlugin]:
        """
        获取所有内置插件
        
        Returns:
            所有内置插件实例的列表
        """
        return [plugin for plugin in self.plugins.values() if plugin.is_builtin]
        
    def get_custom_plugins(self) -> List[BasePlugin]:
        """
        获取所有自定义插件
        
        Returns:
            所有自定义插件实例的列表
        """
        return [plugin for plugin in self.plugins.values() if not plugin.is_builtin]
        
    def get_help(self, show_hidden: bool = False) -> str:
        """
        获取所有插件的帮助信息
        
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
        
        for command, plugin in self.plugins.items():
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
    
    async def handle_command(self, command: str, params: str = "", user_id: str = None) -> str:
        """
        处理命令
        
        Args:
            command: 命令名称
            params: 命令参数
            user_id: 用户ID，用于权限控制
            
        Returns:
            处理结果
        """
        self.logger.info(f"处理命令: {command}, 参数: {params}, 用户ID: {user_id}")
        
        # 检查维护模式
        if auth_manager.is_maintenance_mode() and not auth_manager.is_admin(user_id):
            return "机器人当前处于维护模式，仅管理员可用"
        
        plugin = self.get_plugin(command)
        if not plugin:
            # 命令不存在，返回帮助信息
            help_text = "未找到命令: " + command + "\n\n" + self.get_help()
            return help_text
        
        try:
            return await plugin.handle(params, user_id)
        except Exception as e:
            error_msg = f"处理命令 {command} 时出错: {str(e)}"
            self.logger.error(error_msg)
            return f"执行命令出错: {str(e)}"

# 创建全局插件管理器实例
plugin_manager = PluginManager() 