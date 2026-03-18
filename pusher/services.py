"""
推送服务 API 路由模块
定义推送服务的 RESTful API 接口

接口列表：
    GET /push/health: 健康检查
    GET /push/targets: 获取可用推送目标列表
    POST /push: 执行消息推送

数据流：
    外部请求 → 路由 → 获取目标配置 → 选择发送器 → 发送消息 → 返回结果
"""

from fastapi import APIRouter, HTTPException  # FastAPI 组件
from typing import List, Dict, Any  # 类型注解
from schemas import PushRequest, PushResponse  # 数据模型
from pusher.senders import SENDERS, SENDERS_KEYS

router = APIRouter(prefix="/push", tags=["pusher"])


@router.get("/targets")
async def list_targets():
    """
    获取可用推送目标列表

    作用：查询当前配置的所有推送目标

    Returns:
        {"sources": ["wechat", "dingtalk", "email"]} - 可用推送目标列表
    """

    return {"sources": SENDERS_KEYS}


@router.get("/health")
async def health_check():
    """
    健康检查接口

    Returns:
        {"status": "healthy"}
    """
    return {"status": "healthy"}


@router.post("", response_model=PushResponse)
async def push(request: PushRequest):
    """
    核心推送接口

    作用：将数据推送到指定的目标平台

    请求参数：
        items: 要推送的数据列表
        targets: 目标列表，"all" 或空数组表示推送到全部

    响应：
        status: 状态（success/failed）
        target_type: 推送类型（all/batch）
        success_count: 成功数
        failed_count: 失败数
    """
    # ==================== 确定推送目标 ====================
    # "all" 或空数组表示推送到全部目标
    is_all = "all" in request.targets or not request.targets

    if is_all:
        targets_to_push = SENDERS_KEYS
    else:
        targets_to_push = request.targets

    # errors: 收集各数据源采集过程中的错误信息
    errors = []
    # 初始化计数
    total_success = 0
    total_failed = 0

    # ==================== 遍历目标发送 ====================
    for target in targets_to_push:
        # 检查数据源配置是否存在
        if target not in SENDERS:
            errors.append(f"推送方配置不存在: {target}")
            raise HTTPException(status_code=400, detail=f"推送方配置不存在: {target}")

        try:
            # 推送到单个目标
            sender = SENDERS[target]  # 获取推送器实例
            result = await sender.send_batch(request.items)
            total_success += result["success"]
            total_failed += result["failed"]
        except Exception as e:
            # 异常
            total_failed += len(request.items)
            errors.append(f"{target}推送失败: {str(e)}")

    # ==================== 返回结果 ====================
    return PushResponse(
        status="success" if total_success > 0 else "failed",
        target_type="all" if is_all else "batch",
        success_count=total_success,
        failed_count=total_failed,
        errors=errors if errors else None,  # 无错误时返回 None
    )
