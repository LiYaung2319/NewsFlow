from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from .schemas import PushRequest, PushResponse, TargetListResponse
from .senders import SENDERS
from config import settings


router = APIRouter(prefix="/push", tags=["pusher"])


def get_all_available_targets() -> list:
    return [name for name, config in settings.push_targets.items() 
            if config.get("webhook_url")]


def get_target_config(target: str) -> Dict[str, Any]:
    """从配置获取目标配置"""
    if target not in settings.push_targets:
        raise HTTPException(status_code=400, detail=f"Unknown target: {target}")
    return settings.push_targets[target]


async def _push_to_target(
    target: str,
    items: List[Dict[str, Any]],
    webhook_url: str = ""
) -> Dict[str, int]:
    """推送消息到单个目标"""
    if webhook_url:
        url = webhook_url
        sender_type = "custom"
    else:
        config = get_target_config(target)
        sender_type = config.get("type", "unknown")
        url = config.get("webhook_url")
    
    sender_class = SENDERS.get(sender_type)
    if not sender_class:
        raise HTTPException(status_code=400, detail=f"Unknown sender type: {sender_type}")
    
    sender = sender_class(webhook_url=url)
    return await sender.send_batch(items)


@router.get("/targets", response_model=TargetListResponse)
async def list_targets():
    """列出所有可用的推送目标"""
    targets = []
    for name, config in settings.push_targets.items():
        targets.append({
            "name": name,
            "type": config.get("type", "unknown"),
            "enabled": bool(config.get("webhook_url"))
        })
    return {"targets": targets}


@router.post("", response_model=PushResponse)
async def push(request: PushRequest):
    """推送消息到目标"""
    is_all = "all" in request.targets or not request.targets

    if is_all:
        targets_to_push = get_all_available_targets()
    else:
        targets_to_push = request.targets
    
    if not targets_to_push:
        raise HTTPException(status_code=400, detail="No available targets")
    
    total_success = 0
    total_failed = 0
    
    for target in targets_to_push:
        try:
            result = await _push_to_target(target, request.items)
            total_success += result["success"]
            total_failed += result["failed"]
        except HTTPException as e:
            total_failed += len(request.items)
        except Exception:
            total_failed += len(request.items)
    
    return PushResponse(
        status="success" if total_success > 0 else "failed",
        target_type="all" if is_all else "batch",
        success_count=total_success,
        failed_count=total_failed
    )


@router.get("/health")
async def health_check():
    return {"status": "healthy"}
