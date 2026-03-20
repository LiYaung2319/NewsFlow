"""BrowserClient: 基于 Playwright 的异步浏览器客户端

复用浏览器实例，支持获取 JavaScript 渲染后的完整 DOM:
- 支持单个 URL 获取 (get) 和批量并发获取 (get_batch)
- 自动等待页面加载和网络空闲
- 支持无头模式、等待策略、超时配置
"""

import asyncio
from typing import Dict, Optional, List
from parsel import Selector
from playwright.async_api import async_playwright
from config import settings


class BrowserClient:
    """异步浏览器客户端，复用浏览器实例获取渲染后的网页 DOM"""

    def __init__(
        self,
        headless: Optional[bool] = None,
        timeout: Optional[float] = None,
        wait_until: Optional[str] = None,
        wait_time: Optional[int] = None,
    ):
        """
        初始化浏览器客户端

        Args:
            headless: 无头模式（不显示浏览器窗口），默认使用配置
            timeout: 超时时间（秒），默认使用配置
            wait_until: 等待策略（load/domcontentloaded/networkidle），默认使用配置
            wait_time: 额外等待时间（毫秒），等待动态内容，默认使用配置
        """
        self.headless = headless if headless is not None else settings.browser_headless
        self.timeout = timeout or settings.browser_timeout
        self.wait_until = wait_until or settings.browser_wait_until
        self.wait_time = (
            wait_time if wait_time is not None else settings.browser_wait_time
        )
        self._playwright = None
        self._browser = None
        self._context = None

    async def _start(self):
        """
        启动浏览器实例（惰性加载）

        原理：使用惰性初始化，首次调用时才启动浏览器，避免不必要的资源占用
        """
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        if self._browser is None:
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless
            )
        if self._context is None:
            self._context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )

    async def get(self, url: str) -> Selector:
        """
        访问 URL，返回渲染后的 HTML（Selector 对象）

        流程：
        1. 启动浏览器实例（惰性加载）
        2. 创建新页面
        3. 访问 URL 并等待页面加载
        4. 可选：额外等待动态内容
        5. 获取完整 HTML 并返回 Selector 对象

        Args:
            url: 请求的 URL 地址

        Returns:
            Selector: parsel Selector 对象，包含完整渲染后的 HTML
        """
        await self._start()
        page = await self._context.new_page()

        try:
            await page.goto(
                url,
                wait_until=self.wait_until,
                timeout=self.timeout * 1000,  # 转换为毫秒
            )

            if self.wait_time > 0:
                await asyncio.sleep(self.wait_time)

            html_content = await page.content()
            return Selector(text=html_content)
        finally:
            await page.close()

    async def get_batch(
        self,
        source_urls: Dict[str, str],
        concurrency: Optional[int] = None,
    ) -> tuple[Dict[str, Selector], List[str]]:
        """
        批量并发获取多个网页

        原理：
        - 使用信号量控制并发数，避免过多页面导致资源耗尽
        - 使用 asyncio.gather 并发执行所有请求
        - 每个协程内部捕获异常，单源失败不影响其他源

        Args:
            source_urls: 数据源字典，格式为 {数据源名称: URL}
            concurrency: 最大并发页数，默认使用 settings.max_concurrency

        Returns:
            Tuple[Dict[str, Selector], List[str]]:
                - selectors: 结果字典，格式为 {数据源名称: Selector}
                - errors: 错误信息列表
        """
        concurrency = concurrency or settings.max_concurrency
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_limit(
            source: str, url: str
        ) -> tuple[str, Optional[Selector], Optional[str]]:
            async with semaphore:
                try:
                    selector = await self.get(url)
                    return source, selector, None
                except Exception as e:
                    return source, None, str(e)

        results = await asyncio.gather(
            *(fetch_with_limit(k, url) for k, url in source_urls.items())
        )

        selectors = {}
        errors = []
        for source, selector, error in results:
            if error:
                errors.append(f"{source} 采集失败: {error}")
            else:
                selectors[source] = selector

        return selectors, errors

    async def close(self):
        """
        关闭浏览器实例，释放资源

        关闭顺序：context -> browser -> playwright
        """
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def __aenter__(self):
        """进入上下文时返回自身"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时自动关闭浏览器"""
        await self.close()
