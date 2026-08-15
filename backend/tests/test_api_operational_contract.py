"""Đường API và đường dòng lệnh phải chạy CÙNG một hợp đồng huấn luyện.

Trước lượt này chúng không cùng:

    tay:  hiện vật vận hành → --train/--val/--test tường minh → trainer
    API:  _build_cmd legacy → KHÔNG truyền gì  → mặc định của trainer
                                               → ba tệp nghiên cứu ĐÓNG BĂNG

Cả hai đều "chạy được", cả hai đều sinh checkpoint, và không có gì báo rằng
chúng đọc hai tập dữ liệu khác nhau. Đó là cùng một hình dạng sai với lỗi hai
bản mã băm: mỗi tầng tự nhất quán với chính nó, cả hệ thống thì không.

Bất biến tệp này canh, theo đúng thứ tự chuỗi:

    POST /training/start (operational_split_id)
      → 400 nếu thiếu, không tự chọn hiện vật mới nhất
      → resolver xác minh đúng hiện vật đó
      → BỐN cổng soi chính hiện vật đó, không phải ba tệp gốc
      → _build_cmd truyền chính ba tệp đó
      → _split_csvs_of(cmd) trả chính ba tệp đó  ← cổng đồng thuận soi cái này
      → trainer dựng K = số lớp hiện vật khai
      → checkpoint mang split_id + hai mã băm khớp hiện vật

Ca cuối chạy `train_tcn` THẬT bằng chính `cmd` mà API dựng ra. Chỉ thêm đúng
hai cờ — `--device=cpu` và `--out_dir` — và không cờ nào chạm tới nguồn dữ liệu.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.auth import get_current_user, require_admin  # noqa: E402
from app.routers import training as tr  # noqa: E402
from app.routers.training import router, training_jobs  # noqa: E402

SPLITS = REPO_ROOT / "processed" / "splits"
FEATURES = REPO_ROOT / "dataset" / "features"

#: Hiện vật THẬT, dựng 15/08 từ dữ liệu thật. Cố ý dùng nó chứ không dựng một
#: hiện vật giả trong tmp: mục đích của tệp này là chứng minh đường API và
#: đường tay gặp nhau trên CÙNG MỘT hiện vật, nên hiện vật phải là cái đã được
#: đường tay chứng minh.
SPLIT_ID = "hoa-de-20260815-floor25"
ARTIFACT = SPLITS / "operational" / SPLIT_ID
SO_LOP = 7
PHUONG_NGU = "hoa-de"

_CO = ARTIFACT.is_dir() and (ARTIFACT / "split_metadata.json").exists()

pytestmark = pytest.mark.skipif(
    not _CO,
    reason=(f"cần hiện vật vận hành {SPLIT_ID} (thư mục operational/ nằm ngoài "
            f"Git — dựng lại bằng make_splits.py --dialects=hoa-de "
            f"--min_samples_per_class=25 --operational_split_id={SPLIT_ID})"),
)

USER = {"id": "u-1", "username": "researcher", "role": "user"}
ADMIN = {"id": "a-1", "username": "boss", "role": "admin"}


@pytest.fixture
def client(monkeypatch):
    """Router thật, chỉ thay những hệ thống nằm ngoài tiến trình này.

    `SPLITS_DIR` được trỏ về kho thật vì mặc định của nó là `/workspace/...` —
    đường dẫn của container trainer, không tồn tại trong container test.
    """
    monkeypatch.setattr(tr, "SPLITS_DIR", SPLITS)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[require_admin] = lambda: ADMIN

    async def _khong_ghi_db(job, auth_user_id=None):
        return None

    monkeypatch.setattr(tr, "_persist_job", _khong_ghi_db)
    training_jobs.clear()
    with TestClient(app) as c:
        yield c
    training_jobs.clear()


@pytest.fixture
def khai_bao():
    return json.loads((ARTIFACT / "split_metadata.json").read_text(encoding="utf-8"))


def _gui(client, **cau_hinh):
    goc = {"model_type": "tcn", "epochs": 1, "batch_size": 32}
    goc.update(cau_hinh)
    with patch("app.training_tasks.run_training_job"):
        return client.post("/training/start", json=goc)


class TestCongGhimHienVat:
    """Không có `split_id` thì DỪNG — bất biến quan trọng nhất của lượt này."""

    def test_van_hanh_thieu_split_id_thi_400(self, client):
        r = _gui(client, run_purpose="operational", dialects=[PHUONG_NGU])

        assert r.status_code == 400
        chi_tiet = r.json()["detail"]
        assert "operational_split_id" in chi_tiet
        # Câu báo lỗi phải nói ra cả điều hệ thống KHÔNG làm. Người đọc lỗi
        # này sẽ đi tìm "vậy nó lấy split nào" nếu ta không nói.
        assert "KHÔNG tự chọn" in chi_tiet and "đóng băng" in chi_tiet

    def test_split_id_khong_ton_tai_thi_400_chu_khong_roi_ve_mac_dinh(self, client):
        r = _gui(client, run_purpose="operational",
                 operational_split_id="khong-he-ton-tai")

        assert r.status_code == 400
        assert "khong-he-ton-tai" in r.json()["detail"]

    def test_khong_the_vua_nghien_cuu_vua_van_hanh(self, client):
        r = _gui(client, run_purpose="research", split_version="x",
                 operational_split_id=SPLIT_ID)

        assert r.status_code == 400
        assert "hai hợp đồng" in r.json()["detail"].lower() or \
               "Hai hợp đồng" in r.json()["detail"]

    def test_ghim_duoc_thi_200_va_job_giu_lai_split_id(self, client):
        r = _gui(client, operational_split_id=SPLIT_ID)

        assert r.status_code == 200, r.text
        job = r.json()
        assert job["config"]["operational_split_id"] == SPLIT_ID
        # `run_purpose` phải được nâng lên `operational`: nếu để `smoke_test`
        # thì checkpoint sẽ khai một mục đích khác với hợp đồng nó đã chạy.
        assert job["config"]["run_purpose"] == "operational"

    def test_pham_vi_phuong_ngu_lay_TU_HIEN_VAT(self, client):
        """Bỏ trống `dialects` không được biến thành "không lọc gì".

        Bốn cổng nằm trong `if selected_dialects:`, và `--dialect` là thứ đưa
        trainer vào chế độ subset — nơi nhánh `class_uid → target_idx` sống.
        Bỏ trống mà vẫn chạy là bỏ qua cả bốn cổng VÀ quay về `enumerate`.
        """
        r = _gui(client, operational_split_id=SPLIT_ID)

        assert r.status_code == 200, r.text
        assert r.json()["config"]["dialects"] == [PHUONG_NGU]

    def test_xin_phuong_ngu_ngoai_hien_vat_thi_400(self, client):
        r = _gui(client, operational_split_id=SPLIT_ID,
                 dialects=[PHUONG_NGU, "bang-chu-cai"])

        assert r.status_code == 400
        assert "bang-chu-cai" in r.json()["detail"]


class TestCongSoiDungHienVatDaGhim:
    """Cổng duyệt tập lớp A trong khi trainer học tập B là sai toàn hệ thống."""

    def test_cong_doc_hien_vat_chu_khong_doc_ba_tep_goc(self):
        """Bằng chứng trực tiếp, và nó đo được vì hai bên khác nhau THẬT.

        Ba tệp nghiên cứu đóng băng chứa 8 lớp `hoa-de` (ảnh chụp cũ, gồm cả
        lớp yếu); hiện vật vận hành chứa 7. Nếu cổng vẫn đọc `SPLITS_DIR` thì
        nó sẽ duyệt trên tập 8 lớp — đúng tập mà trainer KHÔNG đọc.
        """
        theo_hien_vat = tr._split_class_uids([PHUONG_NGU], ARTIFACT)
        theo_goc = tr._split_class_uids([PHUONG_NGU], SPLITS)

        assert len(theo_hien_vat) == SO_LOP
        assert len(theo_goc) > SO_LOP, (
            "hai nguồn phải khác nhau, nếu không ca này không chứng minh gì")
        assert set(theo_hien_vat) < set(theo_goc)

    def test_chung_cu_tren_hien_vat_khong_bao_van_de(self):
        """Hiện vật hợp lệ thì cổng chứng cứ phải im lặng."""
        assert tr._split_evidence_problems([PHUONG_NGU], 25, ARTIFACT) == []

    def test_ban_khai_doc_duoc_tu_hien_vat(self, khai_bao):
        khai = tr._split_snapshot(ARTIFACT)

        assert khai["split_id"] == SPLIT_ID
        assert khai["policy"]["min_samples_per_class"] == 25
        assert khai["num_classes"] == SO_LOP == khai_bao["num_classes"]


class TestLenhMangDungBaTepDo:
    """`_build_cmd` và `_split_csvs_of` phải nói cùng một chuyện."""

    @pytest.fixture(autouse=True)
    def _tro_ve_kho_that(self, monkeypatch):
        from app import training_tasks as tt

        monkeypatch.setattr(tt, "SPLITS_DIR", SPLITS)

    def test_van_hanh_truyen_duong_dan_tuong_minh(self):
        from app.training_tasks import _build_cmd

        cmd = _build_cmd(
            {"model_type": "tcn", "run_purpose": "operational",
             "operational_split_id": SPLIT_ID, "dialects": [PHUONG_NGU]},
            Path("m.jsonl"))

        assert f"--train_csv={ARTIFACT / 'train.csv'}" in cmd
        assert f"--val_csv={ARTIFACT / 'val.csv'}" in cmd
        assert f"--test_csv={ARTIFACT / 'test.csv'}" in cmd
        assert f"--dialect={PHUONG_NGU}" in cmd
        # Hiện vật vận hành nằm sâu hơn ba tệp gốc một cấp, nên phép suy
        # `parents[2]` của trainer trỏ nhầm chỗ — phải nói rõ.
        assert any(a.startswith("--features_root=") for a in cmd)

    def test_preflight_soi_DUNG_ba_tep_trainer_doc(self):
        """Bất biến: hiện vật được soi == hiện vật trainer thật sự đọc.

        Kiểm bằng cách đọc lại từ `cmd` — tức là từ chính argv của tiến trình
        con — chứ không dựng lại từ config. Dựng lại là bản cài đặt thứ hai của
        cùng một quy tắc, và bản nào sai thì cổng soi nhầm tệp.
        """
        from app.training_tasks import _build_cmd, _split_csvs_of

        cmd = _build_cmd(
            {"run_purpose": "operational", "operational_split_id": SPLIT_ID},
            Path("m.jsonl"))

        assert _split_csvs_of(cmd) == [
            str(ARTIFACT / "train.csv"), str(ARTIFACT / "val.csv"),
            str(ARTIFACT / "test.csv"),
        ]

    def test_thieu_split_id_o_worker_cung_DUNG(self):
        """Cổng ở API không phải hàng rào duy nhất.

        Job có thể vào hàng đợi từ một đường khác, hoặc hiện vật bị xoá giữa
        lúc duyệt và lúc chạy. Worker phân giải lại, và cũng fail-closed.
        """
        from processed.train_utils.split_artifact import SplitArtifactError
        from app.training_tasks import _build_cmd

        with pytest.raises(SplitArtifactError):
            _build_cmd({"run_purpose": "operational"}, Path("m.jsonl"))

    def test_legacy_khong_con_de_cong_dong_thuan_mu(self):
        """Lỗ cũ: `_split_csvs_of` trả RỖNG cho legacy.

        `_consent_preflight` trả `None` khi không có tệp nào để soi, nên
        **không lượt huấn luyện legacy nào từng được cổng đồng thuận soi**. Giờ
        legacy cũng đi qua resolver và nói ra ba tệp nó dùng.
        """
        from app.training_tasks import _build_cmd, _split_csvs_of

        cmd = _build_cmd({"model_type": "tcn", "dialects": [PHUONG_NGU]},
                         Path("m.jsonl"))

        duong_dan = _split_csvs_of(cmd)
        assert duong_dan, "legacy vẫn không nói ra tệp nó đọc"
        assert duong_dan == [str(SPLITS / "train.csv"), str(SPLITS / "val.csv"),
                             str(SPLITS / "test.csv")]
        # Vẫn là hợp đồng CŨ: ba tệp nghiên cứu, bộ lọc dialect giữ nguyên.
        assert f"--dialect={PHUONG_NGU}" in cmd


#: Những cờ QUYẾT ĐỊNH nguồn dữ liệu. Sau khi `_build_cmd` trả về, `cmd` là
#: bằng chứng cuối cùng về việc lượt chạy đọc gì — cổng đồng thuận đọc lại từ
#: chính nó. Cho phép một bước sau đó thêm hoặc sửa các cờ này là trả lại đúng
#: quyền vừa được thu về một mối, và lần này còn khó thấy hơn: `cmd` đã đi qua
#: preflight rồi nên không ai soi lại.
#:
#: Hai cờ cuối chưa tồn tại ở trainer. Chúng nằm đây để lần ai đó thêm chúng
#: thì đã có sẵn hàng rào, thay vì phải nhớ dựng lại.
CO_QUYET_DINH_NGUON = ("--train_csv", "--val_csv", "--test_csv",
                       "--split_metadata", "--split_id")


class TestArgvLaThamQuyenCuoiCung:
    """Sau `_build_cmd`, không tầng nào được đổi nguồn dữ liệu nữa."""

    @pytest.fixture(autouse=True)
    def _tro_ve_kho_that(self, monkeypatch):
        from app import training_tasks as tt

        monkeypatch.setattr(tt, "SPLITS_DIR", SPLITS)

    def test_khong_ai_sua_cmd_giua_build_va_spawn(self):
        """Kiểm CẤU TRÚC, không kiểm hành vi — và đó là chủ ý.

        Một ca hành vi chỉ chứng minh đường đi hôm nay đúng. Ca này chứng minh
        không có CHỖ nào để đường đi ngày mai sai: giữa `_build_cmd(...)` và
        `subprocess.Popen(cmd, ...)` không có lệnh nào chạm vào `cmd`.
        """
        import inspect

        from app.training_tasks import run_training_job

        ma = inspect.getsource(run_training_job)
        assert "_build_cmd(" in ma and "Popen(" in ma, (
            "ca này bám vào hình dạng của hàm; hàm đã đổi thì phải viết lại ca")

        than = ma[ma.index("_build_cmd("):ma.index("Popen(")]
        for cach in ("cmd.append", "cmd.extend", "cmd.insert", "cmd +=", "cmd["):
            assert cach not in than, (
                f"`{cach}` xuất hiện giữa dựng lệnh và chạy lệnh — nguồn dữ liệu "
                f"có thể bị đổi SAU khi cổng đồng thuận đã soi.")
        for co in CO_QUYET_DINH_NGUON:
            assert co not in than, (
                f"`{co}` được nhắc tới sau khi lệnh đã dựng xong. Chỉ "
                f"`_build_cmd` (qua resolver) được quyết định nguồn dữ liệu.")

    def test_moi_co_nguon_xuat_hien_DUNG_MOT_lan(self):
        """Trùng cờ là một cách âm thầm khác để ghi đè nguồn.

        `argparse` lấy giá trị CUỐI khi một cờ lặp lại. Nên `--train_csv=A
        --train_csv=B` chạy trên B, trong khi `_split_csvs_of` — vốn trả về mọi
        khớp — báo cả A lẫn B cho cổng đồng thuận. Cổng soi hai tệp, trainer đọc
        một, và cả hai đều "không sai".
        """
        from app.training_tasks import _build_cmd

        for cau_hinh in (
            {"run_purpose": "operational", "operational_split_id": SPLIT_ID},
            {"model_type": "tcn", "dialects": [PHUONG_NGU]},          # legacy
        ):
            cmd = _build_cmd(cau_hinh, Path("m.jsonl"))
            for co in CO_QUYET_DINH_NGUON:
                lan = [a for a in cmd if str(a).startswith(f"{co}=")]
                assert len(lan) <= 1, f"{co} lặp {len(lan)} lần: {lan}"

    def test_ba_co_nguon_deu_tro_vao_MOT_thu_muc(self):
        """train/val/test phải cùng một hiện vật.

        Ghép ba tệp từ hai hiện vật khác nhau cho ra một lượt chạy mà mã băm
        của cả hai đều "đúng" ở tệp của nó, nhưng lượt chạy thì không thuộc
        hiện vật nào.
        """
        from app.training_tasks import _build_cmd, _split_csvs_of

        cmd = _build_cmd(
            {"run_purpose": "operational", "operational_split_id": SPLIT_ID},
            Path("m.jsonl"))

        thu_muc = {Path(p).parent for p in _split_csvs_of(cmd)}
        assert thu_muc == {ARTIFACT}


class TestChayThatBangChinhLenhAPIDung:
    """Mắt xích cuối. Không mô phỏng — chạy `train_tcn` bằng đúng `cmd` đó."""

    def test_toan_chuoi_tu_API_toi_checkpoint(self, tmp_path, monkeypatch,
                                              khai_bao):
        from app import training_tasks as tt

        monkeypatch.setattr(tt, "SPLITS_DIR", SPLITS)
        monkeypatch.setenv("FEATURES_ROOT", str(FEATURES))

        cmd = tt._build_cmd(
            {"model_type": "tcn", "epochs": 1, "batch_size": 32,
             "run_purpose": "operational", "operational_split_id": SPLIT_ID},
            tmp_path / "m.jsonl")

        out = tmp_path / "out"
        out.mkdir()
        # Hai cờ duy nhất được thêm, và không cờ nào chạm tới nguồn dữ liệu.
        cmd = [str(x) for x in cmd] + ["--device=cpu", f"--out_dir={out}"]

        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True,
                              text=True, timeout=1800)
        assert proc.returncode == 0, (
            f"lệnh do API dựng ra chạy hỏng:\n{proc.stdout[-3000:]}\n"
            f"{proc.stderr[-3000:]}")
        assert "[OPERATIONAL]" in proc.stdout, (
            f"trainer KHÔNG vào nhánh vận hành dù API đã ghim hiện vật.\n"
            f"{proc.stdout[-2000:]}")

        import torch

        from processed.train_utils.label_mapping import (
            CHECKPOINT_MAPPING_KEY, consume_checkpoint_mapping,
        )
        from processed.splits.make_splits import class_set_checksum

        ck_path = sorted(out.rglob("*.pt"))
        assert ck_path, f"không có checkpoint:\n{proc.stdout[-1500:]}"
        ck = torch.load(ck_path[0], map_location="cpu", weights_only=False)

        assert ck["num_classes"] == SO_LOP

        idx_to_uid = consume_checkpoint_mapping(ck)
        assert {u: i for i, u in idx_to_uid.items()} == {
            c["class_uid"]: c["target_idx"] for c in khai_bao["classes"]}

        nguon_goc = ck.get("split_provenance") or {}
        assert nguon_goc.get("split_id") == SPLIT_ID
        assert nguon_goc.get("class_set_hash") == khai_bao["class_set_hash"]
        assert (ck[CHECKPOINT_MAPPING_KEY]["class_mapping_hash"]
                == khai_bao["class_mapping_hash"])
        # Tính LẠI từ chính danh sách lớp của checkpoint, không tin giá trị đã
        # chép: một giá trị chép được thì cũng chép sai được.
        assert class_set_checksum(list(idx_to_uid.values())) == \
            khai_bao["class_set_hash"]

        # Lớp yếu phải vắng mặt ở tận cuối chuỗi, không chỉ ở tệp split.
        da_loai = {x["class"] for x in khai_bao["excluded_below_floor"]}
        assert da_loai and not (da_loai & set(idx_to_uid.values()))

    def test_tep_trainer_doc_khong_bi_sua_tren_duong_di(self, khai_bao):
        """sha256 của hiện vật trước và sau khi được tiêu thụ phải bằng nhau.

        Bản nối đầu tiên từng ghi đè `label_key := class_uid` vào bản sao trong
        run dir. Membership không đổi, nhưng tệp trainer thật sự đọc không còn
        khớp từng byte với tệp đã khai — và mã băm mất tư cách làm bằng chứng.
        """
        from processed.train_utils.split_artifact import sha256_file

        for ten in ("train", "val", "test"):
            assert sha256_file(ARTIFACT / f"{ten}.csv") == \
                khai_bao["files"][f"{ten}.csv"]["sha256"], ten

    def test_hien_vat_khai_dung_so_lop_no_chua(self, khai_bao):
        """Chốt hiệu lực: nếu ai đó dựng lại hiện vật khác, ca trên mất nghĩa."""
        for ten in ("train", "val", "test"):
            hang = list(csv.DictReader((ARTIFACT / f"{ten}.csv").open(encoding="utf-8")))
            assert len({r["class_uid"] for r in hang}) == SO_LOP, ten
