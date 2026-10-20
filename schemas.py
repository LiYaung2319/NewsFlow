"""
数据模型模块
定义 NewsFlow 项目中使用的数据结构

核心类：
- ParsedItem: 表示一条解析后的新闻数据
- CollectRequest: 采集请求模型
- CollectResponse: 采集响应模型
- PushRequest: 推送请求模型
- PushResponse: 推送响应模型
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


@dataclass
class ParsedItem:
    """
    解析后的新闻条目

    统一不同来源的新闻数据格式
    作用：统一不同来源的新闻数据格式

    字段说明：
    - title: 新闻标题
    - url: 新闻链接
    - source: 数据来源标识（sina/163/tencent）
    - rank: 榜单排名（可选）
    - text: 详情文本（可选）
    """

    title: str
    url: str
    source: str
    text: Optional[str] = None  # 预留字段
    rank: Optional[int] = None  # 榜单排名（可选）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "title": self.title,
            "url": self.url,
            "source": self.source,
        }
        if self.text:
            result["text"] = self.text
        if self.rank is not None:
            result["rank"] = self.rank
        return result


@dataclass
class JobItem(ParsedItem):
    """招聘条目；对外统一输出固定的岗位业务字段。"""

    kind: str = "job"
    job_id: str = ""
    company: Optional[str] = None
    city: Optional[str] = None
    salary_text: Optional[str] = None
    education: Optional[str] = None
    published_at: Optional[str] = None
    # 仅供采集过程统计，不通过 to_dict 对外返回。
    missing_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "company": self.company,
            "city": self.city,
            "salary_text": self.salary_text,
            "education": self.education,
            "text": self.text,
            "published_at": self.published_at,
            "url": self.url,
            "source": self.source,
            "kind": self.kind,
            "job_id": self.job_id,
        }


class JobQuery(BaseModel):
    """招聘查询：固定小批量预算，平台原始搜索结果不做相关性过滤。"""

    keyword: str = Field(default="计算机类", min_length=1, max_length=60)
    max_pages: int = Field(default=3, ge=1, le=6)
    limit_per_source: int = Field(default=100, ge=1, le=120)
    cities_51job: List[str] = Field(
        default_factory=lambda: ["北京", "上海", "广州", "深圳", "杭州"],
        min_length=1, max_length=20,
    )

    @field_validator("keyword")
    @classmethod
    def non_blank_keyword(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("关键词不能为空")
        return value

    @field_validator("cities_51job")
    @classmethod
    def unique_cities(cls, cities: List[str]) -> List[str]:
        if any(not city.strip() for city in cities):
            raise ValueError("城市不能为空")
        return list(dict.fromkeys(city.strip() for city in cities))


class CollectRequest(BaseModel):
    """
    采集请求数据模型

    作用：验证 POST /collect 接口的请求体参数
    """

    sources: List[str]  # 要采集的数据源列表
    concurrency: Optional[int] = None  # 并发请求数，可选
    job_query: Optional[JobQuery] = None


class CollectResponse(BaseModel):
    """
    采集响应数据模型

    作用：格式化 POST /collect 接口的响应数据
    """

    status: str  # 状态：success / no_data / failed
    total_sources: int  # 采集的源数量
    items_by_source: Dict[str, List[Dict[str, Any]]]  # 按源分组的结果
    total_items: int  # 总数据条数
    errors: Optional[List[str]] = None  # 错误信息列表
    source_metadata: Optional[Dict[str, Any]] = None  # 招聘覆盖范围、停止原因和缓存状态


class PushRequest(BaseModel):
    """
    推送请求数据模型

    作用：验证 POST /push 接口的请求体
    """

    items: List[str]  # 格式化后的字符串列表，对标 FormatResponse.messages
    targets: List[str]  # 目标列表


class PushResponse(BaseModel):
    """
    推送响应数据模型

    作用：格式化 POST /push 接口的响应
    """

    status: str  # 状态：success / failed
    target_type: str  # 推送类型：single / batch
    success_count: int  # 成功推送数
    failed_count: int  # 失败数
    errors: Optional[List[str]] = None  # 错误信息列表


class FormatRequest(BaseModel):
    """
    格式化请求数据模型

    作用：验证 POST /processor/format 接口的请求体

    格式：[{format_type: data}, ...]
    例如：单个 [{"collect": {...}}]，多个 [{"collect": {...}}, {"collect": {...}}]
    """

    data: List[Dict[str, Any]]  # 格式化请求列表


class FormatResponse(BaseModel):
    """
    格式化响应数据模型

    作用：格式化 POST /processor/format 接口的响应
    """

    status: str  # 状态：success / failed
    messages: List[str]  # 格式化后的字符串列表
    errors: Optional[List[str]] = None  # 错误信息列表
