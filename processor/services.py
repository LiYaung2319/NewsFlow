"""
处理器服务 API 路由模块
定义处理器的 RESTful API 接口

接口列表：
GET /processor/health: 健康检查
POST /processor/format: 格式化数据为 Markdown

数据流：
外部请求 → 路由 → 选择格式化器 → 执行格式化 → 返回结果
"""

import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any, Union
from processor.formatter import FORMATS, BaseFormatter
from schemas import FormatRequest, FormatResponse


router = APIRouter(prefix="/processor", tags=["processor"])


class HealthResponse(BaseModel):
    status: str


@router.get("/health")
async def health_check():
    """
    健康检查接口

    作用：检查处理器服务是否正常运行

    返回：
    {"status": "healthy"} - 服务运行正常
    """
    return {"status": "healthy"}


async def _format_single(
    format_type: str,
    data: Any,
) -> tuple[str, List[str], List[str]]:
    """
    处理单个格式化请求

    Args:
        format_type: 格式化类型
        data: 要格式化的数据

    Returns:
        tuple: (status, messages, errors)
    """
    formatter = FORMATS.get(format_type)

    if not formatter:
        return "failed", [], [f"不支持的格式化类型: {format_type}"]

    try:
        messages = formatter.format(data)
        return "success", messages, []
    except Exception as e:
        return "failed", [], [str(e)]


async def _format_batch(
    items: List[Dict[str, Any]],
) -> tuple[str, List[str], List[str]]:
    """
    并发处理多个格式化请求

    Args:
        items: 格式化请求列表，格式为 [{format_type: data}, ...]

    Returns:
        tuple: (status, messages, errors)
    """
    tasks = []
    for item in items:
        if not item:
            continue
        format_type, data = next(iter(item.items()))
        tasks.append(_format_single(format_type, data))

    if not tasks:
        return "failed", [], ["请求数据为空"]

    results = await asyncio.gather(*tasks)

    all_messages = []
    all_errors = []
    has_success = False

    for status, messages, errors in results:
        if status == "success":
            has_success = True
            all_messages.extend(messages)
        if errors:
            all_errors.extend(errors)

    final_status = "success" if has_success else "failed"
    return final_status, all_messages, all_errors


@router.post("/format", response_model=FormatResponse)
async def format_data(request: FormatRequest):
    """
    核心格式化接口

    作用：将数据格式化为 Markdown 字符串

    参数：
    request: FormatRequest 格式化请求对象，格式为 [{format_type: data}, ...]

    返回：
    FormatResponse 格式化响应对象，包含状态和格式化后的字符串列表
    """
    if len(request.data) == 1:
        format_type, data = next(iter(request.data[0].items()))
        status, messages, errors = await _format_single(format_type, data)
    else:
        status, messages, errors = await _format_batch(request.data)

    return FormatResponse(
        status=status,
        messages=messages,
        errors=errors if errors else None,
    )
