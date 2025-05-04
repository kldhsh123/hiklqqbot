import logging
import colorama
from colorama import Fore, Style

# 初始化colorama
colorama.init(autoreset=True)

class ColorFormatter(logging.Formatter):
    """为不同级别的日志添加不同颜色的格式化器"""
    
    # 定义不同日志级别对应的颜色
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT
    }
    
    # 定义不同模块名称对应的颜色 (可以按需调整)
    MODULE_COLORS = {
        'websocket_client': Fore.MAGENTA,
        'event_handler': Fore.BLUE,
        'plugin_manager': Fore.LIGHTCYAN_EX,
        'ai_chat': Fore.LIGHTGREEN_EX,
        'plugin.ai_chat': Fore.LIGHTGREEN_EX,
        'plugin.ai_mention': Fore.LIGHTGREEN_EX
    }
    
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
    
    def format(self, record):
        # 获取原始格式化的日志消息
        log_message = super().format(record)
        
        # 获取日志级别对应的颜色
        level_color = self.COLORS.get(record.levelname, '')
        
        # 获取模块名称对应的颜色
        module_name = record.name
        module_color = ''
        for name, color in self.MODULE_COLORS.items():
            if module_name.startswith(name):
                module_color = color
                break
        
        # 如果没有找到对应模块的颜色设置，使用级别的颜色
        if not module_color:
            module_color = level_color
        
        # 构建彩色日志消息
        # 格式: 时间 - 模块名称 - 日志级别 - 消息
        parts = log_message.split(' - ', 3)
        if len(parts) == 4:
            timestamp, name, levelname, message = parts
            return f"{timestamp} - {module_color}{name}{Style.RESET_ALL} - {level_color}{levelname}{Style.RESET_ALL} - {message}"
        
        # 如果格式不符合预期，返回原始消息但添加级别颜色
        return f"{level_color}{log_message}{Style.RESET_ALL}" 