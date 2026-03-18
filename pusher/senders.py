"""
消息发送器模块
实现向各个平台推送消息的功能

设计模式：策略模式
- BaseSender：发送器抽象基类
- WeChatSender：企业微信发送器（已完整实现）
- DingTalkSender：钉钉发送器（预留，未实现）
- EmailSender：邮件发送器（预留，未实现）
- QQSender：QQ 发送器（预留，未实现）

SENDERS：发送器注册表，按类型映射到对应的类
"""

from abc import ABC, abstractmethod  # 抽象基类相关
from typing import List, Dict, Any  # 类型注解
import httpx  # HTTP 客户端
from config import settings


class BaseSender(ABC):
    """
    发送器抽象基类

    定义所有发送器必须实现的接口
    """

    sender_type: str = "base"  # 发送器类型标识

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
    """
    企业微信群机器人发送器

    作用：通过企业微信 Webhook 推送消息

    使用前提：
        - 需要在企业微信群聊中添加群机器人
        - 获取 Webhook 地址（包含 key 参数）
        - 配置到 config.py 的 push_targets 中
    """

    sender_type: str = "wechat"  # 发送器类型

    def __init__(self):
        """
        初始化企业微信发送器

        Args:
            webhook_url: 企业微信机器人 Webhook 地址
        """
        self.webhook_url = settings.push_targets[self.sender_type]

    async def send(self, item: Dict[str, Any]) -> bool:
        """
        发送单条消息到企业微信

        作用：将单条新闻格式化为 Markdown 并发送到群聊

        Args:
            item: 新闻数据，包含 title、url、source 字段

        Returns:
            bool: True 表示发送成功，False 表示失败
        """
        # 格式化为微信 Markdown 消息
        payload = self._format_message(item)

        # 设置请求头
        headers = {"User-Agent": "NewsFlow-Pusher/1.0"}

        # 发送 HTTP POST 请求
        async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
            response = await client.post(self.webhook_url, json=payload)
            data = response.json()

            # 企业微信返回 errcode=0 表示成功
            return data.get("errcode") == 0

    async def send_batch(self, items: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        批量发送消息

        作用：遍历所有消息，逐一发送

        Returns:
            Dict: {"success": 成功数, "failed": 失败数}
        """
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
        """
        验证 webhook_url 是否有效

        Returns:
            bool: True 表示格式正确
        """
        return bool(
            self.webhook_url
            and self.webhook_url.startswith("https://qyapi.weixin.qq.com")
        )

    def _format_message(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化为企业微信 Markdown 消息

        作用：将新闻数据转换为企业微信机器人支持的 Markdown 格式

        Args:
            item: 新闻数据字典

        Returns:
            Dict: 企业微信 API 要求的 JSON 结构
        """
        title = item.get("title", "")
        url = item.get("url", "")
        source = item.get("source", "")

        # 构建 Markdown 内容
        content = f"""# {title}
> 来源：{source}
---
[点击查看详情]({url})"""

        # 返回企业微信消息格式
        return {"msgtype": "markdown", "markdown": {"content": content}}


# ==================== 发送器注册表 ====================

# SENDERS：发送器类注册表
# 格式：{"发送器类型": 发送器类}
SENDERS: Dict[str, Any] = {
    "wechat": WeChatSender(),
    # "wechat": senders.WeChatSender("webhook_url"),
    # "dingtalk": DingTalkSender,
    # "email": EmailSender,
    # "qq": QQSender,
}
# SENDERS_KEYS：所有可用发送器的名称列表
# 方便快速获取可用源列表
SENDERS_KEYS: list = list(SENDERS.keys())  # ["wechat", "dingtalk", "email", "qq"]
