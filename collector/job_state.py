"""招聘源的跨请求/进程限速、租约和短期结果缓存（仅本机 SQLite）。"""

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
import uuid


class JobStateStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS source_state (
                source TEXT PRIMARY KEY, token TEXT, lease_until REAL NOT NULL DEFAULT 0,
                last_request REAL NOT NULL DEFAULT 0, next_run REAL NOT NULL DEFAULT 0)""")
            db.execute("""CREATE TABLE IF NOT EXISTS job_cache (
                cache_key TEXT PRIMARY KEY, expires REAL NOT NULL, payload TEXT NOT NULL)""")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(str(self.path), timeout=5)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def cached(self, key):
        with self.connection() as db:
            row = db.execute("SELECT payload FROM job_cache WHERE cache_key=? AND expires>?", (key, time.time())).fetchone()
        return json.loads(row["payload"]) if row else None

    def acquire(self, source):
        """独占一个站点；冷却期间不排队，不向上游发送请求。"""
        now = time.time()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO source_state(source) VALUES (?)", (source,))
            row = db.execute("SELECT * FROM source_state WHERE source=?", (source,)).fetchone()
            retry_at = max(row["lease_until"], row["next_run"])
            if retry_at > now:
                return None, max(1, int(retry_at - now) + 1)
            token = uuid.uuid4().hex
            db.execute("UPDATE source_state SET token=?, lease_until=? WHERE source=?", (token, now + 600, source))
            return token, 0

    def delay(self, source, token, interval):
        with self.connection() as db:
            row = db.execute("SELECT last_request, token FROM source_state WHERE source=?", (source,)).fetchone()
        if row is None or row["token"] != token:
            raise RuntimeError("招聘源租约失效")
        return max(0.0, row["last_request"] + interval - time.time())

    def mark_request(self, source, token):
        now = time.time()
        with self.connection() as db:
            result = db.execute(
                "UPDATE source_state SET last_request=?, lease_until=? WHERE source=? AND token=?",
                (now, now + 600, source, token),
            )
            if result.rowcount != 1:
                raise RuntimeError("招聘源租约失效")

    def release(self, source, token, cooldown):
        with self.connection() as db:
            db.execute(
                "UPDATE source_state SET token=NULL, lease_until=0, next_run=? WHERE source=? AND token=?",
                (time.time() + cooldown, source, token),
            )

    def cache(self, key, payload, ttl):
        now = time.time()
        with self.connection() as db:
            db.execute("DELETE FROM job_cache WHERE expires<=?", (now,))
            db.execute(
                "INSERT OR REPLACE INTO job_cache(cache_key, expires, payload) VALUES (?, ?, ?)",
                (key, now + ttl, json.dumps(payload, ensure_ascii=False)),
            )
