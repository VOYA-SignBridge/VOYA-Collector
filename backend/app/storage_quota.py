"""Dung lượng: hạn mức dữ liệu DUY NHẤT từ v8.

Vì sao có module này
====================
`plans.py` cố ý đếm mọi chỉ số bằng `count(*)` trên bảng nguồn, để không bản sao
nào lệch được. Dung lượng không theo được nguyên tắc đó: đi bộ cả cây thư mục
mất hàng giây — không chạy nổi ở mỗi lượt ghi.

Nên dung lượng là **ngoại lệ có kiểm chứng**, đúng như `plans.py` dự liệu trong
docstring của nó ("chỗ sửa là thêm một bộ đếm có đối chiếu định kỳ"). Ba lớp,
thiếu lớp nào cũng hỏng theo một kiểu riêng:

    bộ đếm bền          `tenant_storage.bytes_used` — byte ĐÃ nằm trên đĩa
    chặn đồng bộ        kiểm TRƯỚC khi nhận tệp, không đợi lượt tổng hợp hôm sau
    đối chiếu hằng ngày đi bộ thật, ghi đè bộ đếm nếu lệch, kèm log WARNING

Byte nào được tính thì `docs/07-business/BILLABLE_STORAGE_INVENTORY.md` chốt, và
`_billable_bytes()` dưới đây là hiện thực của đúng bảng ấy. Hai chỗ đó phải nói
cùng một điều; nếu lệch thì bảng là bên đúng.

Giữ chỗ là một SỔ, không phải một bộ đếm thứ hai
================================================
Kích thước thật chỉ biết sau khi ghi xong, còn phép chặn phải xảy ra trước. Nên
mỗi lượt ghi đang bay giữ một chỗ, và phép nhận việc hỏi:

    đã dùng + đang giữ chỗ + sắp tới  <=  trần

Phần "đang giữ chỗ" có thể làm bằng một cột `reserved_bytes`, và cách ấy sai ở
đúng một chỗ: một tiến trình CHẾT giữa `reserve` và `settle`. Với một cột đếm,
khoản treo lẫn vào tổng và không phân biệt được với một lượt tải đang chạy thật
— muốn thu hồi thì phải đoán. Với một sổ, khoản treo có `reservation_id` và
`expires_at`, nên thu hồi là một câu `WHERE`.

Hệ quả thứ hai còn quan trọng hơn: phần "đang giữ chỗ" là một tổng **được dẫn
xuất**, nên nó không trôi được. Chỉ còn ĐÚNG MỘT con số có thể lệch khỏi đĩa, và
`reconcile()` biết chính xác phải sửa cái nào.

Vòng đời một lượt ghi
=====================
    reserve(ước lượng)  ->  ghi tệp  ->  đo thật  ->  settle(thật)  ->  metadata
                        ->  hỏng                  ->  release()

Ba trường hợp quyết toán, và trường hợp thứ ba là lý do hàm `settle` phức tạp
hơn một phép cộng:

    thật == giữ chỗ     không đổi
    thật <  giữ chỗ     phần thừa trả lại
    thật >  giữ chỗ     ước lượng SAI VỀ PHÍA THẤP

Ở trường hợp ba, cộng thẳng số thật vào bộ đếm là chấp nhận rằng hạn mức đã bị
vượt SAU KHI tệp tồn tại — tức là hạn mức chỉ còn là một phép kiểm trước lượt
tải, không phải một trần. Nên `settle` kiểm lại trên byte THẬT, và nếu không đủ
chỗ thì `discard()` gỡ tệp vừa ghi, khoản giữ chỗ được trả, và lượt ghi hỏng
trước khi có bất kỳ dòng metadata nào trỏ tới nó.

Phép kiểm lúc quyết toán hỏi `đã dùng + thật <= trần`, CỐ Ý không cộng các khoản
giữ chỗ khác. Byte của lượt này đã có thật; byte của người khác thì chưa. Cộng
vào sẽ khiến một lượt ghi vừa vặn bị từ chối chỉ vì có người đang tải cùng lúc —
một lỗi phụ thuộc lưu lượng, không tái hiện được, và người dùng không hiểu nổi.
Bất biến cần giữ là trên byte thật: `bytes_used <= trần`.

Vượt trần là một trạng thái nghiệp vụ hợp lệ
============================================
`bytes_used > trần` KHÔNG phải hỏng dữ liệu. Nó xảy ra hoàn toàn hợp lệ khi một
tổ chức hạ gói. Lượt đối chiếu ghi nhận và báo, nhưng không xoá gì và không đổi
gói; cưỡng chế chỉ chặn lượt ghi TIẾP THEO. Dữ liệu đã có là của họ.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Callable, Iterator, Optional

logger = logging.getLogger(__name__)

#: Bảng bộ đếm. `bytes_used` là BIGINT: `INTEGER` tràn ở 2 GB, tức là ở đúng
#: hạn mức của gói Free.
TABLE = "tenant_storage"

#: Sổ giữ chỗ.
LEDGER = "storage_reservations"

#: Khoản giữ chỗ sống bao lâu trước khi lượt quét coi là treo.
#:
#: Cửa sổ thật của một lượt ghi tính bằng giây: Starlette đã nhận xong thân yêu
#: cầu trước khi hàm xử lý chạy, nên khoản giữ chỗ chỉ phải sống qua một lượt
#: ghi đĩa. Ba mươi phút là hai bậc độ lớn dư — đủ rộng để không lượt nào hợp lệ
#: bị hết hạn giữa chừng, đủ hẹp để một tiến trình chết không giam chỗ của tổ
#: chức tới tận hôm sau.
RESERVATION_TTL_SECONDS = 1800


class StorageScopeMissing(RuntimeError):
    """Bộ đếm không đọc được — gần như luôn là thiếu phạm vi tenant.

    Tách khỏi `StorageQuotaExceeded` vì hai thứ này đòi hai cách xử lý khác
    hẳn: một cái là người dùng cần nâng gói, cái kia là lập trình viên gọi sai
    chỗ. Gộp chúng thành một 402 sẽ khiến một lỗi phạm vi hiện ra với người
    dùng dưới dạng "hết dung lượng", và không ai đi tìm đúng chỗ nữa.
    """


class StorageQuotaExceeded(Exception):
    """Vượt hạn mức dung lượng. Mang mã máy đọc được, không chỉ một câu tiếng Việt."""

    code = "storage_full"
    status_code = 402

    def __init__(self, tenant_id: str, used: int, limit: int, incoming: int):
        self.tenant_id = tenant_id
        self.used = used
        self.limit = limit
        self.incoming = incoming
        super().__init__(
            f"Tổ chức đã dùng {used / 1048576:.0f} MB trong hạn mức "
            f"{limit / 1048576:.0f} MB; tệp này cần thêm "
            f"{incoming / 1048576:.1f} MB."
        )


@dataclass(frozen=True)
class Reservation:
    """Một khoản giữ chỗ đang mở. Trả về từ `reserve`, tiêu ở `settle`/`release`."""

    reservation_id: str
    tenant_id: str
    bytes: int


def _limit_bytes(tenant_id: str) -> Optional[int]:
    """Trần dung lượng của tenant, theo BYTE. `None` = không giới hạn.

    Miễn trừ billing thì không có trần — cùng đường thoát sớm với `plans`. Chú ý
    rằng `reconcile()` KHÔNG hỏi hàm này: miễn trừ nghĩa là "không dùng trần để
    chặn", không phải "không đo". Một tenant nền tảng không quan sát được là một
    tenant không ai biết đang chiếm bao nhiêu đĩa.
    """
    from app.plans import is_billing_exempt, plan_for_tenant

    if is_billing_exempt(tenant_id):
        return None
    mb = (plan_for_tenant(tenant_id) or {}).get("max_storage_mb")
    return None if mb is None else int(mb) * 1024 * 1024


def _ensure_row(cur, tenant_id: str) -> None:
    cur.execute(
        f"INSERT INTO {TABLE}(tenant_id) VALUES(%s) ON CONFLICT DO NOTHING",
        (tenant_id,),
    )


def _khoa_va_doc(cur, tenant_id: str) -> int:
    """Khoá hàng bộ đếm của tenant và trả về `bytes_used`.

    `FOR UPDATE` là ĐIỂM TUẦN TỰ HOÁ của cả module. Mọi lượt giữ chỗ và mọi lượt
    quyết toán của cùng một tenant phải đi qua đây trước, nên phép đọc-kiểm-ghi
    không thể xen kẽ với nhau. Không có nó thì hai lượt cùng đọc "còn chỗ", cùng
    kết luận "được", và cùng ghi — trần bị vượt gấp đôi và không bài test tuần
    tự nào thấy được.

    Hỏng vì phạm vi thì ném `StorageScopeMissing`, KHÔNG phải
    `StorageQuotaExceeded`. Hai đường dẫn tới đó, và cả hai đều phải đổi tên:

    `InsufficientPrivilege`
        Câu `INSERT` chạm `WITH CHECK` của chính sách RLS — lượt gọi đang ở
        ngoài phạm vi tenant, hoặc ở trong phạm vi của một tenant KHÁC. Đây là
        đường thật, đo được. Để nguyên thì nó là một 500 khó hiểu ở giữa một
        hàm nói về hạn mức.

    `SELECT` không ra hàng nào
        Không xảy ra với chính sách hiện tại (`WITH CHECK` chặn trước). Giữ lại
        vì nó là hình dạng mà một chính sách fail-OPEN sẽ tạo ra, và ở mặt phẳng
        danh tính chuyện đó đã xảy ra ba lần. Rẻ, và nếu chính sách đổi thì đây
        là chỗ bắt được.
    """
    import psycopg2

    try:
        _ensure_row(cur, tenant_id)
    except psycopg2.errors.InsufficientPrivilege as exc:
        raise StorageScopeMissing(
            f"khong ghi duoc bo dem dung luong cua {tenant_id!r}: chinh sach RLS tu "
            f"choi. Luot goi nay dang chay ngoai pham vi tenant, hoac trong pham vi "
            f"cua mot tenant khac — day KHONG phai het dung luong."
        ) from exc
    cur.execute(
        f"SELECT bytes_used FROM {TABLE} WHERE tenant_id = %s FOR UPDATE",
        (tenant_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise StorageScopeMissing(
            f"khong doc duoc bo dem dung luong cua {tenant_id!r} — nhieu kha nang "
            f"luot goi nay chay ngoai pham vi tenant"
        )
    return int(row[0])


def _dang_giu(cur, tenant_id: str) -> int:
    """Tổng các khoản giữ chỗ CÒN HẠN. Khoản quá hạn không tính, kể cả khi lượt
    quét chưa kịp dọn — nếu không thì một tiến trình chết sẽ giam chỗ cho tới
    lần quét sau."""
    cur.execute(
        f"SELECT COALESCE(SUM(bytes), 0) FROM {LEDGER} "
        f" WHERE tenant_id = %s AND expires_at > NOW()",
        (tenant_id,),
    )
    return int(cur.fetchone()[0])


def bytes_used(tenant_id: str) -> int:
    """Byte ĐÃ nằm trên đĩa theo bộ đếm. 0 khi chưa có dòng."""
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        f"SELECT bytes_used FROM {TABLE} WHERE tenant_id = %s", (tenant_id,)
    )
    return int(rows[0]["bytes_used"]) if rows else 0


def bytes_reserved(tenant_id: str) -> int:
    """Byte đang được giữ chỗ cho các lượt ghi chưa xong."""
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        f"SELECT COALESCE(SUM(bytes), 0) AS b FROM {LEDGER} "
        f" WHERE tenant_id = %s AND expires_at > NOW()",
        (tenant_id,),
    )
    return int(rows[0]["b"]) if rows else 0


def reserve(tenant_id: str, nbytes: int) -> Reservation:
    """Giữ chỗ `nbytes` cho tenant, hoặc ném `StorageQuotaExceeded`.

    `nbytes = 0` là hợp lệ và có nghĩa: "tôi chưa biết sẽ ghi bao nhiêu, hãy cho
    tôi một khoản để quyết toán vào". Nó vẫn phải qua phép nhận việc, nên một tổ
    chức đã chạm trần bị chặn ngay chứ không chặn ở lượt quyết toán.
    """
    from app.storage.metadata_db import _cursor

    n = int(nbytes)
    if n < 0:
        raise ValueError("khong giu cho mot so am")

    tran = _limit_bytes(tenant_id)
    rid = str(uuid.uuid4())
    with _cursor() as cur:
        dung = _khoa_va_doc(cur, tenant_id)
        giu = _dang_giu(cur, tenant_id)
        if tran is not None and dung + giu + n > tran:
            raise StorageQuotaExceeded(tenant_id, dung + giu, tran, n)
        cur.execute(
            f"INSERT INTO {LEDGER}(reservation_id, tenant_id, bytes, expires_at) "
            f"VALUES(%s, %s, %s, NOW() + make_interval(secs => %s))",
            (rid, tenant_id, n, RESERVATION_TTL_SECONDS),
        )
    return Reservation(reservation_id=rid, tenant_id=tenant_id, bytes=n)


def release(res: Reservation) -> None:
    """Bỏ một khoản giữ chỗ mà không tính gì vào bộ đếm.

    Dùng khi lượt ghi hỏng TRƯỚC khi có byte nào chạm đĩa. Gọi lại lần nữa là vô
    hại: dòng đã bị xoá thì `DELETE` khớp 0 hàng.
    """
    from app.storage.metadata_db import _execute

    _execute(
        f"DELETE FROM {LEDGER} WHERE reservation_id = %s",
        (res.reservation_id,),
    )


def uncharge(tenant_id: str, nbytes: int) -> None:
    """Trừ byte đã THẬT SỰ rời khỏi đĩa.

    Gọi sau khi tệp đã bị gỡ, không phải sau khi hàng bị đánh dấu xoá. Xoá MỀM
    không gỡ tệp — tệp đi khi Thùng rác được dọn — nên trừ ở lượt xoá mềm sẽ tặng
    không dung lượng cho dữ liệu vẫn đang chiếm đĩa.

    `GREATEST(..., 0)` vì một khoản trừ hai lần không được đẩy bộ đếm âm: số âm
    làm mọi phép kiểm sau đó đi qua, tức là hỏng theo hướng MỞ.

    Sai sót ở đây tự lành sau lượt đối chiếu kế tiếp, nên nó không phải là lớp
    bảo vệ cuối. Nó tồn tại để người vừa dọn Thùng rác thấy dung lượng giảm ngay,
    thay vì phải chờ tới hôm sau.
    """
    n = int(nbytes)
    if n <= 0:
        return
    from app.storage.metadata_db import _execute

    _execute(
        f"UPDATE {TABLE} SET bytes_used = GREATEST(bytes_used - %s, 0), "
        f"updated_at = NOW() WHERE tenant_id = %s",
        (n, tenant_id),
    )


def settle(
    res: Reservation,
    actual: int,
    *,
    discard: Optional[Callable[[], None]] = None,
    absorb_overflow: bool = False,
) -> None:
    """Chuyển một khoản giữ chỗ thành byte thật trên bộ đếm.

    Phải nêu rõ một trong hai cách xử lý khi `actual` vượt phần còn lại của trần
    — không có mặc định, vì im lặng chọn hộ ở đây chính là chỗ hạn mức thôi
    không còn là hạn mức:

    `discard=<hàm>`
        Gỡ hiện vật vừa ghi rồi ném `StorageQuotaExceeded`. Dùng ở nơi metadata
        CHƯA được ghi, nên lượt ghi hỏng gọn và không để lại dòng nào trỏ tới
        một tệp không còn.

    `absorb_overflow=True`
        Nhận phần vượt vào bộ đếm và ghi WARNING. Chỉ hợp lệ ở nơi khoản giữ chỗ
        là một CẬN TRÊN tính được chứ không phải một ước lượng — ở đó vượt là
        một lỗi lập trình, và câu WARNING là cách duy nhất để biết cận trên đã
        sai. Gỡ hiện vật lúc ấy sẽ tệ hơn: metadata đã tồn tại.

    Khoản giữ chỗ luôn được tiêu, kể cả khi từ chối. Không có đường nào ra khỏi
    hàm này mà còn để lại một dòng trong sổ.
    """
    if (discard is None) == (not absorb_overflow):
        raise TypeError(
            "settle() phai neu ro MOT trong hai: discard=<ham> hoac "
            "absorb_overflow=True"
        )

    from app.storage.metadata_db import _cursor

    that = max(int(actual), 0)
    tran = _limit_bytes(res.tenant_id)

    with _cursor() as cur:
        dung = _khoa_va_doc(cur, res.tenant_id)
        cur.execute(
            f"DELETE FROM {LEDGER} WHERE reservation_id = %s",
            (res.reservation_id,),
        )
        con_so = cur.rowcount or 0

        vuot = tran is not None and dung + that > tran
        if con_so == 0:
            # Khoản giữ chỗ đã được tiêu rồi. Một khoản là token DÙNG MỘT LẦN,
            # nên lượt này không được cộng gì — nếu không, một lượt thử lại (hay
            # một lượt gọi `settle` lặp do đường mã rẽ nhánh) tính đôi cùng một
            # tệp, và tổ chức mất dung lượng họ chưa hề dùng.
            #
            # Có một trường hợp khác cũng cho `rowcount = 0`: khoản đã hết hạn
            # và bị lượt quét dọn trong khi lượt ghi vẫn đang chạy. Ở đó byte là
            # THẬT và lẽ ra phải tính. Hai trường hợp không phân biệt được từ
            # sổ, nên phải chọn — và chọn "không cộng":
            #
            #   cộng nhầm  -> tính đôi, tổ chức mất chỗ họ sở hữu (hại THẬT)
            #   bỏ nhầm    -> thiếu tạm thời, lượt đối chiếu sửa trong ngày
            #
            # Trường hợp thứ hai còn rất hiếm: TTL 30 phút so với một lượt ghi
            # đĩa tính bằng giây. Cảnh báo ở dưới là để biết nếu nó thôi hiếm.
            pass
        elif vuot and not absorb_overflow:
            # Khoản giữ chỗ đã bị xoá ở trên, nên ra khỏi khối này là chỗ đã
            # được trả. Tệp thì `discard()` gỡ SAU KHI giao dịch chốt: nếu gỡ
            # trước rồi giao dịch hỏng, ta mất tệp mà khoản giữ chỗ vẫn treo.
            # Theo thứ tự này, `discard()` hỏng chỉ để lại một tệp KHÔNG được
            # tính — và lượt đối chiếu tìm ra nó.
            pass
        elif that:
            cur.execute(
                f"UPDATE {TABLE} SET bytes_used = bytes_used + %s, updated_at = NOW() "
                f" WHERE tenant_id = %s",
                (that, res.tenant_id),
            )

    if con_so == 0:
        # Đã tiêu rồi (hoặc đã hết hạn và bị dọn). Không cộng gì, và cũng KHÔNG
        # từ chối: từ chối ở đây sẽ gỡ một hiện vật mà lượt `settle` đầu tiên đã
        # tính và chấp nhận hợp lệ. Chỉ kêu, để biết nếu chuyện này thôi hiếm.
        logger.warning(
            "[STORAGE] %s: khoan giu cho %s da khong con luc quyet toan — khong "
            "cong gi. Hoac da quyet toan roi, hoac TTL=%ss ngan hon luot ghi.",
            res.tenant_id, res.reservation_id, RESERVATION_TTL_SECONDS,
        )
        return

    if vuot:
        if absorb_overflow:
            logger.warning(
                "[STORAGE] %s: quyet toan VUOT tran — giu cho %d byte, that %d byte, "
                "da dung %d/%d. Nhan vao bo dem vi khoan giu cho le ra la can tren; "
                "cham tren nay SAI.",
                res.tenant_id, res.bytes, that, dung, tran,
            )
            return
        try:
            discard()  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[STORAGE] %s: khong go duoc hien vat sau khi tu choi quyet toan "
                "(%s). Tep con tren dia va KHONG duoc tinh; luot doi chieu se "
                "tim ra no.", res.tenant_id, exc,
            )
        raise StorageQuotaExceeded(res.tenant_id, dung, int(tran or 0), that)


def sweep_expired() -> int:
    """Dọn các khoản giữ chỗ quá hạn. Trả về số dòng đã xoá.

    Đây là câu trả lời cho "tiến trình chết giữa `reserve` và `settle`". Không
    có nó thì một lần backend bị giết giữa lượt tải sẽ giam chỗ của tổ chức
    vĩnh viễn — và vì `_dang_giu()` đã bỏ qua khoản quá hạn, lượt quét này chỉ
    là dọn rác chứ không phải đường sửa lỗi.
    """
    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    # `_execute` trả `None`, nên mở con trỏ trực tiếp để lấy `rowcount` — số đó
    # là thứ duy nhất nói cho ta biết có tiến trình nào đang chết giữa chừng.
    with system_scope("storage quota: don khoan giu cho qua han"):
        with _cursor() as cur:
            cur.execute(f"DELETE FROM {LEDGER} WHERE expires_at <= NOW()")
            n = cur.rowcount
    n = int(n or 0)
    if n:
        logger.info("[STORAGE] don %d khoan giu cho qua han", n)
    return n


# ---------------------------------------------------------------- đối chiếu

def _billable_paths(tenant_id: str) -> Iterator["object"]:
    """Mọi tệp TÍNH VÀO HẠN MỨC của một tenant.

    Hiện thực của `docs/07-business/BILLABLE_STORAGE_INVENTORY.md`. Ba nguồn, và
    nguồn thứ ba quy chủ theo cách khác hẳn hai nguồn đầu:

        features/…              đường dẫn — `_tenants/<id>/` phân vùng sẵn
        raw/…                   đường dẫn — gương của `features/`
        raw_videos/…            HÀNG `raw_uploads` — thư mục KHÔNG phân vùng

    `raw_videos/<lang>/<dialect>/<class>/` chung cho mọi tenant, nên đi bộ thư
    mục ấy không quy được chủ. Nhưng tên tệp mang `upload_uid` duy nhất, nên hai
    tổ chức thu cùng một lớp không đụng tệp nhau — chỉ chung thư mục. Cơ sở dữ
    liệu biết ai sở hữu dòng nào, nên nó là nguồn quy chủ.

    Hàng đã xoá mềm VẪN tính, và đó là nhất quán chứ không phải sót: xoá mềm
    không gỡ tệp (tệp đi khi Thùng rác được dọn), nên byte vẫn chiếm đĩa. Hai
    nguồn đầu đi bộ đĩa nên chúng cũng tính phần đã xoá mềm; nguồn thứ ba phải
    khớp, nếu không cùng một hành động lại cho hai kết quả khác nhau tuỳ nó là
    video hay mẫu.
    """
    from pathlib import Path

    from app.dataset_manager import iter_tenant_feature_files
    from app.dataset_samples import raw_archive_path
    from app.storage.metadata_db import _fetch_all, resolve_absolute_path

    da_thay: set = set()

    for p in iter_tenant_feature_files(tenant_id):
        da_thay.add(p)
        yield p
        # Kho raw là gương của cây features: `raw_archive_path` thay đúng đoạn
        # `features` phải nhất bằng `raw`, nên `_tenants/<id>/` sống sót qua
        # phép thay và phần raw của tenant nào thuộc về tenant ấy. Suy ra từ
        # đường dẫn chứ không đi bộ `raw/` riêng — đi bộ riêng sẽ gặp lại đúng
        # cái bẫy `iter_tenant_feature_files` sinh ra để tránh (thư mục của
        # tenant gốc là cha của thư mục mọi tenant khác).
        kho = raw_archive_path(p)
        if kho not in da_thay:
            da_thay.add(kho)
            yield kho

    rows = _fetch_all(
        "SELECT COALESCE(NULLIF(TRIM(local_path), ''), storage_key) AS duong "
        "  FROM raw_uploads WHERE tenant_id = %s",
        (tenant_id,),
    )
    for r in rows:
        duong = (r.get("duong") or "").strip()
        if not duong:
            continue
        p = resolve_absolute_path(duong)
        if isinstance(p, Path) and p not in da_thay:
            da_thay.add(p)
            yield p


def _billable_bytes(tenant_id: str) -> int:
    """Tổng byte tính vào hạn mức, đo bằng `stat()` thật."""
    tong = 0
    for p in _billable_paths(tenant_id):
        try:
            tong += p.stat().st_size
        except OSError:
            # Tệp biến mất giữa lúc liệt kê và lúc đo, hoặc một dòng
            # `raw_uploads` trỏ tới tệp đã bị dọn. Bỏ một tệp, không bỏ tenant.
            continue
    return tong


def reconcile(tenant_id: Optional[str] = None) -> dict:
    """Lớp ba: đi bộ thật, ghi đè bộ đếm nếu lệch, và KÊU khi lệch.

    Đây là **kiểm toán**, không phải đường ghi thứ hai. Nó không tạo hay xoá
    hiện vật, không đổi gói, và không coi một tổ chức đang vượt trần là hỏng dữ
    liệu — vượt trần sau khi hạ gói là hợp lệ, và cưỡng chế đã chặn lượt ghi
    tiếp theo rồi.

    Ghi đè chứ không cộng dồn: lượt đi bộ là sự thật, bộ đếm chỉ là bản gần đúng
    cho tốc độ. Nhưng ghi đè IM LẶNG thì bộ đếm trôi mãi mà không ai biết nguyên
    nhân — nên mỗi lần lệch là một dòng WARNING kèm hai con số.
    """
    from app.storage.metadata_db import _execute, _fetch_all
    from app.tenant_context import system_scope

    with system_scope("storage quota: doi chieu bo dem voi dia"):
        if tenant_id:
            rows = [{"tenant_id": tenant_id}]
        else:
            rows = _fetch_all(
                "SELECT tenant_id FROM tenants WHERE deleted_at IS NULL")

        ket: dict = {"da_xet": 0, "lech": 0, "loi": 0, "vuot_tran": 0}
        for r in rows:
            t = r["tenant_id"]
            try:
                that = _billable_bytes(t)
            except Exception as exc:  # noqa: BLE001
                ket["loi"] += 1
                logger.warning("[STORAGE] %s: khong quet duoc (%s)", t, exc)
                continue

            _execute(f"INSERT INTO {TABLE}(tenant_id) VALUES(%s) "
                     f"ON CONFLICT DO NOTHING", (t,))
            truoc = _fetch_all(
                f"SELECT bytes_used FROM {TABLE} WHERE tenant_id = %s", (t,))
            dem = int(truoc[0]["bytes_used"]) if truoc else 0
            ket["da_xet"] += 1
            if dem != that:
                ket["lech"] += 1
                logger.warning(
                    "[STORAGE] %s: bo dem lech — dem=%d byte, dia=%d byte (%+d). "
                    "Ghi de theo dia.", t, dem, that, that - dem)
            _execute(
                f"UPDATE {TABLE} SET bytes_used = %s, reconciled_at = NOW(), "
                f"updated_at = NOW() WHERE tenant_id = %s", (that, t))

            tran = _limit_bytes(t)
            if tran is not None and that > tran:
                # Trạng thái nghiệp vụ, không phải sự cố. Ghi ở mức INFO chứ
                # không WARNING: một tổ chức vừa hạ gói sẽ ở đây mỗi ngày cho
                # tới khi họ dọn bớt, và biến việc đó thành cảnh báo hằng ngày
                # là cách nhanh nhất để mọi người thôi đọc cảnh báo.
                ket["vuot_tran"] += 1
                logger.info(
                    "[STORAGE] %s: dang vuot tran — %d/%d byte. Ghi them bi chan; "
                    "du lieu da co giu nguyen.", t, that, tran)

    logger.info("[STORAGE] doi chieu xong: %s", ket)
    return ket
