import json
import asyncio
import websockets
import time
import logging
from config import BOT_APPID, BOT_TOKEN
from event_handler import event_handler

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("websocket_client")

class WebSocketClient:
    def __init__(self):
        self.gateway_url = "wss://api.sgroup.qq.com/websocket/"
        self.token = f"Bot {BOT_APPID}.{BOT_TOKEN}"
        self.heartbeat_interval = 45000  # 默认心跳间隔，将被服务器返回的值覆盖
        self.session_id = None
        self.last_sequence = None
        self.connected = False
        self.ws = None
        self.heartbeat_task = None
    
    async def connect(self):
        """连接到WebSocket网关"""
        try:
            self.ws = await websockets.connect(self.gateway_url)
            self.connected = True
            logger.info("WebSocket连接已建立")
            
            # 接收Hello消息
            hello_message = await self.ws.recv()
            hello_data = json.loads(hello_message)
            
            if hello_data["op"] == 10:  # Hello
                self.heartbeat_interval = hello_data["d"]["heartbeat_interval"]
                logger.info(f"收到Hello消息，心跳间隔: {self.heartbeat_interval}ms")
                
                # 启动心跳任务
                self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
                
                # 发送鉴权消息
                await self.identify()
                
                # 开始监听消息
                await self.listen_messages()
            else:
                logger.error(f"预期接收Hello消息，但接收到: {hello_data}")
        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            self.connected = False
            raise
    
    async def identify(self):
        """发送鉴权消息"""
        identify_payload = {
            "op": 2,
            "d": {
                "token": self.token,
                "intents": 1 << 25 | 1 << 0 | 1 << 1 | 1 << 30,  # 添加所需的意图，包括群聊@消息
                "shard": [0, 1],  # 单分片
                "properties": {
                    "$os": "windows",
                    "$browser": "qqbot_python",
                    "$device": "qqbot_python"
                }
            }
        }
        
        await self.ws.send(json.dumps(identify_payload))
        logger.info("已发送鉴权消息")
    
    async def heartbeat_loop(self):
        """心跳循环"""
        try:
            while self.connected:
                await self.send_heartbeat()
                await asyncio.sleep(self.heartbeat_interval / 1000)  # 转换为秒
        except Exception as e:
            logger.error(f"心跳循环异常: {e}")
    
    async def send_heartbeat(self):
        """发送心跳"""
        heartbeat_payload = {
            "op": 1,
            "d": self.last_sequence
        }
        
        await self.ws.send(json.dumps(heartbeat_payload))
        logger.debug("已发送心跳")
    
    async def listen_messages(self):
        """监听并处理消息"""
        try:
            while self.connected:
                message = await self.ws.recv()
                await self.process_message(message)
        except websockets.ConnectionClosed:
            logger.warning("WebSocket连接已关闭")
            self.connected = False
            # 尝试重新连接
            await self.reconnect()
        except Exception as e:
            logger.error(f"监听消息异常: {e}")
            self.connected = False
    
    async def process_message(self, message):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            op_code = data.get("op", None)
            
            # 更新最后的序列号，用于心跳和重连
            if "s" in data and data["s"] is not None:
                self.last_sequence = data["s"]
            
            if op_code == 0:  # Dispatch
                await self.handle_dispatch(data)
            elif op_code == 11:  # Heartbeat ACK
                logger.debug("收到心跳确认")
            else:
                logger.info(f"收到未处理的操作码: {op_code}")
        except Exception as e:
            logger.error(f"处理消息异常: {e}")
    
    async def handle_dispatch(self, data):
        """处理分发事件"""
        event_type = data.get("t")
        event_data = data.get("d", {})
        
        logger.info(f"收到事件: {event_type}")
        
        if event_type == "READY":
            self.session_id = event_data.get("session_id")
            logger.info(f"收到READY事件，会话ID: {self.session_id}")
        elif event_type == "RESUMED":
            logger.info("连接已恢复")
        else:
            # 处理其他事件
            try:
                result = await event_handler.handle_event(event_type, event_data)
                logger.info(f"事件 {event_type} 处理结果: {result}")
            except Exception as e:
                logger.error(f"处理事件 {event_type} 异常: {e}")
    
    async def reconnect(self):
        """重新连接WebSocket"""
        logger.info("尝试重新连接...")
        try:
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
            
            self.ws = await websockets.connect(self.gateway_url)
            self.connected = True
            
            # 接收Hello消息
            hello_message = await self.ws.recv()
            hello_data = json.loads(hello_message)
            
            if hello_data["op"] == 10:  # Hello
                self.heartbeat_interval = hello_data["d"]["heartbeat_interval"]
                logger.info(f"重连后收到Hello消息，心跳间隔: {self.heartbeat_interval}ms")
                
                # 启动心跳任务
                self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
                
                # 发送恢复连接消息
                if self.session_id and self.last_sequence:
                    await self.resume()
                else:
                    await self.identify()
                
                # 开始监听消息
                await self.listen_messages()
            else:
                logger.error(f"重连时预期接收Hello消息，但接收到: {hello_data}")
        except Exception as e:
            logger.error(f"重新连接失败: {e}")
            self.connected = False
            # 添加延迟后重试
            await asyncio.sleep(5)
            asyncio.create_task(self.reconnect())
    
    async def resume(self):
        """恢复连接"""
        resume_payload = {
            "op": 6,
            "d": {
                "token": self.token,
                "session_id": self.session_id,
                "seq": self.last_sequence
            }
        }
        
        await self.ws.send(json.dumps(resume_payload))
        logger.info(f"已发送恢复连接消息，会话ID: {self.session_id}, 序列号: {self.last_sequence}")
    
    async def close(self):
        """关闭WebSocket连接"""
        if self.connected:
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
            await self.ws.close()
            self.connected = False
            logger.info("WebSocket连接已关闭")

# 创建WebSocket客户端实例
ws_client = WebSocketClient() 