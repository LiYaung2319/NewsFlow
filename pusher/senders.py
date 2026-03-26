"""
消息推送模块
实现向各平台推送资讯的功能

设计模式：策略模式
- BaseSender：推送器抽象基类
- WeChatSender：企业微信推送器
- WPSSender：WPS协作推送器
- DingTalkSender：钉钉推送器（预留）
- EmailSender：邮件推送器（预留）
- QQSender：QQ推送器（预留）

SENDERS：推送器注册表，按平台管理配置和实例
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
import os
import httpx


class BaseSender(ABC):
    """推送器抽象基类"""

    platform: str = "base"

    @abstractmethod
    async def send(self, item: str) -> Tuple[bool, Optional[str]]:
        """推送单条消息，返回 (是否成功, 错误信息)"""
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

    async def send(self, item: str) -> Tuple[bool, Optional[str]]:
        """
        推送单条消息

        Args:
            item: Markdown 格式消息

        Returns:
            bool: True 表示推送成功
        """
        payload = {"msgtype": "markdown_v2", "markdown_v2": {"content": item}}
        headers = {"User-Agent": "NewsFlow-Pusher/1.0"}

        try:
            async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
                response = await client.post(self.webhook_url, json=payload)
                data = response.json()

            if data.get("errcode") == 0:
                return True, None
            else:
                return (
                    False,
                    f"errcode={data.get('errcode')}, errmsg={data.get('errmsg')}",
                )
        except Exception as e:
            return False, f"出现意外错误: {e}"

    async def send_batch(self, items: List[str]) -> Dict[str, Any]:
        """
        批量推送消息

        Returns:
            Dict[str, int]: {"success": 成功数, "failed": 失败数, "errors": 错误列表}
        """
        success, failed = 0, 0
        errors = []

        for item in items:
            ok, error = await self.send(item)
            if ok:
                success += 1
            else:
                failed += 1
                if error:
                    errors.append(error)

        return {"success": success, "failed": failed, "errors": errors}

    def validate_config(self) -> bool:
        """验证 Webhook 地址格式"""
        return bool(
            self.webhook_url
            and self.webhook_url.startswith("https://qyapi.weixin.qq.com")
        )


class WPSSender(BaseSender):
    """WPS协作推送器"""

    platform: str = "wps"

    def __init__(self, webhook_url: str):
        """
        初始化WPS协作推送器

        Args:
            webhook_url: WPS协作 Webhook 地址

        """
        self.webhook_url = webhook_url

    async def send(self, item: str) -> Tuple[bool, Optional[str]]:
        """
        推送单条消息

        Args:
            item: Markdown 格式消息

        Returns:
            bool: True 表示推送成功
        """
        payload = {"msgtype": "markdown", "markdown": {"text": item}}
        headers = {
            "User-Agent": "NewsFlow-Pusher/1.0",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
                response = await client.post(self.webhook_url, json=payload)
                data = response.json()

            if data.get("result") == "ok":
                return True, None
            else:
                return (
                    False,
                    f"code={data.get('code')}, msg={data.get('msg')}",
                )
        except Exception as e:
            return False, f"出现意外错误: {e}"

    async def send_batch(self, items: List[str]) -> Dict[str, Any]:
        """
        批量推送消息

        Returns:
            Dict[str, int]: {"success": 成功数, "failed": 失败数, "errors": 错误列表}
        """
        success, failed = 0, 0
        errors = []

        for item in items:
            ok, error = await self.send(item)
            if ok:
                success += 1
            else:
                failed += 1
                if error:
                    errors.append(error)

        return {"success": success, "failed": failed, "errors": errors}

    def validate_config(self) -> bool:
        """验证 webhook_url 格式"""
        return bool(
            self.webhook_url
            and self.webhook_url.startswith("https://xz.wps.cn/api/v1/webhook/send")
        )


# ==================== 推送器注册表 ====================

SENDERS: Dict[str, Dict[str, Any]] = {
    "wechat": {
        "sender": WeChatSender(webhook_url=os.environ.get("WECHAT_WEBHOOK_URL", "")),
        "enabled": bool(os.environ.get("WECHAT_WEBHOOK_URL")),
    },
    "wps": {
        "sender": WPSSender(
            webhook_url=os.environ.get("WPS_WEBHOOK_URL", ""),
        ),
        "enabled": bool(os.environ.get("WPS_WEBHOOK_URL")),
    },
}

SENDERS_KEYS: List[str] = list(SENDERS.keys())
