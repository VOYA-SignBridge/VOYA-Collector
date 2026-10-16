"""Ghi hộ chấp thuận: mặc định KHÔNG ghi gì, và cái ghi ra phải tự nhận là ghi hộ.

Lệnh này viết vào bảng bằng chứng, nên hai tính chất được canh chặt hơn phần
còn lại của hệ thống:

* **Không có `--apply` thì không một dòng nào ra đời.** Mặc định là liệt kê.
* **Dòng ghi ra tự nhận diện là ghi hộ.** `source='backfill'` kèm `note` bắt
  buộc. Một dòng ghi hộ trông giống chữ ký thật là bằng chứng giả, kể cả khi
  lời khẳng định đằng sau nó hoàn toàn đúng sự thật.

Bộ test này gọi thẳng `main(argv)` chứ không chạy tiến trình con: đọc được mã
thoát và bắt được stdout mà không phải dựng lại toàn bộ môi trường.
"""

from __future__ import annotations

import uuid

import pytest

from app import legal
from app.cli.backfill_consents import main
from app.storage import metadata_db as db
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture
def published():
    """Một bản `terms` và một bản `privacy` — hai loại bắt buộc.

    Cần cả hai vì lệnh mặc định chạy trên `REQUIRED_AT_REGISTRATION`, và nó
    thoát sớm với mã 3 nếu bất kỳ loại nào chưa công bố.
    """
    created: list[tuple[str, str]] = []
    for kind in legal.REQUIRED_AT_REGISTRATION:
        version = f"bf-{uuid.uuid4().hex[:10]}"
        legal.register_document(kind, version, url=f"/legal/{kind}",
                                body=f"Nội dung {kind}.")
        created.append((kind, version))

    yield {kind: version for kind, version in created}

    with system_scope("test cleanup"):
        for kind, version in reversed(created):
            db._execute("DELETE FROM user_consents WHERE kind = %s AND version = %s",
                        (kind, version))
            db._execute("DELETE FROM legal_documents WHERE kind = %s AND version = %s",
                        (kind, version))


@pytest.fixture
def account():
    from app.auth import create_user

    name = f"bfc{uuid.uuid4().hex[:9]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password="correct horse battery")
    yield user
    from conftest import purge_registered_account

    purge_registered_account(name)


def _live_consents(user_id: str) -> list[dict]:
    with system_scope("test read"):
        return [dict(r) for r in db._fetch_all(
            "SELECT kind, version, source, note FROM user_consents "
            "WHERE user_id = %s AND withdrawn_at IS NULL ORDER BY kind",
            (user_id,))]


class TestTheDefaultIsToWriteNothing:
    def test_withoutApply_noConsentIsWritten(self, published, account):
        """Mặc định là liệt kê. Một lệnh ghi vào bảng bằng chứng không nên ghi
        vì người ta gõ thiếu một cờ."""
        exit_code = main(["--username", account["username"], "--note", "thử"])

        assert exit_code == 0
        assert _live_consents(account["id"]) == []

    def test_withoutApply_theOutputNamesTheAccountsItWouldTouch(
        self, published, account, capsys
    ):
        """Bản chạy thử chỉ có ích nếu nó nói ai sẽ bị chạm tới."""
        main(["--username", account["username"], "--note", "thử"])

        out = capsys.readouterr().out
        assert account["username"] in out
        assert "--apply" in out


class TestApplyRequiresAnExplanation:
    def test_applyWithoutNote_exitsTwoAndWritesNothing(self, published, account):
        exit_code = main(["--username", account["username"], "--apply"])

        assert exit_code == 2
        assert _live_consents(account["id"]) == []

    def test_applyWithABlankNote_isTreatedAsMissing(self, published, account):
        exit_code = main(["--username", account["username"],
                          "--note", "   ", "--apply"])

        assert exit_code == 2


class TestWhatApplyWrites:
    def test_apply_writesOneConsentPerRequiredKind(self, published, account):
        main(["--username", account["username"],
              "--note", "tài khoản nội bộ", "--apply"])

        rows = _live_consents(account["id"])

        assert [r["kind"] for r in rows] == ["privacy", "terms"]

    def test_apply_marksTheRowsAsBackfill(self, published, account):
        """Tính chất trung tâm của cả lệnh."""
        main(["--username", account["username"],
              "--note", "tài khoản nội bộ", "--apply"])

        rows = _live_consents(account["id"])

        assert all(r["source"] == "backfill" for r in rows)

    def test_apply_storesTheNoteOnEveryRow(self, published, account):
        main(["--username", account["username"],
              "--note", "tài khoản do nhóm phát triển tạo", "--apply"])

        rows = _live_consents(account["id"])

        assert all("nhóm phát triển" in r["note"] for r in rows)

    def test_apply_pointsAtTheCurrentVersion(self, published, account):
        main(["--username", account["username"], "--note", "x", "--apply"])

        rows = {r["kind"]: r["version"] for r in _live_consents(account["id"])}

        assert rows == published

    def test_apply_isIdempotent(self, published, account):
        """Chạy lại không được nhân đôi. Chỉ mục `uq_consent_live` sẽ chặn ở
        tầng dưới, nhưng lệnh phải tự lọc trước — nếu không lần chạy thứ hai
        đổ vỡ giữa chừng thay vì báo "không có gì để làm"."""
        main(["--username", account["username"], "--note", "x", "--apply"])

        exit_code = main(["--username", account["username"],
                          "--note", "x", "--apply"])

        assert exit_code == 0
        assert len(_live_consents(account["id"])) == 2

    def test_apply_leavesARealSignatureAlone(self, published, account):
        """Nếu người dùng ĐÃ tự bấm đồng ý, lệnh không được ghi đè chữ ký của họ
        bằng một dòng ghi hộ. Ghi đè ở đây là hạ cấp bằng chứng."""
        legal.record_consent(account["id"], "terms", published["terms"])

        main(["--username", account["username"], "--note", "x", "--apply"])

        rows = {r["kind"]: r["source"] for r in _live_consents(account["id"])}
        assert rows["terms"] == "user"
        assert rows["privacy"] == "backfill"


class TestNarrowingTheScope:
    def test_kindFlag_limitsTheWriteToThatKind(self, published, account):
        main(["--kind", "terms", "--username", account["username"],
              "--note", "x", "--apply"])

        rows = _live_consents(account["id"])

        assert [r["kind"] for r in rows] == ["terms"]


class TestRefusingToRunOnAnUnpublishedDeployment:
    def test_whenNothingIsPublished_exitsThree(self, monkeypatch, account):
        """Không thể đồng ý với một văn bản không tồn tại. Thoát 3 chứ không
        ghi bừa một số hiệu rỗng."""
        monkeypatch.setattr(legal, "current_document", lambda kind: None)

        exit_code = main(["--username", account["username"],
                          "--note", "x", "--apply"])

        assert exit_code == 3
