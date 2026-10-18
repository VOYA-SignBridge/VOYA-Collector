"""The metadata pool must QUEUE borrowers, not fail them.

psycopg2's ThreadedConnectionPool raises `PoolError("connection pool exhausted")`
the moment `maxconn` connections are out. FastAPI runs sync endpoints on ~40
threads per worker, so 30 parallel requests turned into 500s (measured
16/10/2026). No database needed: the pool is replaced by a counting fake.
"""
from __future__ import annotations

import threading
import time

import pytest
from psycopg2 import pool as pg_pool

from app.storage import postgres_connection as pc


class FakePool:
    def __init__(self, maxconn):
        self.maxconn = maxconn
        self.out = 0
        self.peak = 0
        self.lock = threading.Lock()

    def getconn(self):
        with self.lock:
            if self.out >= self.maxconn:
                raise pg_pool.PoolError("connection pool exhausted")
            self.out += 1
            self.peak = max(self.peak, self.out)
            return object()

    def putconn(self, conn, close=False):
        with self.lock:
            self.out -= 1


@pytest.fixture
def fake_pool(monkeypatch):
    fake = FakePool(maxconn=2)
    monkeypatch.setattr(pc, "_pool", None)
    monkeypatch.setattr(pc, "_pool_pid", None)
    monkeypatch.setattr(pc, "_pool_slots", None)
    monkeypatch.setattr(pc, "_build_pool", lambda: fake)
    monkeypatch.setattr(pc.settings, "db_pool_wait_seconds", 2.0, raising=False)
    return fake


def test_more_borrowers_than_connections_all_succeed(fake_pool):
    errors, done = [], []

    def borrow():
        try:
            conn = pc.get_pooled_conn()
            time.sleep(0.05)
            pc.put_pooled_conn(conn)
            done.append(1)
        except Exception as exc:  # pragma: no cover - the failure being guarded
            errors.append(exc)

    threads = [threading.Thread(target=borrow) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(done) == 12
    assert fake_pool.peak <= 2  # Never asked psycopg2 for more than maxconn.


def test_waiting_is_bounded(fake_pool, monkeypatch):
    monkeypatch.setattr(pc.settings, "db_pool_wait_seconds", 0.2, raising=False)
    held = [pc.get_pooled_conn(), pc.get_pooled_conn()]
    started = time.monotonic()
    with pytest.raises(pg_pool.PoolError, match="within"):
        pc.get_pooled_conn()
    assert time.monotonic() - started < 1.5
    for conn in held:
        pc.put_pooled_conn(conn)
    pc.put_pooled_conn(pc.get_pooled_conn())  # Slots were all returned.


def test_failed_getconn_does_not_leak_a_slot(fake_pool, monkeypatch):
    monkeypatch.setattr(fake_pool, "getconn", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    for _ in range(5):
        with pytest.raises(RuntimeError):
            pc.get_pooled_conn()
    assert pc._pool_slots.acquire(timeout=0)  # Still free.
    pc._pool_slots.release()


def test_failed_putconn_still_frees_the_slot(fake_pool, monkeypatch):
    conn = pc.get_pooled_conn()
    conn2 = pc.get_pooled_conn()

    def boom(*_a, **_k):
        raise RuntimeError("putconn failed")

    monkeypatch.setattr(fake_pool, "putconn", boom)
    pc.put_pooled_conn(conn)
    assert pc._pool_slots.acquire(timeout=0)
    pc._pool_slots.release()
    monkeypatch.undo()
