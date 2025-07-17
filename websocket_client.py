import json
import asyncio
import websockets
import time
import logging
import random
from config import BOT_APPID, BOT_TOKEN
from event_handler import event_handler
from auth import auth_manager  # 保留auth_manager用于获取动态token

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("websocket_client")

class WebSocketClient:
    def __init__(self):
        self.gateway_url = "wss://api.sgroup.qq.com/websocket/"
        # 不再使用静态token，改为在需要时从auth_manager获取
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
            # 如果已存在心跳任务，先取消
            if self.heartbeat_task and not self.heartbeat_task.done():
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
                self.heartbeat_task = None
            
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
                    
                    # 判断是否有会话ID和序列号，如果有则尝试恢复会话，否则重新鉴权
                    if self.session_id and self.last_sequence:
                        try:
                            await self.resume()
                        except Exception as e:
                            logger.error(f"恢复会话失败: {e}，尝试重新鉴权")
                            await self.identify()
                    else:
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
        try:
            # 获取最新的access_token
            access_token = auth_manager.get_access_token()
            # 使用新的QQBot格式的token
            token = f"QQBot {access_token}"
            logger.info("已获取动态token用于WS鉴权")
            
            identify_payload = {
                "op": 2,
                "d": {
                    "token": token,
                    "intents": 1 << 25 | 1 << 0 | 1 << 1 | 1 << 30,  # 添加所需的意图，包括群聊@消息
                    "shard": [0, 1],  # 单分片
                    "properties": {
                        "$os": "windows",
                        "$browser": "qqbot_python",
                        "$device": "qqbot_python"
                    }
                }
            }
            
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
            elif op_code == 7:  # Reconnect required
                logger.info("收到服务器重连请求，准备重新连接")
                self.connected = False
                await self.reconnect()
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
    
    async def resume(self):
        """恢复连接"""
        try:
            # 获取最新的access_token
            access_token = auth_manager.get_access_token()
            # 使用新的QQBot格式的token
            token = f"QQBot {access_token}"
            logger.info("已获取动态token用于WS恢复连接")
            
            # 确保session_id和last_sequence有效
            if not self.session_id or self.last_sequence is None:
                logger.error("恢复连接失败：没有有效的会话ID或序列号")
                # 回退到重新鉴权
                await self.identify()
                return
            
            resume_payload = {
                "op": 6,
                "d": {
                    "token": token,
                    "session_id": self.session_id,
                    "seq": self.last_sequence
                }
            }
            
            logger.info(f"正在尝试恢复连接，会话ID: {self.session_id}, 序列号: {self.last_sequence}")
            await asyncio.wait_for(
                self.ws.send(json.dumps(resume_payload)),
                timeout=10
            )
            logger.info(f"已发送恢复连接消息")
            
            # 等待服务器确认恢复
            try:
                # 最多等待10秒看是否收到RESUMED事件
                response_start_time = time.time()
                while time.time() - response_start_time < 10:
                    message = await asyncio.wait_for(self.ws.recv(), timeout=5)
                    data = json.loads(message)
                    
                    # 如果收到RESUMED事件，表示恢复成功
                    if data.get("op") == 0 and data.get("t") == "RESUMED":
                        logger.info("会话恢复成功")
                        return
                    
                    # 如果收到错误事件（比如4006无效会话），需要重新鉴权
                    if data.get("op") == 9:
                        logger.warn(f"会话恢复被拒绝: {data}")
                        await self.identify()
                        return
                    
                    # 处理其他消息
                    await self.process_message(message)
                
                # 超时未收到RESUMED，但也没收到错误，假设连接保持
                logger.info("未收到会话恢复确认，但连接保持中")
                
            except asyncio.TimeoutError:
                logger.warn("等待会话恢复确认超时，尝试重新鉴权")
                await self.identify()
            except Exception as e:
                logger.error(f"恢复会话过程中发生错误: {e}")
                await self.identify()
            
        except asyncio.TimeoutError:
            logger.error("发送恢复连接消息超时")
            self.connected = False
            await self.reconnect()
        except Exception as e:
            logger.error(f"发送恢复连接消息失败: {e}")
            self.connected = False
            await self.reconnect()
    
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
            # 取消心跳任务
            if self.heartbeat_task and not self.heartbeat_task.done():
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # 安全关闭WebSocket连接
            if self.ws:
                try:
                    # 使用try-except安全地关闭连接，不依赖于.open属性检查
                    await asyncio.wait_for(self.ws.close(), timeout=5)
                except Exception as e:
                    logger.debug(f"关闭WebSocket时发生异常: {e}")
            
            # 确保ws对象被清除
            self.ws = None
            self.connected = False
            
            # 等待一段时间再重连
            await asyncio.sleep(retry_interval)
            
            # 重新建立连接
            await self.connect()
            
            # 注意：connect()成功后会自动调用identify()重新鉴权
            
        except Exception as e:
            logger.error(f"重新连接失败: {e}")
            self.connected = False
            
            # 增加额外延迟以避免快速失败的循环
            await asyncio.sleep(1)
            
            # 递归调用自身进行下一次重连
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