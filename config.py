import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 机器人配置
BOT_APPID = os.getenv("BOT_APPID")          # 机器人应用ID
BOT_APPSECRET = os.getenv("BOT_APPSECRET")  # 机器人应用密钥，用于获取动态APP_ACCESS_TOKEN
BOT_TOKEN = os.getenv("BOT_TOKEN")          # 机器人Token，仅用于Webhook模式的签名验证，API调用已统一使用动态APP_ACCESS_TOKEN

# 通信方式配置 (可选: "webhook" 或 "websocket")
COMM_MODE = os.getenv("COMM_MODE", "websocket")

# Webhook相关配置 (仅COMM_MODE="webhook"时使用)
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", 8080))
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook/callback")
WEBHOOK_FULL_URL = os.getenv("WEBHOOK_FULL_URL", "") # 如果有公网URL，在此填写

# 服务器配置
SERVER_HOST = os.getenv("BOT_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("BOT_SERVER_PORT", 8080))

# API 端点
API_BASE_URL = "https://api.sgroup.qq.com"
API_AUTH_URL = "https://bots.qq.com/app/getAppAccessToken"  # 正确的OAuth认证端点
API_SEND_MESSAGE_URL = f"{API_BASE_URL}/v2/messages"

# Botpy集成配置
USE_BOTPY_CLIENT = os.getenv("USE_BOTPY_CLIENT", "false").lower() == "true"
BOTPY_INTENTS = os.getenv("BOTPY_INTENTS", "public_messages,public_guild_messages,direct_message")
BOTPY_LOG_LEVEL = os.getenv("BOTPY_LOG_LEVEL", "INFO")
BOTPY_TIMEOUT = int(os.getenv("BOTPY_TIMEOUT", "5"))
BOTPY_IS_SANDBOX = os.getenv("BOTPY_IS_SANDBOX", "false").lower() == "true"

# 统计系统配置
STATS_MAX_MONTHS = int(os.getenv("STATS_MAX_MONTHS", "12"))

# 黑名单功能配置
ENABLE_BLACKLIST = os.getenv("ENABLE_BLACKLIST", "true").lower() == "true"
BLACKLIST_AUTO_SAVE = os.getenv("BLACKLIST_AUTO_SAVE", "true").lower() == "true"
BLACKLIST_LOG_BLOCKED = os.getenv("BLACKLIST_LOG_BLOCKED", "true").lower() == "true"
BLACKLIST_SHOW_REASON = os.getenv("BLACKLIST_SHOW_REASON", "true").lower() == "true"
