import time
import requests
from config import BOT_APPID, BOT_APPSECRET, API_AUTH_URL, BOT_TOKEN

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
        
        response = requests.post(API_AUTH_URL, json=data)
        if response.status_code != 200:
            raise Exception(f"获取访问令牌失败: {response.text}")
        
        result = response.json()
        self.access_token = result['access_token']
        self.expires_at = current_time + result.get('expires_in', 7200)
        
        return self.access_token
    
    def get_auth_header(self, use_bot_token=False):
        """获取包含认证信息的请求头
        
        Args:
            use_bot_token (bool): 是否使用 Bot 令牌格式，用于某些 API
        """
        if use_bot_token:
            # 使用 Bot 令牌格式
            return {
                "Authorization": f"Bot {BOT_APPID}.{BOT_TOKEN}",
                "Content-Type": "application/json"
            }
        else:
            # 使用 OAuth 令牌格式
            token = self.get_access_token()
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

# 创建单例
auth_manager = Auth() 