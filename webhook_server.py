import json
import logging
import time
import hashlib
import hmac
import base64
import asyncio
from aiohttp import web
import binascii
from config import BOT_APPSECRET, WEBHOOK_HOST, WEBHOOK_PORT, WEBHOOK_PATH
from event_handler import event_handler

# 配置日志
logger = logging.getLogger("webhook_server")

# 尝试导入 ed25519 库，如果失败则尝试使用 nacl 库
try:
    import ed25519
    logger.info("使用 ed25519 库进行签名验证")
    
    def generate_signature(secret, message):
        """使用 ed25519 库生成签名"""
        while len(secret) < ed25519.SEED_SIZE:
            secret = secret + secret
        secret = secret[:ed25519.SEED_SIZE]
        signing_key = ed25519.SigningKey(secret.encode('utf-8'))
        signature = signing_key.sign(message.encode('utf-8'))
        return binascii.hexlify(signature).decode('utf-8')
        
except ImportError:
    try:
        import nacl.signing
        logger.info("使用 nacl 库进行签名验证")
        
        def generate_signature(secret, message):
            """使用 nacl 库生成签名"""
            # 准备密钥，确保长度正确
            while len(secret) < 32:
                secret = secret + secret
            secret = secret[:32]
            
            # 从种子创建签名密钥
            seed = secret.encode('utf-8')
            signing_key = nacl.signing.SigningKey(seed)
            
            # 签名消息
            signature = signing_key.sign(message.encode('utf-8')).signature
            return binascii.hexlify(signature).decode('utf-8')
    except ImportError:
        logger.error("无法导入 ed25519 或 nacl 库，请安装其中一个: pip install ed25519 或 pip install pynacl")
        raise ImportError("需要 ed25519 或 nacl 库来处理签名验证")

class WebhookServer:
    def __init__(self):
        self.app = web.Application()
        self.app.router.add_post(WEBHOOK_PATH, self.handle_webhook)
        self.runner = None
        
    async def start(self):
        """启动webhook服务器"""
        logger.info(f"正在启动Webhook服务器在 {WEBHOOK_HOST}:{WEBHOOK_PORT}{WEBHOOK_PATH}...")
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, WEBHOOK_HOST, WEBHOOK_PORT)
        await site.start()
        logger.info("Webhook服务器已启动")
    
    async def stop(self):
        """停止webhook服务器"""
        if self.runner:
            logger.info("正在关闭Webhook服务器...")
            await self.runner.cleanup()
            logger.info("Webhook服务器已关闭")
    
    async def handle_webhook(self, request):
        """处理来自QQ机器人平台的webhook请求"""
        try:
            body_data = await request.read()
            headers = request.headers
            
            # 检查是否是验证请求
            payload = json.loads(body_data)
            if "op" in payload and payload["op"] == 13:
                logger.info("收到Webhook验证请求")
                return await self._handle_validation(payload)
            
            # 处理事件请求
            if "op" in payload and payload["op"] == 0 and "t" in payload and "d" in payload:
                event_type = payload["t"]
                event_data = payload["d"]
                logger.info(f"收到事件: {event_type}")
                
                # 处理事件
                try:
                    result = await event_handler.handle_event(event_type, event_data)
                    logger.info(f"事件 {event_type} 处理结果: {result}")
                except Exception as e:
                    logger.error(f"处理事件 {event_type} 异常: {str(e)}")
            
            return web.Response(text="success")
        except Exception as e:
            logger.error(f"处理Webhook请求异常: {e}")
            return web.Response(text="error", status=500)
    
    async def _handle_validation(self, payload):
        """处理webhook验证请求"""
        try:
            validation_data = payload["d"]
            plain_token = validation_data["plain_token"]
            event_ts = validation_data["event_ts"]
            
            logger.info(f"验证请求: token={plain_token}, ts={event_ts}")
            
            # 生成签名 - 关键修复：使用 BOT_APPSECRET 而不是 BOT_TOKEN
            message = event_ts + plain_token
            signature_hex = generate_signature(BOT_APPSECRET, message)
            
            # 返回验证响应
            response_data = {
                "plain_token": plain_token,
                "signature": signature_hex
            }
            
            logger.info("验证请求处理完成")
            return web.json_response(response_data)
        except Exception as e:
            logger.error(f"处理验证请求异常: {e}")
            return web.Response(text="error", status=500)

webhook_server = WebhookServer()
