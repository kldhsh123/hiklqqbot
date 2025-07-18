import requests
import logging
from auth import auth_manager
from config import API_SEND_MESSAGE_URL, API_BASE_URL
from enhanced_message_types import MessageType
from typing import Dict, Any, Union

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

    @staticmethod
    def build_media_message(media_info, content=""):
        """
        构建富媒体消息

        Args:
            media_info: 富媒体信息，包含file_info等字段
            content: 可选的文本内容

        Returns:
            dict: 富媒体消息数据
        """
        return {
            "content": content,
            "msg_type": 7,  # 7表示富媒体类型
            "media": media_info
        }

    @staticmethod
    def build_video_message(media_info, content=""):
        """
        构建视频消息

        Args:
            media_info: 视频媒体信息
            content: 可选的文本内容

        Returns:
            dict: 视频消息数据
        """
        return MessageBuilder.build_media_message(media_info, content)

    @staticmethod
    def build_audio_message(media_info, content=""):
        """
        构建语音消息

        Args:
            media_info: 语音媒体信息
            content: 可选的文本内容

        Returns:
            dict: 语音消息数据
        """
        return MessageBuilder.build_media_message(media_info, content)

    @staticmethod
    def build_markdown_message(content, markdown):
        """构建Markdown消息"""
        return {
            "content": content,
            "msg_type": 2,  # 2表示markdown类型
            "markdown": markdown
        }

    @staticmethod
    def build_ark_message(ark):
        """构建ARK消息"""
        return {
            "msg_type": 3,  # 3表示ark类型
            "ark": ark
        }

    @staticmethod
    def build_file_message(file_info):
        """构建文件消息"""
        return {
            "msg_type": 7,  # 7表示富媒体/文件类型
            "media": file_info
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
            trace_id = response.headers.get("X-Tps-trace-ID")
            if trace_id:
                logger.debug(f"X-Tps-trace-ID: {trace_id}")
            
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
            trace_id = response.headers.get("X-Tps-trace-ID")
            if trace_id:
                logger.debug(f"X-Tps-trace-ID: {trace_id}")
            
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
            trace_id = response.headers.get("X-Tps-trace-ID")
            if trace_id:
                logger.debug(f"X-Tps-trace-ID: {trace_id}")
            
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
            trace_id = response.headers.get("X-Tps-trace-ID")
            if trace_id:
                logger.debug(f"X-Tps-trace-ID: {trace_id}")
            
            if response.status_code != 200:
                logger.error(f"回复私聊消息失败: {response.text}")
                raise Exception(f"回复私聊消息失败: {response.text}")
            
            logger.info("私聊消息回复成功")
            return response.json()
        except Exception as e:
            logger.error(f"回复私聊消息异常: {str(e)}")
            raise

    @staticmethod
    def upload_private_media(user_openid: str, file_type: int, url: str, srv_send_msg: bool = False):
        """
        上传单聊富媒体文件

        Args:
            user_openid: QQ用户的openid
            file_type: 媒体类型，1=图片png/jpg，2=视频mp4，3=语音silk，4=文件（暂不开放）
            url: 需要发送媒体资源的url
            srv_send_msg: 设置true会直接发送消息到目标端，且会占用主动消息频次

        Returns:
            dict: 包含file_uuid, file_info, ttl等字段的响应数据
        """
        # 使用Bot令牌进行认证
        headers = auth_manager.get_auth_header(use_bot_token=True)

        # 构建API URL
        api_url = f"{API_BASE_URL}/v2/users/{user_openid}/files"

        # 构建请求数据
        data = {
            "file_type": file_type,
            "url": url,
            "srv_send_msg": srv_send_msg
        }

        logger.info(f"上传单聊媒体文件到用户 {user_openid}, 类型: {file_type}, URL: {url}")
        logger.info(f"上传请求数据: {data}")

        try:
            response = requests.post(api_url, headers=headers, json=data)
            logger.info(f"API响应状态码: {response.status_code}")
            logger.info(f"API响应内容: {response.text}")
            trace_id = response.headers.get("X-Tps-trace-ID")
            if trace_id:
                logger.debug(f"X-Tps-trace-ID: {trace_id}")

            if response.status_code != 200:
                logger.error(f"上传单聊媒体文件失败: {response.text}")
                raise Exception(f"上传单聊媒体文件失败: {response.text}")

            logger.info("单聊媒体文件上传成功")
            return response.json()
        except Exception as e:
            logger.error(f"上传单聊媒体文件异常: {str(e)}")
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

    @staticmethod
    def send_private_media_message(user_openid: str, file_type: int, url: str, content: str = "", srv_send_msg: bool = False):
        """
        发送单聊富媒体消息（一站式方法）

        Args:
            user_openid: QQ用户的openid
            file_type: 媒体类型，1=图片，2=视频，3=语音，4=文件（暂不开放）
            url: 媒体资源的URL
            content: 可选的文本内容
            srv_send_msg: 是否直接发送（true会占用主动消息频次）

        Returns:
            dict: API响应结果
        """
        if srv_send_msg:
            # 直接发送模式
            return MessageSender.upload_private_media(user_openid, file_type, url, True)
        else:
            # 两步发送模式：先上传，再发送
            # 1. 上传媒体文件
            upload_result = MessageSender.upload_private_media(user_openid, file_type, url, False)

            # 2. 构建并发送富媒体消息
            media_info = {
                "file_info": upload_result.get("file_info")
            }
            message_data = MessageBuilder.build_media_message(media_info, content)

            return MessageSender.send_enhanced_message(user_openid, message_data, is_private=True)

    @staticmethod
    def send_private_video_message(user_openid: str, video_url: str, content: str = "", srv_send_msg: bool = False):
        """
        发送单聊视频消息

        Args:
            user_openid: QQ用户的openid
            video_url: 视频文件的URL（MP4格式）
            content: 可选的文本内容
            srv_send_msg: 是否直接发送

        Returns:
            dict: API响应结果
        """
        return MessageSender.send_private_media_message(user_openid, 2, video_url, content, srv_send_msg)

    @staticmethod
    def send_private_audio_message(user_openid: str, audio_url: str, content: str = "", srv_send_msg: bool = False):
        """
        发送单聊语音消息

        Args:
            user_openid: QQ用户的openid
            audio_url: 语音文件的URL（SILK格式）
            content: 可选的文本内容
            srv_send_msg: 是否直接发送

        Returns:
            dict: API响应结果
        """
        return MessageSender.send_private_media_message(user_openid, 3, audio_url, content, srv_send_msg)

    @staticmethod
    def send_private_image_message(user_openid: str, image_url: str, content: str = "", srv_send_msg: bool = False):
        """
        发送单聊图片消息

        Args:
            user_openid: QQ用户的openid
            image_url: 图片文件的URL（PNG/JPG格式）
            content: 可选的文本内容
            srv_send_msg: 是否直接发送

        Returns:
            dict: API响应结果
        """
        return MessageSender.send_private_media_message(user_openid, 1, image_url, content, srv_send_msg)
