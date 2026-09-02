"""
格式化器模块
定义数据格式化的抽象基类和具体实现

策略模式：
- BaseFormatter: 抽象基类，定义格式化接口
- CollectFormatter: 采集数据格式化器
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


SOURCE_TITLES = {
    "AgentArena": "Agent Arena Overall 榜",
    "aihot_hot": "AI 热点榜",
    "aihot_daily": "AI 日报",
    "CSDN_all": "CSDN 资讯头条",
    "CSDN_ai": "CSDN 人工智能",
    "CSDN_python": "CSDN Python",
}


class BaseFormatter(ABC):
    """
    格式化器基类

    作用：定义格式化器的统一接口，所有格式化器需继承此类

    方法：
    - format: 将数据格式化为字符串列表
    """

    @abstractmethod
    def format(self, data: Any) -> List[str]:
        """
        格式化数据

        Args:
            data: 输入数据

        Returns:
            List[str]: 格式化后的字符串列表
        """
        pass


class CollectFormatter(BaseFormatter):
    """
    采集数据格式化器

    作用：将采集服务的响应数据（items_by_source）格式化为 Markdown 字符串

    输入数据结构：
        Dict[str, List[Dict[str, Any]]]
        - key: 数据源名称（如 sina, 163, tencent）
        - value: 新闻列表，每条包含 title, url, source

    输出：
        Markdown 格式字符串列表，每条不超过 1500 字符
    """

    def format(self, data: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        """
        格式化为 Markdown 消息

        Args:
            data: 按数据源分组的新闻数据

        Returns:
            List[str]: Markdown 格式字符串列表
        """
        items_list = []
        for source, items in data.items():
            source_title = SOURCE_TITLES.get(source, f"{source} 资讯")
            if any(item.get("rank") is not None for item in items):
                items_list.extend(self._format_ranking(source_title, items))
                continue

            content = f"# {source_title}"
            for item in items:
                item_title = item.get("title", "")
                url = item.get("url", "")
                content += f"\n- [{item_title}]({url})"
                if len(content) > 2000:
                    items_list.append(content)
                    content = f"# {source_title}"
            if content != f"# {source_title}":
                items_list.append(content)
        return items_list

    @staticmethod
    def _format_ranking(
        source_title: str, items: List[Dict[str, Any]]
    ) -> List[str]:
        """将带 rank 的数据按榜单布局格式化，并按消息长度拆分。"""
        ranked_items = sorted(
            (item for item in items if item.get("rank") is not None),
            key=lambda item: item["rank"],
        )
        if not ranked_items:
            return []

        total = len(ranked_items)
        chunks: List[List[Dict[str, Any]]] = []
        current: List[Dict[str, Any]] = []
        for item in ranked_items:
            candidate = current + [item]
            first_rank = candidate[0]["rank"]
            last_rank = candidate[-1]["rank"]
            header = f"# {source_title}\n> 排名 {first_rank}-{last_rank} / {total}\n\n"
            body = "\n".join(
                f"{entry['rank']}. [{entry.get('title', '')}]({entry.get('url', '')})"
                for entry in candidate
            )
            if len(header + body) > 2000 and current:
                chunks.append(current)
                current = [item]
            else:
                current = candidate

        if current:
            chunks.append(current)

        messages = []
        for chunk in chunks:
            first_rank = chunk[0]["rank"]
            last_rank = chunk[-1]["rank"]
            header = f"# {source_title}\n> 排名 {first_rank}-{last_rank} / {total}\n\n"
            body = "\n".join(
                f"{item['rank']}. [{item.get('title', '')}]({item.get('url', '')})"
                for item in chunk
            )
            messages.append(header + body)
        return messages


FORMATS = {
    "collect": CollectFormatter(),
}
