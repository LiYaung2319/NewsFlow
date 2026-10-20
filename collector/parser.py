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
import re
from parsel import Selector
from typing import List, Dict, Any
from schemas import ParsedItem, JobItem
from urllib.parse import urljoin, urlparse, urlunparse


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
                "//div[contains(concat(' ', normalize-space(@class), ' '), ' hot-page ')]"
                "//a[contains(concat(' ', normalize-space(@class), ' '), ' hot-rank-link ')"
                " and starts-with(@href, '/story/')][@href]"
            )
            if not links:
                links = selector.xpath(
                    "//section[@aria-labelledby='hot-day-title']"
                    "//a[contains(concat(' ', normalize-space(@class), ' '), ' hot-rank-link ')"
                    " and starts-with(@href, '/story/')][@href]"
                )
        elif self.section == "daily":
            links = selector.xpath(
                "//div[contains(concat(' ', normalize-space(@class), ' '), ' daily-report-page ')]"
                "//*[contains(concat(' ', normalize-space(@class), ' '), ' report-story-title ')]"
                "//a[starts-with(@href, '/items/')][@href]"
            )
            if not links:
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
        if payload.get("success") is False or payload.get("code") not in (None, 0, 200, "0", "200"):
            raise ValueError(
                f"上游接口错误: code={payload.get('code')}, "
                f"message={payload.get('message') or payload.get('msg')}"
            )

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


class AgentArenaParser(BaseParser):
    """Agent Arena Overall 榜单解析器。"""

    source_name: str = "AgentArena"
    leaderboard_url: str = "https://arena.ai/leaderboard/agent/overall"
    max_rank: int = 50

    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        """提取 Overall 榜单前 50 名，允许不同条目共享 URL。"""
        rows = selector.xpath("//table//tbody/tr")
        if not rows:
            rows = selector.xpath("//*[@role='row'][.//*[@role='cell']]")
        if not rows:
            rows = selector.xpath("//tr[td]")

        items = []
        seen_ranks = set()
        for row in rows:
            rank = self._extract_rank(row)
            if rank is None or rank < 1 or rank > self.max_rank or rank in seen_ranks:
                continue

            title, url = self._extract_model(row)
            if not title:
                continue

            items.append(
                ParsedItem(
                    title=title,
                    url=url or self.leaderboard_url,
                    source=self.source_name,
                    rank=rank,
                )
            )
            seen_ranks.add(rank)

        return sorted(items, key=lambda item: item.rank or 0)

    @staticmethod
    def _extract_rank(row) -> int:
        cells = row.xpath("./td | .//*[@role='cell']")
        if cells:
            for value in cells[0].xpath(".//text()").getall():
                value = value.strip()
                if value.isdigit():
                    return int(value)

        candidates = [
            cell.xpath("normalize-space(string(.))").get("") for cell in cells
        ]
        for value in candidates:
            match = re.match(r"^(\d{1,3})(?:\s|$)", value)
            if match:
                return int(match.group(1))

        row_text = row.xpath("normalize-space(string(.))").get("")
        match = re.match(r"^(\d{1,3})(?:\s|$)", row_text)
        return int(match.group(1)) if match else None

    def _extract_model(self, row):
        model_titles = row.xpath("./td[2]//span[@title]/@title")
        if not model_titles:
            model_titles = row.xpath(
                ".//*[@role='cell'][2]//span[@title]/@title"
            )

        links = row.xpath(".//a[@href]")
        for link in links:
            title = link.xpath(".//span[@title]/@title").get() or link.xpath(
                "normalize-space(string(.))"
            ).get("")
            href = link.xpath("@href").get("")
            parsed = urlparse(href)
            if title and href and not (
                parsed.netloc == "arena.ai" or href.startswith("/leaderboard")
            ):
                return title, urljoin(self.leaderboard_url, href)

        if model_titles:
            return model_titles[0].get().strip(), ""

        cells = row.xpath("./td | .//*[@role='cell']")
        if len(cells) >= 3:
            model_title = cells[2].xpath("normalize-space(string(.))").get("")
            if model_title and len(model_title) <= 120:
                return model_title, ""

        for cell in cells:
            title = cell.xpath("normalize-space(string(.))").get("")
            if title and not re.fullmatch(r"[\d,.%$±/\s-]+", title):
                if len(title) <= 120 and not any(
                    marker in title
                    for marker in ("Proprietary", "Apache", "MIT", "License")
                ):
                    return title, ""

        return "", ""

    def parse_detail(self, selector: Selector) -> ParsedItem:
        """Agent Arena 详情页解析预留接口"""
        pass


class EverythingSkillParser(BaseParser):
    """EverythingSkill 热榜和新榜解析器。"""

    source_name: str = "EverythingSkill"
    base_url: str = "https://everythingskill.net/"
    max_rank: int = 30

    def __init__(self, section: str):
        self.section = section
        self.source_name = f"EverythingSkill_{section}"

    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        """提取榜单前 30 名的排名、标题、简介和详情链接。"""
        rows = selector.xpath(
            "//a[starts-with(@href, '/zh/skills/') and "
            "contains(concat(' ', normalize-space(@class), ' '), ' group ')]"
        )
        items = []
        seen_urls = set()
        for row in rows:
            rank_text = row.xpath("./div[1]//span[1]/text()").get("").strip()
            match = re.match(r"^(\d+)$", rank_text)
            rank = int(match.group(1)) if match else None
            if rank is None or rank < 1 or rank > self.max_rank:
                continue

            title = row.xpath(
                ".//span[contains(@class, 'text-[15px]')][1]/text()"
            ).get("").strip()
            summary = row.xpath(
                ".//p[contains(@class, 'text-[13px]')][1]/text()"
            ).get("").strip()
            relative_url = row.xpath("@href").get("").strip()
            url = urljoin(self.base_url, relative_url)
            if not title or not relative_url or url in seen_urls:
                continue

            display_title = f"{title}（{summary}）" if summary else title
            items.append(
                ParsedItem(
                    title=display_title,
                    url=url,
                    source=self.source_name,
                    rank=rank,
                )
            )
            seen_urls.add(url)

        return sorted(items, key=lambda item: item.rank or 0)

    def parse_detail(self, selector: Selector) -> ParsedItem:
        """EverythingSkill 详情页解析预留接口。"""
        pass


class JobAccessError(RuntimeError):
    """登录、验证、限流等访问限制；采集器必须停止而非重试。"""

    def __init__(self, message, retry_after=0):
        super().__init__(message)
        self.retry_after = retry_after


def _job_text(value):
    return str(value).strip() if value is not None and str(value).strip() else None


def _job_url(value, domain):
    if not isinstance(value, str) or not value.strip():
        return ""
    parsed = urlparse(urljoin(f"https://www.{domain}/", value.strip()))
    host = parsed.hostname or ""
    if parsed.scheme not in ("http", "https") or not (host == domain or host.endswith("." + domain)):
        return ""
    if parsed.username or parsed.password:
        return ""
    # These list responses use stable job IDs in the path; query fields are tracking data.
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


class BaseJobParser(BaseParser):
    """解析浏览器实际收到的列表 JSON，不发送网络请求。"""

    required_fields = ("title", "company", "city", "salary_text", "education", "text", "published_at", "url")

    def parse_list(self, selector: Selector) -> List[ParsedItem]:
        if selector.type != "json":
            raise ValueError("招聘源需要列表 JSON，不能将登录页或普通 HTML 当作岗位列表")
        return self.parse_payload(selector.root)

    def parse_detail(self, selector: Selector) -> ParsedItem:
        raise NotImplementedError("招聘源只采集列表及列表响应已有的描述")

    def parse_payload(self, payload) -> List[JobItem]:
        records, _, _ = self.page_data(payload)
        items = []
        for record in records:
            if not isinstance(record, dict):
                continue
            item = self.make_item(record)
            if not self.validate(item) or not item.job_id:
                continue
            item.missing_fields = [key for key in self.required_fields if not getattr(item, key)]
            items.append(item)
        return items

    @staticmethod
    def check_message(payload):
        if not isinstance(payload, dict):
            raise ValueError("招聘列表响应不是 JSON 对象")
        message = str(payload.get("message") or payload.get("msg") or "")
        if any(word in message.lower() for word in ("验证", "频繁", "登录", "访问受限", "captcha", "login", "forbidden")):
            raise JobAccessError("上游要求登录/验证或限制访问")


class ZhaopinParser(BaseJobParser):
    source_name = "zhaopin"

    def page_data(self, payload):
        self.check_message(payload)
        if payload.get("code") not in (200, "200"):
            raise JobAccessError(f"智联拒绝列表请求，code={payload.get('code')}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("智联响应缺少 data")
        if data.get("isVerification") not in (None, 0, "0", False):
            raise JobAccessError("智联要求访问验证")
        records = data.get("list")
        if not isinstance(records, list):
            raise ValueError("智联响应缺少岗位 list")
        total = data.get("count")
        return records, total if isinstance(total, int) else None, data.get("isEndPage") in (1, "1", True)

    def make_item(self, entry):
        detail = entry.get("jobDetailData") or {}
        position = detail.get("position") or {}
        desc = position.get("desc") or {}
        location = position.get("workLocation") or {}
        raw_text = desc.get("description") or entry.get("jobSummary") or ""
        # Join HTML block text without executing any markup from the upstream page.
        description = "\n".join(t.strip() for t in Selector(text=raw_text or "<div/>").xpath(
            "//text()[not(ancestor::script) and not(ancestor::style)]"
        ).getall() if t.strip())
        return JobItem(
            title=_job_text(entry.get("name")) or "",
            url=_job_url(entry.get("positionURL") or entry.get("positionUrl"), "zhaopin.com"),
            source=self.source_name, job_id=str(entry.get("number") or entry.get("jobId") or ""),
            company=_job_text(entry.get("companyName")),
            city=_job_text(entry.get("workCity")), salary_text=_job_text(entry.get("salary60")),
            education=_job_text(entry.get("education")), published_at=_job_text(entry.get("publishTime")),
            text=description or None,
        )


class Job51Parser(BaseJobParser):
    source_name = "51job"

    def page_data(self, payload):
        self.check_message(payload)
        if str(payload.get("status")) != "1":
            raise JobAccessError(f"51job 拒绝列表请求，status={payload.get('status')}")
        body = payload.get("resultbody") or {}
        job = body.get("job") if isinstance(body, dict) else None
        if not isinstance(job, dict) or not isinstance(job.get("items"), list):
            raise ValueError("51job 响应缺少 job.items")
        total = job.get("totalCount", job.get("totalcount"))
        if isinstance(total, str) and total.isdigit():
            total = int(total)
        return job["items"], total if isinstance(total, int) else None, False

    def make_item(self, entry):
        area = entry.get("jobAreaLevelDetail") or {}
        return JobItem(
            title=_job_text(entry.get("jobName")) or "", url=_job_url(entry.get("jobHref"), "51job.com"),
            source=self.source_name, job_id=str(entry.get("jobId") or ""),
            company=_job_text(entry.get("fullCompanyName") or entry.get("companyName")),
            city=_job_text(area.get("cityString")), salary_text=_job_text(entry.get("provideSalaryString")),
            education=_job_text(entry.get("degreeString")), published_at=_job_text(entry.get("issueDateString")),
            text=_job_text(entry.get("jobDescribe")),
        )


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
    "zhaopin": {
        "parser": ZhaopinParser(),
        "home_url": "https://www.zhaopin.com/sou",
        "collector": "jobs",
        "auth": {
            "mode": "required",
            "login_url": "https://www.zhaopin.com/",
            "state_path": "data/auth/zhaopin/storage_state.json",
            "domain": "zhaopin.com",
        },
    },
    "51job": {
        "parser": Job51Parser(),
        "home_url": "https://we.51job.com/pc/search",
        "collector": "jobs",
        "auth": {
            "mode": "required",
            "login_url": "https://we.51job.com/",
            "state_path": "data/auth/51job/storage_state.json",
            "domain": "51job.com",
        },
    },
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
    "AgentArena": {
        "parser": AgentArenaParser(),
        "home_url": "https://arena.ai/leaderboard/agent/overall",
    },
    "EverythingSkill": {
        "sections": {
            "EverythingSkill_hot": {
                "parser": EverythingSkillParser(section="hot"),
                "home_url": "https://everythingskill.net/zh/rankings/hot",
            },
            "EverythingSkill_new": {
                "parser": EverythingSkillParser(section="new"),
                "home_url": "https://everythingskill.net/zh/rankings/new",
            },
        },
    },
}

# SOURCES_KEYS：所有可用数据源的名称列表
# 方便快速获取可用源列表
SOURCES_KEYS: List[str] = list(SOURCES.keys())  # ["sina", "163", "tencent", "aihot"]
