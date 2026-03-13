"""
HTTP 客户端模块
负责发起异步 HTTP 请求，获取网页内容

核心类：
CollectorClient: 异步 HTTP 客户端，支持单次请求和批量并发请求

特点：
- 使用 httpx 实现异步 HTTP 请求
- 支持并发数量控制（通过信号量）
- 自动处理重定向
- 默认模拟 Chrome 浏览器请求头
"""

import asyncio
import httpx
from typing import Optional, Dict, Any, List
from parsel import Selector
from config import settings


class CollectorClient:
    """
    新闻采集客户端

    职责：
    1. 发送 HTTP GET/POST 请求获取网页
    2. 控制并发请求数量，避免被目标网站封禁
    3. 自动处理请求头和超时

    使用示例：
    async with CollectorClient() as client:
        selector = await client.get("https://news.sina.com.cn/")
        # 处理网页内容...
    """

    def __init__(
        self,
        timeout: Optional[float] = None,
        follow_redirects: bool = True,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        初始化客户端

        参数：
        - timeout: 自定义超时时间（秒），覆盖配置默认值
        - follow_redirects: 是否自动跟随 3xx 重定向
        - headers: 自定义 HTTP 请求头，None 则使用默认头
        """
        self.timeout = timeout or settings.timeout
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=follow_redirects,
            headers=headers or self._default_headers(),
        )

    def _default_headers(self) -> Dict[str, str]:
        """
        获取默认的 HTTP 请求头

        作用：模拟真实浏览器访问，避免被网站识别为爬虫

        返回：
        Dict[str, str]: 请求头字典
        """
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    async def get(self, url: str, **kwargs) -> Selector:
        """
        发起 HTTP GET 请求

        作用：获取单个网页的内容

        参数：
        - url: 请求的 URL 地址
        - **kwargs: 传递给 httpx.get 的其他参数

        返回：
        Selector: parsel Selector 对象，可用于 XPath 解析

        异常：
        httpx.HTTPStatusError: 请求返回非 2xx 状态码时抛出
        """
        response = await self.client.get(url, **kwargs)
        response.raise_for_status()
        return Selector(text=response.text)

    async def get_batch(
        self,
        urls: List[str],
        concurrency: Optional[int] = None,
    ) -> List[Selector]:
        """
        批量并发获取多个网页

        作用：通过信号量控制并发数量，同时请求多个 URL

        原理：
        - 使用 asyncio.Semaphore 创建信号量，限制同时进行的协程数量
        - 使用 asyncio.gather 并发执行所有请求

        参数：
        - urls: 要请求的 URL 列表
        - concurrency: 最大并发请求数，默认使用 settings.max_concurrency

        返回：
        List[Selector]: Selector 对象列表，与输入 URL 顺序对应
        """
        concurrency = concurrency or settings.max_concurrency
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_limit(url: str) -> Selector:
            """在信号量控制下获取单个网页"""
            async with semaphore:
                return await self.get(url)

        selectors = await asyncio.gather(*[fetch_with_limit(url) for url in urls])
        return selectors

    async def post(self, url: str, **kwargs) -> Selector:
        """
        发起 HTTP POST 请求

        作用：发送 POST 请求并返回 Selector 对象

        参数：
        - url: 请求的 URL 地址
        - **kwargs: 传递给 httpx.post 的其他参数

        返回：
        Selector: parsel Selector 对象
        """
        response = await self.client.post(url, **kwargs)
        response.raise_for_status()
        return Selector(text=response.text)

    async def close(self):
        """
        关闭客户端连接

        作用：关闭底层 HTTP 连接，释放资源
        """
        await self.client.aclose()

    async def __aenter__(self):
        """进入上下文时返回自身"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时自动关闭连接"""
        await self.close()
