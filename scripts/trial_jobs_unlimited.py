"""一次性试采集：无页数/条数上限，翻页等待1–10秒，保留访问限制保护。"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from collector.browser_client import BrowserClient
from collector.job_collector import _collect_pages, city_groups
from collector.job_state import JobStateStore
from config import settings
from schemas import JobQuery


async def main():
    logging.basicConfig(level=logging.INFO)
    query = JobQuery()
    store = JobStateStore(settings.jobs_state_path)
    output = ROOT / "data" / ("jobs_unlimited_trial_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    async with BrowserClient() as client:
        for source in ("zhaopin", "51job"):
            token, retry = store.acquire(source)
            if token is None:
                results[source] = {"items": [], "errors": [f"站点正在执行或冷却，剩余 {retry} 秒"],
                                   "metadata": {"stop_reason": "cooldown"}}
            else:
                cooldown = max(1800, settings.jobs_block_cooldown)
                try:
                    results[source], cooldown = await _collect_pages(
                        client, source, query, city_groups(source, query), store, token, unlimited_trial=True)
                finally:
                    store.release(source, token, cooldown)
            (output / f"{source}.json").write_text(json.dumps(results[source], ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"source": source, "items": len(results[source]["items"]),
                              "metadata": results[source]["metadata"], "errors": results[source]["errors"]}, ensure_ascii=False), flush=True)
    summary = {"finished_at": datetime.now(timezone.utc).isoformat(), "keyword": query.keyword,
               "max_pages": None, "limit_per_source": None, "page_delay_seconds": [1, 10],
               "sources": {source: {"items": len(result["items"]), "metadata": result["metadata"],
                                    "errors": result["errors"]} for source, result in results.items()}}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"RESULT_DIR={output}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
