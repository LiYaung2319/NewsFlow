from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class CollectRequest(BaseModel):
    sources: List[str]
    concurrency: int = 10


class CollectResponse(BaseModel):
    status: str
    total_sources: int
    items_by_source: Dict[str, List[Dict[str, Any]]]
    total_items: int
    errors: Optional[List[str]] = None
