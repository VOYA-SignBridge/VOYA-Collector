"""Ai đã ký một hàng — MỘT định nghĩa, dùng chung.

Vì sao tách ra thành tệp riêng
------------------------------
Câu hỏi "hai phân vùng này có chung người ký không" được hỏi ở hai nơi khác
nhau, vì hai lý do khác nhau:

  * `dataset_loader._canonical_signer` — lúc NẠP dữ liệu, để nhóm mẫu theo
    người khi chia;
  * `routers/training` — lúc HIỂN THỊ, để nói cho người dùng biết con số họ sắp
    đọc đo trên người ký mới hay người mô hình đã thấy.

Hai nơi trả lời khác nhau thì giao diện nói một đằng và mô hình học một nẻo, và
không có gì đỏ. Nên định nghĩa nằm ở đây, và cả hai gọi vào.

Vì sao `user_id` chứ không phải `signer_id`
-------------------------------------------
Ngược với trực giác, và đây là điểm dễ làm sai nhất.

`signer_id` được SUY RA từ tài khoản thu thập. Khi nhiều người cùng ký dưới một
tài khoản thì họ bị gộp thành một danh tính. Dữ liệu hoa-de có đúng trường hợp
đó: `S010` (tài khoản "tran") chứa cả Nhung lẫn Khoa.

Hệ quả nếu ưu tiên `signer_id`: một split có Nhung ở train và Khoa ở test sẽ
được chấm là "đã tách người ký" — vì cả hai cùng mang `S010`. Phép kiểm báo ĐẠT
đúng vào lúc nó cần báo TRƯỢT, và con số độ chính xác thu được lạc quan hơn
thực tế mà không có gì chỉ ra điều đó.

`user_id` ghi tên người ký thật. Biến thể chính tả ("Trân" / "Tran" / "trân")
được gộp bằng bảng ở `config/legacy_signer_mapping.json`, do chủ dữ liệu xác
nhận — xem `scripts/apply_signer_merges.py`.

`signer_id` vẫn là đường lui khi `user_id` rỗng: thà một danh tính thô còn hơn
không có danh tính nào.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Mapping, Optional

#: Bảng gộp biến thể chính tả -> mã người ký. Xem docstring đầu tệp.
LEGACY_SIGNER_MAP_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "legacy_signer_mapping.json"
)


@lru_cache(maxsize=1)
def load_legacy_signer_map() -> Dict[str, str]:
    """Bảng gộp, hoặc rỗng nếu không đọc được.

    Rỗng là đường lui CÓ Ý: thiếu bảng thì tên thô được giữ nguyên, đúng hành vi
    trước khi bảng ra đời. Nó làm cho hai biến thể chính tả của cùng một người
    bị đếm thành hai — bảo thủ theo chiều đúng, vì nó chỉ có thể báo một split
    là KHÔNG tách người khi nó thật ra có tách, chứ không bao giờ ngược lại.
    """
    try:
        raw = json.loads(LEGACY_SIGNER_MAP_PATH.read_text(encoding="utf-8"))
        return dict(raw.get("legacy_name_to_signer_id") or {})
    except Exception:
        return {}


def canonical_signer(row: Mapping[str, object],
                     legacy_map: Optional[Mapping[str, str]] = None) -> str:
    """Danh tính người ký của một hàng CSV, hoặc chuỗi rỗng khi không xác định.

    `legacy_map` truyền vào được để người gọi trong vòng lặp nóng nạp một lần;
    bỏ trống thì dùng bảng đã nhớ sẵn.
    """
    mapping = load_legacy_signer_map() if legacy_map is None else legacy_map
    raw = str(row.get("user_id") or "").strip()
    if raw:
        return mapping.get(raw, raw)
    return str(row.get("signer_id") or "").strip()


def identity_column(fieldnames) -> Optional[str]:
    """Cột nào trong CSV mang danh tính người ký, theo đúng thứ tự ưu tiên trên.

    Trả `None` khi không có cột nào — và đó là một câu trả lời có nghĩa, không
    phải một lỗi: nó nói rằng split này KHÔNG kiểm được việc tách người ký, và
    người đọc phải được nói điều đó thay vì nhận một con số im lặng.
    """
    cols = set(fieldnames or ())
    if "user_id" in cols:
        return "user_id"
    if "signer_id" in cols:
        return "signer_id"
    return None
