"""Storage layer. One codebase, two backends, chosen by DATABASE_URL:

  production / pilot:  postgresql+psycopg://...   (PostgreSQL 16 + PostGIS, see docker-compose.yml)
  laptop demo:          sqlite:///data/satyapatra.db (default, zero setup)

SQL is written once with '?' placeholders and translated for the driver in use.
"""
import json
import os
import threading
from contextlib import contextmanager

from sqlalchemy import create_engine, text

from .config import DB_PATH

URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")
IS_PG = URL.startswith("postgresql")
engine = create_engine(URL, pool_pre_ping=True, future=True,
                       connect_args={} if IS_PG else {"check_same_thread": False})
_lock = threading.RLock()

AUTO = "BIGSERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
JSON = "JSONB" if IS_PG else "TEXT"

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS institutions(
      id TEXT PRIMARY KEY, name TEXT, region TEXT, address TEXT, campus_geojson TEXT,
      claimed_builtup_m2 DOUBLE PRECISION, approved_intake INTEGER, synthetic INTEGER DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS applications(
      id TEXT PRIMARY KEY, institution_id TEXT REFERENCES institutions(id), category TEXT, cycle TEXT,
      submitted_at TEXT, status TEXT, risk INTEGER, summary TEXT)""",
    """CREATE TABLE IF NOT EXISTS documents(
      id TEXT PRIMARY KEY, application_id TEXT REFERENCES applications(id), filename TEXT, path TEXT,
      sha256 TEXT, mime TEXT, doc_type TEXT, pages INTEGER, fields TEXT, status TEXT, risk INTEGER,
      created_at TEXT, truth TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS checks(
      id {AUTO}, document_id TEXT, engine TEXT, code TEXT, title TEXT, outcome TEXT, severity TEXT,
      weight INTEGER, detail TEXT, evidence TEXT, rule_ref TEXT, created_at TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS memory(
      id {AUTO}, kind TEXT, value TEXT, institution_id TEXT, document_id TEXT, note TEXT)""",
    "CREATE INDEX IF NOT EXISTS memory_kv ON memory(kind, value)",
    "CREATE INDEX IF NOT EXISTS checks_doc ON checks(document_id)",
    "CREATE INDEX IF NOT EXISTS docs_app ON documents(application_id)",
    """CREATE TABLE IF NOT EXISTS confirmations(
      token TEXT PRIMARY KEY, document_id TEXT, issuer_id TEXT, reference TEXT, state TEXT,
      created_at TEXT, answered_at TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS audit(
      seq {AUTO}, ts TEXT, actor TEXT, action TEXT, subject TEXT, payload TEXT, prev_hash TEXT, hash TEXT)""",
]


def _sql(s):
    return s.replace("?", "%s") if IS_PG else s


class _Conn:
    """Small wrapper so callers can use c.execute(sql, args) on either backend."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, args=()):
        return self.raw.exec_driver_sql(_sql(sql), tuple(args))


def init():
    with engine.begin() as c:
        for stmt in SCHEMA:
            c.exec_driver_sql(stmt)


init()


@contextmanager
def tx():
    with _lock, engine.begin() as raw:
        yield _Conn(raw)


def q(sql, args=()):
    with _lock, engine.connect() as raw:
        res = raw.exec_driver_sql(_sql(sql), tuple(args))
        return [dict(r._mapping) for r in res.fetchall()]


def q1(sql, args=()):
    rows = q(sql, args)
    return rows[0] if rows else None


def j(x):
    return json.dumps(x, ensure_ascii=False, default=str)


def unj(s, default=None):
    if s is None:
        return default
    if isinstance(s, (dict, list)):
        return s
    try:
        return json.loads(s)
    except Exception:
        return default


def reset():
    with tx() as c:
        for t in ("checks", "memory", "confirmations", "audit", "documents", "applications", "institutions"):
            c.execute(f"DELETE FROM {t}")
        if not IS_PG:
            c.execute("DELETE FROM sqlite_sequence")


def backend_name():
    return "PostgreSQL" if IS_PG else "SQLite (demo mode)"
