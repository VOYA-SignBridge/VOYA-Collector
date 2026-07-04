"""Component test — seed idempotency (GĐ 1 gate: chạy 2 lần không nhân đôi)."""
from app.orm.seed import run_seed


def test_seed_runs_twice_without_duplicating_rows():
    run_seed()  # may create on a fresh DB — don't assert counts here
    second = run_seed()
    assert all(v == 0 for v in second.values()), (
        f"seed lần 2 vẫn tạo dòng mới: {second}"
    )
