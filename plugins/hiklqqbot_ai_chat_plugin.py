import json
import logging
import os
import time
import aiohttp
import asyncio
import re
from typing import Dict, List, Optional, Any, Union

from plugins.base_plugin import BasePlugin
from auth_manager import auth_manager
from message import MessageSender

# 设置默认导出列表为空
__all__ = []

# 从环境变量读取配置
ENABLE_AI_CHAT = os.environ.get("ENABLE_AI_CHAT", "true").lower() == "true"

# 初始化日志记录器
logger = logging.getLogger("ai_chat")

# 只在AI聊天功能启用时加载其余配置和定义插件类
if ENABLE_AI_CHAT:
    logger.info("AI聊天功能已启用，初始化AI聊天插件")
    
    # 从环境变量读取配置
    AI_CHAT_API_URL = os.environ.get("AI_CHAT_API_URL", "http://localhost:8000/v1/chat/completions")
    AI_CHAT_API_KEY = os.environ.get("AI_CHAT_API_KEY", "")
    AI_CHAT_MODEL = os.environ.get("AI_CHAT_MODEL", "gpt-3.5-turbo")
    AI_CHAT_MAX_TOKENS = int(os.environ.get("AI_CHAT_MAX_TOKENS", "2000"))
    AI_CHAT_TEMPERATURE = float(os.environ.get("AI_CHAT_TEMPERATURE", "0.7"))
    AI_CHAT_MAX_HISTORY = int(os.environ.get("AI_CHAT_MAX_HISTORY", "10"))
    AI_CHAT_SYSTEM_PROMPT = os.environ.get("AI_CHAT_SYSTEM_PROMPT", "你是一个有用的助手")
    AI_CHAT_MENTION_TRIGGER = os.environ.get("AI_CHAT_MENTION_TRIGGER", "true").lower() == "true"
    ENFORCE_COMMAND_PREFIX = os.environ.get("ENFORCE_COMMAND_PREFIX", "true").lower() == "true"
    AI_CHAT_RATE_LIMIT_WINDOW = int(os.environ.get("AI_CHAT_RATE_LIMIT_WINDOW", "60"))
    AI_CHAT_RATE_LIMIT_COUNT = int(os.environ.get("AI_CHAT_RATE_LIMIT_COUNT", "10"))
    
    # 设置导出的类名列表
    __all__ = ["AIChatPlugin", "AIChatMentionPlugin", "AIChatHelpPlugin"]
    
    # API状态
    API_STATUS = {
        "available": False,
        "last_check": 0,
        "error": None
    }

    class AIChatPlugin(BasePlugin):
        """
        AI聊天插件，实现ChatGPT风格的聊天功能
        """
        
        def __init__(self, logger=None):
            """初始化AI聊天插件"""
            # 调用父类初始化方法设置命令属性
            super().__init__(
                command="chat", 
                description="与AI助手聊天，支持连续对话", 
                is_builtin=True,
                hidden=not ENABLE_AI_CHAT  # 当AI聊天功能未启用时，隐藏命令
            )
            
            # 设置日志记录器
            self.logger = logger or logging.getLogger("plugin.ai_chat")
            
            # 检查并修复API URL配置
            self._fix_api_url()
            
            # 打印当前配置信息
            self.logger.info(f"AI聊天配置: 启用状态={ENABLE_AI_CHAT}, API地址={AI_CHAT_API_URL}")
            self.logger.info(f"AI聊天配置: 模型={AI_CHAT_MODEL}, 系统提示={AI_CHAT_SYSTEM_PROMPT}")
            self.logger.info(f"AI聊天插件在命令列表中{'可见' if ENABLE_AI_CHAT else '隐藏'}")
            
            # 用户聊天历史记录存储 {user_id: [{"role": "user/assistant", "content": "消息内容"}]}
            self.chat_history = {}
            
            # 创建聊天历史存储目录
            self.data_dir = "data/chat_history"
            os.makedirs(self.data_dir, exist_ok=True)
            
            # 加载现有聊天历史
            self._load_chat_histories()
            
            # 检查API可用性
            asyncio.create_task(self._check_api_availability())
            
            # 用户会话存储
            self.user_sessions = {}
            # 用户最后活动时间
            self.user_last_activity = {}
            # 频率限制记录
            self.rate_limit_records = {}
            # 是否启用AI聊天功能
            self.ai_chat_enabled = ENABLE_AI_CHAT
            # 是否启用@触发
            self.at_trigger_enabled = AI_CHAT_MENTION_TRIGGER
            
            self.logger.info(f"AI聊天处理器初始化完成，功能启用状态: {self.ai_chat_enabled}, @触发启用状态: {self.at_trigger_enabled}")
        
        def _fix_api_url(self):
            """检查并修复API URL配置"""
            global AI_CHAT_API_URL
            
            # 检查URL是否以http://或https://开头
            if not AI_CHAT_API_URL.startswith(("http://", "https://")):
                self.logger.warning(f"API URL格式不正确: {AI_CHAT_API_URL}")
                
                # 尝试修复URL
                if "localhost" in AI_CHAT_API_URL or "127.0.0.1" in AI_CHAT_API_URL:
                    AI_CHAT_API_URL = f"http://{AI_CHAT_API_URL}"
                else:
                    AI_CHAT_API_URL = f"https://{AI_CHAT_API_URL}"
                    
                self.logger.info(f"已修复API URL: {AI_CHAT_API_URL}")
            
            # 检查URL是否已包含v1/chat/completions路径
            if not AI_CHAT_API_URL.endswith(("/v1/chat/completions", "/chat/completions")):
                # 如果不是已知的完整路径，检查是否需要添加路径
                if AI_CHAT_API_URL.endswith("/"):
                    AI_CHAT_API_URL += "v1/chat/completions"
                else:
                    AI_CHAT_API_URL += "/v1/chat/completions"
                    
                self.logger.info(f"已添加API路径: {AI_CHAT_API_URL}")
            
            # 记录最终URL
            self.logger.info(f"最终API URL: {AI_CHAT_API_URL}")
        
        def _load_chat_histories(self):
            """加载所有用户的聊天历史"""
            try:
                if os.path.exists(self.data_dir):
                    for filename in os.listdir(self.data_dir):
                        if filename.endswith(".json"):
                            user_id = filename[:-5]  # 移除.json后缀
                            self._load_chat_history(user_id)
            except Exception as e:
                self.logger.error(f"加载聊天历史失败: {e}")
        
        def _load_chat_history(self, user_id: str):
            """加载特定用户的聊天历史"""
            try:
                file_path = os.path.join(self.data_dir, f"{user_id}.json")
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        self.chat_history[user_id] = json.load(f)
                    self.logger.info(f"已加载用户 {user_id} 的聊天历史")
            except Exception as e:
                self.logger.error(f"加载用户 {user_id} 的聊天历史失败: {e}")
                self.chat_history[user_id] = []
        
        def _save_chat_history(self, user_id: str):
            """保存用户聊天历史到文件"""
            try:
                file_path = os.path.join(self.data_dir, f"{user_id}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(self.chat_history.get(user_id, []), f, ensure_ascii=False, indent=2)
            except Exception as e:
                self.logger.error(f"保存用户 {user_id} 的聊天历史失败: {e}")
        
        def _add_message_to_history(self, user_id: str, role: str, content: str):
            """添加消息到用户聊天历史"""
            if user_id not in self.chat_history:
                self.chat_history[user_id] = []
            
            # 添加新消息
            self.chat_history[user_id].append({"role": role, "content": content})
            
            # 截取最近的消息
            if len(self.chat_history[user_id]) > AI_CHAT_MAX_HISTORY * 2:  # 乘以2是因为每次对话包含用户和AI各一条消息
                self.chat_history[user_id] = self.chat_history[user_id][-AI_CHAT_MAX_HISTORY * 2:]
            
            # 保存聊天历史
            self._save_chat_history(user_id)
        
        def _clear_chat_history(self, user_id: str):
            """清除用户聊天历史"""
            if user_id in self.chat_history:
                self.chat_history[user_id] = []
                self._save_chat_history(user_id)
        
        def _clear_all_chat_histories(self):
            """清除所有用户聊天历史"""
            self.chat_history = {}
            for filename in os.listdir(self.data_dir):
                if filename.endswith(".json"):
                    try:
                        os.remove(os.path.join(self.data_dir, filename))
                    except Exception as e:
                        self.logger.error(f"删除聊天历史文件 {filename} 失败: {e}")
        
        async def _check_api_availability(self):
            """检查API是否可用"""
            global API_STATUS
            
            # 如果在60秒内已经检查过，跳过
            if time.time() - API_STATUS["last_check"] < 60:
                return API_STATUS["available"]
            
            API_STATUS["last_check"] = time.time()
            
            # 构建简单测试请求
            headers = {"Content-Type": "application/json"}
            if AI_CHAT_API_KEY:
                headers["Authorization"] = f"Bearer {AI_CHAT_API_KEY}"
            
            test_messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, are you available?"}
            ]
            
            payload = {
                "model": AI_CHAT_MODEL,
                "messages": test_messages,
                "max_tokens": 20,
                "temperature": 0.7
            }
            
            self.logger.info("正在检查AI API可用性...")
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        AI_CHAT_API_URL, 
                        headers=headers, 
                        json=payload, 
                        timeout=10
                    ) as response:
                        
                        if response.status == 200:
                            API_STATUS["available"] = True
                            API_STATUS["error"] = None
                            self.logger.info("AI API连接成功!")
                        else:
                            response_text = await response.text()
                            API_STATUS["available"] = False
                            API_STATUS["error"] = f"API返回错误: {response.status}, {response_text}"
                            self.logger.error(f"AI API连接测试失败: {response.status}, {response_text}")
            except Exception as e:
                API_STATUS["available"] = False
                API_STATUS["error"] = str(e)
                self.logger.error(f"AI API连接测试异常: {str(e)}")
            
            return API_STATUS["available"]
        
        def _extract_message_content(self, message_data: Union[Dict, str]) -> str:
            """从消息中提取实际内容（去掉@部分）"""
            # 记录输入数据类型
            self.logger.info(f"提取消息内容，输入数据类型: {type(message_data)}")
            
            # 提取content
            content = ""
            if isinstance(message_data, dict):
                self.logger.info(f"从字典提取内容，键: {list(message_data.keys())}")
                content = message_data.get("content", "")
                self.logger.info(f"从字典content字段提取到: {content}")
            else:
                # 如果直接传入了字符串
                content = str(message_data)
                self.logger.info(f"直接从字符串提取: {content}")
            
            if not content:
                self.logger.warning("提取到的内容为空")
                return ""
            
            # 记录原始内容
            self.logger.info(f"原始消息内容: {content}")
            
            # 移除Discord格式的@: <@123456>
            clean_content = re.sub(r'<@!?\d+>', '', content).strip()
            
            # 移除一般格式的@用户名: @username
            clean_content = re.sub(r'@[\w\u4e00-\u9fa5]+\s*', '', clean_content).strip()
            
            # 移除CQ码格式的@: [CQ:at,qq=123456]
            clean_content = re.sub(r'\[CQ:at,qq=\d+\]', '', clean_content).strip()
            
            # 移除QQ、微信等平台可能的其他@格式
            clean_content = re.sub(r'@\S+', '', clean_content).strip()
            
            # 如果清理后内容为空，则返回原始内容
            if not clean_content and content:
                self.logger.warning("清理后内容为空，返回原始内容")
                return content
            
            self.logger.info(f"清理后的消息内容: {clean_content}")
            return clean_content

        async def _call_ai_api(self, messages: List[Dict[str, str]]) -> str:
            """
            Call the configured AI API with a conversation history and return the assistant's reply.
            
            This sends the provided messages to AI_CHAT_API_URL using the configured model, max tokens and temperature.
            If the first message is not a system message, a system prompt (AI_CHAT_SYSTEM_PROMPT or a default) will be inserted at the front — note: this mutates the provided `messages` list.
            The function handles JSON parsing of common response shapes (OpenAI-style `choices[0].message.content` and a generic `response` field) and returns a plain string reply or a short user-facing error message when the request or parsing fails.
            
            Parameters:
                messages (List[Dict[str, str]]): Conversation history as a list of message objects with at least
                    the keys `"role"` (e.g., "system", "user", "assistant") and `"content"`. The list may be modified
                    (a system message may be inserted at index 0).
            
            Returns:
                str: The assistant's reply text on success, or a short error message suitable for displaying to users.
            """
            self.logger.info(f"=== 开始调用AI API ===")
            
            # 设置请求头，明确指定不接受压缩内容
            headers = {
                "Content-Type": "application/json", 
                "Accept-Encoding": "identity"  # 不接受压缩内容
            }
            
            if AI_CHAT_API_KEY:
                headers["Authorization"] = f"Bearer {AI_CHAT_API_KEY}"
                self.logger.info("使用API密钥进行认证")
            
            # 添加系统提示（如果不存在）
            if not messages or (messages and messages[0]["role"] != "system"):
                system_prompt = AI_CHAT_SYSTEM_PROMPT or "你是一个有帮助的AI助手。"
                self.logger.info(f"添加系统提示: {system_prompt}")
                messages.insert(0, {"role": "system", "content": system_prompt})
            
            # 记录完整的消息历史
            self.logger.info(f"=== 消息历史（共{len(messages)}条）===")
            for i, msg in enumerate(messages):
                self.logger.info(f"消息[{i}]: 角色={msg.get('role', '未知')}, 内容={msg.get('content', '')[:100]}...")
            
            payload = {
                "model": AI_CHAT_MODEL,
                "messages": messages,
                "max_tokens": AI_CHAT_MAX_TOKENS,
                "temperature": AI_CHAT_TEMPERATURE
            }
            
            self.logger.info(f"发送请求到AI API，URL: {AI_CHAT_API_URL}")
            self.logger.info(f"请求头: {json.dumps(headers, ensure_ascii=False)}")
            self.logger.debug(f"请求体: {json.dumps(payload, ensure_ascii=False)}")
            
            try:
                # 使用更短的超时时间，防止WebSocket连接超时
                timeout = aiohttp.ClientTimeout(total=40, connect=5, sock_connect=5, sock_read=30)

                
                # 创建会话时禁用自动解压
                conn = aiohttp.TCPConnector(force_close=True)  # 强制关闭连接，避免连接池问题
                async with aiohttp.ClientSession(auto_decompress=False, timeout=timeout, connector=conn) as session:
                    # 设置禁用压缩的请求
                    async with session.post(
                        AI_CHAT_API_URL, 
                        headers=headers, 
                        json=payload,
                        compress=False  # 禁用请求压缩
                    ) as response:
                        self.logger.info(f"API响应状态码: {response.status}")
                        self.logger.info(f"API响应头: {response.headers}")
                        
                        # 读取原始响应文本，设置超时
                        try:
                            response_text = await asyncio.wait_for(response.text(errors='replace'), timeout=30)
                            self.logger.info(f"API原始响应前500字符: {response_text[:500]}...")
                        except asyncio.TimeoutError:
                            self.logger.error("读取响应内容超时")
                            return "读取API响应超时，请稍后再试"
                        
                        if response.status != 200:
                            error_msg = f"API请求失败，状态码: {response.status}"
                            if "content-encoding" in response.headers:
                                encoding = response.headers["content-encoding"]
                                error_msg += f", 内容编码: {encoding}"
                            if len(response_text) > 0:
                                error_msg += f", 错误内容: {response_text[:200]}"
                            
                            self.logger.error(error_msg)
                            return f"调用API失败: {response.status}, {response_text[:100] if response_text else '无错误详情'}"
                        
                        try:
                            # 尝试解析JSON响应
                            response_data = json.loads(response_text)
                            self.logger.info(f"API响应格式正确，解析为JSON")
                            
                            # 提取回复内容（根据不同API可能有不同结构）
                            # OpenAI格式
                            if "choices" in response_data and response_data["choices"]:
                                if "message" in response_data["choices"][0]:
                                    content = response_data["choices"][0]["message"].get("content", "")
                                    self.logger.info(f"从OpenAI格式响应提取内容: {content[:100]}...")
                                    return content
                            
                            # 其他API格式
                            if "response" in response_data:
                                content = response_data.get("response", "")
                                self.logger.info(f"从通用格式响应提取内容: {content[:100]}...")
                                return content
                            
                            # 如果没有识别到格式，则返回整个响应
                            self.logger.warning("未能识别响应格式，返回原始响应")
                            return str(response_data)
                            
                        except json.JSONDecodeError as e:
                            self.logger.error(f"API响应不是有效的JSON格式: {str(e)}")
                            return f"API响应解析错误: {str(e)}，原始响应: {response_text[:100]}"
                            
            except aiohttp.ClientError as e:
                self.logger.error(f"API请求客户端错误: {str(e)}")
                self.logger.exception(e)
                return f"API请求失败: {str(e)}"
            except asyncio.TimeoutError:
                self.logger.error("API请求超时")
                return "API请求超时，请稍后再试"
            except Exception as e:
                self.logger.error(f"调用API时发生异常: {str(e)}")
                self.logger.exception(e)
                return f"调用API时发生错误: {str(e)[:100]}..."
            finally:
                # 确保资源释放
                self.logger.info("API调用完成，清理资源")

        async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
            """
            处理AI聊天命令
            
            Args:
                params: 用户输入的文本
                user_id: 用户ID
                group_openid: 群组ID（如果是群消息）
                **kwargs: 其他额外参数，包括event_type和事件数据
                
            Returns:
                str: 处理结果
            """
            try:
                # 检查AI聊天功能是否启用（即使插件可见，功能也可能被禁用）
                if not ENABLE_AI_CHAT:
                    return "AI聊天功能已禁用，请联系管理员开启"
                
                # 如果是help子命令，即使功能禁用也显示帮助
                command_parts = params.strip().split(maxsplit=1)
                subcmd = command_parts[0].lower() if command_parts else ""
                
                if subcmd == "help":
                    help_text = """AI聊天命令:
    - chat <问题>: 与AI对话
    - chat clear: 清空个人聊天历史
    - chat clearall: 清空所有用户聊天历史（仅管理员）
    - chat status: 检查AI API状态（仅管理员）
    - chat prompt: 查看当前系统提示词（仅管理员）
    - chat prompt <新提示词>: 修改系统提示词（仅管理员）
    - chat help: 显示帮助信息

    您也可以直接 @机器人 加问题 进行对话（当命令规范化开启时）"""
                    
                    if not ENABLE_AI_CHAT:
                        help_text += "\n\n注意：AI聊天功能当前已禁用，请联系管理员开启。"
                        
                    return help_text
                
                # 管理命令：清空聊天记录
                if subcmd == "clear":
                    if not auth_manager.is_admin(user_id):
                        return "只有管理员可以使用此命令"
                    
                    if len(command_parts) > 1:
                        target_id = command_parts[1]
                        # 使用新的会话清理方法
                        if self.clear_user_session(target_id):
                            return f"已清空用户 {target_id} 的聊天记录"
                        else:
                            return f"用户 {target_id} 没有活动会话"
                    else:
                        # 清理当前用户会话
                        if self.clear_user_session(user_id):
                            return "已清空您的聊天记录"
                        else:
                            return "您没有活动的聊天会话"
                
                # 管理命令：清空所有聊天记录
                elif subcmd == "clearall":
                    if not auth_manager.is_admin(user_id):
                        return "只有管理员可以使用此命令"
                    
                    # 清空所有会话
                    self.user_sessions = {}
                    self.user_last_activity = {}
                    return "已清空所有用户的聊天记录"
                
                # 管理命令：检查API状态
                elif subcmd == "status":
                    if not auth_manager.is_admin(user_id):
                        return "只有管理员可以使用此命令"
                    
                    # 强制检查API状态
                    await self._check_api_availability()
                    
                    if API_STATUS["available"]:
                        return f"AI API状态: 可用\nAPI地址: {AI_CHAT_API_URL}\n模型: {AI_CHAT_MODEL}"
                    else:
                        return f"AI API状态: 不可用\n错误: {API_STATUS['error']}\nAPI地址: {AI_CHAT_API_URL}"
                
                # 管理命令：修改系统提示词
                elif subcmd == "prompt" and len(command_parts) > 1:
                    if not auth_manager.is_admin(user_id):
                        return "只有管理员可以使用此命令"
                    
                    new_prompt = command_parts[1]
                    global AI_CHAT_SYSTEM_PROMPT
                    AI_CHAT_SYSTEM_PROMPT = new_prompt
                    self.logger.info(f"已修改系统提示词为: {AI_CHAT_SYSTEM_PROMPT}")
                    return f"已修改系统提示词为: {AI_CHAT_SYSTEM_PROMPT}"
                
                # 管理命令：查看当前系统提示词
                elif subcmd == "prompt":
                    if not auth_manager.is_admin(user_id):
                        return "只有管理员可以使用此命令"
                    
                    return f"当前系统提示词为: {AI_CHAT_SYSTEM_PROMPT}"
                
                # 正常聊天
                chat_content = params
                
                # 如果是@消息格式，提取实际内容
                event_type = kwargs.get("event_type", "")
                message_data = kwargs.get("message", {})
                
                # 检查是否是@机器人触发的事件
                is_at_message = False
                if AI_CHAT_MENTION_TRIGGER and ENFORCE_COMMAND_PREFIX:
                    if event_type in ["GROUP_AT_MESSAGE_CREATE", "AT_MESSAGE_CREATE"]:
                        is_at_message = True
                        # 从原始消息中提取内容
                        chat_content = self._extract_message_content_from_event(message_data)
                
                # 如果无内容，返回使用提示
                if not chat_content and not is_at_message:
                    return "请输入您想问的问题，例如: /chat 你好，请问今天天气怎么样？\n使用/chat help获取更多帮助"
                
                # 检查API可用性
                if not API_STATUS["available"] and not await self._check_api_availability():
                    return f"AI API当前不可用，请稍后再试。错误: {API_STATUS['error']}"
                
                # 检查是否达到频率限制
                if not self._check_rate_limit(user_id):
                    return "操作太频繁，请稍后再试"
                
                # 获取或创建用户会话
                session = self._get_or_create_session(user_id)
                
                # 检查会话令牌数并在必要时修剪
                current_token_count = self._estimate_token_count(session)
                if current_token_count > AI_CHAT_MAX_TOKENS * 0.8:
                    session = self._trim_session(session)
                
                # 添加用户消息到会话
                session.append({"role": "user", "content": chat_content})
                
                # 调用AI获取回复
                self.logger.info("开始调用AI API获取回复")
                ai_response = await self._retry_api_call(session)
                
                # 检查AI回复是否有效
                if not ai_response or not ai_response.strip():
                    self.logger.warning("AI返回了空回复")
                    return "抱歉，AI未能提供有效回复，请稍后再试"
                    
                # 将AI回复添加到会话
                session.append({"role": "assistant", "content": ai_response})
                
                # 更新用户会话
                self._update_user_session(user_id, session)
                
                return ai_response
                
            except Exception as e:
                self.logger.error(f"处理聊天命令时出错: {str(e)}")
                self.logger.exception(e)
                return f"处理您的请求时出错: {str(e)[:100]}..."
        
        # 添加一个方法处理@消息事件
        async def handle_at_message(self, event_data: Dict, event_type: str) -> str:
            """处理@消息，提取内容并调用AI API获取回复"""
            self.logger.info("===== 开始处理@消息 =====")
            self.logger.debug(f"事件类型: {event_type}")
            self.logger.debug(f"事件数据: {json.dumps(event_data, ensure_ascii=False)[:300]}...")
            
            try:
                # 检查用户ID
                user_id = self._extract_user_id(event_data)
                if not user_id:
                    self.logger.warning("无法提取用户ID，使用默认ID")
                    user_id = "unknown_user"
                self.logger.info(f"用户ID: {user_id}")
                
                # 检查AI聊天功能是否启用
                if not ENABLE_AI_CHAT:
                    self.logger.info("AI聊天功能未启用")
                    return "AI聊天功能未启用，请联系管理员开启"
                    
                # 检查@触发是否启用
                if not AI_CHAT_MENTION_TRIGGER:
                    self.logger.info("@触发功能未启用")
                    return "AI聊天@触发功能未启用，请联系管理员开启"
                
                # 尝试提取消息内容
                content = self._extract_message_content_from_event(event_data)
                
                # 如果内容为空，使用默认提示语
                if not content or not content.strip():
                    self.logger.warning("提取的消息内容为空，使用默认问候")
                    content = "你好"
                    
                self.logger.info(f"最终提取的消息内容: {content}")
                
                # 检查是否达到了频率限制
                if not self._check_rate_limit(user_id):
                    self.logger.warning(f"用户 {user_id} 已达到频率限制")
                    return "操作太频繁，请稍后再试"
                    
                # 获取或创建用户会话
                session = self._get_or_create_session(user_id)
                session_id = id(session)
                self.logger.info(f"会话ID: {session_id}, 历史消息数: {len(session)}")
                
                # 检查会话令牌数是否超过限制
                current_token_count = self._estimate_token_count(session)
                self.logger.info(f"当前会话估计令牌数: {current_token_count}")
                
                # 如果会话过长，则修剪
                if current_token_count > AI_CHAT_MAX_TOKENS * 0.8:  # 80%阈值
                    self.logger.info(f"会话令牌数接近限制，进行修剪")
                    session = self._trim_session(session)
                    self.logger.info(f"修剪后会话消息数: {len(session)}")
                
                # 添加用户消息到会话
                session.append({"role": "user", "content": content})
                self.logger.info("已将用户消息添加到会话")
                
                # 调用AI获取回复
                self.logger.info("开始调用AI API获取回复")
                ai_response = await self._retry_api_call(session)
                
                # 检查AI回复是否有效
                if not ai_response or not ai_response.strip():
                    self.logger.warning("AI返回了空回复")
                    return "抱歉，AI未能提供有效回复，请稍后再试"
                    
                # 将AI回复添加到会话
                session.append({"role": "assistant", "content": ai_response})
                self.logger.info(f"已将AI回复添加到会话，当前会话长度: {len(session)}")
                
                # 更新用户会话
                self._update_user_session(user_id, session)
                self.logger.info(f"用户 {user_id} 的会话已更新")
                
                # 返回AI回复
                self.logger.info("===== 处理@消息完成 =====")
                return ai_response
                
            except Exception as e:
                self.logger.error(f"处理@消息时发生错误: {str(e)}")
                self.logger.exception(e)
                return f"处理消息时出错: {str(e)[:100]}... 请稍后再试"
        
        def _extract_message_content_from_event(self, event_data: Dict) -> str:
            """从事件数据中提取消息内容，尝试多种提取方法"""
            content = None
            self.logger.info(f"尝试从事件数据中提取消息内容")
            
            # 基于格式化的日志示例，检查特定结构
            if isinstance(event_data, dict):
                # 方法1: content字段（适用于QQ、飞书等平台）
                if "content" in event_data:
                    content = self._extract_message_content(event_data)
                    self.logger.info(f"从content字段提取内容: {content}")
                    if content:
                        return content
                
                # 方法2: 从author的message字段提取（适用于Discord等平台）
                if "author" in event_data and "content" in event_data:
                    content = self._extract_message_content({"content": event_data.get("content", "")})
                    self.logger.info(f"从author/content结构提取内容: {content}")
                    if content:
                        return content
                    
                # 方法3: 从message字段提取（适用于多种平台）
                if "message" in event_data:
                    msg_content = self._extract_message_content(event_data["message"])
                    self.logger.info(f"从message字段提取内容: {msg_content}")
                    if msg_content:
                        return msg_content
                
                # 方法4: 从raw_message字段提取（适用于OneBot协议）
                if "raw_message" in event_data:
                    raw_content = self._extract_message_content({"content": event_data["raw_message"]})
                    self.logger.info(f"从raw_message字段提取内容: {raw_content}")
                    if raw_content:
                        return raw_content
                
                # 方法5: 遍历所有可能的文本字段
                text_fields = ["text", "msg", "message_content", "message_text"]
                for field in text_fields:
                    if field in event_data and isinstance(event_data[field], str):
                        field_content = self._extract_message_content({"content": event_data[field]})
                        self.logger.info(f"从{field}字段提取内容: {field_content}")
                        if field_content:
                            return field_content
                
                # 方法6: 尝试递归搜索所有可能的文本字段
                for key, value in event_data.items():
                    if isinstance(value, str) and len(value) > 0:
                        test_content = self._extract_message_content({"content": value})
                        self.logger.info(f"从字段 {key} 提取内容: {test_content}")
                        if test_content:
                            return test_content
                        
                    # 递归检查嵌套字典
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if isinstance(sub_value, str) and len(sub_value) > 0:
                                test_content = self._extract_message_content({"content": sub_value})
                                self.logger.info(f"从嵌套字段 {key}.{sub_key} 提取内容: {test_content}")
                                if test_content:
                                    return test_content
            
            # 如果所有方法都失败，尝试将整个事件转为字符串
            self.logger.warning("无法从结构化数据中提取内容，尝试使用事件的字符串表示")
            str_content = self._extract_message_content(str(event_data))
            if str_content:
                return str_content
            
            # 如果最终无法提取任何内容，返回空字符串
            self.logger.error("所有提取方法均失败，无法获取消息内容")
            return ""

        def _extract_user_id(self, event_data: Dict) -> Optional[str]:
            """从事件数据中提取用户ID"""
            # 尝试多种可能的位置提取用户ID
            user_id = None
            
            # 直接从根级别提取
            if "user_id" in event_data:
                user_id = str(event_data["user_id"])
                self.logger.info(f"从根级别提取到用户ID: {user_id}")
                return user_id
            
            # 从sender字段提取
            if "sender" in event_data and isinstance(event_data["sender"], dict):
                sender = event_data["sender"]
                if "user_id" in sender:
                    user_id = str(sender["user_id"])
                    self.logger.info(f"从sender字段提取到用户ID: {user_id}")
                    return user_id
                
            # 从其他可能的字段提取
            possible_fields = ["from_id", "uid", "openid", "sender_id", "user_openid"]
            for field in possible_fields:
                if field in event_data:
                    user_id = str(event_data[field])
                    self.logger.info(f"从字段 {field} 提取到用户ID: {user_id}")
                    return user_id
                
            # 记录未找到用户ID
            self.logger.warning(f"在事件数据中未找到用户ID，事件键: {list(event_data.keys())}")
            return None

        def _get_or_create_session(self, user_id: str) -> List[Dict[str, str]]:
            """获取或创建用户的会话历史"""
            if user_id not in self.user_sessions:
                self.logger.info(f"为用户 {user_id} 创建新会话")
                self.user_sessions[user_id] = []
            return self.user_sessions[user_id]
        
        def _update_user_session(self, user_id: str, session: List[Dict[str, str]]) -> None:
            """更新用户的会话历史"""
            self.user_sessions[user_id] = session
            # 记录最后活动时间
            self.user_last_activity[user_id] = time.time()
            self.logger.info(f"已更新用户 {user_id} 的会话和活动时间")
        
        def _check_rate_limit(self, user_id: str) -> bool:
            """检查用户是否达到频率限制"""
            current_time = time.time()
            # 清理过期的频率限制记录
            expired_time = current_time - AI_CHAT_RATE_LIMIT_WINDOW
            self.rate_limit_records = {uid: times for uid, times in self.rate_limit_records.items() 
                                      if any(t > expired_time for t in times)}
            
            # 获取用户的请求记录
            user_records = self.rate_limit_records.get(user_id, [])
            # 只保留窗口期内的记录
            user_records = [t for t in user_records if t > expired_time]
            
            # 检查是否超过限制
            if len(user_records) >= AI_CHAT_RATE_LIMIT_COUNT:
                self.logger.warning(f"用户 {user_id} 已达到频率限制: {len(user_records)}/{AI_CHAT_RATE_LIMIT_COUNT}")
                return False
            
            # 添加新记录
            user_records.append(current_time)
            self.rate_limit_records[user_id] = user_records
            self.logger.info(f"用户 {user_id} 频率检查通过: {len(user_records)}/{AI_CHAT_RATE_LIMIT_COUNT}")
            return True
        
        def _estimate_token_count(self, messages: List[Dict[str, str]]) -> int:
            """估计消息列表的令牌数量（粗略估计）"""
            # 简单估计：每个字符约为0.25个令牌，每条消息有固定开销
            total_tokens = 0
            for msg in messages:
                # 消息基本结构开销 (~4 tokens)
                total_tokens += 4
                # 角色名称 (~1-2 tokens)
                total_tokens += 1
                # 内容字符数 (粗略估计为每4个字符1个token)
                content = msg.get("content", "")
                total_tokens += len(content) // 4
            
            self.logger.info(f"估计消息列表令牌数: {total_tokens}")
            return total_tokens
        
        def _trim_session(self, session: List[Dict[str, str]]) -> List[Dict[str, str]]:
            """修剪会话历史以保持在令牌限制内"""
            # 如果会话为空或只有1-2条消息，不需要修剪
            if len(session) <= 2:
                return session
            
            # 首先，保留系统消息（如果有）
            new_session = []
            if session and session[0].get("role") == "system":
                new_session.append(session[0])
                session = session[1:]
            
            # 计算当前令牌数（不包括系统消息）
            current_tokens = self._estimate_token_count(session)
            target_tokens = int(AI_CHAT_MAX_TOKENS * 0.7)  # 目标为最大限制的70%
            
            # 如果已经在目标范围内，直接返回
            if current_tokens <= target_tokens:
                return new_session + session
            
            # 如果超出目标，从最旧的消息开始移除
            # 但始终保留最新的2-3轮对话（4-6条消息）
            keep_last_n = min(6, len(session))
            recent_messages = session[-keep_last_n:]
            older_messages = session[:-keep_last_n]
            
            # 计算最近消息的令牌数
            recent_tokens = self._estimate_token_count(recent_messages)
            
            # 如果最近的消息已经超过目标，则保留最后3轮对话
            # 否则，从较老的消息中尽可能添加更多而不超过目标
            if recent_tokens > target_tokens:
                # 如果最近消息已经超过限制，则只保留最后2轮（4条消息）
                self.logger.warning(f"最近{keep_last_n}条消息令牌数({recent_tokens})超过目标({target_tokens})，进一步减少")
                keep_last_n = min(4, len(session))
                new_session.extend(session[-keep_last_n:])
            else:
                # 计算可以添加的较老消息
                available_tokens = target_tokens - recent_tokens
                self.logger.info(f"最近{keep_last_n}条消息令牌数: {recent_tokens}, 可用令牌数: {available_tokens}")
                
                # 从后往前添加较老的消息，直到接近但不超过目标
                for msg in reversed(older_messages):
                    msg_tokens = self._estimate_token_count([msg])
                    if available_tokens >= msg_tokens:
                        new_session.insert(len(new_session) - len(recent_messages), msg)
                        available_tokens -= msg_tokens
                    else:
                        break
                    
                # 添加最近的消息
                new_session.extend(recent_messages)
            
            self.logger.info(f"会话已修剪: 从{len(session)}条消息减少到{len(new_session)}条")
            return new_session
        
        def clear_user_session(self, user_id: str) -> bool:
            """清除用户的会话历史"""
            if user_id in self.user_sessions:
                # 保留系统消息如果有
                system_message = None
                current_session = self.user_sessions[user_id]
                if current_session and current_session[0].get("role") == "system":
                    system_message = current_session[0]
                
                # 创建新会话，可能包含系统消息
                new_session = []
                if system_message:
                    new_session.append(system_message)
                
                self.user_sessions[user_id] = new_session
                self.logger.info(f"已清除用户 {user_id} 的会话历史")
                return True
            else:
                self.logger.info(f"用户 {user_id} 没有活动会话")
                return False
            
        def cleanup_inactive_sessions(self, max_idle_time: int = 3600) -> None:
            """清理长时间不活动的会话"""
            current_time = time.time()
            inactive_users = []
            
            for user_id, last_activity in self.user_last_activity.items():
                if current_time - last_activity > max_idle_time:
                    inactive_users.append(user_id)
            
            for user_id in inactive_users:
                if user_id in self.user_sessions:
                    del self.user_sessions[user_id]
                del self.user_last_activity[user_id]
            
            if inactive_users:
                self.logger.info(f"已清理{len(inactive_users)}个不活动会话: {inactive_users}")
        
        async def _retry_api_call(self, messages: List[Dict[str, str]]) -> str:
            """使用不同的请求配置重试API调用，解决gzip压缩问题"""
            self.logger.info("尝试使用不同的请求配置调用API")

            # 第一种方法：使用标准设置但有更严格的超时控制
            self.logger.info("方法1: 使用标准设置和严格超时控制")
            try:
                result = await asyncio.wait_for(self._call_ai_api(messages), timeout=25)
                if not result.startswith("调用API失败") and not result.startswith("API请求失败") and not result.startswith("API响应解析错误"):
                    return result
            except asyncio.TimeoutError:
                self.logger.error("方法1超时")
            except Exception as e:
                self.logger.error(f"方法1异常: {str(e)}")

            # 第二种方法：使用requests库尝试请求
            self.logger.info("方法2: 使用同步请求但在单独线程中执行")
            try:
                import requests
                headers = {
                    "Content-Type": "application/json",
                    "Accept-Encoding": "identity"
                }
                if AI_CHAT_API_KEY:
                    headers["Authorization"] = f"Bearer {AI_CHAT_API_KEY}"

                payload = {
                    "model": AI_CHAT_MODEL,
                    "messages": messages,
                    "max_tokens": AI_CHAT_MAX_TOKENS,
                    "temperature": AI_CHAT_TEMPERATURE
                }

                self.logger.info("发送同步请求")
                # 创建一个新的线程执行同步请求，避免阻塞事件循环
                loop = asyncio.get_event_loop()
                # 使用更短的超时时间
                response_future = loop.run_in_executor(
                    None,
                    lambda: requests.post(
                        AI_CHAT_API_URL,
                        headers=headers,
                        json=payload,
                        timeout=20
                    )
                )
                
                # 添加整体超时
                try:
                    response = await asyncio.wait_for(response_future, timeout=25)
                    
                    self.logger.info(f"同步请求响应状态码: {response.status_code}")
                    if response.status_code == 200:
                        try:
                            response_data = response.json()
                            if "choices" in response_data and response_data["choices"]:
                                if "message" in response_data["choices"][0]:
                                    content = response_data["choices"][0]["message"].get("content", "")
                                    self.logger.info(f"从OpenAI格式响应提取内容: {content[:100]}...")
                                    return content
                            if "response" in response_data:
                                content = response_data.get("response", "")
                                self.logger.info(f"从通用格式响应提取内容: {content[:100]}...")
                                return content
                            return str(response_data)
                        except Exception as e:
                            self.logger.error(f"解析同步请求响应时出错: {str(e)}")
                    else:
                        self.logger.error(f"同步请求失败，状态码: {response.status_code}, 响应: {response.text[:200]}")
                except asyncio.TimeoutError:
                    self.logger.error("方法2整体超时")
            except Exception as e:
                self.logger.error(f"执行同步请求时出错: {str(e)}")
                self.logger.exception(e)

            # 第三种方法：使用curl命令
            self.logger.info("方法3: 使用curl命令")
            try:
                import subprocess
                
                # 准备curl命令
                cmd = ["curl", "-s", "-m", "15", "-X", "POST", AI_CHAT_API_URL]  # 添加15秒超时
                cmd.extend(["-H", "Content-Type: application/json"])
                cmd.extend(["-H", "Accept-Encoding: identity"])
                if AI_CHAT_API_KEY:
                    cmd.extend(["-H", f"Authorization: Bearer {AI_CHAT_API_KEY}"])
                    
                # 准备请求体
                payload = {
                    "model": AI_CHAT_MODEL,
                    "messages": messages,
                    "max_tokens": AI_CHAT_MAX_TOKENS,
                    "temperature": AI_CHAT_TEMPERATURE
                }
                
                # 添加请求体
                cmd.extend(["-d", json.dumps(payload)])
                
                # 执行curl命令，添加整体超时
                self.logger.info(f"执行curl命令: {' '.join(cmd[:5])}...")
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                try:
                    # 添加整体超时控制
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=20)
                    
                    if process.returncode == 0 and stdout:
                        try:
                            response_text = stdout.decode('utf-8')
                            self.logger.info(f"curl命令响应: {response_text[:200]}...")
                            
                            response_data = json.loads(response_text)
                            if "choices" in response_data and response_data["choices"]:
                                if "message" in response_data["choices"][0]:
                                    content = response_data["choices"][0]["message"].get("content", "")
                                    self.logger.info(f"从curl响应提取内容: {content[:100]}...")
                                    return content
                            if "response" in response_data:
                                content = response_data.get("response", "")
                                self.logger.info(f"从curl响应提取内容: {content[:100]}...")
                                return content
                            return str(response_data)
                        except Exception as e:
                            self.logger.error(f"解析curl响应时出错: {str(e)}")
                            stderr_text = stderr.decode('utf-8', errors='replace') if stderr else ""
                            self.logger.error(f"curl错误输出: {stderr_text}")
                    else:
                        stderr_text = stderr.decode('utf-8', errors='replace') if stderr else ""
                        self.logger.error(f"curl命令执行失败，退出码: {process.returncode}, 错误: {stderr_text}")
                except asyncio.TimeoutError:
                    self.logger.error("curl命令执行超时")
                    # 尝试终止进程
                    try:
                        process.terminate()
                    except:
                        pass
            except Exception as e:
                self.logger.error(f"执行curl命令时出错: {str(e)}")
                self.logger.exception(e)
            
            # 所有方法都失败，返回默认消息
            return "抱歉，多次尝试请求AI服务都失败了，请联系管理员检查API配置或网络连接。"

        def update_visibility(self):
            """根据配置更新插件的可见性"""
            # 更新插件的hidden属性，只有当AI聊天和@触发都启用时才显示
            self.hidden = not (ENABLE_AI_CHAT and AI_CHAT_MENTION_TRIGGER)
            self.logger.info(f"已更新AI聊天@触发插件可见性: {'可见' if not self.hidden else '隐藏'}")
            return self.hidden
        
        def reload_config(self):
            """重新加载AI聊天配置"""
            global ENABLE_AI_CHAT, AI_CHAT_API_URL, AI_CHAT_API_KEY, AI_CHAT_MODEL
            global AI_CHAT_MAX_TOKENS, AI_CHAT_TEMPERATURE, AI_CHAT_SYSTEM_PROMPT, AI_CHAT_MENTION_TRIGGER
            
            # 重新从环境变量读取配置
            ENABLE_AI_CHAT = os.environ.get("ENABLE_AI_CHAT", "true").lower() == "true"
            AI_CHAT_API_URL = os.environ.get("AI_CHAT_API_URL", "http://localhost:8000/v1/chat/completions")
            AI_CHAT_API_KEY = os.environ.get("AI_CHAT_API_KEY", "")
            AI_CHAT_MODEL = os.environ.get("AI_CHAT_MODEL", "gpt-3.5-turbo")
            AI_CHAT_MAX_TOKENS = int(os.environ.get("AI_CHAT_MAX_TOKENS", "2000"))
            AI_CHAT_TEMPERATURE = float(os.environ.get("AI_CHAT_TEMPERATURE", "0.7"))
            AI_CHAT_SYSTEM_PROMPT = os.environ.get("AI_CHAT_SYSTEM_PROMPT", "你是一个有用的助手")
            AI_CHAT_MENTION_TRIGGER = os.environ.get("AI_CHAT_MENTION_TRIGGER", "true").lower() == "true"
            
            # 修复API URL配置
            self._fix_api_url()
            
            # 更新插件可见性
            self.update_visibility()
            
            # 更新内部状态
            self.ai_chat_enabled = ENABLE_AI_CHAT
            self.at_trigger_enabled = AI_CHAT_MENTION_TRIGGER
            
            # 记录新配置
            self.logger.info(f"已重新加载AI聊天配置: 启用状态={ENABLE_AI_CHAT}, API地址={AI_CHAT_API_URL}")
            self.logger.info(f"AI聊天配置: 模型={AI_CHAT_MODEL}, 系统提示={AI_CHAT_SYSTEM_PROMPT}")
            
            # 检查API可用性
            asyncio.create_task(self._check_api_availability())
            
            return {
                "enabled": ENABLE_AI_CHAT,
                "api_url": AI_CHAT_API_URL,
                "model": AI_CHAT_MODEL,
                "mention_trigger": AI_CHAT_MENTION_TRIGGER,
                "visible": not self.hidden
            }

    class AIChatMentionPlugin(BasePlugin):
        """
        AI聊天@触发设置插件
        """
        
        def __init__(self):
            super().__init__(
                command="ai_mention", 
                description="通过@机器人触发AI聊天", 
                is_builtin=True,
                hidden=not (ENABLE_AI_CHAT and AI_CHAT_MENTION_TRIGGER)  # 当AI聊天或@触发功能未启用时，隐藏命令
            )
            self.logger = logging.getLogger("plugin.ai_mention")
            
            # 创建AI聊天插件实例用于处理聊天请求
            self.ai_chat = AIChatPlugin(logger=self.logger.getChild("ai_chat"))
            self.logger.info("AI聊天@触发插件初始化完成")
            self.logger.info(f"AI聊天@触发插件在命令列表中{'可见' if (ENABLE_AI_CHAT and AI_CHAT_MENTION_TRIGGER) else '隐藏'}")
        
        async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
            """
            处理@机器人消息，调用AI聊天插件处理
            
            Args:
                params: 通常为空，实际参数来自事件数据
                user_id: 用户ID
                group_openid: 群组ID
                **kwargs: 其他额外参数，主要包含event_type和事件数据
                
            Returns:
                str: 处理结果
            """
            try:
                self.logger.info(f"处理@消息，用户: {user_id}, 群组: {group_openid}")
                self.logger.debug(f"参数: {params}, 额外参数: {kwargs}")
                
                # 检查是否启用AI聊天和@触发功能（即使插件可见，功能也可能被禁用）
                if not ENABLE_AI_CHAT:
                    return "AI聊天功能未启用，请联系管理员开启"
                    
                if not AI_CHAT_MENTION_TRIGGER:
                    return "AI聊天@触发功能未启用，请联系管理员开启"
                    
                # 获取事件数据和类型
                event_data = kwargs.get("event_data", {})
                if not event_data:
                    self.logger.warning("事件数据为空")
                    # 如果没有事件数据但有params，尝试使用params作为消息内容
                    if params:
                        event_data = {"content": params, "user_id": user_id}
                    else:
                        return "无法处理空的事件数据"
                
                # 确保事件数据中包含用户ID
                if "user_id" not in event_data and user_id:
                    event_data["user_id"] = user_id
                    
                event_type = kwargs.get("event_type", "")
                self.logger.info(f"事件类型: {event_type}, 事件数据大小: {len(json.dumps(event_data))}")
                
                # 调用AI聊天插件处理消息
                try:
                    result = await self.ai_chat.handle_at_message(event_data, event_type)
                    self.logger.info(f"AI聊天处理结果: {result[:100]}...")
                    return result
                except Exception as e:
                    self.logger.error(f"AI聊天处理异常: {str(e)}")
                    self.logger.exception(e)
                    return f"处理消息时出错: {str(e)[:100]}..."
            
            except Exception as e:
                self.logger.error(f"@触发插件处理异常: {str(e)}")
                self.logger.exception(e)
                return "抱歉，处理您的消息时出现错误，请稍后再试" 

        def update_visibility(self):
            """根据配置更新插件的可见性"""
            # 更新插件的hidden属性，只有当AI聊天和@触发都启用时才显示
            self.hidden = not (ENABLE_AI_CHAT and AI_CHAT_MENTION_TRIGGER)
            self.logger.info(f"已更新AI聊天@触发插件可见性: {'可见' if not self.hidden else '隐藏'}")
            return self.hidden
            
        def reload_config(self):
            """重新加载AI聊天@触发配置"""
            # 重新从环境变量读取配置
            global ENABLE_AI_CHAT, AI_CHAT_MENTION_TRIGGER
            ENABLE_AI_CHAT = os.environ.get("ENABLE_AI_CHAT", "true").lower() == "true"
            AI_CHAT_MENTION_TRIGGER = os.environ.get("AI_CHAT_MENTION_TRIGGER", "true").lower() == "true"
            
            # 更新插件可见性
            self.update_visibility()
            
            # 让AI聊天插件也重新加载配置
            self.ai_chat.reload_config()
            
            self.logger.info(f"已重新加载AI聊天@触发配置: AI聊天={ENABLE_AI_CHAT}, @触发={AI_CHAT_MENTION_TRIGGER}")
            
            return {
                "enabled": ENABLE_AI_CHAT and AI_CHAT_MENTION_TRIGGER,
                "ai_chat": ENABLE_AI_CHAT,
                "mention_trigger": AI_CHAT_MENTION_TRIGGER,
                "visible": not self.hidden
            }

    class AIChatHelpPlugin(BasePlugin):
        """
        AI聊天帮助插件
        """
        
        def __init__(self):
            super().__init__(
                command="chat_help", 
                description="获取AI聊天命令帮助", 
                is_builtin=True,
                hidden=not ENABLE_AI_CHAT  # 当AI聊天功能未启用时，隐藏命令
            )
            self.logger = logging.getLogger("plugin.chat_help")
            
            # 创建AI聊天插件实例用于处理聊天请求
            self.ai_chat = AIChatPlugin(logger=self.logger.getChild("ai_chat"))
            self.logger.info("AI聊天帮助插件初始化完成")
            self.logger.info(f"AI聊天帮助插件在命令列表中{'可见' if ENABLE_AI_CHAT else '隐藏'}")
        
        async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
            """
            处理AI聊天帮助命令
            
            Args:
                params: 通常为空，实际参数来自事件数据
                user_id: 用户ID
                group_openid: 群组ID
                **kwargs: 其他额外参数，主要包含event_type和事件数据
                
            Returns:
                str: 处理结果
            """
            try:
                self.logger.info(f"处理AI聊天帮助命令，用户: {user_id}, 群组: {group_openid}")
                self.logger.debug(f"参数: {params}, 额外参数: {kwargs}")
                
                # 检查是否启用AI聊天功能（即使插件可见，功能也可能被禁用）
                if not ENABLE_AI_CHAT:
                    return "AI聊天功能未启用，请联系管理员开启"
                    
                # 获取事件数据和类型
                event_data = kwargs.get("event_data", {})
                if not event_data:
                    self.logger.warning("事件数据为空")
                    # 如果没有事件数据但有params，尝试使用params作为消息内容
                    if params:
                        event_data = {"content": params, "user_id": user_id}
                    else:
                        return "无法处理空的事件数据"
                
                # 确保事件数据中包含用户ID
                if "user_id" not in event_data and user_id:
                    event_data["user_id"] = user_id
                    
                event_type = kwargs.get("event_type", "")
                self.logger.info(f"事件类型: {event_type}, 事件数据大小: {len(json.dumps(event_data))}")
                
                # 调用AI聊天插件处理消息
                try:
                    result = await self.ai_chat.handle_at_message(event_data, event_type)
                    self.logger.info(f"AI聊天帮助处理结果: {result[:100]}...")
                    return result
                except Exception as e:
                    self.logger.error(f"AI聊天帮助处理异常: {str(e)}")
                    self.logger.exception(e)
                    return f"处理消息时出错: {str(e)[:100]}..."
            
            except Exception as e:
                self.logger.error(f"AI聊天帮助插件处理异常: {str(e)}")
                self.logger.exception(e)
                return "抱歉，处理您的消息时出现错误，请稍后再试" 

        def update_visibility(self):
            """根据配置更新插件的可见性"""
            # 更新插件的hidden属性，只有当AI聊天功能启用时才显示
            self.hidden = not ENABLE_AI_CHAT
            self.logger.info(f"已更新AI聊天帮助插件可见性: {'可见' if not self.hidden else '隐藏'}")
            return self.hidden
            
        def reload_config(self):
            """重新加载AI聊天帮助配置"""
            # 重新从环境变量读取配置
            global ENABLE_AI_CHAT
            ENABLE_AI_CHAT = os.environ.get("ENABLE_AI_CHAT", "true").lower() == "true"
            
            # 更新插件可见性
            self.update_visibility()
            
            self.logger.info(f"已重新加载AI聊天帮助配置: AI聊天={ENABLE_AI_CHAT}")
            
            return {
                "enabled": ENABLE_AI_CHAT,
                "visible": not self.hidden
            }

# 如果AI聊天功能启用，导出插件类以便插件管理器发现并加载
if ENABLE_AI_CHAT:
    __all__ = ["AIChatPlugin", "AIChatMentionPlugin", "AIChatHelpPlugin"] 
else:
    logger.info("AI聊天功能已禁用，不加载AI聊天插件") 