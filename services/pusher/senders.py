from abc import ABC, abstractmethod
from typing import List, Dict, Any
import httpx


class BaseSender(ABC):
    """推送发送器抽象基类"""
    
    sender_type: str = "base"
    
    @abstractmethod
    async def send(self, item: Dict[str, Any]) -> bool:
        """发送单条消息"""
        pass
    
    @abstractmethod
    async def send_batch(self, items: List[Dict[str, Any]]) -> Dict[str, int]:
        """批量发送消息"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """验证配置是否有效"""
        pass


class WeChatSender(BaseSender):
    """企业微信群机器人发送器"""
    sender_type: str = "wechat"
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send(self, item: Dict[str, Any]) -> bool:
        """发送单条消息到微信"""
        payload = self._format_message(item)
        headers = {"User-Agent": "NewsFlow-Pusher/1.0"}
        async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
            response = await client.post(self.webhook_url, json=payload)
            data = response.json()
            return data.get("errcode") == 0
    
    async def send_batch(self, items: List[Dict[str, Any]]) -> Dict[str, int]:
        """批量发送"""
        success, failed = 0, 0
        for item in items:
            try:
                if await self.send(item):
                    success += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
        return {"success": success, "failed": failed}
    
    def validate_config(self) -> bool:
        """验证 webhook_url 是否有效"""
        return bool(self.webhook_url and self.webhook_url.startswith("https://qyapi.weixin.qq.com"))
    
    def _format_message(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """格式化为微信 Markdown 消息"""
        title = item.get("title", "")
        url = item.get("url", "")
        source = item.get("source", "")
        
        content = f"""# {title}
> 来源：{source}
---
[点击查看详情]({url})"""
        
        return {
            "msgtype": "markdown",
            "markdown": {"content": content}
        }


class DingTalkSender(BaseSender):
    sender_type: str = "dingtalk"
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send(self, item: Dict[str, Any]) -> bool:
        return False
    
    async def send_batch(self, items: List[Dict[str, Any]]) -> Dict[str, int]:
        return {"success": 0, "failed": len(items)}
    
    def validate_config(self) -> bool:
        return False


class EmailSender(BaseSender):
    sender_type: str = "email"
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send(self, item: Dict[str, Any]) -> bool:
        return False
    
    async def send_batch(self, items: List[Dict[str, Any]]) -> Dict[str, int]:
        return {"success": 0, "failed": len(items)}
    
    def validate_config(self) -> bool:
        return False


class QQSender(BaseSender):
    sender_type: str = "qq"
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send(self, item: Dict[str, Any]) -> bool:
        return False
    
    async def send_batch(self, items: List[Dict[str, Any]]) -> Dict[str, int]:
        return {"success": 0, "failed": len(items)}
    
    def validate_config(self) -> bool:
        return False


SENDERS: Dict[str, type] = {
    "wechat": WeChatSender,
    "dingtalk": DingTalkSender,
    "email": EmailSender,
    "qq": QQSender,
}
