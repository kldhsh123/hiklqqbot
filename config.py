import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 机器人配置
BOT_APPID = os.getenv("BOT_APPID")
BOT_APPSECRET = os.getenv("BOT_APPSECRET")
BOT_TOKEN = os.getenv("BOT_TOKEN")

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
API_AUTH_URL = f"{API_BASE_URL}/auth/token"
API_SEND_MESSAGE_URL = f"{API_BASE_URL}/v2/messages" 