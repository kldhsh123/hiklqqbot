import os
import asyncio
import logging
import logging.config
from config import BOT_APPID, BOT_APPSECRET, BOT_TOKEN, COMM_MODE
from websocket_client import ws_client
from webhook_server import webhook_server
from plugins.plugin_manager import plugin_manager
from auth_manager import auth_manager
from stats_manager import stats_manager
from event_handler import event_handler
from plugins.hiklqqbot_admin_plugin import HiklqqbotAdminPlugin
from plugins.hiklqqbot_maintenance_plugin import HiklqqbotMaintenancePlugin
from plugins.hiklqqbot_userid_plugin import HiklqqbotUseridPlugin
from plugins.hiklqqbot_reload_plugin import HiklqqbotReloadPlugin
from plugins.hiklqqbot_stats_plugin import HiklqqbotStatsPlugin

# 确保彩色日志格式化器模块可用
try:
    import color_formatter
    # 预加载colorama以确保控制台颜色正常工作
    import colorama
    colorama.init(autoreset=True)
    logging.info("彩色日志格式化器已加载")
except ImportError as e:
    print(f"无法加载彩色日志格式化器: {e}")
    print("将使用普通日志格式化器")

# 使用配置文件初始化日志
if os.path.exists('logging.ini'):
    logging.config.fileConfig('logging.ini')
    logging.info("已从logging.ini加载日志配置")
else:
    # 如果配置文件不存在，使用默认配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logging.warning("logging.ini文件不存在，使用默认日志配置")

logger = logging.getLogger("main")

def check_env():
    """检查环境变量是否已配置"""
    missing = []
    if not BOT_APPID:
        missing.append("BOT_APPID")
    if not BOT_APPSECRET:
        missing.append("BOT_APPSECRET")
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    
    if missing:
        logger.error("以下环境变量未设置:")
        for var in missing:
            logger.error(f"  - {var}")
        logger.error("请创建并配置 .env 文件 (参考 .env.example)")
        return False
    
    return True

async def start_websocket_client():
    """启动WebSocket客户端"""
    logger.info("使用WebSocket模式启动QQ机器人...")
    max_restart_attempts = 5
    restart_attempts = 0
    restart_delay = 10  # 初始重启延迟（秒）
    
    while restart_attempts < max_restart_attempts:
        try:
            # 连接到WebSocket
            logger.info("正在连接到QQ机器人WebSocket网关...")
            await ws_client.connect()
            
            # 如果连接成功并运行完毕（正常结束），退出循环
            break
            
        except Exception as e:
            restart_attempts += 1
            logger.error(f"WebSocket运行失败 (尝试 {restart_attempts}/{max_restart_attempts}): {e}")
            
            if restart_attempts < max_restart_attempts:
                # 指数退避策略
                restart_delay = min(restart_delay * 2, 300)  # 最大等待5分钟
                logger.info(f"将在 {restart_delay} 秒后重新启动WebSocket客户端...")
                await asyncio.sleep(restart_delay)
            else:
                logger.critical("WebSocket客户端达到最大重启次数，退出程序")
        finally:
            # 确保关闭所有资源
            await ws_client.close()
    
    logger.info("WebSocket客户端已停止")

async def start_webhook_server():
    """启动Webhook服务器"""
    logger.info("使用Webhook模式启动QQ机器人...")
    try:
        # 启动Webhook服务器
        await webhook_server.start()
        # 保持服务器运行
        while True:
            await asyncio.sleep(3600)  # 每小时检查一次
    except asyncio.CancelledError:
        logger.info("Webhook服务器收到停止信号")
    except Exception as e:
        logger.error(f"Webhook服务器异常: {e}")
    finally:
        # 确保关闭服务器
        await webhook_server.stop()

def init_stats_system():
    """初始化统计系统"""
    logger.info("正在初始化统计系统...")
    # 确保stats_manager已初始化
    _ = stats_manager.initialized
    logger.info("统计系统已初始化")

def register_builtin_plugins():
    """
    注册系统内置插件
    """
    plugin_manager.register_plugin(HiklqqbotAdminPlugin())
    plugin_manager.register_plugin(HiklqqbotMaintenancePlugin())
    plugin_manager.register_plugin(HiklqqbotUseridPlugin())
    plugin_manager.register_plugin(HiklqqbotReloadPlugin())
    plugin_manager.register_plugin(HiklqqbotStatsPlugin())  # 注册统计插件

async def main_async():
    """异步主程序"""
    logger.info("正在启动QQ机器人...")
    
    # 检查环境变量
    if not check_env():
        return
    
    # 初始化统计系统
    init_stats_system()
    
    # 加载所有插件
    logger.info("正在加载插件...")
    plugin_manager.load_plugins("plugins")
    
    # 注册内置插件
    register_builtin_plugins()
    
    logger.info(f"通信模式: {COMM_MODE}")
    logger.info(f"Bot AppID: {BOT_APPID}")
    
    if COMM_MODE.lower() == "webhook":
        await start_webhook_server()
    else:
        await start_websocket_client()

def main():
    """程序入口"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序异常: {e}", exc_info=True)

if __name__ == "__main__":
    main() 