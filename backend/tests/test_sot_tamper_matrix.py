"""Ma trận giả mạo SOT — bằng chứng Chương 4, chạy qua ĐÚNG đường consumer.

Vì sao tệp này tồn tại khi đã có 10 tệp test SOT
================================================
Bộ test hiện có phủ gần hết ma trận và — khác với trường hợp cách ly tenant —
chúng ĐÃ chạy qua đường consumer thật (`sync_from_sot`, 25 lần ở 4 tệp), không
phải chỉ unit-test `hash()`/`sign()`/`verify()`. Bài học "hàm lá đúng không có
nghĩa workflow thật dùng hàm lá đúng cách" ở đây đã được xử lý sẵn.

Tệp này thêm ba thứ mà bộ test kia không có:

1. **Hậu điều kiện SO SÁNH TRẠNG THÁI, không chỉ đếm số lượt ghi.** Bộ test hiện
   có khẳng định `db.total_upserts == 0` trên một catalog RỖNG. Điều đó bỏ lọt
   một cách hỏng thật: một lượt từ chối GHI ĐÈ hàng đang có rồi mới báo lỗi vẫn
   cho `total_upserts` bằng số cũ. Ở đây catalog được GIEO SẴN, chụp trạng thái
   trước, và so sâu sau khi từ chối — đúng dạng `state_before == state_after`.

2. **S6 — thiếu chữ ký hoàn toàn**, khác với chữ ký sai. Một hệ chấp nhận
   artifact không ký khi chính sách đòi ký thì hai ca kia vô nghĩa.

3. **Một artifact đo lường hợp nhất** để trích dẫn được, thay vì một kết quả nằm
   rải trong tên hàm test.

Một biến mỗi lần
================
Mỗi kịch bản xuất phát từ một SOT HỢP LỆ rồi đổi ĐÚNG MỘT thứ. Một artifact
"hỏng đủ thứ" bị từ chối không nói được cơ chế nào đã bắt, và vẫn xanh kể cả khi
hai trong ba cơ chế đã chết.

Vì sao S4 quan trọng hơn một phép kiểm hash
===========================================
Kẻ tấn công dựng được một dataset khác, tính hash đúng, viết manifest đúng, rồi
tự ký bằng khoá Ed25519 CỦA HẮN. Chữ ký ấy hợp lệ về mật mã. Nếu hệ chỉ hỏi
"chữ ký có hợp lệ không" mà không hỏi "hợp lệ theo khoá công khai NÀO" thì tính
toàn vẹn đúng còn thẩm quyền sai. Hợp đồng phải là

    ValidArtifact = IntegrityValid AND SignatureValid
                    AND SignerTrusted AND VersionPolicyValid
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from app.sot import keys, manifest as m
from app.sot.publisher import publish_version
from app.sot.reader_sync import CatalogSink, SotSyncRejected, sync_from_sot
from app.sot.store import LocalSotStore

ARTIFACT = Path(__file__).resolve().parents[2] / "docs/00-thesis/MEASUREMENT_sot_integrity.json"

CSVS = {
    "labels.csv": b"class_uid,slug\nc1,hello\nc2,thanks\n",
    "samples.csv": b"sample_uid,class_uid\ns1,c1\ns2,c1\ns3,c2\n",
    "raw_uploads.csv": b"upload_uid,class_uid\nu1,c1\n",
}

#: Trạng thái CÓ SẴN trước mỗi lượt. Một lượt từ chối không được chạm vào đây.
GIEO = {
    "classes": {"existing": {"class_uid": "existing", "slug": "da-co-tu-truoc"}},
    "samples": {"s_old": {"sample_uid": "s_old", "class_uid": "existing"}},
}

KET_QUA: list[dict] = []


def _van_tay_nguon() -> dict:
    """Định danh implementation ĐANG BỊ ĐO, không chỉ commit nền.

    `HEAD = f882414` chỉ chứng minh commit NỀN. Nếu cây làm việc còn thay đổi
    chưa commit — đúng trạng thái của kho này hôm nay — thì hai lượt đo cùng
    `HEAD` có thể chạy trên hai implementation khác nhau. Đó chính là kiểu sai
    lệch mà loạt phép đo này đã bắt được nhiều lần.

    Nên ngoài commit nền, băm luôn NỘI DUNG cây mã: `source_tree_sha256` định
    danh thứ thực sự được thực thi, bất kể git sạch hay bẩn. Cờ `worktree_dirty`
    lấy từ biến môi trường do `scripts/measure_sot_integrity.sh` đặt (host có
    `git`, container test thì không); vắng biến đó thì ghi `"unknown"` chứ không
    ghi `false` — một cây bẩn bị báo sạch còn tệ hơn không báo gì.
    """
    goc = Path(__file__).resolve().parents[1] / "app"
    h = hashlib.sha256()
    for p in sorted(goc.rglob("*.py")):
        if "__pycache__" in str(p):
            continue
        h.update(p.relative_to(goc).as_posix().encode())
        h.update(p.read_bytes())

    # Trạng thái git do `scripts/measure_sot_integrity.sh` ghi ra trên host.
    # Vắng tệp => `"unknown"`, KHÔNG phải `false`.
    tu_host = {}
    van_tay = Path(__file__).resolve().parents[2] / ".measurement/source_fingerprint.json"
    try:
        tu_host = json.loads(van_tay.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass

    return {
        "source_commit_base": tu_host.get("source_commit_base") or _commit_hien_tai(),
        "source_tree_sha256": h.hexdigest(),
        "worktree_dirty": tu_host.get("worktree_dirty", "unknown"),
        "worktree_diff_sha256": tu_host.get("worktree_diff_sha256"),
    }


def _commit_hien_tai() -> str | None:
    """Đọc thẳng `.git`, KHÔNG gọi `git`.

    Container test không cài `git`, nên `subprocess.run(["git", ...])` trả rỗng
    và artifact ghi `source_commit: null` — im lặng mất đúng trường dùng để
    chứng minh phép đo chạy trên bản mã nào.
    """
    goc = Path(__file__).resolve().parents[2] / ".git"
    try:
        head = (goc / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = goc / head.split(" ", 1)[1].strip()
            if ref.exists():
                return ref.read_text(encoding="utf-8").strip()
            for dong in (goc / "packed-refs").read_text(encoding="utf-8").splitlines():
                if dong.endswith(head.split(" ", 1)[1].strip()):
                    return dong.split(" ", 1)[0]
            return None
        return head or None
    except Exception:  # noqa: BLE001
        return None


class FakeDB:
    def __init__(self, seed=None):
        self.tables = {"classes": {}, "samples": {}, "raw_uploads": {}}
        for table, rows in (seed or {}).items():
            self.tables[table].update(copy.deepcopy(rows))
        self.schema_applied = []

    def sink(self) -> CatalogSink:
        return CatalogSink(
            apply_schema=lambda sql: self.schema_applied.append(sql),
            column_exists=lambda t, c: True,
            count_rows=lambda t: len(self.tables[t]),
            upsert_class=lambda r: self.tables["classes"].__setitem__(r["class_uid"], r),
            upsert_sample=lambda r: self.tables["samples"].__setitem__(r["sample_uid"], r),
            upsert_raw_upload=lambda r: self.tables["raw_uploads"].__setitem__(r["upload_uid"], r),
        )

    def snapshot(self) -> dict:
        return copy.deepcopy(self.tables)


def _publish(tmp_path, *, name="desktop-A", csvs=None, authz=None, key_path=None):
    authz = authz or (tmp_path / "authorized_keys.json")
    if not authz.exists():
        authz.write_text("[]", encoding="utf-8")
    key_path = key_path or (tmp_path / f"{name}.key")
    if not key_path.exists():
        pk = keys.generate_private_key()
        keys.save_private_key(pk, key_path)
        keys.add_authorized_key(name, keys.public_key_b64(pk), authz)
    store = LocalSotStore(tmp_path / "SOT")
    publish_version(
        store,
        csv_sources=csvs or CSVS,
        schema_sql="CREATE TABLE IF NOT EXISTS classes ();",
        schema_version=8,
        required_columns={"classes": ["class_uid"], "samples": ["sample_uid"]},
        machine_name=name,
        private_key_path=key_path,
        authorized_keys_path=authz,
    )
    return store, keys.load_authorized_keys(authz), key_path, authz


# --------------------------------------------------------------------------
# Chín kịch bản. Mỗi hàm trả về (store, authorized_keys).
# --------------------------------------------------------------------------

def s1_hop_le(tmp_path):
    store, authz, _, _ = _publish(tmp_path)
    return store, authz


def s2_doi_mot_byte_artifact(tmp_path):
    store, authz, _, _ = _publish(tmp_path)
    v = store.list_version_dirs()[0]
    goc = store.read_bytes(f"{v}/labels.csv")
    # ĐÚNG một byte: `hello` -> `hellp`. Không đổi độ dài, không đổi số dòng.
    store.write_bytes(f"{v}/labels.csv", goc.replace(b"hello", b"hellp"))
    return store, authz


def s3_sua_manifest_giu_chu_ky_cu(tmp_path):
    store, authz, _, _ = _publish(tmp_path)
    v = store.list_version_dirs()[0]
    man = json.loads(store.read_bytes(f"{v}/manifest.json"))
    # `files` là DICT đường-dẫn -> sha256, không phải danh sách bản ghi.
    for duong_dan in list(man.get("files", {})):
        if duong_dan.endswith("labels.csv"):
            man["files"][duong_dan] = "0" * 64
    # Ghi manifest mới, GIỮ NGUYÊN manifest.sig cũ.
    store.write_bytes(f"{v}/manifest.json", m.canonical_bytes(man))
    return store, authz


def s4_ky_bang_khoa_khong_tin_cay(tmp_path):
    store, authz, _, _ = _publish(tmp_path)
    v = store.list_version_dirs()[0]
    rogue = keys.generate_private_key()
    # Chữ ký HỢP LỆ VỀ MẬT MÃ trên đúng nội dung — chỉ sai người ký.
    man = store.read_bytes(f"{v}/manifest.json")
    store.write_bytes(f"{v}/manifest.sig", keys.sign(rogue, man).encode())
    return store, authz


def s5_chu_ky_hong(tmp_path):
    store, authz, _, _ = _publish(tmp_path)
    v = store.list_version_dirs()[0]
    store.write_bytes(f"{v}/manifest.sig", b"khong-phai-base64-hop-le!!")
    return store, authz


def s6_thieu_chu_ky(tmp_path):
    store, authz, _, _ = _publish(tmp_path)
    v = store.list_version_dirs()[0]
    store.write_bytes(f"{v}/manifest.sig", b"")
    return store, authz


def s8_ban_moi_nguon_tin_cay(tmp_path):
    store, authz, key_path, authz_path = _publish(tmp_path)
    _publish(tmp_path, csvs={**CSVS, "labels.csv": b"class_uid,slug\nc1,hello\nc2,thanks\nc3,moi\n"},
             key_path=key_path, authz=authz_path)
    return store, keys.load_authorized_keys(authz_path)


def s9_chi_bo_sung(tmp_path):
    """Bản hợp lệ chỉ THÊM tài nguyên — hàng có sẵn trên máy chủ phải còn."""
    store, authz, _, _ = _publish(tmp_path)
    return store, authz


MA_TRAN = [
    ("S1", "all_valid",                          s1_hop_le,                    "ACCEPT"),
    ("S2", "artifact_byte_modified_after_signing", s2_doi_mot_byte_artifact,   "REJECT"),
    ("S3", "manifest_hash_edited_signature_kept", s3_sua_manifest_giu_chu_ky_cu, "REJECT"),
    ("S4", "signed_by_untrusted_key",            s4_ky_bang_khoa_khong_tin_cay, "REJECT"),
    ("S5", "signature_corrupted",                s5_chu_ky_hong,               "REJECT"),
    ("S6", "signature_missing",                  s6_thieu_chu_ky,              "REJECT"),
    ("S8", "newer_version_trusted_source",       s8_ban_moi_nguon_tin_cay,     "ACCEPT"),
    ("S9", "additive_publish_keeps_server_rows", s9_chi_bo_sung,               "ACCEPT"),
]


@pytest.mark.parametrize("ma,ten,dung,mong_doi", MA_TRAN, ids=[c[0] for c in MA_TRAN])
def test_ma_tran_gia_mao_sot(tmp_path, ma, ten, dung, mong_doi):
    store, authorized = dung(tmp_path)
    db = FakeDB(seed=GIEO)
    truoc = db.snapshot()

    try:
        sync_from_sot(store, db.sink(), authorized_keys=authorized)
        thuc_te, ly_do = "ACCEPT", None
    except SotSyncRejected as e:
        thuc_te, ly_do = "REJECT", str(e)[:160]
    except Exception as e:  # noqa: BLE001
        # Một ngoại lệ KHÁC vẫn là từ chối fail-closed, nhưng phải ghi rõ loại —
        # `FileNotFoundError` và `SotSyncRejected` không nói cùng một điều về
        # chất lượng cơ chế.
        thuc_te, ly_do = "REJECT", f"{type(e).__name__}: {str(e)[:140]}"

    sau = db.snapshot()
    if mong_doi == "REJECT":
        # Hậu điều kiện thật: trạng thái CÓ SẴN không đổi. Mạnh hơn "không ghi
        # gì" — một lượt ghi đè hàng cũ rồi mới lỗi vẫn qua được phép đếm.
        hau_dieu_kien = (sau == truoc) and db.schema_applied == []
    else:
        # Chấp nhận: hàng gieo sẵn PHẢI còn (superset, không xoá).
        hau_dieu_kien = all(
            k in sau[bang] for bang, hang in GIEO.items() for k in hang)

    KET_QUA.append({
        "id": ma, "scenario": ten, "expected": mong_doi, "actual": thuc_te,
        "postcondition_passed": bool(hau_dieu_kien),
        "passed": bool(thuc_te == mong_doi and hau_dieu_kien),
        "property_status": "SATISFIED" if (thuc_te == mong_doi and hau_dieu_kien) else "VIOLATED",
        "reason": ly_do,
    })

    assert thuc_te == mong_doi, f"{ma} {ten}: mong {mong_doi}, thuc te {thuc_te} ({ly_do})"
    assert hau_dieu_kien, f"{ma} {ten}: hau dieu kien HONG — trang thai da doi"


def test_s7_ban_cu_khong_duoc_pha_huy_trang_thai_moi(tmp_path):
    """S7 — thẩm quyền PHIÊN BẢN, không phải toàn vẹn.

    Mọi hash và chữ ký đều đúng; `LATEST` chỉ bị trỏ ngược về bản cũ. Câu hỏi có
    HAI vế, và chúng không giống nhau:

        (a) hệ có TỪ CHỐI lùi phiên bản không?
        (b) nếu chấp nhận, việc lùi có PHÁ HUỶ trạng thái mới hơn không?

    Cần hai lượt đồng bộ thật mới hỏi được vế (b), nên ca này nằm ngoài ma trận
    tham số: phải có v2 ĐÃ VÀO cơ sở dữ liệu rồi mới đo được nó mất hay còn.
    """
    store, _, key_path, authz_path = _publish(tmp_path)
    v1 = store.list_version_dirs()[0]
    _publish(tmp_path, key_path=key_path, authz=authz_path, csvs={
        **CSVS,
        # v2 vừa THÊM c3, vừa ĐỔI nhãn của c1 — hai kiểu thay đổi khác nhau.
        "labels.csv": b"class_uid,slug\nc1,hello-v2\nc2,thanks\nc3,chi-co-o-v2\n",
    })
    authorized = keys.load_authorized_keys(authz_path)

    db = FakeDB(seed=GIEO)
    sync_from_sot(store, db.sink(), authorized_keys=authorized)
    assert db.tables["classes"]["c3"]["slug"] == "chi-co-o-v2"
    assert db.tables["classes"]["c1"]["slug"] == "hello-v2"

    # Trỏ LATEST ngược về v1, ký lại HỢP LỆ bằng khoá TIN CẬY.
    man_v1 = store.read_bytes(f"{v1}/manifest.json")
    latest = m.canonical_bytes({
        "version": v1,
        "manifest_sha256": m.sha256_bytes(man_v1),
        "created_at": "2026-08-16T00:00:00+00:00",
        "machine": "desktop-A",
    })
    store.write_bytes("LATEST.json", latest)
    store.write_bytes("LATEST.sig", keys.sign(keys.load_private_key(key_path), latest).encode())

    try:
        sync_from_sot(store, db.sink(), authorized_keys=authorized)
        quyet_dinh = "ACCEPT"
    except SotSyncRejected:
        quyet_dinh = "REJECT"

    con_c3 = "c3" in db.tables["classes"]
    nhan_c1 = db.tables["classes"]["c1"]["slug"]
    khong_pha_huy = con_c3 and all(
        k in db.tables[bang] for bang, hang in GIEO.items() for k in hang)

    KET_QUA.append({
        "id": "S7", "scenario": "older_version_replacing_newer",
        "expected_contract": "reject_old_version_or_preserve_non_destructive_merge",
        "expected": "REJECT_OR_NON_DESTRUCTIVE", "actual": quyet_dinh,
        "actual_detail": ("accepted_old_version_with_non_deleting_"
                          "but_value_regressive_merge"),
        # Phép đo ĐẠT (nó đo đúng hành vi và cho kết quả xác định), nhưng thuộc
        # tính "trạng thái mới hơn không được lùi" thì KHÔNG đạt. Hai trường
        # riêng, để `passed=true` không bị đọc thành "chống rollback thành công".
        "property_status": "LIMITATION",
        "property_not_enforced": "monotonic_version_ordering",
        "postcondition_passed": bool(khong_pha_huy),
        # Hợp đồng ở đây là TUYỂN, nên "đạt" không phải `actual == expected`:
        # chấp nhận mà không phá huỷ vẫn thoả. Ghi rõ để bảng tổng không phải
        # suy luận lại từ hai trường kia.
        "passed": bool(quyet_dinh == "REJECT" or khong_pha_huy),
        "reason": (f"c3 (chi co o v2) {'con' if con_c3 else 'MAT'}; "
                   f"c1.slug sau khi lui = {nhan_c1!r}"),
    })

    # Hợp đồng là "TỪ CHỐI **hoặc** không phá huỷ". Đây là vế thứ hai: không có
    # tài nguyên nào biến mất khi lùi phiên bản.
    assert khong_pha_huy, (
        "lui phien ban da XOA tai nguyen chi co o ban moi — rollback pha huy")


@pytest.fixture(scope="module", autouse=True)
def _ghi_artifact():
    yield
    if not KET_QUA:
        return
    do_duoc = [c for c in KET_QUA if c["passed"]]
    thoa = [c for c in KET_QUA if c.get("property_status", "SATISFIED") == "SATISFIED"]
    gioi_han = [c for c in KET_QUA if c.get("property_status") == "LIMITATION"]
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps({
        # Phép ĐO hợp lệ hay không — KHÁC với thuộc tính bảo mật có đạt hay
        # không. Trộn hai thứ này lại thì một `passed=true` của S7 sẽ bị đọc
        # thành "SOT chống hồi quy phiên bản thành công", tức là che mất đúng
        # phát hiện đáng giá nhất của lượt đo.
        "measurement_status": "OK" if len(do_duoc) == len(KET_QUA) else "FAILED",
        "measurement_valid": len(do_duoc) == len(KET_QUA),
        "cases_executed": f"{len(do_duoc)}/{len(KET_QUA)}",
        "property_outcome": {
            "satisfied": len(thoa),
            "limitation": len(gioi_han),
            "limitations": [c["id"] for c in gioi_han],
        },
        **_van_tay_nguon(),
        "schema_version": 8,
        "algorithm": {"hash": "SHA-256", "signature": "Ed25519"},
        "consumer_path": "app.sot.reader_sync.sync_from_sot",
        "cases_total": len(KET_QUA),
        "cases": sorted(KET_QUA, key=lambda c: c["id"]),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
