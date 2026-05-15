"""富回复对象 - 插件 handle() 可返回此对象, event_handler 统一渲染发送。

设计:
- 与 str 返回值并存, 兼容旧插件
- 字段互斥处理: media_file_info 设置时 msg_type=7; 否则 markdown 优先(msg_type=2); 否则 text(msg_type=0)
- keyboard 可与 markdown 组合(QQ API 支持), 但与 text/media 单独发时会被忽略
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class Reply:
    text: str = ""
    markdown: str = ""
    keyboard: Optional[Dict[str, Any]] = None  # 完整 keyboard payload (含 content.rows)
    media_file_info: Optional[str] = None  # 富媒体 file_info (来自 upload_image 上传响应)

    def is_empty(self) -> bool:
        return not (self.text or self.markdown or self.media_file_info)

    def to_payload(self, *, message_id: Optional[str] = None,
                   event_id: Optional[str] = None,
                   msg_seq: int = 1) -> Dict[str, Any]:
        """渲染为 QQ V2 群/单聊 messages 接口请求体。"""
        # 1) 富媒体优先 (msg_type=7)
        if self.media_file_info:
            data: Dict[str, Any] = {
                "msg_type": 7,
                "content": self.text or "",
                "media": {"file_info": self.media_file_info},
            }
        # 2) markdown (msg_type=2)
        elif self.markdown:
            data = {
                "msg_type": 2,
                "content": " ",
                "markdown": {"content": self.markdown},
            }
            if self.keyboard:
                data["keyboard"] = self.keyboard
        # 3) 纯文本 (msg_type=0)
        else:
            data = {
                "msg_type": 0,
                "content": self.text or "",
            }

        if message_id:
            data["msg_id"] = message_id
            data["msg_seq"] = msg_seq
        elif event_id:
            # msg_id 优先于 event_id (常规消息回复用 msg_id, 按钮回调等无 msg_id 时才用 event_id)
            data["event_id"] = event_id
        return data
