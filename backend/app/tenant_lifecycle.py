"""Khách hàng rời đi: lấy dữ liệu của họ ra, rồi xoá hẳn nó khỏi hệ thống.

`tenant_admin.delete_tenant` chỉ đánh dấu `deleted_at` — có chủ ý, vì
`ON DELETE RESTRICT` chặn xoá thật và vì dữ liệu phải còn địa chỉ để lấy ra.
Nhưng dừng ở đó là dừng giữa đường: một tổ chức rời nền tảng không có cách nào
mang dữ liệu của mình đi, và cũng không có cách nào yêu cầu xoá hẳn.

Với dữ liệu người khuyết tật kèm phiếu chấp thuận, hai việc đó không phải tiện
nghi. Chúng là điều kiện để một trường dám ký hợp đồng, và là nghĩa vụ khi
người ký rút lại chấp thuận.

Ba cái phanh trước khi xoá vĩnh viễn
-------------------------------------
Đây là thao tác KHÔNG hoàn tác được duy nhất trong hệ thống. Nên nó đòi cả ba:

1. Tenant đã bị xoá mềm, và đã nằm ở trạng thái đó đủ `tenant_purge_grace_days`.
2. Người gọi gõ đúng `tenant_id` vào ô xác nhận — không phải tích một ô.
3. Đã có một bản xuất `ready`, hoặc người gọi nói rõ là không cần.

Điều kiện 3 tồn tại vì kịch bản hỏng hay gặp nhất không phải kẻ xấu, mà là một
người vận hành xoá đúng tenant mình định xoá rồi phát hiện chưa ai lấy dữ liệu
ra. Bắt buộc phải có bản xuất khiến trình tự đúng thành đường mặc định.

Về thứ tự xoá
--------------
`PURGE_ORDER` là LÁ TRƯỚC GỐC và trật tự đó là một phần của tính đúng: mọi bảng
trong đó đều bị bảng khác trỏ tới, nên xoá cha trước con sẽ bị khoá ngoại từ
chối. Danh sách này là nguồn sự thật DUY NHẤT — `tests/conftest.py` nhập lại
chính nó thay vì giữ một bản sao, vì hai bản sao của một thứ tự phụ thuộc là
thứ trôi khỏi nhau ngay lần thêm bảng tiếp theo.
"""

from __future__ import annotations

import json
import logging
import shutil
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Bảng có `tenant_id`, xếp lá trước gốc. Xem chú thích đầu tệp.
PURGE_ORDER: tuple[str, ...] = (
    # v4 — không bảng nào bị bảng khác trỏ tới, nên đi trước cho gọn
    "webhook_deliveries", "webhook_endpoints", "api_keys",
    "tenant_exports", "tenant_usage_daily", "tenant_subscriptions",
    # `tenant_storage` (v8): không bảng nào trỏ tới nó nên đứng đâu cũng được;
    # đặt cạnh các bảng vận hành khác của tenant cho dễ đọc.
    "tenant_storage",
    # `storage_reservations` (v8): cũng không bị trỏ tới. Xoá tenant giữa lúc
    # một lượt tải lên đang bay sẽ bỏ lại khoản giữ chỗ; xoá ở đây để lượt quét
    # khoản treo không phải đi tìm một tenant đã không còn.
    "storage_reservations",
    # v6 — `support_messages` PHẢI đi trước `support_tickets`: nó có khoá ngoại
    # trỏ tới phiếu, nên xoá phiếu trước sẽ bị từ chối. `notifications` không bị
    # bảng nào trỏ tới nên đứng đâu cũng được; đặt cạnh nhau cho dễ đọc.
    "notifications", "support_messages", "support_tickets",
    # corpus
    "samples",                                   # -> classes, signers, capture_sessions
    # `training_metrics` PHẢI đi trước `training_jobs`: nó trỏ tới job.
    #
    # Có thể nghĩ nó thừa, vì `fk_training_metrics_job` là ON DELETE CASCADE nên
    # xoá job sẽ kéo theo chỉ số. Nhưng nó KHÔNG thừa, và lý do nằm ở một khoá
    # ngoại khác: `fk_training_metrics_tenant` là ON DELETE **RESTRICT**. Bất kỳ
    # dòng chỉ số nào còn sót lại mà cascade không với tới đều làm bước xoá
    # `tenants` ở cuối lượt purge bị từ chối, và cả lượt dừng giữa chừng.
    #
    # Danh sách này còn là nguồn dọn dẹp của fixture test (`conftest.purge_tenant`),
    # nơi dữ liệu được dựng tay và không phải lúc nào cũng có job cha để cascade.
    # Liệt kê tường minh thì đúng trong cả hai đường; dựa vào cascade thì chỉ
    # đúng ở một.
    "training_metrics",                          # -> training_jobs, tenants(RESTRICT)
    "training_job_classes", "training_jobs",     # -> classes, users
    "raw_uploads",                               # -> classes, dialects
    "capture_sessions",                          # -> classes, signers, collection_sessions
    # `collection_sessions` PHẢI đi SAU `capture_sessions`: capture session trỏ
    # lên buổi thu, nên xoá buổi trước sẽ bị khoá ngoại từ chối. Và nó phải đi
    # TRƯỚC `signers` vì chính nó trỏ xuống người ký.
    #
    # Đừng trông vào `ON DELETE SET NULL` của `fk_capture_sessions_collection`
    # để khỏi phải liệt kê ở đây: SET NULL gỡ con trỏ chứ không xoá hàng, và
    # hàng buổi thu còn sót lại mang `tenant_id` với khoá ngoại RESTRICT sẽ làm
    # bước `DELETE FROM tenants` cuối lượt purge bị từ chối — đúng vết đã ghi
    # cho `training_metrics` và `project_allocations`.
    "collection_sessions",                       # -> signers
    "dialect_aliases", "classes",                # -> dialects, vocabulary_groups
    "vocabulary_groups",                         # <- classes
    "signer_consents", "signer_aliases",         # -> signers
    # `vocabulary_registry_meta` PHẢI đi TRƯỚC `registry_versions`, và thứ tự
    # này đảo lại ngày 24/08/2026 vì quan hệ cha–con giữa hai bảng vừa được
    # KHAI BÁO ra: `fk_vocabulary_registry_meta_version` làm dòng meta thành
    # CON trỏ tới phiên bản registry.
    #
    # Trước khoá ngoại ấy, hai bảng chỉ liên quan theo quy ước, nên thứ tự nào
    # cũng chạy. Sau nó, xoá cha trước bị từ chối và cả lượt purge dừng giữa
    # chừng — nghĩa là tenant mất một phần dữ liệu nhưng vẫn còn tồn tại.
    "vocabulary_registry_meta",                  # -> registry_versions
    "registry_versions", "recognition_profiles", "dialects",
    "signers",
    # PDM v5 — mặt phẳng phân quyền. Thứ tự trong khối này KHÔNG tuỳ ý.
    #
    # Vì sao danh sách này KHÔNG còn `*_member_roles` và `*_members`
    # --------------------------------------------------------------
    # v5 gộp ba bảng thành viên thành `memberships` và bốn bảng gán thành
    # `role_assignments`. Bảy cái tên cũ KHÔNG còn được tạo ra ở đâu cả, nên
    # giữ chúng ở đây làm mọi lượt purge — và mọi fixture test dùng nó — ngã
    # với `UndefinedTable`. Đo được 11/08/2026: 108 lỗi trong ba tệp test, tất
    # cả từ đúng chỗ này.
    #
    #   memberships     -> workspaces, projects (CASCADE), tenants (RESTRICT)
    #   projects        -> workspaces
    #   roles           <- role_assignments     (ON DELETE RESTRICT!)
    #
    # `role_assignments` KHÔNG có mặt trong danh sách này, và đó là chủ ý chứ
    # không phải bỏ sót: bảng đó không mang `tenant_id`, nên vòng lặp
    # `DELETE ... WHERE tenant_id = %s` không đụng tới nó được. Nó ra đi theo
    # `fk_role_assignments_membership`, vốn là ON DELETE CASCADE — xoá
    # `memberships` là xoá luôn mọi lần gán treo dưới đó.
    #
    # Hệ quả cho thứ tự: `roles` phải đứng SAU `memberships`.
    # `role_assignments.role_id -> roles` là RESTRICT (một role còn người đang
    # giữ thì không được biến mất lặng lẽ), nên xoá role riêng của tenant trước
    # khi cascade dọn assignment sẽ bị từ chối và cả lượt purge dừng giữa chừng.
    #
    # `tenant_members` KHÔNG có ở đây nữa: nó là VIEW trên `memberships`, và
    # xoá qua view sau khi đã xoá bảng nền là một lượt quét thừa trên 0 dòng.
    #
    # `event_outbox` không bị bảng nào trỏ tới nên đứng đâu cũng được; đặt đầu
    # khối cho dễ đọc.
    "event_outbox",
    "memberships",
    # `project_allocations` PHẢI đi trước `projects`, và có mặt ở đây là bắt
    # buộc chứ không phải cho gọn. Nó mang HAI khoá ngoại tới `tenants`: một cái
    # ON DELETE CASCADE (từ câu `REFERENCES` viết thẳng trong `CREATE TABLE`) và
    # một cái ON DELETE **RESTRICT** (do lượt cấp khoá ngoại chung cho mọi bảng
    # có `tenant_id` thêm vào). Khi hai ràng buộc cùng áp, cái chặt hơn thắng —
    # nên CASCADE ở đây KHÔNG dọn gì cả, và một dòng cấp phát còn sót sẽ làm
    # bước `DELETE FROM tenants` ở cuối lượt purge bị từ chối, y hệt vết đã ghi
    # cho `training_metrics` phía trên.
    #
    # Danh sách này cũng là đường dọn của `conftest.purge_tenant`, nên thiếu nó
    # thì mọi fixture chạm tới cấp phát sẽ rò dữ liệu sang lượt test sau.
    "project_allocations",
    "projects", "workspaces",
    "roles",
    "tenant_invitations",
    "audit_log",
)

#: Bảng được ĐƯA VÀO bản xuất. Gần bằng `PURGE_ORDER` nhưng không phải một:
#: `api_keys` và `webhook_endpoints` chứa bí mật xác thực, và một tệp zip gửi
#: qua email không phải chỗ để chúng đi ra ngoài. Khách hàng rời đi thì cấp
#: khoá mới ở nơi mới, không mang khoá cũ theo.
EXPORT_TABLES: tuple[str, ...] = tuple(
    t for t in PURGE_ORDER if t not in ("api_keys", "webhook_endpoints", "webhook_deliveries")
) + ("users",)


class LifecycleError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _export_root() -> Path:
    from app.config import settings

    root = Path(settings.dataset_root) / "_exports"
    root.mkdir(parents=True, exist_ok=True)
    return root


# --------------------------------------------------------------------------- export


#: Hoàn trả dữ liệu cho chính đơn vị quản trị: sao lưu, hoặc rời nền tảng.
EXPORT_PURPOSE_PORTABILITY = "tenant_portability"

#: Phát hành dữ liệu cho một mục đích sử dụng tiếp theo. Tên trùng với thang của
#: `consent_gate.SCOPE_LADDER` vì mỗi mục đích phát hành yêu cầu đúng mức đó.
RELEASE_PURPOSES: tuple = ("internal_training", "research_release", "public_library")

EXPORT_PURPOSES: tuple = (EXPORT_PURPOSE_PORTABILITY,) + RELEASE_PURPOSES


def request_export(
    tenant_id: str,
    *,
    requested_by: Optional[str] = None,
    scope: str = "metadata",
    export_purpose: str,
) -> Dict[str, Any]:
    """Ghi nhận yêu cầu xuất và trả về ngay. Việc nặng do tác vụ nền làm.

    `scope` và `export_purpose` hỏi hai câu khác nhau, và gộp chúng là gốc của
    lỗ hổng đã đo ngày 17\\08\\2026:

        scope           CÁI GÌ nằm trong gói   (metadata | full)
        export_purpose  gói này DỰNG ĐỂ LÀM GÌ (hoàn trả | phát hành)

    Bản trước chỉ có `scope`, nên cùng một endpoint vừa là đường hoàn trả dữ liệu
    cho tổ chức, vừa có thể là đường phát hành cho một bên sử dụng tiếp theo —
    và ranh giới đồng thuận phụ thuộc vào việc người gọi *hiểu đúng mục đích*.
    Đó là khoảng trống thẩm quyền ở tầng ngữ nghĩa, không phải ở tầng mã.

    Vì sao KHÔNG chặn đường hoàn trả bằng thang đồng thuận phát hành
    ----------------------------------------------------------------
    Vì nó tạo ra bế tắc: rút đồng thuận → không xuất được → `purge_tenant` từ
    chối vì chưa có bản xuất → muốn rời nền tảng phải dùng `skip_export_check`,
    tức là dữ liệu bị xoá mà chưa từng được mang đi. Một cơ chế an toàn mà đường
    vận hành bình thường phải thường xuyên đi vòng qua là cơ chế đặt sai chỗ.

    Hoàn trả cho đơn vị quản trị và phát hành cho mục đích sử dụng tiếp theo là
    hai hoạt động khác nhau, và phải được xét theo hai điều kiện khác nhau. Gói
    hoàn trả vì thế được phép chứa mẫu đã rút đồng thuận, nhưng KHÔNG được phép
    giao chúng đi trần: nó mang theo trạng thái đồng thuận và một bản kê hạn chế
    sử dụng, để dữ liệu đã rút không lặng lẽ trở thành dữ liệu dùng tự do.

    `export_purpose` là tham số bắt buộc và không có giá trị mặc định. Quên nó là
    `TypeError` ngay tại chỗ gọi, chứ không phải một lượt xuất im lặng rơi vào
    nhánh dễ dãi nhất — cùng lý do với `resolve_operational(..., *, tenant_id)`.
    """
    from app.config import settings
    from app.storage.metadata_db import _execute
    from app.tenancy import normalize_tenant_id
    from app.tenant_context import system_scope

    if scope not in ("metadata", "full"):
        raise LifecycleError("scope phải là 'metadata' hoặc 'full'", status_code=422)
    if export_purpose not in EXPORT_PURPOSES:
        raise LifecycleError(
            f"export_purpose phải là một trong {', '.join(EXPORT_PURPOSES)}",
            status_code=422)

    tenant = normalize_tenant_id(tenant_id)
    export_id = str(uuid.uuid4())
    expires = datetime.now(timezone.utc) + timedelta(days=settings.tenant_export_ttl_days)

    with system_scope("lifecycle: record an export request"):
        _execute(
            "INSERT INTO tenant_exports(export_id, tenant_id, requested_by, scope, "
            "export_purpose, status, expires_at) "
            "VALUES(%s, %s, %s, %s, %s, 'pending', %s)",
            (export_id, tenant, str(requested_by) if requested_by else None, scope,
             export_purpose, expires),
        )
    logger.info("[EXPORT] %s yêu cầu xuất %s (scope=%s, muc dich=%s)",
                requested_by, tenant, scope, export_purpose)
    return {"export_id": export_id, "tenant_id": tenant, "status": "pending",
            "scope": scope, "export_purpose": export_purpose}


def run_export(export_id: str) -> Dict[str, Any]:
    """Dựng gói zip cho một yêu cầu xuất. Chạy trong tác vụ nền.

    Ghi ra tệp tạm rồi mới đổi tên: một tiến trình bị giết giữa chừng để lại
    `.part` chứ không để lại một tệp zip hỏng mang đúng tên tệp thật, thứ mà
    người dùng sẽ tải về và tưởng là dữ liệu của mình.
    """
    from app.storage.metadata_db import _execute, _fetch_all
    from app.tenant_context import system_scope

    with system_scope("lifecycle: read an export request"):
        rows = _fetch_all("SELECT * FROM tenant_exports WHERE export_id = %s", (str(export_id),))
    if not rows:
        raise LifecycleError("không tìm thấy yêu cầu xuất", status_code=404)
    job = dict(rows[0])
    tenant = job["tenant_id"]

    with system_scope("lifecycle: mark an export running"):
        _execute(
            "UPDATE tenant_exports SET status = 'running' WHERE export_id = %s",
            (str(export_id),),
        )

    target = _export_root() / f"{tenant}_{export_id}.zip"
    partial = target.with_suffix(".zip.part")
    counts: Dict[str, int] = {}

    try:
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as bundle:
            for table in EXPORT_TABLES:
                with system_scope(f"lifecycle: export rows of {table}"):
                    data = _fetch_all(
                        f"SELECT * FROM {table} WHERE tenant_id = %s", (tenant,)
                    )
                counts[table] = len(data)
                bundle.writestr(
                    f"data/{table}.json",
                    json.dumps(data, ensure_ascii=False, indent=2, default=str),
                )

            with system_scope("lifecycle: export the tenant record"):
                tenant_row = _fetch_all(
                    "SELECT * FROM tenants WHERE tenant_id = %s", (tenant,)
                )
            bundle.writestr(
                "data/tenant.json",
                json.dumps(tenant_row, ensure_ascii=False, indent=2, default=str),
            )
            bundle.writestr(
                "README.txt",
                _export_readme(tenant, job.get("scope") or "metadata", counts),
            )

            if (job.get("scope") or "metadata") == "full":
                counts["_files"], ban_ke = _add_feature_files(
                    bundle, tenant,
                    export_purpose=job.get("export_purpose") or EXPORT_PURPOSE_PORTABILITY)
                # Bản kê đi CÙNG gói, không chỉ nằm trong nhật ký máy chủ. Người
                # mở gói ra sáu tháng sau phải đọc được gói này gồm gì, thiếu gì
                # và vì sao — nếu không, một gói đã lọc và một gói đầy đủ trông
                # giống hệt nhau.
                bundle.writestr(
                    "MANIFEST_CONSENT.json",
                    json.dumps(ban_ke, ensure_ascii=False, indent=2, default=str))

        partial.replace(target)
        size = target.stat().st_size
        with system_scope("lifecycle: mark an export ready"):
            _execute(
                "UPDATE tenant_exports SET status = 'ready', file_path = %s, "
                "size_bytes = %s, row_counts = %s, completed_at = NOW() "
                "WHERE export_id = %s",
                (str(target), size, json.dumps(counts), str(export_id)),
            )
        logger.info("[EXPORT] %s xong: %s (%d byte)", tenant, target.name, size)
        return {"export_id": export_id, "status": "ready", "size_bytes": size,
                "row_counts": counts}

    except Exception as exc:
        partial.unlink(missing_ok=True)
        with system_scope("lifecycle: mark an export failed"):
            _execute(
                "UPDATE tenant_exports SET status = 'failed', error = %s, "
                "completed_at = NOW() WHERE export_id = %s",
                (f"{type(exc).__name__}: {exc}"[:500], str(export_id)),
            )
        logger.error("[EXPORT] %s hỏng: %s", tenant, exc)
        raise


def _ten_tep_duoc_phep(tenant: str, scope_yeu_cau: str, *,
                       ap_kiem_duyet: bool) -> tuple:
    """(tên tệp đủ điều kiện, bản kê) cho một mức phạm vi đồng thuận.

    Trả về TÊN TỆP chứ không phải đường dẫn: hàng mẫu ghi `file_path` theo bố cục
    lúc nó được tạo, còn tệp trên đĩa có thể đã đi qua một lượt đổi tên lớp hoặc
    một lượt chuyển phương ngữ. Tên `sample_<uid>.npz` có mang `sample_uid` nên
    nó là thứ duy nhất bền qua những lượt ấy.
    """
    from app import consent_gate, moderation
    from app.dataset_samples import list_samples

    rows = list_samples(tenant)

    # Cổng kiểm duyệt chỉ áp cho nhánh PHÁT HÀNH, không áp cho hoàn trả.
    #
    # Hàm này phục vụ hai nhánh với hai ngữ nghĩa trái ngược:
    #
    #   phát hành   tệp ngoài `duoc_phep` bị LOẠI
    #   hoàn trả    tệp ngoài `duoc_phep` bị ĐÁNH DẤU, vẫn đi vào gói
    #
    # Bản đầu lọc ở đây cho cả hai, và `test_c5_7` bắt được ngay: gói hoàn trả
    # là "trả lại dữ liệu của CHÍNH tổ chức". Một mẫu họ vừa thu, chưa ai duyệt,
    # vẫn là dữ liệu của họ — đánh dấu nó "bị hạn chế" trong gói hoàn trả là
    # trả lời sai một câu hỏi hoàn toàn khác.
    #
    # Kiểm duyệt hỏi "cái này có được dùng CHUNG không", không hỏi "cái này có
    # phải của anh không".
    #
    # Chạy TRƯỚC cổng đồng thuận vì rẻ hơn: một phép so chuỗi trên từng dòng,
    # không phải nạp bảng đồng thuận và giải chuỗi bí danh người ký.
    if ap_kiem_duyet:
        truoc_kd = len(rows)
        rows = moderation.filter_rows(rows, viewer_id=None).kept
        if len(rows) != truoc_kd:
            logger.info("[RELEASE] cong kiem duyet giu lai %d/%d mau",
                        len(rows), truoc_kd)

    ket_qua = consent_gate.filter_rows(rows, scope=scope_yeu_cau, tenant_id=tenant)

    def _ten(row: Dict[str, Any]) -> str:
        for khoa in ("file_path", "storage_key", "storage_url"):
            gia_tri = str(row.get(khoa) or "").strip()
            if gia_tri:
                return Path(gia_tri.replace("\\", "/")).name
        return ""

    duoc_phep = {_ten(r) for r in ket_qua.kept}
    duoc_phep.discard("")
    giu_lai = {_ten(r) for r in ket_qua.withheld}
    giu_lai.discard("")
    return duoc_phep, ket_qua, giu_lai


def _add_feature_files(bundle: zipfile.ZipFile, tenant: str, *,
                       export_purpose: str) -> tuple:
    """Tệp đặc trưng CỦA tenant này vào gói zip. Trả về (số tệp, bản kê).

    Hai chuyện tách bạch xảy ra ở đây.

    Một — phạm vi tổ chức. Đi qua `iter_tenant_feature_files`, không phải
    `root.rglob('*')`. Với tenant gốc, `root` chính là `FEATURES_ROOT`, mà
    `_tenants/` nằm bên trong đó, nên `rglob` đóng gói dữ liệu của mọi tổ chức
    vào một tệp tên `default-export.zip`. Đo được 17\\08\\2026.

    Hai — phạm vi đồng thuận, và nó phụ thuộc mục đích của gói:

    ```
    tenant_portability   ĐƯA ĐỦ, kèm bản kê đánh dấu phần bị hạn chế sử dụng
    <mục đích phát hành> LỌC fail-closed theo thang đồng thuận tương ứng
    ```

    Ở nhánh phát hành, một tệp trên đĩa KHÔNG khớp hàng mẫu nào cũng bị loại.
    Nó không có người ký xác định được, nên không có đồng thuận nào để dựa vào —
    và "không biết" ở một cổng phát hành phải nghĩa là không, giống hệt lý do
    `consent_gate._signer_of` từ chối lùi về `user_id`.
    """
    from app.dataset_manager import iter_tenant_feature_files, tenant_features_root

    root = tenant_features_root(tenant)
    la_phat_hanh = export_purpose in RELEASE_PURPOSES

    duoc_phep: set = set()
    giu_lai: set = set()
    ket_qua = None
    if la_phat_hanh or export_purpose == EXPORT_PURPOSE_PORTABILITY:
        # Cả hai nhánh đều cần biết ai bị hạn chế: nhánh phát hành để LOẠI,
        # nhánh hoàn trả để ĐÁNH DẤU.
        muc = export_purpose if la_phat_hanh else "research_release"
        duoc_phep, ket_qua, giu_lai = _ten_tep_duoc_phep(
            tenant, muc, ap_kiem_duyet=la_phat_hanh)

    added = 0
    loai_vi_dong_thuan = 0
    loai_vi_khong_ro = 0
    danh_dau: List[str] = []

    for path in iter_tenant_feature_files(tenant):
        ten = path.name
        if la_phat_hanh:
            if ten not in duoc_phep:
                if ten in giu_lai:
                    loai_vi_dong_thuan += 1
                else:
                    loai_vi_khong_ro += 1
                continue
        elif ten in giu_lai:
            danh_dau.append(path.relative_to(root).as_posix())
        try:
            bundle.write(path, f"files/{path.relative_to(root).as_posix()}")
            added += 1
        except OSError as exc:
            # Một tệp không đọc được không được làm hỏng cả bản xuất; nó được
            # ghi vào nhật ký và bản xuất đi tiếp thiếu đúng tệp đó.
            logger.warning("[EXPORT] bỏ qua %s: %s", path, exc)

    ban_ke: Dict[str, Any] = {
        "export_purpose": export_purpose,
        "thoi_diem": datetime.now(timezone.utc).isoformat(),
        "tong_mau_xet": ket_qua.total if ket_qua is not None else 0,
        "so_tep_dua_vao": added,
    }
    if la_phat_hanh:
        ban_ke.update({
            "muc_dong_thuan_yeu_cau": export_purpose,
            "loai_vi_dong_thuan": loai_vi_dong_thuan,
            "loai_vi_khong_xac_dinh_nguoi_ky": loai_vi_khong_ro,
            "ly_do": dict(ket_qua.reasons) if ket_qua is not None else {},
            "tom_tat": ket_qua.summary() if ket_qua is not None else "",
        })
    else:
        ban_ke.update({
            "han_che_su_dung": (
                "Gói này được dựng để HOÀN TRẢ dữ liệu cho đơn vị quản trị. Các "
                "tệp liệt kê dưới đây thuộc về người ký đã rút hoặc chưa cấp đủ "
                "phạm vi đồng thuận; chúng có mặt để đơn vị quản trị giữ được bản "
                "sao đầy đủ, KHÔNG phải để dùng cho huấn luyện, nghiên cứu hay "
                "phát hành. Xem data/signer_consents.json để đối chiếu."),
            "so_tep_bi_han_che": len(danh_dau),
            "tep_bi_han_che": sorted(danh_dau),
        })
    return added, ban_ke


def _export_readme(tenant: str, scope: str, counts: Dict[str, int]) -> str:
    lines = [
        f"Bản xuất dữ liệu của tổ chức: {tenant}",
        f"Thời điểm: {datetime.now(timezone.utc).isoformat()}",
        f"Phạm vi: {scope}",
        "",
        "data/*.json  — từng bảng một, giữ nguyên tên cột trong cơ sở dữ liệu.",
    ]
    if scope == "full":
        lines.append("files/*     — tệp đặc trưng (.npz) theo đúng cấu trúc thư mục gốc.")
    lines += [
        "",
        "KHÔNG có trong bản xuất, có chủ ý: khoá API và bí mật webhook.",
        "Chúng là thông tin xác thực, không phải dữ liệu của bạn; hãy cấp lại ở nơi mới.",
        "",
        "Số dòng theo bảng:",
    ]
    lines += [f"  {table:<28} {n}" for table, n in sorted(counts.items())]
    return "\n".join(lines) + "\n"


def list_exports(tenant_id: str) -> List[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all
    from app.tenancy import normalize_tenant_id
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id)
    with system_scope("lifecycle: list the exports of a tenant"):
        rows = _fetch_all(
            "SELECT export_id, tenant_id, status, scope, export_purpose, size_bytes, "
            "row_counts, error, created_at, completed_at, expires_at FROM tenant_exports "
            "WHERE tenant_id = %s ORDER BY created_at DESC LIMIT 50",
            (tenant,),
        )
    return [dict(r) for r in rows]


def export_file(tenant_id: str, export_id: str) -> Path:
    """Đường dẫn tệp của một bản xuất, sau khi đã kiểm nó còn tải được.

    Phạm vi theo CẢ tenant lẫn id, cùng lý do với `webhooks.delete_endpoint`:
    một UUID đoán trúng không được phép trở thành đường tải dữ liệu của tổ chức
    khác.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenancy import normalize_tenant_id
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id)
    with system_scope("lifecycle: resolve an export file"):
        rows = _fetch_all(
            "SELECT status, file_path, expires_at FROM tenant_exports "
            "WHERE export_id = %s AND tenant_id = %s",
            (str(export_id), tenant),
        )
    if not rows:
        raise LifecycleError("không tìm thấy bản xuất", status_code=404)
    row = dict(rows[0])
    if row["status"] != "ready":
        raise LifecycleError(f"bản xuất đang ở trạng thái {row['status']}", status_code=409)
    expires = row.get("expires_at")
    if expires is not None and expires <= datetime.now(timezone.utc):
        raise LifecycleError("bản xuất đã hết hạn tải", status_code=410)
    path = Path(row["file_path"] or "")
    if not path.exists():
        raise LifecycleError("tệp của bản xuất không còn trên đĩa", status_code=410)
    return path


def cleanup_expired_exports() -> int:
    """Xoá tệp của những bản xuất đã hết hạn và đánh dấu chúng.

    Bản xuất chứa toàn bộ dữ liệu của một tổ chức. Để nó nằm mãi trên đĩa là tự
    tạo thêm một bản sao đầy đủ phải canh giữ, ở một thư mục không có kiểm soát
    truy cập nào ngoài quyền tệp.
    """
    from app.storage.metadata_db import _execute, _fetch_all
    from app.tenant_context import system_scope

    with system_scope("lifecycle: find expired exports"):
        rows = _fetch_all(
            "SELECT export_id, file_path FROM tenant_exports "
            "WHERE status = 'ready' AND expires_at IS NOT NULL AND expires_at <= NOW()"
        )
    removed = 0
    for row in rows:
        path = Path(row["file_path"] or "")
        try:
            if path.exists():
                path.unlink()
            removed += 1
        except OSError as exc:
            logger.warning("[EXPORT] không xoá được %s: %s", path, exc)
            continue
        with system_scope("lifecycle: mark an export expired"):
            _execute(
                "UPDATE tenant_exports SET status = 'expired', file_path = NULL "
                "WHERE export_id = %s",
                (str(row["export_id"]),),
            )
    if removed:
        logger.info("[EXPORT] dọn %d bản xuất hết hạn", removed)
    return removed


# --------------------------------------------------------------------------- purge


def purge_preview(tenant_id: str) -> Dict[str, Any]:
    """Sẽ xoá những gì, và đã đủ điều kiện xoá chưa. Không thay đổi gì cả.

    Tồn tại để giao diện hiện được con số THẬT trước ô xác nhận. "Bạn có chắc
    không?" mà không kèm "3.860 mẫu, 63 lớp, 10 tài khoản" là một câu hỏi người
    ta bấm qua theo phản xạ.
    """
    from app.config import settings
    from app.storage.metadata_db import _fetch_all
    from app.tenancy import DEFAULT_TENANT_ID, normalize_tenant_id
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id)
    blockers: List[str] = []

    if tenant == DEFAULT_TENANT_ID:
        blockers.append("Đây là tenant gốc của nền tảng và không bao giờ xoá được.")

    with system_scope("lifecycle: preview a purge"):
        rows = _fetch_all(
            "SELECT display_name, deleted_at FROM tenants WHERE tenant_id = %s", (tenant,)
        )
        if not rows:
            raise LifecycleError("không tìm thấy tổ chức", status_code=404)
        record = dict(rows[0])

        counts: Dict[str, int] = {}
        for table in PURGE_ORDER:
            result = _fetch_all(
                f"SELECT count(*) AS n FROM {table} WHERE tenant_id = %s", (tenant,)
            )
            counts[table] = int(result[0]["n"]) if result else 0
        users = _fetch_all(
            "SELECT count(*) AS n FROM users WHERE tenant_id = %s", (tenant,)
        )
        counts["users"] = int(users[0]["n"]) if users else 0

        # CHỈ gói hoàn trả mới đủ tư cách làm điều kiện trước khi xoá.
        #
        # Một gói phát hành đã bị lọc theo đồng thuận, nên nó KHÔNG phải bản sao
        # dữ liệu của tổ chức — nhận nó rồi cho xoá vĩnh viễn nghĩa là phần bị
        # lọc biến mất mà chưa từng được hoàn trả cho ai. Đúng những mẫu của
        # người đã rút đồng thuận là phần dễ mất nhất theo đường này.
        ready = _fetch_all(
            "SELECT count(*) AS n FROM tenant_exports "
            "WHERE tenant_id = %s AND status = 'ready' AND export_purpose = %s",
            (tenant, EXPORT_PURPOSE_PORTABILITY),
        )
        has_export = bool(ready and int(ready[0]["n"]) > 0)

    deleted_at = record.get("deleted_at")
    if deleted_at is None:
        blockers.append("Tổ chức chưa bị xoá mềm. Hãy xoá mềm trước.")
    else:
        grace = timedelta(days=settings.tenant_purge_grace_days)
        earliest = deleted_at + grace
        if earliest > datetime.now(timezone.utc):
            blockers.append(
                f"Còn trong thời gian ân hạn; sớm nhất có thể xoá vĩnh viễn là "
                f"{earliest.isoformat()}."
            )

    return {
        "tenant_id": tenant,
        "display_name": record.get("display_name") or tenant,
        "deleted_at": deleted_at,
        "row_counts": counts,
        "total_rows": sum(counts.values()),
        "has_ready_export": has_export,
        "blockers": blockers,
        "can_purge": not blockers,
    }


def _record_purge(
    *, purge_id: str, tenant: str, display_name: str,
    requested_by: Optional[str], counts: Dict[str, int],
    files_removed: int, bytes_removed: int, reason: str,
) -> None:
    """Ghi sổ cái nền tảng — qua vai ĐIỀU KHIỂN, không qua vai ứng dụng.

    Trước 15/08/2026 câu này chạy bằng `_execute` (vai `voya_app`) bọc trong
    `system_scope`. Hai điều sai với cách đó:

      * `voya_app` có đủ bốn quyền trên `tenant_purges`, nên nó vừa **xoá được
        lịch sử purge** vừa **ghi được "đã purge"** cho một tổ chức chưa hề bị
        xoá. Đó là lỗ toàn vẹn sổ cái.
      * `system_scope` ở đây chẳng bảo vệ gì: bảng không có RLS, và bản thân
        sentinel ấy `voya_app` cũng tự đặt được.

    Nay năng lực đến từ QUYỀN của một danh tính khác — `voya_control`, có đúng
    `INSERT` trên đúng bảng này. Không sentinel, không GUC. Xem
    `app/storage/control_plane.py`.

    Phân quyền đã xảy ra TRƯỚC: `routers/tenants.py` chặn bằng `require_sudo`,
    và `purge_tenant` tự kiểm điều kiện nghiệp vụ trước khi tới đây. Hàm này
    KHÔNG tự quyết định ai được purge.
    """
    from app.storage.control_plane import control_cursor

    with control_cursor() as cur:
        cur.execute(
            "INSERT INTO tenant_purges(purge_id, tenant_id, display_name, requested_by, "
            "row_counts, files_removed, bytes_removed, reason) "
            "VALUES(%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                purge_id, tenant, display_name, requested_by,
                json.dumps(counts), files_removed, bytes_removed, reason,
            ),
        )


def purge_tenant(
    tenant_id: str,
    *,
    confirm_tenant_id: str,
    requested_by: Optional[str] = None,
    reason: str = "",
    skip_export_check: bool = False,
) -> Dict[str, Any]:
    """Xoá vĩnh viễn một tổ chức. Không hoàn tác được.

    `confirm_tenant_id` phải bằng đúng `tenant_id`. Đây không phải nghi thức:
    một lời gọi API bị lặp lại, một nút bấm nhầm, một script chạy sai biến đều
    vượt qua được một cờ boolean, nhưng không vượt qua được việc phải gõ lại
    đúng cái tên.
    """
    from app.storage.metadata_db import _execute, _fetch_all
    from app.tenancy import DEFAULT_TENANT_ID, normalize_tenant_id
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id)
    if (confirm_tenant_id or "").strip() != tenant:
        raise LifecycleError(
            "Xác nhận không khớp: hãy gõ đúng mã tổ chức để xác nhận xoá vĩnh viễn.",
            status_code=400,
        )
    if tenant == DEFAULT_TENANT_ID:
        raise LifecycleError("Tenant gốc không bao giờ xoá được.", status_code=409)

    preview = purge_preview(tenant)
    if preview["blockers"]:
        raise LifecycleError("; ".join(preview["blockers"]), status_code=409)
    if not preview["has_ready_export"] and not skip_export_check:
        raise LifecycleError(
            "Chưa có bản xuất nào sẵn sàng. Hãy xuất dữ liệu trước, hoặc gọi lại "
            "với skip_export_check nếu tổ chức đã xác nhận không cần.",
            status_code=409,
        )

    counts: Dict[str, int] = {}
    with system_scope("lifecycle: purge every row of a tenant"):
        for table in PURGE_ORDER:
            before = _fetch_all(
                f"SELECT count(*) AS n FROM {table} WHERE tenant_id = %s", (tenant,)
            )
            counts[table] = int(before[0]["n"]) if before else 0
            _execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant,))

        # Tài khoản: chỉ xoá người KHÔNG còn thuộc tổ chức nào khác.
        #
        # Một người có thể là thành viên của hai tổ chức. Xoá tài khoản của họ
        # vì một tổ chức đóng cửa là lấy mất quyền truy cập ở tổ chức kia — và
        # bản ghi thành viên bên đó vẫn còn, nên hệ thống sẽ có một thành viên
        # trỏ tới tài khoản không tồn tại.
        #
        # Câu dưới đây đúng NHỜ THỨ TỰ, và điều đó không hiển nhiên:
        # `memberships` nằm trong `PURGE_ORDER` nên mọi dòng thành viên CỦA
        # TENANT NÀY đã bị xoá ở vòng lặp bên trên. Vì thế `EXISTS (SELECT 1
        # FROM tenant_members WHERE user_id = u.id)` chỉ còn tìm thấy tư cách
        # thành viên ở NƠI KHÁC — đúng thứ cần hỏi. Chuyển câu này lên trước
        # vòng lặp sẽ khiến nó luôn đúng cho mọi người và không ai bị xoá.
        #
        # Hỏi qua VIEW `tenant_members` chứ không thẳng `memberships`, và có lý
        # do: view đã lọc `scope_level = 'TENANT'`. Hỏi thẳng bảng nền sẽ đếm cả
        # membership workspace/project, và một người chỉ còn dòng WORKSPACE mồ
        # côi sẽ được coi là "còn thuộc tổ chức khác" rồi thoát khỏi lượt xoá.
        survivors = _fetch_all(
            "SELECT u.id FROM users u WHERE u.tenant_id = %s AND EXISTS ("
            "  SELECT 1 FROM tenant_members m WHERE m.user_id = u.id"
            ")",
            (tenant,),
        )
        for row in survivors:
            # Chuyển nhà sang một tổ chức họ còn thuộc về. `LIMIT 1` là tuỳ ý
            # nhưng có định: người dùng đổi lại được, còn để họ không có nhà thì
            # không đăng nhập được để mà đổi.
            _execute(
                "UPDATE users SET tenant_id = ("
                "  SELECT m.tenant_id FROM tenant_members m WHERE m.user_id = %s LIMIT 1"
                ") WHERE id = %s",
                (str(row["id"]), str(row["id"])),
            )
        deleted_users = _fetch_all(
            "SELECT count(*) AS n FROM users WHERE tenant_id = %s", (tenant,)
        )
        counts["users"] = int(deleted_users[0]["n"]) if deleted_users else 0
        _execute("DELETE FROM users WHERE tenant_id = %s", (tenant,))
        _execute("DELETE FROM tenants WHERE tenant_id = %s", (tenant,))

    files_removed, bytes_removed = _remove_tenant_files(tenant)

    purge_id = str(uuid.uuid4())
    _record_purge(
        purge_id=purge_id, tenant=tenant,
        display_name=preview["display_name"],
        requested_by=str(requested_by) if requested_by else None,
        counts=counts, files_removed=files_removed,
        bytes_removed=bytes_removed, reason=reason.strip()[:1000],
    )

    logger.warning(
        "[PURGE] xoá vĩnh viễn %s: %d dòng, %d tệp, %d byte (bởi %s)",
        tenant, sum(counts.values()), files_removed, bytes_removed, requested_by,
    )
    return {
        "purge_id": purge_id, "tenant_id": tenant, "row_counts": counts,
        "files_removed": files_removed, "bytes_removed": bytes_removed,
    }


def _remove_tenant_files(tenant: str) -> tuple[int, int]:
    """Xoá thư mục dữ liệu của một tenant, trả về (số tệp, số byte).

    Tenant gốc dùng bố cục thư mục LỊCH SỬ nằm ngay tại gốc dataset, không nằm
    dưới `_tenants/`. Xoá nó sẽ cuốn theo dữ liệu của cả nền tảng. Hàm này từ
    chối thẳng thay vì tin vào việc người gọi đã kiểm — `purge_tenant` cũng
    kiểm, và hai lớp cho một thao tác không hoàn tác được là đúng mức.
    """
    from app.dataset_manager import tenant_features_root
    from app.tenancy import DEFAULT_TENANT_ID

    if tenant == DEFAULT_TENANT_ID:
        return (0, 0)

    try:
        root = tenant_features_root(tenant)
    except Exception as exc:
        logger.error("[PURGE] không giải được thư mục của %s: %s", tenant, exc)
        return (0, 0)

    if not root.exists():
        return (0, 0)

    count = total = 0
    for path in root.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
                count += 1
            except OSError:
                continue
    try:
        shutil.rmtree(root)
    except OSError as exc:
        logger.error("[PURGE] không xoá được %s: %s", root, exc)
        return (0, 0)
    return (count, total)
