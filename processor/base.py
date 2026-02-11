from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseProcessor(ABC):
    """数据处理器抽象基类"""
    processor_type: str = "base"

    @abstractmethod
    async def process(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """处理数据，返回处理后的数据"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """验证配置是否有效"""
        pass
