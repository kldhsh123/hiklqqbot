import random
import logging
from plugins.base_plugin import BasePlugin

class FortunePlugin(BasePlugin):
    """
    运势插件，随机返回1-100的运势值
    """
    
    def __init__(self):
        super().__init__(command="/运势", description="查看今日运势，返回1-100的幸运指数", is_builtin=False)
        self.logger = logging.getLogger("plugin.fortune")
        
        # 运势等级说明
        self.fortune_levels = {
            (1, 20): "不太好，今天做事多小心哦~",
            (21, 40): "一般般，平常心对待今天吧！",
            (41, 60): "还不错，可能有小惊喜等着你！",
            (61, 80): "很棒！适合尝试新事物！",
            (81, 100): "超级幸运！今天宜大胆行动！"
        }
    
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """
        处理运势命令
        
        Args:
            params: 命令参数（不使用）
            user_id: 用户ID（不使用）
            group_openid: 群组ID（不使用）
            **kwargs: 其他额外参数
            
        Returns:
            str: 运势结果
        """
        self.logger.info("收到运势命令")
        
        # 生成1-100的随机数
        fortune_value = random.randint(1, 100)
        
        # 获取对应等级的描述
        fortune_desc = ""
        for (min_val, max_val), desc in self.fortune_levels.items():
            if min_val <= fortune_value <= max_val:
                fortune_desc = desc
                break
        
        # 构建运势消息
        result = f"✨ 今日运势: {fortune_value}\n"
        result += f"💫 运势评价: {fortune_desc}\n"
        
        # 添加额外信息
        if params:
            result += f"\n针对「{params}」的特别运势:\n"
            special_fortune = random.randint(1, 100)
            result += f"🔮 特别运势值: {special_fortune}\n"
        
        return result 