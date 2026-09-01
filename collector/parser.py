"""
数据解析器模块
负责将网页 HTML 内容解析为结构化的新闻数据

设计模式：策略模式
- 每个新闻源对应一个解析器类
- 所有解析器继承自 BaseParser 抽象基类
- 通过 SOURCES 字典注册和管理所有解析器

解析器列表：
    - SinaParser: 新浪新闻解析器
    - NeteaseParser: 网易新闻解析器
    - TencentParser: 腾讯新闻解析器
    - ArticleParser: 通用文章解析器
"""

from abc import ABC, abstractmethod
import json
from parsel import Selector
from typing import List, Dict, Any
from schemas import ParsedItem
from urllib.parse import urljoin


class BaseParser(ABC):
    """
    解析器抽象基类

    定义所有解析器必须实现的接口：
    - parse_list(): 解析新闻列表页
    - parse_detail(): 解析新闻详情页
    - validate(): 验证解析结果有效性
    """

    source_name: str = "base"  # 数据源标识符，子类需覆盖

    @abstractmethod
    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        """
        解析新闻列表页，提取新闻标题和链接

        Args:
            selector: parsel Selector 对象，包含网页内容

        Returns:
            List[ParsedItem]: 解析出的新闻列表
        """
        pass

    @abstractmethod
    def parse_detail(self, selector: Selector) -> ParsedItem:
        """
        解析新闻详情页，提取完整信息

        Args:
            selector: parsel Selector 对象，包含网页内容

        Returns:
            ParsedItem: 单条新闻数据
        """
        pass

    def validate(self, item: ParsedItem) -> bool:
        """
        验证解析结果的有效性

        作用：过滤掉标题或链接为空的无效数据

        Args:
            item: 待验证的 ParsedItem 对象

        Returns:
            bool: True 表示有效，False 表示无效
        """
        return bool(item.title and item.url)


class SinaParser(BaseParser):
    """
    新浪新闻解析器

    解析规则：
    - 从热点新闻区块提取：div.blk_card > ul.uni-blk-list > li > a
    - 从要闻区块提取：div#blk_yw_01 > h1[data-client="headline"] > a
    """

    source_name: str = "sina"  # 数据源标识

    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        """
        解析新浪新闻首页列表

        XPath 解释：
        - //div[contains(@class, "blk_card")]: 查找包含 blk_card 类的 div
        - //ul[contains(@class, "uni-blk-list") and contains(@class, "list-a")]: 查找包含指定类的 ul
        - /li/a: 获取 li 下的 a 标签
        - @href: 获取 a 标签的 href 属性
        - text(): 获取文本内容
        """
        items = []

        # ==================== 解析热点新闻区块 ====================
        # 获取热点新闻列表
        hot_list = selector.xpath(
            '//div[contains(@class, "blk_card")]//ul[contains(@class, "uni-blk-list") and contains(@class, "list-a")]/li/a'
        )
        for a in hot_list[:10]:  # 只取前10条
            href = a.xpath("@href").get()  # 获取链接
            title = (
                a.xpath("text()").get() or a.xpath("string(.)").get()
            )  # 获取标题，优先 text()，失败用 string()

            # 过滤：必须有 http 链接和标题
            if href and title and href.startswith("http"):
                items.append(
                    ParsedItem(
                        title=title.strip(),
                        url=href,
                        source=self.source_name,  # 去除首尾空白
                    )
                )

        # ==================== 解析要闻区块 ====================
        # 获取要闻 headlines（前5条）
        yaowen_headlines = selector.xpath(
            '//div[@id="blk_yw_01"]//h1[contains(@data-client, "headline")]/a'
        )
        for a in yaowen_headlines[:5]:
            href = a.xpath("@href").get()
            title = a.xpath("text()").get() or a.xpath("string(.)").get()

            if href and title and href.startswith("http"):
                items.append(
                    ParsedItem(title=title.strip(), url=href, source=self.source_name)
                )

        return items

    def parse_detail(self, selector: Selector) -> ParsedItem:
        """
        解析新浪新闻详情页

        """
        pass


class NeteaseParser(BaseParser):
    """
    网易新闻解析器

    解析规则：
    从 news_df_yw 或 ns_area 区块提取链接
    """

    source_name: str = "163"

    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        items = []

        # 查找 news_df_yw 区块
        containers = selector.xpath('//div[contains(@class, "news_df_yw")]')

        # 遍历每个容器，提取链接
        for container in containers:
            all_links = container.xpath(
                './/div[contains(@class, "mod_guidance_news") or contains(@class, "clearfix")]//a[@href]'
            )  # . 表示在当前容器内查找
            for a in all_links:
                href = a.xpath("@href").get()
                title = a.xpath("string(.)").get()  # string() 获取节点的全部文本

                if href and title and href.startswith("http"):
                    title = title.strip()
                    if title:  # 再次确认标题不为空
                        items.append(ParsedItem(title=title, url=href, source="163"))

        return items

    def parse_detail(self, selector: Selector) -> ParsedItem:
        """
        解析网易新闻详情页
        """
        pass


class TencentParser(BaseParser):
    """
    腾讯新闻解析器

    解析规则：
    1. 从 div.BW8UAt3nyAHToseflkyM channel-command 下的 top-article 和 command-content-row 提取要闻标题和链接
    2. 从 div.swiper-wrapper 下的每个 article-base-info 提取热点精选标题和链接
    """

    source_name: str = "tencent"

    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        """
        解析腾讯新闻首页列表

        提取内容：
        1. channel-command 区块：
           - .top-article 下的所有链接
           - .command-content-row 下的所有链接
        2. swiper-wrapper 区块：
           - 每个 article-base-info 中的链接和标题

        返回：
        List[ParsedItem]: 解析出的新闻列表
        """
        items = []
        seen_urls = set()

        command_container = selector.xpath(
            '//div[contains(@class, "BW8UAt3nyAHToseflkyM") and contains(@class, "channel-command")]'
        )
        swiper_container = selector.xpath('//div[contains(@class, "swiper-wrapper")]')

        for a in command_container.xpath(
            './/a[@href and contains(@class, "link-item")]'
        ):
            href = a.xpath("@href").get()
            if href and href.startswith("http") and href not in seen_urls:
                title = a.xpath("string(.)").get()
                if title:
                    title = title.strip()
                    if title and len(title) > 0:
                        items.append(
                            ParsedItem(title=title, url=href, source=self.source_name)
                        )
                        seen_urls.add(href)

        for a in swiper_container.xpath('.//a[contains(@class, "article-base-info")]'):
            href = a.xpath("@href").get()
            if href and href.startswith("http") and href not in seen_urls:
                title_span = a.xpath('.//span[contains(@class, "article-title-text")]')
                if title_span:
                    title = title_span.xpath("string(.)").get()
                    if title:
                        title = title.strip()
                        if title and len(title) > 0:
                            items.append(
                                ParsedItem(
                                    title=title, url=href, source=self.source_name
                                )
                            )
                            seen_urls.add(href)

        return items

    def parse_detail(self, selector: Selector) -> ParsedItem:
        """解析腾讯新闻详情页"""
        pass


class AihotParser(BaseParser):
    """AIHOT 新闻解析器，支持热点榜和 AI 日报两个板块"""

    source_name: str = "aihot"

    def __init__(self, section: str):
        self.section = section
        self.source_name = f"aihot_{section}"

    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        """解析指定板块的标题和链接"""
        if self.section == "hot":
            links = selector.xpath(
                "//section[@aria-labelledby='hot-day-title']"
                "//a[contains(concat(' ', normalize-space(@class), ' '), ' hot-rank-link ')"
                " and starts-with(@href, '/story/')][@href]"
            )
        elif self.section == "daily":
            links = selector.xpath(
                "//div[contains(concat(' ', normalize-space(@class), ' '), ' daily-report-page ')]"
                "//article[contains(concat(' ', normalize-space(@class), ' '), ' daily-paper ')"
                " and contains(concat(' ', normalize-space(@class), ' '), ' daily-report ')]"
                "//div[contains(concat(' ', normalize-space(@class), ' '), ' daily-section-articles ')]"
                "//article[contains(concat(' ', normalize-space(@class), ' '), ' daily-article ')]"
                "//h3[contains(concat(' ', normalize-space(@class), ' '), ' daily-article-title ')]"
                "//a[starts-with(@href, '/items/')][@href]"
            )
        else:
            return []

        items = []
        seen_urls = set()
        for link in links:
            relative_url = link.xpath("@href").get()
            title = link.xpath("normalize-space(string(.))").get()
            if not relative_url or not title:
                continue

            url = urljoin("https://aihot.virxact.com/", relative_url)
            if url in seen_urls:
                continue

            items.append(
                ParsedItem(title=title, url=url, source=self.source_name)
            )
            seen_urls.add(url)

        return items

    def parse_detail(self, selector: Selector) -> ParsedItem:
        """AIHOT 详情页解析预留接口"""
        pass


class CsdnParser(BaseParser):
    """CSDN 首页资讯及分类内容解析器"""

    source_name: str = "CSDN"

    def __init__(self, section: str):
        self.section = section
        self.source_name = f"CSDN_{section}"

    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        """解析 CSDN 指定板块的新闻列表"""
        if self.section == "all":
            return self._parse_homepage(selector)

        return self._parse_api_response(selector)

    def _parse_homepage(self, selector: Selector) -> List[ParsedItem]:
        items = []
        seen_urls = set()

        links = selector.xpath(
            "//div[@id='home-content-box']//div[contains(@class, 'home-info-banner')]"
            "//a[contains(@class, 'banner-box')]"
        )
        links += selector.xpath(
            "//div[@id='home-content-box']//div[contains(@class, 'home-info-headlines')]"
            "//a[@href]"
        )

        for link in links:
            url = link.xpath("@href").get()
            title = link.xpath(
                "normalize-space(string(.//p//span | .//span[contains(@class, 'text')]))"
            ).get()
            if not url or not title or url in seen_urls:
                continue

            items.append(ParsedItem(title=title, url=url, source=self.source_name))
            seen_urls.add(url)

        return items

    def _parse_api_response(self, selector: Selector) -> List[ParsedItem]:
        response_text = selector.xpath("//pre/text()").get()
        if not response_text:
            response_text = selector.xpath("string(//body)").get()
        if not response_text:
            response_text = selector.xpath("string(.)").get()

        payload = json.loads(response_text.strip())
        component_data = payload["data"]["silkroad-pre-home-list"]
        entries = component_data.get("info", [])[:10]

        items = []
        seen_urls = set()
        for entry in entries:
            article = entry.get("extend", {})
            title = article.get("title", "").strip()
            url = article.get("url", "").strip()
            if not title or not url or url in seen_urls:
                continue

            items.append(ParsedItem(title=title, url=url, source=self.source_name))
            seen_urls.add(url)

        return items

    def parse_detail(self, selector: Selector) -> ParsedItem:
        """CSDN 详情页解析预留接口"""
        pass


class ArticleParser(BaseParser):
    """
    通用文章解析器

    作用：作为后备解析器，从任意网页提取链接
    """

    source_name: str = "article"

    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        """
        通用解析：提取页面中所有链接

        特点：不做任何过滤，返回所有 http 链接
        """
        urls = selector.xpath("//a[@href]/@href").getall()

        items = []
        for url in urls:
            if url.startswith("http"):
                items.append(ParsedItem(title="", url=url, source="article"))

        return items

    def parse_detail(self, selector: Selector) -> ParsedItem:
        """通用解析详情页"""
        title = selector.xpath("//h1//text()").get("") or selector.xpath(
            "//title/text()"
        ).get("")

        return ParsedItem(
            title=title.strip() if title else "",
            url="",
            source="article",
        )


# ==================== 解析器注册表 ====================

# SOURCES：数据源配置字典
# 格式：{"源名称": {"parser": 解析器类, "home_url": 主页URL}}
# 复合信息源可使用 sections 配置多个实际访问页面
SOURCES: Dict[str, Dict[str, Any]] = {
    "sina": {
        "parser": SinaParser(),
        "home_url": "https://news.sina.com.cn/",  # 新浪新闻主页
    },
    "163": {
        "parser": NeteaseParser(),
        "home_url": "https://www.163.com/",  # 网易首页（包含新闻）
    },
    "tencent": {
        "parser": TencentParser(),
        "home_url": "https://news.qq.com/",  # 腾讯新闻主页
    },
    "aihot": {
        "sections": {
            "aihot_hot": {
                "parser": AihotParser(section="hot"),
                "home_url": "https://aihot.virxact.com/hot",
            },
            "aihot_daily": {
                "parser": AihotParser(section="daily"),
                "home_url": "https://aihot.virxact.com/daily",
            },
        },
    },
    "CSDN": {
        "sections": {
            "CSDN_all": {
                "parser": CsdnParser(section="all"),
                "home_url": "https://www.csdn.net/",
            },
            "CSDN_ai": {
                "parser": CsdnParser(section="ai"),
                "home_url": "https://cms-api.csdn.net/v1/web_home/select_content?componentIds=silkroad-pre-home-list&cate1=ai",
            },
            "CSDN_python": {
                "parser": CsdnParser(section="python"),
                "home_url": "https://cms-api.csdn.net/v1/web_home/select_content?componentIds=silkroad-pre-home-list&cate1=python",
            },
        },
    },
}

# SOURCES_KEYS：所有可用数据源的名称列表
# 方便快速获取可用源列表
SOURCES_KEYS: List[str] = list(SOURCES.keys())  # ["sina", "163", "tencent", "aihot"]
