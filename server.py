from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import json
import hmac
import hashlib
import base64
import logging
from config import BOT_TOKEN, SERVER_HOST, SERVER_PORT
from event_handler import event_handler
import nacl.signing  # 替换ed25519

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("server")

app = FastAPI()

async def verify_signature(request: Request):
    """验证请求签名"""
    if not BOT_TOKEN:
        raise HTTPException(status_code=401, detail="BOT_TOKEN is not set")
    
    # 获取QQ发送的签名和时间戳
    qq_signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    
    if not qq_signature or not timestamp:
        raise HTTPException(status_code=401, detail="Missing signature or timestamp")
    
    # 读取请求体
    body = await request.body()
    raw_body = body.decode()
    
    # 构造签名内容
    message = timestamp + raw_body
    
    # 计算签名
    h = hmac.new(BOT_TOKEN.encode(), message.encode(), hashlib.sha256)
    signature = base64.b64encode(h.digest()).decode()
    
    # 验证签名
    if not hmac.compare_digest(qq_signature, signature):
        logger.warning(f"签名验证失败! 收到: {qq_signature}, 计算: {signature}")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    return raw_body

@app.post("/")
async def bot_event_handler(raw_body: str = Depends(verify_signature)):
    """处理QQ机器人事件"""
    try:
        # 解析事件数据
        event_data = json.loads(raw_body)
        logger.info(f"收到事件: {event_data}")
        
        # 处理鉴权挑战
        if "challenge" in event_data:
            logger.info("收到鉴权挑战请求")
            return JSONResponse(content={"challenge": event_data["challenge"]})
        
        # 处理OP 13验证请求
        if event_data.get("op") == 13:
            logger.info("收到OP 13验证请求")
            d = event_data.get("d", {})
            plain_token = d.get("plain_token", "")
            event_ts = d.get("event_ts", "")
            
            # 构造消息
            msg = event_ts + plain_token
            
            # 使用BOT_TOKEN扩展到ED25519密钥长度
            seed = BOT_TOKEN
            while len(seed) < 32:
                seed = seed + seed
            seed = seed[:32]
            
            # 使用PyNaCl库计算签名
            signing_key = nacl.signing.SigningKey(seed.encode())
            signed = signing_key.sign(msg.encode())
            signature = signed.signature.hex()
            
            # 返回签名结果
            return JSONResponse(content={
                "plain_token": plain_token,
                "signature": signature
            })
        
        # 获取事件类型和数据
        event_type = event_data.get("t")
        event_info = event_data.get("d", {})
        
        if not event_type:
            logger.warning(f"未找到事件类型: {event_data}")
            return JSONResponse(content={"success": False, "error": "No event type"})
        
        # 处理事件
        logger.info(f"处理事件: {event_type}")
        try:
            result = await event_handler.handle_event(event_type, event_info)
            logger.info(f"事件 {event_type} 处理结果: {result}")
        except Exception as e:
            logger.error(f"处理事件 {event_type} 异常: {str(e)}")
        
        return JSONResponse(content={"success": True})
    except Exception as e:
        logger.error(f"事件处理异常: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok"}

def start_server():
    """启动服务器"""
    logger.info(f"启动Webhook服务器 - 监听: {SERVER_HOST}:{SERVER_PORT}")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT) 