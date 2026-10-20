"""Ba lỗi tìm ra khi kiểm chứng hai tenant thật từ đầu đến cuối (17/10/2026).

Mỗi tenant 60 mẫu, cùng phương ngữ `hoa-de`, chạy trên một stack cô lập:

1. Lớp ĐẦU TIÊN của tenant mới không vào được DB: `fk_classes_vocabulary_group`
   vì nhóm từ vựng không được clone sang tenant mới, kéo theo phiên thu + mẫu.
2. `GET /training/dataset-info` báo 120 mẫu cho mỗi bên (đọc CSV chung, không
   lọc tổ chức) và lộ tên phương ngữ của tenant kia.
3. Trainer loại sạch mẫu của tenant vì chỉ tìm tệp ở cây của tenant khởi tạo,
   không ở `features/_tenants/<tenant>/` -> "train split became empty".

Lỗi thứ tư (split của B chứa cả 60 mẫu của A) nằm trong `make_splits.py` và được
kiểm bằng lượt chạy E2E, vì nó chỉ lộ ra trong hàm `main()`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


# ---------------------------------------------------------------------------
# 1. Nhóm từ vựng có trước lớp
# ---------------------------------------------------------------------------

class TestVocabularyGroupBeforeClass:
    def _calls(self, monkeypatch, row):
        from app.storage import metadata_db as mdb

        calls = []
        monkeypatch.setattr(mdb, "_execute", lambda sql, params=None: calls.append((sql, params)))
        mdb.upsert_class(row)
        return calls

    def test_group_row_is_written_for_the_class_tenant_first(self, monkeypatch):
        calls = self._calls(monkeypatch, {
            "class_uid": "c1", "tenant_id": "truong-b", "vocabulary_group": "hoa_de_vocabulary"})
        assert len(calls) == 2
        sql, params = calls[0]
        assert "INSERT INTO vocabulary_groups" in sql and "ON CONFLICT" in sql
        assert params == ("truong-b", "hoa_de_vocabulary", "hoa_de_vocabulary")
        assert "INSERT INTO classes" in calls[1][0]

    def test_no_group_means_no_extra_write(self, monkeypatch):
        calls = self._calls(monkeypatch, {"class_uid": "c1", "tenant_id": "truong-b", "vocabulary_group": ""})
        assert len(calls) == 1

    def test_silent_tenant_falls_back_like_the_class_row(self, monkeypatch):
        calls = self._calls(monkeypatch, {"class_uid": "c1", "vocabulary_group": "g"})
        sql, params = calls[0]
        assert params[0] is None and "COALESCE(%s, 'default')" in sql


# ---------------------------------------------------------------------------
# 2. dataset-info chỉ đếm dữ liệu của người gọi
# ---------------------------------------------------------------------------

def test_rows_of_tenant_keeps_only_own_rows_and_blank_means_default():
    from app.routers.training import _rows_of_tenant

    rows = [{"tenant_id": "a", "k": 1}, {"tenant_id": "b", "k": 2},
            {"tenant_id": "", "k": 3}, {"k": 4}]
    assert [r["k"] for r in _rows_of_tenant(rows, "a")] == [1]
    assert [r["k"] for r in _rows_of_tenant(rows, "default")] == [3, 4]


# ---------------------------------------------------------------------------
# 3. Trainer tìm được tệp trong phân vùng tenant
# ---------------------------------------------------------------------------

REL = "features/_tenants/truong-b/vn/hoa-de/class_x_1234/sample_aa.npz"


def _row(**extra):
    row = {"folder_name": "class_x_1234", "file": "sample_aa.npz", "language": "vn",
           "dialect": "hoa-de", "tenant_id": "truong-b", "file_path": REL}
    row.update(extra)
    return row


@pytest.fixture
def tenant_tree(tmp_path):
    path = tmp_path / REL
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x")
    return tmp_path / "features", path


class TestTrainerFindsTenantFiles:
    def test_filter_keeps_row_via_file_path(self, tenant_tree):
        from processed.train_utils.train_tcn import _filter_rows_with_existing_features

        root, _ = tenant_tree
        assert len(_filter_rows_with_existing_features([_row()], features_root=root)) == 1

    def test_filter_keeps_row_via_tenant_id_when_file_path_is_absent(self, tenant_tree):
        from processed.train_utils.train_tcn import _filter_rows_with_existing_features

        root, _ = tenant_tree
        assert len(_filter_rows_with_existing_features([_row(file_path="")], features_root=root)) == 1

    def test_file_path_cannot_escape_the_dataset_root(self, tenant_tree):
        from processed.train_utils.train_tcn import _row_feature_path_candidates

        root, _ = tenant_tree
        cands = _row_feature_path_candidates(_row(file_path="../../etc/passwd", tenant_id=""),
                                             features_root=root)
        assert all(c.resolve().is_relative_to(root.parent.resolve()) for c in cands)

    def test_loader_opens_the_same_file_the_filter_kept(self, tenant_tree):
        from processed.train_utils.dataset_loader import NPZSignDataset

        root, path = tenant_tree
        ds = NPZSignDataset.__new__(NPZSignDataset)
        ds.root = root
        ds.root_is_explicit = False
        for row in (_row(), _row(file_path="")):
            assert ds._resolve_feature_path(row).resolve() == path.resolve()


# ---------------------------------------------------------------------------
# 4. Bản xuất không kẹt ở "running" khi Windows giữ tệp
# ---------------------------------------------------------------------------

class TestExportRenameOnWindowsMount:
    def test_rename_retries_a_transient_permission_error(self, tmp_path, monkeypatch):
        from app import tenant_lifecycle as tl

        partial, target = tmp_path / "x.zip.part", tmp_path / "x.zip"
        partial.write_bytes(b"zip")
        real, calls = Path.replace, []

        def flaky(self, dst):
            calls.append(1)
            if len(calls) < 3:
                raise PermissionError(13, "Permission denied")
            return real(self, dst)

        monkeypatch.setattr(Path, "replace", flaky)
        monkeypatch.setattr("time.sleep", lambda s: None)
        tl.finish_partial(partial, target)
        assert target.read_bytes() == b"zip" and len(calls) == 3

    def test_rename_gives_up_after_the_last_attempt(self, tmp_path, monkeypatch):
        from app import tenant_lifecycle as tl

        def always(self, dst):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(Path, "replace", always)
        monkeypatch.setattr("time.sleep", lambda s: None)
        with pytest.raises(PermissionError):
            tl.finish_partial(tmp_path / "a.part", tmp_path / "a", attempts=3)

    def test_cleanup_failure_never_hides_the_failed_status(self, tmp_path, monkeypatch):
        from app import tenant_lifecycle as tl

        def denied(self, missing_ok=False):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(Path, "unlink", denied)
        tl.discard_partial(tmp_path / "a.part")  # không ném lỗi
