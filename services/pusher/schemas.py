from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class PushRequest(BaseModel):
    items: List[Dict[str, Any]]
    targets: List[str]


class PushResponse(BaseModel):
    status: str
    target_type: str
    success_count: int
    failed_count: int


class TargetInfo(BaseModel):
    name: str
    type: str
    enabled: bool


class TargetListResponse(BaseModel):
    targets: List[TargetInfo]
