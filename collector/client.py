import asyncio
import httpx
from typing import Optional, Dict, Any, List
from parsel import Selector
from config import settings


class CollectorClient:
    def __init__(
        self,
        timeout: Optional[float] = None,
        follow_redirects: bool = True,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.timeout = timeout or settings.timeout
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=follow_redirects,
            headers=headers or self._default_headers(),
        )

    def _default_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    async def get(self, url: str, **kwargs) -> Selector:
        response = await self.client.get(url, **kwargs)
        response.raise_for_status()
        return Selector(text=response.text)

    async def get_batch(
        self, urls: List[str], concurrency: Optional[int] = None
    ) -> List[Selector]:
        concurrency = concurrency or settings.max_concurrency
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_limit(url: str) -> Selector:
            async with semaphore:
                return await self.get(url)

        selectors = await asyncio.gather(*[fetch_with_limit(url) for url in urls])
        return selectors

    async def post(self, url: str, **kwargs) -> Selector:
        response = await self.client.post(url, **kwargs)
        response.raise_for_status()
        return Selector(text=response.text)

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
