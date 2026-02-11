from typing import Dict, List, Callable, Literal

FormatType = Literal["markdown", "text", "plain"]


def _format_markdown(item: Dict) -> str:
    title = item.get("title", "").strip()
    url = item.get("url", "").strip()
    source = item.get("source", "").strip()
    return f"# {title}\n> 来源：{source}\n---\n[查看详情]({url})"


def _format_text(item: Dict) -> str:
    title = item.get("title", "").strip()
    url = item.get("url", "").strip()
    source = item.get("source", "").strip()
    return f"{title} ({source})\n{url}"


def _format_plain(item: Dict) -> str:
    title = item.get("title", "").strip()
    url = item.get("url", "").strip()
    source = item.get("source", "").strip()
    return f"{title}\n{source}\n{url}"


_FORMATTERS: Dict[FormatType, Callable[[Dict], str]] = {
    "markdown": _format_markdown,
    "text": _format_text,
    "plain": _format_plain,
}


def format_item(item: Dict, format_type: FormatType = "markdown") -> str:
    """将单条数据格式化为目标字符串

    Args:
        item: 数据字典，包含 title、url、source 等字段
        format_type: 格式化类型，支持 markdown、text、plain

    Returns:
        格式化后的字符串

    Raises:
        ValueError: 未知的格式类型
    """
    formatter = _FORMATTERS.get(format_type)
    if not formatter:
        raise ValueError(f"Unknown format type: {format_type}")
    return formatter(item)


def format_batch(items: List[Dict], format_type: FormatType = "markdown") -> List[str]:
    """批量格式化数据

    Args:
        items: 数据字典列表
        format_type: 格式化类型，支持 markdown、text、plain

    Returns:
        格式化后的字符串列表
    """
    return [format_item(item, format_type) for item in items]
