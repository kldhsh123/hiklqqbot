import time
import requests
from config import BOT_APPID, BOT_APPSECRET, API_AUTH_URL, BOT_TOKEN
import logging

logger = logging.getLogger("auth")

class Auth:
    def __init__(self):
        self.access_token = None
        self.expires_at = 0
    
    def get_access_token(self):
        """获取或刷新访问令牌"""
        current_time = time.time()
        
        # 如果令牌未过期，直接返回
        if self.access_token and current_time < self.expires_at - 60:
            return self.access_token
        
        # 请求新的访问令牌
        data = {
            "appId": BOT_APPID,
            "clientSecret": BOT_APPSECRET
        }
        
        # 添加内容类型头
        headers = {
            "Content-Type": "application/json"
        }
        
        response = requests.post(API_AUTH_URL, json=data, headers=headers)
        if response.status_code != 200:
            logger.error(f"获取访问令牌失败: 状态码 {response.status_code}")
            logger.error(f"响应内容: {response.text}")
            raise Exception(f"获取访问令牌失败: {response.text}")
        
        trace_id = response.headers.get("X-Tps-trace-ID")
        if trace_id:
            logger.debug(f"X-Tps-trace-ID: {trace_id}")
            
        result = response.json()
        
        # 记录完整的响应以便调试
        logger.debug(f"获取token响应: {result}")
        
        if 'access_token' not in result:
            logger.error(f"访问令牌格式不正确: {result}")
            raise Exception(f"访问令牌格式不正确: {result}")
            
        self.access_token = result['access_token']
        
        # 确保expires_in是整数类型
        try:
            expires_in = int(result.get('expires_in', 7200))
        except (ValueError, TypeError):
            logger.warning(f"无法将expires_in转换为整数，使用默认值7200: {result.get('expires_in')}")
            expires_in = 7200
            
        self.expires_in = expires_in
        self.expires_at = current_time + expires_in
        
        logger.info(f"成功获取新的访问令牌，有效期 {self.expires_in} 秒")
        return self.access_token
    
    def get_auth_header(self, use_bot_token=False):
        """获取包含认证信息的请求头
        
        Args:
            use_bot_token (bool): 之前参数用于区分是否使用Bot令牌格式，现在QQ已经统一要求使用AccessToken
        """
        # 获取动态令牌，不再区分令牌格式，QQ已禁用固定Token
        token = self.get_access_token()
        return {
            "Authorization": f"QQBot {token}",
            "Content-Type": "application/json"
        }

# 创建单例
auth_manager = Auth() 