"""Kho tài liệu trên đĩa: địa chỉ sinh từ nội dung, ghi nguyên tử, dọn rác an toàn.

Ba nhóm khẳng định:

* **Địa chỉ hoá.** Tên tệp phải là băm nội dung, và hai lần ghi cùng nội dung
  phải cho ra cùng một tệp. Đây là thứ khiến một bản văn không thể bị tráo lặng
  lẽ, nên nó được kiểm trước mọi thứ khác.
* **An toàn đường dẫn.** Khoá đọc từ cơ sở dữ liệu không phải dữ liệu tin được.
* **Dọn rác không ăn nhầm.** Cửa sổ tuổi tồn tại để che đúng một khoảng: giữa
  lúc ghi tệp và lúc ghi hàng, blob hợp lệ nhưng chưa ai trỏ tới.

Mọi test dùng một gốc kho TẠM qua `LEGAL_STORE_ROOT`. Không có nó, bộ test ghi
vào `dataset/legal` thật — và bài học đó đã trả giá ở chỗ khác trong dự án này.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from app import legal_store


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    """Gốc kho riêng cho mỗi test.

    `store_root()` đọc biến môi trường ở MỖI lần gọi thay vì chốt lúc import,
    chính là để fixture này hoạt động. Một hằng số cấp module sẽ giữ giá trị
    nạp lần đầu và mọi test sau đó ghi vào kho thật.
    """
    monkeypatch.setenv("LEGAL_STORE_ROOT", str(tmp_path / "legal"))
    return tmp_path / "legal"


BODY = "# Điều khoản\n\nMột đoạn văn.\n"


class TestTheAddressComesFromTheContent:
    def test_write_putsTheDigestInTheFilename(self, temp_store):
        key, digest, _ = legal_store.write("terms", BODY)

        assert digest in key
        assert key.endswith(".md")

    def test_write_shardsByTheFirstTwoHexCharacters(self, temp_store):
        """Thói quen của Git và mọi kho định-địa-chỉ-bằng-nội-dung: một thư mục
        phẳng vài nghìn mục làm chậm `readdir`."""
        key, digest, _ = legal_store.write("terms", BODY)

        assert key == f"terms/{digest[:2]}/{digest}.md"

    def test_writingTheSameContentTwice_producesOneFile(self, temp_store):
        """Khử trùng lặp là hệ quả của địa chỉ hoá, không phải một tính năng
        thêm vào. Người soạn bấm Lưu mười lần thì vẫn là một tệp."""
        first, _, _ = legal_store.write("terms", BODY)
        second, _, _ = legal_store.write("terms", BODY)

        assert first == second
        assert len(list(legal_store.iter_keys())) == 1

    def test_differentContent_producesDifferentFiles(self, temp_store):
        legal_store.write("terms", BODY)
        legal_store.write("terms", BODY + "Thêm một dòng.")

        assert len(list(legal_store.iter_keys())) == 2

    def test_sameContentUnderDifferentKinds_staysSeparate(self, temp_store):
        """Phân vùng theo loại để người vận hành đọc được cây thư mục, chấp nhận
        đánh đổi là hai loại có nội dung trùng sẽ lưu hai lần. Với bốn văn bản
        thì cái giá đó bằng không, còn cái lợi là `ls terms/` nói được điều gì."""
        a, _, _ = legal_store.write("terms", BODY)
        b, _, _ = legal_store.write("privacy", BODY)

        assert a != b
        assert len(list(legal_store.iter_keys())) == 2

    def test_readReturnsExactlyWhatWasWritten(self, temp_store):
        key, _, _ = legal_store.write("terms", BODY)

        assert legal_store.read(key) == BODY

    def test_write_reportsByteSizeNotCharacterCount(self, temp_store):
        """Tiếng Việt có dấu tốn nhiều byte hơn số ký tự. Cột `byte_size` phải
        nói về đĩa, không nói về độ dài chuỗi."""
        _, _, size = legal_store.write("terms", BODY)

        assert size == len(BODY.encode("utf-8"))
        assert size > len(BODY)

    def test_write_refusesAnEmptyBody(self, temp_store):
        with pytest.raises(ValueError):
            legal_store.write("terms", "   \n ")


class TestIntegrityChecking:
    def test_verify_passesForAnUntouchedFile(self, temp_store):
        key, _, _ = legal_store.write("terms", BODY)

        assert legal_store.verify(key) is True

    def test_verify_failsWhenTheFileIsEditedInPlace(self, temp_store):
        """Đây là toàn bộ lý do tên tệp là băm: sửa nội dung mà giữ tên thì phép
        kiểm bắt được ngay, không cần tra bảng nào."""
        key, _, _ = legal_store.write("terms", BODY)
        (temp_store / key).write_text(BODY + "sửa lén", encoding="utf-8")

        assert legal_store.verify(key) is False

    def test_verify_failsWhenTheExpectedDigestDisagrees(self, temp_store):
        """Đối chiếu với băm LƯU TRONG BẢNG bắt thêm một trường hợp mà tên tệp
        không bắt được: hàng dữ liệu bị sửa để trỏ sang một blob khác."""
        key, _, _ = legal_store.write("terms", BODY)
        other = legal_store.content_digest("nội dung khác")

        assert legal_store.verify(key, other) is False

    def test_verify_failsForAMissingFile(self, temp_store):
        digest = legal_store.content_digest(BODY)

        assert legal_store.verify(legal_store.storage_key("terms", digest)) is False


class TestPathSafety:
    def test_aKeyThatEscapesTheRoot_isRefused(self, temp_store):
        """Khoá đến từ cơ sở dữ liệu, và một hàng bị sửa thành `../../etc/passwd`
        thì phép kiểm này là thứ duy nhất còn đứng giữa."""
        with pytest.raises(ValueError):
            legal_store.read("../../../etc/passwd")

    def test_existsReturnsFalseRatherThanRaisingForABadKey(self, temp_store):
        """`exists` được gọi ở đường báo cáo, nơi một ngoại lệ sẽ làm hỏng cả
        báo cáo thay vì đánh dấu một hàng."""
        assert legal_store.exists("../../secret") is False

    def test_storageKey_refusesSomethingThatIsNotASha256(self, temp_store):
        with pytest.raises(ValueError):
            legal_store.storage_key("terms", "khong-phai-bam")

    def test_storageKey_refusesAKindThatWouldEscape(self, temp_store):
        with pytest.raises(ValueError):
            legal_store.storage_key("../..", "a" * 64)


class TestGarbageCollection:
    def test_anUnreferencedOldBlob_isCollected(self, temp_store):
        key, _, _ = legal_store.write("terms", BODY)
        _age(temp_store / key, days=2)

        removed = legal_store.collect_garbage([], dry_run=False)

        assert removed == [key]
        assert not (temp_store / key).exists()

    def test_aReferencedBlob_isKept(self, temp_store):
        key, _, _ = legal_store.write("terms", BODY)
        _age(temp_store / key, days=2)

        assert legal_store.collect_garbage([key], dry_run=False) == []
        assert (temp_store / key).exists()

    def test_aFreshUnreferencedBlob_isKept(self, temp_store):
        """Cửa sổ tuổi che đúng một khoảng: giữa lúc ghi tệp và lúc ghi hàng,
        blob hợp lệ nhưng chưa ai trỏ tới. Dọn rác chạy trúng đó mà không xét
        tuổi sẽ xoá nội dung của bản vừa công bố."""
        key, _, _ = legal_store.write("terms", BODY)

        assert legal_store.collect_garbage([], dry_run=False) == []
        assert (temp_store / key).exists()

    def test_dryRunIsTheDefaultAndDeletesNothing(self, temp_store):
        """Đây là lệnh xoá tệp. Nó không nên chạy vì người ta gõ thiếu một cờ."""
        key, _, _ = legal_store.write("terms", BODY)
        _age(temp_store / key, days=2)

        removed = legal_store.collect_garbage([])

        assert removed == [key]
        assert (temp_store / key).exists()


class TestTheSuiteNeverWritesToTheRealStore:
    """Lá chắn ở `conftest.py`, ghim tại đây.

    Từ v6, mỗi lượt công bố GHI MỘT TỆP. Bốn tệp test công bố văn bản, và sổ dấu
    vết không bắt được chuyện này — nó theo dõi hàng trong cơ sở dữ liệu, không
    theo dõi tệp trên đĩa. Một lượt chạy suite đã để lại 37 blob trong
    `dataset/legal` thật trước khi có lá chắn.
    """

    def test_theDefaultStoreRootIsNotTheDatasetDirectory(self, monkeypatch):
        # Bỏ ghi đè của fixture `temp_store` để nhìn thấy mặc định của suite.
        monkeypatch.undo()
        from app.config import settings

        root = str(legal_store.store_root())

        assert root != str(Path(settings.dataset_root) / "legal"), (
            "bộ test đang trỏ vào kho tài liệu THẬT — xem lá chắn "
            "`LEGAL_STORE_ROOT` ở tests/conftest.py"
        )

    def test_theGuardUsesAssignmentNotSetdefault(self):
        """`setdefault` sẽ nhường chỗ cho biến môi trường của ảnh container, và
        một lá chắn nhường chỗ thì không chắn gì cả."""
        source = (Path(__file__).parent / "conftest.py").read_text(encoding="utf-8")

        assert 'os.environ["LEGAL_STORE_ROOT"]' in source
        assert 'setdefault("LEGAL_STORE_ROOT"' not in source


class TestListing:
    def test_iterKeys_returnsRelativePaths(self, temp_store):
        """Lưu TƯƠNG ĐỐI: gốc kho khác nhau giữa máy phát triển, container và
        một lần khôi phục, và đường tuyệt đối trong bảng biến mỗi lần dời chỗ
        thành một lần UPDATE hàng loạt."""
        key, _, _ = legal_store.write("terms", BODY)

        assert list(legal_store.iter_keys()) == [key]
        assert not key.startswith("/")

    def test_iterKeys_skipsPartialWrites(self, temp_store):
        """Tệp `.tmp-*` là một lượt ghi đang dở. Đếm nó là rác sẽ khiến dọn rác
        xoá mất một lượt ghi đang chạy."""
        legal_store.write("terms", BODY)
        (temp_store / "terms").mkdir(exist_ok=True)
        (temp_store / "terms" / ".tmp-dangdo.md").write_text("dở", encoding="utf-8")

        assert all(".tmp-" not in k for k in legal_store.iter_keys())

    def test_iterKeys_onAnEmptyStore_returnsNothing(self, temp_store):
        assert list(legal_store.iter_keys()) == []


def _age(path, *, days: int) -> None:
    """Lùi thời điểm sửa của một tệp về quá khứ.

    Rẻ hơn nhiều so với chờ thật, và chính xác hơn so với hạ `min_age_seconds`
    xuống 0 — hạ ngưỡng sẽ làm test không còn kiểm cái ngưỡng ấy nữa.
    """
    past = time.time() - days * 86400
    os.utime(path, (past, past))
