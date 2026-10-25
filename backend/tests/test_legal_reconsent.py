"""Boundary tests for legal re-consent notifications."""

from __future__ import annotations

from app.modules.legal import reconsent


def test_notify_active_users_delegates_scoped_recipients(monkeypatch) -> None:
    sent = {}
    monkeypatch.setattr(
        reconsent,
        "_fetch_all",
        lambda sql: [{"id": "user-1"}, {"id": "user-2"}],
    )
    monkeypatch.setattr(
        reconsent.notifications,
        "notify_many",
        lambda user_ids, **kwargs: sent.update(user_ids=user_ids, **kwargs) or 2,
    )

    assert reconsent.notify_active_users("privacy", "v3") == 2
    assert sent == {
        "user_ids": ["user-1", "user-2"],
        "kind": "consent",
        "title": "Văn bản pháp lý mới cần bạn đồng ý lại",
        "body": "privacy — bản v3. Chưa ký lại thì một số thao tác sẽ bị tạm dừng.",
        "link": "/settings/consents",
        "severity": "warning",
    }


def test_notify_active_users_does_not_fail_publication(monkeypatch) -> None:
    def fail(_sql):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(reconsent, "_fetch_all", fail)

    assert reconsent.notify_active_users("terms", "v4") == 0
