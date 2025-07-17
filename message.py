import requests
import logging
from auth import auth_manager
from config import API_SEND_MESSAGE_URL, API_BASE_URL
from enhanced_message_types import MessageBuilder, MessageType
from typing import Optional, Dict, Any, Union

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
    def _prepare_message_data(message_content: Union[str, Dict[str, Any]], message_type: Union[str, int] = "text") -> Dict[str, Any]:
        """准备消息数据，支持多种消息格式"""
        if isinstance(message_content, dict):
            # 如果是字典格式，可能包含完整的消息结构
            if "msg_type" in message_content:
                return message_content
            elif "content" in message_content:
                return {
                    "content": message_content["content"],
                    "msg_type": MessageType.TEXT.value if message_type == "text" else message_type,
                    **{k: v for k, v in message_content.items() if k != "content"}
                }

        # 处理字符串内容
        content_to_send = str(message_content)
        msg_type = MessageType.TEXT.value if message_type == "text" else message_type

        return {
            "content": content_to_send,
            "msg_type": msg_type
        }

    @staticmethod
    def send_message(channel_id, message_type, message_content, is_group=False):
        """发送消息到指定频道或群聊"""
        # 群聊消息使用 Bot 令牌，频道消息使用 OAuth 令牌
        headers = auth_manager.get_auth_header(use_bot_token=is_group)

        # 准备消息数据
        message_data = MessageSender._prepare_message_data(message_content, message_type)
        content_to_send = message_data.get("content", str(message_content))
            
        # 对于群聊消息，使用不同的API端点
        if is_group:
            api_url = f"{API_BASE_URL}/v2/groups/{channel_id}/messages"
            data = {
                "msg_type": message_data.get("msg_type", 0),
                "content": content_to_send
            }
            # 添加其他消息字段支持
            for key in ["markdown", "keyboard", "ark", "media", "image"]:
                if key in message_data:
                    data[key] = message_data[key]
            # 记录完整请求数据用于调试
            logger.info(f"群聊请求数据: {data}")
        else:
            api_url = API_SEND_MESSAGE_URL
            data = {
                "channel_id": channel_id,
                "msg_type": message_data.get("msg_type", MessageType.TEXT.value if message_type == "text" else message_type),
                "content": content_to_send
            }
            # 添加其他消息字段支持
            for key in ["markdown", "keyboard", "ark", "media", "image"]:
                if key in message_data:
                    data[key] = message_data[key]
        
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
        
    @staticmethod
    def send_private_message(user_openid, message_content, message_type=0, markdown=None, keyboard=None, ark=None, media=None, event_id=None):
        """
        发送私聊消息到指定用户
        
        Args:
            user_openid: QQ用户的openid
            message_content: 消息内容
            message_type: 消息类型，0=文本，2=markdown，3=ark，4=embed，7=media富媒体
            markdown: markdown对象
            keyboard: 按钮对象
            ark: ark对象 
            media: 富媒体对象
            event_id: 前置事件ID，用于发送被动消息
            
        Returns:
            API响应结果
        """
        # 使用Bot令牌进行认证
        headers = auth_manager.get_auth_header(use_bot_token=True)
        
        # 构建API URL
        api_url = f"{API_BASE_URL}/v2/users/{user_openid}/messages"
        
        # 构建请求数据
        data = {
            "content": message_content,
            "msg_type": message_type
        }
        
        # 添加可选参数
        if markdown:
            data["markdown"] = markdown
        if keyboard:
            data["keyboard"] = keyboard
        if ark:
            data["ark"] = ark
        if media:
            data["media"] = media
        if event_id:
            data["event_id"] = event_id
            
        logger.info(f"发送私聊消息到用户 {user_openid}, 类型: {message_type}")
        logger.info(f"私聊请求数据: {data}")
        
        try:
            response = requests.post(api_url, headers=headers, json=data)
            logger.info(f"API响应状态码: {response.status_code}")
            logger.info(f"API响应内容: {response.text}")
            
            if response.status_code != 200:
                logger.error(f"发送私聊消息失败: {response.text}")
                raise Exception(f"发送私聊消息失败: {response.text}")
            
            logger.info("私聊消息发送成功")
            return response.json()
        except Exception as e:
            logger.error(f"发送私聊消息异常: {str(e)}")
            raise
            
    @staticmethod
    def reply_private_message(user_openid, message_id, message_content, message_type=0, markdown=None, keyboard=None, ark=None, media=None, msg_seq=1):
        """
        回复私聊消息
        
        Args:
            user_openid: QQ用户的openid
            message_id: 要回复的消息ID
            message_content: 消息内容
            message_type: 消息类型，0=文本，2=markdown，3=ark，4=embed，7=media富媒体
            markdown: markdown对象
            keyboard: 按钮对象
            ark: ark对象
            media: 富媒体对象
            msg_seq: 回复消息序号，默认为1
            
        Returns:
            API响应结果
        """
        # 使用Bot令牌进行认证
        headers = auth_manager.get_auth_header(use_bot_token=True)
        
        # 构建API URL
        api_url = f"{API_BASE_URL}/v2/users/{user_openid}/messages"
        
        # 构建请求数据
        data = {
            "content": message_content,
            "msg_type": message_type,
            "msg_id": message_id,
            "msg_seq": msg_seq
        }
        
        # 添加可选参数
        if markdown:
            data["markdown"] = markdown
        if keyboard:
            data["keyboard"] = keyboard
        if ark:
            data["ark"] = ark
        if media:
            data["media"] = media
            
        logger.info(f"回复私聊消息 {message_id} 到用户 {user_openid}, 类型: {message_type}")
        logger.info(f"私聊回复请求数据: {data}")
        
        try:
            response = requests.post(api_url, headers=headers, json=data)
            logger.info(f"API响应状态码: {response.status_code}")
            logger.info(f"API响应内容: {response.text}")
            
            if response.status_code != 200:
                logger.error(f"回复私聊消息失败: {response.text}")
                raise Exception(f"回复私聊消息失败: {response.text}")
            
            logger.info("私聊消息回复成功")
            return response.json()
        except Exception as e:
            logger.error(f"回复私聊消息异常: {str(e)}")
            raise

    # 新增的增强消息发送方法
    @staticmethod
    def send_enhanced_message(target_id: str, message_data: Dict[str, Any], is_group: bool = False, is_private: bool = False):
        """
        发送增强消息，支持多种消息类型

        Args:
            target_id: 目标ID（频道ID、群组ID或用户ID）
            message_data: 消息数据字典
            is_group: 是否为群聊消息
            is_private: 是否为私聊消息
        """
        if is_private:
            return MessageSender.send_private_message(
                target_id,
                message_data.get("content", ""),
                message_data.get("msg_type", 0),
                message_data.get("markdown"),
                message_data.get("keyboard"),
                message_data.get("ark"),
                message_data.get("media")
            )
        else:
            return MessageSender.send_message(target_id, message_data.get("msg_type", "text"), message_data, is_group)

    @staticmethod
    def send_markdown_message(target_id: str, content: str, markdown: Dict[str, Any], is_group: bool = False, is_private: bool = False):
        """发送Markdown消息"""
        message_data = MessageBuilder.build_markdown_message(content, markdown)
        return MessageSender.send_enhanced_message(target_id, message_data, is_group, is_private)

    @staticmethod
    def send_image_message(target_id: str, image_url: str, is_group: bool = False, is_private: bool = False):
        """发送图片消息"""
        message_data = MessageBuilder.build_image_message(image_url)
        return MessageSender.send_enhanced_message(target_id, message_data, is_group, is_private)

    @staticmethod
    def send_keyboard_message(target_id: str, content: str, keyboard: Dict[str, Any], is_group: bool = False, is_private: bool = False):
        """发送带按钮的消息"""
        message_data = MessageBuilder.build_keyboard_message(content, keyboard)
        return MessageSender.send_enhanced_message(target_id, message_data, is_group, is_private)

    @staticmethod
    def send_file_message(target_id: str, file_info: Dict[str, Any], is_group: bool = False, is_private: bool = False):
        """发送文件消息"""
        message_data = MessageBuilder.build_file_message(file_info)
        return MessageSender.send_enhanced_message(target_id, message_data, is_group, is_private)

    @staticmethod
    def send_ark_message(target_id: str, ark: Dict[str, Any], is_group: bool = False, is_private: bool = False):
        """发送ARK消息"""
        message_data = MessageBuilder.build_ark_message(ark)
        return MessageSender.send_enhanced_message(target_id, message_data, is_group, is_private)