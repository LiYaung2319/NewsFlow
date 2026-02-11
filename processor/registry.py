from typing import Dict, Type
from .base import BaseProcessor


class ProcessorRegistry:
    """处理器注册表

    用于注册和管理可用的处理器，方便后续扩展和动态加载。

    Example:
        # 注册处理器
        ProcessorRegistry.register("dedup", DedupProcessor)

        # 获取处理器
        cls = ProcessorRegistry.get("dedup")
        processor = cls()
    """

    _processors: Dict[str, Type[BaseProcessor]] = {}

    @classmethod
    def register(cls, name: str, processor_cls: Type[BaseProcessor]) -> None:
        """注册处理器

        Args:
            name: 处理器标识符
            processor_cls: 处理器类（实现 BaseProcessor 接口）
        """
        cls._processors[name] = processor_cls

    @classmethod
    def get(cls, name: str) -> Type[BaseProcessor] | None:
        """获取处理器类

        Args:
            name: 处理器标识符

        Returns:
            处理器类，未找到返回 None
        """
        return cls._processors.get(name)

    @classmethod
    def list_all(cls) -> List[str]:
        """列出所有已注册的处理器"""
        return list(cls._processors.keys())

    @classmethod
    def clear(cls) -> None:
        """清空注册表"""
        cls._processors.clear()
