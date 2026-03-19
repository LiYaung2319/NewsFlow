"""
推送服务 API 路由模块
定义推送服务的 RESTful 接口

接口列表：
GET /push/health: 健康检查
GET /push/targets: 获取可用推送目标列表
POST /push: 执行消息推送

数据流：外部请求 → 路由 → 选择推送器 → 发送消息 → 返回结果
"""

from fastapi import APIRouter
from typing import List, Dict, Any
from schemas import PushRequest, PushResponse
from pusher.senders import SENDERS, SENDERS_KEYS

router = APIRouter(prefix="/push", tags=["pusher"])


@router.get("/targets")
async def list_targets():
    """获取可用推送目标列表"""
    return {"targets": SENDERS_KEYS}


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


@router.post("", response_model=PushResponse)
async def push(request: PushRequest):
    """
    核心推送接口

    请求参数：
        items: 要推送的数据，按数据源分组
        targets: 目标列表，"all" 或空列表表示推送到全部

    响应：
        status: 状态（success/failed）
        target_type: 推送类型（all/batch）
        success_count: 成功数
        failed_count: 失败数
    """
    # ==================== 确定推送目标 ====================
    is_all = "all" in request.targets or not request.targets
    targets_to_push = SENDERS_KEYS if is_all else request.targets

    # ==================== 遍历目标推送 ====================
    errors = []
    total_success = 0
    total_failed = 0

    for target in targets_to_push:
        if target not in SENDERS:
            errors.append(f"推送目标不存在: {target}")
            continue

        sender = SENDERS[target]["sender"]

        if not SENDERS[target].get("enabled", True):
            errors.append(f"{target} 未启用")
            continue

        try:
            items_list = process_data(request.items)
            result = await sender.send_batch(items_list)
            total_success += result["success"]
            total_failed += result["failed"]

            if result["failed"] > 0:
                errors.append(f"{target} 推送失败 {result['failed']} 条")
        except Exception as e:
            total_failed += len(request.items)
            errors.append(f"{target} 推送异常: {str(e)}")

    # ==================== 返回结果 ====================
    return PushResponse(
        status="success" if total_success > 0 else "failed",
        target_type="all" if is_all else "batch",
        success_count=total_success,
        failed_count=total_failed,
        errors=errors if errors else None,
    )


def process_data(items_dict: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """
    格式化为 Markdown 消息

    将采集数据转换为 Markdown 格式字符串列表

    Args:
        items_dict: 按数据源分组的新闻数据

    Returns:
        List[str]: Markdown 格式字符串列表
    """
    items_list = []
    for source, items in items_dict.items():
        content = f"# {source} 资讯"
        for item in items:
            title = item.get("title", "")
            url = item.get("url", "")
            content += f"\n- [{title}]({url})"
        items_list.append(content)
    return items_list
