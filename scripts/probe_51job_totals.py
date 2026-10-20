"""比较51job深圳、广州和随机三个城市查询首页声明的总数。"""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from collector.browser_client import BrowserClient
from collector.job_collector import CITY_CODES, capture_list, check_access
from collector.job_state import JobStateStore
from collector.parser import Job51Parser, JobAccessError
from config import settings
from schemas import JobQuery


async def main():
    store = JobStateStore(settings.jobs_state_path)
    token, retry = store.acquire("51job")
    if token is None:
        print(json.dumps({"status": "cooldown", "retry_after_seconds": retry}), flush=True)
        return
    output = ROOT / "data" / ("51job_totals_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    output.mkdir(parents=True, exist_ok=True)
    groups = [["深圳"], ["广州"], random.sample(list(CITY_CODES), 3)]
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "keyword": "计算机类",
              "planned_groups": groups, "queries": [], "errors": []}
    cooldown = max(300, settings.jobs_run_cooldown)
    try:
        async with BrowserClient() as client:
            for index, cities in enumerate(groups, 1):
                query = JobQuery(cities_51job=cities)
                area = ",".join(CITY_CODES[city] for city in cities)
                url = "https://we.51job.com/pc/search?" + urlencode({"keyword": query.keyword, "jobArea": area})
                await asyncio.sleep(store.delay("51job", token, max(10, settings.jobs_request_interval) + random.uniform(0, 3)))
                store.mark_request("51job", token)
                async with client.open_page() as page:
                    async def navigate():
                        response = await page.goto(url, wait_until="domcontentloaded", timeout=settings.jobs_response_timeout)
                        if response and response.status in (401, 403, 429):
                            raise JobAccessError(f"搜索页面 HTTP {response.status}")
                    payload = await capture_list(page, "51job", query, area, 1, navigate)
                    (output / f"query_{index}_response.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                    parser = Job51Parser()
                    records, total, _ = parser.page_data(payload)
                    items = parser.parse_payload(payload)
                    result = {"cities": cities, "area_code": area, "url": url, "totalCount": total,
                              "first_page_records": len(records),
                              "observed_cities": sorted({item.city for item in items if item.city}),
                              "job_metadata": {key: value for key, value in payload["resultbody"]["job"].items() if key != "items"}}
                    report["queries"].append(result)
                    print(json.dumps(result, ensure_ascii=False), flush=True)
                    await check_access(page)
    except Exception as exc:
        report["errors"].append(str(exc))
        if isinstance(exc, JobAccessError):
            cooldown = max(1800, settings.jobs_block_cooldown, exc.retry_after)
    finally:
        store.release("51job", token, cooldown)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"RESULT_DIR={output}", flush=True)
        print(json.dumps({"completed_queries": len(report["queries"]), "errors": report["errors"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
