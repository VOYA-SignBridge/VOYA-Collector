"""`SplitProvenance` phải nói về ĐÚNG hiện vật lượt chạy sẽ đọc, và đếm đúng người.

Vì sao tệp này tồn tại
======================
Bước 3 của giao diện huấn luyện từng hiện ba thanh trượt tỉ lệ train/val/test.
Chúng là state cục bộ: không gì gửi chúng lên máy chủ, và máy chủ không có tham
số nào để nhận. Người dùng kéo, và không có gì xảy ra. Trong khi đó màn hình im
lặng về sự thật quyết định cách đọc con số cuối: cùng một người có ở cả tập học
lẫn tập đánh giá hay không — khác biệt đáng 0.129 độ chính xác trên tập này.

`SplitProvenance` thay chỗ đó. Nhưng nó chỉ có giá trị khi hai điều kiện giữ
được, và cả hai đều hỏng theo kiểu IM LẶNG:

  1. Nó phải mô tả hiện vật mà trainer THẬT SỰ đọc. Một bản trước của ý tưởng
     này đọc thẳng `processed/splits/{train,val,test}.csv` ở thư mục gốc — nhưng
     ở kho này ba tệp ấy là hiện vật nghiên cứu ĐÓNG BĂNG, còn đường vận hành đã
     chuyển sang `operational/<split_id>/`. Một màn hình mô tả tệp mà lượt chạy
     không đọc còn tệ hơn một màn hình không nói gì: nó tạo ra niềm tin sai.

  2. Nó phải đếm NGƯỜI, không phải đếm chuỗi. "Trân", "Tran" và "trân" là một
     người; đếm theo chuỗi thô sẽ thấy ba danh tính khác nhau, kết luận hai phía
     không giao nhau, và báo "đã tách người ký" cho một split rò rỉ.

Cả hai đều cho ra một màn hình trông bình thường và một con số trông hợp lý, nên
không có cách nào phát hiện bằng mắt.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.routers import training as tr  # noqa: E402

COT = ["sample_uid", "class_uid", "dialect", "user_id", "signer_id"]


def _viet_csv(path: Path, nguoi_ky, *, cot=None) -> None:
    """Một split CSV tối thiểu: mỗi người ký một dòng."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = cot if cot is not None else COT
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for i, ai in enumerate(nguoi_ky):
            row = {c: "" for c in fieldnames}
            row.update({"sample_uid": f"s{i}", "class_uid": "c1", "dialect": "hoa-de"})
            if isinstance(ai, tuple):
                user_id, signer_id = ai
            elif "user_id" in row:
                user_id, signer_id = ai, ""
            else:
                # Không có cột `user_id` trong lược đồ này thì giá trị đi vào
                # `signer_id` — nếu không, hàng ra đời KHÔNG có danh tính nào và
                # bài kiểm "lùi về signer_id" lại đo một ca khác hẳn.
                user_id, signer_id = "", ai
            if "user_id" in row:
                row["user_id"] = user_id
            if "signer_id" in row:
                row["signer_id"] = signer_id
            w.writerow(row)


@pytest.fixture
def hien_vat(tmp_path, monkeypatch):
    """Thay `_resolve_for_run` bằng một hiện vật giả trỏ vào CSV trong tmp.

    Chặn ở ĐÂY chứ không dựng hiện vật thật qua CLI: bộ phân giải đã có bộ kiểm
    riêng (`test_split_artifact_resolver`, `test_split_resolver_tenant_gate`), và
    dựng lại nó ở đây sẽ kiểm hai lần cùng một thứ trong khi bỏ sót thứ CHỈ tệp
    này kiểm — phép đếm người ký và các câu cảnh báo.
    """
    from processed.train_utils.split_artifact import SplitArtifact

    def _lam(train, val, test, *, cot=None, purpose="operational",
             split_id="sp-test", owner_state="owned"):
        d = tmp_path / split_id
        _viet_csv(d / "train.csv", train, cot=cot)
        _viet_csv(d / "val.csv", val, cot=cot)
        _viet_csv(d / "test.csv", test, cot=cot)
        art = SplitArtifact(
            split_id=split_id, purpose=purpose,
            train_csv=d / "train.csv", val_csv=d / "val.csv", test_csv=d / "test.csv",
            tenant_id="default", owner_state=owner_state)
        import app.training_tasks as tt
        monkeypatch.setattr(tt, "_resolve_for_run", lambda cfg, *, tenant_id: art)
        return art

    return _lam


# ---------------------------------------------------------------------------
# 1. Một cửa: cái được hiển thị phải là cái được huấn luyện
# ---------------------------------------------------------------------------

def test_di_qua_dung_mot_cua_resolve_for_run():
    """`_split_provenance` phải hỏi `_resolve_for_run`, không tự mở tệp.

    Khẳng định ở mức MÃ NGUỒN vì đây là bất biến về cấu trúc: một lần ai đó
    thêm `open(SPLITS_DIR / "train.csv")` vào đây thì màn hình lại mô tả hiện
    vật đóng băng trong khi lượt chạy đọc `operational/<split_id>/`, và không
    có bài kiểm hành vi nào thấy được điều đó — cả hai đường đều trả về một
    `SplitProvenance` trông hợp lệ.
    """
    import inspect

    src = inspect.getsource(tr._split_provenance)
    assert "_resolve_for_run" in src, (
        "provenance không còn đi qua cửa chung; nó sẽ mô tả một hiện vật khác "
        "với hiện vật trainer đọc")
    assert "SPLITS_DIR" not in src, (
        "provenance đang đọc thẳng thư mục split gốc — ba tệp ở đó là hiện vật "
        "nghiên cứu ĐÓNG BĂNG, không phải thứ một lượt vận hành đọc")


def test_mang_theo_danh_tinh_cua_hien_vat(hien_vat):
    hien_vat(["A"], ["B"], ["C"], split_id="sp-42")
    p = tr._split_provenance(tenant_id="default")
    assert p.split_id == "sp-42"
    assert p.purpose == "operational"
    assert p.owner_state == "owned"
    assert p.counts == {"train": 1, "val": 1, "test": 1}


# ---------------------------------------------------------------------------
# 2. Đếm NGƯỜI, không đếm chuỗi
# ---------------------------------------------------------------------------

def test_bang_gop_chinh_ta_duoc_ap_dung(hien_vat):
    """"Trân" ở train và "Tran" ở test là MỘT người — phải báo là rò rỉ.

    Đây là bài kiểm trung tâm của tệp. So chuỗi thô sẽ thấy hai danh tính khác
    nhau, kết luận hai phía không giao nhau, và báo "đã tách người ký" cho một
    split mà cùng một người xuất hiện ở cả hai bên. Màn hình khi ấy nói điều
    ngược hẳn với sự thật, bằng một giao diện trông hoàn toàn bình thường.

    Cả hai biến thể cùng ánh xạ về `S001` trong
    `config/legacy_signer_mapping.json`.
    """
    hien_vat(["Trân"], [], ["Tran"])
    p = tr._split_provenance(tenant_id="default")

    assert p.signers["train"] == ["S001"], "bảng gộp không được áp ở phía train"
    assert p.signers["test"] == ["S001"], "bảng gộp không được áp ở phía test"
    assert p.signer_disjoint is False
    assert p.warning and "người ký xuất hiện ở cả" in p.warning


def test_uu_tien_user_id_chu_khong_phai_signer_id(hien_vat):
    """`user_id` thắng `signer_id`, và điều đó thay đổi kết luận.

    `signer_id` được suy ra từ TÀI KHOẢN thu, nên nhiều người ký chung một tài
    khoản bị gộp thành một danh tính — dữ liệu hoa-de có đúng ca đó (`S010`,
    tài khoản "tran", chứa cả Nhung lẫn Khoa).

    Ở đây hai hàng mang CÙNG `signer_id` nhưng KHÁC `user_id`. Đọc theo
    `signer_id` sẽ thấy một người ở cả hai phía; đọc theo `user_id` thấy đúng
    hai người khác nhau. Kết luận về việc tách người ký lật ngược hoàn toàn tuỳ
    theo cột nào được đọc, nên cột nào được đọc phải được khoá lại.
    """
    hien_vat([("Nhung", "S010")], [], [("Khoa", "S010")])
    p = tr._split_provenance(tenant_id="default")

    assert p.identity_column == "user_id"
    # `S012` / `S013`, không phải "Nhung" / "Khoa": bảng gộp được áp SAU khi
    # `user_id` thắng, nên hai phép biến đổi cùng được khoá trong một khẳng định.
    assert p.signers["train"] == ["S012"]
    assert p.signers["test"] == ["S013"]
    assert p.signer_disjoint is True, (
        "đang đọc theo signer_id: hai người khác nhau bị gộp thành một và split "
        "bị chấm nhầm là có rò rỉ")


def test_lui_ve_signer_id_khi_khong_co_user_id(hien_vat):
    """Thiếu `user_id` thì `signer_id` vẫn hơn là không có danh tính nào."""
    hien_vat(["S001"], [], ["S002"], cot=["sample_uid", "class_uid", "dialect", "signer_id"])
    p = tr._split_provenance(tenant_id="default")
    assert p.identity_column == "signer_id"
    assert p.signer_disjoint is True


def test_split_tach_nguoi_that_thi_khong_canh_bao(hien_vat):
    """Ba phân vùng, ba người khác nhau — không có gì để cảnh báo.

    `val` cũng phải rời khỏi `train`, không chỉ `test`. `val` là thứ chọn epoch
    tốt nhất, nên một người ký nằm ở cả train lẫn val làm phép chọn ấy lạc quan
    — và `_assert_signer_disjoint` trong `make_splits.py` đòi cả ba phân vùng
    rời nhau chứ không chỉ hai.
    """
    hien_vat(["Minh"], ["Trâm"], ["Khoa"])
    p = tr._split_provenance(tenant_id="default")
    assert p.signers == {"train": ["S002"], "val": ["S003"], "test": ["S013"]}
    assert p.signer_disjoint is True
    assert p.warning is None


# ---------------------------------------------------------------------------
# 3. Không kiểm được phải đọc ra là "chưa bảo đảm"
# ---------------------------------------------------------------------------

def test_khong_co_cot_dinh_danh_thi_noi_ra(hien_vat):
    """Không có cột người ký: `signer_disjoint` phải là False, kèm câu giải thích.

    False ở đây KHÔNG có nghĩa "đã đo và thấy rò rỉ" — nó có nghĩa "chưa bảo
    đảm". Mặc định ngược lại sẽ biến một split không kiểm được thành một split
    được chấm là an toàn, và đó là chiều sai để đoán.
    """
    hien_vat(["x"], ["y"], ["z"], cot=["sample_uid", "class_uid", "dialect"])
    p = tr._split_provenance(tenant_id="default")

    assert p.identity_column is None
    assert p.signer_disjoint is False
    assert p.warning and "không có cột định danh người ký" in p.warning


def test_khong_phan_giai_duoc_thi_noi_ra_chu_khong_no(monkeypatch):
    """Đường HIỂN THỊ không được ném: một hiện vật hỏng phải hiện thành câu chữ.

    Nếu nó ném, `/dataset/info` trả 500 và cả trang biến mất vì một split chưa
    dựng — trong khi thứ người dùng cần đọc lúc ấy chính là lý do. Phần CHẶN
    thật nằm ở chỗ phái job và vẫn chặn nguyên.
    """
    import app.training_tasks as tt

    def _no(cfg, *, tenant_id):
        raise RuntimeError("hiện vật không xác minh được")

    monkeypatch.setattr(tt, "_resolve_for_run", _no)
    p = tr._split_provenance(tenant_id="default")
    assert p.split_id is None
    assert p.warning and "Chưa xác định được tập dữ liệu" in p.warning
    # Chuỗi lỗi Python KHÔNG được ra màn hình (14/09: "No module named
    # 'processed'" từng hiện nguyên văn trong cảnh báo của trang huấn luyện).
    assert "hiện vật không xác minh được" not in p.warning
    assert "RuntimeError" not in p.warning


def test_thu_muc_workspace_duoc_dua_vao_sys_path_truoc_khi_import():
    """`/workspace` không nằm sẵn trên sys.path của tiến trình API; thiếu bước
    chèn thì import `processed.*` ném ở mọi lượt gọi."""
    import inspect
    src = inspect.getsource(tr._split_provenance)
    assert "sys.path.insert(0, workspace)" in src


def test_tra_None_thi_noi_la_mac_dinh_trainer(monkeypatch):
    """`_resolve_for_run` trả None = trainer đi theo mặc định của chính nó.

    Không được đoán hộ rằng đó là ba tệp gốc: nhánh nghiên cứu ghim
    `split_version` cũng trả None, và hai trường hợp ấy đọc hai nơi khác nhau.
    """
    import app.training_tasks as tt

    monkeypatch.setattr(tt, "_resolve_for_run", lambda cfg, *, tenant_id: None)
    p = tr._split_provenance(tenant_id="default")
    assert p.split_id is None
    assert p.signer_disjoint is False
    assert p.warning and "mặc định của trainer" in p.warning


def test_moi_import_deu_nam_trong_khoi_bat_loi():
    """Không import nào của `_split_provenance` được đứng ngoài `try`.

    `processed.train_utils` sống ngoài gói `app`; nó có mặt nhờ bố cục thư mục
    của container chứ không nhờ một phụ thuộc đã khai. Một `import` đứng ngoài
    khối bắt lỗi sẽ ném `ImportError` và biến hàm "không bao giờ ném" thành
    nguồn của một trang 500 — trong khi thứ người dùng cần lúc ấy chính là câu
    giải thích vì sao.

    Khẳng định ở mức mã nguồn vì đường hỏng này không tái hiện được trong bộ
    test: ở đây `processed` LUÔN import được, nên một bài kiểm hành vi sẽ xanh
    dù import nằm ở đâu.
    """
    import inspect
    import textwrap

    src = textwrap.dedent(inspect.getsource(tr._split_provenance))
    than = src.split("\n")
    try_o = next(i for i, l in enumerate(than) if l.strip() == "try:")

    ngoai = [l.strip() for l in than[:try_o]
             if l.strip().startswith(("import ", "from ")) and "csv" not in l]
    assert not ngoai, (
        "import đứng ngoài khối bắt lỗi của `_split_provenance`: "
        f"{ngoai} — đường hiển thị sẽ ném thay vì nói ra")
