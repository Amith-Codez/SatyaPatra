"""Background verification jobs.

  production: Redis + RQ workers (`rq worker satyapatra`), scaled out in approval season
  laptop demo: an in-process thread pool (no Redis needed)
The API returns immediately with a job id; the screen polls the document's status.
"""
import os
from concurrent.futures import ThreadPoolExecutor

REDIS_URL = os.environ.get("REDIS_URL")
_pool = ThreadPoolExecutor(max_workers=int(os.environ.get("SATYA_WORKERS", "3")))
_queue = None


def _q():
    global _queue
    if _queue is None:
        from redis import Redis
        from rq import Queue
        _queue = Queue("satyapatra", connection=Redis.from_url(REDIS_URL), default_timeout=600)
    return _queue


def submit(fn, *args):
    if REDIS_URL:
        return _q().enqueue(fn, *args).id
    _pool.submit(fn, *args)
    return "local"


def backend_name():
    return "Redis + RQ workers" if REDIS_URL else "In-process workers (demo mode)"
