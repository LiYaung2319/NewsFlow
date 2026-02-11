from typing import List, Dict, Any, Optional
from .base import BaseProcessor
from .formatter import format_batch, FormatType


class DataProcessor:
    """数据处理链主类

    负责协调多个处理器按顺序处理数据，支持：
    - 处理器链式添加
    - 多种输出格式选择
    - 原始数据或格式化输出

    Example:
        processor = DataProcessor()
        processor.add_processor(DedupProcessor())
        processor.add_processor(FilterProcessor(keywords=["AI"]))
        result = await processor.run(items, format_type="markdown")
    """

    def __init__(self):
        self._processors: List[BaseProcessor] = []
        self._format_type: FormatType = "markdown"

    def add_processor(self, processor: BaseProcessor) -> "DataProcessor":
        """添加处理器到处理链

        Args:
            processor: 实现 BaseProcessor 接口的处理器实例

        Returns:
            self，支持链式调用
        """
        self._processors.append(processor)
        return self

    def set_format(self, format_type: FormatType) -> "DataProcessor":
        """设置输出格式

        Args:
            format_type: 格式化类型，支持 markdown、text、plain

        Returns:
            self，支持链式调用
        """
        self._format_type = format_type
        return self

    async def run(self, data: List[Dict[str, Any]]) -> List[str]:
        """执行处理链，返回格式化后的字符串列表

        Args:
            data: 原始数据列表

        Returns:
            格式化后的字符串列表
        """
        current_data = data

        for processor in self._processors:
            current_data = await processor.process(current_data)

        return format_batch(current_data, self._format_type)

    async def run_with_raw_output(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """执行处理链，返回原始数据（用于调试或下一步处理）

        Args:
            data: 原始数据列表

        Returns:
            处理后的原始数据列表
        """
        current_data = data
        for processor in self._processors:
            current_data = await processor.process(current_data)
        return current_data

    @property
    def processor_count(self) -> int:
        """当前已添加的处理器数量"""
        return len(self._processors)

    def clear_processors(self) -> None:
        """清空所有处理器"""
        self._processors.clear()
