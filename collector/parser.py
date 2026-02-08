from abc import ABC, abstractmethod
from parsel import Selector
from typing import List, Dict, Any
from .protocol import ParsedItem


class BaseParser(ABC):
    source_name: str = "base"

    @abstractmethod
    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        pass

    @abstractmethod
    def parse_detail(self, selector: Selector) -> ParsedItem:
        pass

    def validate(self, item: ParsedItem) -> bool:
        return bool(item.title and item.url)


class SinaParser(BaseParser):
    source_name: str = "sina"

    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        items = []

        hot_list = selector.xpath('//div[contains(@class, "blk_card")]//ul[contains(@class, "uni-blk-list") and contains(@class, "list-a")]/li/a')
        for a in hot_list[:10]:
            href = a.xpath('@href').get()
            title = a.xpath('text()').get() or a.xpath('string(.)').get()
            if href and title and href.startswith("http"):
                items.append(ParsedItem(
                    title=title.strip(),
                    url=href,
                    source="sina"
                ))

        yaowen_headlines = selector.xpath('//div[@id="blk_yw_01"]//h1[contains(@data-client, "headline")]/a')
        for a in yaowen_headlines[:5]:
            href = a.xpath('@href').get()
            title = a.xpath('text()').get() or a.xpath('string(.)').get()
            if href and title and href.startswith("http"):
                items.append(ParsedItem(
                    title=title.strip(),
                    url=href,
                    source="sina"
                ))

        return items

    def parse_detail(self, selector: Selector) -> ParsedItem:
        title = selector.xpath('//h1//text()').get("") or selector.xpath('//title/text()').get("")
        return ParsedItem(
            title=title.strip() if title else "",
            url="",
            source=self.source_name,
        )


class NeteaseParser(BaseParser):
    source_name: str = "163"

    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        news_list = selector.xpath('//div[@class="news_list"]//a[@href]/@href').getall()
        items = []
        for url in news_list:
            if url.startswith("http"):
                items.append(ParsedItem(title="", url=url, source="163"))
        return items

    def parse_detail(self, selector: Selector) -> ParsedItem:
        title = selector.xpath('//h1[@class="headline"]/text()').get("") or selector.xpath('//h1/text()').get("")
        return ParsedItem(
            title=title.strip() if title else "",
            url="",
            source=self.source_name,
        )


class TencentParser(BaseParser):
    source_name: str = "tencent"

    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        news_list = selector.xpath('//div[@class="list"]//a[@href]/@href').getall()
        items = []
        for url in news_list:
            if url.startswith("http"):
                items.append(ParsedItem(title="", url=url, source="tencent"))
        return items

    def parse_detail(self, selector: Selector) -> ParsedItem:
        title = selector.xpath('//h1[@class="article-title"]/text()').get("") or selector.xpath('//h1/text()').get("")
        return ParsedItem(
            title=title.strip() if title else "",
            url="",
            source=self.source_name,
        )


class ArticleParser(BaseParser):
    source_name: str = "article"

    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        urls = selector.xpath("//a[@href]/@href").getall()
        items = []
        for url in urls:
            if url.startswith("http"):
                items.append(ParsedItem(title="", url=url, source="article"))
        return items

    def parse_detail(self, selector: Selector) -> ParsedItem:
        title = selector.xpath("//h1//text()").get("") or selector.xpath("//title/text()").get("")
        return ParsedItem(
            title=title.strip() if title else "",
            url="",
            source="article",
        )


PARSERS: Dict[str, type] = {
    "sina": SinaParser,
    "163": NeteaseParser,
    "tencent": TencentParser,
    "article": ArticleParser,
}


SOURCES: Dict[str, Dict[str, Any]] = {
    "sina": {
        "parser": SinaParser,
        "home_url": "https://news.sina.com.cn/",
    },
    "163": {
        "parser": NeteaseParser,
        "home_url": "https://www.163.com/news/",
    },
    "tencent": {
        "parser": TencentParser,
        "home_url": "https://news.qq.com/",
    },
}


SOURCES_KEYS: list = list(SOURCES.keys())
