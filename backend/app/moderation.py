"""Cổng kiểm duyệt: mẫu chưa duyệt chỉ người đóng góp dùng được.

Xem docs/01-architecture/COMMUNITY_MODERATION.md §5.

Quy tắc, phát biểu một lần
---------------------------
Một mẫu **dùng được** với người xem V khi::

    review_status = 'approved'   HOẶC   auth_user_id = V

Khi KHÔNG có người xem — phát hành, công bố, thống kê công khai — thì chỉ
`approved`. "Không có người xem" nghĩa là dữ liệu sắp rời khỏi phạm vi một
người, nên không ai để mà miễn trừ.

Vì sao là một mô-đun riêng chứ không nhét vào `consent_gate`
-------------------------------------------------------------
Hai cổng trả lời hai câu khác nhau và **cùng phải qua**:

    đồng thuận    người ký có cho phép mức phát hành này không
    kiểm duyệt    nội dung này có đạt không

Một mẫu được duyệt vẫn bị đồng thuận chặn, và ngược lại. Gộp chúng vào một cột
hay một hàm sẽ làm mất khả năng trả lời "vì sao dòng này bị loại" — và hai lý
do ấy dẫn tới hai hành động sửa hoàn toàn khác nhau.

Vì sao lọc ở đây chứ không ở giao diện
---------------------------------------
Bộ lọc phải nằm ở chỗ CHỌN dữ liệu — lúc dựng tập huấn luyện, lúc đóng gói bản
phát hành — chứ không phải lúc vẽ màn hình. Cổng đồng thuận đứng đúng những chỗ
đó vì lý do này; kiểm duyệt đứng cùng chỗ, hoặc nó chỉ là trang trí.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

#: Ba trạng thái, khớp ràng buộc `ck_samples_review_status`.
PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"

#: Lý do một dòng bị giữ lại. Khoá ổn định để đếm và để dịch.
REASON_PENDING = "cho_duyet"
REASON_REJECTED = "bi_tu_choi"

REASON_TEXT: Dict[str, str] = {
    REASON_PENDING: "đang chờ duyệt",
    REASON_REJECTED: "đã bị từ chối",
}


@dataclass
class ModerationResult:
    """Phần đi tiếp, phần bị giữ lại, và vì sao."""

    kept: List[Dict[str, Any]] = field(default_factory=list)
    withheld: List[Dict[str, Any]] = field(default_factory=list)
    reasons: Dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.kept) + len(self.withheld)

    def summary(self) -> str:
        if not self.withheld:
            return f"{len(self.kept)}/{self.total} mẫu đã qua kiểm duyệt"
        parts = ", ".join(
            f"{n} {REASON_TEXT.get(r, r)}"
            for r, n in sorted(self.reasons.items(), key=lambda kv: -kv[1])
        )
        return (f"{len(self.kept)}/{self.total} mẫu đã qua kiểm duyệt; "
                f"giữ lại {len(self.withheld)} ({parts})")


def status_of(row: Dict[str, Any]) -> str:
    """Trạng thái duyệt của một dòng, chuẩn hoá.

    Ô RỖNG và khoá VẮNG MẶT đều đọc thành `pending`, và đó là quyết định quan
    trọng nhất trong tệp này.

    Một dòng đến từ tệp CSV ghi trước lượt migration không nói gì về việc nó đã
    được duyệt hay chưa. Đọc sự im lặng đó thành "đã duyệt" sẽ mở đúng cái cửa
    mà cổng này sinh ra để đóng: chép một tệp cũ vào là phát hành được mọi thứ
    trong đó. Sự im lặng phải đọc thành "chưa biết", và "chưa biết" thì chưa
    được dùng chung.

    Hướng hỏng này nhìn thấy được: hàng đợi dài bất thường thì có người đi hỏi.
    Hướng ngược lại không ai thấy gì cả.
    """
    return (str(row.get("review_status") or "").strip().lower() or PENDING)


def filter_rows(
    rows: Iterable[Dict[str, Any]],
    *,
    viewer_id: Optional[str] = None,
) -> ModerationResult:
    """Chia các dòng thành phần dùng được và phần bị giữ lại.

    `viewer_id` là tài khoản đang yêu cầu dữ liệu (`samples.auth_user_id`).
    `None` nghĩa là KHÔNG có người xem — chỉ `approved` đi tiếp.

    Không đụng cơ sở dữ liệu: trạng thái nằm sẵn trên từng dòng, ở cả CSV lẫn
    Postgres. Nhờ vậy hàm này test được mà không cần CSDL, và gọi được từ trong
    tiến trình huấn luyện vốn đọc thẳng từ tệp.
    """
    me = (str(viewer_id).strip() if viewer_id else "")
    out = ModerationResult()

    for row in rows:
        trang_thai = status_of(row)
        if trang_thai == APPROVED:
            out.kept.append(row)
            continue

        # Chủ sở hữu dùng được dữ liệu của chính mình ngay, kể cả khi chưa duyệt
        # — đó là nửa còn lại của hợp đồng: thu xong là dùng được, chỉ chưa
        # được dùng CHUNG. So sánh chuỗi vì `auth_user_id` tới từ ba nguồn (ô
        # CSV, UUID của psycopg2, chuỗi trong JSON) với ba kiểu khác nhau.
        chu = str(row.get("auth_user_id") or "").strip()
        if me and chu and chu == me:
            out.kept.append(row)
            continue

        out.withheld.append(row)
        ly_do = REASON_REJECTED if trang_thai == REJECTED else REASON_PENDING
        out.reasons[ly_do] = out.reasons.get(ly_do, 0) + 1

    return out


#: Mệnh đề SQL cho các đường ĐỌC theo truy vấn, thay vì lọc trong Python.
#:
#: Dùng khi tập dòng lớn hoặc khi câu hỏi là một phép đếm — kéo 3.862 dòng về
#: chỉ để đếm rồi vứt đi là lãng phí, và một phép đếm sai kiểu đó chính là thứ
#: `/classes/community-stats` từng làm.
#:
#: `%(viewer)s` nhận `None` cho "không có người xem". `IS NOT DISTINCT FROM`
#: KHÔNG dùng ở đây: với `viewer = NULL` nó sẽ cho qua mọi dòng có
#: `auth_user_id` NULL — tức 997 mẫu cũ vô chủ — và đó đúng là rò rỉ mà mệnh đề
#: này phải chặn.
SQL_VISIBLE = (
    "(samples.review_status = 'approved' "
    " OR (%(viewer)s IS NOT NULL AND samples.auth_user_id = %(viewer)s::uuid))"
)
