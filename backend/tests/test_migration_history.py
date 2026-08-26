"""Lịch sử migration là bất biến, kể cả khi phép phân loại tiến hoá.

Sự cố 13/08/2026 để lại một bất biến trung tâm, và tệp này canh đúng nó:

    phân loại   ĐƯỢC tiến hoá   (`one_way_statements()` bắt 11 -> 43 -> 80 câu)
    lịch sử     KHÔNG được      (`migration_payload(5)` mãi mãi 11 câu)

Bản đầu dẫn xuất cái sau từ cái trước, nên mỗi lần bộ phân loại giỏi lên là một
lần quá khứ bị viết lại. `TestClassificationDoesNotRewriteHistory` là nhóm quan
trọng nhất ở đây: nó chứng minh lỗi đó đã chết, chứ không chỉ đã được vá.
"""

from __future__ import annotations

import pytest

from app.storage.migration_history import (
    MIGRATION_HISTORY,
    V5_CHECKSUM,
    UnknownMigrationVersion,
    labelled_payload,
    migration_payload,
)
from app.storage.schema_version import migration_checksum


class TestVersionFivePayloadIsFrozen:
    """Mười một câu, đúng thứ tự đó, checksum đó."""

    def test_the_v5_payload_has_exactly_eleven_statements(self):
        payload = migration_payload(5)

        assert len(payload) == 11, (
            f"v5 da chay tren san xuat voi 11 cau ngay 12/08/2026; bay gio la "
            f"{len(payload)}. Mot phien ban da apply thi bat bien — neu can "
            f"them cau, tao v6."
        )

    def test_the_v5_checksum_is_still_the_one_production_recorded(self):
        """`V5_CHECKSUM` chép từ `schema_migrations` của sản xuất, không tính
        ra từ mã trong kho này. Nên đây là phép đối chứng độc lập."""
        assert migration_checksum(5) == V5_CHECKSUM

    def test_every_v5_statement_has_a_label(self):
        """Nhãn là thứ làm một lượt hỏng nói được nó hỏng ở đâu. Vài câu tham
        chiếu qua chỉ số (`_DROP_GLOBAL_CLASS_UNIQUES[0]`), và đảo thứ tự
        trong tuple gốc sẽ đổi payload mà không đổi dòng mã nào ở đây."""
        labels = [label for label, _ in labelled_payload(5)]

        assert len(labels) == len(set(labels)), f"nhan trung nhau: {labels}"
        assert all(label and not label[0].isdigit() for label in labels)

    def test_an_unpackaged_version_is_refused_not_guessed(self):
        """Phiên bản chưa đóng gói phải bị TỪ CHỐI, không được đoán.

        Đoán payload nghĩa là đóng dấu checksum của một bản nửa vời rồi khoá
        vĩnh viễn — không sửa lại được, chỉ có thể tạo phiên bản mới.

        Bài này CỐ Ý hỏi phiên bản kế tiếp phiên bản cao nhất đã đóng gói, chứ
        không hỏi một số cố định. Bản trước ghim `6`, và khi v6/v7/v8 lần lượt
        được đóng gói thì nó chuyển từ "canh một bất biến" sang "báo đỏ vì công
        việc đã hoàn thành" — một bài test hỏng theo lịch, không theo lỗi.
        """
        chua_dong_goi = max(MIGRATION_HISTORY) + 1
        with pytest.raises(UnknownMigrationVersion) as caught:
            migration_payload(chua_dong_goi)

        assert f"v{chua_dong_goi}" in str(caught.value)


class TestClassificationDoesNotRewriteHistory:
    """Nhóm chứng minh lỗi 13/08 đã chết."""

    def test_a_newly_classified_statement_leaves_v5_untouched(self):
        """Thêm một câu nguy hiểm vào đường khởi động: bộ phân loại PHẢI bắt
        được nó, và checksum v5 PHẢI đứng yên.

        Bản cũ trượt đúng ở đây — payload v5 lọc theo `one_way_statements()`,
        nên mỗi câu mới bộ phân loại bắt được đều chui vào lịch sử của v5.
        """
        import app.storage.metadata_db as mdb

        intruder = "UPDATE users SET display_name = username WHERE display_name IS NULL"
        before_payload = migration_payload(5)
        before_checksum = migration_checksum(5)

        mdb.MIGRATION_STATEMENTS.append(intruder)
        try:
            # Phân loại có tiến hoá: câu mới bị đẩy khỏi đường khởi động.
            assert intruder in mdb.one_way_statements(), (
                "bo phan loai KHONG bat duoc cau moi — test nay khong con "
                "chung minh duoc gi")

            # Nhưng lịch sử thì không.
            assert migration_payload(5) == before_payload
            assert migration_checksum(5) == before_checksum == V5_CHECKSUM
        finally:
            mdb.MIGRATION_STATEMENTS.remove(intruder)

        assert migration_checksum(5) == V5_CHECKSUM

    def test_the_payload_does_not_read_the_classifier_at_all(self):
        """Chặt hơn test trên: kể cả khi phép phân loại hỏng hoàn toàn, lịch sử
        vẫn dựng được. Một `migration_payload` còn gọi `one_way_statements()`
        sẽ ngã ở đây."""
        import app.storage.metadata_db as mdb

        def explode():
            raise AssertionError("migration_payload KHONG duoc doc phan loai")

        original = mdb.one_way_statements
        mdb.one_way_statements = explode
        try:
            assert migration_checksum(5) == V5_CHECKSUM
        finally:
            mdb.one_way_statements = original


class TestEditingAnAppliedMigrationTurnsTheGateRed:
    """Chiều ngược lại: nếu lịch sử THỰC SỰ bị sửa, phải đỏ."""

    def test_changing_one_statement_body_breaks_the_checksum(self):
        import app.storage.migration_history as history

        original = history.MIGRATION_HISTORY[5]

        def edited():
            rows = list(original())
            label, statement = rows[3]
            rows[3] = (label, statement.replace("IF n = 0", "IF n <= 0", 1))
            assert rows[3][1] != statement, "phep sua khong doi gi — test vo nghia"
            return tuple(rows)

        history.MIGRATION_HISTORY[5] = edited
        try:
            assert migration_checksum(5) != V5_CHECKSUM
        finally:
            history.MIGRATION_HISTORY[5] = original

        assert migration_checksum(5) == V5_CHECKSUM

    def test_reordering_two_statements_breaks_the_checksum(self):
        """Thứ tự là một phần của hợp đồng, không phải chi tiết cài đặt: bốn
        ràng buộc thứ tự trong `AUTHZ_DDL_STATEMENTS` mỗi cái đổi lấy một lần
        hỏng thật."""
        import app.storage.migration_history as history

        original = history.MIGRATION_HISTORY[5]

        def swapped():
            rows = list(original())
            rows[5], rows[6] = rows[6], rows[5]
            return tuple(rows)

        history.MIGRATION_HISTORY[5] = swapped
        try:
            assert migration_checksum(5) != V5_CHECKSUM, (
                "doi thu tu hai cau ma checksum khong doi — phep bam dang bo "
                "qua thu tu, va no phai KHONG bo qua")
        finally:
            history.MIGRATION_HISTORY[5] = original

    def test_dropping_a_statement_breaks_the_checksum(self):
        import app.storage.migration_history as history

        original = history.MIGRATION_HISTORY[5]
        history.MIGRATION_HISTORY[5] = lambda: tuple(original()[:-1])
        try:
            assert migration_checksum(5) != V5_CHECKSUM
        finally:
            history.MIGRATION_HISTORY[5] = original
