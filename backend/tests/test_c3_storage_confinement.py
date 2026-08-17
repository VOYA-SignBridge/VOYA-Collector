"""C3-S — mặt phẳng LƯU TRỮ VẬT LÝ: hiện vật mô hình nằm ở đâu, và ai chạm được.

Chạy:
    bash scripts/run_tests.sh backend/tests/test_c3_storage_confinement.py -q -s

Đây là PHÉP ĐO, không phải bản vá. Layout hiện tại giữ nguyên:

```
processed/train_utils/outputs/
    <model_type>_<stamp>.pt          <- phẳng, MỌI tổ chức cùng thư mục
    job_artifacts/
        <job_id>.log
        <job_id>.metrics.jsonl
```

Ba khả năng cần phân biệt, và chúng dẫn tới ba kết luận khác nhau
=================================================================
```
A  phẳng nhưng không tạo được năng lực xuyên tenant  ->  nợ kiến trúc
B  B đọc/phân giải được hiện vật của A               ->  LỖI THẬT, phải vá
C  B không đọc được nhưng ghi đè/xoá được của A      ->  rủi ro TOÀN VẸN
```

Thư mục phẳng tự nó KHÔNG phải lỗ hổng. Nếu tên tệp mang định danh duy nhất
toàn cục, resolver luôn theo phạm vi, và không API nào nhận đường dẫn tuỳ ý, thì
layout phẳng chỉ là cơ hội gia cố. Kết luận phải đến từ NĂNG LỰC đo được, không
từ hình dạng thư mục.

Và đường dẫn KHÔNG BAO GIỜ là thẩm quyền: `/outputs/iso_a/...` không chứng minh
tệp thuộc `iso_a`. Thẩm quyền vẫn là `training_jobs.tenant_id`. Namespace vật lý
chỉ là phòng thủ chiều sâu và nguồn gốc tốt hơn.
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import training_tasks as tt  # noqa: E402

A = "iso_a"
B = "iso_b"


@pytest.fixture
def kho(tmp_path, monkeypatch):
    """Thư mục đầu ra tí hon, trỏ CẢ hai hằng số của module về nó.

    `JOB_ARTIFACTS_DIR` được suy ra từ `OUTPUTS_DIR` lúc NẠP MODULE, nên chỉ vá
    một hằng số sẽ để lượt dọn chạy trên thư mục thật. Đó đúng kiểu sự cố ngày
    13/08 — test tưởng đang ghi vào tmp mà thật ra ghi vào cây sản xuất.
    """
    out = tmp_path / "outputs"
    arts = out / "job_artifacts"
    arts.mkdir(parents=True)
    monkeypatch.setattr(tt, "OUTPUTS_DIR", out)
    monkeypatch.setattr(tt, "JOB_ARTIFACTS_DIR", arts)
    return out


def _ckpt(thu_muc: Path, ten: str, tuoi_giay: float = 0.0) -> Path:
    p = thu_muc / ten
    p.write_bytes(b"weights")
    if tuoi_giay:
        t = time.time() - tuoi_giay
        os.utime(p, (t, t))
    return p


# =========================================================================
# C3-S4 — hợp đồng ĐẶT TÊN: tên tệp có mang định danh duy nhất không?
# =========================================================================

class TestC3_S4_HopDongDatTen:

    def test_ten_checkpoint_KHONG_mang_dinh_danh_job_hay_tenant(self):
        """Đo hợp đồng đặt tên thật của trainer, đọc từ chính mã sinh ra nó.

        `train_tcn.py` ghi `f"{model_type}_{stamp}.pt"`. Không `job_id`, không
        `tenant_id`. Hệ quả: hai tệp cạnh nhau trong thư mục phẳng chỉ phân biệt
        được bằng `mtime` — và `mtime` chính là thứ mà đường dự phòng và lượt
        dọn định kỳ dùng để quyết định.
        """
        nguon = (REPO_ROOT / "processed" / "train_utils" / "train_tcn.py").read_text(
            encoding="utf-8")
        m = re.search(r'prefix = (f".*?")\s*if not subset_mode else (f".*?")', nguon)
        assert m, "không tìm thấy chỗ đặt tên checkpoint — hợp đồng đã đổi"
        print(f"\n[evidence] prefix thuong  = {m.group(1)}")
        print(f"[evidence] prefix subset  = {m.group(2)}")
        mau = m.group(1) + m.group(2)
        assert "job_id" not in mau
        assert "tenant" not in mau

    def test_ten_hien_vat_phu_CO_mang_job_id(self, kho):
        """Nhật ký và tệp chỉ số thì có: `<job_id>.log`, `<job_id>.metrics.jsonl`.

        Nên hai loại hiện vật của cùng một lượt chạy có hai hợp đồng đặt tên
        khác nhau — và loại quan trọng hơn (trọng số mô hình) lại là loại không
        có định danh.
        """
        nguon = (REPO_ROOT / "backend" / "app" / "training_tasks.py").read_text(
            encoding="utf-8")
        assert 'f"{job_id}.metrics.jsonl"' in nguon
        assert 'f"{job_id}.log"' in nguon


# =========================================================================
# C3-S6 — đường DỰ PHÒNG chọn checkpoint theo mtime trên thư mục dùng chung
# =========================================================================

class TestC3_S6_DuPhongChonNhamHienVat:

    def test_du_phong_tra_ve_tep_moi_nhat_BAT_KE_thuoc_ai(self, kho):
        """★ Đây là năng lực xuyên tenant, không phải chuyện hình thức.

        Kịch bản, và nó KHÔNG cần ai cố ý tấn công:

        ```
        job của A chạy xong nhưng bản ghi `final` thiếu checkpoint_path
        (trainer bị giết, tệp chỉ số cụt, ghi hụt dòng cuối)
            -> đường dự phòng chọn tệp .pt MỚI NHẤT trong outputs/
            -> tệp đó là của B, vì B vừa train xong sau A
            -> hàng job của A ghi checkpoint của B
        ```

        Từ đó mọi phép kiểm phạm vi đều ĐẠT: hàng job thuộc A thật, RLS cho A
        đọc thật. A tải về, đánh giá, và đưa vào sản xuất trọng số của B — qua
        một đường hoàn toàn hợp lệ. Không tầng nào phía trên phát hiện được, vì
        không tầng nào sai.

        VÁ 16/08/2026: đường dự phòng không đoán nữa. Lọc theo tenant là bất
        khả — tên tệp không mang định danh — nên lựa chọn duy nhất đúng là DỪNG.
        """
        _ckpt(kho, "tcn_A.pt", tuoi_giay=60)     # A xong trước
        cua_b = _ckpt(kho, "tcn_B.pt")           # B xong sau

        chon = tt._fallback_checkpoint()
        print(f"\n[evidence] du phong chon: {chon!r} (cua B = {cua_b.name})")
        assert chon == "", (
            "đường dự phòng lại đoán checkpoint. Thư mục dùng chung + tên tệp "
            "không mang định danh = không có cách nào biết tệp thuộc về ai.")

    def test_job_khong_biet_checkpoint_cua_minh_thi_FAIL_chu_khong_completed(self):
        """Trả rỗng chưa đủ — job phải nói ra là nó HỎNG.

        Một job `completed` mà `checkpoint_path` rỗng là trạng thái không ai đọc
        đúng được, và bước kế tiếp sẽ đi tìm một tệp không tồn tại. Kiểm bằng
        cấu trúc: nhánh xử lý phải đặt `status="failed"` và leo thang.
        """
        nguon = (REPO_ROOT / "backend" / "app" / "training_tasks.py").read_text(
            encoding="utf-8")
        i = nguon.index("_fallback_checkpoint()\n")
        than = nguon[i:i + 1400]
        co_failed = 'status="failed"' in than
        print(f"\n[evidence] nhanh thieu checkpoint co status=failed: {co_failed}")
        assert co_failed
        assert 'source="checkpoint_missing"' in than


# =========================================================================
# C3-S5 — lượt dọn định kỳ xoá hiện vật XUYÊN tenant
# =========================================================================

class TestC3_S5_LuotDonXuyenToChuc:

    def test_giu_N_moi_nhat_TREN_TOAN_THU_MUC_nen_B_xoa_duoc_cua_A(
            self, kho, monkeypatch):
        """★ Rủi ro TOÀN VẸN: B không đọc được của A, nhưng XOÁ được.

        `cleanup_training_artifacts` giữ N tệp `.pt` mới nhất trong thư mục
        dùng chung. Một tổ chức train nhiều hơn sẽ đẩy checkpoint của tổ chức
        khác ra khỏi cửa sổ giữ — và lượt dọn xoá chúng.

        Đây không phải kịch bản tấn công tinh vi: nó là hệ quả bình thường của
        việc hai khách hàng cùng dùng hệ thống, và nó xảy ra theo lịch.

        VÁ 16/08/2026: nhóm theo chủ sở hữu (tra từ hàng job) rồi mới áp N.
        """
        monkeypatch.setenv("TRAINING_OUTPUTS_KEEP", "2")
        cua_a = _ckpt(kho, "tcn_cua_A.pt", tuoi_giay=300)
        b1 = _ckpt(kho, "tcn_B_1.pt", tuoi_giay=20)
        b2 = _ckpt(kho, "tcn_B_2.pt", tuoi_giay=10)
        monkeypatch.setattr(tt, "_checkpoint_owners",
                            lambda: {str(cua_a): A, str(b1): B, str(b2): B})

        tt.cleanup_training_artifacts.run()

        con_lai = sorted(p.name for p in kho.glob("*.pt"))
        print(f"\n[evidence] giu lai: {con_lai}")
        print(f"[evidence] checkpoint cua A con: {cua_a.exists()}")
        assert cua_a.exists(), (
            "B train nhiều hơn KHÔNG được đẩy checkpoint của A ra khỏi cửa sổ "
            "giữ. `giữ N bản mới nhất` chỉ có nghĩa trong phạm vi MỘT tổ chức.")

    def test_moi_to_chuc_van_bi_ap_han_muc_cua_rieng_no(self, kho, monkeypatch):
        """Chốt hiệu lực: bản vá không được biến lượt dọn thành không-làm-gì.

        Nếu chỉ kiểm "A còn sống" thì một bản vá `return []` cũng xanh. Ca này
        đòi hạn mức vẫn được áp — trong phạm vi từng tổ chức.
        """
        monkeypatch.setenv("TRAINING_OUTPUTS_KEEP", "1")
        a_cu = _ckpt(kho, "tcn_A_cu.pt", tuoi_giay=300)
        a_moi = _ckpt(kho, "tcn_A_moi.pt", tuoi_giay=200)
        b1 = _ckpt(kho, "tcn_B_1.pt", tuoi_giay=10)
        monkeypatch.setattr(tt, "_checkpoint_owners",
                            lambda: {str(a_cu): A, str(a_moi): A, str(b1): B})

        tt.cleanup_training_artifacts.run()

        print(f"\n[evidence] A cu={a_cu.exists()} A moi={a_moi.exists()} "
              f"B={b1.exists()}")
        assert not a_cu.exists(), "hạn mức của A không được áp"
        assert a_moi.exists() and b1.exists()

    def test_tep_KHONG_tra_duoc_chu_thi_KHONG_bi_xoa(self, kho, monkeypatch):
        """"Không biết của ai" không phải căn cứ để xoá.

        Cùng luật đã áp ở C2c, đổi chiều: ở đó không biết chủ thì không cho
        đọc; ở đây không biết chủ thì không được xoá.
        """
        monkeypatch.setenv("TRAINING_OUTPUTS_KEEP", "0")
        mo_coi = _ckpt(kho, "tcn_khong_ro_chu.pt", tuoi_giay=999)
        monkeypatch.setattr(tt, "_checkpoint_owners", lambda: {})

        tt.cleanup_training_artifacts.run()

        print(f"\n[evidence] tep khong ro chu con: {mo_coi.exists()}")
        assert mo_coi.exists()

    def test_khong_tra_duoc_chu_so_huu_thi_BO_QUA_ca_luot_don(self, kho, monkeypatch):
        """CSDL hỏng thì lượt dọn phải đứng im, không quay về quét mù.

        Đây là hình dạng lỗi đã gặp nhiều lần trong đợt này: một nhánh xử lý
        lỗi âm thầm hạ cấp về hành vi cũ, kém an toàn hơn.
        """
        monkeypatch.setenv("TRAINING_OUTPUTS_KEEP", "0")
        a = _ckpt(kho, "tcn_A.pt", tuoi_giay=300)

        def _no(*_a, **_k):
            raise RuntimeError("DB down")

        monkeypatch.setattr(tt, "_checkpoint_owners", _no)
        tt.cleanup_training_artifacts.run()

        print(f"\n[evidence] tep con sau khi tra chu that bai: {a.exists()}")
        assert a.exists()

    def test_luot_don_khong_biet_gi_ve_tenant(self):
        """Tác vụ khai `platform_wide=True` — toàn nền tảng, không phạm vi nào.

        Khai như vậy là ĐÚNG với một lượt dọn hạ tầng. Vấn đề không nằm ở phạm
        vi của tác vụ mà ở chỗ chính sách giữ-N được áp trên một tập DÙNG CHUNG:
        "20 checkpoint mới nhất" là một câu hỏi chỉ có nghĩa khi hỏi trong phạm
        vi một tổ chức.
        """
        nguon = (REPO_ROOT / "backend" / "app" / "training_tasks.py").read_text(
            encoding="utf-8")
        i = nguon.index("def cleanup_training_artifacts")
        than = nguon[i:i + 2000]
        print(f"\n[evidence] than tac vu nhac 'tenant': {'tenant' in than}")
        assert "tenant" not in than


# =========================================================================
# C3-S1 / C3-S2 / C3-S3 — đọc: có API nào phát tệp theo đường dẫn không?
# =========================================================================

class TestC3_S1_S2_S3_DuongDoc:

    def test_KHONG_endpoint_nao_nhan_duong_dan_tu_nguoi_goi(self):
        """C3-S3 — phân biệt "cấp quyền theo định danh" với "cầm được đường dẫn".

        Nếu không có giao diện nào nhận đường dẫn tuỳ ý thì ca S3 là NOT
        APPLICABLE, và ta ghi đúng như vậy thay vì dựng một endpoint giả để có
        cái mà kiểm.

        Bản đầu của ca này quét cả tệp tìm chuỗi `"path: str"` và báo ĐỎ. Sai —
        nó khớp vào tham số của hàm trợ giúp nội bộ (`_update_registry`,
        `_notify_realtime_service_reload`) và vào trường `checkpoint_path` của
        `TrainingJob`, vốn là mô hình TRẢ VỀ. Không cái nào là đầu vào của người
        gọi. Một bộ dò quét cả tệp trả lời câu "chuỗi này có xuất hiện không",
        không phải câu "endpoint có nhận đường dẫn không".

        Bản này chỉ soi CHỮ KÝ của các endpoint và các mô hình dùng làm THÂN
        yêu cầu.
        """
        import inspect

        from fastapi.routing import APIRoute

        from app.routers.training import router

        ngo = []
        for route in router.routes:
            if not isinstance(route, APIRoute):
                continue
            for ten, tham in inspect.signature(route.endpoint).parameters.items():
                if re.search(r"path|file|key|dir", ten, re.IGNORECASE):
                    ngo.append(f"{route.path}({ten})")
        print(f"\n[evidence] endpoint nhan duong dan: {ngo or 'khong co'}")
        assert not ngo, (
            f"endpoint nhận đường dẫn từ người gọi: {ngo} — C3-S3 chuyển từ NOT "
            f"APPLICABLE sang phải kiểm thật")

    def test_TrainingJob_khong_bao_gio_la_than_yeu_cau(self):
        """`TrainingJob` mang `checkpoint_path`, nên nó phải chỉ là mô hình TRẢ VỀ.

        Dùng nó làm thân yêu cầu ở bất kỳ đâu là mở đúng cánh cửa mà ca trên
        vừa đóng: người gọi tự khai đường dẫn checkpoint.
        """
        import inspect

        from fastapi.routing import APIRoute

        from app.routers.training import TrainingJob, router

        vi_pham = []
        for route in router.routes:
            if not isinstance(route, APIRoute):
                continue
            for ten, tham in inspect.signature(route.endpoint).parameters.items():
                if tham.annotation is TrainingJob:
                    vi_pham.append(f"{route.path}({ten})")
        print(f"\n[evidence] endpoint nhan TrainingJob lam body: {vi_pham or 'khong co'}")
        assert not vi_pham

    def test_duong_dan_checkpoint_chi_den_tu_hang_job(self):
        """C3-S2 — người gọi lấy được đường dẫn CHỈ qua hàng job của họ.

        Mà hàng job thì đã nằm dưới RLS và dưới cổng cache đã vá ở C3. Nên
        đường ĐỌC được canh bởi tầng logic, không bởi vị trí tệp.
        """
        nguon = (REPO_ROOT / "backend" / "app" / "routers" / "training.py").read_text(
            encoding="utf-8")
        # Mọi lượt đọc `checkpoint_path` đều đi từ đối tượng job, không từ tham
        # số đường dẫn của request.
        assert "job.checkpoint_path" in nguon
