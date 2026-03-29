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

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


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
    - text: 详情文本（可选）
    """

    title: str
    url: str
    source: str
    text: Optional[str] = None  # 预留字段

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "title": self.title,
            "url": self.url,
            "source": self.source,
        }
        if self.text:
            result["text"] = self.text
        return result


class CollectRequest(BaseModel):
    """
    采集请求数据模型

    作用：验证 POST /collect 接口的请求体参数
    """

    sources: List[str]  # 要采集的数据源列表
    concurrency: Optional[int] = None  # 并发请求数，可选


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
