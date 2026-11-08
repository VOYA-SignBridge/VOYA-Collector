"""Seed vai/quyền phải chạy TRƯỚC bước backfill "mọi tài khoản thuộc cộng đồng".

Lỗi 18/10/2026: nâng cấp DB cũ (11 tài khoản, chưa từng có authz) lên v8 dừng ở
`migration:v6:moi-tai-khoan-deu-thuoc-cong-dong` — backfill gán vai bằng JOIN vào
`roles`, mà `roles` còn rỗng vì seed chạy sau cả danh sách DDL. Trên DB dựng từ số
không không có tài khoản nào nên hậu điều kiện luôn đạt và lỗi không lộ ra.

Kiểm bằng thứ tự gọi, không cần DB: thứ tự là toàn bộ hợp đồng.
"""
from __future__ import annotations

from app.storage import metadata_db as mdb
from app.storage.authz_schema import (
    _SQL_BACKFILL_COMMUNITY_MEMBERSHIP,
    _SQL_BACKFILL_COMMUNITY_ROLE,
    AUTHZ_DDL_STATEMENTS,
)


def _record(monkeypatch):
    events: list = []
    monkeypatch.setattr(mdb, "_run_ddl", lambda cur, stmts, kind: events.append(("ddl", kind, list(stmts))))
    monkeypatch.setattr(mdb, "_seed_authorization", lambda cur: events.append(("seed",)))
    return events


def test_seed_runs_between_ddl_and_backfill(monkeypatch):
    events = _record(monkeypatch)
    mdb._run_authz_ddl(object(), AUTHZ_DDL_STATEMENTS)

    kinds = [e[0] if e[0] == "seed" else e[1] for e in events]
    assert kinds == ["authz", "seed", "authz backfill"]

    before, _, after = events
    assert _SQL_BACKFILL_COMMUNITY_MEMBERSHIP not in before[2]
    assert _SQL_BACKFILL_COMMUNITY_ROLE not in before[2]
    assert after[2][0] == _SQL_BACKFILL_COMMUNITY_MEMBERSHIP
    assert _SQL_BACKFILL_COMMUNITY_ROLE in after[2]


def test_no_statement_is_lost_or_reordered_by_the_split(monkeypatch):
    events = _record(monkeypatch)
    mdb._run_authz_ddl(object(), AUTHZ_DDL_STATEMENTS)
    flat = [s for e in events if e[0] == "ddl" for s in e[2]]
    assert flat == list(AUTHZ_DDL_STATEMENTS)


def test_list_without_backfill_is_run_whole_and_not_seeded_here(monkeypatch):
    # Đường khởi động có thể lọc mất câu backfill; khi đó không có gì để canh thứ
    # tự, và `_apply_schema` vẫn seed sau danh sách như trước.
    events = _record(monkeypatch)
    rest = [s for s in AUTHZ_DDL_STATEMENTS if s != _SQL_BACKFILL_COMMUNITY_MEMBERSHIP]
    mdb._run_authz_ddl(object(), rest)
    assert [e[0] if e[0] == "seed" else e[1] for e in events] == ["authz"]
    assert events[0][2] == rest
