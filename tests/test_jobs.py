"""招聘源回归：离线运行，不请求网站，不发送 Webhook。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx
from parsel import Selector
from pydantic import ValidationError

from collector.job_collector import _collect_pages, capture_list, city_groups, collect_jobs, is_list_response, retry_after
from collector.auth_session import AuthSessionError, auth_config, require_state
from collector.job_state import JobStateStore
from collector.parser import Job51Parser, JobAccessError, ZhaopinParser
from processor.formatter import CollectFormatter
from schemas import JobQuery


def z_record(job_id="J1", **overrides):
    record = {
        "name": "计算机类专业教师", "number": job_id,
        "positionURL": f"https://www.zhaopin.com/jobdetail/{job_id}.htm?refcode=123",
        "companyName": "示例学院", "workCity": "济南", "cityDistrict": "历城", "salary60": "5000-6000元",
        "workingExp": "经验不限", "education": "硕士", "publishTime": "2026-10-13 10:53:00",
        "jobSkillTags": [{"name": "软件工程"}],
        "jobDetailData": {"position": {"desc": {"description": "<p>计算机教学</p><p>五险一金</p>"},
                                        "workLocation": {"workAddress": "济南历城"}}},
    }
    record.update(overrides)
    return record


def z_payload(records, total=100, end=0):
    return {"code": 200, "data": {"list": records, "count": total, "isVerification": 0, "isEndPage": end}}


def f_record(job_id="123", **overrides):
    record = {
        "jobId": job_id, "jobName": "嵌入式软件工程师", "jobHref": f"https://jobs.51job.com/shanghai/{job_id}.html?s=search",
        "fullCompanyName": "示例科技有限公司", "jobAreaLevelDetail": {"cityString": "上海"},
        "jobAreaString": "上海", "provideSalaryString": "2-3万·13薪", "workYearString": "5年及以上",
        "degreeString": "本科", "issueDateString": "2026-10-13 15:19:29",
        "jobDescribe": "开发嵌入式软件\n要求熟悉C++。", "jobTags": ["C++", "嵌入式", "C++"],
        "jobWelfareCodeDataList": [{"chineseTitle": "五险一金"}],
    }
    record.update(overrides)
    return record


def f_payload(records, total=100):
    return {"status": "1", "resultbody": {"job": {"items": records, "totalCount": total}}}


class ParserTests(unittest.TestCase):
    def test_authentication_is_configured_per_source(self):
        self.assertEqual(auth_config("zhaopin")["mode"], "required")
        self.assertEqual(auth_config("51job")["mode"], "required")
        self.assertEqual(auth_config("sina")["mode"], "anonymous")
        with patch("collector.auth_session.Path.read_text", side_effect=FileNotFoundError), self.assertRaises(AuthSessionError) as raised:
            require_state("zhaopin")
        self.assertEqual(raised.exception.status, "missing")
        self.assertIn("zhaopin", raised.exception.login_url)

    def test_zhaopin_json_description_and_tracking_url(self):
        selector = Selector(text=json.dumps(z_payload([z_record()])), type="json")
        item = ZhaopinParser().parse_list(selector)[0].to_dict()
        self.assertEqual(item["text"], "计算机教学\n五险一金")
        self.assertEqual(item["city"], "济南")
        self.assertNotIn("location", item)
        self.assertNotIn("?", item["url"])
        self.assertEqual(item["source"], "zhaopin")
        self.assertEqual(item["kind"], "job")

    def test_job_output_uses_unified_business_fields(self):
        item = ZhaopinParser().parse_payload(z_payload([z_record()]))[0].to_dict()
        self.assertEqual(set(item), {"title", "company", "city", "salary_text", "education",
                                     "text", "published_at", "url", "source", "kind", "job_id"})

    def test_51job_keeps_salary_period_and_missing_values(self):
        items = Job51Parser().parse_payload(f_payload([f_record(), f_record("124", provideSalaryString="")]))
        self.assertEqual(items[0].salary_text, "2-3万·13薪")
        self.assertIsNone(items[1].salary_text)
        self.assertIn("salary_text", items[1].missing_fields)

    def test_retains_non_technical_platform_result(self):
        self.assertEqual(ZhaopinParser().parse_payload(z_payload([z_record(name="空调施工员")]))[0].title, "空调施工员")

    def test_rejects_missing_identity_and_external_links(self):
        records = [z_record(name=" "), z_record(positionURL="javascript:alert(1)"),
                   z_record(positionURL="https://zhaopin.com.evil.test/job/1"), z_record(number="")]
        self.assertEqual(ZhaopinParser().parse_payload(z_payload(records)), [])

    def test_access_errors_and_schema_drift_are_not_empty_success(self):
        with self.assertRaises(JobAccessError):
            ZhaopinParser().parse_payload({"code": 200, "data": {"isVerification": 1, "list": []}})
        with self.assertRaises(JobAccessError):
            Job51Parser().parse_payload({"status": "0", "message": "访问频繁"})
        with self.assertRaises(ValueError):
            Job51Parser().parse_payload({"status": "1", "resultbody": {}})
        with self.assertRaises(ValueError):
            ZhaopinParser().parse_list(Selector(text="<h1>登录</h1>"))

    def test_query_budget_and_unknown_city(self):
        for data in ({"max_pages": 7}, {"limit_per_source": 121}, {"keyword": " "}):
            with self.assertRaises(ValidationError):
                JobQuery(**data)
        with self.assertRaises(ValueError):
            city_groups("51job", JobQuery(cities_51job=["全国"]))
        groups = city_groups("51job", JobQuery(cities_51job=["北京", "上海", "广州", "深圳", "杭州", "武汉"]))
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0][1], "010000,020000,030200,040000,080200")

    def test_only_final_json_and_access_errors_match(self):
        response = SimpleNamespace(url="https://we.51job.com/api/job/search-pc", status=200,
                                   headers={"content-type": "text/html"}, request=SimpleNamespace(method="GET"))
        self.assertFalse(is_list_response(response, "51job"))
        response.headers["content-type"] = "application/json; charset=utf-8"
        self.assertTrue(is_list_response(response, "51job"))
        response.request.method = "OPTIONS"
        self.assertFalse(is_list_response(response, "51job"))
        response.request.method = "GET"
        response.headers["content-type"] = "text/html"
        response.status = 429
        response.headers["retry-after"] = "7200"
        self.assertTrue(is_list_response(response, "51job"))
        self.assertEqual(retry_after(response), 7200)
        response.url = "https://51job.com.other.test/api/job/search-pc"
        self.assertFalse(is_list_response(response, "51job"))

    def test_formatter_separate_messages_and_length_budget(self):
        items = [Job51Parser().parse_payload(f_payload([f_record(str(i), jobName="岗位[*]" * 40)]))[0].to_dict() for i in range(30)]
        messages = CollectFormatter().format({"51job": items, "zhaopin": [ZhaopinParser().parse_payload(z_payload([z_record()]))[0].to_dict()]})
        self.assertTrue(all(len(m) <= 2000 for m in messages))
        self.assertEqual(sum(m.count("https://jobs.51job.com/") for m in messages), 30)
        self.assertTrue(messages[-1].startswith("# 智联招聘"))
        self.assertIn("薪", messages[0])
        self.assertNotIn("开发嵌入式软件", messages[0])


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = JobStateStore(Path(self.temp.name) / "state.db")

    def test_exclusive_source_lock_across_connections(self):
        other = JobStateStore(self.store.path)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda store: store.acquire("51job"), [self.store, other]))
        self.assertEqual(sum(token is not None for token, _ in results), 1)
        self.assertIsNotNone(other.acquire("zhaopin")[0])

    def test_persistent_interval_cooldown_and_expiry(self):
        with patch("collector.job_state.time.time", return_value=1000):
            token, _ = self.store.acquire("51job")
            self.store.mark_request("51job", token)
            self.assertEqual(self.store.delay("51job", token, 12), 12)
            self.store.release("51job", token, 300)
        with patch("collector.job_state.time.time", return_value=1100):
            self.assertIsNone(JobStateStore(self.store.path).acquire("51job")[0])
        with patch("collector.job_state.time.time", return_value=1301):
            self.assertIsNotNone(self.store.acquire("51job")[0])

    def test_cache_expiry(self):
        with patch("collector.job_state.time.time", return_value=1000):
            self.store.cache("a", {"items": [1]}, 30)
            self.assertEqual(self.store.cached("a"), {"items": [1]})
        with patch("collector.job_state.time.time", return_value=1031):
            self.assertIsNone(self.store.cached("a"))


class FakeClient:
    @asynccontextmanager
    async def open_page(self, source=None, authenticated=False):
        yield SimpleNamespace()


class CollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_unlimited_trial_exceeds_budgets_and_waits_between_pages(self):
        payloads = [z_payload([z_record(str(i))]) for i in range(4)] + [z_payload([], total=0)]
        with patch("collector.job_collector.capture_list", new=AsyncMock(side_effect=payloads)), \
             patch("collector.job_collector.check_access", new=AsyncMock()), \
             patch("collector.job_collector.asyncio.sleep", new=AsyncMock()) as sleep, \
             patch("collector.job_collector.random.uniform", return_value=4.5) as random_delay:
            result, _ = await _collect_pages(FakeClient(), "zhaopin", JobQuery(max_pages=1, limit_per_source=1),
                                             [("全国", "489")], Mock(), "token", unlimited_trial=True)
        self.assertEqual(len(result["items"]), 4)
        self.assertEqual(result["metadata"]["pages_fetched"], 5)
        self.assertEqual(result["metadata"]["stop_reason"], "upstream_end")
        self.assertEqual(sleep.await_count, 5)
        self.assertTrue(all(call.args == (4.5,) for call in sleep.await_args_list))
        self.assertTrue(all(call.args == (1, 10) for call in random_delay.call_args_list))

    async def run_pages(self, payloads, query=None):
        store = Mock()
        store.delay.return_value = 0
        with patch("collector.job_collector.capture_list", new=AsyncMock(side_effect=payloads)), \
             patch("collector.job_collector.check_access", new=AsyncMock()):
            return await _collect_pages(FakeClient(), "zhaopin", query or JobQuery(max_pages=3), [("全国", "489")], store, "token")

    async def test_dedup_and_repeated_page_stop(self):
        payload = z_payload([z_record("J1"), z_record("J2")])
        result, _ = await self.run_pages([payload, payload])
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["metadata"]["duplicates_removed"], 2)
        self.assertEqual(result["metadata"]["stop_reason"], "repeated_page")

    async def test_access_restriction_preserves_previous_page(self):
        result, cooldown = await self.run_pages([z_payload([z_record()]), JobAccessError("需要验证")])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["metadata"]["pages_fetched"], 1)
        self.assertEqual(result["metadata"]["stop_reason"], "access_restricted")
        self.assertGreaterEqual(cooldown, 1800)

    async def test_limit_and_invalid_row_accounting(self):
        result, _ = await self.run_pages([z_payload([z_record("J1"), z_record("J2"), z_record(name="")])], JobQuery(limit_per_source=1))
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["metadata"]["limit_dropped"], 1)
        self.assertEqual(result["metadata"]["invalid_items"], 1)
        self.assertEqual(result["metadata"]["stop_reason"], "item_limit")

    async def test_empty_is_success_but_changed_schema_is_failure(self):
        result, _ = await self.run_pages([z_payload([], total=0)])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["metadata"]["stop_reason"], "upstream_end")
        result, _ = await self.run_pages([{"code": 200, "data": {}}])
        self.assertTrue(result["errors"])

    async def test_cache_and_cooldown_make_no_browser_calls(self):
        with TemporaryDirectory() as temp, patch("collector.job_collector.settings.jobs_state_path", str(Path(temp) / "state.db")):
            saved = {"items": [{"job_id": "one"}], "errors": [], "metadata": {"cache_hit": False, "pages_fetched": 1, "stop_reason": "page_budget"}}
            with patch("collector.job_collector._collect_pages", new=AsyncMock(return_value=(saved, 300))) as fetch:
                await collect_jobs(None, "51job")
                second = await collect_jobs(None, "51job")
                third = await collect_jobs(None, "51job", JobQuery(keyword="另一个关键词"))
                self.assertTrue(second["metadata"]["cache_hit"])
                self.assertEqual(third["metadata"]["stop_reason"], "cooldown")
                fetch.assert_awaited_once()

    async def test_response_rejects_wrong_city_and_429(self):
        request = SimpleNamespace(url="https://we.51job.com/api/job/search-pc?keyword=x&jobArea=030500&pageNum=1")
        response = SimpleNamespace(status=200, request=request, json=AsyncMock(return_value={}))

        class Pending:
            async def __aenter__(self):
                future = asyncio.get_running_loop().create_future()
                future.set_result(response)
                return SimpleNamespace(value=future)

            async def __aexit__(self, *args):
                pass

        page = SimpleNamespace(expect_response=lambda *args, **kwargs: Pending())
        with patch("collector.job_collector.check_access", new=AsyncMock()):
            with self.assertRaisesRegex(RuntimeError, "搜索条件"):
                await capture_list(page, "51job", JobQuery(keyword="x"), "010000", 1, AsyncMock())
            response.status = 429
            with self.assertRaises(JobAccessError):
                await capture_list(page, "51job", JobQuery(keyword="x"), "030500", 1, AsyncMock())
        response.json.assert_not_awaited()

    async def test_cancellation_releases_lease_and_preserves_cooldown(self):
        with TemporaryDirectory() as temp:
            state_path = str(Path(temp) / "state.db")
            with patch("collector.job_collector.settings.jobs_state_path", state_path), \
                 patch("collector.job_collector._collect_pages", new=AsyncMock(side_effect=asyncio.CancelledError)):
                with self.assertRaises(asyncio.CancelledError):
                    await collect_jobs(None, "51job")
            store = JobStateStore(state_path)
            with store.connection() as db:
                row = db.execute("SELECT token, lease_until FROM source_state WHERE source='51job'").fetchone()
                self.assertIsNone(row["token"])
                self.assertEqual(row["lease_until"], 0)
            token, retry = store.acquire("51job")
            self.assertIsNone(token)
            self.assertGreaterEqual(retry, 1790)

    async def test_api_preserves_ordinary_and_composite_routing_with_jobs(self):
        from main import app
        from collector.parser import SOURCES

        job = Job51Parser().parse_payload(f_payload([f_record()]))[0].to_dict()
        job_result = {"items": [job], "errors": [], "metadata": {"stop_reason": "page_budget"}}
        for source, keys in (("sina", ["sina"]), ("EverythingSkill", list(SOURCES["EverythingSkill"]["sections"]))):
            with self.subTest(source=source):
                ordinary = {key: [{"title": "原有栏目", "url": "https://example.com/item", "source": key}] for key in keys}
                with patch("collector.services._collect_single", new=AsyncMock(return_value=(ordinary, []))) as single, \
                     patch("collector.services._collect_batch", new=AsyncMock(return_value=(ordinary, []))) as batch, \
                     patch("collector.services.collect_jobs", new=AsyncMock(return_value=job_result)):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                        response = await client.post("/collect", json={"sources": [source, "51job"]})
                    self.assertEqual(response.status_code, 200)
                    data = response.json()
                    self.assertEqual(data["status"], "success")
                    self.assertEqual(data["total_sources"], 2)
                    self.assertEqual(data["total_items"], len(keys) + 1)
                    self.assertEqual(set(data["items_by_source"]), {*keys, "51job"})
                    for key in keys:
                        self.assertEqual(data["items_by_source"][key], ordinary[key])
                    if source == "sina":
                        single.assert_awaited_once()
                        batch.assert_not_awaited()
                    else:
                        single.assert_not_awaited()
                        batch.assert_awaited_once()
                        self.assertEqual(set(batch.await_args.args[1]), set(keys))

    async def test_api_partial_success_keeps_other_source(self):
        from main import app
        good = {"items": [f_record()], "errors": [], "metadata": {"stop_reason": "page_budget"}}
        bad = {"items": [], "errors": ["zhaopin 需要验证"], "metadata": {"stop_reason": "access_restricted"}}
        async def fake_collect(client, source, query):
            return good if source == "51job" else bad
        with patch("collector.services.collect_jobs", side_effect=fake_collect):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/collect", json={"sources": ["zhaopin", "51job"]})
                data = response.json()
                self.assertEqual(data["status"], "partial_success")
                self.assertEqual(data["total_sources"], 2)
                self.assertEqual(data["total_items"], 1)
                self.assertEqual(data["items_by_source"]["zhaopin"], [])
                self.assertIn("51job", data["source_metadata"])

    async def test_auth_routes_removed(self):
        from main import app
        self.assertFalse(any(route.path.startswith("/collect/auth/") for route in app.routes))

    async def test_startup_checks_sessions_without_waiting_for_login(self):
        from collector.auth_session import AuthTaskManager
        manager = AuthTaskManager()
        async def waiting(source):
            await asyncio.Event().wait()
        with patch("collector.auth_session.require_state", side_effect=lambda s: (_ for _ in ()).throw(AuthSessionError(s, "missing", "missing")) if s == "zhaopin" else {}), \
             patch.object(manager, "_run", side_effect=waiting) as run:
            await manager.start_missing()
            manager.request_login("zhaopin")
            await asyncio.sleep(0)
            run.assert_awaited_once_with("zhaopin")
            await manager.close()
            manager.request_login("zhaopin")
            self.assertEqual(len(manager._tasks), 0)

    async def test_session_save_is_atomic_and_changes_cache_version(self):
        from collector.auth_session import save_state, session_version
        with TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            config = {"mode": "required", "state_path": path}
            with patch("collector.auth_session.auth_config", return_value=config):
                save_state(path, {"cookies": [], "origins": [{"origin": "https://example.com"}]})
                before = session_version("test")
                with patch("collector.auth_session.Path.replace", side_effect=OSError):
                    with self.assertRaises(OSError):
                        save_state(path, {"cookies": [], "origins": []})
                self.assertEqual(session_version("test"), before)
                save_state(path, {"cookies": [], "origins": [{"origin": "https://new.example.com"}]})
                self.assertNotEqual(session_version("test"), before)

    async def test_login_window_close_and_timeout_never_save(self):
        from collector.auth_session import AuthTaskManager
        for outcome in ("cancelled", "timeout", "saved"):
            with self.subTest(outcome=outcome), TemporaryDirectory() as temp:
                path = Path(temp) / "state.json"
                path.write_text("old state", encoding="utf-8")
                handlers = {}
                control = SimpleNamespace(main_frame=object(), url="about:blank", on=Mock(),
                                          set_content=AsyncMock(), expose_binding=AsyncMock())
                page = SimpleNamespace(on=lambda name, callback: handlers.update({name: callback}),
                                       bring_to_front=AsyncMock())
                async def navigate(*args, **kwargs):
                    if outcome == "cancelled":
                        handlers["close"]()
                    elif outcome == "saved":
                        callback = control.expose_binding.await_args.args[1]
                        await callback({"frame": control.main_frame})
                page.goto = AsyncMock(side_effect=navigate)
                context = SimpleNamespace(new_page=AsyncMock(side_effect=[page, control]),
                                          storage_state=AsyncMock(return_value={"cookies": [], "origins": []}))
                browser = SimpleNamespace(new_context=AsyncMock(return_value=context), on=Mock(), close=AsyncMock())
                playwright = SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)))
                @asynccontextmanager
                async def fake_playwright():
                    yield playwright
                manager = AuthTaskManager()
                with patch("collector.auth_session.async_playwright", fake_playwright), \
                     patch("collector.auth_session.auth_config", return_value={"state_path": path, "login_url": "https://example.com"}), \
                     patch("collector.auth_session.settings.auth_login_timeout", 0.01):
                    await manager._run("test")
                self.assertEqual(manager._records["test"], outcome)
                if outcome != "saved":
                    self.assertEqual(path.read_text(encoding="utf-8"), "old state")
                    context.storage_state.assert_not_awaited()
                else:
                    context.storage_state.assert_awaited_once()
                self.assertFalse(path.with_suffix(".lock").exists())
                browser.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
