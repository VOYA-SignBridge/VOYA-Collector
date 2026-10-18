"""Ánh xạ `storage_key` (bố cục trên đĩa) -> đường dẫn trên Google Drive.

Hai bố cục, chọn bằng `settings.gdrive_layout`:

    legacy   Drive soi đúng cây trên đĩa (hành vi trước 18/10/2026)
    tenant   Community/… hoặc Tenants/<slug>/{Samples,Raw,Videos,Models}/…

Bất biến được canh ở đây:
  * `storage_key` KHÔNG đổi — DB, samples.csv, sidecar, split đóng băng, gói SOT
    vẫn mang khoá trên đĩa; chỉ đường dẫn Drive được ánh xạ.
  * Không bao giờ rơi về tenant `default` khi thiếu tenant cho một cây KHÔNG phân
    vùng trên đĩa (raw_videos, models) — rơi-về im lặng là cách dữ liệu của tổ
    chức X chui vào thư mục của nền tảng.
  * Ánh xạ là idempotent: áp hai lần = áp một lần (task Celery retry, migration
    chạy lại).
"""
import pytest

from app.config import settings
from app.storage import drive_layout as dl


#: Thư mục Drive của tổ chức đọc từ bảng `tenants`; ở đây thay bằng bảng cố định.
ROOTS = {"default": "Community", "truong-b": "Tenants/truong-b", "truong-c": "Tenants/truong-c"}


@pytest.fixture(autouse=True)
def tenant_roots(monkeypatch):
    def _root(tenant_id):
        if tenant_id not in ROOTS:
            raise ValueError(f"không có tổ chức {tenant_id!r}")
        return ROOTS[tenant_id]
    monkeypatch.setattr(dl, "tenant_drive_root", _root)


@pytest.fixture
def tenant_mode(monkeypatch):
    monkeypatch.setattr(settings, "gdrive_layout", "tenant", raising=False)


@pytest.fixture
def legacy_mode(monkeypatch):
    monkeypatch.setattr(settings, "gdrive_layout", "legacy", raising=False)


NPZ = "features/vn/hoa-de/class_tom_7246af3c/sample_21a0842b56.npz"
NPZ_T = "features/_tenants/truong-b/vn/hoa-de/class_xin-chao_8d76181c/sample_d8c52ee1ae.npz"
RAW_ARCHIVE_T = "raw/_tenants/truong-b/vn/hoa-de/class_xin-chao_8d76181c/sample_d8c52ee1ae.npz"
VIDEO = "raw_videos/vn/nam/class_dia-chi_df77087d/8219900a_D0001N.mp4"
MODEL = "models/Hòa đê/Deploy 2026-08-18 04-11-40/tcn.pt"


class TestLegacyIsTheCurrentBehaviour:
    """Mặc định phải là legacy: triển khai mã này không được dời thứ gì trên Drive."""

    def test_default_layout_is_legacy(self):
        """Giá trị mặc định trong mã, không phải `.env` của máy đang chạy test."""
        import inspect

        from app.config import Settings

        assert 'os.getenv("GDRIVE_LAYOUT", "legacy")' in inspect.getsource(Settings)

    @pytest.mark.parametrize("key", [NPZ, NPZ_T, RAW_ARCHIVE_T, VIDEO, MODEL,
                                     "features/vn/hoa-de/class_tom_7246af3c"])
    def test_legacy_returns_the_storage_key_unchanged(self, legacy_mode, key):
        assert dl.drive_path_for(key) == key

    def test_legacy_does_not_need_a_tenant_for_unpartitioned_trees(self, legacy_mode):
        assert dl.drive_path_for(VIDEO) == VIDEO
        assert dl.drive_path_for(MODEL, tenant_id=None) == MODEL


class TestTenantLayout:
    def test_default_tenant_features(self, tenant_mode):
        assert dl.drive_path_for(NPZ) == "Community/Samples/" + NPZ.split("/", 1)[1]

    def test_partitioned_features_take_tenant_from_the_key(self, tenant_mode):
        assert dl.drive_path_for(NPZ_T) == (
            "Tenants/truong-b/Samples/vn/hoa-de/class_xin-chao_8d76181c/sample_d8c52ee1ae.npz")

    def test_raw_archive_mirrors_features(self, tenant_mode):
        assert dl.drive_path_for(RAW_ARCHIVE_T).startswith("Tenants/truong-b/Raw/vn/")

    def test_raw_videos_need_an_explicit_tenant(self, tenant_mode):
        assert dl.drive_path_for(VIDEO, tenant_id="truong-b") == "Tenants/truong-b/Videos/" + VIDEO.split("/", 1)[1]

    def test_raw_videos_without_tenant_refuse_instead_of_defaulting(self, tenant_mode):
        with pytest.raises(ValueError, match="tenant"):
            dl.drive_path_for(VIDEO)

    def test_models(self, tenant_mode):
        assert dl.drive_path_for(MODEL, tenant_id="default") == "Community/Models/" + MODEL.split("/", 1)[1]

    def test_folder_paths_map_too(self, tenant_mode):
        assert dl.drive_path_for("features/vn/hoa-de/class_tom_7246af3c") == (
            "Community/Samples/vn/hoa-de/class_tom_7246af3c")
        assert dl.drive_path_for("raw_videos", tenant_id="truong-b") == "Tenants/truong-b/Videos"

    @pytest.mark.parametrize("key,tenant", [(NPZ, None), (NPZ_T, None), (VIDEO, "truong-b"),
                                            (MODEL, "default"), (RAW_ARCHIVE_T, "truong-b")])
    def test_idempotent(self, tenant_mode, key, tenant):
        once = dl.drive_path_for(key, tenant_id=tenant)
        assert dl.drive_path_for(once, tenant_id=tenant) == once
        assert dl.drive_path_for(once) == once


class TestNotTenantData:
    """SOT, CSV soi và Sheets ở gốc Drive giữ nguyên chỗ ở MỌI bố cục."""

    @pytest.mark.parametrize("key", ["samples.csv", "labels.csv", "raw_uploads.csv",
                                     "SOT/LATEST.json", "SOT/Ver17_17102026/samples.csv"])
    @pytest.mark.parametrize("layout", ["legacy", "tenant"])
    def test_untouched(self, monkeypatch, key, layout):
        monkeypatch.setattr(settings, "gdrive_layout", layout, raising=False)
        assert dl.drive_path_for(key) == key


class TestRefusals:
    @pytest.mark.parametrize("layout", ["legacy", "tenant"])
    def test_key_tenant_and_argument_disagree(self, monkeypatch, layout):
        monkeypatch.setattr(settings, "gdrive_layout", layout, raising=False)
        with pytest.raises(ValueError, match="truong-b"):
            dl.drive_path_for(NPZ_T, tenant_id="truong-c")

    @pytest.mark.parametrize("layout", ["legacy", "tenant"])
    def test_unpartitioned_features_belong_to_default(self, monkeypatch, layout):
        """`features/vn/…` (không có `_tenants/`) là cây của tenant gốc trên đĩa."""
        monkeypatch.setattr(settings, "gdrive_layout", layout, raising=False)
        with pytest.raises(ValueError):
            dl.drive_path_for(NPZ, tenant_id="truong-b")
        assert dl.drive_path_for(NPZ, tenant_id="default") == dl.drive_path_for(NPZ)

    @pytest.mark.parametrize("bad", ["", "  ", "../x", "Truong", "truong-b\n", "a/b"])
    def test_malformed_tenant(self, tenant_mode, bad):
        with pytest.raises(ValueError):
            dl.drive_path_for(VIDEO, tenant_id=bad)

    def test_non_string_tenant(self, tenant_mode):
        with pytest.raises(TypeError):
            dl.drive_path_for(VIDEO, tenant_id=123)

    @pytest.mark.parametrize("key", ["", "features/../SOT/LATEST.json", "features/vn/./x",
                                     "features/_tenants", "features/_tenants/BAD!/vn/x",
                                     "Tenants/x", "Community", "tenants/x"])
    def test_malformed_key(self, tenant_mode, key):
        with pytest.raises(ValueError):
            dl.drive_path_for(key)

    def test_unknown_layout(self, monkeypatch):
        monkeypatch.setattr(settings, "gdrive_layout", "tenants", raising=False)
        with pytest.raises(ValueError, match="GDRIVE_LAYOUT"):
            dl.drive_path_for(NPZ)

    def test_backslashes_and_leading_slash_are_normalised(self, tenant_mode):
        assert dl.drive_path_for("/features\\vn\\hoa-de\\x.npz") == "Community/Samples/vn/hoa-de/x.npz"


# ---------------------------------------------------------------- các chỗ gọi


class _Recorder:
    def __init__(self):
        self.uploads, self.db, self.csv = [], [], []


@pytest.fixture
def fake_drive(monkeypatch, tmp_path):
    import app.dataset_samples as ds
    import app.storage.gdrive_client as gc
    import app.storage.metadata_db as mdb

    rec = _Recorder()
    monkeypatch.setattr(settings, "use_google_drive", True, raising=False)
    monkeypatch.setattr(gc, "upload_to_gdrive",
                        lambda data, key, **kw: rec.uploads.append(key) or f"https://drive.google.com/file/d/ID_{len(rec.uploads)}/view")
    monkeypatch.setattr(mdb, "update_sample_gdrive_url",
                        lambda uid, url, storage_key=None: rec.db.append((uid, storage_key)))
    monkeypatch.setattr(ds, "update_sample_row", lambda uid, upd: rec.csv.append((uid, upd.get("storage_key"))))
    monkeypatch.setattr(ds, "update_sample_rows_bulk",
                        lambda updates: rec.csv.extend((u, v.get("storage_key")) for u, v in updates.items()))
    npz = tmp_path / "s.npz"
    npz.write_bytes(b"npz")
    rec.npz = str(npz)
    return rec


class TestUploadTasks:
    def test_single_npz_uploads_to_mapped_path_but_records_the_disk_key(self, tenant_mode, fake_drive):
        from app.export_tasks import upload_npz_to_gdrive_task

        upload_npz_to_gdrive_task.apply(args=["21a0842b56", fake_drive.npz, NPZ, ""], throw=True)
        assert fake_drive.uploads == ["Community/Samples/" + NPZ.split("/", 1)[1]]
        # Thứ được GHI LẠI là khoá trên đĩa, không bao giờ là đường dẫn Drive.
        # (DB có thể không nhận khoá — tuỳ phiên bản `update_sample_gdrive_url`.)
        assert all(key in (None, NPZ) for _, key in fake_drive.db) and fake_drive.db
        assert fake_drive.csv == [("21a0842b56", NPZ)]

    def test_batch_npz(self, tenant_mode, fake_drive):
        from app.export_tasks import upload_npz_batch_to_gdrive_task

        items = [{"sample_uid": "d8c52ee1ae", "local_path": fake_drive.npz, "storage_key": NPZ_T, "sidecar_path": ""}]
        upload_npz_batch_to_gdrive_task.apply(args=[items], throw=True)
        assert fake_drive.uploads == ["Tenants/truong-b/Samples/" + NPZ_T.split("truong-b/", 1)[1]]
        assert all(key in (None, NPZ_T) for _, key in fake_drive.db) and fake_drive.db
        assert ("d8c52ee1ae", NPZ_T) in fake_drive.csv

    def test_legacy_upload_path_is_the_storage_key(self, legacy_mode, fake_drive):
        from app.export_tasks import upload_npz_to_gdrive_task

        upload_npz_to_gdrive_task.apply(args=["21a0842b56", fake_drive.npz, NPZ, ""], throw=True)
        assert fake_drive.uploads == [NPZ]

    def test_raw_video_uses_the_tenant_argument(self, tenant_mode, fake_drive, monkeypatch):
        import app.raw_uploads as ru
        import app.storage.metadata_db as mdb
        from app.export_tasks import upload_raw_video_to_gdrive_task

        monkeypatch.setattr(ru, "update_raw_upload_row", lambda uid, upd: None)
        monkeypatch.setattr(mdb, "update_raw_upload_gdrive_url", lambda uid, url: None)
        upload_raw_video_to_gdrive_task.apply(
            args=["8219900a", fake_drive.npz, VIDEO, "video/mp4"], kwargs={"tenant_id": "truong-b"}, throw=True)
        assert fake_drive.uploads == ["Tenants/truong-b/Videos/" + VIDEO.split("/", 1)[1]]


class TestCatalogSyncPaths:
    def test_raw_dir_needs_the_class_tenant(self, tenant_mode):
        from app.catalog_sync import _drive_relative_path

        raw_dir = settings.dataset_root / "raw_videos" / "vn" / "nam" / "class_dia-chi_df77087d"
        assert _drive_relative_path(raw_dir, tenant_id="truong-b") == (
            "Tenants/truong-b/Videos/vn/nam/class_dia-chi_df77087d")

    def test_dispatch_skips_an_unmappable_path_instead_of_failing_the_rename(self, tenant_mode, monkeypatch):
        """Đổi tên/xoá lớp đã commit cục bộ; Drive là phần best-effort phía sau."""
        import app.catalog_sync as cs
        import app.export_tasks as et

        sent = []
        monkeypatch.setattr(et.move_gdrive_paths_task, "delay", lambda pairs: sent.append(pairs))
        feat = settings.dataset_root / "features" / "vn" / "nam"
        raw = settings.dataset_root / "raw_videos" / "vn" / "nam"
        cs._dispatch_gdrive_folder_move([(feat / "class_a_1", feat / "class_b_1"), (raw / "class_a_1", raw / "class_b_1")])
        assert sent == [[["Community/Samples/vn/nam/class_a_1", "Community/Samples/vn/nam/class_b_1"]]]


class TestClassFolderOnCreate:
    """Lỗi có sẵn: thư mục Drive của lớp được tạo theo đường viết cứng
    `features/<lang>/<dialect>/…`, bỏ qua tenant — lớp của tổ chức X được tạo
    thư mục nằm trong cây của tenant gốc."""

    def _meta(self, tenant):
        from app.dataset_manager import ClassMetadata

        return ClassMetadata(class_uid="8d76181c-0000-0000-0000-000000000000", class_idx=1, slug="xin-chao",
                             label_original="xin chào", language="vn", dialect="hoa-de",
                             is_common_global=False, is_common_language=False, tenant_id=tenant)

    def test_legacy_tenant_class_goes_under_its_partition(self, legacy_mode):
        from app.dataset_manager import drive_class_folder

        assert drive_class_folder(self._meta("truong-b")) == "features/_tenants/truong-b/vn/hoa-de/class_xin-chao_8d76181c"
        assert drive_class_folder(self._meta("default")) == "features/vn/hoa-de/class_xin-chao_8d76181c"

    def test_tenant_layout(self, tenant_mode):
        from app.dataset_manager import drive_class_folder

        assert drive_class_folder(self._meta("truong-b")) == "Tenants/truong-b/Samples/vn/hoa-de/class_xin-chao_8d76181c"


class TestDialectMergeDrivePairs:
    """`features/*/<old>` không phải đường dẫn Drive hiểu được — `resolve_folder_path`
    tìm một thư mục tên đúng là `*`, không thấy, và task ghi 'skipped (source
    missing)'. Bước Drive của gộp phương ngữ chưa từng chạy. Cặp phải tường minh."""

    def test_pairs_are_explicit_per_language_and_tree(self, legacy_mode, tmp_path):
        from app.catalog_migrations import drive_dialect_move_pairs

        (tmp_path / "features" / "vn" / "nam").mkdir(parents=True)
        (tmp_path / "features" / "en" / "nam").mkdir(parents=True)
        (tmp_path / "raw_videos" / "vn" / "nam").mkdir(parents=True)
        pairs = drive_dialect_move_pairs(tmp_path, "mien-nam", "nam", raw_tenants=["default"])
        assert sorted(pairs) == sorted([
            ("features/en/mien-nam", "features/en/nam"),
            ("features/vn/mien-nam", "features/vn/nam"),
            ("raw_videos/vn/mien-nam", "raw_videos/vn/nam"),
        ])
        assert not any("*" in a or "*" in b for a, b in pairs)

    def test_tenant_layout_one_raw_pair_per_owning_tenant(self, tenant_mode, tmp_path):
        from app.catalog_migrations import drive_dialect_move_pairs

        (tmp_path / "raw_videos" / "vn" / "nam").mkdir(parents=True)
        pairs = drive_dialect_move_pairs(tmp_path, "mien-nam", "nam", raw_tenants=["default", "truong-b"])
        assert sorted(pairs) == [
            ("Community/Videos/vn/mien-nam", "Community/Videos/vn/nam"),
            ("Tenants/truong-b/Videos/vn/mien-nam", "Tenants/truong-b/Videos/vn/nam"),
        ]


class TestModelBackupPaths:
    def test_legacy_keeps_the_fixed_path_mobile_reads(self, legacy_mode):
        from app.training_tasks import model_drive_paths

        deploy, latest = model_drive_paths("Hòa đê", "2026-08-18 04-11-40", tenant_id="default")
        assert deploy == "models/Hòa đê/Deploy 2026-08-18 04-11-40"
        assert latest == "models/Hòa đê/latest_manifest.json"

    def test_tenant_layout(self, tenant_mode):
        from app.training_tasks import model_drive_paths

        deploy, latest = model_drive_paths("Hòa đê", "2026-08-18 04-11-40", tenant_id="truong-b")
        assert deploy == "Tenants/truong-b/Models/Hòa đê/Deploy 2026-08-18 04-11-40"
        assert latest == "Tenants/truong-b/Models/Hòa đê/latest_manifest.json"


class TestStorageKeyIsTheFileOnDisk:
    """Khoá lưu trữ (và từ đó đường dẫn Drive) phải là ĐÚNG vị trí tệp trên đĩa.

    `save_sequence_npz` từng ghép tay `features/<lang>/<dialect>/<lớp>/…`, bỏ qua
    `_tenants/<id>/` lẫn `<lang>/common/` và `global_common/` — trong khi tệp thật
    nằm theo `hierarchy_path()`. Khoá lệch tệp thì Drive nhận sai chỗ, và mọi
    phép đối chiếu theo khoá báo "không thấy" (18/10/2026).
    """

    @pytest.fixture
    def kho_tam(self, monkeypatch, tmp_path):
        import app.dataset_manager as dm
        import app.dataset_samples as ds

        monkeypatch.setattr(dm, "FEATURES_ROOT", tmp_path / "features")
        monkeypatch.setattr(ds, "DATASET_ROOT", tmp_path)
        monkeypatch.setattr(settings, "use_google_drive", True, raising=False)
        bat = {}
        monkeypatch.setattr(ds, "append_sample_row", lambda row: bat.update(csv=dict(row)))
        monkeypatch.setattr("app.storage.metadata_db.insert_sample", lambda row: bat.update(db=dict(row)))
        return bat

    def _meta(self, tenant="default", common=False):
        from app.dataset_manager import ClassMetadata

        return ClassMetadata(class_uid="7246af3c-0000-0000-0000-000000000000", class_idx=1, slug="tom",
                             label_original="tôm", language="vn", dialect="hoa-de",
                             is_common_global=False, is_common_language=common, tenant_id=tenant)

    def _save(self, meta):
        import numpy as np

        from app.dataset_samples import save_sequence_npz

        items = []
        save_sequence_npz(meta, np.zeros((60, 126), dtype=np.float32), meta={}, augment_id=0,
                          source_type="camera", upload_collector=items)
        return items[0]

    @pytest.mark.parametrize("tenant,common,prefix", [
        ("truong-b", False, "features/_tenants/truong-b/vn/hoa-de/class_tom_7246af3c/"),
        ("default", True, "features/vn/common/class_tom_7246af3c/"),
        ("default", False, "features/vn/hoa-de/class_tom_7246af3c/"),
    ])
    def test_capture_key_is_the_saved_file(self, kho_tam, tmp_path, tenant, common, prefix):
        item = self._save(self._meta(tenant, common))
        assert item["storage_key"].startswith(prefix), item["storage_key"]
        assert (tmp_path / item["storage_key"]) == __import__("pathlib").Path(item["local_path"])

    def test_class_storage_dir_follows_hierarchy(self, kho_tam):
        from app.dataset_manager import class_storage_dir

        assert class_storage_dir(self._meta("truong-b")) == "features/_tenants/truong-b/vn/hoa-de/class_tom_7246af3c"
        assert class_storage_dir(self._meta("default", common=True)) == "features/vn/common/class_tom_7246af3c"
