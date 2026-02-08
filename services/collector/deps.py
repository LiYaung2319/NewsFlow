from collector.client import CollectorClient
from collector.parser import SOURCES, BaseParser
from typing import AsyncGenerator


async def get_collector_client() -> AsyncGenerator[CollectorClient, None]:
    async with CollectorClient() as client:
        yield client


def get_parser(name: str) -> BaseParser:
    source_config = SOURCES.get(name)
    if source_config is None:
        raise ValueError(f"Unknown source: {name}")
    parser_class = source_config["parser"]
    return parser_class()
