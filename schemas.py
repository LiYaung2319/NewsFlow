"""
数据模型模块
定义 NewsFlow 项目中使用的数据结构

核心类：
- ParsedItem: 表示一条解析后的新闻数据
- CollectRequest: 采集请求模型
- CollectResponse: 采集响应模型

特点：
- ParsedItem 使用 @dataclass 装饰器
- CollectRequest 和 CollectResponse 使用 Pydantic BaseModel（用于 FastAPI 验证）
- 提供序列化方法（to_dict、to_json）
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json
from pydantic import BaseModel


@dataclass
class ParsedItem:
    """
    解析后的新闻条目数据类

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
    text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典

        作用：用于 API 响应或数据传输

        返回：
        Dict: 包含 title、url、source 的字典（text 为空时不包含）
        """
        result = {
            "title": self.title,
            "url": self.url,
            "source": self.source,
        }
        if self.text:
            result["text"] = self.text
        return result

    def to_json(self) -> str:
        """
        转换为 JSON 字符串

        作用：用于日志记录或调试

        返回：
        str: JSON 格式的字符串
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)


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
