"""Đo mức dùng theo tenant: gộp mỗi ngày một lần, đọc tức thì về sau.

Vì sao gộp theo ngày thay vì đếm lúc hỏi
-----------------------------------------
Câu hỏi thật là "tháng này tổ chức B thu bao nhiêu mẫu, huấn luyện bao nhiêu
giờ". Tính trực tiếp thì mỗi lần mở bảng điều khiển là một lượt quét `samples`
theo khoảng thời gian; tính sẵn mỗi ngày một lần thì cùng câu đó đọc 30 dòng.

Quan trọng hơn tốc độ: bản gộp **giữ được quá khứ**. Mẫu bị xoá mềm hôm nay
vẫn phải được tính cho ngày nó được thu — người ta đã dùng tài nguyên để xử lý
nó. Tính trực tiếp trên bảng nguồn sẽ lặng lẽ viết lại lịch sử mỗi lần ai đó
dọn dữ liệu, và hoá đơn tháng trước đổi số sau khi đã gửi đi.

Đây là ranh giới với `plans.current_usage`: hàm đó đếm HIỆN TẠI trên bảng
nguồn để chặn, và phải luôn khớp thực tế. Module này ghi lại ĐÃ TỪNG, và phải
không bao giờ đổi. Hai câu hỏi khác nhau, hai đường tính khác nhau, cố ý.

Chạy lại có an toàn không
--------------------------
Có. Mỗi câu là `INSERT ... ON CONFLICT DO UPDATE`, khoá chính là
`(tenant_id, usage_date, metric)`. Gộp lại ngày hôm qua lần thứ hai cho ra
đúng con số đó. Điều này cần thiết vì tác vụ nền có thể chạy hai lần sau một
lần khởi động lại, và vì người vận hành phải lấp được khoảng trống bằng tay
sau một sự cố.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Mỗi chỉ số: (tên, SQL sinh ra (tenant_id, value) cho MỘT ngày).
#:
#: `%(day)s` là ngày đang gộp. Truy vấn phải trả về đúng hai cột và không được
#: lọc theo tenant — cả bảng được gộp trong một lượt, vì hai mươi truy vấn nhỏ
#: cho hai mươi tenant tốn hơn hẳn một truy vấn có GROUP BY.
_ROLLUPS: Dict[str, str] = {
    # Số mẫu THU được trong ngày. Không lọc `deleted_at`: xem chú thích đầu
    # tệp — xoá về sau không làm ngày đó chưa từng xảy ra.
    "samples_created": """
        SELECT tenant_id, count(*)::bigint AS value
        FROM samples
        WHERE created_at >= %(day)s::date AND created_at < (%(day)s::date + 1)
        GROUP BY tenant_id
    """,
    "raw_uploads_created": """
        SELECT tenant_id, count(*)::bigint AS value
        FROM raw_uploads
        WHERE created_at >= %(day)s::date AND created_at < (%(day)s::date + 1)
        GROUP BY tenant_id
    """,
    "training_jobs_started": """
        SELECT tenant_id, count(*)::bigint AS value
        FROM training_jobs
        WHERE created_at >= %(day)s::date AND created_at < (%(day)s::date + 1)
        GROUP BY tenant_id
    """,
    # Giây máy đã tiêu cho huấn luyện. Tính trên job KẾT THÚC trong ngày chứ
    # không job bắt đầu trong ngày: một lượt chạy qua nửa đêm chỉ có đủ số liệu
    # khi nó xong, và gán trọn thời lượng cho ngày kết thúc là quy ước duy nhất
    # không cần sửa lại số của ngày hôm trước.
    "training_seconds": """
        SELECT tenant_id,
               COALESCE(sum(EXTRACT(EPOCH FROM (completed_at - started_at))), 0)::bigint AS value
        FROM training_jobs
        WHERE completed_at IS NOT NULL AND started_at IS NOT NULL
          AND completed_at >= %(day)s::date AND completed_at < (%(day)s::date + 1)
        GROUP BY tenant_id
    """,
    # Số tài khoản thực sự đóng góp trong ngày. `auth_user_id` NULL ở phần lớn
    # dữ liệu cũ (xem [[sheets-marker-and-ownership]]), nên con số này chỉ có
    # nghĩa từ khi đường ghi bắt đầu điền nó — lọc NULL để không đếm một "người
    # dùng không xác định" thành một người.
    "active_users": """
        SELECT tenant_id, count(DISTINCT auth_user_id)::bigint AS value
        FROM samples
        WHERE auth_user_id IS NOT NULL
          AND created_at >= %(day)s::date AND created_at < (%(day)s::date + 1)
        GROUP BY tenant_id
    """,
}

#: Chỉ số đo TRẠNG THÁI chứ không đo dòng chảy: dung lượng đĩa hôm nay là bao
#: nhiêu, chứ không phải "tăng bao nhiêu". Ghi cùng bảng nhưng tính riêng vì
#: nguồn của nó là hệ thống tệp, không phải SQL.
STORAGE_METRIC = "storage_mb"


def _yesterday() -> date:
    return (datetime.now(timezone.utc) - timedelta(days=1)).date()


def _upsert(rows: List[tuple]) -> int:
    """Ghi (tenant_id, usage_date, metric, value) theo lô."""
    if not rows:
        return 0
    from app.storage.metadata_db import _execute_many

    _execute_many(
        "INSERT INTO tenant_usage_daily(tenant_id, usage_date, metric, value, computed_at) "
        "VALUES(%s, %s, %s, %s, NOW()) "
        "ON CONFLICT (tenant_id, usage_date, metric) "
        "DO UPDATE SET value = EXCLUDED.value, computed_at = EXCLUDED.computed_at",
        rows,
    )
    return len(rows)


def tenant_storage_mb() -> Dict[str, int]:
    """Dung lượng đĩa mỗi tenant đang chiếm, tính bằng MB.

    Uỷ quyền cho `storage_quota._billable_bytes` chứ không tự đi bộ. Vì sao —
    trước v8 hàm này có định nghĩa "dung lượng" RIÊNG (chỉ cây `features/`),
    còn bộ đếm hạn mức có định nghĩa khác (thêm kho raw và video thô). Hai con
    số cùng tên, cùng một trang giao diện, và không bằng nhau. Người dùng thấy
    hai câu trả lời cho một câu hỏi thì không tin câu nào.

    Bảng hiện vật tính phí ở `docs/07-business/BILLABLE_STORAGE_INVENTORY.md` là
    định nghĩa DUY NHẤT, và `_billable_bytes` là hiện thực duy nhất của nó.

    Lỗi đọc một thư mục không làm hỏng cả phép đo: tenant đó bị bỏ qua và được
    ghi lại, các tenant khác vẫn có số.
    """
    from app.storage.metadata_db import _fetch_all
    from app.storage_quota import _billable_bytes
    from app.tenant_context import system_scope

    with system_scope("usage: list tenants for the storage sweep"):
        rows = _fetch_all("SELECT tenant_id FROM tenants WHERE deleted_at IS NULL")

    out: Dict[str, int] = {}
    for row in rows:
        tenant = row["tenant_id"]
        try:
            out[tenant] = _billable_bytes(tenant) // (1024 * 1024)
        except Exception as exc:
            logger.warning("[USAGE] %s: không quét được thư mục (%s)", tenant, exc)
            continue
    return out


def rollup_day(day: Optional[date] = None, *, include_storage: bool = True) -> Dict[str, int]:
    """Tính lại mọi chỉ số cho một ngày. Chạy lại bao nhiêu lần cũng ra một kết quả."""
    target = day or _yesterday()
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    written: Dict[str, int] = {}
    for metric, sql in _ROLLUPS.items():
        try:
            # ĐỌC và GHI phải nằm trong CÙNG khối scope.
            #
            # Bản đầu đóng scope ngay sau câu đọc rồi mới gọi `_upsert`, và
            # RLS từ chối sạch mọi lượt ghi: `tenant_usage_daily` có chính
            # sách với `WITH CHECK`, nên một kết nối không scope không chèn
            # được hàng nào. Cả tính năng đo mức dùng ghi ra số không, mỗi
            # ngày, mãi mãi — chỉ để lại một dòng lỗi trong nhật ký của một
            # tác vụ nền mà không ai đọc.
            #
            # Đây là RLS làm đúng việc: ghi không scope thì hỏng theo hướng
            # đóng. Chỗ sai là ranh giới khối, không phải chính sách.
            with system_scope(f"usage: roll up {metric} across tenants"):
                rows = _fetch_all(sql, {"day": target.isoformat()})
                payload = [
                    (r["tenant_id"], target, metric, int(r["value"] or 0)) for r in rows
                ]
                written[metric] = _upsert(payload)
        except Exception as exc:
            # Một chỉ số hỏng không được kéo theo các chỉ số khác: mất một cột
            # trong biểu đồ tốt hơn mất cả ngày dữ liệu.
            logger.error("[USAGE] gộp %s cho %s hỏng: %s", metric, target, exc)
            written[metric] = 0

    if include_storage:
        try:
            sizes = tenant_storage_mb()
            with system_scope("usage: write the storage readings"):
                written[STORAGE_METRIC] = _upsert(
                    [(t, target, STORAGE_METRIC, int(mb)) for t, mb in sizes.items()]
                )
        except Exception as exc:
            logger.error("[USAGE] đo dung lượng cho %s hỏng: %s", target, exc)
            written[STORAGE_METRIC] = 0

    logger.info("[USAGE] đã gộp %s: %s", target, written)
    return written


def backfill(days: int = 30) -> Dict[str, int]:
    """Gộp lại `days` ngày gần nhất.

    Dùng sau khi triển khai lần đầu (bảng trống nhưng dữ liệu đã có) và sau một
    sự cố làm tác vụ nền nghỉ vài ngày. Chỉ đo dung lượng cho ngày cuối: dung
    lượng là trạng thái hiện tại, và gán con số hôm nay cho ba mươi ngày trước
    là bịa ra một lịch sử phẳng chưa từng có.
    """
    today = datetime.now(timezone.utc).date()
    totals: Dict[str, int] = {}
    for offset in range(days, 0, -1):
        day = today - timedelta(days=offset)
        result = rollup_day(day, include_storage=False)
        for metric, n in result.items():
            totals[metric] = totals.get(metric, 0) + n
    result = rollup_day(today)
    for metric, n in result.items():
        totals[metric] = totals.get(metric, 0) + n
    return totals


def usage_series(
    tenant_id: str,
    *,
    days: int = 30,
    metrics: Optional[List[str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Chuỗi thời gian cho một tenant, dạng {chỉ số: [{ngày, giá trị}]}.

    Ngày KHÔNG có dòng thì không xuất hiện, và đó là chủ ý: chèn số 0 cho ngày
    chưa gộp sẽ khiến "chưa tính" trông y hệt "không có hoạt động". Biểu đồ ở
    giao diện tự lấp khoảng trống nếu muốn — nó biết mình muốn vẽ gì, ở đây thì
    không.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenancy import normalize_tenant_id
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id)
    wanted = metrics or [*_ROLLUPS.keys(), STORAGE_METRIC]
    since = datetime.now(timezone.utc).date() - timedelta(days=max(1, days))

    with system_scope("usage: read the usage series of a tenant"):
        rows = _fetch_all(
            "SELECT usage_date, metric, value FROM tenant_usage_daily "
            "WHERE tenant_id = %s AND metric = ANY(%s) AND usage_date >= %s "
            "ORDER BY usage_date",
            (tenant, list(wanted), since),
        )

    out: Dict[str, List[Dict[str, Any]]] = {m: [] for m in wanted}
    for row in rows:
        out.setdefault(row["metric"], []).append(
            {"date": row["usage_date"].isoformat(), "value": int(row["value"])}
        )
    return out


def usage_totals(tenant_id: str, *, days: int = 30) -> Dict[str, int]:
    """Tổng mỗi chỉ số trong `days` ngày qua.

    Dung lượng được lấy GIÁ TRỊ CUỐI chứ không cộng dồn: cộng ba mươi lần đo
    dung lượng lại với nhau cho ra một con số không có nghĩa gì cả.
    """
    series = usage_series(tenant_id, days=days)
    out: Dict[str, int] = {}
    for metric, points in series.items():
        if not points:
            out[metric] = 0
        elif metric == STORAGE_METRIC:
            out[metric] = int(points[-1]["value"])
        else:
            out[metric] = sum(int(p["value"]) for p in points)
    return out


def platform_totals(*, days: int = 30) -> List[Dict[str, Any]]:
    """Bảng xếp hạng cho người vận hành: mỗi tenant một dòng, đã cộng sẵn.

    Một truy vấn có GROUP BY, không phải một lượt gọi `usage_totals` cho mỗi
    tenant — cùng lý do N+1 mà `list_tenants` đã tránh.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    since = datetime.now(timezone.utc).date() - timedelta(days=max(1, days))
    with system_scope("usage: platform-wide usage table"):
        rows = _fetch_all(
            """
            SELECT u.tenant_id,
                   t.display_name,
                   t.plan_code,
                   t.billing_status,
                   sum(u.value) FILTER (WHERE u.metric = 'samples_created')      AS samples,
                   sum(u.value) FILTER (WHERE u.metric = 'training_seconds')     AS training_seconds,
                   sum(u.value) FILTER (WHERE u.metric = 'training_jobs_started') AS training_jobs,
                   max(u.value) FILTER (WHERE u.metric = 'storage_mb')           AS storage_mb
            FROM tenant_usage_daily u
            JOIN tenants t ON t.tenant_id = u.tenant_id
            WHERE u.usage_date >= %s
            GROUP BY u.tenant_id, t.display_name, t.plan_code, t.billing_status
            ORDER BY samples DESC NULLS LAST
            """,
            (since,),
        )
    return [
        {
            "tenant_id": r["tenant_id"],
            "display_name": r["display_name"],
            "plan_code": r["plan_code"],
            "billing_status": r["billing_status"],
            "samples": int(r["samples"] or 0),
            "training_seconds": int(r["training_seconds"] or 0),
            "training_jobs": int(r["training_jobs"] or 0),
            "storage_mb": int(r["storage_mb"] or 0),
        }
        for r in rows
    ]
