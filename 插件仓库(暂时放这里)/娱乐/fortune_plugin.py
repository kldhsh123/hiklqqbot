import random
import logging
import os
import json
from datetime import datetime
from plugins.base_plugin import BasePlugin

class FortunePlugin(BasePlugin):
    """
    今日运势插件，为每个用户提供每日1-100的运势值，每天每人只能抽一次。
    
    功能特点:
    1. 每个用户每天只能抽取一次运势
    2. 重复抽取会返回当天的结果
    3. 支持针对特定关键词的特别运势
    4. 自动清理过期运势记录，默认只保留30天内的记录
    """
    
    def __init__(self):
        super().__init__(command="运势", description="查看今日运势，返回1-100的幸运指数", is_builtin=False, display_name="运势")
        self.logger = logging.getLogger("plugin.fortune")
        
        # 运势等级说明
        self.fortune_levels = {
            (1, 20): "不太好，今天做事多小心哦~",
            (21, 40): "一般般，平常心对待今天吧！",
            (41, 60): "还不错，可能有小惊喜等着你！",
            (61, 80): "很棒！适合尝试新事物！",
            (81, 100): "超级幸运！今天宜大胆行动！"
        }
        
        # 数据存储相关
        self.data_dir = "data/fortune"
        os.makedirs(self.data_dir, exist_ok=True)
        self.fortune_file = os.path.join(self.data_dir, "fortune_records.json")
        
        # 保留运势记录的天数
        self.record_keep_days = 30
        
        # 用户运势记录 {user_id: {date_str: fortune_value}}
        self.fortune_records = self._load_data()
    
    def _load_data(self):
        """加载运势记录数据，并清理过期记录"""
        data = {}
        if os.path.exists(self.fortune_file):
            try:
                with open(self.fortune_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.logger.info("成功加载运势记录数据")
            except Exception as e:
                self.logger.error(f"加载运势记录数据失败: {e}")
        else:
            self.logger.info("没有找到现有运势记录，创建新的记录")
        
        # 返回加载的数据
        result = data or {}
        
        # 清理过期记录
        self.fortune_records = result
        self._clean_expired_records()
        return self.fortune_records
    
    def _save_data(self):
        """保存运势记录数据"""
        try:
            with open(self.fortune_file, "w", encoding="utf-8") as f:
                json.dump(self.fortune_records, f, ensure_ascii=False, indent=2)
            self.logger.info("成功保存运势记录数据")
            return True
        except Exception as e:
            self.logger.error(f"保存运势记录数据失败: {e}")
            return False
    
    def _get_today_date_str(self):
        """获取今天的日期字符串，格式为YYYY-MM-DD"""
        return datetime.now().strftime("%Y-%m-%d")
    
    def _clean_expired_records(self):
        """清理过期的运势记录，只保留最近N天的记录"""
        if not self.fortune_records:
            return
            
        self.logger.info(f"开始清理过期运势记录，保留{self.record_keep_days}天内的记录")
        today = datetime.now()
        records_cleaned = 0
        users_with_records = list(self.fortune_records.keys())
        
        for user_id in users_with_records:
            if not self.fortune_records[user_id]:  # 如果用户没有记录，删除空字典
                del self.fortune_records[user_id]
                continue
                
            date_records = list(self.fortune_records[user_id].keys())
            for date_str in date_records:
                try:
                    # 将日期字符串转换为datetime对象
                    record_date = datetime.strptime(date_str, "%Y-%m-%d")
                    # 计算日期差
                    days_diff = (today - record_date).days
                    
                    # 如果超过保留天数，删除记录
                    if days_diff > self.record_keep_days:
                        del self.fortune_records[user_id][date_str]
                        records_cleaned += 1
                except ValueError:
                    # 日期格式无效，删除记录
                    self.logger.warning(f"发现无效日期格式: {date_str}，已删除")
                    del self.fortune_records[user_id][date_str]
                    records_cleaned += 1
            
            # 如果用户的所有记录都被删除，删除用户条目
            if not self.fortune_records[user_id]:
                del self.fortune_records[user_id]
        
        if records_cleaned > 0:
            self.logger.info(f"清理完成，共删除{records_cleaned}条过期记录")
            self._save_data()
        else:
            self.logger.info("没有发现过期记录，无需清理")
    
    async def handle(self, params: str, user_id: str = None, group_openid: str = None, **kwargs) -> str:
        """
        处理运势命令
        
        Args:
            params: 命令参数（不使用）
            user_id: 用户ID
            group_openid: 群组ID（不使用）
            **kwargs: 其他额外参数
            
        Returns:
            str: 运势结果
        """
        self.logger.info("收到运势命令")
        
        # 如果没有用户ID，使用默认值
        user_id = user_id or "anonymous"
        
        # 获取今日日期
        today = self._get_today_date_str()
        
        # 检查用户今天是否已经抽过运势
        if user_id in self.fortune_records and today in self.fortune_records[user_id]:
            # 如果已抽过，返回之前的结果
            fortune_value = self.fortune_records[user_id][today]
            self.logger.info(f"用户 {user_id} 今天已经抽过运势: {fortune_value}")
            result = f"✨ 今日运势: {fortune_value}\n"
            
            # 获取对应等级的描述
            fortune_desc = ""
            for (min_val, max_val), desc in self.fortune_levels.items():
                if min_val <= fortune_value <= max_val:
                    fortune_desc = desc
                    break
            
            result += f"💫 运势评价: {fortune_desc}\n"
            
            # 添加提示信息
            result += "\n🔮 提示：每人每天只能抽一次运势哦！"
            
            return result
        
        # 如果是新的一天或新用户，生成新的运势
        fortune_value = random.randint(1, 100)
        
        # 保存运势记录
        if user_id not in self.fortune_records:
            self.fortune_records[user_id] = {}
        
        self.fortune_records[user_id][today] = fortune_value
        self._save_data()
        
        self.logger.info(f"为用户 {user_id} 生成新运势: {fortune_value}")
        
        # 获取对应等级的描述
        fortune_desc = ""
        for (min_val, max_val), desc in self.fortune_levels.items():
            if min_val <= fortune_value <= max_val:
                fortune_desc = desc
                break
        
        # 构建运势消息
        result = f"✨ 今日运势: {fortune_value}\n"
        result += f"💫 运势评价: {fortune_desc}\n"
        
        return result 