"""免登录招聘列表：仅访问正常搜索页面，捕获页面自身的响应并低频翻页。"""

import asyncio
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from itertools import count
import json
import logging
import random
from urllib.parse import parse_qs, urlencode, urlsplit

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from collector.job_state import JobStateStore
from collector.auth_session import AuthSessionError, auth_config, session_version, auth_tasks
from collector.parser import SOURCES, JobAccessError
from config import settings
from schemas import JobQuery

logger = logging.getLogger(__name__)

# 站点城市码；全国不在 51job 当前城市选择器内，不能用 000000 冒充全国。
# 来源：https://js.51jobcdn.com/in/js/2023/dd/dd_city.json（2026-10-13 核对）。
CITY_CODES = {
    "北京": "010000", "上海": "020000", "广州": "030200", "深圳": "040000", "杭州": "080200",
    "武汉": "180200", "成都": "090200", "南京": "070200", "西安": "200200", "重庆": "060000",
    "苏州": "070300", "长沙": "190200", "合肥": "150200", "郑州": "170200", "天津": "050000",
    "济南": "120200", "青岛": "120300", "厦门": "110300", "福州": "110200", "珠海": "030500",
}
ENDPOINTS = {"zhaopin": "/c/i/search/positions", "51job": "/api/job/search-pc"}


def city_groups(source, query):
    if source == "zhaopin":
        return [("全国", "489")]
    unsupported = [city for city in query.cities_51job if city not in CITY_CODES]
    if unsupported:
        raise ValueError("51job 尚未配置城市: " + "、".join(unsupported))
    cities = query.cities_51job
    return [("、".join(cities[i:i + 5]), ",".join(CITY_CODES[c] for c in cities[i:i + 5]))
            for i in range(0, len(cities), 5)]


def request_filters(request, source):
    if source == "zhaopin":
        try:
            body = request.post_data_json or {}
        except (ValueError, TypeError):
            return None
        if not isinstance(body, dict):
            return None
        return body.get("S_SOU_FULL_INDEX"), str(body.get("S_SOU_WORK_CITY", "")), str(body.get("pageIndex", ""))
    params = parse_qs(urlsplit(request.url).query)
    return tuple(params.get(k, [""])[0] for k in ("keyword", "jobArea", "pageNum"))


def matches_endpoint(response, source):
    parsed = urlsplit(response.url)
    domain = "zhaopin.com" if source == "zhaopin" else "51job.com"
    host = parsed.hostname or ""
    return parsed.path == ENDPOINTS[source] and (host == domain or host.endswith("." + domain))


def is_list_response(response, source):
    """排除同 URL 的 OPTIONS 预检和非 JSON，等待页面真正的列表请求。"""
    method = "POST" if source == "zhaopin" else "GET"
    return matches_endpoint(response, source) and response.request.method == method and (
        response.status >= 400 or "json" in response.headers.get("content-type", "").lower()
    )


def retry_after(response):
    value = getattr(response, "headers", {}).get("retry-after", "")
    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        try:
            return max(0, int((parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()) + 1)
        except (ValueError, TypeError, OverflowError):
            return 0


async def check_access(page):
    title = (await page.title()).lower()
    if any(marker in title for marker in ("security verification", "访问验证", "滑动验证", "安全验证", "验证码")):
        raise JobAccessError("页面要求安全验证，已停止采集")
    if "passport." in urlsplit(page.url).netloc:
        raise JobAccessError("页面跳转登录，已停止采集")
    # 不把正常页头/页脚的“登录”链接误识别为访问限制。
    welcome = page.get_by_text("欢迎来到智联招聘", exact=True)
    if await welcome.count() and await welcome.first.is_visible():
        raise JobAccessError("智联显示登录弹窗，已停止继续翻页")


async def capture_list(page, source, query, area, page_number, action):
    """监听先于页面操作；只接收指定关键词、地区和页码的列表。"""
    await check_access(page)
    try:
        async with page.expect_response(lambda r: is_list_response(r, source), timeout=settings.jobs_response_timeout) as pending:
            await action()
        response = await pending.value
    except PlaywrightTimeoutError:
        await check_access(page)
        raise RuntimeError("未在时限内取得列表响应；已停止，不自动重试") from None
    if response.status in (401, 403, 429):
        raise JobAccessError(f"上游 HTTP {response.status}，已停止并进入冷却", retry_after(response))
    if response.status >= 400:
        raise RuntimeError(f"上游 HTTP {response.status}，已停止")
    expected = (query.keyword, area, str(page_number))
    actual = request_filters(response.request, source)
    if actual != expected:
        raise RuntimeError(f"搜索条件与请求不一致（关键词/城市/页码），拒绝混入默认地区数据: {actual}")
    try:
        return await asyncio.wait_for(response.json(), timeout=15)
    except ValueError as exc:
        raise RuntimeError(f"列表 JSON 解码失败（{response.request.method}, HTTP {response.status}, {type(exc).__name__}），已停止") from None
    except asyncio.TimeoutError:
        raise RuntimeError("列表 JSON 读取超时，已停止") from None


async def _collect_pages(client, source, query, groups, store, token, *, unlimited_trial=False):
    parser = SOURCES[source]["parser"]
    items = []
    seen_ids, seen_urls = set(), set()
    metadata = {
        "keyword": query.keyword, "authenticated": False, "filter_mode": "platform_results",
        "requested_scope": "全国" if source == "zhaopin" else query.cities_51job,
        "national_coverage": source == "zhaopin", "full_market_coverage": False,
        "pages_fetched": 0, "raw_items": 0, "duplicates_removed": 0, "invalid_items": 0,
        "limit_dropped": 0, "groups": [], "cache_hit": False, "stop_reason": "page_budget",
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
    errors = []
    cooldown = settings.jobs_run_cooldown
    # 分配固定总页预算，优先让各城市组获得至少一页，避免无限扩张请求量。
    group_limit = len(groups) if unlimited_trial else min(len(groups), query.max_pages)
    if unlimited_trial:
        metadata["trial_policy"] = {"max_pages": None, "limit_per_source": None, "page_delay_seconds": [1, 10]}
    metadata["unvisited_groups"] = [g[0] for g in groups[group_limit:]]
    for index, (label, area) in enumerate(groups[:group_limit]):
        if not unlimited_trial and len(items) >= query.limit_per_source:
            metadata["unvisited_groups"].extend(g[0] for g in groups[index:group_limit])
            break
        remaining = query.max_pages - metadata["pages_fetched"]
        budget = max(1, remaining // (group_limit - index))
        group = {"scope": label, "area_code": area, "pages": 0, "raw_items": 0, "upstream_total": None, "stop_reason": "page_budget"}
        metadata["groups"].append(group)
        try:
            async with client.open_page(source=source) as page:
                metadata["authenticated"] = auth_config(source)["mode"] != "anonymous"
                params = {"jl": area, "kw": query.keyword} if source == "zhaopin" else {"keyword": query.keyword, "jobArea": area}
                url = SOURCES[source]["home_url"] + "?" + urlencode(params)
                for page_number in (count(1) if unlimited_trial else range(1, budget + 1)):
                    if unlimited_trial:
                        # 从上页处理完成后开始计时，确保翻页前完整等待随机间隔。
                        await asyncio.sleep(random.uniform(1, 10))
                    else:
                        interval = max(10.0, settings.jobs_request_interval) + random.uniform(0, 3)
                        await asyncio.sleep(store.delay(source, token, interval))
                    store.mark_request(source, token)

                    async def action():
                        if page_number == 1:
                            navigation = await page.goto(url, wait_until="domcontentloaded", timeout=settings.jobs_response_timeout)
                            if navigation and navigation.status in (401, 403, 429):
                                raise JobAccessError(f"搜索页面 HTTP {navigation.status}", retry_after(navigation))
                            if navigation and navigation.status >= 400:
                                raise RuntimeError(f"搜索页面 HTTP {navigation.status}")
                        elif source == "zhaopin":
                            await page.get_by_text("下一页", exact=True).click(timeout=5000)
                        else:
                            await page.locator(".el-pagination .btn-next").click(timeout=5000)

                    payload = await capture_list(page, source, query, area, page_number, action)
                    records, total, is_end = parser.page_data(payload)
                    parsed = parser.parse_payload(payload)
                    group["upstream_total"] = total
                    group["pages"] += 1
                    group["raw_items"] += len(records)
                    metadata["pages_fetched"] += 1
                    metadata["raw_items"] += len(records)
                    metadata["invalid_items"] += len(records) - len(parsed)
                    if records and not parsed:
                        raise RuntimeError("列表非空但没有有效岗位，疑似字段结构变化")
                    new_count = 0
                    for item in parsed:
                        if item.job_id in seen_ids or item.url in seen_urls:
                            metadata["duplicates_removed"] += 1
                            continue
                        seen_ids.add(item.job_id)
                        seen_urls.add(item.url)
                        new_count += 1
                        if unlimited_trial or len(items) < query.limit_per_source:
                            items.append(item.to_dict())
                        else:
                            metadata["limit_dropped"] += 1
                    reason = None
                    logger.info("job_page source=%s page=%d items=%d unlimited_trial=%s", source, page_number, len(items), unlimited_trial)
                    if not unlimited_trial and len(items) >= query.limit_per_source:
                        reason = "item_limit"
                    elif not records:
                        reason = "empty_page"
                    elif not new_count:
                        reason = "repeated_page"
                    elif is_end or (total is not None and group["raw_items"] >= total):
                        reason = "upstream_end"
                    if reason:
                        group["stop_reason"] = reason
                        break
                # 检查访问限制，不主动请求额外页面。
                if group["stop_reason"] == "page_budget":
                    await check_access(page)
        except AuthSessionError as exc:
            cooldown = 0  # 未访问网站，登录后可立即采集。
            group["stop_reason"] = "auth_required" if exc.status == "missing" else "auth_failed"
            errors.append(f"{source} {exc}")
            metadata["auth_status"] = exc.status
            metadata["login_url"] = exc.login_url
            metadata["unvisited_groups"].extend(g[0] for g in groups[index + 1:group_limit])
            break
        except Exception as exc:
            limited = isinstance(exc, JobAccessError)
            group["stop_reason"] = "access_restricted" if limited else "fetch_failed"
            if limited and "登录" in str(exc) and auth_config(source)["mode"] != "anonymous":
                metadata["authenticated"] = False
                metadata["auth_status"] = "expired"
                auth_tasks.request_login(source)
            errors.append(f"{source} {str(exc)}")
            cooldown = max(settings.jobs_block_cooldown, 1800, exc.retry_after) if limited else max(settings.jobs_run_cooldown, 300)
            metadata["unvisited_groups"].extend(g[0] for g in groups[index + 1:group_limit])
            break
    reasons = [g["stop_reason"] for g in metadata["groups"]]
    if errors:
        metadata["stop_reason"] = reasons[-1]
    elif "item_limit" in reasons:
        metadata["stop_reason"] = "item_limit"
    elif reasons and all(reason in ("upstream_end", "empty_page") for reason in reasons):
        metadata["stop_reason"] = "upstream_end"
    elif "repeated_page" in reasons:
        metadata["stop_reason"] = "repeated_page"
    metadata["returned_items"] = len(items)
    metadata["observed_cities"] = sorted({item["city"] for item in items if item.get("city")})
    fields = ("title", "company", "city", "salary_text", "education", "text", "published_at", "url")
    metadata["missing_fields"] = dict(Counter(key for item in items for key in fields if not item.get(key)))
    metadata["field_coverage"] = {key: {"present": sum(bool(i.get(key)) for i in items), "total": len(items)} for key in fields}
    metadata["complete_within_query"] = (not errors and not metadata["unvisited_groups"]
                                         and metadata["stop_reason"] == "upstream_end"
                                         and metadata["invalid_items"] == 0)
    metadata["retry_after_seconds"] = cooldown
    return {"items": items, "errors": errors, "metadata": metadata}, cooldown


async def collect_jobs(client, source, query=None):
    query = query or JobQuery()
    try:
        groups = city_groups(source, query)
        store = JobStateStore(settings.jobs_state_path)
        cache_key = hashlib.sha256(("jobs-v2:" + source + session_version(source) + query.model_dump_json()).encode()).hexdigest()
        cached = store.cached(cache_key)
        if cached is not None:
            cached["metadata"]["cache_hit"] = True
            return cached
        token, retry = store.acquire(source)
        if token is None:
            return {"items": [], "errors": [f"{source} 正在采集或冷却中，请在 {retry} 秒后再试"],
                    "metadata": {"keyword": query.keyword, "stop_reason": "cooldown", "retry_after_seconds": retry,
                                 "pages_fetched": 0, "cache_hit": False, "full_market_coverage": False}}
    except Exception as exc:
        return {"items": [], "errors": [f"{source} 配置/状态存储错误: {exc}"],
                "metadata": {"stop_reason": "configuration_error", "pages_fetched": 0}}
    cooldown = max(settings.jobs_block_cooldown, 1800)
    try:
        result, cooldown = await _collect_pages(client, source, query, groups, store, token)
        if result["items"] or not result["errors"]:
            store.cache(cache_key, result, settings.jobs_cache_ttl)
        logger.info("collect_jobs source=%s pages=%d items=%d stop=%s", source,
                    result["metadata"]["pages_fetched"], len(result["items"]), result["metadata"]["stop_reason"])
        return result
    finally:
        # 包括取消/超时：释放租约并保留冷却，防止调用方取消后立即重刷。
        store.release(source, token, cooldown)
