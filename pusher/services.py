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
        items: 格式化后的字符串列表，对标 FormatResponse.messages
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

        if not SENDERS[target].get("enabled", True):
            errors.append(f"{target} 未启用")
            continue

        sender = SENDERS[target]["sender"]

        try:
            result = await sender.send_batch(request.items)
            total_success += result["success"]
            total_failed += result["failed"]

            if result.get("errors"):
                for error in result["errors"]:
                    errors.append(f"{target} 推送失败: {error}")
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
