from fastapi import APIRouter, Depends, HTTPException
from collector.client import CollectorClient
from collector.parser import SOURCES, SOURCES_KEYS
from .schemas import CollectRequest, CollectResponse
from .deps import get_collector_client, get_parser


router = APIRouter(prefix="/collect", tags=["collector"])


def get_all_available_sources() -> list:
    return SOURCES_KEYS


@router.get("/sources")
async def list_sources():
    return {"sources": SOURCES_KEYS}


@router.get("/health")
async def health_check():
    return {"status": "healthy"}


@router.post("", response_model=CollectResponse)
async def collect(request: CollectRequest, client: CollectorClient = Depends(get_collector_client)):
    if "all" in request.sources or not request.sources:
        sources_to_collect = get_all_available_sources()
    else:
        sources_to_collect = request.sources

    items_by_source = {}
    errors = []

    for source in sources_to_collect:
        if source not in SOURCES:
            errors.append(f"Source config not found: {source}")
            items_by_source[source] = []
            continue

        home_url = SOURCES[source]["home_url"]
        parser = get_parser(source)

        try:
            selector = await client.get(home_url)
            parsed_items = parser.parse_list(selector)

            if not parsed_items:
                errors.append(f"No items found from {source}")
                items_by_source[source] = []
                continue

            items = []
            for item in parsed_items:
                if parser.validate(item):
                    items.append(item.to_dict())

            items_by_source[source] = items

        except Exception as e:
            errors.append(f"Fetch error {source}: {str(e)}")
            items_by_source[source] = []

    total_items = sum(len(items) for items in items_by_source.values())

    return CollectResponse(
        status="success" if total_items > 0 else "no_data",
        total_sources=len(sources_to_collect),
        items_by_source=items_by_source,
        total_items=total_items,
        errors=errors if errors else None,
    )
