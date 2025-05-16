import json
import asyncio
import websockets
import time
import logging
import random
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
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.max_retry_interval = 60  # 最大重试间隔（秒）
    
    async def connect(self):
        """连接到WebSocket网关"""
        try:
            # 设置连接超时
            self.ws = await asyncio.wait_for(
                websockets.connect(
                    self.gateway_url,
                    ping_interval=30,  # 更频繁的ping以保持连接
                    ping_timeout=10,
                    close_timeout=10
                ),
                timeout=20
            )
            self.connected = True
            self.reconnect_attempts = 0  # 重置重连计数器
            logger.info("WebSocket连接已建立")
            
            # 接收Hello消息，添加超时
            try:
                hello_message = await asyncio.wait_for(self.ws.recv(), timeout=15)
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
                    await self.reconnect()
            except asyncio.TimeoutError:
                logger.error("等待Hello消息超时")
                self.connected = False
                await self.reconnect()
        except asyncio.TimeoutError:
            logger.error("WebSocket连接超时")
            self.connected = False
            await self.reconnect()
        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            self.connected = False
            await self.reconnect()
    
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
        
        try:
            await asyncio.wait_for(
                self.ws.send(json.dumps(identify_payload)),
                timeout=10
            )
            logger.info("已发送鉴权消息")
        except asyncio.TimeoutError:
            logger.error("发送鉴权消息超时")
            self.connected = False
            await self.reconnect()
        except Exception as e:
            logger.error(f"发送鉴权消息失败: {e}")
            self.connected = False
            await self.reconnect()
    
    async def heartbeat_loop(self):
        """心跳循环"""
        try:
            while self.connected:
                await self.send_heartbeat()
                # 使用心跳间隔的90%作为实际等待时间，避免接近临界值
                sleep_time = self.heartbeat_interval * 0.9 / 1000  # 转换为秒
                await asyncio.sleep(sleep_time)
        except asyncio.CancelledError:
            logger.info("心跳任务被取消")
        except Exception as e:
            logger.error(f"心跳循环异常: {e}")
            if self.connected:
                self.connected = False
                asyncio.create_task(self.reconnect())
    
    async def send_heartbeat(self):
        """发送心跳"""
        heartbeat_payload = {
            "op": 1,
            "d": self.last_sequence
        }
        
        try:
            await asyncio.wait_for(
                self.ws.send(json.dumps(heartbeat_payload)),
                timeout=10
            )
            logger.debug("已发送心跳")
        except asyncio.TimeoutError:
            logger.error("发送心跳超时")
            self.connected = False
            raise
        except Exception as e:
            logger.error(f"发送心跳失败: {e}")
            self.connected = False
            raise
    
    async def listen_messages(self):
        """监听并处理消息"""
        try:
            while self.connected:
                try:
                    # 添加消息接收超时
                    message = await asyncio.wait_for(self.ws.recv(), timeout=60)
                    # 处理消息时添加超时保护
                    await asyncio.wait_for(self.process_message(message), timeout=30)
                except asyncio.TimeoutError as e:
                    if "recv" in str(e):
                        logger.warning("超过60秒未收到消息，发送额外心跳保活")
                        try:
                            await self.send_heartbeat()
                        except:
                            logger.error("发送保活心跳失败")
                            break
                    else:
                        logger.error(f"处理消息超时: {e}")
                        # 继续监听，不断开连接
        except websockets.ConnectionClosed as e:
            logger.warning(f"WebSocket连接已关闭: {e}")
            self.connected = False
            # 尝试重新连接
            await self.reconnect()
        except Exception as e:
            logger.error(f"监听消息异常: {e}")
            self.connected = False
            await self.reconnect()
    
    async def process_message(self, message):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            op_code = data.get("op", None)
            
            # 更新最后的序列号，用于心跳和重连
            if "s" in data and data["s"] is not None:
                self.last_sequence = data["s"]
            
            if op_code == 0:  # Dispatch
                # 为每个事件设置独立的超时保护
                await asyncio.wait_for(self.handle_dispatch(data), timeout=20)
            elif op_code == 11:  # Heartbeat ACK
                logger.debug("收到心跳确认")
            else:
                logger.info(f"收到未处理的操作码: {op_code}")
        except asyncio.TimeoutError:
            logger.error("处理消息超时")
        except Exception as e:
            logger.error(f"处理消息异常: {e}")
    
    async def handle_dispatch(self, data):
        """处理分发事件"""
        try:
            event_type = data.get("t", None)
            event_data = data.get("d", {})
            
            if event_type:
                logger.info(f"收到事件: {event_type}")
                
                # 处理会话ID (用于断线重连)
                if event_type == "READY":
                    self.session_id = event_data.get("session_id")
                    logger.info(f"已准备就绪，会话ID: {self.session_id}")
                
                # 使用事件处理器处理所有类型的事件
                try:
                    # 支持QQ官方的所有事件类型：
                    # 群组事件: GROUP_ADD_ROBOT, GROUP_DEL_ROBOT, GROUP_MSG_REJECT, GROUP_MSG_RECEIVE
                    # 用户事件: FRIEND_ADD, FRIEND_DEL, C2C_MSG_REJECT, C2C_MSG_RECEIVE
                    # 消息事件: AT_MESSAGE_CREATE, GROUP_AT_MESSAGE_CREATE, DIRECT_MESSAGE_CREATE
                    await event_handler.handle_event(event_type, event_data)
                except Exception as e:
                    logger.error(f"事件处理失败 ({event_type}): {e}")
            else:
                logger.warning(f"收到没有事件类型的消息: {data}")
        except Exception as e:
            logger.error(f"分发事件异常: {e}")
    
    async def reconnect(self):
        """重新连接WebSocket"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"已达到最大重连次数 ({self.max_reconnect_attempts})，停止重连")
            return
        
        self.reconnect_attempts += 1
        
        # 计算重试间隔（指数退避策略）
        retry_interval = min(2 ** self.reconnect_attempts + random.uniform(0, 1), self.max_retry_interval)
        
        logger.info(f"准备重新连接，第 {self.reconnect_attempts} 次尝试，等待 {retry_interval:.2f} 秒...")
        
        try:
            if self.heartbeat_task and not self.heartbeat_task.done():
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            if self.ws and self.ws.open:
                await self.ws.close()
            
            # 等待一段时间再重连
            await asyncio.sleep(retry_interval)
            
            # 如果有会话ID和序列号，尝试恢复连接，否则重新建立连接
            await self.connect()
            
        except Exception as e:
            logger.error(f"重新连接失败: {e}")
            self.connected = False
            # 递归调用自身进行下一次重连
            await self.reconnect()
    
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
        
        try:
            await asyncio.wait_for(
                self.ws.send(json.dumps(resume_payload)),
                timeout=10
            )
            logger.info(f"已发送恢复连接消息，会话ID: {self.session_id}, 序列号: {self.last_sequence}")
        except asyncio.TimeoutError:
            logger.error("发送恢复连接消息超时")
            self.connected = False
            await self.reconnect()
        except Exception as e:
            logger.error(f"发送恢复连接消息失败: {e}")
            self.connected = False
            await self.reconnect()
    
    async def close(self):
        """关闭WebSocket连接"""
        if self.connected:
            if self.heartbeat_task and not self.heartbeat_task.done():
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            if self.ws and self.ws.open:
                await self.ws.close()
            
            self.connected = False
            logger.info("WebSocket连接已关闭")

# 创建WebSocket客户端实例
ws_client = WebSocketClient() 