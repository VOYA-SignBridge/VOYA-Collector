"""Danh tính lớp cho một lượt huấn luyện: `class_uid` → `target_idx`.

Nguyên tắc, viết ra vì nó đã bị vi phạm ở ba chỗ khác nhau:

    KHÔNG một chuỗi hiển thị hay tổ hợp metadata nào được làm ĐỊNH DANH của
    lớp trong huấn luyện, khi cơ sở dữ liệu đã có `class_uid` bền vững.

`slug`, `dialect`, `region`, `label_key` đều đổi được và va chạm được theo
nghiệp vụ. `class_uid` mới là neo đúng.

Ba đường đã dựng danh tính sai, tìm ra 14/08/2026:

  1. `train_tcn._build_subset_label_maps` — `enumerate(unique_keys)` với
     `unique_keys` gom theo THỨ TỰ HÀNG trong CSV. Lớp 0 của mô hình là "nhãn
     nào nằm ở dòng đầu tiên". Hai lượt chạy cùng tập lớp, khác thứ tự hàng,
     ra hai mô hình có ngữ nghĩa đầu ra khác nhau.
  2. Cùng chỗ đó, khoá là `label_key = vn/<dialect>/<slug>` — KHÔNG có region.
     Cơ sở dữ liệu cho phép `ăn|bac` và `ăn|nam` cùng một dialect (khoá duy
     nhất là `(tenant_id, slug, language, dialect, region)`), nên hai lớp hợp
     lệ đó GỘP thành một, im lặng, và pipeline vẫn chạy ra số.
  3. `dataset_loader` khi thiếu `label_to_index.json` thì dựng ánh xạ từ
     `labels.csv` HIỆN TẠI với chỉ số `class_idx - 1`. Hai cái sai một lúc:
     giải mã đầu ra bằng từ vựng hiện tại thay vì từ vựng lúc huấn luyện, và
     `class_idx` là định danh toàn cục THƯA nên `class_idx - 1` cho một không
     gian chỉ số có lỗ trong khi `num_classes` đếm số phần tử.

Kiểu (2) nguy nhất vì nó không hỏng gì cả — không lỗi, không cảnh báo, chỉ là
hai vùng bị coi là một và độ chính xác vẫn ra một con số trông hợp lý.

Hai đường, cố ý KHÔNG hợp nhất
------------------------------
`consume_declared()`   Split VẬN HÀNH. Bắt buộc có `class_uid`, `target_idx`,
                       `class_mapping_hash`. Thiếu một trong ba thì TỪ CHỐI,
                       không rơi về cách cũ.
`legacy_row_order()`   Split NGHIÊN CỨU đã đóng băng, dựng trước khi hợp đồng
                       này tồn tại. Giữ nguyên hành vi cũ.

Không có nhánh "ưu tiên class_uid, thiếu thì dùng label_key". Một fallback như
vậy giữ nguyên đường lỗi cũ và vài tháng sau sẽ lặng lẽ chạy trên dữ liệu
QIPEDC — nơi hàng trăm từ có biến thể vùng dùng chung slug.

    tương thích ngược  ≠  đúng đắn khi vận hành
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

SPLIT_METADATA_NAME = "split_metadata.json"


class MappingError(Exception):
    """Ánh xạ lớp không dùng được. Luôn là lý do để DỪNG, không phải để đoán."""


def canonical_mapping_hash(mapping: Mapping[str, int]) -> str:
    """Băm ĐÚNG danh tính: `class_uid` → `target_idx`.

    Chuẩn hoá: sắp theo `class_uid`, mỗi dòng `uid<TAB>idx`, nối bằng xuống
    dòng. Nhờ vậy thứ tự trả về của CSDL không ảnh hưởng kết quả.

    Cố ý KHÔNG băm `label_key → target_idx` cũng KHÔNG băm
    `class_idx → target_idx`. Đổi nhãn hiển thị của một vùng (`bac` thành
    `Bắc Bộ`) không được làm đổi mã băm này; đổi vị trí đầu ra thì phải.
    """
    canon = "\n".join(f"{str(k).strip()}\t{int(v)}"
                      for k, v in sorted(mapping.items(), key=lambda kv: str(kv[0])))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def validate_mapping(mapping: Mapping[str, int]) -> None:
    """Ba kiểm ĐỘC LẬP. Song ánh, không chỉ liên tục.

    Liên tục thôi là chưa đủ: `{A:0, B:0, C:1}` có tập chỉ số {0,1} và không
    thủng lỗ theo nghĩa hẹp, nhưng hai lớp dùng chung một chiều đầu ra — đúng
    hình dạng của lỗi gộp vùng mà module này sinh ra để chặn.
    """
    if not mapping:
        raise MappingError("ánh xạ rỗng — không có lớp nào để học")

    for uid, idx in mapping.items():
        if not str(uid).strip():
            raise MappingError("có class_uid rỗng trong ánh xạ")
        if not isinstance(idx, int) or isinstance(idx, bool):
            raise MappingError(f"target_idx của {uid!r} không phải số nguyên: {idx!r}")

    # 1. mỗi class_uid đúng một target_idx — dict đã bảo đảm.
    # 2. mỗi target_idx đúng một class_uid.
    nguoc: Dict[int, list] = {}
    for uid, idx in mapping.items():
        nguoc.setdefault(int(idx), []).append(str(uid))
    dung_chung = {i: sorted(u) for i, u in nguoc.items() if len(u) > 1}
    if dung_chung:
        raise MappingError(
            f"nhiều class_uid dùng chung một target_idx: {dung_chung}. "
            f"Đây là hình dạng của lỗi gộp lớp — hai lớp hợp lệ ở CSDL bị coi "
            f"là một ở tầng mô hình.")

    # 3. đúng 0..K-1.
    chi_so = sorted(int(v) for v in mapping.values())
    if chi_so != list(range(len(mapping))):
        thieu = sorted(set(range(len(mapping))) - set(chi_so))
        raise MappingError(
            f"target_idx phải là 0..{len(mapping) - 1} liên tục, nhận {chi_so}"
            + (f"; thiếu {thieu}" if thieu else ""))


def read_declared(split_dir: Path) -> Optional[Dict[str, object]]:
    """Đọc `split_metadata.json` cạnh split. `None` khi không có."""
    p = Path(split_dir) / SPLIT_METADATA_NAME
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise MappingError(f"{p} không đọc được: {exc}") from exc


def consume_declared(meta: Mapping[str, object]) -> Dict[str, int]:
    """Ánh xạ cho split VẬN HÀNH. Thiếu thứ gì thì từ chối, không đoán.

    Trả về `{class_uid: target_idx}` đã kiểm đủ ba điều kiện và đã đối chiếu
    với `class_mapping_hash` mà chính hiện vật khai.
    """
    lop = meta.get("classes")
    if not isinstance(lop, list) or not lop:
        raise MappingError(
            "split khai purpose vận hành nhưng không có mục `classes` — "
            "không dựng lại được ý nghĩa của tầng đầu ra. Chia lại bằng "
            "make_splits.py bản hiện tại.")

    anh_xa: Dict[str, int] = {}
    for i, muc in enumerate(lop):
        if not isinstance(muc, dict):
            raise MappingError(f"classes[{i}] không phải object: {muc!r}")
        uid = str(muc.get("class_uid") or "").strip()
        if not uid:
            raise MappingError(
                f"classes[{i}] thiếu `class_uid`. Danh tính lớp phải là "
                f"class_uid — slug/dialect/region đều đổi và va chạm được.")
        if "target_idx" not in muc:
            raise MappingError(f"classes[{i}] ({uid}) thiếu `target_idx`")
        if uid in anh_xa:
            raise MappingError(f"class_uid trùng trong khai báo: {uid}")
        try:
            anh_xa[uid] = int(muc["target_idx"])
        except Exception as exc:
            raise MappingError(
                f"target_idx của {uid} không phải số nguyên: "
                f"{muc['target_idx']!r}") from exc

    validate_mapping(anh_xa)

    khai = str(meta.get("class_mapping_hash") or "").strip()
    if not khai:
        raise MappingError(
            "split vận hành thiếu `class_mapping_hash`. Không có nó thì "
            "checkpoint không chứng minh được nó đã học ánh xạ nào.")
    that = canonical_mapping_hash(anh_xa)
    if khai != that:
        raise MappingError(
            f"`class_mapping_hash` không khớp với chính mục `classes` trong "
            f"cùng tệp: khai={khai} thật={that}. Hiện vật đã bị sửa sau khi "
            f"ghi, hoặc được ghi bởi một bản mã không nhất quán.")
    return anh_xa


def partitions_agree(
    rows_by_partition: Mapping[str, Sequence[Mapping[str, str]]],
    mapping: Mapping[str, int],
    *,
    uid_field: str = "class_uid",
) -> None:
    """Ba phần train/val/test phải nói CÙNG một chuyện về từng lớp.

    Hai điều được kiểm, và điều thứ hai là thứ mà soi từng tệp riêng lẻ sẽ
    KHÔNG thấy: mỗi tệp một mình có thể hợp lệ trong khi `UID_A → 0` ở train
    lại là `UID_A → 2` ở val.

    Ở đây `target_idx` nằm ngay trong hàng, nên chuyện đó phát hiện được.
    """
    la = {}
    lech = {}
    for ten, rows in rows_by_partition.items():
        for r in rows:
            uid = str(r.get(uid_field) or "").strip()
            if not uid:
                continue
            if uid not in mapping:
                la.setdefault(ten, set()).add(uid)
                continue
            raw = str(r.get("target_idx") or "").strip()
            if raw and int(raw) != int(mapping[uid]):
                lech.setdefault(uid, {})[ten] = int(raw)

    if la:
        chi_tiet = "; ".join(
            f"{ten}: {sorted(u)[:5]}" + (f" (+{len(u) - 5})" if len(u) > 5 else "")
            for ten, u in sorted(la.items()))
        raise MappingError(
            f"có class_uid trong tệp split KHÔNG nằm trong bản khai: {chi_tiet}. "
            f"Không lọc chúng đi — một lượt chạy trên tập khác với tập đã khai "
            f"là một lượt chạy nói sai về nguồn gốc của nó.")
    if lech:
        raise MappingError(
            f"cùng một class_uid mang target_idx khác nhau giữa các phần: "
            f"{ {k: v for k, v in list(lech.items())[:5]} }")


#: Khoá của khối ánh xạ trong checkpoint. Tách khỏi `idx_to_label`/`label_to_idx`
#: đã có: hai khoá đó phục vụ HIỂN THỊ và có thể được làm tươi bằng từ vựng mới;
#: khối này là NGỮ NGHĨA và không được phép đổi sau khi huấn luyện xong.
CHECKPOINT_MAPPING_KEY = "label_mapping"


def build_checkpoint_mapping(mapping: Mapping[str, int],
                             declared_classes: Sequence[Mapping[str, object]] = ()
                             ) -> Dict[str, object]:
    """Khối ánh xạ để nhúng vào checkpoint.

    `declared_classes` là mục `classes` của split — dùng để chép kèm metadata
    đọc được (`class_idx`, `slug`, `dialect`, `region`). Chúng chỉ để người và
    giao diện đọc; KHÔNG cái nào tham gia quyết định chỉ số đầu ra.
    """
    theo_uid = {str(m.get("class_uid") or "").strip(): m for m in declared_classes}
    return {
        "class_mapping_hash": canonical_mapping_hash(mapping),
        "classes": [
            {
                "class_uid": uid,
                "target_idx": int(idx),
                **{k: theo_uid.get(uid, {}).get(k)
                   for k in ("class_idx", "slug", "dialect", "region")
                   if theo_uid.get(uid, {}).get(k) is not None},
            }
            for uid, idx in sorted(mapping.items(), key=lambda kv: kv[0])
        ],
    }


def consume_checkpoint_mapping(ckpt: Mapping[str, object]) -> Dict[int, str]:
    """`target_idx → class_uid` lấy từ CHÍNH checkpoint. Không nhìn đi đâu khác.

    Đây là mắt xích cuối của chuỗi: split khai ánh xạ → trainer học theo nó →
    checkpoint đóng băng nó → suy luận giải mã bằng nó. Đọc `labels.csv` hiện
    tại ở bước này là hỏng cả chuỗi, vì từ vựng đổi được sau khi huấn luyện
    xong và không có gì báo.

    Kiểm lại mã băm chứ không tin: một checkpoint bị sửa `target_idx` mà giữ
    hash cũ phải TỪ CHỐI nạp, chứ không im lặng đoán sai mọi nhãn.
    """
    khoi = ckpt.get(CHECKPOINT_MAPPING_KEY)
    if not isinstance(khoi, dict):
        raise MappingError(
            f"checkpoint không có khối {CHECKPOINT_MAPPING_KEY!r}. Nó được "
            f"huấn luyện trước khi hợp đồng này tồn tại, hoặc bởi đường "
            f"nghiên cứu/legacy — hai trường hợp đó dùng đường tương thích "
            f"riêng, không dùng hàm này.")

    lop = khoi.get("classes")
    if not isinstance(lop, list) or not lop:
        raise MappingError(f"{CHECKPOINT_MAPPING_KEY}.classes rỗng hoặc sai kiểu")

    anh_xa: Dict[str, int] = {}
    for i, muc in enumerate(lop):
        if not isinstance(muc, dict):
            raise MappingError(f"classes[{i}] không phải object")
        uid = str(muc.get("class_uid") or "").strip()
        if not uid:
            raise MappingError(f"classes[{i}] thiếu class_uid")
        if uid in anh_xa:
            raise MappingError(f"class_uid trùng trong checkpoint: {uid}")
        if "target_idx" not in muc:
            raise MappingError(f"classes[{i}] ({uid}) thiếu target_idx")
        anh_xa[uid] = int(muc["target_idx"])

    validate_mapping(anh_xa)

    khai = str(khoi.get("class_mapping_hash") or "").strip()
    if not khai:
        raise MappingError("checkpoint thiếu class_mapping_hash")
    that = canonical_mapping_hash(anh_xa)
    if khai != that:
        raise MappingError(
            f"class_mapping_hash của checkpoint không khớp chính mục classes "
            f"của nó: khai={khai} thật={that}. Checkpoint đã bị sửa sau khi "
            f"tạo — TỪ CHỐI nạp, vì nạp nghĩa là giải mã sai mọi dự đoán mà "
            f"không có dấu hiệu nào.")
    return {v: k for k, v in anh_xa.items()}


def legacy_row_order(
    rows: Iterable[Mapping[str, str]], *, key_field: str = "label_key",
) -> Tuple[Dict[str, int], Dict[int, str]]:
    """Đường TƯƠNG THÍCH cho hiện vật nghiên cứu đã đóng băng. Đừng dùng lại.

    Giữ nguyên hành vi cũ — gom khoá theo thứ tự hàng — vì các split nghiên cứu
    đã công bố được dựng bằng đúng nó, và áp luật mới lên chúng sẽ phá tính lặp
    lại của kết quả đã đăng.

    Tách khỏi `consume_declared` một cách CÓ CHỦ Ý, và không có đường nào rơi
    từ bên kia sang đây.
    """
    khoa: list = []
    thay = set()
    for r in rows:
        k = str(r.get(key_field) or "").strip()
        if not k or k in thay:
            continue
        thay.add(k)
        khoa.append(k)
    l2i = {k: i for i, k in enumerate(khoa)}
    return l2i, {i: k for k, i in l2i.items()}
