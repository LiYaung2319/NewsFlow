"""来源会话：启动时本地登录，浏览器确认保存，不提供认证 HTTP 路由。"""

import asyncio
from contextlib import suppress
from html import escape
import json
import logging
import os
import time
from pathlib import Path
import uuid

from playwright.async_api import async_playwright
from collector.parser import SOURCES
from config import settings

logger = logging.getLogger(__name__)


class AuthSessionError(RuntimeError):
    def __init__(self, source, status, message, login_url=None):
        super().__init__(message)
        self.source, self.status, self.login_url = source, status, login_url
        self.retry_after = 0


def auth_config(source):
    auth = SOURCES.get(source, {}).get("auth") or {"mode": "anonymous"}
    path = Path(auth["state_path"]) if auth.get("state_path") else None
    if path and not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    return {**auth, "mode": auth.get("mode", "anonymous"), "state_path": path,
            "login_url": auth.get("login_url")}


def require_state(source):
    config = auth_config(source)
    if config["mode"] == "anonymous":
        return config
    try:
        state = json.loads(config["state_path"].read_text(encoding="utf-8"))
        if not isinstance(state, dict) or not isinstance(state.get("cookies"), list) or not isinstance(state.get("origins"), list):
            raise ValueError("invalid storage state")
        if not state["cookies"] and not state["origins"]:
            raise ValueError("empty storage state")
    except (OSError, ValueError, TypeError, AttributeError):
        raise AuthSessionError(source, "missing", "登录会话缺失或不可读取，请完成本机登录窗口或导入该来源会话文件", config["login_url"]) from None
    return config


def session_version(source):
    """缓存随会话内容更新，文件存在不代表已验证登录。"""
    import hashlib
    config = auth_config(source)
    if config["mode"] == "anonymous":
        return "anonymous"
    try:
        return hashlib.sha256(config["state_path"].read_bytes()).hexdigest()
    except OSError:
        return "missing"


def save_state(path, state):
    """同目录原子替换，失败不覆盖旧会话。"""
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class AuthTaskManager:
    """后台单来源单次提示；取消后不随每次采集反复弹窗。"""

    def __init__(self):
        self._tasks = {}
        self._attempted = set()
        self._records = {}

    async def start_missing(self):
        self._attempted.clear()
        for source in SOURCES:
            try:
                require_state(source)
            except AuthSessionError:
                self.request_login(source)

    def request_login(self, source):
        if auth_config(source)["mode"] == "anonymous":
            return
        record = self._records.get(source)
        if source in self._attempted and record in {"starting", "waiting_user", "saved"}:
            return
        if record == "saved" and auth_config(source)["state_path"].is_file():
            return
        self._attempted.add(source)
        self._records[source] = "starting"
        self._tasks[source] = asyncio.create_task(self._run(source))

    async def close(self):
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    async def _run(self, source):
        config = auth_config(source)
        path = config["state_path"]
        # 本机跨进程锁：服务多 worker 时同来源只显示一个登录窗口。
        lock = path.with_suffix(".lock")
        acquired = False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = self._create_or_reclaim_lock(lock)
        except FileExistsError:
            logger.warning("auth source=%s 已有登录锁；异常退出后可在确认无登录进程时删除 %s", source, lock)
            self._records[source] = "busy"
            return
        except OSError:
            self._records[source] = "failed"
            logger.warning("auth source=%s 无法创建会话目录或登录锁", source)
            return
        os.close(descriptor)
        acquired = True
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=False)
                try:
                    context = await browser.new_context()
                    page = await context.new_page()
                    controls = await context.new_page()
                    closed, confirmed = asyncio.Event(), asyncio.Event()
                    page.on("close", lambda: closed.set())
                    controls.on("close", lambda: closed.set())
                    browser.on("disconnected", lambda: closed.set())

                    async def confirm(binding):
                        # 按钮仅来自本地 about:blank 控制页，网站页面无权保存会话。
                        if binding["frame"] == controls.main_frame and controls.url == "about:blank":
                            confirmed.set()

                    await controls.expose_binding("saveLogin", confirm)
                    await controls.set_content(
                        f"<meta charset='utf-8'><h2>{escape(source)} 登录配置</h2>"
                        "<p>请在另一个标签页完成登录，再回到本页保存。关闭任一标签页即取消。</p>"
                        "<button onclick='window.saveLogin()'>登录完成，保存会话</button>"
                        "<p id='result'>等待登录，最多5分钟。</p>")
                    await page.goto(config["login_url"], wait_until="domcontentloaded", timeout=60000)
                    await page.bring_to_front()
                    logger.info("auth source=%s 请在本机浏览器登录，然后点击登录配置页的保存按钮", source)
                    self._records[source] = "waiting_user"
                    try:
                        async with asyncio.timeout(settings.auth_login_timeout):
                            while not closed.is_set():
                                if confirmed.is_set():
                                    confirmed.clear()
                                    if closed.is_set():
                                        break
                                    state = await context.storage_state()
                                    if closed.is_set():
                                        break
                                    save_state(path, state)
                                    self._records[source] = "saved"
                                    logger.info("auth source=%s 会话已保存，下次采集自动加载", source)
                                    return
                                await asyncio.sleep(0.3)
                        self._records[source] = "cancelled"
                    except TimeoutError:
                        self._records[source] = "timeout"
                finally:
                    with suppress(Exception):
                        await browser.close()
        except asyncio.CancelledError:
            self._records[source] = "cancelled"
            raise
        except Exception as exc:
            self._records[source] = "failed"
            logger.warning("auth source=%s 登录窗口未完成 (%s)，保留现有会话", source, type(exc).__name__)
        finally:
            if acquired:
                lock.unlink(missing_ok=True)
            logger.info("auth source=%s status=%s", source, self._records.get(source))

    @staticmethod
    def _create_or_reclaim_lock(lock):
        """创建登录锁；锁文件为空、进程已退出或超过登录超时则视为遗留锁。"""
        try:
            descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            return descriptor
        except FileExistsError:
            stale = False
            try:
                text = lock.read_text(encoding="ascii").strip()
                pid = int(text) if text else None
                if pid is None:
                    stale = True
                else:
                    try:
                        os.kill(pid, 0)
                    except OSError:
                        stale = True
                if time.time() - lock.stat().st_mtime > settings.auth_login_timeout + 60:
                    stale = True
            except (OSError, ValueError):
                stale = True
            if stale:
                lock.unlink(missing_ok=True)
                descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(descriptor, str(os.getpid()).encode("ascii"))
                return descriptor
            raise


auth_tasks = AuthTaskManager()
