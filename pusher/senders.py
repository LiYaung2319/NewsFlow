"""
消息推送模块
实现向各平台推送资讯的功能

设计模式：策略模式
- BaseSender：推送器抽象基类
- WeChatSender：企业微信推送器
- DingTalkSender：钉钉推送器（预留）
- EmailSender：邮件推送器（预留）
- QQSender：QQ推送器（预留）

SENDERS：推送器注册表，按平台管理配置和实例
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
import os
import httpx


class BaseSender(ABC):
    """推送器抽象基类"""

    platform: str = "base"

    @abstractmethod
    async def send(self, item: str) -> bool:
        """推送单条消息"""
        pass

    @abstractmethod
    async def send_batch(self, items: List[str]) -> Dict[str, int]:
        """批量推送消息"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """验证配置有效性"""
        pass


class WeChatSender(BaseSender):
    """企业微信推送器"""

    platform: str = "wechat"

    def __init__(self, webhook_url: str):
        """
        初始化企业微信推送器

        Args:
            webhook_url: 企业微信 Webhook 地址
        """
        self.webhook_url = webhook_url

    async def send(self, item: str) -> bool:
        """
        推送单条消息

        Args:
            item: Markdown 格式消息

        Returns:
            bool: True 表示推送成功
        """
        payload = {"msgtype": "markdown_v2", "markdown_v2": {"content": item}}
        headers = {"User-Agent": "NewsFlow-Pusher/1.0"}

        async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
            response = await client.post(self.webhook_url, json=payload)
            data = response.json()

        return data.get("errcode") == 0

    async def send_batch(self, items: List[str]) -> Dict[str, int]:
        """
        批量推送消息

        Returns:
            Dict[str, int]: {"success": 成功数, "failed": 失败数}
        """
        success, failed = 0, 0

        for item in items:
            try:
                if await self.send(item):
                    success += 1
                else:
                    failed += 1
            except httpx.RequestError:
                failed += 1

        return {"success": success, "failed": failed}

    def validate_config(self) -> bool:
        """验证 Webhook 地址格式"""
        return bool(
            self.webhook_url
            and self.webhook_url.startswith("https://qyapi.weixin.qq.com")
        )


# ==================== 推送器注册表 ====================

SENDERS: Dict[str, Dict[str, Any]] = {
    "wechat": {
        "sender": WeChatSender(webhook_url=os.environ.get("WECHAT_WEBHOOK_URL", "")),
        "enabled": bool(os.environ.get("WECHAT_WEBHOOK_URL")),
    },
}

SENDERS_KEYS: List[str] = list(SENDERS.keys())
