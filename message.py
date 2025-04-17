import requests
import logging
from auth import auth_manager
from config import API_SEND_MESSAGE_URL, API_BASE_URL

# 配置日志
logger = logging.getLogger("message")

class MessageBuilder:
    @staticmethod
    def build_text_message(content):
        """构建纯文本消息"""
        return {
            "content": content
        }
    
    @staticmethod
    def build_image_message(url):
        """构建图片消息"""
        return {
            "image": url
        }
    
    @staticmethod
    def build_keyboard_message(content, buttons):
        """构建带按钮的消息"""
        return {
            "content": content,
            "keyboard": {
                "buttons": buttons
            }
        }

class MessageSender:
    @staticmethod
    def send_message(channel_id, message_type, message_content, is_group=False):
        """发送消息到指定频道或群聊"""
        # 群聊消息使用 Bot 令牌，频道消息使用 OAuth 令牌
        headers = auth_manager.get_auth_header(use_bot_token=is_group)
        
        # 确保消息内容格式正确
        if message_type == "text" and isinstance(message_content, str):
            content_to_send = message_content
        elif isinstance(message_content, dict) and "content" in message_content:
            content_to_send = message_content["content"]
        else:
            content_to_send = str(message_content)
            
        # 对于群聊消息，使用不同的API端点
        if is_group:
            api_url = f"{API_BASE_URL}/v2/groups/{channel_id}/messages"
            data = {
                "msg_type": 0,  # 0表示文本消息
                "content": content_to_send
            }
            # 记录完整请求数据用于调试
            logger.info(f"群聊请求数据: {data}")
        else:
            api_url = API_SEND_MESSAGE_URL
            data = {
                "channel_id": channel_id,
                "msg_type": message_type,
                "content": content_to_send
            }
        
        logger.info(f"发送消息到 {channel_id}, 类型: {message_type}, 是群聊: {is_group}")
        
        try:
            response = requests.post(api_url, headers=headers, json=data)
            logger.info(f"API响应状态码: {response.status_code}")
            logger.info(f"API响应内容: {response.text}")
            
            if response.status_code != 200:
                logger.error(f"发送消息失败: {response.text}")
                raise Exception(f"发送消息失败: {response.text}")
            
            logger.info("消息发送成功")
            return response.json()
        except Exception as e:
            logger.error(f"发送消息异常: {str(e)}")
            raise
    
    @staticmethod
    def reply_message(channel_id, message_id, message_type, message_content, is_group=False):
        """回复特定消息，支持频道消息和群聊消息"""
        # 群聊消息使用 Bot 令牌，频道消息使用 OAuth 令牌
        headers = auth_manager.get_auth_header(use_bot_token=is_group)
        
        # 确保消息内容格式正确
        if message_type == "text" and isinstance(message_content, str):
            content_to_send = message_content
        elif isinstance(message_content, dict) and "content" in message_content:
            content_to_send = message_content["content"]
        else:
            content_to_send = str(message_content)
            
        # 对于群聊消息，使用不同的API端点
        if is_group:
            api_url = f"{API_BASE_URL}/v2/groups/{channel_id}/messages"
            data = {
                "msg_type": 0,  # 0表示文本消息
                "content": content_to_send,
                "msg_id": message_id
            }
            # 记录完整请求数据用于调试
            logger.info(f"群聊回复请求数据: {data}")
        else:
            api_url = API_SEND_MESSAGE_URL
            data = {
                "channel_id": channel_id,
                "msg_id": message_id,
                "msg_type": message_type,
                "content": content_to_send
            }
        
        logger.info(f"回复消息 {message_id} 到 {channel_id}, 类型: {message_type}, 是群聊: {is_group}")
        
        try:
            response = requests.post(api_url, headers=headers, json=data)
            logger.info(f"API响应状态码: {response.status_code}")
            logger.info(f"API响应内容: {response.text}")
            
            if response.status_code != 200:
                logger.error(f"回复消息失败: {response.text}")
                raise Exception(f"回复消息失败: {response.text}")
            
            logger.info("消息回复成功")
            return response.json()
        except Exception as e:
            logger.error(f"回复消息异常: {str(e)}")
            raise
    
    @staticmethod
    def send_group_message(group_openid, message_type, message_content):
        """专门发送群聊消息"""
        return MessageSender.send_message(group_openid, message_type, message_content, is_group=True)
    
    @staticmethod
    def reply_group_message(group_openid, message_id, message_type, message_content):
        """专门回复群聊消息"""
        return MessageSender.reply_message(group_openid, message_id, message_type, message_content, is_group=True) 