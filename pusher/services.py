"""
推送服务 API 路由模块
定义推送服务的 RESTful 接口

接口列表：
GET /push/health: 健康检查
GET /push/targets: 获取可用推送目标列表
POST /push: 执行消息推送

推送策略：
- 单个目标：使用串行访问 _push_single
- 多个目标：使用并发访问 _push_batch

数据流：外部请求 → 路由 → 选择推送器 → 发送消息 → 返回结果
"""

import asyncio
from fastapi import APIRouter
from schemas import PushRequest, PushResponse
from pusher.senders import SENDERS, SENDERS_KEYS

router = APIRouter(prefix="/push", tags=["pusher"])


async def _push_single(
    target: str,
    items: list,
) -> tuple[int, int, list]:
    """
    串行推送：推送单个目标

    Args:
        target: 推送目标名称
        items: 要推送的消息列表

    Returns:
        tuple: (success_count, failed_count, errors)
    """
    if target not in SENDERS:
        return 0, len(items), [f"推送目标不存在: {target}"]

    if not SENDERS[target].get("enabled", True):
        return 0, len(items), [f"{target} 未启用"]

    sender = SENDERS[target]["sender"]

    try:
        result = await sender.send_batch(items)
        errors = []
        if result.get("errors"):
            for error in result["errors"]:
                errors.append(f"{target} 推送失败: {error}")
        return result["success"], result["failed"], errors
    except Exception as e:
        return 0, len(items), [f"{target} 推送异常: {str(e)}"]


async def _push_batch(
    targets: list,
    items: list,
) -> tuple[int, int, list]:
    """
    并发推送：批量推送到多个目标

    Args:
        targets: 推送目标列表
        items: 要推送的消息列表

    Returns:
        tuple: (total_success, total_failed, all_errors)
    """
    tasks = [_push_single(target, items) for target in targets]
    results = await asyncio.gather(*tasks)

    total_success = 0
    total_failed = 0
    all_errors = []

    for success, failed, errors in results:
        total_success += success
        total_failed += failed
        all_errors.extend(errors)

    return total_success, total_failed, all_errors


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

    推送策略：
    - 单个目标：使用串行访问 _push_single
    - 多个目标：使用并发访问 _push_batch

    请求参数：
        items: 格式化后的字符串列表，对标 FormatResponse.messages
        targets: 目标列表，"all" 或空列表表示推送到全部

    响应：
        status: 状态（success/failed）
        target_type: 推送类型（single/batch）
        success_count: 成功数
        failed_count: 失败数
    """
    is_all = "all" in request.targets or not request.targets
    targets_to_push = SENDERS_KEYS if is_all else request.targets

    if len(targets_to_push) == 1:
        target = targets_to_push[0]
        total_success, total_failed, errors = await _push_single(
            target, request.items
        )
        target_type = "single"
    else:
        total_success, total_failed, errors = await _push_batch(
            targets_to_push, request.items
        )
        target_type = "batch"

    return PushResponse(
        status="success" if total_success > 0 else "failed",
        target_type=target_type,
        success_count=total_success,
        failed_count=total_failed,
        errors=errors if errors else None,
    )
