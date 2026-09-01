"""
采集服务 API 路由模块
定义采集服务的 RESTful API 接口

接口列表：
GET /collect/health: 健康检查
GET /collect/sources: 获取可用数据源列表
POST /collect: 执行数据采集

采集策略：
- 串行访问：单个数据源，使用 client.get 逐个请求
- 并行访问：多个数据源，使用 client.get_batch 批量并发请求

数据流：
外部请求 → 路由 → 创建客户端 → 判断采集策略 → 执行采集 → 格式化响应 → 返回
"""

from typing import Dict, List, Optional, Tuple
from fastapi import APIRouter
from parsel import Selector
from collector.browser_client import BrowserClient
from collector.parser import SOURCES, SOURCES_KEYS
from schemas import CollectRequest, CollectResponse

router = APIRouter(prefix="/collect", tags=["collector"])


@router.get("/sources")
async def list_sources():
    """
    获取可用数据源列表

    作用：查询当前配置的所有可用数据源

    返回：
    {"sources": ["sina", "163", "tencent"]} - 可用数据源名称列表
    """
    return {"sources": SOURCES_KEYS}


@router.get("/health")
async def health_check():
    """
    健康检查接口

    作用：检查采集服务是否正常运行

    返回：
    {"status": "healthy"} - 服务运行正常
    """
    return {"status": "healthy"}


async def _collect_single(
    client: BrowserClient,
    source: str,
) -> Tuple[Dict[str, List[Dict]], List[str]]:
    """
    串行访问：采集单个数据源

    流程：
    1. 通过 source 获取数据源配置（URL 和解析器）
    2. 调用 client.get 获取网页内容
    3. 使用解析器解析网页
    4. 验证并转换数据格式

    Args:
        client: 浏览器客户端实例
        source: 数据源名称

    Returns:
        Tuple[Dict[str, List[Dict]], List[str]]:
            - items_by_source: 按数据源分组的结果
            - errors: 错误信息列表
    """
    if source not in SOURCES:
        return {source: []}, [f"数据源配置不存在: {source}"]

    home_url = SOURCES[source]["home_url"]
    parser = SOURCES[source]["parser"]

    try:
        selector = await client.get(home_url)
        items, error = _parse_and_validate(selector, parser, source)
        return {source: items}, [error] if error else []
    except Exception as e:
        return {source: []}, [f"{source} 采集失败: {str(e)}"]


async def _collect_batch(
    client: BrowserClient,
    source_configs: Dict[str, Dict],
    concurrency: Optional[int],
) -> Tuple[Dict[str, List[Dict]], List[str]]:
    """
    并行访问：批量采集多个数据源

    流程：
    1. 将 source_configs 中的页面传给 client.get_batch 并发请求
    2. 遍历返回的 selectors 和 errors
    3. 对每个 source 获取对应解析器并解析数据
    4. 汇总所有数据源结果

    Args:
        client: 浏览器客户端实例
        source_configs: 页面配置字典，格式为 {页面名称: 配置}
        concurrency: 最大并发数

    Returns:
        Tuple[Dict[str, List[Dict]], List[str]]:
            - items_by_source: 按数据源分组的结果
            - errors: 错误信息列表
    """
    source_urls = {
        source: config["home_url"] for source, config in source_configs.items()
    }
    selectors, batch_errors = await client.get_batch(source_urls, concurrency)
    items_by_source = {}
    errors = list(batch_errors)

    for source, selector in selectors.items():
        parser = source_configs[source]["parser"]
        items, error = _parse_and_validate(selector, parser, source)

        if error:
            errors.append(error)

        items_by_source[source] = items

    return items_by_source, errors


def _expand_source_configs(sources: List[str]) -> Dict[str, Dict]:
    """将逻辑信息源展开为实际需要访问的页面配置。"""
    source_configs = {}
    for source in sources:
        config = SOURCES.get(source)
        if not config:
            continue

        sections = config.get("sections")
        if sections:
            source_configs.update(sections)
        else:
            source_configs[source] = config

    return source_configs


def _parse_and_validate(
    selector: Selector,
    parser,
    source: str,
) -> Tuple[List[Dict], Optional[str]]:
    """
    解析网页并验证数据

    Args:
        selector: 网页 Selector 对象
        parser: 解析器实例
        source: 数据源名称

    Returns:
        Tuple[List[Dict], Optional[str]]:
            - items: 解析后的数据列表
            - error: 错误信息，无错误时为 None
    """
    try:
        parsed_items = parser.parse_list(selector)

        if not parsed_items:
            return [], f"未从 {source} 获取到数据"

        items = [item.to_dict() for item in parsed_items if parser.validate(item)]

        return items, None
    except Exception as e:
        return [], f"{source} 解析失败: {str(e)}"


@router.post("", response_model=CollectResponse)
async def collect(request: CollectRequest):
    """
    核心采集接口

    作用：从指定数据源采集新闻数据

    采集策略：
    - 单个数据源：使用串行访问 _collect_single
    - 多个数据源：使用并行访问 _collect_batch

    参数：
    request: CollectRequest 采集请求对象，包含 sources 和 concurrency

    返回：
    CollectResponse 采集响应对象，包含状态、结果和错误信息
    """
    async with BrowserClient() as client:
        if "all" in request.sources or not request.sources:
            sources_to_collect = SOURCES_KEYS
        else:
            sources_to_collect = request.sources

        source = sources_to_collect[0] if len(sources_to_collect) == 1 else None
        is_composite_source = (
            source in SOURCES and "sections" in SOURCES[source]
            if source
            else False
        )

        if len(sources_to_collect) == 1 and not is_composite_source:
            items_by_source, errors = await _collect_single(client, source)
        else:
            source_configs = _expand_source_configs(sources_to_collect)
            items_by_source, errors = await _collect_batch(
                client, source_configs, request.concurrency
            )

        total_items = sum(len(items) for items in items_by_source.values())
        errors = [e for e in errors if e is not None]

        return CollectResponse(
            status="success" if total_items > 0 else "no_data",
            total_sources=len(sources_to_collect),
            items_by_source=items_by_source,
            total_items=total_items,
            errors=errors if errors else None,
        )
