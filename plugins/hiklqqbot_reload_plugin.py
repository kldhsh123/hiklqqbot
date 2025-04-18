import logging
import importlib
import sys
from plugins.base_plugin import BasePlugin
from plugins.plugin_manager import plugin_manager
from auth_manager import auth_manager

class HiklqqbotReloadPlugin(BasePlugin):
    """
    热重载插件，用于在运行时重新加载所有插件
    """
    
    def __init__(self):
        super().__init__(command="/hiklqqbot_reload", description="重新加载所有插件 (仅管理员可用)", is_builtin=True)
        self.logger = logging.getLogger("plugin.reload")
    
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """
        处理reload命令，重新加载plugins目录下的所有插件
        
        Args:
            params: 参数，可以为空或特定的插件名称
            user_id: 用户ID，用于权限控制
            group_openid: 群组ID（不使用）
            **kwargs: 其他额外参数
            
        Returns:
            str: 重载结果信息
        """
        self.logger.info(f"执行插件热重载，参数: {params}")
        
        # 检查用户是否是管理员
        if not auth_manager.is_admin(user_id):
            return "您没有权限执行此命令，请联系管理员"
        
        try:
            # 清空当前插件列表前先保存命令列表
            old_commands = list(plugin_manager.plugins.keys())
            old_plugin_count = len(old_commands)
            
            # 重载特定模块
            for name, module in list(sys.modules.items()):
                if name.startswith('plugins.') and name not in ['plugins.plugin_manager', 'plugins.base_plugin', 'plugins.hiklqqbot_reload_plugin']:
                    try:
                        self.logger.debug(f"重载模块: {name}")
                        importlib.reload(module)
                    except Exception as e:
                        self.logger.error(f"重载模块 {name} 失败: {str(e)}")
            
            # 清空插件列表
            old_plugins = plugin_manager.plugins.copy()
            plugin_manager.plugins.clear()
            
            # 保留当前reload插件
            reload_plugin = old_plugins.get('/hiklqqbot_reload')
            if reload_plugin:
                plugin_manager.register_plugin(reload_plugin)
            
            # 重新加载所有插件
            plugin_manager.load_plugins("plugins")
            
            # 计算新增和删除的插件
            new_commands = list(plugin_manager.plugins.keys())
            new_plugin_count = len(new_commands)
            
            added_plugins = [cmd for cmd in new_commands if cmd not in old_commands]
            removed_plugins = [cmd for cmd in old_commands if cmd not in new_commands]
            
            # 准备响应消息
            response = f"插件热重载完成!\n"
            response += f"- 原插件数量: {old_plugin_count}\n"
            response += f"- 当前插件数量: {new_plugin_count}\n"
            
            if added_plugins:
                response += f"- 新增插件: {', '.join(added_plugins)}\n"
            if removed_plugins:
                response += f"- 移除插件: {', '.join(removed_plugins)}\n"
                
            # 显示当前可用命令
            response += "\n当前可用命令:\n"
            for cmd in sorted(new_commands):
                plugin = plugin_manager.get_plugin(cmd)
                if plugin:
                    response += f"- {cmd}: {plugin.description}\n"
            
            return response
            
        except Exception as e:
            error_msg = f"插件热重载失败: {str(e)}"
            self.logger.error(error_msg)
            return error_msg
    
    def _normalize_commands(self):
        """
        标准化命令前缀并移除重复项
        确保所有命令都以/开头，且不存在重复的命令
        """
        # 收集所有插件及其命令
        plugins_by_name = {}
        for cmd, plugin in list(plugin_manager.plugins.items()):
            # 标准化命令名称（确保以/开头）
            normalized_cmd = cmd if cmd.startswith('/') else f'/{cmd}'
            
            # 如果已经存在相同名称但格式不同的命令，保留带/前缀的版本
            base_name = normalized_cmd.lstrip('/')
            if base_name in plugins_by_name:
                # 已存在此插件的另一个版本，记录日志
                self.logger.warning(f"发现重复的插件命令: {cmd} 和 {plugins_by_name[base_name]}")
                # 如果当前版本带前缀而已存在版本不带，则保留当前版本
                if normalized_cmd.startswith('/') and not plugins_by_name[base_name].startswith('/'):
                    # 移除不带前缀的版本
                    if plugins_by_name[base_name] in plugin_manager.plugins:
                        del plugin_manager.plugins[plugins_by_name[base_name]]
                    # 更新记录
                    plugins_by_name[base_name] = normalized_cmd
                    # 确保带前缀的版本存在
                    plugin_manager.plugins[normalized_cmd] = plugin
            else:
                # 记录此插件
                plugins_by_name[base_name] = normalized_cmd
                
                # 如果命令格式已更改，更新插件管理器
                if normalized_cmd != cmd:
                    # 移除旧格式
                    del plugin_manager.plugins[cmd]
                    # 添加标准化格式
                    plugin_manager.plugins[normalized_cmd] = plugin
                    # 更新插件内部的命令属性
                    plugin.command = normalized_cmd
        
        self.logger.info(f"命令标准化完成，共有 {len(plugins_by_name)} 个唯一插件")