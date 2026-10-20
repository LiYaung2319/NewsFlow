"""真实采集/API/格式化检查，不调用推送接口。结果写入被忽略的 data/。"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import httpx
from main import app
from schemas import JobQuery


async def verify(args):
    query = JobQuery(max_pages=args.pages, limit_per_source=args.limit)
    if args.cities:
        query = JobQuery(**{**query.model_dump(), "cities_51job": args.cities.split(",")})
    request = {"sources": ["zhaopin", "51job"], "job_query": query.model_dump()}
    findings = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://newsflow.test", timeout=180) as client:
        response = await client.post("/collect", json=request)
        response.raise_for_status()
        result = response.json()
        for source in request["sources"]:
            items = result["items_by_source"].get(source, [])
            meta = (result.get("source_metadata") or {}).get(source, {})
            if not items:
                findings.append(f"{source}: 本次未取得岗位")
            if len(items) > query.limit_per_source:
                findings.append(f"{source}: 数量超过限制")
            if len({i["url"] for i in items}) != len(items) or len({i["job_id"] for i in items}) != len(items):
                findings.append(f"{source}: 存在重复岗位")
            if any(not i.get("title") or not i.get("url") or i.get("source") != source for i in items):
                findings.append(f"{source}: 必填字段不正确")
            if meta.get("pages_fetched", 0) > query.max_pages:
                findings.append(f"{source}: 页数超过预算")
            print(json.dumps({"source": source, "items": len(items), "metadata": meta,
                              "samples": [{k: i.get(k) for k in ("title", "url", "company", "city", "salary_text")} for i in items[:3]]}, ensure_ascii=False))
        formatted = await client.post("/processor/format", json={"data": [{"collect": result["items_by_source"]}]})
        formatted.raise_for_status()
        format_result = formatted.json()
        messages = format_result["messages"]
        if any(len(message) > 2000 for message in messages):
            findings.append("格式化消息超过 2000 字符")
        if sum(message.count("](") for message in messages) != result["total_items"]:
            findings.append("格式化丢失岗位链接")
        cached_response = await client.post("/collect", json=request)
        cached_response.raise_for_status()
        cached = cached_response.json()
        for source, items in result["items_by_source"].items():
            if items and not cached.get("source_metadata", {}).get(source, {}).get("cache_hit"):
                findings.append(f"{source}: 重复请求未命中缓存")
    output = ROOT / "data" / "jobs_verification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"verified_at": datetime.now(timezone.utc).isoformat(), "request": request,
                                  "collection": result, "formatting": format_result,
                                  "cache_metadata": cached.get("source_metadata"), "findings": findings}, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = ["# 招聘源真实验证结果", "", f"请求：`{json.dumps(request, ensure_ascii=False)}`", "",
                f"采集状态：{result['status']}；岗位：{result['total_items']}；消息：{len(messages)}。", "",
                "## 限制与错误", "", *(result.get("errors") or ["本次无采集错误。"]), "",
                "## 自动检查", "", *(findings or ["通过：条数、去重、必填字段、来源、消息长度、缓存复用。"]), "",
                "## 格式化结果", "", *messages]
    output.with_suffix(".md").write_text("\n\n".join(markdown), encoding="utf-8")
    print(json.dumps({"checks_passed": not findings, "findings": findings, "total_items": result["total_items"],
                      "messages": len(messages), "result_file": str(output)}, ensure_ascii=False))
    return 1 if findings else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--cities", help="51job 城市，用英文逗号分隔，最多20个")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(verify(args)))
