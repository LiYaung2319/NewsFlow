"""
采集服务 API 路由模块
定义采集服务的 RESTful API 接口

接口列表：
GET /collect/health: 健康检查
GET /collect/sources: 获取可用数据源列表
POST /collect: 执行数据采集

数据流：
外部请求 → 路由 → 创建客户端 → 采集数据 → 返回响应
"""

from fastapi import APIRouter
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


@router.post("", response_model=CollectResponse)
async def collect(request: CollectRequest):
    """
    核心采集接口

    作用：从指定数据源采集新闻数据

    参数：
    request: CollectRequest 采集请求对象，包含 sources 和 concurrency

    返回：
    CollectResponse 采集响应对象，包含状态、结果和错误信息
    """
    # 使用 async with 自动管理客户端生命周期
    async with BrowserClient() as client:
        # ========== 确定要采集的数据源 ==========
        # "all" 或空列表表示采集全部数据源
        if "all" in request.sources or not request.sources:
            sources_to_collect = SOURCES_KEYS
        else:
            sources_to_collect = request.sources

        # 初始化结果容器
        # items_by_source: 按数据源分组的结果，格式: {"sina": [...], "163": [...]}
        items_by_source = {}
        # errors: 收集各数据源采集过程中的错误信息
        errors = []

        # ========== 遍历数据源进行采集 ==========
        for source in sources_to_collect:
            # 检查数据源配置是否存在
            if source not in SOURCES:
                errors.append(f"数据源配置不存在: {source}")
                items_by_source[source] = []
                continue

            # 获取数据源配置
            home_url = SOURCES[source]["home_url"]  # 主页 URL
            parser = SOURCES[source]["parser"]  # 获取解析器实例

            try:
                # 步骤1：获取网页内容
                selector = await client.get(home_url)

                # 步骤2：解析新闻列表
                parsed_items = parser.parse_list(selector)

                # 步骤3：检查是否有解析结果
                if not parsed_items:
                    errors.append(f"未从 {source} 获取到数据")
                    items_by_source[source] = []
                    continue

                # 步骤4：验证并转换数据格式
                items = []
                for item in parsed_items:
                    # validate() 检查标题和链接是否有效
                    if parser.validate(item):
                        items.append(item.to_dict())  # 转换为字典
                items_by_source[source] = items

            except Exception as e:
                # 捕获采集过程中的任何异常
                errors.append(f"{source} 采集失败: {str(e)}")
                items_by_source[source] = []

        # ========== 计算总数据条数 ==========
        total_items = sum(len(items) for items in items_by_source.values())

        # ========== 构建响应 ==========
        return CollectResponse(
            status=(
                "success" if total_items > 0 else "no_data"
            ),  # 有数据返回 success，无数据返回 no_data
            total_sources=len(sources_to_collect),
            items_by_source=items_by_source,
            total_items=total_items,
            errors=errors if errors else None,  # 无错误时返回 None
        )
