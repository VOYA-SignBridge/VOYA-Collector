import psycopg2
from psycopg2.extras import Json, RealDictCursor
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Dict, List, NamedTuple, Optional
import logging
import re

from app.config import settings
from app.storage.postgres_connection import get_pooled_conn, put_pooled_conn
from app.storage.rls import apply_scope
from app.tenancy import DEFAULT_TENANT_ID, TENANT_COLUMN, optional_tenant_id

logger = logging.getLogger(__name__)


@contextmanager
def _cursor():
    # Borrow from the process-local pool instead of opening a fresh connection
    # per query (hot path: hundreds of insert/update during npz upload).
    conn = get_pooled_conn()
    broken = False
    try:
        with conn:  # commits on success, rolls back on exception
            with conn.cursor() as cur:
                # Bind the tenant scope as the transaction's first statement.
                # Pooled connections are shared, so this must be re-established
                # every transaction and must be transaction-scoped — see
                # storage/rls.py for why a plain SET would leak one tenant's
                # context into the next request to borrow this connection.
                apply_scope(cur)
                yield cur
    except Exception:
        # A rolled-back connection stays reusable; only discard if truly dead.
        broken = bool(getattr(conn, "closed", 0))
        raise
    finally:
        put_pooled_conn(conn, close=broken)


def _execute(sql: str, params: Dict[str, Any] | tuple | None = None) -> None:
    with _cursor() as cur:
        cur.execute(sql, params)


def _execute_many(sql: str, rows: List[tuple]) -> None:
    """Một câu, nhiều bộ tham số, MỘT lượt đi về cơ sở dữ liệu.

    Tồn tại cho các đường ghi theo lô (gộp số đo, sổ dấu vết): vòng lặp gọi
    `_execute` cho 500 dòng là 500 lượt khứ hồi, và trên một tác vụ nền chạy
    mỗi đêm thì đó là phút chứ không phải giây.

    Danh sách rỗng thì không mở con trỏ nào — người gọi không phải tự kiểm.
    """
    if not rows:
        return
    with _cursor() as cur:
        cur.executemany(sql, rows)


@contextmanager
def _migration_cursor():
    """Cursor authenticated as the DDL role, outside the shared pool.

    Schema changes must not run as the application role: `ALTER TABLE` is what
    disables row-level security, so an application role able to issue it could
    revoke its own tenant containment. `connect_migration()` resolves to
    MIGRATION_DATABASE_URL, or to DATABASE_URL when the roles have not been
    split yet — so this is a no-op change on a deployment that has not run
    `app.cli.provision_db_roles`.

    autocommit, deliberately: `ensure_tables()` relies on each statement
    standing alone, so that a CREATE that fails because the object already
    exists does not roll back the twenty statements before it. Inside one
    transaction the first error would poison the rest.
    """
    from app.storage.postgres_connection import connect_migration

    conn = connect_migration()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            _assert_expected_database(cur)
            yield cur
    finally:
        conn.close()


#: Biến môi trường chốt chặn: nếu đặt, cơ sở dữ liệu ĐANG NỐI TỚI phải trùng tên
#: với nó, không thì huỷ trước khi chạy bất kỳ câu DDL nào.
EXPECTED_DATABASE_ENV = "EXPECTED_DATABASE"


class WrongMigrationTarget(RuntimeError):
    """Kết nối tới cơ sở dữ liệu khác với cái người gọi tuyên bố."""


def _assert_expected_database(cur) -> None:
    """Xác minh ĐÍCH trước khi chạy DDL, và ghi lại đích đó vào nhật ký.

    Vì sao tồn tại
    --------------
    Ngày 12/08/2026, một lệnh kiểm chứng chạy `ensure_tables()` trên một
    container dùng-một-lần với `-e POSTGRES_DB=authz_v5`, với ý định dựng lược
    đồ v5 lên một BẢN SAO. Ứng dụng không dựng DSN từ `POSTGRES_DB` — nó phân
    giải `MIGRATION_DATABASE_URL`/`DATABASE_URL` — nên biến đó bị bỏ qua trong
    im lặng và lượt migration chạy thẳng lên `signdb` của SẢN XUẤT.

    Không mất dữ liệu, nhưng sản xuất rơi vào trạng thái lược-đồ-mới/mã-cũ mà
    không ai chọn. Điều biến một lỗi gõ thành một sự cố là ở chỗ **không có
    bước nào nói ra nó đang sắp ghi vào đâu**.

    Nên có hai lớp ở đây, và chúng khác nhau:

      * Dòng nhật ký chạy LUÔN LUÔN. Nó biến đích thành thứ đọc được sau này,
        kể cả khi không ai đặt biến chốt chặn. Sự cố trên sẽ hiện ra ngay ở
        dòng đầu tiên của log thay vì sau khi bảng đã bị bỏ.
      * `EXPECTED_DATABASE` là lớp CHẶN, và cố ý chỉ bật khi được yêu cầu:
        `ensure_tables()` chạy hợp lệ ở mỗi lần khởi động backend trên sản
        xuất, nên một chốt chặn luôn-bật sẽ chặn cả đường đi đúng. Ai chạy
        migration bằng tay thì đặt nó, và câu lệnh gây ra sự cố kia đã bị huỷ
        nếu có nó.

    Vì sao so bằng `current_database()` chứ không bằng chuỗi DSN: DSN có thể
    viết bằng nhiều dạng (tên máy, biến, tham số ẩn) và so chuỗi sẽ vừa bỏ sót
    vừa báo nhầm. `current_database()` là câu trả lời của chính máy chủ về nơi
    phiên này đang đứng — không diễn giải lại được.
    """
    import os

    cur.execute(
        "SELECT current_database(), current_user, "
        "inet_server_addr()::text, inet_server_port()"
    )
    database, user, host, port = cur.fetchone()

    expected = (os.getenv(EXPECTED_DATABASE_ENV) or "").strip()
    logger.warning(
        "[MIGRATION-TARGET] database=%s user=%s server=%s:%s expected=%s",
        database, user, host or "local", port, expected or "(khong dat)",
    )

    if expected and database != expected:
        raise WrongMigrationTarget(
            f"{EXPECTED_DATABASE_ENV}={expected!r} nhung dang noi toi {database!r}. "
            f"Khong chay DDL nao. Sua DSN (MIGRATION_DATABASE_URL/DATABASE_URL) "
            f"chu khong phai POSTGRES_DB — bien do KHONG duoc dung de dung DSN."
        )


class MigrationStepFailed(RuntimeError):
    """Một bước migration BẮT BUỘC không đạt. Migration phải dừng."""


def _run_data_step(cur, reason: str, statements: tuple[str, ...],
                   postcondition: str) -> None:
    """Chạy một bước ĐỊNH HÌNH DỮ LIỆU của migration, trong phạm vi hệ thống.

    Vì sao cần, và vì sao chỉ ĐÚNG những bước được đăng ký
    ------------------------------------------------------
    Đo ngày 15/08/2026 trên `signdb_test`, vai `voya_test_owner`
    (NOSUPERUSER, NOBYPASSRLS) — tức đúng mô hình quyền mà hệ thống khuyến nghị:

        UPDATE classes SET region='unclassified' WHERE region IS NULL
        -> UPDATE 0        (RLS chặn, KHÔNG ném lỗi)
        ALTER TABLE classes ALTER COLUMN region SET NOT NULL
        -> that bai        (còn NULL) — và `_run_ddl` NUỐT lỗi

    Cùng vai đó dưới `admin` (superuser, bypassrls): `UPDATE 63`. Nên migration
    lâu nay chỉ chạy đúng vì sản xuất dùng superuser — không phải vì hợp đồng
    migration hợp lệ.

    Sau khi `tenants` bật RLS, câu bootstrap tenant gốc còn hỏng theo một đường
    tinh hơn: RLS làm MÙ chính phép kiểm tồn tại đang bảo vệ nó.

        SELECT ... FROM tenants WHERE tenant_id='default'   -> 0 dòng (RLS)
        WHERE NOT EXISTS                                    -> hoá TRUE
        INSERT                                              -> WITH CHECK từ chối

    Trên bản cài mới với vai tối thiểu, tenant gốc sẽ không bao giờ ra đời.

    Vì sao đây KHÔNG phải vá biên giới bằng sentinel
    ------------------------------------------------
    `app.system_scope` tự đặt được bởi vai ứng dụng, và đó vẫn là giới hạn TCB
    **Mức II** (xem docs/TENANT_ISOLATION_AND_AUTHZ.md §4.1). Nhưng bộ thực thi
    migration vốn đã nằm trong mặt phẳng điều khiển tin cậy của **Mức I**, và
    thao tác ở đây thật sự là xuyên-tenant / trước-tenant. Ranh giới là:

        yêu cầu thông thường   KHÔNG được dùng system_scope chỉ vì khó phạm vi
        bootstrap / backfill   thao tác xuyên tenant thật -> hợp lệ, và phải
                               NÓI RA mình đang mở phạm vi để làm gì

    Ba tính chất bắt buộc
    ---------------------
    * **Theo GIAO DỊCH**, không theo phiên: `set_config(..., true)` chỉ sống
      trong giao dịch, nên không kết nối nào mang `system_scope='on'` sang bước
      kế tiếp. `_migration_cursor` chạy autocommit nên phải mở `BEGIN` tường
      minh — cũng chính là thứ làm cặp "định hình dữ liệu + ràng buộc" trở nên
      nguyên tử.
    * **Hậu điều kiện**, không phải rowcount. `UPDATE 0` hợp lệ khi dữ liệu vốn
      đã đúng, và sai khi RLS vừa nuốt mất phép ghi. Chỉ trạng thái CUỐI phân
      biệt được hai trường hợp đó.
    * **Hỏng thì DỪNG.** Đây là nơi `_run_ddl` nuốt lỗi phải chấm dứt: một bước
      định hình dữ liệu chạy hụt để lại lược đồ nửa vời mà mọi phép kiểm khác
      vẫn báo "khớp".

    Hậu điều kiện kiểm TRONG cùng phạm vi
    -------------------------------------
    Câu kiểm chạy TRƯỚC `COMMIT`, tức vẫn trong `system_scope`. Nếu thoát phạm
    vi rồi mới kiểm thì chính câu kiểm bị RLS làm mù và trả `count(*) = 0` cho
    một dòng vừa ghi xong — đúng cái bẫy `NOT EXISTS` mà bước này sinh ra để gỡ,
    chỉ khác là lần này nó làm migration đỏ oan thay vì xanh oan.
    """
    logger.warning("[MIGRATE][DATA] bat dau %s", reason)
    cur.execute("BEGIN")
    try:
        cur.execute("SELECT set_config('app.system_scope', 'on', true)")
        for stmt in statements:
            cur.execute(stmt)
        cur.execute(postcondition)
        dat = cur.fetchone()[0]
        if not dat:
            raise MigrationStepFailed(
                f"{reason}: hau dieu kien KHONG dat sau khi chay. "
                f"Kiem: {postcondition}")
        cur.execute("COMMIT")
    except Exception:
        try:
            cur.execute("ROLLBACK")
        except Exception:
            pass
        logger.error("[MIGRATE][DATA][THAT BAI] %s", reason)
        raise
    logger.warning("[MIGRATE][DATA] xong %s — hau dieu kien DAT", reason)


def _run_ddl(cur, statements, kind: str) -> None:
    """Execute schema statements, logging and continuing past failures.

    Hai ngoại lệ cho luật "ghi log rồi đi tiếp", cả hai đều thêm 15/08/2026:

      * câu nằm trong `MIGRATION_DATA_STEPS` -> đi qua `_run_data_step`
      * câu nằm trong `MIGRATION_MUST_SUCCEED` -> hỏng là DỪNG migration

    Việc nuốt lỗi vẫn đúng cho phần còn lại (`IF NOT EXISTS` chạy lại, khác biệt
    giữa các bản cài), nhưng nó KHÔNG đúng cho những câu mà trạng thái cuối phụ
    thuộc vào chúng.
    """
    so_dang_ky = _data_steps()
    theo_sau = _data_step_followers()
    for stmt in statements:
        buoc = so_dang_ky.get(stmt)
        if buoc is not None:
            _run_data_step(cur, *buoc)
            continue
        if stmt in theo_sau:
            continue  # đã chạy cùng câu dẫn đầu, trong phạm vi
        try:
            cur.execute(stmt)
        except Exception as exc:
            if stmt in MIGRATION_MUST_SUCCEED:
                logger.error("[MIGRATE][THAT BAI] cau BAT BUOC hong: %s : %s",
                             getattr(exc, "pgerror", str(exc)), stmt[:160])
                raise
            logger.warning(
                "ensure_tables: %s statement failed (ignored): %s : %s",
                kind, getattr(exc, "pgerror", str(exc)), stmt[:120],
            )


#: Ba câu dưới đây là HẰNG SỐ DÙNG CHUNG, không phải chuỗi gõ lại.
#:
#: Chúng xuất hiện ở HAI nơi — trong `MIGRATION_STATEMENTS` (để giữ đúng vị trí
#: thứ tự) và trong các sổ đăng ký bên dưới (để được xử lý đặc biệt). Sổ đăng ký
#: khớp theo NGUYÊN VĂN chuỗi, nên chép lại lần thứ hai là dựng sẵn một lỗi:
#: sửa một chỗ, chỗ kia lặng lẽ hết khớp, và bước ấy âm thầm quay về đường
#: "nuốt lỗi rồi đi tiếp".
_SQL_BACKFILL_CLASS_REGION = (
    "UPDATE classes SET region = 'unclassified' "
    "WHERE region IS NULL OR btrim(region) = ''"
)
_SQL_CLASS_REGION_NOT_NULL = "ALTER TABLE classes ALTER COLUMN region SET NOT NULL"
_SQL_BOOTSTRAP_DEFAULT_TENANT = (
    f"INSERT INTO tenants(tenant_id, display_name, slug) "
    f"SELECT '{DEFAULT_TENANT_ID}', 'VOYA', '{DEFAULT_TENANT_ID}' "
    f"WHERE NOT EXISTS (SELECT 1 FROM tenants WHERE tenant_id = '{DEFAULT_TENANT_ID}')"
)
_SQL_SEED_VOCAB_REGISTRY_META = (
    f"INSERT INTO vocabulary_registry_meta(tenant_id) VALUES('{DEFAULT_TENANT_ID}') "
    f"ON CONFLICT DO NOTHING"
)

#: C3 — `training_metrics` nhận chủ sở hữu TỪ HÀNG JOB CHA.
#:
#: Backfill này khác hẳn hai hiện vật vận hành mất chủ ở C2b, và khác đúng ở
#: điểm quyết định: ở đây có một QUAN HỆ CHA đã lưu và đáng tin —
#: `training_metrics.job_id → training_jobs.job_id` — nên chủ sở hữu được TRA
#: RA, không phải phỏng đoán. Có provenance thì có quyền backfill.
#:
#: Chỉ số nào không tra được job cha thì để nguyên NULL, và hậu điều kiện dưới
#: đây làm migration DỪNG. Không suy nó về `default`: một chỉ số mồ côi là dấu
#: hiệu dữ liệu hỏng, và gán bừa một tổ chức cho nó là biến một lỗi thấy được
#: thành một lỗi im lặng.
_SQL_BACKFILL_METRIC_TENANT = (
    "UPDATE training_metrics m SET tenant_id = j.tenant_id "
    "FROM training_jobs j WHERE m.job_id = j.job_id AND m.tenant_id IS NULL"
)
_SQL_METRIC_TENANT_NOT_NULL = (
    "ALTER TABLE training_metrics ALTER COLUMN tenant_id SET NOT NULL"
)

#: Bước ĐỊNH HÌNH DỮ LIỆU: chạy trong phạm vi hệ thống theo giao dịch, và phải
#: chứng minh HẬU ĐIỀU KIỆN. Xem `_run_data_step` về vì sao rowcount không đủ.
#:
#: Khoá là câu DẪN ĐẦU; giá trị là `(lý do, các câu, hậu điều kiện)`. Một bước
#: được phép gồm NHIỀU câu vì có ý định không diễn đạt nổi bằng một câu — bước
#: cộng đồng là "gieo nếu chưa có, SỬA nếu có mà sai loại", và tách đôi thì mỗi
#: nửa tự nhận là đã xong trong khi trạng thái đích chưa đạt.
#:
#: `reason` phải nêu đích danh phiên bản và bước — không dùng `"migration"` trơn,
#: vì sổ kiểm toán sau này cần trả lời được "phạm vi được mở để làm gì".
MIGRATION_DATA_STEPS: dict[str, tuple[str, tuple[str, ...], str]] = {
    _SQL_BOOTSTRAP_DEFAULT_TENANT: (
        "migration:v5:bootstrap-default-tenant",
        (_SQL_BOOTSTRAP_DEFAULT_TENANT,),
        f"SELECT count(*) = 1 FROM tenants WHERE tenant_id = '{DEFAULT_TENANT_ID}'",
    ),
    _SQL_BACKFILL_CLASS_REGION: (
        "migration:v5:backfill-class-region",
        (_SQL_BACKFILL_CLASS_REGION,),
        "SELECT count(*) = 0 FROM classes WHERE region IS NULL",
    ),
    # NỢ KIẾN TRÚC — bước tương thích/khởi tạo, KHÔNG phải nơi canonical.
    #
    # Quyền sở hữu dài hạn của dòng này thuộc về đường khởi tạo registry chạy
    # DƯỚI phạm vi tenant (`vocabulary_registry._bump()` tự chèn khi thiếu, và
    # `clone_catalog_to_tenant` chèn cho tenant mới) — cả hai đều đã tự lo được
    # và tự lo ĐÚNG, vì chúng có tenant context. Migration là chỗ duy nhất không
    # có, nên là chỗ duy nhất hỏng.
    #
    # Ghi ra đây để người đọc sổ đăng ký sau này đừng kết luận ngược: nhìn thấy
    # nó ở đây KHÔNG có nghĩa migration là nơi phải gieo registry meta.
    _SQL_SEED_VOCAB_REGISTRY_META: (
        "migration:v5:seed-vocabulary-registry-meta",
        (_SQL_SEED_VOCAB_REGISTRY_META,),
        f"SELECT count(*) = 1 FROM vocabulary_registry_meta "
        f"WHERE tenant_id = '{DEFAULT_TENANT_ID}'",
    ),
    # Hậu điều kiện có HAI vế, và vế thứ hai mới là vế bảo mật:
    #
    #   1. không còn chỉ số nào thiếu tenant  -> backfill đã phủ hết
    #   2. không chỉ số nào LỆCH tenant cha   -> backfill lấy đúng nguồn
    #
    # Chỉ kiểm vế một thì một bản vá sai — ví dụ gán tất cả về `default` — vẫn
    # đạt hậu điều kiện. Vế hai là thứ phân biệt "đã điền" với "điền ĐÚNG".
    _SQL_BACKFILL_METRIC_TENANT: (
        "migration:v5:backfill-training-metric-tenant-from-parent-job",
        (_SQL_BACKFILL_METRIC_TENANT,),
        "SELECT count(*) = 0 FROM training_metrics m "
        "LEFT JOIN training_jobs j ON j.job_id = m.job_id "
        "WHERE m.tenant_id IS NULL OR j.job_id IS NULL "
        "   OR m.tenant_id IS DISTINCT FROM j.tenant_id",
    ),
}


@lru_cache(maxsize=1)
def _data_steps() -> dict[str, tuple[str, tuple[str, ...], str]]:
    """Sổ đăng ký GỘP, gồm cả bước do mặt phẳng phân quyền sở hữu.

    Nhập trễ: `authz_schema` được nạp sau tệp này, và bước cộng đồng phải sống
    cạnh câu SQL nó chạy chứ không phải bị chép sang đây — chép là dựng sẵn cái
    lệch mà `_SQL_*` ở trên sinh ra để tránh.
    """
    from app.storage.authz_schema import AUTHZ_DATA_STEPS

    return {**MIGRATION_DATA_STEPS, **AUTHZ_DATA_STEPS}


@lru_cache(maxsize=1)
def _data_step_followers() -> frozenset[str]:
    """Câu THEO SAU trong một bước nhiều câu — đã chạy cùng câu dẫn đầu.

    Không có tập này thì câu sửa chữa của bước cộng đồng sẽ chạy lần thứ hai,
    lần đó NGOÀI phạm vi, và lại lặng lẽ `UPDATE 0`.
    """
    return frozenset(
        stmt
        for _, cac_cau, _ in _data_steps().values()
        for stmt in cac_cau[1:]
    )

#: Câu mà trạng thái cuối phụ thuộc vào: hỏng là DỪNG migration, không ghi log
#: rồi đi tiếp. `SET NOT NULL` ở đây vì nó là nửa sau của cặp backfill→ràng
#: buộc; nếu nó hụt thì cột vẫn nhận NULL và vòng lặp tự nuôi mình quay lại.
MIGRATION_MUST_SUCCEED: frozenset[str] = frozenset({
    _SQL_CLASS_REGION_NOT_NULL,
    # C3 — nuốt lỗi ở đây là để lại một cột `tenant_id` NULLABLE trên bảng vừa
    # được bật RLS. Vị từ policy so `tenant_id = current_setting(...)`, và
    # `NULL = 'iso_a'` cho ra NULL chứ không phải FALSE — hàng đó vô hình với
    # mọi tenant, kể cả chủ của nó. Một lỗi im lặng biến thành mất dữ liệu.
    _SQL_METRIC_TENANT_NOT_NULL,
})


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _int_or_none(value: Any) -> int | None:
    text = str(value).strip() if value is not None else ""
    try:
        return int(text) if text else None
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    text = str(value).strip() if value is not None else ""
    try:
        return float(text) if text else None
    except (TypeError, ValueError):
        return None


def _ts_or_none(value: Any) -> Any:
    """Empty string -> NULL for timestamp columns (CSV mirror leaves them blank,
    which Postgres rejects as 'invalid input syntax for type timestamp')."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


#: Bỏ bảng `dialects` đời tiền-registry. MỘT CHIỀU: xem `ONE_WAY_STATEMENTS`.
_DROP_PRE_REGISTRY_DIALECTS = """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'dialects' AND column_name = 'code'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'dialects' AND column_name = 'dialect_id'
        ) THEN
            DROP TABLE dialects;
            RAISE NOTICE 'dropped legacy dialects table (pre-registry schema)';
        END IF;
    END $$;
    """


#: Bỏ bảng `user_profiles` đã chết, chỉ khi nó RỖNG. MỘT CHIỀU.
#: Bỏ DEFAULT của `training_jobs.tenant_id` — giữ NOT NULL. MỘT CHIỀU.
#:
#: Cùng khuôn với `_DROP_USERS_TENANT_DEFAULT` (xem chú thích ở đó cho lý do
#: đầy đủ). Ở đây hậu quả nặng hơn một bậc: một job lập hồ sơ thiếu tenant
#: không chỉ thuộc nhầm tổ chức, mà kéo theo MỌI thứ móc vào nó — hợp đồng lớp
#: đầu ra, hiện vật, sự kiện webhook.
#:
#:     CreateTrainingJob(thiếu tenant)  ->  PostgreSQL gán 'default'   (trước)
#:     CreateTrainingJob(thiếu tenant)  ->  TỪ CHỐI                    (sau)
#:
#: KHÔNG di chuyển job hiện hữu: job đang mang `default` vẫn thuộc `default`.
#: Câu này chỉ chặn việc tạo THÊM một job thuộc tenant khởi tạo do sơ suất.
_DROP_TRAINING_JOBS_TENANT_DEFAULT = """
    ALTER TABLE training_jobs ALTER COLUMN tenant_id DROP DEFAULT
    """

#: Bỏ DEFAULT của `users.tenant_id` — giữ NOT NULL. MỘT CHIỀU.
#:
#: Vì sao
#: ------
#: Cột đang là `NOT NULL DEFAULT 'default'`. Nghĩa là một lượt `INSERT INTO
#: users` quên `tenant_id` KHÔNG hỏng — PostgreSQL lặng lẽ gán tenant khởi tạo,
#: và một lỗi thiếu phạm vi biến thành một tư cách thành viên CÓ THẬT.
#:
#:     INSERT user thiếu tenant_id  ->  PostgreSQL gán 'default'  ->  membership
#:
#: Sau câu này, cùng lượt INSERT ấy sẽ NỔ. Đó là điểm khác biệt cốt lõi:
#:
#:     bootstrap TƯỜNG MINH tới default   hợp lệ
#:     fallback NGẦM tới default          cấm
#:
#: KHÔNG chuyển một hàng nào. Tài khoản đang mang `tenant_id='default'` vẫn
#: thuộc `default`; câu này chỉ loại bỏ khả năng tạo THÊM một tư cách thành viên
#: default một cách vô tình.
#:
#: Cột vẫn NOT NULL. Không biến thành nullable — "không có tenant" không phải
#: một trạng thái hợp lệ để lưu, nó là một lỗi cần chặn lúc ghi.
_DROP_USERS_TENANT_DEFAULT = """
    ALTER TABLE users ALTER COLUMN tenant_id DROP DEFAULT
    """

_DROP_DEAD_USER_PROFILES = """
    DO $$
    DECLARE n bigint;
    BEGIN
        IF to_regclass('public.user_profiles') IS NOT NULL THEN
            EXECUTE 'SELECT count(*) FROM user_profiles' INTO n;
            IF n = 0 THEN
                DROP TABLE user_profiles;
            END IF;
        END IF;
    END $$
    """


#: Hai chỉ mục DUY NHẤT ở phạm vi TOÀN CỤC, bị thay bằng bản theo tenant. Bỏ
#: chúng là một chiều: dựng lại được, nhưng chỉ khi dữ liệu còn thoả — mà sau
#: khi hai tenant cùng có một `class_idx` thì nó không còn thoả nữa.
_DROP_GLOBAL_CLASS_UNIQUES: tuple[str, ...] = (
    "DROP INDEX IF EXISTS uq_classes_slug_lang_dialect",
    "DROP INDEX IF EXISTS uq_classes_class_idx",
)


#: Chỉ mục duy nhất KHÔNG có `region`, bị thay bằng bản có. Bỏ là một chiều:
#: dựng lại được, nhưng chỉ khi dữ liệu còn thoả — mà sau khi ba biến thể miền
#: của cùng một từ cùng tồn tại thì nó không còn thoả nữa.
_DROP_PRE_REGION_CLASS_UNIQUE: tuple[str, ...] = (
    "DROP INDEX IF EXISTS uq_classes_tenant_slug_lang_dialect",
)


#: Bản `coalesce(region,'')` của chỉ mục duy nhất, dựng khi `region` còn nhận
#: NULL. v3.19 đặt cột thành NOT NULL nên `coalesce` hết việc — nhưng phải BỎ
#: bản cũ trước, vì `CREATE UNIQUE INDEX IF NOT EXISTS` KHÔNG thay thế một chỉ
#: mục cùng tên có định nghĩa khác: nó lặng lẽ không làm gì. Bỏ sót bước này
#: thì máy đã chạy giữ bản `coalesce`, máy dựng mới có bản trần, và hai lược đồ
#: trôi khỏi nhau mà không ai báo.
_DROP_COALESCE_REGION_UNIQUE: tuple[str, ...] = (
    "DROP INDEX IF EXISTS uq_classes_tenant_slug_lang_dialect_region",
)


#: Lược đồ v6 — mô hình gói `free / plus / pro / enterprise`.
#:
#: Xem `docs/07-business/BILLING_MODEL_V6.md`. Bước MỘT của kế hoạch, và nó cố ý **không
#: đụng tới một giá trị hạn mức nào đang có hiệu lực**: chỉ đổi mã gói, thêm
#: cột cho các hạn mức của mô hình mới, và gỡ khái niệm dùng thử.
#:
#: Vì sao hạn mức không đổi ở đây
#: -------------------------------
#: Bảng gói mới nói "sample không giới hạn, chặn bằng dung lượng". Đặt
#: `max_samples = NULL` ngay bây giờ sẽ gỡ trần ghi DUY NHẤT đang có, trong khi
#: cổng dung lượng thay thế nó phải tới v7 mới tồn tại — tức là một cửa sổ
#: triển khai mà gói Free không có trần nào cả. Nên v6 giữ nguyên các con số
#: hiện hành dưới tên mới, và v7 lật chúng CÙNG LÚC với `enforce` dung lượng.
#: Các cột mới bên dưới mang sẵn giá trị đích vì chưa có ai đọc chúng.
#:
#: Vì sao đổi tên chứ không tạo mới rồi xoá
#: -----------------------------------------
#: `tenants.plan_code` và `tenant_subscriptions.plan_code` đều có khoá ngoại
#: `ON UPDATE CASCADE` trỏ vào `plans.plan_code`, nên một câu `UPDATE` lan sang
#: cả lịch sử đăng ký. Đường ngược lại — chèn gói mới rồi `DELETE` gói cũ — bị
#: `ON DELETE RESTRICT` chặn đúng ở những dòng lịch sử đó.
#:
#: Đổi mã bốn gói cũ sang bốn gói của v6, CHỊU ĐƯỢC trạng thái lẫn.
#:
#: Bản đầu là bốn câu `UPDATE plans SET plan_code = ...`, và nó vỡ ở đúng một
#: trạng thái có thật: khi cả mã cũ lẫn mã mới cùng tồn tại. Lúc đó câu đổi tên
#: đụng khoá chính và cả lượt migration dừng. Trạng thái đó không phải giả
#: thuyết — nó đã xuất hiện trên cơ sở dữ liệu phát triển của máy này ngày
#: 13/08/2026, khi câu seed (chèn bốn mã MỚI) và câu đổi tên (đổi bốn mã CŨ)
#: chạy trong hai lượt khác nhau, xen kẽ nhau.
#:
#: Nên nó phải là hợp nhất chứ không phải đổi tên: mã mới đã có thì chuyển mọi
#: tham chiếu sang đó rồi bỏ mã cũ; chưa có thì đổi tên như cũ (rẻ hơn, và
#: `ON UPDATE CASCADE` tự lo phần tham chiếu).
#:
#: `to_regclass` chứ không giả định bảng tồn tại: trên một cơ sở dữ liệu trắng,
#: khối này chạy TRƯỚC khi `tenants` và `tenant_subscriptions` ra đời.
#:
#: DO $$ được `startup_ddl_policy` xếp vào nhóm an toàn theo HÌNH DẠNG, nên câu
#: này phải được đăng ký tay ở `one_way_statements()` — nó chuyển dữ liệu, và
#: một lượt `docker compose up` không được phép làm việc đó.
_BILLING_V6_RENAME_PLANS = """
DO $$
DECLARE
    pair RECORD;
BEGIN
    FOR pair IN
        SELECT * FROM (VALUES
            ('internal',    'enterprise'),
            ('trial',       'free'),
            ('school',      'plus'),
            ('institution', 'pro')
        ) AS t(old_code, new_code)
    LOOP
        IF NOT EXISTS (SELECT 1 FROM plans WHERE plan_code = pair.old_code) THEN
            CONTINUE;
        END IF;

        IF EXISTS (SELECT 1 FROM plans WHERE plan_code = pair.new_code) THEN
            IF to_regclass('public.tenants') IS NOT NULL THEN
                UPDATE tenants SET plan_code = pair.new_code
                 WHERE plan_code = pair.old_code;
            END IF;
            IF to_regclass('public.tenant_subscriptions') IS NOT NULL THEN
                UPDATE tenant_subscriptions SET plan_code = pair.new_code
                 WHERE plan_code = pair.old_code;
            END IF;
            DELETE FROM plans WHERE plan_code = pair.old_code;
        ELSE
            UPDATE plans SET plan_code = pair.new_code
             WHERE plan_code = pair.old_code;
        END IF;
    END LOOP;
END $$
"""


#: Câu nào ở đây chạy lúc khởi động, câu nào không, là việc của
#: `startup_ddl_policy` chứ không của cái tên biến này: mọi `UPDATE ... SET`
#: bên dưới bị xếp vào nhóm chỉ-migration (và vì thế nằm trong checksum), còn
#: bốn câu `DROP NOT NULL` là nới lỏng ràng buộc — không hỏng được vì dữ liệu
#: đang có — nên chúng chạy cả lúc khởi động.
#:
#: Khối chia làm HAI vì thứ tự trong `MIGRATION_STATEMENTS` là thứ tự thật:
#: phần `plans` phải chạy TRƯỚC câu seed gói (ngược lại thì trên cơ sở dữ liệu
#: đã có, seed chèn `free` xong rồi câu đổi tên `trial -> free` đụng khoá
#: chính), còn phần `tenants` phải chạy SAU khi bảng `tenants`,
#: `tenant_subscriptions` và các cột của chúng đã tồn tại — trên một cơ sở dữ
#: liệu trắng, chúng chưa có ở thời điểm khối `plans` chạy.
_BILLING_V6_PLANS: tuple[str, ...] = (
    # NULL phải diễn đạt được "không giới hạn" ở mọi trần, không chỉ ở bốn trần
    # đã nullable từ v4. Enterprise là gói custom: mọi trần của nó là NULL.
    "ALTER TABLE plans ALTER COLUMN max_concurrent_training_jobs DROP NOT NULL",
    "ALTER TABLE plans ALTER COLUMN max_queued_training_jobs DROP NOT NULL",
    "ALTER TABLE plans ALTER COLUMN max_api_keys DROP NOT NULL",
    "ALTER TABLE plans ALTER COLUMN max_webhook_endpoints DROP NOT NULL",
    # Giá: NULL nghĩa là CHƯA CÔNG BỐ, khác hẳn 0 nghĩa là miễn phí. Không có
    # phân biệt này thì bảng giá công khai in "Miễn phí" cho Plus và Pro.
    "ALTER TABLE plans ALTER COLUMN price_cents DROP NOT NULL",
    # Bốn cặp đổi tên. `internal` thành `enterprise` vì hạn mức của nó vốn đã
    # NULL toàn phần — đúng nghĩa "custom" — và vì sau lượt này phải KHÔNG còn
    # gói nào tên `internal`: tenant nền tảng được nhận diện bằng
    # `tenants.billing_exempt`, không bằng một gói giả.
    _BILLING_V6_RENAME_PLANS,
    # Tên hiển thị là tên thương hiệu, cùng một chuỗi ở mọi ngôn ngữ. Phần mô
    # tả để RỖNG có chủ ý: giao diện dựng nó từ `plan_code` qua i18n, nên một
    # câu tiếng Việt nằm trong cơ sở dữ liệu sẽ là chuỗi duy nhất không bao giờ
    # dịch được. Gói do người vận hành tự tạo vẫn dùng được cột này.
    "UPDATE plans SET display_name = initcap(plan_code), description = '' "
    "WHERE plan_code IN ('free', 'plus', 'pro', 'enterprise')",
    # Giá thương mại chưa chốt. Free là 0 thật; ba gói còn lại về NULL.
    "UPDATE plans SET price_cents = 0 WHERE plan_code = 'free'",
    "UPDATE plans SET price_cents = NULL "
    "WHERE plan_code IN ('plus', 'pro', 'enterprise')",
    # Enterprise: mọi trần là NULL.
    "UPDATE plans SET max_concurrent_training_jobs = NULL, "
    "max_queued_training_jobs = NULL, max_api_keys = NULL, "
    "max_webhook_endpoints = NULL WHERE plan_code = 'enterprise'",
    # Hạn mức của mô hình mới. Chưa có cổng nào đọc chúng — v7 mới cưỡng chế —
    # nên đặt thẳng giá trị đích ở đây là an toàn, và nó làm cái đích nhìn thấy
    # được thay vì nằm trong một tài liệu.
    "UPDATE plans SET max_workspaces = 1, max_projects = 5, "
    "included_training_credits = 60, audit_retention_days = 7 "
    "WHERE plan_code = 'free'",
    "UPDATE plans SET max_workspaces = 5, max_projects = 25, "
    "included_training_credits = 250, audit_retention_days = 30 "
    "WHERE plan_code = 'plus'",
    "UPDATE plans SET max_workspaces = 20, max_projects = 100, "
    "included_training_credits = 1000, audit_retention_days = 180 "
    "WHERE plan_code = 'pro'",
    "UPDATE plans SET max_workspaces = NULL, max_projects = NULL, "
    "included_training_credits = NULL, audit_retention_days = NULL "
    "WHERE plan_code = 'enterprise'",
    # Sắp xếp lại bảng giá theo bậc.
    "UPDATE plans SET sort_order = 10, is_self_serve = TRUE, is_listed = TRUE "
    "WHERE plan_code = 'free'",
    "UPDATE plans SET sort_order = 20, is_self_serve = FALSE, is_listed = TRUE "
    "WHERE plan_code = 'plus'",
    "UPDATE plans SET sort_order = 30, is_self_serve = FALSE, is_listed = TRUE "
    "WHERE plan_code = 'pro'",
    "UPDATE plans SET sort_order = 40, is_self_serve = FALSE, is_listed = TRUE "
    "WHERE plan_code = 'enterprise'",
    # Free là gói VĨNH VIỄN, nên không gói nào còn thời gian dùng thử. Đây là
    # chỗ khái niệm "trial" chấm dứt: `plans.trial_days` là thứ duy nhất từng
    # sinh ra `trial_ends_at`.
    "UPDATE plans SET trial_days = 0",
)


#: Phần v6 chạm tới `tenants` và `tenant_subscriptions`. Chạy SAU khi hai bảng
#: đó và các cột của chúng đã được tạo — xem chú thích ở `_BILLING_V6_PLANS`.
_BILLING_V6_TENANTS: tuple[str, ...] = (
    # Tổ chức đang ở `trialing` chuyển thẳng sang `active`. Không còn gói nào
    # có thời gian dùng thử thì `trialing` là trạng thái không ai thoát ra
    # được: lượt quét vòng đời chỉ rời khỏi nó khi một kỳ hết hạn, mà gói Free
    # không có kỳ nào.
    "UPDATE tenants SET billing_status = 'active', trial_ends_at = NULL "
    "WHERE billing_status = 'trialing'",
    "UPDATE tenants SET trial_ends_at = NULL WHERE trial_ends_at IS NOT NULL",
    "UPDATE tenant_subscriptions SET trial_ends_at = NULL "
    "WHERE trial_ends_at IS NOT NULL",
    # Tenant nền tảng: miễn trừ bằng thuộc tính, không bằng một gói riêng.
    #
    # Một chiều chứ không chạy lúc khởi động: nếu người vận hành cố ý bỏ cờ này
    # đi, một lượt `docker compose up` không được phép bật lại nó.
    f"UPDATE tenants SET billing_exempt = TRUE "
    f"WHERE tenant_id = '{DEFAULT_TENANT_ID}'",
    # Mặc định mới. Vẫn là gói CHẶT NHẤT trong bốn gói, nên một đường chèn quên
    # nêu gói vẫn sai theo hướng chặn — cùng lý do như khi mặc định là `trial`.
    "ALTER TABLE tenants ALTER COLUMN plan_code SET DEFAULT 'free'",
)


DDL_STATEMENTS = [
    # MUST stay first. An older schema shipped a `dialects` table shaped
    # (code PK, language_code FK->languages, name), and `CREATE TABLE IF NOT
    # EXISTS dialects` further down then did NOTHING on such a machine — the
    # vocabulary registry silently never installed, and every INSERT into it
    # failed with 'column "tenant_id" does not exist'. Observed on the dev
    # database 2026-08-01; the deploy machine would have hit the same wall.
    #
    # Dropping is safe and was verified before writing this:
    #   - no foreign key anywhere REFERENCES dialects (only its own outbound
    #     FK to languages, which goes away with the table);
    #   - no code in the repo reads code/name/language_code — every query uses
    #     dialect_id/display_name/tenant_id;
    #   - the SOT publisher exports classes/samples/raw_uploads only;
    #   - all 8 legacy rows are reproduced byte-for-byte by
    #     config/dialects.seed.csv (Chung, Miền Bắc, Hòa Đê, Bảng chữ cái, …).
    #
    # The guard makes this a no-op once migrated, and — critically — it must
    # run BEFORE the CREATE below: putting it in MIGRATION_STATEMENTS would
    # drop the table only after the CREATE had already no-opped, leaving the
    # machine with no dialects table at all until the next start.
    #
    # Vị trí "phải đứng đầu" chính là lý do câu này được TÁCH RA làm hằng số
    # thay vì chuyển sang một danh sách migration riêng: nó một chiều, nhưng nó
    # cũng phải chạy trước `CREATE TABLE dialects` ngay bên dưới. Giữ nó đúng
    # chỗ và lọc theo `ONE_WAY_STATEMENTS` bảo toàn cả hai tính chất.
    _DROP_PRE_REGISTRY_DIALECTS,
    # -----------------------------------------------------------------------
    # `languages` và `roles` — hai bảng CHỈ tồn tại trên máy đang chạy, không
    # có định nghĩa nào trong mã cho tới 2026-08-10.
    #
    # Chúng có mặt ở `signdb` sản xuất (2 và 3 dòng) vì được dựng tay từ đời
    # lược đồ cũ, và bản dump ở `backup.sql` mang chúng theo — nhưng
    # `ensure_tables()` thì không. Hệ quả đo được: một máy dựng MỚI ra 42 bảng
    # thay vì 44, và bốn khoá ngoại trong `INTEGRITY_FK_SPECS` trỏ tới
    # `languages(code)` **không tạo được**.
    #
    # Chúng không chết ồn ào. Vòng lặp áp khoá ngoại ở `MIGRATION_STATEMENTS`
    # chỉ bảo vệ bảng ĐANG SỬA (`to_regclass(parts[1])`), không kiểm bảng ĐƯỢC
    # THAM CHIẾU, nên `ALTER TABLE classes ADD CONSTRAINT … REFERENCES
    # languages(code)` ném "relation languages does not exist" rồi bị chính
    # `EXCEPTION WHEN others` hạ xuống WARNING. Máy khởi động bình thường, khoẻ
    # mạnh, và thiếu bốn ràng buộc toàn vẹn.
    #
    # Phát hiện khi lần đầu chạy bộ test trên một CSDL TRỐNG (cho CI): 22 test
    # đỏ, 4 tệp trong đó là test lược đồ. Trên bản sao của sản xuất chúng luôn
    # xanh, vì ở đó món nợ này đã được trả bằng tay từ trước.
    #
    # Đặt TRƯỚC `users` và mọi bảng corpus: khoá ngoại chỉ tạo được khi bảng
    # được tham chiếu đã có.
    """
    CREATE TABLE IF NOT EXISTS languages (
        code VARCHAR(50) PRIMARY KEY,
        name TEXT NOT NULL
    )
    """,
    # Hạt giống khớp đúng dữ liệu đang chạy. `ON CONFLICT DO NOTHING` chứ không
    # `DO UPDATE`: đây là danh mục người vận hành sửa được, và một lần khởi động
    # lại không được phép ghi đè lên chỉnh sửa của họ.
    """
    INSERT INTO languages (code, name) VALUES ('vn', 'Tiếng Việt'), ('en', 'English')
    ON CONFLICT DO NOTHING
    """,
    """
    CREATE TABLE IF NOT EXISTS roles (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(50) NOT NULL UNIQUE,
        description TEXT DEFAULT ''
    )
    """,
    # `roles` chưa có mã nào đọc — phân quyền hiện chạy bằng `users.is_admin` và
    # `tenant_members.role`. Dựng nó ở đây KHÔNG phải để bật thêm tính năng, mà
    # để một máy mới có cùng hình dạng lược đồ với máy đang chạy; lệch hình dạng
    # là thứ làm `verify_deployment` báo nợ và làm bộ test lược đồ đỏ.
    # `WHERE NOT EXISTS` chứ KHÔNG `ON CONFLICT DO NOTHING`, và đây là một lỗi
    # đã trả giá trên sản xuất chứ không phải sở thích.
    #
    # Bản cũ dựa vào ràng buộc `name VARCHAR(50) NOT NULL UNIQUE` ở câu CREATE
    # ngay trên: không có nó thì `ON CONFLICT` không có gì để bám, và câu lệnh
    # chèn thêm ba dòng MỖI LẦN `ensure_tables()` chạy.
    #
    # PDM v1.0 đã BỎ ràng buộc unique đó (xem `authz_schema`: tên role thuộc
    # không gian tên của tenant, không phải của nền tảng), nên câu này lặng lẽ
    # trở thành một vòi rò. Đo được trên sản xuất ngày 11/08: 21 dòng rác sau
    # bảy lượt khởi động — bốn worker gunicorn cùng gọi `ensure_tables()` nên
    # nó tăng ba dòng mỗi lượt, mỗi worker.
    #
    # Không có hậu quả về quyền (các dòng đó không có `role_permissions` nào
    # nên không chiếu vào Casbin), nhưng nó tăng vô hạn và làm bảng `roles`
    # không đọc được bằng mắt. `authz_schema` dọn phần đã tích luỹ.
    # Câu chèn ba role hạt giống ('admin', 'contributor', 'guest') từng ở đây đã
    # được GỠ BỎ ở PDM v5, không phải sửa.
    #
    # Nó thuộc về thời `roles` chưa có mã nào đọc. Từ v5, bảng đó là nguồn sự
    # thật của phân quyền và `app.authorization.seed` sở hữu nó: seed đối chiếu
    # 13 role dựng sẵn theo `role_code`, thêm cái thiếu và gỡ quyền thừa. Hai
    # nơi cùng ghi vào một bảng là cách chắc chắn để chúng lệch nhau.
    #
    # Nó cũng KHÔNG CÒN CHẠY ĐƯỢC: v5 đổi tên cột `name` → `role_code`, nên câu
    # này chỉ còn sinh ra một dòng WARNING ở mỗi lượt khởi động của mỗi worker.
    # Trên năm service dùng chung ảnh này, đó là tiếng ồn vĩnh viễn về một tình
    # trạng hoàn toàn bình thường — và cái giá thật của nó không phải dung lượng
    # log mà là dạy người vận hành bỏ qua cảnh báo của `ensure_tables`.
    #
    # Ba dòng đã tích luỹ trên máy đang chạy được `authz_schema` nhận nuôi
    # (`is_builtin = TRUE, is_active = FALSE`) chứ không xoá, vì `users.role_id`
    # còn trỏ vào chúng.
    """
    CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        is_admin BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS classes (
        class_uid TEXT PRIMARY KEY,
        class_idx INTEGER,
        slug TEXT,
        label_original TEXT,
        language TEXT,
        dialect TEXT,
        is_common_global BOOLEAN,
        is_common_language BOOLEAN,
        folder_name TEXT,
        created_at TIMESTAMP WITH TIME ZONE,
        migrated_at TIMESTAMP WITH TIME ZONE,
        deleted_at TIMESTAMP WITH TIME ZONE,
        hands_required INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS samples (
        sample_uid TEXT PRIMARY KEY,
        class_uid TEXT,
        slug TEXT,
        label_original TEXT,
        language TEXT,
        dialect TEXT,
        source_type TEXT,
        user_id TEXT,
        auth_user_id UUID,
        session_id TEXT,
        fps_original TEXT,
        fps_processed TEXT,
        seq_len INTEGER,
        augment_id INTEGER,
        completeness REAL,
        file_path TEXT,
        storage_url TEXT,
        checksum TEXT,
        created_at TIMESTAMP WITH TIME ZONE,
        -- DEFAULT TRUE, không phải FALSE. Cột này được khai hai lần với hai
        -- giá trị mặc định TRÁI NGƯỢC nhau: ở đây, và ở MIGRATION_STATEMENTS
        -- ("ALTER TABLE samples ADD COLUMN IF NOT EXISTS gdrive_synced BOOLEAN
        -- DEFAULT TRUE"). Bên nào thắng phụ thuộc vào việc CSDL đã có sẵn hay
        -- dựng mới: máy đã chạy nhận cột qua ALTER nên là TRUE, máy dựng mới
        -- nhận qua CREATE nên là FALSE và câu ALTER thành no-op.
        --
        -- TRUE là giá trị đúng, theo ba nguồn độc lập: máy sản xuất đang là
        -- TRUE; _normalise_sample_payload tự điền True khi thiếu; và vòng đồng
        -- bộ Sheets lọc gdrive_synced = TRUE, nên mặc định FALSE làm mọi mẫu
        -- mới vô hình với nó.
        --
        -- Chú thích ở đây phải là "--", KHÔNG phải "#": đây là thân một chuỗi
        -- SQL, và "#" làm cả câu CREATE TABLE sai cú pháp — bảng không được tạo
        -- và triệu chứng hiện ra rất xa nguồn ("relation samples does not
        -- exist" ở một test khác hẳn).
        gdrive_synced BOOLEAN DEFAULT TRUE,
        deleted_at TIMESTAMP WITH TIME ZONE,
        left_hand_ratio REAL,
        right_hand_ratio REAL,
        both_hands_ratio REAL,
        jitter REAL,
        quality_flags TEXT,
        FOREIGN KEY (auth_user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_uploads (
        upload_uid TEXT PRIMARY KEY,
        class_uid TEXT,
        slug TEXT,
        label_original TEXT,
        language TEXT,
        dialect TEXT,
        source_type TEXT,
        user_id TEXT,
        auth_user_id UUID,
        session_id TEXT,
        original_filename TEXT,
        local_path TEXT,
        storage_key TEXT,
        storage_url TEXT,
        created_at TIMESTAMP WITH TIME ZONE,
        updated_at TIMESTAMP WITH TIME ZONE,
        deleted_at TIMESTAMP WITH TIME ZONE,
        FOREIGN KEY (auth_user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS training_jobs (
        job_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        model_type TEXT,
        config JSONB,
        auth_user_id UUID,
        created_at TIMESTAMP WITH TIME ZONE,
        started_at TIMESTAMP WITH TIME ZONE,
        completed_at TIMESTAMP WITH TIME ZONE,
        current_epoch INTEGER NOT NULL DEFAULT 0,
        total_epochs INTEGER NOT NULL DEFAULT 0,
        checkpoint_path TEXT,
        test_acc REAL,
        test_f1 REAL,
        error_message TEXT,
        promoted_at TIMESTAMP WITH TIME ZONE,
        superseded_at TIMESTAMP WITH TIME ZONE,
        evaluation JSONB,
        FOREIGN KEY (auth_user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS training_metrics (
        job_id TEXT NOT NULL,
        epoch INTEGER NOT NULL,
        train_loss REAL,
        train_acc REAL,
        val_loss REAL,
        val_acc REAL,
        val_f1 REAL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        PRIMARY KEY (job_id, epoch)
    )
    """,
]

INDEX_STATEMENTS = [
    # users.username/users.email đã có UNIQUE -> PostgreSQL tự tạo index, không cần tạo thêm index trùng
    "CREATE INDEX IF NOT EXISTS idx_classes_class_idx ON classes(class_idx)",
    "CREATE INDEX IF NOT EXISTS idx_classes_slug ON classes(slug)",
    "CREATE INDEX IF NOT EXISTS idx_classes_lang_dialect ON classes(language, dialect)",
    "CREATE INDEX IF NOT EXISTS idx_samples_class_uid ON samples(class_uid)",
    "CREATE INDEX IF NOT EXISTS idx_samples_auth_user_id ON samples(auth_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_samples_created_at ON samples(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_raw_uploads_class_uid ON raw_uploads(class_uid)",
    "CREATE INDEX IF NOT EXISTS idx_raw_uploads_auth_user_id ON raw_uploads(auth_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_uploads_created_at ON raw_uploads(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_training_jobs_created_at ON training_jobs(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_training_jobs_status ON training_jobs(status)",
    # Partial index for Celery export: only indexes rows not yet synced to Sheets
    "CREATE INDEX IF NOT EXISTS idx_samples_sheets_synced ON samples(sheets_synced) WHERE sheets_synced = FALSE",
    "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id)",
    # Dot ca ho khi phat hien tai su dung -> luon quet theo family_id.
    "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_family ON refresh_tokens(family_id)",
    # Beat don bang quet theo expires_at moi ngay.
    "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens(expires_at)",
]

# Every table carrying a `tenant_id`. Single source of truth: the migration
# below builds its SQL from this tuple and `missing_tenant_foreign_keys()`
# audits against the same tuple, so the two cannot drift into disagreeing about
# which tables are tenant-scoped.
#
# Hai bảng v4 CỐ Ý vắng mặt ở đây:
#   * `plans` — danh mục của cả nền tảng, không thuộc tenant nào.
#   * `tenant_purges` — sổ ghi việc một tenant đã bị xoá; một khoá ngoại tới
#     `tenants` sẽ khiến chính hành động nó ghi lại thành bất khả thi.
# Ba bảng v6 CỐ Ý vắng mặt (`user_totp`, `user_recovery_codes`, và
# `refresh_tokens` từ trước): mặt phẳng DANH TÍNH, đọc trước khi biết tenant.
# RLS ở đó fail-OPEN — xem chú thích dài ở `CREATE TABLE user_totp`.
# Import cục bộ ở mức module: `authz_schema` không import gì từ đây, nên không
# có vòng. Nó được nhập để danh sách bảng phân quyền chỉ tồn tại MỘT chỗ — nơi
# DDL tạo ra chúng — thay vì phải nhớ cập nhật ba tệp.
from app.storage.authz_schema import (  # noqa: E402  (sau `logger`, có chủ ý)
    TENANT_SCOPED_AUTHZ_TABLES as _AUTHZ_TENANT_TABLES,
    add_constraint as _add_constraint,
)

TENANT_SCOPED_TABLES = (
    "api_keys", "audit_log", "capture_sessions", "classes", "dialect_aliases",
    "dialects", "notifications", "raw_uploads", "recognition_profiles",
    "registry_versions", "samples", "signer_aliases", "signer_consents",
    "signers", "support_messages", "support_tickets",
    # `tenant_members` KHÔNG còn ở đây, và không phải vì nó hết cần bảo vệ.
    #
    # PDM v5 biến nó thành một VIEW trên `memberships`. Không gắn được khoá
    # ngoại lên view, cũng không bật được RLS trên view — Postgres từ chối cả
    # hai, và `_run_ddl` nuốt lỗi, nên hậu quả là `verify_deployment` báo FAIL
    # vĩnh viễn ở hai mục ("khoa ngoai tenant_id" và "RLS bat tren bang") cho
    # một thứ không bao giờ sửa được.
    #
    # Bảo vệ chuyển xuống BẢNG NỀN: `memberships` nằm trong
    # `TENANT_SCOPED_AUTHZ_TABLES` nên nó nhận cả khoá ngoại tenant lẫn policy
    # RLS, và view khai `security_invoker = true` nên mọi truy vấn qua nó chạy
    # dưới quyền NGƯỜI GỌI và chịu đúng policy đó. Bỏ `security_invoker` đi là
    # mở toang view này — xem chú thích ở `_TENANT_MEMBERS_VIEW`.
    "tenant_exports", "tenant_invitations",
    "tenant_subscriptions", "tenant_usage_daily", "training_job_classes",
    # `training_metrics` thêm ở C3 (16/08/2026). Vòng lặp khoá ngoại chạy SAU
    # các câu C3 nên cột đã tồn tại lúc nó đi qua; `CONTINUE WHEN NOT EXISTS`
    # sẽ bỏ qua nếu ngược lại, nên thứ tự sai chỉ mất khoá ngoại chứ không hỏng
    # migration. Có mặt ở đây còn khiến `verify_deployment` và
    # `missing_tenant_foreign_keys()` soi luôn bảng này.
    "training_jobs", "training_metrics", "users",
    "vocabulary_groups", "vocabulary_registry_meta",
    "webhook_deliveries", "webhook_endpoints",
    # PDM v1.0 — mặt phẳng phân quyền. Cùng danh sách mà `storage/rls.py` dùng
    # để cài chính sách; nối vào đây để `TENANT_FK_LOOP_SQL` cũng gắn khoá
    # ngoại tenant cho chúng, và để `missing_tenant_foreign_keys()` đếm luôn.
    #
    # `roles` KHÔNG có ở đây dù nó có cột tenant_id: khoá ngoại tenant của nó
    # được khai tường minh trong `authz_schema` với ON DELETE CASCADE (xoá
    # tenant thì role riêng của nó đi theo), còn vòng lặp này gắn RESTRICT.
    *_AUTHZ_TENANT_TABLES,
)


# Khoá ngoại vá "liên kết mồ côi": cột mang tên một dòng ở bảng khác mà không
# có ràng buộc nào bắt nó phải tồn tại. Mỗi phần tử là "bảng~tên~định nghĩa",
# ngăn bằng dấu ~ vì không định nghĩa nào chứa ký tự đó; v3.12 tách chuỗi rồi
# áp trong một vòng lặp có bảo vệ.
#
# Nguồn sự thật duy nhất cho cả ba nơi: câu migration sinh SQL từ đây,
# `missing_integrity_constraints()` kiểm tra lại cũng từ đây, và bộ test đọc
# chính danh sách này. Ba nơi không thể trôi ra khỏi nhau.
#
# ON UPDATE CASCADE ở các khoá tham chiếu danh mục (ngôn ngữ, phương ngữ, hồ
# sơ, nhóm từ vựng) và KHÔNG có ON DELETE: xoá một mục danh mục còn lớp đang
# dùng phải báo lỗi, không được lặng lẽ kéo theo hay bỏ trống.
INTEGRITY_FK_SPECS: tuple[str, ...] = (
    # corpus -> danh mục, đều ghép tenant_id để một tenant không trỏ sang tenant khác
    "samples~fk_samples_class_tenant~FOREIGN KEY (tenant_id, class_uid) "
    "REFERENCES classes(tenant_id, class_uid) ON UPDATE CASCADE",
    "samples~fk_samples_signer~FOREIGN KEY (tenant_id, signer_id) "
    "REFERENCES signers(tenant_id, signer_id) ON UPDATE CASCADE",
    "samples~fk_samples_capture_session~FOREIGN KEY (capture_session_id) "
    "REFERENCES capture_sessions(capture_session_id) ON DELETE SET NULL",
    "samples~fk_samples_language~FOREIGN KEY (language) REFERENCES languages(code) "
    "ON UPDATE RESTRICT",
    "classes~fk_classes_language~FOREIGN KEY (language) REFERENCES languages(code) "
    "ON UPDATE RESTRICT",
    "classes~fk_classes_recognition_profile~FOREIGN KEY (tenant_id, recognition_profile) "
    "REFERENCES recognition_profiles(tenant_id, profile_id) ON UPDATE CASCADE",
    "classes~fk_classes_vocabulary_group~FOREIGN KEY (tenant_id, vocabulary_group) "
    "REFERENCES vocabulary_groups(tenant_id, group_id) ON UPDATE CASCADE",
    "raw_uploads~fk_raw_uploads_class_tenant~FOREIGN KEY (tenant_id, class_uid) "
    "REFERENCES classes(tenant_id, class_uid) ON UPDATE CASCADE",
    "raw_uploads~fk_raw_uploads_dialect~FOREIGN KEY (tenant_id, dialect) "
    "REFERENCES dialects(tenant_id, dialect_id) ON UPDATE CASCADE",
    # Hai khoá cùng hình dạng cho `classes` và `samples`. Máy đang chạy đã có
    # chúng dưới tên Postgres tự đặt; danh sách này thì chỉ phủ `raw_uploads`,
    # nên một máy dựng mới thiếu đúng hai ràng buộc đó. Giữ nguyên tên cũ vì
    # cùng lý do như `users_role_id_fkey` ở dưới: so khớp bằng TÊN.
    "classes~classes_dialect_fkey~FOREIGN KEY (tenant_id, dialect) "
    "REFERENCES dialects(tenant_id, dialect_id) ON UPDATE CASCADE",
    "samples~samples_dialect_fkey~FOREIGN KEY (tenant_id, dialect) "
    "REFERENCES dialects(tenant_id, dialect_id) ON UPDATE CASCADE",
    "raw_uploads~fk_raw_uploads_language~FOREIGN KEY (language) REFERENCES languages(code) "
    "ON UPDATE RESTRICT",
    # danh mục tự tham chiếu
    "dialects~fk_dialects_language~FOREIGN KEY (language) REFERENCES languages(code) "
    "ON UPDATE RESTRICT",
    "dialects~fk_dialects_merged_into~FOREIGN KEY (tenant_id, merged_into) "
    "REFERENCES dialects(tenant_id, dialect_id) ON UPDATE CASCADE",
    # `old_dialect_id` CỐ Ý không có khoá ngoại: nó trỏ tới phương ngữ đã bị gộp
    # đi mất, nên bảng bí danh chính là chỗ duy nhất còn nhớ id đó từng tồn tại.
    "dialect_aliases~fk_dialect_aliases_new~FOREIGN KEY (tenant_id, new_dialect_id) "
    "REFERENCES dialects(tenant_id, dialect_id) ON UPDATE CASCADE",
    # phiên thu
    "capture_sessions~fk_capture_sessions_class~FOREIGN KEY (tenant_id, class_uid) "
    "REFERENCES classes(tenant_id, class_uid) ON UPDATE CASCADE",
    "capture_sessions~fk_capture_sessions_signer~FOREIGN KEY (tenant_id, signer_id) "
    "REFERENCES signers(tenant_id, signer_id) ON UPDATE CASCADE",
    # `users.role_id` -> `roles.id`. Tên giữ nguyên `users_role_id_fkey` — tên
    # Postgres tự đặt trên máy đang chạy — chứ KHÔNG đổi sang lối đặt tên
    # `fk_<bảng>_<cột>` của danh sách này. `missing_integrity_constraints()` so
    # khớp bằng TÊN, nên đặt tên mới sẽ báo máy sản xuất đang thiếu một ràng
    # buộc mà nó vốn đã có, và `verify_deployment` sẽ kêu nợ vĩnh viễn.
    "users~users_role_id_fkey~FOREIGN KEY (role_id) REFERENCES roles(id)",
    # người ký và đồng ý
    "signers~fk_signers_user~FOREIGN KEY (external_user_id) REFERENCES users(id) "
    "ON DELETE SET NULL",
    "signer_consents~fk_signer_consents_signer~FOREIGN KEY (tenant_id, signer_id) "
    "REFERENCES signers(tenant_id, signer_id) ON UPDATE CASCADE",
    "signer_consents~fk_signer_consents_document~FOREIGN KEY (kind, version) "
    "REFERENCES legal_documents(kind, version) ON DELETE RESTRICT",
    "signer_aliases~fk_signer_aliases_new~FOREIGN KEY (tenant_id, new_signer_id) "
    "REFERENCES signers(tenant_id, signer_id) ON UPDATE CASCADE",
    # huấn luyện
    "training_metrics~fk_training_metrics_job~FOREIGN KEY (job_id) "
    "REFERENCES training_jobs(job_id) ON DELETE CASCADE",
    "training_job_classes~fk_training_job_classes_class~FOREIGN KEY (class_uid) "
    "REFERENCES classes(class_uid) ON DELETE SET NULL",
    "training_jobs~fk_training_jobs_registry~FOREIGN KEY (tenant_id, registry_version) "
    "REFERENCES registry_versions(tenant_id, version)",
    # xuất xứ bản sao danh mục cộng đồng
    "tenants~fk_tenants_cloned_version~FOREIGN KEY (cloned_from_community_version) "
    "REFERENCES community_versions(version)",
)


def tenant_fk_name(table: str) -> str:
    return f"fk_{table}_tenant"


#: Vòng lặp gắn khoá ngoại `tenant_id` cho mọi bảng trong TENANT_SCOPED_TABLES.
#:
#: Là hằng số chứ không viết thẳng vào danh sách migration vì nó phải chạy HAI
#: lần: một lần ở vị trí lịch sử của nó, và một lần nữa ở cuối, sau khi các
#: bảng schema v3 đã được tạo. `CREATE TABLE` của chúng nằm cuối danh sách, nên
#: ở lượt chạy thứ nhất chúng CHƯA TỒN TẠI khi vòng lặp đi qua — `CONTINUE WHEN
#: to_regclass(...) IS NULL` bỏ qua đúng như thiết kế, và sáu bảng mới ra đời
#: không có khoá ngoại tenant. Trên máy này lỗi đó tự lành ở lần khởi động thứ
#: hai, nghĩa là nó sẽ không bao giờ lộ ra trong lúc phát triển và chỉ hiện
#: hình ở một lần cài mới. `schema_debt()` bắt được nó vì chạy ngay sau lượt
#: đầu tiên; sửa bằng cách phát lại chính vòng lặp này, không phải bằng cách
#: chép một bản thứ hai có thể trôi ra khỏi bản gốc.
#:
#: Chạy lần hai không tốn gì: `CONTINUE WHEN EXISTS` bỏ qua mọi ràng buộc đã có.
TENANT_FK_LOOP_SQL = f"""
DO $$
DECLARE
    t    text;
    name text;
BEGIN
    FOREACH t IN ARRAY ARRAY[{", ".join(f"'{t}'" for t in TENANT_SCOPED_TABLES)}] LOOP
        name := 'fk_' || t || '_tenant';
        CONTINUE WHEN to_regclass('public.' || t) IS NULL;
        CONTINUE WHEN NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = t
              AND column_name = 'tenant_id'
        );
        CONTINUE WHEN EXISTS (SELECT 1 FROM pg_constraint WHERE conname = name);
        BEGIN
            EXECUTE format(
                'ALTER TABLE public.%I ADD CONSTRAINT %I FOREIGN KEY (tenant_id) '
                'REFERENCES tenants(tenant_id) ON UPDATE RESTRICT ON DELETE RESTRICT',
                t, name);
        EXCEPTION WHEN others THEN
            RAISE WARNING '[TENANT_FK] % skipped: %', t, SQLERRM;
        END;
    END LOOP;
END $$
"""


def missing_tenant_foreign_keys() -> List[str]:
    """Tenant-scoped tables that exist but have NO foreign key on `tenant_id`.

    `ensure_tables` swallows a failed migration into a log warning so one bad
    statement cannot brick startup. That is the right trade for a boot path, but
    it means "the migration ran" and "the constraint is there" are different
    facts — and only the second one protects anything. This reports the second.

    Empty list = every tenant-scoped table is guarded by the database itself.
    """
    rows = _fetch_all(
        "SELECT c.relname AS table_name FROM pg_constraint k "
        "JOIN pg_class c ON c.oid = k.conrelid "
        "WHERE k.contype = 'f' AND k.confrelid = 'tenants'::regclass"
    )
    guarded = {r["table_name"] for r in rows}
    present = {
        r["table_name"]
        for r in _fetch_all(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
    }
    return sorted(t for t in TENANT_SCOPED_TABLES if t in present and t not in guarded)


def missing_integrity_constraints() -> List[str]:
    """Khoá ngoại trong `INTEGRITY_FK_SPECS` mà cơ sở dữ liệu KHÔNG có.

    Cùng lý do tồn tại như `missing_tenant_foreign_keys()`: `_run_ddl` hạ mọi
    thất bại xuống một dòng log cảnh báo để một câu hỏng không làm chết khởi
    động. Đó là đánh đổi đúng cho đường khởi động, nhưng nó khiến "migration
    đã chạy" và "ràng buộc đang bảo vệ dữ liệu" thành hai sự thật khác nhau.
    Hàm này báo cáo sự thật thứ hai.

    Bảng chưa tồn tại trên máy này thì không tính là thiếu — nó chưa tới lượt.

    Danh sách rỗng = mọi liên kết đã kiểm kê đều được chính cơ sở dữ liệu ép.
    """
    present = {
        r["table_name"]
        for r in _fetch_all(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
    }
    existing = {
        r["conname"] for r in _fetch_all("SELECT conname FROM pg_constraint WHERE contype = 'f'")
    }
    missing = []
    for spec in INTEGRITY_FK_SPECS:
        table, name, _definition = spec.split("~", 2)
        if table in present and name not in existing:
            missing.append(name)
    return sorted(missing)


def schema_debt() -> Dict[str, Any]:
    """Một lần đọc gộp: schema còn nợ những gì so với thiết kế đã chốt.

    Dùng bởi `app.cli.verify_deployment` và bộ test. Gộp vào một hàm vì ba
    câu hỏi này luôn phải hỏi cùng lúc — biết thiếu khoá ngoại mà không biết
    còn bảng chết nào thì vẫn chưa trả lời được "schema đã đúng chưa".
    """
    leftovers = [
        t
        for t in ("user_profiles",)
        if _fetch_all(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = %s",
            (t,),
        )
    ]
    return {
        "missing_tenant_foreign_keys": missing_tenant_foreign_keys(),
        "missing_integrity_constraints": missing_integrity_constraints(),
        "dead_tables_still_present": leftovers,
    }


MIGRATION_STATEMENTS = [
    # -----------------------------------------------------------------------
    # v3.17 — tách vùng miền ra khỏi `dialect`.
    #
    # `dialect` gánh ba nghĩa cùng lúc: tập vốn từ (`bang-chu-cai`, `spa`,
    # `can-tho`, `hoa-de`), phạm vi (`common`), và vùng miền (`bac`/`nam`/
    # `trung`). Chính `app/dataset_manager.py` đã ghi "DEPRECATED as a semantic
    # field (it conflated region / vocabulary domain / collection campaign)" —
    # cột này hoàn tất việc tách đó.
    #
    # `dialect` KHÔNG bị đụng tới: nó vẫn là tên thư mục lưu trữ
    # (`features/{language}/{dialect}/{folder}`) và vẫn nằm trong `storage_key`
    # của từng mẫu. Đổi nó sẽ kéo theo chuyển tệp trên đĩa, ghi lại storage_key
    # và đồng bộ lại Drive — nên không đổi.
    #
    # Chỉ THÊM cột, không ràng buộc CHECK: giá trị hợp lệ được chuẩn hoá ở
    # `normalize_region()` phía ứng dụng. Thêm CHECK ở đây sẽ làm mọi hàng cũ
    # (region NULL) hợp lệ nhưng chặn mọi lượt ghi sai chính tả một cách im
    # lặng ở tầng dưới, khó lần ra hơn là để tầng ứng dụng từ chối.
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS region TEXT",
    # -----------------------------------------------------------------------
    # v3.19 — `region` thành NOT NULL với danh mục riêng, và `unclassified`
    # tách hẳn khỏi `common`.
    #
    # v3.17/v3.18 để `region` nhận NULL và chuỗi rỗng cùng nghĩa "chưa biết".
    # Hai vấn đề, và cái thứ hai nặng hơn:
    #
    #   1. Khoá duy nhất phải bọc `coalesce(region,'')`, vì hai NULL không đụng
    #      nhau — một workaround che một lỗ, không phải một thiết kế.
    #   2. "Chưa xác minh thuộc vùng nào" và "đã xác minh là không phân biệt
    #      vùng" bị gộp làm một. Đó là hai TRẠNG THÁI QUY TRÌNH khác hẳn nhau,
    #      và gộp chúng thì không bao giờ trả lời được "còn bao nhiêu nhãn chờ
    #      phân loại" — câu hỏi vận hành duy nhất đáng hỏi ở đây.
    #
    # Nên: `unclassified` = chưa qua phân loại; `common` = đã kiểm chứng là
    # dùng chung; `bac`/`trung`/`nam` = đã kiểm chứng là biến thể vùng. Chuyển
    # trạng thái luôn đi từ `unclassified` sang một trong bốn cái còn lại.
    #
    # KHÔNG dùng ENUM của PostgreSQL. `tay-nguyen`, `tay-nam-bo`, hay cách chia
    # vùng riêng của một tenant đều sẽ tới, và `ALTER TYPE ... ADD VALUE` khoá
    # bảng, không quay lui được trong giao dịch, cũng không xoá được giá trị.
    # Bảng danh mục thì thêm/nghỉ hưu một dòng là xong.
    #
    # Bảng TOÀN CỤC, không có `tenant_id` — cùng hình dạng với `languages`, mà
    # `classes.language` đã trỏ tới bằng `fk_classes_language`.
    #
    # Bản đầu tôi làm nó theo tenant, khuôn `community_dialects` -> `dialects`.
    # Sai, và bộ test bắt ngay: 11 lỗi khoá ngoại từ những chỗ chèn thẳng một
    # hàng `tenants` bằng SQL thô (test làm vậy, và migration cũng vậy). Một
    # tenant không có dòng `regions` nào thì KHÔNG tạo nổi một lớp nào — đúng
    # cái bẫy "khoá ngoại làm tenant mới vô dụng" đã gặp một lần với `dialects`.
    #
    # Vùng địa lý của tiếng Việt không phải thứ mỗi tổ chức định nghĩa lại,
    # y như mã ngôn ngữ. Khi nào thật sự có tenant cần cách chia riêng thì thêm
    # một bảng phủ theo tenant — rẻ hơn nhiều so với việc bây giờ bắt mọi
    # đường tạo tenant phải nhớ gieo năm hàng.
    """CREATE TABLE IF NOT EXISTS regions (
        code          TEXT PRIMARY KEY,
        name_vi       TEXT NOT NULL,
        name_en       TEXT NOT NULL DEFAULT '',
        status        TEXT NOT NULL DEFAULT 'approved',
        sort_order    INTEGER NOT NULL DEFAULT 0,
        is_active     BOOLEAN NOT NULL DEFAULT TRUE,
        note          TEXT,
        updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    """INSERT INTO regions(code, name_vi, name_en, sort_order, note) VALUES
        ('unclassified', 'Chưa phân loại', 'Unclassified', 0,
         'Đã nhập vào hệ thống nhưng CHƯA qua bước phân loại vùng. Khác hẳn common.'),
        ('common',       'Chung',          'Common',       1,
         'ĐÃ kiểm chứng là không cần phân biệt vùng.'),
        ('bac',          'Bắc',            'North',        2, NULL),
        ('trung',        'Trung',          'Central',      3, NULL),
        ('nam',          'Nam',            'South',        4, NULL)
       ON CONFLICT (code) DO NOTHING""",
    # Backfill TRƯỚC khi đặt NOT NULL. Cả NULL lẫn chuỗi rỗng đều là "chưa
    # phân loại" theo nghĩa cũ, nên cả hai về `unclassified`.
    _SQL_BACKFILL_CLASS_REGION,
    "ALTER TABLE classes ALTER COLUMN region SET DEFAULT 'unclassified'",
    _SQL_CLASS_REGION_NOT_NULL,
    # Khoá ngoại đúng hình dạng `fk_classes_language`: một cột, bảng toàn cục.
    #
    # ON UPDATE RESTRICT, KHÔNG phải CASCADE — và đây là bài học từ một lỗ thật
    # đã bắt được ngày 14/08, không phải sự cẩn thận thừa.
    # ------------------------------------------------------------------------
    # Với CASCADE, một câu `UPDATE regions SET code = ...` ghi lại `classes` của
    # MỌI tenant cùng lúc, mà lượt ghi đó KHÔNG chạm bảng `classes` nên không
    # policy RLS nào của nó được hỏi tới. Một bảng không chứa dữ liệu tenant nào
    # vẫn trở thành ranh giới cô lập, nếu thao tác trên nó làm thay đổi được dữ
    # liệu thuộc về tenant. Gọi tên nó ra thì dễ rà: ĐƯỜNG GHI BẮC CẦU.
    #
    # Thu quyền ghi của vai ứng dụng đã chặn được đường khai thác đó, nhưng
    # RESTRICT chặn thêm một tầng nữa — cho cả mã chạy dưới vai migration.
    #
    # Cái giá gần như bằng không, vì `code` là ĐỊNH DANH MÁY chứ không phải nhãn
    # hiển thị: `bac` cố định, còn `name_vi`/`name_en` mới là thứ người ta đổi.
    # Đổi `bac` thành `north` phải là một migration có chủ ý, không phải hệ quả
    # phụ của một lượt ghi nghiệp vụ.
    # `add_constraint` chứ không phải `ALTER TABLE` trần: SQL không có
    # `ADD CONSTRAINT IF NOT EXISTS`, nên bản trần hỏng ở MỌI lượt chạy thứ hai
    # trở đi và để lại một dòng
    #
    #     ensure_tables: migration statement failed (ignored):
    #     constraint "classes_region_fkey" for relation "classes" already exists
    #
    # trong mỗi lần khởi động của mỗi service dùng chung ảnh này. Đây là lỗi
    # chưa-phân-loại CUỐI CÙNG còn sót sau lượt migration 15/08/2026, và tiếng
    # ồn kiểu đó dạy người vận hành bỏ qua cảnh báo của `ensure_tables` — cảnh
    # báo tiếp theo có thể là thật.
    #
    # Đánh đổi, nêu rõ: đổi ĐỊNH NGHĨA ràng buộc này về sau sẽ không tự áp
    # dụng nữa, phải viết một câu migration riêng. Giống hệt đánh đổi mà 20 ràng
    # buộc khác trong kho này đã chấp nhận.
    _add_constraint("classes", "classes_region_fkey",
                    "FOREIGN KEY (region) REFERENCES regions(code) "
                    "ON UPDATE RESTRICT"),
    # Bỏ bản `coalesce` TRƯỚC khi bản trần được dựng phía dưới. Không có
    # khoảng trống về đảm bảo: `NOT NULL` + khoá ngoại vừa đặt ở trên đã chặn
    # đúng cái mà `coalesce` từng chặn.
    *_DROP_COALESCE_REGION_UNIQUE,
    # -----------------------------------------------------------------------
    # v3.16 — trợ lý tự động trả lời trước khi có người trực.
    #
    # `is_staff` là một cờ HAI giá trị, và kênh hỗ trợ giờ có BA loại người
    # nói: người dùng, người trực, và trợ lý tự động. Nhét trợ lý vào một
    # trong hai ô sẵn có đều là nói dối trên một bản ghi trao đổi:
    #
    #   * `is_staff = TRUE`  → giao diện gắn nhãn "người trực" cho một câu máy
    #     sinh ra. Người dùng tin rằng đã có người thật đọc phiếu của họ.
    #   * `is_staff = FALSE` → câu của trợ lý lẫn vào lời người dùng, và người
    #     trực đọc lại phiếu sẽ tưởng người dùng tự nói những câu đó.
    #
    # Nên: một cột thứ ba nói thẳng ai là người nói. Backfill suy từ `is_staff`
    # — KHÔNG phải bịa dữ liệu, vì với các hàng cũ `is_staff` đúng là toàn bộ
    # thông tin đã có: hồi đó chỉ có hai loại người nói.
    "ALTER TABLE support_messages ADD COLUMN IF NOT EXISTS author_kind TEXT",
    "UPDATE support_messages SET author_kind = "
    "CASE WHEN is_staff THEN 'staff' ELSE 'user' END "
    "WHERE author_kind IS NULL",
    "ALTER TABLE support_messages ALTER COLUMN author_kind SET DEFAULT 'user'",
    # Ràng buộc phải thêm SAU backfill, nếu không migration đổ ở hàng cũ.
    "ALTER TABLE support_messages DROP CONSTRAINT IF EXISTS ck_support_author_kind",
    "ALTER TABLE support_messages ADD CONSTRAINT ck_support_author_kind "
    "CHECK (author_kind IN ('user', 'staff', 'bot'))",
    # `is_staff` và `author_kind` phải nói cùng một chuyện. Thiếu ràng buộc này,
    # một lượt ghi hụt tạo ra hàng `author_kind='bot'` mà `is_staff=TRUE` —
    # đúng lời nói dối mà cả cột này sinh ra để ngăn.
    "ALTER TABLE support_messages DROP CONSTRAINT IF EXISTS ck_support_author_kind_matches",
    "ALTER TABLE support_messages ADD CONSTRAINT ck_support_author_kind_matches "
    "CHECK ((author_kind = 'staff') = is_staff)",

    # -----------------------------------------------------------------------
    # v3.15 — văn bản pháp lý là TỆP, không phải markdown gõ trong ứng dụng.
    #
    # Văn bản pháp lý thật đi qua tay người không dùng trình soạn markdown:
    # phòng pháp chế gửi `.docx`, bản đã ký về dưới dạng `.pdf` có dấu. Bắt họ
    # dán vào một ô markdown là làm mất định dạng, mất chữ ký, và mất luôn bản
    # gốc để đối chiếu.
    #
    # Bốn cột NULLABLE, và điều đó là bắt buộc: bốn văn bản đã công bố trên máy
    # chạy thật đang mang thân markdown và đã có chữ ký trỏ vào `content_hash`
    # của chúng. Cột NOT NULL ở đây sẽ hoặc chặn migration, hoặc buộc phải bịa
    # một giá trị cho hàng cũ — và bịa dữ liệu trên bảng làm bằng chứng pháp lý
    # là điều không được phép.
    #
    # `file_key` trỏ vào cùng kho định-địa-chỉ-bằng-nội-dung mà markdown đang
    # dùng (`app/legal_store.py`), nên tính bất biến và khử trùng lặp có sẵn.
    "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS file_key TEXT",
    "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS file_name TEXT",
    "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS file_mime TEXT",
    "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS file_size BIGINT",
    # `language` KHÔNG khai lại ở đây — một migration cũ đã thêm nó. Khai hai
    # lần thì `IF NOT EXISTS` vẫn chạy được, nhưng nó nói dối người đọc rằng cột
    # này ra đời ở v3.15, và người tiếp theo đi tìm nguồn gốc sẽ dừng sai chỗ.
    #
    # Tra theo (loại, ngôn ngữ) là truy vấn của MỌI lượt mở trang văn bản.
    "CREATE INDEX IF NOT EXISTS idx_legal_documents_kind_lang "
    "ON legal_documents (kind, language, effective_from DESC)",
    # Nới CHECK cho `body_format = 'file'`. Ràng buộc cũ chỉ cho
    # ('markdown','text') và nó ĐÃ chặn đúng — một cột trạng thái không có
    # CHECK là một cột sẽ nhận mọi lỗi chính tả. Nới bằng DROP rồi ADD thay vì
    # sửa tại chỗ: Postgres không có `ALTER CONSTRAINT ... CHECK`.
    """
    DO $$ BEGIN
        ALTER TABLE legal_documents DROP CONSTRAINT IF EXISTS ck_legal_documents_body_format;
        ALTER TABLE legal_documents ADD CONSTRAINT ck_legal_documents_body_format
            CHECK (body_format IN ('markdown', 'text', 'file'));
    END $$
    """,
    # Một bản `file` PHẢI có tệp, và một bản markdown thì KHÔNG được có. Thiếu
    # ràng buộc này, một lượt ghi hụt sẽ tạo ra hàng `body_format='file'` mà
    # `file_key` NULL — giao diện chọn trình đọc tệp, và người dùng thấy một
    # trang trắng thay vì điều khoản họ sắp ký.
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_legal_documents_file_pair'
        ) THEN
            ALTER TABLE legal_documents ADD CONSTRAINT ck_legal_documents_file_pair
                CHECK ((body_format = 'file') = (file_key IS NOT NULL));
        END IF;
    END $$
    """,

    # -----------------------------------------------------------------------
    # v3.14 — vòng đời phiên đăng nhập (xem docs/03-security/AUTH_TOKEN_LIFECYCLE.md).
    #
    # Ba cột này biến việc xoay refresh token từ "đúng một nửa" thành đủ: xoay
    # mà KHÔNG phát hiện tái sử dụng thì kết quả bị lộn ngược — kẻ trộm gọi
    # /refresh trước sẽ cầm token mới, còn người dùng thật bị 401 và đăng xuất.
    # RFC 9700 đòi thu hồi cả họ token khi gặp trường hợp đó.
    #
    # `sessions_invalid_before` là mốc force-logout hạ xuống Postgres. Trước đây
    # mốc này CHỈ nằm ở Redis, nên Redis khởi động lại là mọi lệnh thu hồi phiên
    # của quản trị viên bốc hơi, và không ai để ý vì nó không kêu.
    "ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS family_id UUID",
    "ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS replaced_by TEXT",
    "ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS reuse_detected_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS sessions_invalid_before TIMESTAMP WITH TIME ZONE",
    # Token cũ (cấp trước lần triển khai này) không có họ. Gán cho mỗi cái một
    # họ RIÊNG chứ không gộp chung: gộp lại thì một lần phát hiện tái sử dụng sẽ
    # đá luôn mọi phiên cũ của mọi người, mà chúng vốn không liên quan gì nhau.
    "UPDATE refresh_tokens SET family_id = gen_random_uuid() WHERE family_id IS NULL",
    # -----------------------------------------------------------------------
    # v3.13 — 14 cột chỉ có trên máy đang chạy, không có trong mã.
    #
    # Cùng loại nợ với `languages`/`roles` ở `DDL_STATEMENTS`, chỉ ở tầng CỘT.
    # Đo 2026-08-10 bằng cách so `information_schema.columns` giữa `signdb` và
    # một CSDL dựng từ số không: bản dựng mới thiếu **14 cột** mà máy sản xuất
    # có. Chúng không phải cột chết — `users.phone_number` là cột luồng OTP
    # đang đọc, `samples.storage_key`/`username` là cột đường đồng bộ đang ghi.
    # Chúng ra đời bằng tay ở đời lược đồ cũ và không ai chép ngược vào mã.
    #
    # Vì sao chưa từng ai thấy: bộ test luôn chạy trên **bản sao của sản xuất**,
    # nơi 14 cột này đã có sẵn. Lần đầu chạy trên CSDL trống — để dựng CI — thì
    # 22 test đỏ, và đây là một nửa nguyên nhân.
    #
    # Hệ quả thật, không phải giả thuyết: một máy triển khai MỚI (kịch bản "máy
    # thứ hai") khởi động khoẻ mạnh rồi vỡ ở lần chạm đầu tiên vào cột thiếu.
    #
    # Kiểu và giá trị mặc định lấy đúng từ máy đang chạy, để hai bên hội tụ chứ
    # không sinh ra một phiên bản thứ ba.
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS role_id UUID",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS description TEXT DEFAULT ''",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS username TEXT",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS session_uid TEXT",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'PENDING'",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS storage_key TEXT DEFAULT ''",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS error_log TEXT DEFAULT ''",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS username TEXT",
    "ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS session_uid TEXT",
    "ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'PENDING'",
    # Soft delete trash
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE",
    # Add sheets_synced column to samples (safe for existing data: defaults to FALSE)
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS sheets_synced BOOLEAN DEFAULT FALSE",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS gdrive_synced BOOLEAN DEFAULT TRUE",
    # Promotion timestamp for training jobs (admin promoted model to realtime)
    "ALTER TABLE training_jobs ADD COLUMN IF NOT EXISTS promoted_at TIMESTAMP WITH TIME ZONE",
    # When a LATER promotion for the same dialect replaced this job's model.
    # The realtime slot is keyed by dialect (one dialect = one model), so
    # promoted_at alone stopped meaning "currently serving" — two jobs could
    # both carry it while only one was live. Kept as a separate column rather
    # than clearing promoted_at: "was promoted at T1, replaced at T2" is an
    # audit fact worth keeping, and the retention sweep needs to tell a live
    # checkpoint from a retired one.
    "ALTER TABLE training_jobs ADD COLUMN IF NOT EXISTS superseded_at TIMESTAMP WITH TIME ZONE",
    # Test-set evaluation (confusion matrix + per-class metrics) for Step 7
    "ALTER TABLE training_jobs ADD COLUMN IF NOT EXISTS evaluation JSONB",
    # Live-capture QC: per-class hand requirement + per-sample quality metrics
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS hands_required INTEGER",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS left_hand_ratio REAL",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS right_hand_ratio REAL",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS both_hands_ratio REAL",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS jitter REAL",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS quality_flags TEXT",
    # Vocabulary schema v2 (dialect is deprecated as a semantic field)
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS semantic_label TEXT",
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS vocabulary_scope TEXT",
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS recognition_profile TEXT",
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS vocabulary_group TEXT",
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS collection_campaign TEXT",
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS motion_type TEXT",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS signer_id TEXT",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS collection_campaign TEXT",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS raw_landmarks_available BOOLEAN",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS normalization_version TEXT",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS preprocess_contract_version TEXT",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS sequence_length_original INTEGER",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS quality_status TEXT",
    # Normalized signer registry (signer_id is the ONLY key for signer-disjoint splits)
    """
    CREATE TABLE IF NOT EXISTS signers (
        signer_id TEXT PRIMARY KEY,
        display_name TEXT,
        regional_group TEXT,
        external_user_id TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_samples_signer_id ON samples(signer_id)",
    # ---------------------------------------------------------------------
    # Multi-tenant groundwork (control plane / data plane split).
    #
    # Additive and inert today: every column carries DEFAULT 'default', so
    # existing rows backfill to the single tenant and no write path has to
    # change yet. What this buys now is the part that is expensive to retrofit
    # later — a tenant key on every data-plane row, and uniqueness scoped to it.
    #
    # Read docs/11-worklog/MULTITENANT_PREP.md before wiring tenant_id into the
    # write paths: the schema is the easy half, and the things still assuming a
    # single tenant (dataset/ layout, Drive folder, class_idx, checkpoints)
    # are listed there.
    """
    CREATE TABLE IF NOT EXISTS tenants (
        tenant_id TEXT PRIMARY KEY,
        display_name TEXT,
        slug TEXT UNIQUE,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        deleted_at TIMESTAMP WITH TIME ZONE
    )
    """,
    # The tenant id is interpolated from app.tenancy.DEFAULT_TENANT_ID rather
    # than spelled inline, so the DDL default, the CSV backfill and the upsert
    # payloads provably agree. The constant is validated against a strict
    # alphabet at import, which is what makes this interpolation safe.
    # `INSERT ... SELECT ... WHERE NOT EXISTS`, KHÔNG phải `ON CONFLICT DO
    # NOTHING`. Hai câu này tương đương về ý định và khác nhau ở một điểm đắt
    # giá: `ON CONFLICT` vẫn DỰNG tuple rồi mới phát hiện trùng, nên mọi ràng
    # buộc NOT NULL trên bảng được kiểm TRƯỚC bước phát hiện đó.
    #
    # Hệ quả thật, đã đo được: v4.2 thêm `plan_code NOT NULL`. Câu này nằm
    # trước v4.2 trong danh sách, nên ở lượt chạy ĐẦU nó vô hại (cột chưa tồn
    # tại), còn từ lượt chạy THỨ HAI nó vi phạm NOT NULL và bị `ensure_tables`
    # nuốt thành một dòng cảnh báo. Trên máy đã có tenant gốc thì không ai
    # thấy gì — nhưng trên một bản cài mà hàng đó vắng mặt, tenant gốc sẽ lặng
    # lẽ không bao giờ được tạo, và cả stack đứng.
    #
    # `WHERE NOT EXISTS` không sinh hàng nào khi hàng đã có, nên không có tuple
    # nào để kiểm ràng buộc. Đúng ba trường hợp: cài mới (chèn, chưa có cột),
    # chạy lại (không làm gì, không lỗi), hàng bị xoá (chèn, cột lấy mặc định).
    _SQL_BOOTSTRAP_DEFAULT_TENANT,
    f"ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT '{DEFAULT_TENANT_ID}'",
    f"ALTER TABLE classes ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT '{DEFAULT_TENANT_ID}'",
    f"ALTER TABLE samples ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT '{DEFAULT_TENANT_ID}'",
    f"ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT '{DEFAULT_TENANT_ID}'",
    f"ALTER TABLE signers ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT '{DEFAULT_TENANT_ID}'",
    f"ALTER TABLE training_jobs ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT '{DEFAULT_TENANT_ID}'",
    "CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_classes_tenant_id ON classes(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_samples_tenant_id ON samples(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_uploads_tenant_id ON raw_uploads(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_training_jobs_tenant_id ON training_jobs(tenant_id)",
    # username/email should be unique per TENANT, not globally: two schools must
    # both be able to have an "admin". These add the scoped guarantee now.
    #
    # The GLOBAL users_username_key / users_email_key from the users DDL are
    # deliberately left in place — dropping uniqueness on a live auth table is
    # not a change to slip in ahead of a second tenant existing. Until they are
    # dropped, tenant B genuinely cannot register a username tenant A already
    # took. That drop is step 3 in docs/11-worklog/MULTITENANT_PREP.md.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_tenant_username ON users(tenant_id, username)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_tenant_email ON users(tenant_id, email)",
    # ---------------------------------------------------------------------
    # Vocabulary registry. Postgres is the SOURCE OF TRUTH here, unlike
    # labels/samples where the CSV is — because only a FK can actually refuse a
    # bad value at write time. See docs/02-data/DIALECT_LIFECYCLE.md.
    #
    # dialect_id is IMMUTABLE: it names a directory on disk
    # (features/<lang>/<dialect>/), a checkpoint file, and a published split
    # manifest. Renaming it would reach 10 storage layers, 3 of which are
    # deliberately unchangeable. display_name carries the accents and is the
    # thing people actually rename.
    f"""
    CREATE TABLE IF NOT EXISTS dialects (
        tenant_id    TEXT NOT NULL DEFAULT '{DEFAULT_TENANT_ID}',
        dialect_id   TEXT NOT NULL,
        display_name TEXT NOT NULL,
        language     TEXT NOT NULL DEFAULT 'vn',
        is_alphabet  BOOLEAN NOT NULL DEFAULT FALSE,
        is_active    BOOLEAN NOT NULL DEFAULT TRUE,
        status       TEXT NOT NULL DEFAULT 'pending',
        merged_into  TEXT,
        created_by   UUID REFERENCES users(id) ON DELETE SET NULL,
        approved_by  UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        approved_at  TIMESTAMP WITH TIME ZONE,
        note         TEXT,
        PRIMARY KEY (tenant_id, dialect_id)
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS recognition_profiles (
        tenant_id    TEXT NOT NULL DEFAULT '{DEFAULT_TENANT_ID}',
        profile_id   TEXT NOT NULL,
        display_name TEXT NOT NULL,
        is_trainable BOOLEAN NOT NULL DEFAULT TRUE,
        is_active    BOOLEAN NOT NULL DEFAULT TRUE,
        created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        PRIMARY KEY (tenant_id, profile_id)
    )
    """,
    # A merged-away dialect_id must stay resolvable forever: checkpoints and
    # published split manifests still carry the OLD string and must not be
    # rewritten — they are the record of an experiment that already ran.
    f"""
    CREATE TABLE IF NOT EXISTS dialect_aliases (
        tenant_id      TEXT NOT NULL DEFAULT '{DEFAULT_TENANT_ID}',
        old_dialect_id TEXT NOT NULL,
        new_dialect_id TEXT NOT NULL,
        merged_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        merged_by      UUID REFERENCES users(id) ON DELETE SET NULL,
        PRIMARY KEY (tenant_id, old_dialect_id)
    )
    """,
    # One integer the offline exporters stamp into their snapshot. A host-run
    # script comparing it against its own copy detects a stale export instead of
    # silently using last month's list — the exact failure that lost
    # config/legacy_signer_mapping.json without anyone noticing.
    f"""
    CREATE TABLE IF NOT EXISTS vocabulary_registry_meta (
        tenant_id TEXT PRIMARY KEY DEFAULT '{DEFAULT_TENANT_ID}',
        version   BIGINT NOT NULL DEFAULT 1,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    _SQL_SEED_VOCAB_REGISTRY_META,
    "CREATE INDEX IF NOT EXISTS idx_dialects_status ON dialects(tenant_id, status, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_dialects_created_by ON dialects(created_by)",
    # ---------------------------------------------------------------------
    # Immutable registry versions.
    #
    # vocabulary_registry_meta.version above is a COUNTER that gets overwritten,
    # and export_snapshot() overwrote a single file. Together they made
    # "this dataset pins registry v2" impossible to honour: v2's contents were
    # gone the moment v3 was written, so an artifact could claim a version that
    # no longer described anything. Rows here are append-only and never updated;
    # meta.version stays as the pointer to the current one.
    #
    # content_hash is over the canonical JSON, so a pinned snapshot can be
    # verified byte-for-byte rather than trusted by version number alone.
    """
    CREATE TABLE IF NOT EXISTS registry_versions (
        tenant_id    TEXT NOT NULL,
        version      BIGINT NOT NULL,
        content_hash TEXT NOT NULL,
        snapshot     JSONB NOT NULL,
        note         TEXT,
        created_by   UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        PRIMARY KEY (tenant_id, version)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_registry_versions_hash ON registry_versions(content_hash)",
    # ---------------------------------------------------------------------
    # Community plane — the bootstrap template, owned by system admins.
    #
    # Separate tables, not a reserved tenant_id, so "tenant may never read the
    # community catalogue" is enforceable by which table a query names rather
    # than by remembering a WHERE clause. Nothing at runtime reads these: they
    # are cloned once when a tenant is created (see clone_catalog_to_tenant).
    """
    CREATE TABLE IF NOT EXISTS community_dialects (
        dialect_id    TEXT PRIMARY KEY,
        display_name  TEXT NOT NULL,
        language      TEXT NOT NULL DEFAULT 'vn',
        is_alphabet   BOOLEAN NOT NULL DEFAULT FALSE,
        display_order INTEGER NOT NULL DEFAULT 0,
        is_active     BOOLEAN NOT NULL DEFAULT TRUE,
        note          TEXT,
        updated_by    UUID REFERENCES users(id) ON DELETE SET NULL,
        updated_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS community_profiles (
        profile_id    TEXT PRIMARY KEY,
        display_name  TEXT NOT NULL,
        is_trainable  BOOLEAN NOT NULL DEFAULT TRUE,
        display_order INTEGER NOT NULL DEFAULT 0,
        is_active     BOOLEAN NOT NULL DEFAULT TRUE,
        note          TEXT,
        updated_by    UUID REFERENCES users(id) ON DELETE SET NULL,
        updated_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS community_versions (
        version      BIGINT PRIMARY KEY,
        content_hash TEXT NOT NULL,
        snapshot     JSONB NOT NULL,
        note         TEXT,
        created_by   UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    # Which community version a tenant was cloned from. Kept so a tenant that
    # diverged can still be compared against its origin.
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS cloned_from_community_version BIGINT",
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS cloned_at TIMESTAMP WITH TIME ZONE",
    # ---------------------------------------------------------------------
    # Tenant membership. Editing a tenant's registry requires being an admin or
    # editor OF THAT TENANT — a system admin flag is a different authority and
    # is checked separately, so one tenant's editor can never touch another's.
    """
    CREATE TABLE IF NOT EXISTS tenant_members (
        tenant_id  TEXT NOT NULL,
        user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role       TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        PRIMARY KEY (tenant_id, user_id),
        CONSTRAINT tenant_members_role_valid CHECK (role IS NULL OR role IN ('admin', 'editor'))
    )
    """,
    # ---------------------------------------------------------------------
    # `role` NULL = tư cách thành viên CÓ, vai ở tầng tenant KHÔNG CÓ.
    #
    # Đây là chỗ hai khái niệm bị trộn lẫn suốt từ đầu được tách ra. Cột này
    # từng `NOT NULL DEFAULT 'viewer'`, nghĩa là mọi lời mời không nói gì đều
    # cấp một vai — và vai đó, `tenant_viewer`, đọc được hoá đơn, nhật ký kiểm
    # toán, danh sách khoá API và trạng thái đồng thuận của người ký thật. Một
    # mặc định không ai chọn đã trở thành một quyết định phân quyền.
    #
    # Ba trạng thái, và giờ chúng nói ba điều khác nhau:
    #
    #     'admin'   quản trị tenant
    #     'editor'  biên tập dữ liệu và danh mục
    #     NULL      là thành viên, chưa có vai nào ở tầng tenant
    #
    # Người ở trạng thái NULL chỉ nhận quyền qua assignment ở workspace/project,
    # hoặc qua một role TỰ TẠO mà Tenant Owner/Admin dựng. Đó là điểm của việc
    # gỡ `tenant_viewer`: chỉ-đọc toàn tenant là lựa chọn của tổ chức, có người
    # ký tên, chứ không phải mặc định của nền tảng.
    #
    # Vì sao CẢ KHỐI nằm trong một `DO` có canh `pg_tables`
    # ------------------------------------------------------
    # `tenant_members` chỉ còn là BẢNG cho tới khi `authz_schema` gộp nó vào
    # `memberships` và thay bằng một VIEW — việc đó xảy ra ở `AUTHZ_DDL_STATEMENTS`,
    # tức là SAU danh sách này, trong cùng một lượt `ensure_tables()`.
    #
    # Nên câu `ALTER TABLE` trần ở đây đúng đúng MỘT lần: lượt khởi động đầu
    # tiên sau khi triển khai. Từ lượt thứ hai trở đi nó gặp một view và ném
    # lỗi — mà `_run_ddl` nuốt, nên nó thành một dòng cảnh báo ở mọi lần khởi
    # động, mãi mãi. Cảnh báo vĩnh viễn dạy người ta bỏ qua cảnh báo.
    #
    # Ràng buộc BỀN của giá trị vai không sống ở đây; nó sống ở
    # `authz_schema.ck_memberships_legacy_role_valid`, trên bảng nền. Khối này
    # chỉ lo cho quãng thời gian bảng cũ còn tồn tại — kể cả một bản triển khai
    # không bao giờ chạy tới lượt gộp.
    """
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_tables
                        WHERE schemaname = current_schema()
                          AND tablename = 'tenant_members') THEN
            RETURN;
        END IF;

        ALTER TABLE tenant_members ALTER COLUMN role DROP DEFAULT;
        ALTER TABLE tenant_members ALTER COLUMN role DROP NOT NULL;

        -- Mọi 'viewer' cũ thành NULL, KHÔNG thành 'editor'. Hạ xuống editor sẽ
        -- NỚI quyền ghi cho người chưa từng có — hỏng theo hướng nguy hiểm, do
        -- một lượt đổi lược đồ. Đo trên sản xuất 11/08/2026: 0 dòng, nên câu
        -- này không đụng tới ai; nó có mặt cho những bản triển khai khác.
        --
        -- Chuyển dữ liệu TRƯỚC khi siết ràng buộc. Thứ tự ngược lại làm
        -- `ADD CONSTRAINT` vỡ trên chính những dòng nó sắp cấm.
        UPDATE tenant_members SET role = NULL WHERE role = 'viewer';

        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'tenant_members_role_valid'
              AND pg_get_constraintdef(oid) LIKE '%%viewer%%'
        ) THEN
            ALTER TABLE tenant_members DROP CONSTRAINT tenant_members_role_valid;
            ALTER TABLE tenant_members ADD CONSTRAINT tenant_members_role_valid
                CHECK (role IS NULL OR role IN ('admin', 'editor'));
        END IF;
    END $$
    """,
    # Hai chỉ mục trên `tenant_members` đã CHUYỂN sang bảng nền.
    #
    # Từ PDM v5, `tenant_members` là một VIEW trên lát cắt `scope_level =
    # 'TENANT'` của `memberships`, và Postgres không đánh chỉ mục được view:
    #
    #     ERROR: cannot create index on relation "tenant_members"
    #     DETAIL: This operation is not supported for views.
    #
    # Chúng không biến mất — `authz_schema` dựng `ix_memberships_user` và
    # `ix_memberships_tenant_scope` trên `memberships`. Truy vấn đi qua view
    # vẫn dùng được chúng, vì planner mở view ra thành truy vấn trên bảng nền
    # trước khi chọn đường đi.
    #
    # Câu tương đương cho "tenant nào còn quản trị viên" nằm ở
    # `ix_memberships_tenant_scope`: một tenant không còn quản trị viên thì
    # không quản trị được, và không gì trong lược đồ ngăn việc gỡ người cuối
    # cùng — API cưỡng chế điều đó, và chỉ mục là thứ làm phép kiểm ấy đủ rẻ để
    # chạy ở mỗi lần gỡ thành viên.
    # ---------------------------------------------------------------------
    # Thiết lập toàn nền tảng, đổi được lúc chạy.
    #
    # KHÔNG mang `tenant_id`: đây là dữ liệu VỀ cả bản triển khai, không thuộc
    # tenant nào — nên nó cũng không nằm trong TENANT_SCOPED_TABLES và không có
    # policy. Ghi vào bảng này chỉ đi qua `app/platform_settings.py`, nơi có
    # danh sách trắng khoá và kiểm biên giá trị.
    #
    # `value` là TEXT thay vì một cột cho mỗi kiểu: lớp Python ép kiểu khi đọc,
    # và một bảng khoá-giá trị với năm cột giá trị rỗng mỗi dòng là cái giá
    # không đáng trả cho tính an toàn kiểu mà danh sách trắng đã cung cấp.
    """
    CREATE TABLE IF NOT EXISTS platform_settings (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    # ---------------------------------------------------------------------
    # Văn bản pháp lý và chấp thuận.
    #
    # Vì sao KHÔNG phải một cột `accepted_terms BOOLEAN` trên `users`: cờ đó
    # trả lời được "người này có bấm không", nhưng không trả lời được câu hỏi
    # thật sự quan trọng — **bấm vào cái gì**. Ngày điều khoản đổi, mọi chữ ký
    # trở nên vô nghĩa và không có cách nào biết ai cần hỏi lại.
    #
    # `content_hash` là thứ biến bản ghi thành BẰNG CHỨNG: nó chứng minh bản văn
    # nào đã hiện trên màn hình, không chỉ số hiệu phiên bản. Sửa một câu mà
    # quên tăng phiên bản sẽ lộ ra ở hash.
    #
    # `requires_reconsent` tách hai loại thay đổi: sửa lỗi chính tả không nên
    # đá mọi người ra màn hình đồng ý; đổi phạm vi sử dụng dữ liệu thì phải.
    """
    CREATE TABLE IF NOT EXISTS legal_documents (
        doc_id             UUID PRIMARY KEY,
        kind               TEXT NOT NULL,
        version            TEXT NOT NULL,
        effective_from     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        content_hash       TEXT NOT NULL,
        url                TEXT NOT NULL,
        title              TEXT NOT NULL DEFAULT '',
        requires_reconsent BOOLEAN NOT NULL DEFAULT FALSE,
        -- v3.15: bản văn là TỆP (pdf/docx/odt) chứ không phải markdown gõ tay.
        -- NULL với bốn văn bản công bố trước v3.15 — chúng mang thân markdown,
        -- và có chữ ký trỏ vào `content_hash` của thân đó. Xem MIGRATION_STATEMENTS.
        file_key           TEXT,
        file_name          TEXT,
        file_mime          TEXT,
        file_size          BIGINT,
        language           TEXT NOT NULL DEFAULT 'vi',
        CONSTRAINT legal_documents_kind_valid CHECK (
            kind IN ('terms', 'privacy', 'data_contribution', 'guardian')
        ),
        CONSTRAINT legal_documents_kind_version_unique UNIQUE (kind, version)
    )
    """,
    # Một người, một loại văn bản, một chấp thuận CÒN HIỆU LỰC.
    #
    # Rút lại là `withdrawn_at`, không phải DELETE: lịch sử ai đồng ý với bản
    # nào vào lúc nào chính là thứ tài liệu này tồn tại để giữ. Xoá dòng là xoá
    # bằng chứng cho một câu hỏi sẽ được hỏi sau.
    """
    CREATE TABLE IF NOT EXISTS user_consents (
        consent_id   UUID PRIMARY KEY,
        user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        kind         TEXT NOT NULL,
        version      TEXT NOT NULL,
        accepted_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        ip_hash      TEXT,
        user_agent   TEXT,
        withdrawn_at TIMESTAMP WITH TIME ZONE,
        FOREIGN KEY (kind, version)
            REFERENCES legal_documents (kind, version) ON DELETE RESTRICT
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_consent_live "
    "ON user_consents (user_id, kind) WHERE withdrawn_at IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_consent_user ON user_consents (user_id)",
    # ---------------------------------------------------------------------
    # Invitations — the only way a person ends up in a tenant other than the
    # bootstrap one.
    #
    # Self-serve tenant signup is deliberately NOT offered: this platform serves
    # named institutions, so a tenant is created by a platform operator and
    # people are invited into it. That keeps the tenant list a curated set
    # rather than something an anonymous caller can grow.
    #
    # The token is never stored. `token_hash` is HMAC-SHA256 keyed by a pepper
    # held OUTSIDE the database (env), so reading every row of this table does
    # not let an attacker accept a single invitation. A bare SHA-256 would not
    # do: the token is high-entropy so preimage search is hopeless either way,
    # but the pepper is what makes a database-only compromise insufficient.
    #
    # `role` is on the INVITATION, not supplied at accept time — otherwise the
    # person accepting would be choosing their own authority.
    """
    CREATE TABLE IF NOT EXISTS tenant_invitations (
        invitation_id UUID PRIMARY KEY,
        tenant_id     TEXT NOT NULL,
        email         TEXT NOT NULL,
        -- NULL = mời vào tổ chức mà KHÔNG kèm vai nào ở tầng tenant. Cùng ba
        -- trạng thái và cùng lý do như `tenant_members.role` ở trên; hai cột
        -- phải nhận đúng một tập giá trị, vì `consume_invitation` chép thẳng
        -- cột này sang cột kia.
        role          TEXT,
        token_hash    TEXT NOT NULL UNIQUE,
        invited_by    UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        expires_at    TIMESTAMP WITH TIME ZONE NOT NULL,
        accepted_at   TIMESTAMP WITH TIME ZONE,
        accepted_by   UUID REFERENCES users(id) ON DELETE SET NULL,
        revoked_at    TIMESTAMP WITH TIME ZONE,
        CONSTRAINT tenant_invitations_role_valid
            CHECK (role IS NULL OR role IN ('admin', 'editor')),
        CONSTRAINT tenant_invitations_email_lower
            CHECK (email = lower(email)),
        -- One direction only. The symmetric version — `(accepted_at IS NULL) =
        -- (accepted_by IS NULL)` — was written first and is wrong: `accepted_by`
        -- is ON DELETE SET NULL, so hard-deleting the account that accepted an
        -- invitation nulls that column while `accepted_at` stays set, the CHECK
        -- fires, and the DELETE fails. An accepted invitation whose accepter was
        -- later removed is a real state; an accepter with no acceptance time is
        -- not, and that is the half worth forbidding.
        CONSTRAINT tenant_invitations_accept_is_complete
            CHECK (accepted_by IS NULL OR accepted_at IS NOT NULL)
    )
    """,
    # Cùng lượt tách membership khỏi role như `tenant_members` ở trên.
    #
    # Một lời mời ĐANG BAY mang vai 'viewer' sẽ trở thành lời mời không kèm vai.
    # Đó là hạ quyền, không phải nâng — người nhận vào tổ chức rồi chờ được cấp
    # vai, thay vì tự động đọc được hoá đơn và nhật ký kiểm toán. Đo trên sản
    # xuất 11/08/2026: 0 lời mời tồn tại, kể cả đã đóng.
    "ALTER TABLE tenant_invitations ALTER COLUMN role DROP DEFAULT",
    "ALTER TABLE tenant_invitations ALTER COLUMN role DROP NOT NULL",
    "UPDATE tenant_invitations SET role = NULL WHERE role = 'viewer'",
    """
    DO $$ BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'tenant_invitations_role_valid'
              AND pg_get_constraintdef(oid) LIKE '%%viewer%%'
        ) THEN
            ALTER TABLE tenant_invitations DROP CONSTRAINT tenant_invitations_role_valid;
            ALTER TABLE tenant_invitations ADD CONSTRAINT tenant_invitations_role_valid
                CHECK (role IS NULL OR role IN ('admin', 'editor'));
        END IF;
    END $$
    """,
    # Repair for any database that already got the symmetric version above.
    # CREATE TABLE IF NOT EXISTS does not revisit an existing table's constraints.
    """
    DO $$ BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'tenant_invitations_accept_is_complete'
              AND pg_get_constraintdef(oid) LIKE '%%accepted_at IS NULL) = (%%'
        ) THEN
            ALTER TABLE tenant_invitations
                DROP CONSTRAINT tenant_invitations_accept_is_complete;
            ALTER TABLE tenant_invitations
                ADD CONSTRAINT tenant_invitations_accept_is_complete
                CHECK (accepted_by IS NULL OR accepted_at IS NOT NULL);
        END IF;
    END $$
    """,
    # One live invitation per (tenant, email). Re-inviting someone who already
    # has an open invitation should replace it, not create a second valid token
    # — two live tokens means revoking one still leaves a way in.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_invitations_open "
    "ON tenant_invitations(tenant_id, email) "
    "WHERE accepted_at IS NULL AND revoked_at IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_tenant_invitations_tenant "
    "ON tenant_invitations(tenant_id, created_at DESC)",
    # ---------------------------------------------------------------------
    # One-time codes for email and phone verification, and for password reset.
    #
    # `code_hash` is HMAC-SHA256 keyed by a pepper held OUTSIDE the database
    # (app/tokens.py). A six-digit code has ~20 bits of entropy: a plain hash
    # would let anyone who can read this table build all one million digests in
    # under a second and reverse every outstanding code. The pepper is what
    # makes a database-only compromise insufficient.
    #
    # The code itself is NEVER stored and never logged — not at DEBUG, not in an
    # error, not in a metric label.
    #
    # `destination` is stored so a code issued to one address cannot be replayed
    # against another, and so a channel switch mid-flow can invalidate what came
    # before (see app/otp.py).
    #
    # No tenant_id: a challenge belongs to a person, and it exists before we know
    # which tenant that person is in — the same reason `users` reads are exempt
    # from row-level security during authentication.
    """
    CREATE TABLE IF NOT EXISTS verification_codes (
        challenge_id UUID PRIMARY KEY,
        user_id      UUID REFERENCES users(id) ON DELETE CASCADE,
        purpose      TEXT NOT NULL,
        channel      TEXT NOT NULL,
        destination  TEXT NOT NULL,
        code_hash    TEXT NOT NULL,
        attempts     INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 5,
        created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        expires_at   TIMESTAMP WITH TIME ZONE NOT NULL,
        consumed_at  TIMESTAMP WITH TIME ZONE,
        CONSTRAINT verification_codes_purpose_valid
            CHECK (purpose IN ('verify_email', 'verify_phone', 'reset_password')),
        CONSTRAINT verification_codes_channel_valid
            CHECK (channel IN ('email', 'sms')),
        CONSTRAINT verification_codes_attempts_bounded
            CHECK (attempts >= 0 AND attempts <= max_attempts)
    )
    """,
    # At most ONE live challenge per (user, purpose), across BOTH channels.
    #
    # This is the answer to "asked for a reset by email, came back and chose
    # phone": issuing the second challenge closes the first, and the index makes
    # the database refuse to hold two. Without it the email code stays valid
    # after the person switched — a code sitting in an inbox that still opens the
    # account, which is precisely the situation a channel switch is meant to end.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_verification_codes_live "
    "ON verification_codes(user_id, purpose) WHERE consumed_at IS NULL",
    # Sweeping expired rows: they are dead weight and every one is a digest.
    "CREATE INDEX IF NOT EXISTS idx_verification_codes_expiry "
    "ON verification_codes(expires_at)",
    # Verification state lives on the account, not on the challenge — the
    # challenge is deleted or expires, the fact that the address was proven does
    # not. NULL means "never verified", which is the honest state for every
    # account that predates this table.
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified_at TIMESTAMP WITH TIME ZONE",
    # ---------------------------------------------------------------------
    # Every `tenant_id` actually references a tenant.
    #
    # Twelve tables carried this column and NOT ONE had a foreign key, so a
    # typo'd tenant id was accepted everywhere and only discovered — if ever —
    # by noticing the rows were unreachable. `clone_catalog_to_tenant` made
    # that concrete: it writes a full catalogue keyed by tenant_id and then runs
    # `UPDATE tenants SET cloned_from_community_version WHERE tenant_id = ...`,
    # which silently matches zero rows for an id that does not exist. Half the
    # write lands, the provenance half does not, and nothing reports it.
    # routers/vocabulary.py checks before writing; this makes the database
    # refuse regardless of which code path is used, now or later.
    #
    # ON DELETE RESTRICT, never CASCADE: `tenants` soft-deletes (`deleted_at`),
    # so a hard DELETE is already a mistake — and one that would otherwise take
    # every class, sample and upload of that tenant with it. RESTRICT turns that
    # mistake into an error message.
    #
    # ON UPDATE RESTRICT for the same reason `dialect_id` is immutable: the id
    # names directories and published artifacts, so cascading a rename through
    # the database would leave the filesystem behind.
    #
    # Applied in one guarded loop: skips tables that do not exist yet on this
    # machine, skips constraints already present, and downgrades a genuine
    # failure (pre-existing orphan rows) to a WARNING rather than aborting
    # startup — `missing_tenant_foreign_keys()` is what reports the result, so a
    # skipped constraint cannot pass for a present one.
    TENANT_FK_LOOP_SQL,
    # Display order is data, not alphabetical luck. Ordering profiles by
    # profile_id put them in abc order (alphabet, central, hoa_de, …) while the
    # intended order is geographic (alphabet, north, central, south, hoa_de);
    # "alphabet" only stayed first by coincidence, and one new profile named
    # "aa*" would have silently reshuffled every dropdown.
    "ALTER TABLE recognition_profiles ADD COLUMN IF NOT EXISTS display_order INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE dialects ADD COLUMN IF NOT EXISTS display_order INTEGER NOT NULL DEFAULT 0",
    # ---------------------------------------------------------------------
    # Parity with samples/raw_uploads: per-user training history queries
    "CREATE INDEX IF NOT EXISTS idx_training_jobs_auth_user_id ON training_jobs(auth_user_id)",
    # Sync status tracking table for Google Sheets auto-rotation
    """
    CREATE TABLE IF NOT EXISTS google_sheets_sync_status (
        id SERIAL PRIMARY KEY,
        table_name VARCHAR(50) UNIQUE NOT NULL,
        current_spreadsheet_id VARCHAR(100) NOT NULL DEFAULT '',
        current_sheet_index INT NOT NULL DEFAULT 1,
        current_data_rows INT NOT NULL DEFAULT 0,
        max_rows_per_sheet INT NOT NULL DEFAULT 500000,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
    """,
    # Forgot-password flow: stores a hash of the reset token (never the raw
    # token) so a leaked DB dump can't be used to reset accounts directly.
    """
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        token_hash TEXT PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        used_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    # Refresh tokens for the cookie session flow. Only a sha256 hash of the
    # token is stored (a leaked DB dump can't be replayed). Rotated on every
    # refresh (old row gets revoked_at) and revoked on logout.
    """
    CREATE TABLE IF NOT EXISTS refresh_tokens (
        token_hash TEXT PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        revoked_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        -- Ho token: MOT lan dang nhap = MOT ho. Xoay token giu nguyen family_id,
        -- nen phat hien tai su dung co the dot ca ho chu khong chi mot ban ghi.
        family_id UUID,
        -- Bam cua token ke nhiem. Chi de DIEU TRA (dung lai chuoi xoay khi co su
        -- co); khong duong chay nao doc no de quyet dinh.
        replaced_by TEXT,
        -- Khac NULL = ho nay da bi dot vi tai su dung. Mot khi da dat, moi token
        -- trong ho deu chet vinh vien, ke ca token chua het han.
        reuse_detected_at TIMESTAMP WITH TIME ZONE
    )
    """,
    # SOT writer registry (admin-managed via the SOT admin page). Unioned with the
    # committed authorized_keys.json baseline by reader_sync.effective_authorized_keys,
    # so a machine registered here is trusted by this deployment's reader WITHOUT a
    # git commit / redeploy. Public keys are not secret; the private key never leaves
    # the writer machine (or is downloaded once when the server generates the pair).
    """
    CREATE TABLE IF NOT EXISTS sot_authorized_keys (
        public_key TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        fingerprint TEXT NOT NULL,
        note TEXT,
        added_by TEXT,
        added_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        revoked_at TIMESTAMP WITH TIME ZONE
    )
    """,
    # ---------------------------------------------------------------------
    # Integrity constraints. Last in the list, because each one needs the
    # tables above to exist. They live here rather than in the CREATE TABLE
    # bodies so that databases predating them get them too — ensure_tables()
    # runs this list on every startup, and CREATE ... IF NOT EXISTS / the
    # duplicate_object catch makes each one idempotent.
    #
    # Every constraint corresponds to damage that actually happened to this
    # dataset, not to a hypothetical:
    #
    #  - two classes sharing a class_idx silently merge two labels into one
    #    model output slot (class_idx IS the output index — dataset_loader.py
    #    maps class_idx-1 to the tensor index), and nothing prevented it;
    #  - a sample_uid is uuid4().hex[:10], so it is always 10 lowercase hex
    #    chars. One row reached the DB as '7,69E+10' because a uid of the form
    #    <digits>e<digits> ("7690373e04") is valid scientific notation, and a
    #    round-trip through a spreadsheet converted it to a float. The CHECK
    #    rejects that at the door instead of leaving an unjoinable row behind;
    #  - file_path is a local path; 728 rows once held a Drive URL there after
    #    a sync wrote to the wrong column, which made every file lookup miss;
    #  - samples.class_uid had no FK, so a class delete that ran before its
    #    samples were deleted left orphans no class-scoped query could see.
    #
    # The partial WHERE deleted_at IS NULL is deliberate: soft-deleted rows sit
    # in the Trash and must not block a new class reusing the same slug/idx.
    #
    # Both are scoped by tenant_id — see the multi-tenant block above. With one
    # tenant they are exactly equivalent to the global versions they replace.
    # `uq_classes_tenant_slug_lang_dialect` (không có `region`) ĐÃ ĐƯỢC GỠ khỏi
    # đây, không chỉ thêm một câu DROP. Lý do, và nó là một bài học đắt:
    #
    # Câu DROP nằm trong danh sách MỘT CHIỀU nên KHÔNG chạy lúc khởi động —
    # đúng thiết kế, khởi động chỉ được phép THÊM. Nhưng câu CREATE thì lại
    # chạy mọi lần khởi động. Kết quả: migration bỏ chỉ mục cũ, rồi backend
    # khởi động lại và dựng nó lên nguyên vẹn, và ba biến thể vùng lại bị chặn.
    # Đã đo đúng như vậy trên `signdb` ngày 14/08.
    #
    # Quy tắc rút ra: retire một đối tượng thì phải GỠ câu tạo nó, chứ thêm
    # câu xoá là chưa đủ.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_classes_tenant_class_idx "
    "ON classes(tenant_id, class_idx) WHERE deleted_at IS NULL AND class_idx IS NOT NULL",
    # -----------------------------------------------------------------------
    # v3.18 — `region` bước vào ĐỊNH DANH của lớp, không chỉ là chú thích.
    #
    # v3.17 thêm cột `region` nhưng để nguyên khoá duy nhất. Hệ quả đo được:
    # ba dạng miền của cùng một từ (từ điển quốc gia ghi nhận 483 từ như vậy)
    # có chung `slug`, `language` và `dialect`, nên dòng thứ hai và thứ ba bị
    # khoá duy nhất từ chối. Cột `region` khi đó chỉ ghi chú được cho những lớp
    # vốn đã một dạng — đúng thứ nó sinh ra để khắc phục thì lại chưa làm được.
    #
    # `region` trần, KHÔNG `coalesce`
    # -------------------------------
    # Bản đầu phải bọc `coalesce(region,'')`, vì cột khi đó nhận NULL và hai
    # NULL không đụng nhau trong chỉ mục duy nhất — tức hai lớp trùng hệt nhau
    # lọt qua chỉ bằng cách để `region` là NULL. v3.19 đặt `NOT NULL` kèm khoá
    # ngoại tới `regions`, nên lỗ đó không còn tồn tại để phải bọc.
    #
    # Chỗ lưu KHÔNG đổi: `folder_name()` là `class_{slug}_{class_uid[:8]}`, mà
    # ba biến thể có ba `class_uid`, nên chúng đã tự tách thư mục. Không phải
    # di dời tệp nào.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_classes_tenant_slug_lang_dialect_region "
    "ON classes(tenant_id, slug, language, dialect, region) "
    "WHERE deleted_at IS NULL",
    # Retire bản không có `region` chỉ SAU khi bản có đã tồn tại, để không có
    # khoảnh khắc nào cả hai cùng vắng. Một chiều, nên chỉ chạy dưới lệnh
    # migration — xem `one_way_statements()`.
    *_DROP_PRE_REGION_CLASS_UNIQUE,
    # Retire the global predecessors only AFTER the scoped ones exist, so the
    # guarantee is never absent in between. Một chiều, nên chỉ chạy dưới lệnh
    # migration — xem `ONE_WAY_STATEMENTS`.
    *_DROP_GLOBAL_CLASS_UNIQUES,
    """
    DO $$ BEGIN
        ALTER TABLE samples ADD CONSTRAINT samples_uid_is_hex10
            CHECK (sample_uid ~ '^[0-9a-f]{10}$');
    EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """,
    """
    DO $$ BEGIN
        ALTER TABLE samples ADD CONSTRAINT samples_file_path_is_local
            CHECK (file_path IS NULL OR file_path NOT LIKE 'http%');
    EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """,
    # `samples_class_uid_fkey` (một cột) từng được thêm ở đây. Nó đã được thay
    # bằng `fk_samples_class_tenant` ghép cả tenant_id ở v3.12 — bản một cột
    # cho phép mẫu của tenant A trỏ sang lớp của tenant B. Câu thêm bị gỡ khỏi
    # đây chứ không chỉ thêm câu xoá ở dưới, nếu không mỗi lần khởi động sẽ
    # thêm rồi xoá lại đúng ràng buộc đó.
    # =====================================================================
    # Schema v3 — 2026-08-08. Bảng mồ côi, liên kết mồ côi, bảng trung gian.
    # Thiết kế, số đo và ERD: docs/02-data/SAAS_SCHEMA_DESIGN.md §9sexies.
    #
    # Nguyên tắc của cả khối: THÊM, KHÔNG SỬA. Không câu nào ở đây ghi đè hay
    # xoá dữ liệu đang có. Ba chỗ cố ý để trống thay vì đoán — 997 mẫu
    # `session_id` rỗng, 100/250 phiên không rõ người ký, 90 job cũ không có
    # tập lớp — lý do ghi tại chỗ ở v3.3, v3.6 và v3.10.
    #
    # ---------------------------------------------------------------------
    # v3.1 — Đích cho khoá ngoại ghép. `classes` và `signers` có khoá chính một
    # cột nên không làm đích cho khoá (tenant_id, x) được. Chỉ mục duy nhất bổ
    # khuyết mà không phải mổ khoá chính, và cho đúng sự bảo đảm cần thiết: mẫu
    # của tenant A không trỏ sang lớp của tenant B.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_classes_tenant_class_uid "
    "ON classes(tenant_id, class_uid)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_signers_tenant_signer_id "
    "ON signers(tenant_id, signer_id)",
    # ---------------------------------------------------------------------
    # v3.2 — Nhóm từ vựng. `classes.vocabulary_group` đang là chữ tự do với 5
    # giá trị; không có bảng nào để tra tên hiển thị hay thứ tự, nên mọi
    # dropdown phải tự đoán.
    """
    CREATE TABLE IF NOT EXISTS vocabulary_groups (
        tenant_id     TEXT NOT NULL,
        group_id      TEXT NOT NULL,
        display_name  TEXT NOT NULL,
        display_order INTEGER NOT NULL DEFAULT 0,
        is_active     BOOLEAN NOT NULL DEFAULT TRUE,
        created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        PRIMARY KEY (tenant_id, group_id),
        CONSTRAINT vocabulary_groups_id_not_blank CHECK (group_id <> '')
    )
    """,
    # ---------------------------------------------------------------------
    # v3.3 — Phiên thu: 6 endpoint trong `label_sessions.py` thao tác trên thực
    # thể này mà không có bảng nào.
    #
    # Khoá tự nhiên (tenant_id, class_uid, session_id) là ĐÚNG cặp mà router
    # dùng làm danh tính; `session_id` một mình không đủ vì 31 giá trị của nó
    # trải trên nhiều lớp. Khoá chính vẫn là UUID thay thế để `samples` trỏ tới
    # bằng MỘT cột — khoá ngoại ba cột sẽ buộc `session_id` thành NOT NULL,
    # trong khi 997 dòng đang rỗng.
    #
    # Không có cột đếm số mẫu: bộ đếm phi chuẩn hoá lệch ngay lần xoá mềm đầu
    # tiên, và `count(*)` trên `idx_samples_capture_session` rẻ hơn một số sai.
    """
    CREATE TABLE IF NOT EXISTS capture_sessions (
        capture_session_id UUID PRIMARY KEY,
        tenant_id    TEXT NOT NULL,
        class_uid    TEXT NOT NULL,
        session_id   TEXT NOT NULL,
        signer_id    TEXT,
        auth_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
        source_type  TEXT,
        started_at   TIMESTAMP WITH TIME ZONE,
        ended_at     TIMESTAMP WITH TIME ZONE,
        note         TEXT,
        created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_capture_sessions_natural
            UNIQUE (tenant_id, class_uid, session_id),
        CONSTRAINT capture_sessions_session_id_not_blank
            CHECK (session_id <> ''),
        CONSTRAINT capture_sessions_ends_after_start
            CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at)
    )
    """,
    # ---------------------------------------------------------------------
    # v3.4 — Đồng ý của NGƯỜI KÝ, tách khỏi đồng ý của CHỦ TÀI KHOẢN.
    #
    # `user_consents` ghi đồng ý của CHỦ TÀI KHOẢN. Người xuất hiện trong video
    # thường là người khác, và có thể là trẻ vị thành niên — nên bảng riêng.
    # `scope` ba mức tăng dần: đồng ý huấn luyện nội bộ KHÔNG kéo theo đồng ý
    # công bố công khai. Đây là thứ chặn thư viện video mẫu, và giờ chặn bằng
    # một câu SQL kiểm được thay vì bằng trí nhớ.
    """
    CREATE TABLE IF NOT EXISTS signer_consents (
        consent_id   UUID PRIMARY KEY,
        tenant_id    TEXT NOT NULL,
        signer_id    TEXT NOT NULL,
        scope        TEXT NOT NULL,
        kind         TEXT NOT NULL,
        version      TEXT NOT NULL,
        granted_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        withdrawn_at TIMESTAMP WITH TIME ZONE,
        guardian_name TEXT,
        evidence     TEXT,
        recorded_by  UUID REFERENCES users(id) ON DELETE SET NULL,
        CONSTRAINT signer_consents_scope_valid
            CHECK (scope IN ('internal_training', 'research_release', 'public_library')),
        CONSTRAINT signer_consents_withdraw_after_grant
            CHECK (withdrawn_at IS NULL OR withdrawn_at >= granted_at)
    )
    """,
    # Một đồng ý còn hiệu lực cho mỗi (người ký, mức). Rút rồi cấp lại là hai
    # dòng, và dòng cũ giữ nguyên `withdrawn_at` — lịch sử đồng ý là bằng
    # chứng, không được ghi đè.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_signer_consents_live "
    "ON signer_consents(tenant_id, signer_id, scope) WHERE withdrawn_at IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_signer_consents_signer "
    "ON signer_consents(tenant_id, signer_id)",
    # ---------------------------------------------------------------------
    # v3.5 — Bí danh người ký, theo đúng khuôn `dialect_aliases` đã có.
    #
    # `samples.user_id` chứa "Trâm"/"Tram", "Thu Ngân"/"Thungan"/"Ngan" — gần
    # chắc cùng người — và một dòng có nguyên UUID lọt vào ô tên. Gộp là quyết
    # định của con người, không phải của migration; bảng này ghi quyết định đó
    # kèm lý do, để mẫu cũ trỏ tới id đã gộp vẫn tra ngược được.
    """
    CREATE TABLE IF NOT EXISTS signer_aliases (
        tenant_id     TEXT NOT NULL,
        old_signer_id TEXT NOT NULL,
        new_signer_id TEXT NOT NULL,
        reason        TEXT,
        merged_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        merged_by     UUID REFERENCES users(id) ON DELETE SET NULL,
        PRIMARY KEY (tenant_id, old_signer_id),
        CONSTRAINT signer_aliases_not_self CHECK (old_signer_id <> new_signer_id)
    )
    """,
    # ---------------------------------------------------------------------
    # v3.6 — BẢNG TRUNG GIAN job ↔ lớp: hợp đồng đầu ra của một model.
    #
    # `config` chỉ lưu BỘ LỌC (`{"dialects": ["bang-chu-cai"]}`), không lưu tập
    # lớp đã giải — nên "model xuất ra nhãn nào ở chỉ số nào" hiện không có ở
    # đâu, dù `class_idx` LÀ chỉ số đầu ra của tensor.
    #
    # KHÔNG backfill 90 job cũ: giải bộ lọc bằng danh mục hôm nay cho ra tập
    # lớp của hôm nay, không phải của lúc train. Xuất xứ bịa tệ hơn ô trống.
    #
    # `label` đóng băng tại chỗ chứ không join sang `classes` — đổi tên một lớp
    # không được đổi nhãn mà model đã phát hành đang mang. `class_uid` là
    # ON DELETE SET NULL vì hiện vật phải sống lâu hơn lớp.
    """
    CREATE TABLE IF NOT EXISTS training_job_classes (
        job_id    TEXT NOT NULL REFERENCES training_jobs(job_id) ON DELETE CASCADE,
        class_idx INTEGER NOT NULL,
        class_uid TEXT,
        label     TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        PRIMARY KEY (job_id, class_idx)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_training_job_classes_class "
    "ON training_job_classes(class_uid)",
    # ---------------------------------------------------------------------
    # v3.7 — Nhật ký kiểm toán bền.
    #
    # `activity.py` ghi vào Redis, cấu hình `volatile-lru` 400mb — dấu vết bị
    # ĐUỔI khi hết chỗ. Sudo mode và việc đổi hạn mức lúc chạy hiện không để
    # lại gì tồn tại qua một lần restart.
    #
    # `tenant_id` cho phép NULL cho hành động tầng nền tảng. Với vị từ RLS dùng
    # chung, `NULL = 'x'` cho ra NULL nên dòng đó chỉ hiện trong system scope —
    # đúng ý muốn.
    #
    # `detail` không bao giờ chứa bí mật. Ràng buộc đó không viết được bằng SQL
    # nên nó nằm ở `app/audit.py`, lối vào duy nhất của bảng này.
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        audit_id      BIGSERIAL PRIMARY KEY,
        tenant_id     TEXT,
        actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
        actor_label   TEXT,
        action        TEXT NOT NULL,
        target_type   TEXT,
        target_id     TEXT,
        detail        JSONB,
        ip_hash       TEXT,
        created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT audit_log_action_not_blank CHECK (action <> '')
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor_user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_target ON audit_log(target_type, target_id)",
    # ---------------------------------------------------------------------
    # v3.8 — Cột mới trên bảng cũ. Đều là THÊM, không cột nào bị ghi đè.
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS capture_session_id UUID",
    "ALTER TABLE signers ADD COLUMN IF NOT EXISTS note TEXT",
    "ALTER TABLE signers ADD COLUMN IF NOT EXISTS display_order INTEGER NOT NULL DEFAULT 0",
    # Phiên bản danh mục mà job đã dùng. Để NULL cho 90 job cũ vì không suy ra
    # được — cùng lý do như v3.6.
    "ALTER TABLE training_jobs ADD COLUMN IF NOT EXISTS registry_version BIGINT",
    # ---------------------------------------------------------------------
    # v3.9 — Chuẩn hoá chuỗi rỗng thành NULL, CHỈ ở những cột sắp có khoá
    # ngoại. '' và NULL cùng nghĩa "không có" ở các cột này, nhưng khoá ngoại
    # phân biệt: NULL được miễn, '' thì phải tồn tại thật. Không đụng tới
    # `samples.session_id` — 997 dòng rỗng ở đó được xử lý bằng cách để
    # `capture_session_id` NULL, chứ không sửa cột gốc.
    "UPDATE classes SET vocabulary_group = NULL WHERE vocabulary_group = ''",
    "UPDATE classes SET recognition_profile = NULL WHERE recognition_profile = ''",
    "UPDATE classes SET language = NULL WHERE language = ''",
    "UPDATE dialects SET language = NULL WHERE language = ''",
    "UPDATE dialects SET merged_into = NULL WHERE merged_into = ''",
    "UPDATE samples SET signer_id = NULL WHERE signer_id = ''",
    # ---------------------------------------------------------------------
    # v3.10 — Backfill. Mỗi câu idempotent: chạy lại lần hai không đổi gì.
    #
    # `languages` thôi mồ côi: nạp mọi mã ngôn ngữ đang thực sự được dùng, rồi
    # khoá ngoại ở v3.11 biến bảng thành thứ chặn 'vn'/'vi'/'VN' trôi dạt.
    """
    INSERT INTO languages (code, name)
    SELECT DISTINCT lang, lang FROM (
        SELECT language AS lang FROM classes  WHERE language IS NOT NULL
        UNION SELECT language        FROM dialects WHERE language IS NOT NULL
        UNION SELECT language        FROM samples  WHERE language IS NOT NULL
    ) s
    ON CONFLICT (code) DO NOTHING
    """,
    """
    INSERT INTO vocabulary_groups (tenant_id, group_id, display_name)
    SELECT DISTINCT c.tenant_id, c.vocabulary_group, c.vocabulary_group
    FROM classes c
    WHERE c.vocabulary_group IS NOT NULL
    ON CONFLICT (tenant_id, group_id) DO NOTHING
    """,
    # 899 mẫu trỏ tới S010/S011 — hai id không có dòng nào trong `signers`.
    # Tạo dòng cho chúng thay vì gỡ tham chiếu: gỡ là mất thông tin, tạo là
    # giữ. `note` nói rõ đây là dòng máy sinh, và `display_name` bằng chính id
    # để không ai nhầm nó với một cái tên đã được xác nhận.
    """
    INSERT INTO signers (signer_id, display_name, tenant_id, is_active, created_at, note)
    SELECT DISTINCT s.signer_id, s.signer_id, s.tenant_id, TRUE, NOW(),
           'tu sinh 2026-08-08 khi va khoa ngoai: samples tham chieu signer_id chua co dong'
    FROM samples s
    WHERE s.signer_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM signers g
          WHERE g.tenant_id = s.tenant_id AND g.signer_id = s.signer_id)
    ON CONFLICT DO NOTHING
    """,
    # Phiên thu. `array_agg(...)[1]` vì Postgres không có `min(uuid)`.
    #
    # Ba câu CASE là mấu chốt: 15 nhóm chứa NHIỀU người ký, nên lấy đại một
    # người là tạo khẳng định sai. Chỉ điền khi nhóm đồng nhất, còn lại NULL.
    # `started_at`/`ended_at` thì luôn điền được vì min/max là phép ĐO trên
    # chính nhóm đó, không phải một lựa chọn đại diện.
    """
    INSERT INTO capture_sessions (
        capture_session_id, tenant_id, class_uid, session_id,
        signer_id, auth_user_id, source_type, started_at, ended_at)
    SELECT gen_random_uuid(), s.tenant_id, s.class_uid, s.session_id,
           CASE WHEN count(DISTINCT s.signer_id) = 1
                THEN (array_agg(s.signer_id) FILTER (WHERE s.signer_id IS NOT NULL))[1]
           END,
           CASE WHEN count(DISTINCT s.auth_user_id) = 1
                THEN (array_agg(s.auth_user_id) FILTER (WHERE s.auth_user_id IS NOT NULL))[1]
           END,
           CASE WHEN count(DISTINCT s.source_type) = 1
                THEN (array_agg(s.source_type) FILTER (WHERE s.source_type IS NOT NULL))[1]
           END,
           min(s.created_at), max(s.created_at)
    FROM samples s
    WHERE s.class_uid IS NOT NULL AND s.session_id IS NOT NULL AND s.session_id <> ''
    GROUP BY s.tenant_id, s.class_uid, s.session_id
    ON CONFLICT (tenant_id, class_uid, session_id) DO NOTHING
    """,
    """
    UPDATE samples s SET capture_session_id = cs.capture_session_id
    FROM capture_sessions cs
    WHERE s.capture_session_id IS NULL
      AND cs.tenant_id = s.tenant_id
      AND cs.class_uid = s.class_uid
      AND cs.session_id = s.session_id
    """,
    # ĐÃ GỠ: lượt backfill `users` → `tenant_members` của v3.
    #
    # Nó chạy đúng một lần, năm 2026, khi `tenant_members` còn rỗng trong khi
    # `users` đã có 10 dòng. Từ đó tới nay nó không còn chạy được nữa, và giờ
    # thì không còn chạy được trên BẤT KỲ cơ sở dữ liệu nào — vì ba lý do
    # chồng lên nhau, mỗi lý do đủ để nó ngã:
    #
    #   * `roles.id` và `users.role_id` không còn tồn tại (PDM v5 đổi `roles`
    #     sang `role_id`/`role_code`, và `users.role_id` đã bị bỏ từ trước).
    #   * `tenant_members` giờ là VIEW, và `ON CONFLICT` không bám được vào
    #     view — xem chú thích ở `tenant_admin.add_member`.
    #   * Nó gán `'viewer'`, một giá trị mà `tenant_members_role_valid` không
    #     còn cho phép.
    #
    # `_run_ddl` nuốt lỗi nên nó chỉ để lại một dòng cảnh báo ở MỖI lần khởi
    # động, mãi mãi. Xoá thay vì sửa: không có dữ liệu nào để nó di trú nữa.
    # ---------------------------------------------------------------------
    # v3.11 — `signers.external_user_id`: TEXT không khoá ngoại  →  UUID có
    # khoá ngoại. Đây là cái lỗ đã để 20 dòng rác sống sót qua một đợt dọn.
    #
    # Giá trị treo được CHÉP vào `note` trước khi gỡ. Một con trỏ trỏ vào hư
    # không thì vô dụng, nhưng biết nó từng trỏ đi đâu thì không — đó là bằng
    # chứng để lần ra dòng rác về sau.
    """
    DO $$ BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'signers'
              AND column_name = 'external_user_id' AND data_type <> 'uuid'
        ) THEN
            UPDATE signers SET note = concat_ws(' | ', note,
                       'external_user_id treo, go 2026-08-08: ' || external_user_id)
             WHERE external_user_id IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id::text = signers.external_user_id);
            UPDATE signers SET external_user_id = NULL
             WHERE external_user_id IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id::text = signers.external_user_id);
            ALTER TABLE signers
                ALTER COLUMN external_user_id TYPE UUID USING external_user_id::uuid;
        END IF;
    END $$
    """,
    # ---------------------------------------------------------------------
    # v3.12 — Khoá ngoại vá từng liên kết mồ côi.
    #
    # Một vòng lặp có bảo vệ, cùng khuôn với khối khoá ngoại tenant ở trên:
    # bỏ qua bảng chưa có, bỏ qua ràng buộc đã có, và hạ một thất bại thật
    # (còn dòng vi phạm) xuống WARNING thay vì làm chết khởi động. Đây là lý
    # do `missing_integrity_constraints()` tồn tại — "migration đã chạy" và
    # "ràng buộc đang có" là hai chuyện khác nhau, và chỉ chuyện thứ hai bảo
    # vệ được gì đó.
    f"""
    DO $$
    DECLARE
        spec text;
        parts text[];
    BEGIN
        FOREACH spec IN ARRAY ARRAY[{", ".join(repr(s) for s in INTEGRITY_FK_SPECS)}] LOOP
            parts := string_to_array(spec, '~');
            CONTINUE WHEN to_regclass('public.' || parts[1]) IS NULL;
            CONTINUE WHEN EXISTS (SELECT 1 FROM pg_constraint WHERE conname = parts[2]);
            BEGIN
                EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I %s',
                               parts[1], parts[2], parts[3]);
            EXCEPTION WHEN others THEN
                RAISE WARNING '[INTEGRITY_FK] % skipped: %', parts[2], SQLERRM;
            END;
        END LOOP;
    END $$
    """,
    # Khoá ngoại ghép (tenant_id, class_uid) bao trùm hoàn toàn khoá ngoại một
    # cột có từ trước, nên giữ cả hai là thừa một lần tra chỉ mục mỗi lần chèn.
    # Bỏ cái cũ SAU khi cái mới đã vào — thứ tự này khiến sự bảo đảm không
    # biến mất một khoảnh khắc nào.
    """
    DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_samples_class_tenant')
        THEN
            ALTER TABLE samples DROP CONSTRAINT IF EXISTS samples_class_uid_fkey;
        END IF;
    END $$
    """,
    # ---------------------------------------------------------------------
    # v3.12b — Email của tài khoản luôn là chữ thường, ép ở CƠ SỞ DỮ LIỆU.
    #
    # `create_user` hạ chữ thường, nhưng đó là MỘT đường ghi — đồng bộ CSV và
    # công cụ quản trị ghi thẳng vào `users`. Một hàng chữ hoa lọt vào thì
    # `uq_users_tenant_email` (trên cột thô) coi 'A@x.com' và 'a@x.com' là hai
    # địa chỉ, và `_fetch_user_by_login` dùng `LIMIT 1` KHÔNG ORDER BY — hàng
    # nào trả về là do Postgres quyết định. `tenant_invitations` đã có ràng
    # buộc này; `users` quan trọng hơn mà đang yếu hơn. Đã đo: 10/10 hàng hiện
    # có đều chữ thường.
    """
    DO $$ BEGIN
        ALTER TABLE users ADD CONSTRAINT users_email_lower
            CHECK (email = lower(email));
    EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """,
    # ---------------------------------------------------------------------
    # v3.13 — Chỉ mục cho các đường join mới.
    "CREATE INDEX IF NOT EXISTS idx_samples_capture_session "
    "ON samples(capture_session_id)",
    "CREATE INDEX IF NOT EXISTS idx_capture_sessions_class "
    "ON capture_sessions(tenant_id, class_uid)",
    "CREATE INDEX IF NOT EXISTS idx_capture_sessions_signer "
    "ON capture_sessions(tenant_id, signer_id)",
    "CREATE INDEX IF NOT EXISTS idx_training_metrics_job ON training_metrics(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_classes_vocabulary_group "
    "ON classes(tenant_id, vocabulary_group)",
    # ---------------------------------------------------------------------
    # v3.14 — Bỏ bảng chết, có bảo vệ.
    #
    # `user_profiles`: 0 dòng, 0 dòng Python nào chạm tới. Điều kiện
    # `count(*) = 0` khiến câu này không thể mất dữ liệu trên bất kỳ máy nào.
    #
    # `roles` thì KHÔNG bỏ dù cũng không ai đọc: nó có 3 dòng thật và 5 tài
    # khoản trỏ tới. Dữ liệu đã chuyển sang `tenant_members.role` ở v3.10; bỏ
    # nguồn ngay trong cùng lần chạy là tự tước đường đối chiếu.
    #
    # Hai `IF` LỒNG NHAU, không phải `IF ... AND ...`: PL/pgSQL lập kế hoạch cả
    # biểu thức trước khi chạy, nên vế phải vẫn bị phân tích sau khi bảng đã bị
    # xoá và đẻ ra cảnh báo mỗi lần khởi động. `EXECUTE` hoãn việc đó lại.
    _DROP_DEAD_USER_PROFILES,
    # Bỏ DEFAULT của `users.tenant_id` (16/08/2026). Nằm ở ĐÂY thì
    # `app.cli.migrate` mới chạy nó; chỉ đăng ký vào `one_way_statements()`
    # thôi thì câu lệnh bị LOẠI khỏi đường khởi động mà cũng không bao giờ
    # được thi hành ở đâu cả — một câu "đã đăng ký" nhưng chết. Đo lại thấy
    # đúng như vậy trước khi thêm dòng này.
    _DROP_USERS_TENANT_DEFAULT,
    _DROP_TRAINING_JOBS_TENANT_DEFAULT,
    # ---------------------------------------------------------------------
    # C3 (16/08/2026) — `training_metrics` nhận quyền sở hữu.
    #
    # Trước lượt này bảng con không có `tenant_id` và không có RLS, trong khi
    # bảng cha có cả hai. Quyền sở hữu của đầu ra đứt đúng ở đó: cổng duy nhất
    # bảo vệ chỉ số là hàng job cha, nên bất kỳ đường đọc nào bỏ qua hàng cha
    # là đọc được chỉ số của mọi tổ chức.
    #
    # THỨ TỰ dưới đây là hợp đồng, không phải sở thích:
    #
    #   1  thêm cột NULLABLE          — chưa ràng buộc gì, chưa hỏng được gì
    #   2  backfill từ job cha        — bước dữ liệu, có hậu điều kiện HAI vế
    #   3  SET NOT NULL               — chỉ hợp lệ sau khi (2) đã chứng minh
    #   4  UNIQUE(tenant_id, job_id)  — đích cho khoá ngoại ghép
    #   5  khoá ngoại GHÉP            — CSDL tự chặn metric.tenant ≠ job.tenant
    #
    # Đi thẳng tới `NOT NULL` sẽ hỏng trên mọi máy đã có dữ liệu, và đi thẳng
    # tới khoá ngoại ghép sẽ hỏng vì chưa có đích UNIQUE.
    "ALTER TABLE training_metrics ADD COLUMN IF NOT EXISTS tenant_id TEXT",
    _SQL_BACKFILL_METRIC_TENANT,
    _SQL_METRIC_TENANT_NOT_NULL,
    # Đích của khoá ngoại ghép. `job_id` vốn đã là khoá chính nên ràng buộc này
    # không thu hẹp gì — nó chỉ tạo ra thứ mà `REFERENCES (tenant_id, job_id)`
    # cần để tồn tại.
    """
    DO $$ BEGIN
        ALTER TABLE training_jobs
            ADD CONSTRAINT uq_training_jobs_tenant_job UNIQUE (tenant_id, job_id);
    EXCEPTION WHEN duplicate_table OR duplicate_object THEN NULL;
    END $$
    """,
    # ★ Lưới thứ hai, và là lưới KHÔNG phụ thuộc mã ứng dụng.
    #
    # Khoá ngoại ghép làm PostgreSQL tự từ chối trạng thái
    # `metric.tenant_id = A` trong khi `job.tenant_id = B`. Nếu chỉ trông vào
    # việc worker truyền đúng tenant thì một lượt gọi sai sẽ tạo ra một hàng
    # trông hợp lệ với mọi phép kiểm phía trên nó.
    """
    DO $$ BEGIN
        ALTER TABLE training_metrics
            ADD CONSTRAINT fk_training_metrics_job_tenant
            FOREIGN KEY (tenant_id, job_id)
            REFERENCES training_jobs(tenant_id, job_id) ON DELETE CASCADE;
    EXCEPTION WHEN duplicate_table OR duplicate_object THEN NULL;
    END $$
    """,
    # =====================================================================
    # v4 — MẶT PHẲNG THƯƠNG MẠI VÀ VÒNG ĐỜI KHÁCH HÀNG
    #
    # v3 làm cho dữ liệu đúng. v4 làm cho nó bán được: gói và hạn mức, số đo
    # mức dùng, khoá API, webhook, xuất dữ liệu và xoá vĩnh viễn.
    #
    # Đặt TRƯỚC vòng lặp khoá ngoại tenant ở v3.15 chứ không sau: vòng lặp đó
    # quét TENANT_SCOPED_TABLES, nên chỉ cần các bảng này ra đời trước nó là
    # chúng được gắn khoá ngoại tenant miễn phí. Đặt sau sẽ phải phát vòng lặp
    # lần thứ ba — đúng cái bẫy v3 đã trả giá một lần.
    # ---------------------------------------------------------------------
    # v4.1 — Bảng gói. KHÔNG có tenant_id: gói là danh mục của cả nền tảng,
    # mọi tenant đọc chung. Vì thế nó cũng không nằm trong RLS_TABLES.
    #
    # NULL nghĩa là KHÔNG GIỚI HẠN, không phải "chưa biết". Quy ước này được
    # chọn thay vì một số rất lớn vì một trần giả (999999) sẽ có ngày bị chạm
    # tới và không ai hiểu vì sao; và thay vì -1 vì `NULL` khiến mọi phép so
    # sánh trong SQL tự trả về NULL, tức là "không vi phạm" — đúng ngữ nghĩa
    # cần, không phải một trường hợp đặc biệt phải nhớ. CHECK bên dưới chặn số
    # âm để -1 không lẻn vào mang nghĩa thứ hai.
    """
    CREATE TABLE IF NOT EXISTS plans (
        plan_code                    TEXT PRIMARY KEY,
        display_name                 TEXT NOT NULL,
        description                  TEXT NOT NULL DEFAULT '',
        max_seats                    INTEGER,
        max_samples                  INTEGER,
        max_storage_mb               INTEGER,
        max_classes                  INTEGER,
        max_training_jobs_per_month  INTEGER,
        max_concurrent_training_jobs INTEGER NOT NULL DEFAULT 1,
        max_queued_training_jobs     INTEGER NOT NULL DEFAULT 3,
        max_api_keys                 INTEGER NOT NULL DEFAULT 0,
        max_webhook_endpoints        INTEGER NOT NULL DEFAULT 0,
        price_cents                  BIGINT  NOT NULL DEFAULT 0,
        currency                     TEXT    NOT NULL DEFAULT 'VND',
        billing_period               TEXT    NOT NULL DEFAULT 'monthly',
        is_self_serve                BOOLEAN NOT NULL DEFAULT FALSE,
        is_listed                    BOOLEAN NOT NULL DEFAULT TRUE,
        trial_days                   INTEGER NOT NULL DEFAULT 0,
        sort_order                   INTEGER NOT NULL DEFAULT 0,
        created_at                   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at                   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_plans_limits_non_negative') THEN
            ALTER TABLE plans ADD CONSTRAINT ck_plans_limits_non_negative CHECK (
                coalesce(max_seats, 0) >= 0
                AND coalesce(max_samples, 0) >= 0
                AND coalesce(max_storage_mb, 0) >= 0
                AND coalesce(max_classes, 0) >= 0
                AND coalesce(max_training_jobs_per_month, 0) >= 0
                AND max_concurrent_training_jobs >= 0
                AND max_queued_training_jobs >= 0
                AND max_api_keys >= 0
                AND max_webhook_endpoints >= 0
                AND price_cents >= 0
                AND trial_days >= 0
            );
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_plans_billing_period') THEN
            ALTER TABLE plans ADD CONSTRAINT ck_plans_billing_period
                CHECK (billing_period IN ('monthly', 'yearly', 'none'));
        END IF;
    END $$
    """,
    # -----------------------------------------------------------------------
    # v6 — hạn mức của mô hình Free/Plus/Pro/Enterprise.
    #
    # Thuần THÊM, nên chúng chạy được ở `ensure_tables()`. Chưa cổng nào đọc
    # bốn cột này: `max_workspaces` và `max_projects` chờ v7 (workspace/project
    # còn chưa có đường tạo), `included_training_credits` chờ v8, và
    # `audit_retention_days` chờ cơ chế purge chưa tồn tại. Chúng có mặt từ v6
    # để một chỗ duy nhất mô tả gói, thay vì một nửa ở bảng và một nửa ở doc.
    "ALTER TABLE plans ADD COLUMN IF NOT EXISTS max_workspaces INTEGER",
    "ALTER TABLE plans ADD COLUMN IF NOT EXISTS max_projects INTEGER",
    "ALTER TABLE plans ADD COLUMN IF NOT EXISTS included_training_credits INTEGER",
    "ALTER TABLE plans ADD COLUMN IF NOT EXISTS audit_retention_days INTEGER",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint
                       WHERE conname = 'ck_plans_v6_limits_non_negative') THEN
            ALTER TABLE plans ADD CONSTRAINT ck_plans_v6_limits_non_negative CHECK (
                coalesce(max_workspaces, 0) >= 0
                AND coalesce(max_projects, 0) >= 0
                AND coalesce(included_training_credits, 0) >= 0
                AND coalesce(audit_retention_days, 0) >= 0
            );
        END IF;
    END $$
    """,
    # Khối chuyển đổi gói của v6, và nó phải đứng TRƯỚC câu seed bên dưới. Đảo lại
    # thì trên một cơ sở dữ liệu đã có, seed chèn `free` trước rồi câu đổi tên
    # `trial -> free` đụng khoá chính. Xem `_BILLING_V6_PLANS`.
    *_BILLING_V6_PLANS,
    # Bốn gói hạt giống. `ON CONFLICT DO NOTHING` chứ không phải `DO UPDATE`:
    # người vận hành sửa hạn mức bằng API quản trị, và một migration ghi đè
    # lại mỗi lần khởi động sẽ âm thầm huỷ mọi chỉnh tay đó.
    #
    # Trên một cơ sở dữ liệu ĐÃ CÓ, câu này không chèn gì: khối một chiều bên
    # trên vừa đổi tên bốn gói cũ thành đúng bốn mã này. Trên một cơ sở dữ liệu
    # TRẮNG, nó là nơi bốn gói ra đời, và khối một chiều không khớp dòng nào.
    # Hai đường hội tụ về cùng một trạng thái — đó là điều kiện để `--adopt`
    # trên máy mới và `--to 6` trên máy cũ cho ra cùng một lược đồ.
    #
    # `description` để RỖNG: giao diện dựng phần mô tả từ `plan_code` qua i18n.
    # Một câu tiếng Việt nằm trong bảng là chuỗi duy nhất không đi qua từ điển
    # được, và nó sẽ hiện nguyên tiếng Việt trong bản tiếng Anh.
    #
    # Các trần của Free/Plus/Pro dưới đây là con số ĐANG CHẠY của trial/school/
    # institution, không phải bảng gói mới: v6 không đổi hạn mức nào đang có
    # hiệu lực. Xem chú thích ở `_BILLING_V6_ONE_WAY`.
    """
    INSERT INTO plans (
        plan_code, display_name, description,
        max_seats, max_samples, max_storage_mb, max_classes,
        max_training_jobs_per_month, max_concurrent_training_jobs,
        max_queued_training_jobs, max_api_keys, max_webhook_endpoints,
        max_workspaces, max_projects, included_training_credits,
        audit_retention_days,
        price_cents, currency, billing_period, is_self_serve, is_listed,
        trial_days, sort_order
    ) VALUES
        ('free', 'Free', '',
         3, 500, 2048, 30, 5, 1, 2, 1, 0,
         1, 5, 60, 7,
         0, 'VND', 'none', TRUE, TRUE, 0, 10),
        ('plus', 'Plus', '',
         25, 20000, 51200, 500, 50, 1, 5, 5, 3,
         5, 25, 250, 30,
         NULL, 'VND', 'monthly', FALSE, TRUE, 0, 20),
        ('pro', 'Pro', '',
         200, 200000, 512000, 5000, 300, 2, 20, 25, 10,
         20, 100, 1000, 180,
         NULL, 'VND', 'monthly', FALSE, TRUE, 0, 30),
        ('enterprise', 'Enterprise', '',
         NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
         NULL, NULL, NULL, NULL,
         NULL, 'VND', 'none', FALSE, TRUE, 0, 40)
    ON CONFLICT (plan_code) DO NOTHING
    """,
    # ---------------------------------------------------------------------
    # v4.2 — Cột thương mại trên `tenants`. Tất cả đều THÊM.
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS plan_code TEXT",
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS billing_status TEXT NOT NULL DEFAULT 'active'",
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS current_period_start TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS current_period_end TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS is_self_serve BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS owner_user_id UUID",
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS suspended_reason TEXT",
    # Backfill trước khi SET NOT NULL. Tenant gốc lấy `internal`; mọi tenant
    # đã tồn tại lấy `school` chứ không phải `trial` — chúng được người vận
    # hành tạo tay từ trước, và hạ chúng xuống gói dùng thử là tự dựng một
    # trần 500 mẫu lên dữ liệu đang chạy.
    f"UPDATE tenants SET plan_code = 'internal' "
    f"WHERE plan_code IS NULL AND tenant_id = '{DEFAULT_TENANT_ID}'",
    "UPDATE tenants SET plan_code = 'school' WHERE plan_code IS NULL",
    # GIÁ TRỊ MẶC ĐỊNH, không chỉ NOT NULL. Bắt buộc, và đây là lỗi đã mắc
    # rồi sửa: câu `INSERT INTO tenants(tenant_id, display_name, slug)` ở đầu
    # danh sách migration KHÔNG nêu `plan_code`. Ở lượt chạy đầu nó vô hại vì
    # cột chưa tồn tại; từ lượt thứ HAI trở đi nó vi phạm NOT NULL và bị
    # `ensure_tables` nuốt thành một dòng cảnh báo. Trên máy này tenant gốc đã
    # có sẵn nên không ai thấy gì — nhưng trên một bản cài mới mà hàng đó chưa
    # kịp ra đời, tenant gốc sẽ lặng lẽ không bao giờ được tạo.
    #
    # Mặc định là `trial`, tức gói CHẶT NHẤT. Một đường chèn quên nêu gói sẽ
    # nhận hạn mức nhỏ nhất chứ không phải không giới hạn — sai theo hướng
    # chặn, không phải theo hướng mở.
    "ALTER TABLE tenants ALTER COLUMN plan_code SET DEFAULT 'trial'",
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'tenants'
              AND column_name = 'plan_code' AND is_nullable = 'YES'
        ) AND NOT EXISTS (SELECT 1 FROM tenants WHERE plan_code IS NULL) THEN
            ALTER TABLE tenants ALTER COLUMN plan_code SET NOT NULL;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_tenants_plan') THEN
            ALTER TABLE tenants ADD CONSTRAINT fk_tenants_plan
                FOREIGN KEY (plan_code) REFERENCES plans(plan_code)
                ON UPDATE CASCADE ON DELETE RESTRICT;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_tenants_billing_status') THEN
            ALTER TABLE tenants ADD CONSTRAINT ck_tenants_billing_status CHECK (
                billing_status IN ('trialing', 'active', 'past_due', 'suspended', 'cancelled')
            );
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_tenants_owner_user') THEN
            ALTER TABLE tenants ADD CONSTRAINT fk_tenants_owner_user
                FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE SET NULL;
        END IF;
    END $$
    """,
    # ---------------------------------------------------------------------
    # v4.3 — Lịch sử gói. `tenants.plan_code` là gói ĐANG có hiệu lực; bảng này
    # là chuỗi thay đổi dẫn tới nó. Cần tách vì một hoá đơn tranh chấp hỏi
    # "ngày 3 tháng trước họ đang ở gói nào", và một cột duy nhất không trả lời
    # được câu đó.
    """
    CREATE TABLE IF NOT EXISTS tenant_subscriptions (
        subscription_id UUID PRIMARY KEY,
        tenant_id       TEXT NOT NULL,
        plan_code       TEXT NOT NULL REFERENCES plans(plan_code) ON UPDATE CASCADE,
        status          TEXT NOT NULL DEFAULT 'active',
        started_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        ended_at        TIMESTAMP WITH TIME ZONE,
        changed_by      UUID REFERENCES users(id) ON DELETE SET NULL,
        note            TEXT NOT NULL DEFAULT '',
        created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    # Một tenant chỉ có MỘT đăng ký đang mở. Chỉ mục một phần là chỗ ép điều
    # đó; không có nó, một lần đổi gói hỏng giữa chừng để lại hai dòng mở và
    # mọi truy vấn "gói hiện tại" bắt đầu trả về hai kết quả.
    # -----------------------------------------------------------------------
    # v3.14 — KỲ HẠN. Trước đây bảng này chỉ có `started_at` và `ended_at`
    # (thời điểm bị đóng), nên một đăng ký mở là mở **vô thời hạn** cho tới khi
    # người vận hành sửa tay. Không có mốc kết thúc thì không có hết hạn, không
    # có gia hạn, và `plans.trial_days` là một cột trang trí — chưa mã nào đọc.
    #
    # `auto_renew` mặc định TRUE: gói đang chạy không được im lặng chết vì thêm
    # một cột. Người muốn dừng phải nói ra, không phải người muốn tiếp tục.
    #
    # `grace_until` tách khỏi `current_period_end` vì hai mốc trả lời hai câu
    # khác nhau: "đã tới hạn chưa" và "đã hết kiên nhẫn chưa". Gộp chúng lại thì
    # không diễn tả được khoảng đệm, mà khoảng đệm chính là thứ ngăn một hoá đơn
    # trễ hai ngày biến thành một trường mất quyền ghi.
    "ALTER TABLE tenant_subscriptions "
    "ADD COLUMN IF NOT EXISTS current_period_start TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE tenant_subscriptions "
    "ADD COLUMN IF NOT EXISTS current_period_end TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE tenant_subscriptions "
    "ADD COLUMN IF NOT EXISTS auto_renew BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE tenant_subscriptions "
    "ADD COLUMN IF NOT EXISTS grace_until TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE tenant_subscriptions "
    "ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP WITH TIME ZONE",
    # Mốc nhắc GẦN NHẤT đã gửi, tính bằng số ngày còn lại (7, 3, 1). Cột này là
    # toàn bộ cơ chế chống gửi trùng: tác vụ quét chạy mỗi giờ, nên không có nó
    # thì người dùng nhận 24 lá thư "còn 7 ngày" trong một ngày.
    "ALTER TABLE tenant_subscriptions "
    "ADD COLUMN IF NOT EXISTS last_reminder_days INTEGER",
    "CREATE INDEX IF NOT EXISTS idx_tenant_subscriptions_period_end "
    "ON tenant_subscriptions(current_period_end) WHERE ended_at IS NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_subscriptions_open "
    "ON tenant_subscriptions(tenant_id) WHERE ended_at IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_tenant_subscriptions_tenant "
    "ON tenant_subscriptions(tenant_id, started_at DESC)",
    # Mỗi tenant đang có phải có một dòng đăng ký mở, nếu không thì lịch sử
    # bắt đầu từ hư không.
    """
    INSERT INTO tenant_subscriptions (subscription_id, tenant_id, plan_code, status, started_at, note)
    SELECT gen_random_uuid(), t.tenant_id, t.plan_code, 'active', t.created_at,
           'Dòng mở đầu do migration v4.3 sinh từ gói đang có hiệu lực.'
    FROM tenants t
    WHERE t.plan_code IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM tenant_subscriptions s
          WHERE s.tenant_id = t.tenant_id AND s.ended_at IS NULL
      )
    """,
    # ---------------------------------------------------------------------
    # v6 — miễn trừ thanh toán, và phần một chiều chạm `tenants`.
    #
    # `billing_exempt` thay cho gói `internal` đã bị đổi tên: tenant nền tảng
    # là một THUỘC TÍNH của tenant, không phải một bậc trong bảng giá. Cột thuần
    # THÊM nên nó ở đây; câu bật cờ cho tenant gốc là một chiều nên nó nằm
    # trong `_BILLING_V6_TENANTS`.
    #
    # Mặc định FALSE: một tenant mới không được im lặng thoát khỏi mọi hạn mức.
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS billing_exempt "
    "BOOLEAN NOT NULL DEFAULT FALSE",
    *_BILLING_V6_TENANTS,
    # ---------------------------------------------------------------------
    # v4.4 — Số đo mức dùng, gộp theo NGÀY chứ không lưu từng sự kiện.
    #
    # Một bảng sự kiện thô sẽ nhận mỗi lượt tải lên một dòng — cùng thứ tự độ
    # lớn với `samples` — chỉ để trả lời một câu hỏi mỗi tháng. Bảng gộp giữ
    # một dòng cho mỗi (tenant, ngày, chỉ số): với 20 tenant và 7 chỉ số là
    # ~51 nghìn dòng một năm, đọc tức thì và không cần dọn.
    #
    # Đánh đổi được nhận: không truy ngược được về từng lượt. Chấp nhận, vì
    # `audit_log` đã giữ dấu vết từng hành động rồi — bảng này để tính tiền và
    # vẽ biểu đồ, không phải để điều tra.
    """
    CREATE TABLE IF NOT EXISTS tenant_usage_daily (
        tenant_id   TEXT NOT NULL,
        usage_date  DATE NOT NULL,
        metric      TEXT NOT NULL,
        value       BIGINT NOT NULL DEFAULT 0,
        computed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        PRIMARY KEY (tenant_id, usage_date, metric)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tenant_usage_daily_metric "
    "ON tenant_usage_daily(metric, usage_date DESC)",
    # ---------------------------------------------------------------------
    # v4.5 — Khoá API. Lưu BĂM, không lưu khoá.
    #
    # `prefix` là 12 ký tự đầu, lưu nguyên văn và có chỉ mục duy nhất: nó vừa
    # là thứ hiện trên giao diện để người dùng nhận ra khoá nào, vừa là đường
    # tra cứu O(1) lúc xác thực. Không có nó, mỗi lượt gọi phải so băm với mọi
    # khoá của mọi tenant.
    """
    CREATE TABLE IF NOT EXISTS api_keys (
        key_id       UUID PRIMARY KEY,
        tenant_id    TEXT NOT NULL,
        name         TEXT NOT NULL DEFAULT '',
        prefix       TEXT NOT NULL UNIQUE,
        key_hash     TEXT NOT NULL,
        scopes       TEXT NOT NULL DEFAULT 'read',
        created_by   UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        last_used_at TIMESTAMP WITH TIME ZONE,
        expires_at   TIMESTAMP WITH TIME ZONE,
        revoked_at   TIMESTAMP WITH TIME ZONE,
        revoked_by   UUID REFERENCES users(id) ON DELETE SET NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys(tenant_id) "
    "WHERE revoked_at IS NULL",
    # ---------------------------------------------------------------------
    # v4.6 — Webhook. `secret` lưu NGUYÊN VĂN, và đó là bắt buộc chứ không
    # phải cẩu thả: chữ ký HMAC cần chính bí mật đó ở mỗi lần gửi, nên một bản
    # băm sẽ không ký được gì. Đây là mô hình của Stripe và GitHub. Bù lại:
    # bí mật chỉ hiện MỘT lần lúc tạo, không endpoint nào đọc lại nó, và
    # `audit._SENSITIVE_KEYS` đã chặn nó khỏi nhật ký.
    """
    CREATE TABLE IF NOT EXISTS webhook_endpoints (
        endpoint_id     UUID PRIMARY KEY,
        tenant_id       TEXT NOT NULL,
        url             TEXT NOT NULL,
        secret          TEXT NOT NULL,
        event_types     TEXT NOT NULL DEFAULT '*',
        is_active       BOOLEAN NOT NULL DEFAULT TRUE,
        description     TEXT NOT NULL DEFAULT '',
        created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        last_success_at TIMESTAMP WITH TIME ZONE,
        last_failure_at TIMESTAMP WITH TIME ZONE,
        failure_streak  INTEGER NOT NULL DEFAULT 0,
        disabled_at     TIMESTAMP WITH TIME ZONE,
        disabled_reason TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_webhook_endpoints_tenant "
    "ON webhook_endpoints(tenant_id) WHERE is_active",
    """
    CREATE TABLE IF NOT EXISTS webhook_deliveries (
        delivery_id      UUID PRIMARY KEY,
        tenant_id        TEXT NOT NULL,
        endpoint_id      UUID NOT NULL REFERENCES webhook_endpoints(endpoint_id) ON DELETE CASCADE,
        event_type       TEXT NOT NULL,
        payload          JSONB NOT NULL,
        status           TEXT NOT NULL DEFAULT 'pending',
        attempts         INTEGER NOT NULL DEFAULT 0,
        last_status_code INTEGER,
        last_error       TEXT,
        next_attempt_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        delivered_at     TIMESTAMP WITH TIME ZONE
    )
    """,
    # Chỉ mục cho vòng quét gửi lại: chỉ những lần giao còn dang dở mới được
    # lấy ra, nên chỉ mục một phần vừa nhỏ vừa đúng hình dạng truy vấn.
    "CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_pending "
    "ON webhook_deliveries(next_attempt_at) WHERE status = 'pending'",
    "CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_endpoint "
    "ON webhook_deliveries(endpoint_id, created_at DESC)",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_webhook_deliveries_status') THEN
            ALTER TABLE webhook_deliveries ADD CONSTRAINT ck_webhook_deliveries_status
                CHECK (status IN ('pending', 'delivered', 'failed', 'dropped'));
        END IF;
    END $$
    """,
    # ---------------------------------------------------------------------
    # v4.7 — Yêu cầu xuất dữ liệu của một tenant.
    """
    CREATE TABLE IF NOT EXISTS tenant_exports (
        export_id    UUID PRIMARY KEY,
        tenant_id    TEXT NOT NULL,
        requested_by UUID REFERENCES users(id) ON DELETE SET NULL,
        status       TEXT NOT NULL DEFAULT 'pending',
        scope        TEXT NOT NULL DEFAULT 'metadata',
        file_path    TEXT,
        size_bytes   BIGINT,
        row_counts   JSONB,
        error        TEXT,
        created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMP WITH TIME ZONE,
        expires_at   TIMESTAMP WITH TIME ZONE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tenant_exports_tenant "
    "ON tenant_exports(tenant_id, created_at DESC)",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_tenant_exports_status') THEN
            ALTER TABLE tenant_exports ADD CONSTRAINT ck_tenant_exports_status
                CHECK (status IN ('pending', 'running', 'ready', 'failed', 'expired'));
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_tenant_exports_scope') THEN
            ALTER TABLE tenant_exports ADD CONSTRAINT ck_tenant_exports_scope
                CHECK (scope IN ('metadata', 'full'));
        END IF;
    END $$
    """,
    # ---------------------------------------------------------------------
    # v4.8 — Sổ xoá vĩnh viễn.
    #
    # CỐ Ý KHÔNG có khoá ngoại tới `tenants`, và vì thế cũng CỐ Ý không nằm
    # trong TENANT_SCOPED_TABLES. Bảng này tồn tại để ghi lại việc một tenant
    # đã bị xoá khỏi hệ thống; một khoá ngoại sẽ khiến chính hành động nó ghi
    # lại trở nên bất khả thi. `tenant_id` ở đây là chữ, là dấu vết, không phải
    # một liên kết.
    #
    # Không có RLS trên bảng này cùng lý do: sau khi xoá, không còn tenant nào
    # để phạm vi hoá. Nó chỉ đọc được qua đường quản trị nền tảng.
    """
    CREATE TABLE IF NOT EXISTS tenant_purges (
        purge_id     UUID PRIMARY KEY,
        tenant_id    TEXT NOT NULL,
        display_name TEXT NOT NULL DEFAULT '',
        requested_by UUID,
        row_counts   JSONB,
        files_removed INTEGER NOT NULL DEFAULT 0,
        bytes_removed BIGINT NOT NULL DEFAULT 0,
        export_id    UUID,
        reason       TEXT NOT NULL DEFAULT '',
        created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tenant_purges_created ON tenant_purges(created_at DESC)",
    # =====================================================================
    # v5 — KHO VĂN BẢN PHÁP LÝ
    #
    # v4 làm hệ thống bán được. v5 làm nó ký được: bản văn mà người ta đồng ý
    # phải ĐỌC LẠI ĐƯỢC, nguyên văn, nhiều năm sau, kể cả khi bản hiện hành đã
    # là bản thứ tư.
    #
    # Bản v1 của `legal_documents` lưu `content_hash` và `url`, còn thân văn
    # bản nằm ở "file tĩnh do nginx phục vụ". Trên thực tế file đó không tồn
    # tại: `register_document(body=...)` băm rồi VỨT, nên hash không đối chiếu
    # được với gì, `url` trỏ vào 404, và không đường nào — API hay giao diện —
    # đọc được bản văn. Cả bộ máy chấp thuận chạy đúng quanh một khoảng trống.
    #
    # Vì sao thân văn bản thuộc về CƠ SỞ DỮ LIỆU chứ không phải hệ tệp: bằng
    # chứng chấp thuận và bản văn được chấp thuận phải sao lưu, khôi phục và
    # nhân bản CÙNG NHAU. Tách hai thứ ra hai hệ thống lưu trữ có nghĩa là mỗi
    # lần khôi phục là một cơ hội để chúng lệch nhau, và cái lệch đó chỉ lộ ra
    # đúng lúc có người hỏi "bản tôi ký hồi đó viết gì".
    # ---------------------------------------------------------------------
    # v5.1 — Thân văn bản và xuất xứ bản công bố. Tất cả đều THÊM.
    #
    # `body` có DEFAULT '' vì đây là câu ALTER trên một bảng có thể đã mang
    # dòng — những dòng công bố dưới thời v1, khi thân văn bản chưa từng được
    # lưu. Không dựng lại được nội dung đã mất, nên cột phải chấp nhận sự thật
    # đó. Ràng buộc "thân không rỗng" nằm ở `legal.register_document`, chỗ duy
    # nhất tạo dòng mới; xem chú thích tại đó.
    "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS body TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS body_format TEXT NOT NULL "
    "DEFAULT 'markdown'",
    # Ngôn ngữ của BẢN VĂN NÀY. Không phải chiều dịch thuật: xem
    # docs/04-legal/LEGAL_DOCUMENTS.md §"Bản dịch" để biết vì sao bản dịch KHÔNG phải
    # một dòng nữa ở đây.
    "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS language TEXT NOT NULL DEFAULT 'vi'",
    # Tóm tắt "bản này khác bản trước ở chỗ nào". Bắt người ta đồng ý lại mà
    # không nói đổi cái gì thì họ bấm đồng ý mà không đọc, và chữ ký thu được
    # có giá trị đúng bằng không.
    "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS change_summary TEXT NOT NULL "
    "DEFAULT ''",
    "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS published_at TIMESTAMP WITH TIME "
    "ZONE NOT NULL DEFAULT NOW()",
    # AI bấm nút công bố. ON DELETE SET NULL chứ không RESTRICT: một người rời
    # tổ chức không được phép khoá cứng bản ghi văn bản của cả nền tảng.
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'legal_documents' AND column_name = 'published_by'
        ) THEN
            ALTER TABLE legal_documents
                ADD COLUMN published_by UUID REFERENCES users(id) ON DELETE SET NULL;
        END IF;
    END $$
    """,
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_legal_documents_body_format'
        ) THEN
            ALTER TABLE legal_documents ADD CONSTRAINT ck_legal_documents_body_format
                CHECK (body_format IN ('markdown', 'text'));
        END IF;
    END $$
    """,
    # ---------------------------------------------------------------------
    # v5.2 — Bất biến, cưỡng chế ở TẦNG CƠ SỞ DỮ LIỆU.
    #
    # `register_document` đã từ chối ghi đè nội dung dưới cùng một số hiệu, và
    # có test ghim điều đó. Nhưng đó là một quy ước của ứng dụng, còn bảng này
    # thì mở cho mọi câu UPDATE: một lệnh `psql` trong lúc vận hành, một script
    # sửa dữ liệu, một migration tương lai viết ẩu — bất kỳ cái nào cũng viết
    # lại được bản văn nằm dưới hàng nghìn chữ ký mà không để lại dấu vết.
    #
    # Đây đúng là loại bất biến phải nằm ở cơ sở dữ liệu chứ không ở ứng dụng:
    # giá trị của nó nằm ở chỗ nó đúng KỂ CẢ khi mã ứng dụng sai.
    #
    # Cái gì được sửa: `url`, `title`, `requires_reconsent`, `change_summary`.
    # Cái gì không: `kind`, `version`, `body`, `content_hash` — bộ tứ mà một
    # chấp thuận trỏ tới.
    #
    # `effective_from` là trường hợp ở giữa, và biên giới là THỜI ĐIỂM: dời
    # ngày hiệu lực của một bản CHƯA tới hạn là lên lịch lại, hoàn toàn hợp lệ;
    # dời của một bản ĐÃ hiệu lực là viết lại lịch sử — nó đổi câu trả lời cho
    # "hôm đó bản nào đang áp dụng".
    """
    CREATE OR REPLACE FUNCTION legal_documents_freeze() RETURNS trigger AS $$
    BEGIN
        IF NEW.kind <> OLD.kind OR NEW.version <> OLD.version
           OR NEW.body <> OLD.body OR NEW.content_hash <> OLD.content_hash THEN
            RAISE EXCEPTION
                'legal_documents la ban ghi chi-them: khong duoc sua kind/version/'
                'body/content_hash cua % ban % (moi chap thuan da thu deu tro toi '
                'bo tu nay). Muon doi noi dung thi cong bo mot phien ban moi.',
                OLD.kind, OLD.version
                USING ERRCODE = 'restrict_violation';
        END IF;
        IF NEW.effective_from <> OLD.effective_from AND OLD.effective_from <= now() THEN
            RAISE EXCEPTION
                'khong duoc doi effective_from cua % ban % vi ban nay DA co hieu '
                'luc tu %; doi no la viet lai cau tra loi cho "hom do ban nao dang '
                'ap dung".',
                OLD.kind, OLD.version, OLD.effective_from
                USING ERRCODE = 'restrict_violation';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS trg_legal_documents_freeze ON legal_documents",
    """
    CREATE TRIGGER trg_legal_documents_freeze
        BEFORE UPDATE ON legal_documents
        FOR EACH ROW EXECUTE FUNCTION legal_documents_freeze()
    """,
    # ---------------------------------------------------------------------
    # v5.3 — Xuất xứ của một chấp thuận.
    #
    # Một dòng do người dùng bấm "Tôi đồng ý" và một dòng do người vận hành ghi
    # hộ cho tài khoản có sẵn KHÔNG phải cùng một loại bằng chứng, và trước cột
    # này chúng trông giống hệt nhau. Ghi hộ mà không đánh dấu là làm giả chữ
    # ký — kể cả khi mọi tài khoản đều do chính người vận hành tạo ra, vì bản
    # ghi sẽ sống lâu hơn hoàn cảnh biết được điều đó.
    #
    # DEFAULT 'user' đúng cho các dòng có sẵn: tính tới v5, đường DUY NHẤT tạo
    # ra một dòng ở đây là `POST /auth/register`.
    "ALTER TABLE user_consents ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'user'",
    "ALTER TABLE user_consents ADD COLUMN IF NOT EXISTS note TEXT NOT NULL DEFAULT ''",
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'user_consents' AND column_name = 'recorded_by'
        ) THEN
            ALTER TABLE user_consents
                ADD COLUMN recorded_by UUID REFERENCES users(id) ON DELETE SET NULL;
        END IF;
    END $$
    """,
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_user_consents_source'
        ) THEN
            ALTER TABLE user_consents ADD CONSTRAINT ck_user_consents_source
                CHECK (source IN ('user', 'backfill', 'import'));
        END IF;
    END $$
    """,
    # KHÔNG có chỉ mục HIỆU NĂNG nào ở v5, và đó là một quyết định chứ không
    # phải bỏ sót: `legal_documents` sẽ có cỡ vài chục dòng trong suốt vòng đời
    # hệ thống, nên một chỉ mục để tăng tốc chỉ thêm việc cho mỗi lượt ghi để
    # bộ lập lịch bỏ qua nó và quét tuần tự bốn dòng. `user_consents` đã có
    # `idx_consent_user` và `uq_consent_live`, phủ đúng hai câu truy vấn duy
    # nhất chạy trên nó.
    #
    # (v6 có thêm một chỉ mục, nhưng nó là RÀNG BUỘC ĐÚNG ĐẮN chứ không phải
    # tăng tốc — xem v6.4.)
    # =====================================================================
    # v6 — QUẢN LÝ TÀI LIỆU: BẢN NHÁP, KHO TỆP, SỔ ĐĂNG BẠ
    #
    # v5 làm bản văn đọc lại được. v6 làm nó SOẠN được: một bản văn pháp lý
    # trong đời thực đi qua nháp → rà soát → phê duyệt → hiệu lực → thay thế,
    # và ba trạng thái đầu không tồn tại khi đường duy nhất để đưa nội dung vào
    # hệ thống là một lệnh CLI công bố thẳng.
    #
    # Mô hình lấy từ cách các hệ quản lý tài liệu có kiểm soát làm việc (eQMS,
    # 21 CFR Part 11, ISO 9001): **bản hồ sơ** đóng băng trong hệ thống hồ sơ,
    # **bản làm việc** sống trong kho tài liệu, và một **sổ đăng bạ chỉ-thêm**
    # ghi ai làm gì lên đối tượng nào vào lúc nào — không ghi nội dung.
    # ---------------------------------------------------------------------
    # v6.1 — Con trỏ tới kho tệp trên `legal_documents`.
    #
    # Nội dung nằm ở HAI nơi và đó là chủ ý, không phải trùng lặp do sơ ý:
    #
    #   * `body` trong bảng = BẢN HỒ SƠ. Đóng băng, nằm cùng một `pg_dump` với
    #     những chấp thuận trỏ tới nó. Bỏ nó đi thì khôi phục một bản sao lưu
    #     trên máy mới sẽ cho ra các bản ghi chấp thuận trỏ tới văn bản không
    #     ai có.
    #   * `storage_key` trỏ tới BẢN TÀI LIỆU trong kho tệp. Đây là thứ công cụ
    #     quản lý thao tác lên: so sánh, sao chép, kiểm toàn vẹn.
    #
    # `content_hash` là mối nối, và `app.cli.legal_store --verify` chứng minh
    # hai bên trùng từng byte. Hai bản mà có một phép kiểm chứng minh chúng
    # bằng nhau thì không phải hai nguồn sự thật.
    "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS storage_backend TEXT NOT NULL "
    "DEFAULT 'local'",
    "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS storage_key TEXT",
    "ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS byte_size INTEGER NOT NULL DEFAULT 0",
    # ---------------------------------------------------------------------
    # v6.2 — Bản nháp. Đây là bảng DUY NHẤT trong mặt phẳng pháp lý được sửa.
    #
    # `revision` là khoá lạc quan: mọi lượt ghi mang theo số hiệu bản mình đọc
    # được, và `UPDATE ... WHERE revision = %s` trả về 0 hàng khi có người khác
    # đã ghi trước. Không có nó, hai người soạn cùng một văn bản thì người lưu
    # sau âm thầm đè mất bài của người lưu trước — kiểu mất dữ liệu không để lại
    # dấu vết nào và chỉ phát hiện được bằng cách đọc lại toàn văn.
    """
    CREATE TABLE IF NOT EXISTS legal_document_drafts (
        draft_id           UUID PRIMARY KEY,
        kind               TEXT NOT NULL,
        title              TEXT NOT NULL DEFAULT '',
        language           TEXT NOT NULL DEFAULT 'vi',
        body               TEXT NOT NULL DEFAULT '',
        body_format        TEXT NOT NULL DEFAULT 'markdown',
        change_summary     TEXT NOT NULL DEFAULT '',
        target_version     TEXT NOT NULL DEFAULT '',
        requires_reconsent BOOLEAN NOT NULL DEFAULT FALSE,
        effective_from     TIMESTAMP WITH TIME ZONE,
        status             TEXT NOT NULL DEFAULT 'draft',
        revision           INTEGER NOT NULL DEFAULT 1,
        based_on_version   TEXT,
        published_version  TEXT,
        storage_key        TEXT,
        content_hash       TEXT,
        byte_size          INTEGER NOT NULL DEFAULT 0,
        created_by         UUID REFERENCES users(id) ON DELETE SET NULL,
        updated_by         UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT ck_legal_drafts_kind CHECK (
            kind IN ('terms', 'privacy', 'data_contribution', 'guardian')
        ),
        CONSTRAINT ck_legal_drafts_status CHECK (
            status IN ('draft', 'in_review', 'approved', 'published', 'discarded')
        ),
        CONSTRAINT ck_legal_drafts_revision CHECK (revision >= 1)
    )
    """,
    # ĐÚNG MỘT bản nháp đang mở cho mỗi loại.
    #
    # Ràng buộc này biến câu hỏi khó thành câu hỏi dễ. Cho phép nhiều bản nháp
    # song song nghĩa là hai người soạn hai bản khác nhau của cùng một văn bản
    # và không ai hợp nhất chúng — một bài toán trộn văn bản pháp lý mà phần mềm
    # này không có công cụ để giải. Một bản nháp chung, với khoá lạc quan, biến
    # nó thành xung đột ghi phát hiện được ngay.
    #
    # Cái giá: không soạn trước được hai phiên bản tương lai cùng lúc. Với một
    # nền tảng công bố cỡ hai bản mỗi năm, đó không phải hạn chế thật.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_legal_draft_open "
    "ON legal_document_drafts (kind) "
    "WHERE status IN ('draft', 'in_review', 'approved')",
    "CREATE INDEX IF NOT EXISTS idx_legal_drafts_updated "
    "ON legal_document_drafts (updated_at DESC)",
    # ---------------------------------------------------------------------
    # v6.3 — Sổ đăng bạ. CHỈ THÊM.
    #
    # Vì sao KHÔNG dùng `audit_log`: bảng đó thuộc-tenant. Lịch sử pháp lý áp
    # cho cả nền tảng, nên nhét vào đó sẽ phân mảnh nó theo tenant của bất kỳ
    # quản trị viên nào tình cờ thao tác. Vòng đời lưu trữ cũng khác — audit 12
    # tháng, còn xuất xứ của một bản ghi chấp thuận phải sống lâu hơn chính bản
    # ghi ấy.
    #
    # `detail` là JSONB nhưng **không bao giờ chứa thân văn bản**. Sổ này được
    # đọc, xuất và chuyển tiếp thường xuyên hơn bảng văn bản; nhét bản văn vào
    # đây là nhân bản một tài liệu có thể còn đang cấm phát hành sang một chỗ có
    # quyền đọc khác hẳn. Ghi HÀNH ĐỘNG và ĐỐI TƯỢNG, không ghi nội dung.
    #
    # KHÔNG có khoá ngoại nào ở bảng này — không tới `legal_document_drafts`,
    # và **không tới `users`**. Cả hai đều là quyết định, và cái thứ hai đã trả
    # giá để học:
    #
    # Bản đầu có `actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL`.
    # Nghe vô hại. Nhưng `ON DELETE SET NULL` phát ra một câu **UPDATE** lên
    # bảng này, và trigger chỉ-thêm bên dưới từ chối mọi UPDATE — nên
    # `DELETE FROM users` bắt đầu thất bại cho bất kỳ ai từng xuất hiện trong
    # sổ. Tức là: thêm một sổ đăng bạ đã âm thầm làm hỏng quyền xoá tài khoản,
    # đúng cái quyền mà chính sách quyền riêng tư hứa ở mục 6.
    #
    # Bộ test bắt được vì sổ dấu vết báo 9 hàng `users` bị bỏ lại; bản thân câu
    # xoá thì im lặng vì `purge_registered_account` nuốt ngoại lệ.
    #
    # Cách đúng là bỏ khoá ngoại, cùng lý do `tenant_purges` cố ý không có:
    # **một sổ đăng bạ không được cản chính hành động nó ghi lại.** Danh tính
    # người thao tác còn lại ở `actor_label`, vốn được điền ngay lúc ghi.
    """
    CREATE TABLE IF NOT EXISTS legal_document_events (
        event_id      BIGSERIAL PRIMARY KEY,
        occurred_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        actor_user_id UUID,
        actor_label   TEXT NOT NULL DEFAULT '',
        action        TEXT NOT NULL,
        kind          TEXT,
        version       TEXT,
        draft_id      UUID,
        revision      INTEGER,
        storage_key   TEXT,
        content_hash  TEXT,
        detail        JSONB,
        CONSTRAINT ck_legal_events_action_not_blank CHECK (action <> '')
    )
    """,
    # Gỡ khoá ngoại của bản đầu trên những cơ sở dữ liệu đã tạo bảng rồi.
    # `CREATE TABLE IF NOT EXISTS` không sửa bảng đã tồn tại, nên nếu chỉ đổi
    # câu CREATE ở trên thì máy phát triển nào đã chạy bản cũ sẽ giữ nguyên
    # khoá ngoại — và giữ nguyên lỗi không xoá được tài khoản.
    """
    DO $$ BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'legal_document_events_actor_user_id_fkey'
        ) THEN
            ALTER TABLE legal_document_events
                DROP CONSTRAINT legal_document_events_actor_user_id_fkey;
        END IF;
    END $$
    """,
    "CREATE INDEX IF NOT EXISTS idx_legal_events_occurred "
    "ON legal_document_events (occurred_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_legal_events_object "
    "ON legal_document_events (kind, version)",
    # Chỉ-thêm, cưỡng chế ở tầng cơ sở dữ liệu. Cùng lý do với
    # `trg_legal_documents_freeze`: giá trị của một bất biến kiểu này nằm ở chỗ
    # nó đúng KỂ CẢ khi mã ứng dụng sai. Một sổ đăng bạ sửa được thì không trả
    # lời được câu hỏi duy nhất nó tồn tại để trả lời.
    """
    CREATE OR REPLACE FUNCTION legal_events_append_only() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION
            'legal_document_events la so dang ba CHI-THEM: khong duoc % dong nao. '
            'Ghi mot dong su kien moi de dinh chinh, dung sua dong cu.',
            lower(TG_OP)
            USING ERRCODE = 'restrict_violation';
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS trg_legal_events_append_only ON legal_document_events",
    """
    CREATE TRIGGER trg_legal_events_append_only
        BEFORE UPDATE OR DELETE ON legal_document_events
        FOR EACH ROW EXECUTE FUNCTION legal_events_append_only()
    """,
    # ---------------------------------------------------------------------
    # v6.4 — MỘT bản có hiệu lực tại một thời điểm, cho mỗi loại.
    #
    # Đây là vá một lỗi đang tồn tại, không phải thêm tính năng.
    # `current_document` chọn bản bằng `ORDER BY effective_from DESC LIMIT 1`.
    # Hai bản cùng loại có cùng `effective_from` làm câu đó trả về một trong hai
    # một cách KHÔNG XÁC ĐỊNH — cùng một truy vấn, hai lần chạy, hai bản văn
    # khác nhau, và chấp thuận thu được trỏ tới bản nào là chuyện may rủi.
    #
    # Hôm nay chưa đụng vì mỗi loại mới có một bản. Nó sẽ đụng ở lần công bố thứ
    # hai nếu hai người bấm nút trong cùng một giây, hoặc nếu ai đó hẹn giờ
    # trùng ngày với một bản đã hẹn.
    #
    # Chỉ mục duy nhất biến chuyện đó từ "thắng ngẫu nhiên" thành "một lượt công
    # bố thất bại rõ ràng" — và thất bại rõ ràng là thứ sửa được.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_legal_effective "
    "ON legal_documents (kind, effective_from)",
    # ---------------------------------------------------------------------
    # v6.5 — Mở rộng phanh bất biến sang con trỏ kho.
    #
    # `body` đã bị đóng băng từ v5. Nhưng nếu `storage_key` sửa được thì vẫn
    # trỏ được một bản đã công bố sang một tệp khác trong kho — đi vòng qua
    # phanh cũ mà không chạm vào nó.
    """
    CREATE OR REPLACE FUNCTION legal_documents_freeze() RETURNS trigger AS $$
    BEGIN
        IF NEW.kind <> OLD.kind OR NEW.version <> OLD.version
           OR NEW.body <> OLD.body OR NEW.content_hash <> OLD.content_hash THEN
            RAISE EXCEPTION
                'legal_documents la ban ghi chi-them: khong duoc sua kind/version/'
                'body/content_hash cua % ban % (moi chap thuan da thu deu tro toi '
                'bo tu nay). Muon doi noi dung thi cong bo mot phien ban moi.',
                OLD.kind, OLD.version
                USING ERRCODE = 'restrict_violation';
        END IF;
        -- Con tro kho: cho phep DIEN VAO khi con trong (di tru du lieu v5 sang
        -- kho tep), nhung khong cho DOI sang tep khac.
        IF OLD.storage_key IS NOT NULL AND NEW.storage_key IS DISTINCT FROM OLD.storage_key THEN
            RAISE EXCEPTION
                'khong duoc tro % ban % sang mot tep khac trong kho (% -> %); '
                'dia chi kho sinh ra tu noi dung, nen doi no la doi noi dung.',
                OLD.kind, OLD.version, OLD.storage_key, NEW.storage_key
                USING ERRCODE = 'restrict_violation';
        END IF;
        IF NEW.effective_from <> OLD.effective_from AND OLD.effective_from <= now() THEN
            RAISE EXCEPTION
                'khong duoc doi effective_from cua % ban % vi ban nay DA co hieu '
                'luc tu %; doi no la viet lai cau tra loi cho "hom do ban nao dang '
                'ap dung".',
                OLD.kind, OLD.version, OLD.effective_from
                USING ERRCODE = 'restrict_violation';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    # ---------------------------------------------------------------------
    # v6 — Thông báo trong ứng dụng.
    #
    # Thư điện tử đã có, nhưng nó rời khỏi hệ thống và không quay lại: không ai
    # biết người dùng đã đọc chưa, và một người đổi địa chỉ thư là mất luôn mọi
    # thông báo. Bảng này là bản ghi BỀN của cùng những sự kiện đó.
    #
    # `link` trỏ vào một đường dẫn TRONG ứng dụng chứ không phải URL tuyệt đối:
    # nền tảng chạy dưới hai gốc khác nhau (`/` khi phát triển, `/voya` trên máy
    # chủ CTU), nên một URL tuyệt đối lưu trong CSDL sẽ hỏng ở một trong hai.
    """
    CREATE TABLE IF NOT EXISTS notifications (
        notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id       TEXT NOT NULL,
        user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        kind            TEXT NOT NULL,
        title           TEXT NOT NULL,
        body            TEXT NOT NULL DEFAULT '',
        link            TEXT,
        severity        TEXT NOT NULL DEFAULT 'info',
        read_at         TIMESTAMP WITH TIME ZONE,
        created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT notifications_severity_valid
            CHECK (severity IN ('info', 'success', 'warning', 'critical'))
    )
    """,
    # Truy vấn nóng duy nhất: "thông báo CHƯA ĐỌC của tôi, mới nhất trước".
    # Index từng phần vì phần đã đọc lớn dần vô hạn còn phần chưa đọc thì không.
    "CREATE INDEX IF NOT EXISTS idx_notifications_unread "
    "ON notifications(user_id, created_at DESC) WHERE read_at IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_notifications_user "
    "ON notifications(user_id, created_at DESC)",
    # ---------------------------------------------------------------------
    # v6 — Kênh hỗ trợ.
    #
    # `author_label` được CHÉP vào lúc ghi và KHÔNG bao giờ cập nhật theo lượt
    # đổi tên tài khoản — cùng nguyên tắc với `audit_log.actor_label`: một cuộc
    # trao đổi hỗ trợ là bằng chứng lịch sử, và sửa tên trong đó là viết lại lịch
    # sử. Xem `app/account_rename.py`.
    """
    CREATE TABLE IF NOT EXISTS support_tickets (
        ticket_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id   TEXT NOT NULL,
        user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
        subject     TEXT NOT NULL,
        category    TEXT NOT NULL DEFAULT 'other',
        status      TEXT NOT NULL DEFAULT 'open',
        priority    TEXT NOT NULL DEFAULT 'normal',
        created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        resolved_at TIMESTAMP WITH TIME ZONE,
        CONSTRAINT support_tickets_status_valid
            CHECK (status IN ('open', 'pending', 'resolved', 'closed')),
        CONSTRAINT support_tickets_priority_valid
            CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
        CONSTRAINT support_tickets_category_valid
            CHECK (category IN ('account', 'billing', 'data', 'bug', 'other'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS support_messages (
        message_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id    TEXT NOT NULL,
        ticket_id    UUID NOT NULL REFERENCES support_tickets(ticket_id) ON DELETE CASCADE,
        author_id    UUID REFERENCES users(id) ON DELETE SET NULL,
        author_label TEXT NOT NULL,
        is_staff     BOOLEAN NOT NULL DEFAULT FALSE,
        -- Ba loại người nói, không phải hai. Xem khối v3.16 trong
        -- MIGRATION_STATEMENTS về vì sao `is_staff` một mình là nói dối khi có
        -- trợ lý tự động. Cột này phải có mặt Ở ĐÂY, không chỉ trong migration:
        -- một máy dựng mới chạy CREATE TABLE chứ không chạy ALTER, và lệch
        -- lược đồ giữa máy mới với máy đang chạy là kiểu hỏng im lặng nhất.
        author_kind  TEXT NOT NULL DEFAULT 'user',
        body         TEXT NOT NULL,
        created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT ck_support_author_kind
            CHECK (author_kind IN ('user', 'staff', 'bot')),
        CONSTRAINT ck_support_author_kind_matches
            CHECK ((author_kind = 'staff') = is_staff)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_support_tickets_owner "
    "ON support_tickets(tenant_id, user_id, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_support_tickets_queue "
    "ON support_tickets(status, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_support_messages_ticket "
    "ON support_messages(ticket_id, created_at)",
    # ---------------------------------------------------------------------
    # v6 — Xác thực hai bước (TOTP, RFC 6238).
    #
    # CỐ Ý KHÔNG có `tenant_id` và CỐ Ý không nằm trong TENANT_SCOPED_TABLES —
    # cùng lý do với `refresh_tokens` và `password_reset_tokens`: đây là mặt
    # phẳng DANH TÍNH, và nó được đọc **giữa chừng lúc đăng nhập**, tức trước
    # khi hệ thống biết người này thuộc tenant nào.
    #
    # Nếu bảng có row-level security, truy vấn kiểm 2FA lúc đăng nhập sẽ khớp 0
    # dòng và hệ thống kết luận "người này không bật 2FA" — tức là **bỏ qua lớp
    # bảo vệ thứ hai trong im lặng**. Không phải giả thuyết: đúng dạng lỗi đó đã
    # xảy ra hai lần trong ngày 2026-08-10 (mốc thu hồi phiên, và đường đồng bộ
    # đồng thuận). RLS ở đây fail-OPEN, nên không được dùng RLS.
    #
    # `secret_enc` là bí mật đã MÃ HOÁ, không phải băm: TOTP cần chính bí mật để
    # tính lại mã, nên băm một chiều không dùng được. Khoá mã hoá dẫn xuất từ
    # SECRET_KEY và nằm ngoài CSDL — một bản dump CSDL không đủ để giả mạo mã.
    """
    CREATE TABLE IF NOT EXISTS user_totp (
        user_id        UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        secret_enc     TEXT NOT NULL,
        confirmed_at   TIMESTAMP WITH TIME ZONE,
        last_used_step BIGINT,
        created_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    # Mã khôi phục: BĂM, không mã hoá. Khác `user_totp.secret_enc` vì ở đây hệ
    # thống chỉ cần trả lời "mã người dùng gõ có đúng không", không cần đọc lại
    # mã — nên băm một chiều là đủ và an toàn hơn.
    """
    CREATE TABLE IF NOT EXISTS user_recovery_codes (
        code_hash  TEXT PRIMARY KEY,
        user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        used_at    TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_user_recovery_codes_user "
    "ON user_recovery_codes(user_id) WHERE used_at IS NULL",
    # ---------------------------------------------------------------------
    # v3.15 — Vòng lặp khoá ngoại tenant, lần thứ hai. Xem chú thích ở
    # TENANT_FK_LOOP_SQL: các bảng v3 và v4 vừa được tạo bên trên, sau khi lượt
    # chạy đầu tiên của vòng lặp đã đi qua chỗ chúng còn chưa tồn tại.
    TENANT_FK_LOOP_SQL,
]

def _column_exists(table: str, column: str) -> bool:
    # kiểm tra nếu column tồn tại trong table
    q = """
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
    LIMIT 1
    """
    try:
        with _cursor() as cur:
            cur.execute(q, (table, column))
            return cur.fetchone() is not None
    except Exception:
        logger.error(f"Error occurred while checking column existence: {table}.{column}")
        return False

def drop_all_tables():
    tables = [
        "training_metrics",
        "training_jobs",
        "raw_uploads",
        "samples",
        "classes",
        "refresh_tokens",
        "password_reset_tokens",
        "users",
        "google_sheets_sync_status"
    ]
    # DROP is DDL, so it goes through the migration role like every other schema
    # change — the application role is not permitted to demolish tables.
    with _migration_cursor() as cur:
        for t in tables:
            try:
                cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
            except Exception as exc:
                logger.warning("drop_all_tables: failed to drop %s: %s", t, getattr(exc, "pgerror", str(exc)))

def _seed_authorization(cur) -> None:
    """Nạp danh mục quyền + role dựng sẵn, trong system scope.

    Vì sao `set_config(..., false)` chứ không `SET LOCAL`
    -----------------------------------------------------
    `_migration_cursor` chạy autocommit, và `SET LOCAL` ngoài một giao dịch là
    lệnh không có tác dụng — Postgres còn cảnh báo đúng như vậy. Nên phạm vi
    được đặt ở mức PHIÊN.

    Điều khiến chuyện đó an toàn ở đây mà không an toàn ở `_cursor()`: kết nối
    này KHÔNG thuộc pool. `_migration_cursor` mở riêng và đóng ngay ở `finally`,
    nên không có kết nối nào mang theo `app.system_scope = 'on'` trở lại pool
    để request tiếp theo thừa hưởng. Đó chính là lỗi mà `storage/rls.py` cảnh
    báo, và lý do nó không xảy ra ở đây đáng được viết ra.

    Vì sao cần system scope: seed ghi role dựng sẵn với `tenant_id NULL`, và vế
    WITH CHECK của chính sách danh mục dùng chung từ chối dòng đó ở mọi tenant
    scope. Không có dòng này, chín role dựng sẵn lặng lẽ không bao giờ ra đời
    và mọi phép phân quyền trả về DENY.
    """
    from app.authorization.seed import seed_authorization_catalogue
    from app.storage.rls import SYSTEM_SCOPE_GUC, SYSTEM_SCOPE_ON

    try:
        cur.execute("SELECT set_config(%s, %s, false)", (SYSTEM_SCOPE_GUC, SYSTEM_SCOPE_ON))
        seed_authorization_catalogue(cur)
    except Exception as exc:
        # Cùng chính sách với `_run_ddl`: một lần seed hỏng không được chặn
        # khởi động, vì phần còn lại của schema vẫn dùng được và hệ cũ
        # (`is_admin`, `tenant_members.role`) vẫn đang cầm quyền trong suốt
        # shadow mode. `authz_schema.missing_objects()` và bộ test là nơi phát
        # hiện, không phải một lần crash lúc khởi động.
        logger.error("[AUTHZ-SEED] that bai: %s: %s", exc.__class__.__name__, exc)


def one_way_statements() -> frozenset[str]:
    """Mọi câu KHÔNG được chạy khi backend khởi động.

    "Một chiều" ở đây nghĩa là: chạy xong thì không có câu nào trong mã đưa cơ
    sở dữ liệu về lại trạng thái cũ. Bỏ bảng, bỏ chỉ mục duy nhất, chép dữ liệu
    lịch sử sang hình dạng mới, ghi đè giá trị cũ. Chúng đều được canh cẩn thận
    và đều đã chạy đúng — vấn đề không phải chúng sai, mà là **ai cho phép
    chúng chạy**. Trước 12/08/2026 câu trả lời là "bất kỳ ai gõ `docker compose
    up`", kể cả khi người đó chỉ định khởi động lại một service.

    Tập này có HAI nguồn, và nguồn thứ hai mới là biên giới thật:

      * **Danh sách tay** (`_DROP_*`, `AUTHZ_ONE_WAY_DDL`) — mười một câu đã
        được đọc từng chữ trong lượt vá 12/08/2026. Giữ lại làm lớp đỡ: nếu bộ
        phân loại có ngày phân loại sai, mười một câu này vẫn không lên được
        đường khởi động.
      * **Bộ phân loại** (`startup_ddl_policy`) — mọi câu KHÔNG chứng minh
        được là thuộc một hình dạng an toàn. Danh sách tay chỉ mạnh bằng trí
        nhớ của người viết nó; đo lại ngày 13/08/2026 thì có thêm ba mươi hai
        câu không ai đăng ký mà vẫn đổi dữ liệu hoặc đổi hình dạng cột ở mỗi
        lần khởi động — trong đó có đổi tên năm role, tắt role, đổi kiểu một
        cột sang `uuid`, và hai câu `RENAME COLUMN`.

    Nạp muộn cả hai vì `metadata_db` được chúng nhập ngược lại ở tầng module;
    nhập sớm sẽ thành vòng.
    """
    from app.storage.authz_schema import AUTHZ_ONE_WAY_DDL
    from app.storage.startup_ddl_policy import migration_only_statements

    by_hand = frozenset((
        _DROP_PRE_REGISTRY_DIALECTS,
        _DROP_DEAD_USER_PROFILES,
        # Bỏ DEFAULT của `users.tenant_id`. Đăng ký TAY vì bộ phân loại xếp
        # `ALTER ... DROP DEFAULT` vào nhóm an toàn theo hình dạng — đúng với
        # phần lớn cột, sai với cột này: bỏ default ở đây làm MỌI đường ghi
        # quên `tenant_id` chuyển từ "im lặng gán default" sang "nổ". Đó là
        # thay đổi hành vi, và nó phải đi qua `app.cli.migrate` chứ không lên
        # đường khởi động.
        _DROP_USERS_TENANT_DEFAULT,
        _DROP_TRAINING_JOBS_TENANT_DEFAULT,
        *_DROP_GLOBAL_CLASS_UNIQUES,
        *_DROP_PRE_REGION_CLASS_UNIQUE,
        *_DROP_COALESCE_REGION_UNIQUE,
        # v6: hợp nhất bốn mã gói cũ vào bốn mã mới. Bộ phân loại xếp `DO $$`
        # vào nhóm an toàn theo hình dạng — đúng với các khối tạo ràng buộc,
        # sai với khối này, vì nó CHUYỂN dữ liệu giữa các bảng. Đăng ký tay là
        # cách duy nhất để nó không lên đường khởi động.
        _BILLING_V6_RENAME_PLANS,
    )) | AUTHZ_ONE_WAY_DDL

    return by_hand | migration_only_statements()


#: `DROP INDEX [CONCURRENTLY] [IF EXISTS] <tên>` — bắt tên chỉ mục bị bỏ.
_RE_DROP_INDEX = re.compile(
    r"^\s*DROP\s+INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+EXISTS\s+)?"
    r"([A-Za-z_][A-Za-z0-9_.\"]*)", re.IGNORECASE)

#: `CREATE [UNIQUE] INDEX [CONCURRENTLY] [IF NOT EXISTS] <tên>`
_RE_CREATE_INDEX = re.compile(
    r"^\s*CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?"
    r"(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_.\"]*)", re.IGNORECASE)


def _all_schema_statements() -> list[str]:
    """Mọi câu DDL của lược đồ, gộp từ ba danh sách. Chỉ để SOI, không chạy."""
    from app.storage.authz_schema import AUTHZ_DDL_STATEMENTS

    ra: list[str] = []
    for ds in (DDL_STATEMENTS, INDEX_STATEMENTS, MIGRATION_STATEMENTS,
               AUTHZ_DDL_STATEMENTS):
        ra += [s for s in ds if isinstance(s, str)]
    return ra


def retired_indexes() -> frozenset[str]:
    """Chỉ mục ĐÃ RETIRE: bị một câu một chiều bỏ, và KHÔNG được tạo lại ở đâu.

    Suy ra từ chính các câu DDL chứ không liệt kê tay, và đó là cả điểm của
    hàm này. Sự cố 14/08 đã chứng minh liệt kê tay không đủ: câu
    `DROP INDEX uq_classes_tenant_slug_lang_dialect` được thêm vào danh sách
    một chiều, nhưng câu `CREATE` của chính chỉ mục đó vẫn nằm trong đường khởi
    động — nên migration bỏ nó, backend khởi động lại dựng nó lên nguyên vẹn,
    và ba biến thể vùng lại bị chặn. Không ai được báo.

    Điều kiện "và KHÔNG được tạo lại" là thứ phân biệt RETIRE với THAY THẾ:
    `uq_classes_tenant_slug_lang_dialect_region` cũng có một câu DROP (bản
    `coalesce` cũ phải bị bỏ trước khi dựng bản trần, vì
    `CREATE ... IF NOT EXISTS` lặng lẽ không thay thế một chỉ mục cùng tên).
    Nó bị bỏ RỒI TẠO LẠI, nên nó phải CÓ MẶT — không phải retire.

    Hệ quả có chủ ý: thêm một câu DROP mà quên gỡ câu CREATE thì hàm này trả
    về rỗng cho chỉ mục đó. Đúng ngữ nghĩa — một đối tượng vừa bị bỏ vừa được
    tạo là đối tượng đang được thay thế, và trạng thái đích của nó là CÓ MẶT.
    Cái bẫy 14/08 nằm ở chỗ khác: người viết TƯỞNG mình đã retire nó. Phép
    kiểm bắt được chuyện đó là `test_migration_retired_objects`, nó khẳng định
    danh sách này không rỗng và có chứa đúng chỉ mục ấy.
    """
    tao = set()
    for s in _all_schema_statements():
        m = _RE_CREATE_INDEX.match(s)
        if m:
            tao.add(m.group(1).strip('"').lower())

    bo = set()
    for s in one_way_statements():
        m = _RE_DROP_INDEX.match(s)
        if m:
            bo.add(m.group(1).strip('"').lower())

    return frozenset(bo - tao)


def creates_retired_object(stmt: str) -> str | None:
    """Tên đối tượng ĐÃ RETIRE mà câu lệnh này định tạo lại — hoặc None.

    Tồn tại để `app.sot.reader_sync` hỏi được cùng một câu hỏi mà
    `migrate --status` đang hỏi, bằng cùng một nguồn sự thật.

    Vì sao không để bên SOT tự liệt kê
    -----------------------------------
    Ngày 15/08/2026 phát hiện gói SOT `Ver5_06082026` — đã ký, hợp lệ, ký
    TRƯỚC khi `region` vào định danh lớp — mang theo một bản chụp đông lạnh của
    lược đồ cũ, trong đó có:

        CREATE UNIQUE INDEX IF NOT EXISTS uq_classes_tenant_slug_lang_dialect …

    `reader_sync` phát lại toàn bộ đoạn SQL ấy ở MỖI lượt sync, nên `migrate`
    gỡ chỉ mục rồi `sot_init` dựng lại ngay trong cùng một lượt triển khai. Đo
    được: `--status` xanh trước `up -d`, đỏ sau `up -d`.

    Một danh sách retire thứ hai nằm bên SOT sẽ trôi khỏi danh sách này đúng
    như mọi danh sách chép tay khác đã trôi. Một đối tượng đã retire phải có
    ĐÚNG MỘT nơi định nghĩa, và đó là `retired_indexes()` — thứ tự nó cũng suy
    ra từ các câu DDL chứ không viết tay.

    Nguyên tắc đằng sau, rộng hơn cái chỉ mục này:

        Một hiện vật lịch sử được phép MÔ TẢ lược đồ của thời điểm nó ra đời,
        nhưng không được phép vượt quyền migration để khôi phục thứ mà hệ
        thống hiện hành đã retire.
    """
    m = _RE_CREATE_INDEX.match((stmt or "").strip())
    if not m:
        return None
    ten = m.group(1).strip('"').lower()
    return ten if ten in retired_indexes() else None


def retired_still_present(cur) -> list[str]:
    """Đối tượng đáng lẽ đã biến mất mà vẫn còn trên cơ sở dữ liệu này.

    Đây là NỬA THỨ HAI của hợp đồng migration, và trước 15/08/2026 nó không tồn
    tại. `--status` chỉ chứng minh được "đối tượng CẦN CÓ đang có", nên trạng
    thái `chỉ mục mới có + chỉ mục cũ VẪN còn` được báo là *"khớp"* — trong khi
    lược đồ thực tế sai và biến thể vùng vẫn bị chặn.

    Một câu retire chạy hụt không để lại dấu vết nào khác. Nếu không có phép
    kiểm này thì không có gì phát hiện được nó.
    """
    ten = retired_indexes()
    if not ten:
        return []
    cur.execute(
        "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() "
        "AND lower(indexname) = ANY(%s)", (sorted(ten),))
    return [f"CHI MUC DA RETIRE VAN CON: {r[0]}" for r in cur.fetchall()]


def startup_safe(statements) -> list[str]:
    """Cùng danh sách đó, bỏ đi phần một chiều. Thứ tự tương đối giữ nguyên."""
    one_way = one_way_statements()
    return [stmt for stmt in statements if stmt not in one_way]


def ensure_tables():
    """Đường KHỞI ĐỘNG: chỉ thêm, chỉ bổ khuyết, không phá gì.

    Chạy ở mỗi lần backend lên, bốn lần song song (bốn worker gunicorn). Sau
    12/08/2026 nó KHÔNG còn là công cụ migration: phần một chiều bị lọc ra và
    chỉ `python -m app.cli.migrate` mới chạy được chúng.

    Nó vẫn chạy khá nhiều DDL, và đó là chủ ý: `CREATE TABLE IF NOT EXISTS`,
    `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, cài lại chính
    sách RLS. Tất cả đều bổ khuyết chứ không đổi hình dạng, nên một ảnh mới
    mang theo bảng mới của nó vẫn lên được mà không cần nghi thức. Ranh giới
    nằm ở chỗ: thêm thì tự làm, ĐỔI và BỎ thì phải có người ra lệnh.
    """
    _apply_schema(include_one_way=False)


def migrate_database(note: str | None = None, stamp: bool = True) -> None:
    """Đường MIGRATION: chạy đủ, kể cả phần một chiều, rồi đóng dấu phiên bản.

    Chỉ được gọi từ `app.cli.migrate` và từ bộ test. Đây chính là hành vi mà
    `ensure_tables()` từng có — không có gì mới ở đây, chỉ là bây giờ nó có một
    cái tên và một người phải gõ ra cái tên đó.
    """
    from app.storage.schema_version import APP_SCHEMA_VERSION, stamp_schema_version

    _apply_schema(include_one_way=True)

    if stamp:
        with _migration_cursor() as cur:
            stamp_schema_version(cur, APP_SCHEMA_VERSION, note=note)


def _apply_schema(*, include_one_way: bool):
    from app.storage.authz_schema import AUTHZ_DDL_STATEMENTS
    from app.storage.rls import rls_ddl
    from app.storage.schema_version import SCHEMA_VERSION_DDL

    def wanted(statements):
        return list(statements) if include_one_way else startup_safe(statements)

    # One migration connection for the whole run rather than one per statement:
    # these lists hold well over a hundred statements and each used to pay a
    # full connect+auth round trip.
    with _migration_cursor() as cur:
        from app.authorization.seed import SEED_LOCK_KEY

        # MỘT khoá tư vấn bao TOÀN BỘ lượt DDL, không chỉ khối phân quyền.
        #
        # Bản trước dừng phạm vi khoá ở khối phân quyền, với lập luận rằng hai
        # danh sách bên dưới "vốn đã chịu được chạy song song" nên giữ khoá qua
        # chúng chỉ làm ba worker chờ lâu hơn mà không mua được gì.
        #
        # Lập luận đó SAI, và lượt triển khai 12/08/2026 đo được bằng chứng —
        # bốn cảnh báo, mỗi lần khởi động:
        #
        #     constraint "ck_support_author_kind" ... already exists
        #     constraint "ck_support_author_kind_matches" ... already exists
        #     trigger "trg_legal_documents_freeze" ... already exists
        #     tuple concurrently updated : CREATE OR REPLACE FUNCTION
        #       legal_documents_freeze()
        #
        # Ba cái đầu là mẫu `DROP ...; ADD/CREATE ...` viết thành HAI câu: khe
        # giữa hai câu chính là chỗ đua. Worker A drop, worker B drop, A add
        # (thắng), B add (thua). Cái thứ tư là hai worker cùng
        # `CREATE OR REPLACE FUNCTION`, đua ngay trên catalog của Postgres —
        # thứ không guard nào ở tầng câu lệnh chữa được.
        #
        # Kết cục vẫn ĐÚNG ở cả bốn (câu sau tự lành, `_run_ddl` nuốt lỗi).
        # Nhưng chính chú thích cũ đã nêu vì sao thế vẫn chưa đủ: **cảnh báo
        # vĩnh viễn dạy người ta bỏ qua cảnh báo**. Trên năm service dùng chung
        # ảnh này, đó là hàng chục dòng mỗi lượt triển khai về một tình trạng
        # hoàn toàn bình thường — và lượt này đã phải lọc qua chúng để tìm ra
        # cảnh báo THẬT.
        #
        # Cái giá là có thật và nhỏ: bốn worker khởi động nối tiếp thay vì song
        # song ở phần DDL. Phần đó tính bằng giây, chạy đúng một lần cho mỗi
        # lần khởi động, và đổi lại là một nhật ký khởi động sạch — thứ đọc
        # được khi có sự cố.
        #
        # Mức PHIÊN chứ không mức giao dịch: `_migration_cursor` chạy autocommit
        # nên `pg_advisory_xact_lock` sẽ nhả ngay lập tức. Kết nối này không
        # thuộc pool và đóng ở `finally` của context manager, nên khoá không rò
        # sang ai. Khoá TÁI NHẬP ĐƯỢC, nên khối phân quyền bên dưới và `seed.py`
        # vẫn giữ khoá riêng của chúng mà không tự chặn mình.
        cur.execute("SELECT pg_advisory_lock(%s)", (SEED_LOCK_KEY,))
        try:
            # Sổ đăng bạ phiên bản trước mọi thứ khác: cổng khởi động đọc nó,
            # và một cổng không đọc được thì fail-closed trên máy cài mới —
            # tức là chặn cả đường đi đúng.
            _run_ddl(cur, SCHEMA_VERSION_DDL, "schema version")
            # Applied one-by-one so a later failure won't undo earlier successes.
            _run_ddl(cur, wanted(DDL_STATEMENTS), "DDL")
            _run_ddl(cur, wanted(MIGRATION_STATEMENTS), "migration")
        finally:
            cur.execute("SELECT pg_advisory_unlock(%s)", (SEED_LOCK_KEY,))

        # Mặt phẳng phân quyền, SAU hai danh sách trên: nó tham chiếu `users`,
        # `tenants` và `tenant_members`, cả ba đều ra đời ở đó. Chạy trước sẽ
        # làm mọi khoá ngoại thất bại lặng lẽ và để lại một cây phân quyền
        # không có ràng buộc nào — hình dạng nguy hiểm nhất, vì nó TRÔNG như
        # đã cài xong.
        # Cả khối phân quyền chạy dưới MỘT khoá tư vấn, vì `ensure_tables()`
        # KHÔNG chạy một lần: gunicorn dựng 4 worker và cả bốn gọi nó trong
        # cùng một mili giây. Đo được trên sản xuất — bốn dòng
        # "[DB_INIT] starting schema initialization" cùng dấu thời gian.
        #
        # Không có khoá, hai worker cùng chạy `DROP TRIGGER; CREATE TRIGGER`
        # thì một cái thắng và cái kia báo `trigger ... already exists`; hai
        # worker cùng seed thì một cái ăn `UniqueViolation`. Cả hai đều vô hại
        # ở đây (câu sau tự lành, `_run_ddl` nuốt lỗi) — nhưng chúng đẻ ra
        # cảnh báo vĩnh viễn, và cảnh báo vĩnh viễn dạy người ta bỏ qua cảnh
        # báo.
        #
        # Mức PHIÊN chứ không mức giao dịch: `_migration_cursor` chạy
        # autocommit nên `pg_advisory_xact_lock` sẽ nhả ngay lập tức. Kết nối
        # này không thuộc pool và đóng ở `finally` của context manager, nên
        # khoá không rò sang ai. Khoá tái nhập được, nên `seed.py` giữ khoá
        # riêng của nó mà không tự chặn mình.
        #
        # Phạm vi khoá dừng ở đây: tạo index và cài chính sách RLS bên dưới
        # dùng `IF NOT EXISTS` / `DROP POLICY IF EXISTS` nên vốn đã chịu được
        # chạy song song, và giữ khoá qua chúng chỉ làm ba worker phải chờ lâu
        # hơn ở mỗi lần khởi động mà không mua được gì.
        from app.authorization.seed import SEED_LOCK_KEY

        cur.execute("SELECT pg_advisory_lock(%s)", (SEED_LOCK_KEY,))
        try:
            _run_ddl(cur, wanted(AUTHZ_DDL_STATEMENTS), "authz")

            # Lần phát thứ BA của vòng lặp khoá ngoại tenant, và cần đúng như
            # hai lần trước cần: `MIGRATION_STATEMENTS` chạy nó ở hai vị trí,
            # cả hai đều TRƯỚC khi các bảng phân quyền tồn tại, nên
            # `CONTINUE WHEN to_regclass(...) IS NULL` bỏ qua chúng — im lặng,
            # đúng thiết kế, và để lại tám bảng không có khoá ngoại tenant.
            #
            # Trên máy này lỗi đó sẽ tự lành ở lần khởi động SAU, tức là không
            # bao giờ lộ ra lúc phát triển và chỉ hiện hình ở một lần cài mới.
            # Đó chính là bài học đã ghi trong chú thích của
            # `TENANT_FK_LOOP_SQL`; phát lại vòng lặp gốc là cách sửa, chép một
            # bản thứ hai thì không.
            _run_ddl(cur, [TENANT_FK_LOOP_SQL], "authz tenant fk")

            _seed_authorization(cur)
        finally:
            cur.execute("SELECT pg_advisory_unlock(%s)", (SEED_LOCK_KEY,))

        # Create indexes safely: check referenced columns exist first.
        #
        # Qua `wanted()` như ba danh sách trên, dù hôm nay không câu nào ở đây
        # là một chiều: bộ lọc phải phủ MỌI danh sách chạy lúc khởi động, nếu
        # không thì `test_no_irreversible_statement_survives_the_filter` sẽ
        # kiểm một tập khác với tập thực sự chạy — và một cái lưới đặt sai chỗ
        # chỉ tạo cảm giác an toàn.
        idx_re = re.compile(r"ON\s+([a-zA-Z_][\w]*)\s*\(([^)]+)\)", re.IGNORECASE)
        for stmt in wanted(INDEX_STATEMENTS):
            m = idx_re.search(stmt)
            if not m:
                # If we cannot parse, try to run but guard with exception
                _run_ddl(cur, [stmt], "index")
                continue

            table = m.group(1)
            cols = [c.strip().split()[0].strip('"') for c in m.group(2).split(",")]
            # check all columns exist
            all_exist = True
            for col in cols:
                if not _column_exists(table, col):
                    logger.warning("ensure_tables: skipping index creation because column missing: %s.%s", table, col)
                    all_exist = False
                    break

            if not all_exist:
                continue

            _run_ddl(cur, [stmt], "index")

        # Tenant isolation policies, last: they reference `tenant_id`, which the
        # migration statements above are responsible for adding. Installing them
        # earlier would fail on a database that predates the column and then be
        # skipped for the rest of that boot.
        _run_ddl(cur, rls_ddl(), "rls")

    verify_integrity_constraints()


# Constraint name -> the query that finds the rows blocking it, so a failure
# report can say WHICH data is in the way instead of only that something is.
_INTEGRITY_CONSTRAINTS = {
    "samples_uid_is_hex10": (
        "samples",
        "SELECT count(*) FROM samples WHERE sample_uid !~ '^[0-9a-f]{10}$'",
        "sample_uid khong phai 10 ky tu hex",
    ),
    "samples_file_path_is_local": (
        "samples",
        "SELECT count(*) FROM samples WHERE file_path LIKE 'http%'",
        "file_path dang chua URL thay vi duong dan cuc bo",
    ),
    # Đổi tên ở schema v3: bản một cột `samples_class_uid_fkey` cho phép mẫu của
    # tenant A trỏ sang lớp của tenant B, nên nó được thay bằng khoá ghép. Mục
    # này phải đổi theo, nếu không bộ kiểm tra sẽ mãi báo thiếu một ràng buộc đã
    # cố ý gỡ — một báo động giả, và báo động giả thì người ta tắt đi.
    "fk_samples_class_tenant": (
        "samples",
        "SELECT count(*) FROM samples s LEFT JOIN classes c "
        "ON c.class_uid = s.class_uid AND c.tenant_id = s.tenant_id "
        "WHERE s.class_uid IS NOT NULL AND c.class_uid IS NULL",
        "mau mo coi: (tenant_id, class_uid) khong tro toi lop nao",
    ),
    # 899 mẫu từng trỏ tới S010/S011 — hai id không có dòng nào trong `signers`.
    # Backfill v3.10 tạo dòng cho chúng; mục này canh để chuyện đó không tái diễn.
    "fk_samples_signer": (
        "samples",
        "SELECT count(*) FROM samples s LEFT JOIN signers g "
        "ON g.signer_id = s.signer_id AND g.tenant_id = s.tenant_id "
        "WHERE s.signer_id IS NOT NULL AND g.signer_id IS NULL",
        "mau tro toi signer_id khong co dong nao trong signers",
    ),
    "fk_training_metrics_job": (
        "training_metrics",
        "SELECT count(*) FROM training_metrics m LEFT JOIN training_jobs j "
        "ON j.job_id = m.job_id WHERE j.job_id IS NULL",
        "so lieu huan luyen mo coi: job_id khong tro toi job nao",
    ),
    "uq_classes_tenant_class_idx": (
        "classes",
        "SELECT coalesce(sum(n - 1), 0) FROM (SELECT count(*) AS n FROM classes "
        "WHERE deleted_at IS NULL AND class_idx IS NOT NULL "
        "GROUP BY tenant_id, class_idx HAVING count(*) > 1) d",
        "hai lop dung chung class_idx trong cung mot tenant (= chung mot o dau ra cua model)",
    ),
    "uq_classes_tenant_slug_lang_dialect_region": (
        "classes",
        "SELECT coalesce(sum(n - 1), 0) FROM (SELECT count(*) AS n FROM classes "
        "WHERE deleted_at IS NULL "
        "GROUP BY tenant_id, slug, language, dialect, coalesce(region, '') "
        "HAVING count(*) > 1) d",
        "hai lop trung (slug, language, dialect, region) trong cung mot tenant",
    ),
}


def verify_integrity_constraints() -> list[str]:
    """Report which integrity constraints are NOT in force, and why.

    Postgres refuses to add a CHECK/FK/unique index that the existing rows
    already violate, and ensure_tables() deliberately swallows DDL failures so
    one bad statement cannot block startup. Those two behaviours combine badly:
    on a database with pre-existing bad rows the constraints simply never
    apply, startup looks healthy, and the guarantees are quietly absent. That
    is how a deployment ends up believing it is protected when it is not.

    Measured on a database seeded with the exact damage this dataset suffered
    (an orphan sample, a spreadsheet-mangled uid, a Drive URL in file_path, two
    classes on one class_idx): 4 of the 5 constraints failed to apply and the
    only trace was a warning.

    So state it plainly, once, at startup, naming the offending row count and
    the fix. Returns the missing constraint names (empty list = fully armed).
    """
    missing: list[str] = []
    for name, (table, offender_sql, why) in _INTEGRITY_CONSTRAINTS.items():
        try:
            with _cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_constraint WHERE conname = %s "
                    "UNION ALL SELECT 1 FROM pg_indexes WHERE indexname = %s",
                    (name, name),
                )
                if cur.fetchone() is not None:
                    continue
        except Exception as exc:
            logger.warning("verify_integrity_constraints: cannot check %s: %s", name, exc)
            continue

        missing.append(name)
        try:
            with _cursor() as cur:
                cur.execute(offender_sql)
                bad = cur.fetchone()[0]
        except Exception:
            bad = "?"
        logger.error(
            "[INTEGRITY] %s KHONG duoc ap dung tren bang %s — %s hang dang vi pham (%s). "
            "Du lieu xau phai duoc don truoc; rang buoc se tu dong ap dung o lan khoi dong sau.",
            name, table, bad, why,
        )

    if missing:
        logger.error(
            "[INTEGRITY] %d/%d rang buoc KHONG co hieu luc: %s. "
            "Database nay dang KHONG duoc bao ve khoi cac loi da tung xay ra.",
            len(missing), len(_INTEGRITY_CONSTRAINTS), ", ".join(missing),
        )
    else:
        logger.info("[INTEGRITY] du %d/%d rang buoc toan ven dang co hieu luc.",
                    len(_INTEGRITY_CONSTRAINTS), len(_INTEGRITY_CONSTRAINTS))
    return missing


#: `tenant_id` TƯỜNG MINH. Trước 16/08/2026 câu này bỏ trống cột ấy và dựa vào
#: `DEFAULT 'default'` của lược đồ; sau khi default bị bỏ
#: (`_DROP_USERS_TENANT_DEFAULT`) nó sẽ nổ, và đó là hành vi đúng — nhưng đường
#: bootstrap thì THẬT SỰ thuộc tenant khởi tạo, nên nó nói ra điều đó.
SQL_UPSERT_USER = """
INSERT INTO users(id, username, email, password_hash, is_active, is_admin, created_at, tenant_id)
VALUES(%(id)s, %(username)s, %(email)s, %(password_hash)s, %(is_active)s, %(is_admin)s, %(created_at)s, %(tenant_id)s)
ON CONFLICT (id) DO UPDATE SET
    username = EXCLUDED.username,
    email = EXCLUDED.email,
    password_hash = EXCLUDED.password_hash,
    is_active = EXCLUDED.is_active,
    is_admin = EXCLUDED.is_admin,
    created_at = EXCLUDED.created_at
"""

SQL_UPSERT_CLASS = f"""
INSERT INTO classes(
    class_uid, class_idx, slug, label_original, language, dialect,
    is_common_global, is_common_language, folder_name, created_at, migrated_at,
    hands_required,
    semantic_label, vocabulary_scope, recognition_profile, vocabulary_group, collection_campaign, is_active,
    motion_type, tenant_id,
    region
)
VALUES(
    %(class_uid)s, %(class_idx)s, %(slug)s, %(label_original)s, %(language)s, %(dialect)s,
    %(is_common_global)s, %(is_common_language)s, %(folder_name)s, %(created_at)s, %(migrated_at)s,
    %(hands_required)s,
    %(semantic_label)s, %(vocabulary_scope)s, %(recognition_profile)s, %(vocabulary_group)s, %(collection_campaign)s, %(is_active)s,
    %(motion_type)s,
    -- Same rule as samples: absent means bootstrap tenant on INSERT only.
    COALESCE(%(tenant_id)s, '{DEFAULT_TENANT_ID}'),
    -- VẮNG MẶT khác NULL TƯỜNG MINH, và khác biệt đó là cả điểm của dòng này.
    --
    -- Gói SOT `Ver5_06082026` ra đời TRƯỚC khi cột `region` tồn tại, nên
    -- `labels.csv` của nó không có cột ấy. Hiểu "không có trường" thành "hãy
    -- ghi NULL" là để một hiện vật lịch sử **xoá** một chiều thông tin mà nó
    -- chưa từng biết là có. Đo được trên `signdb_test` ngày 15/08: 63/63 lớp
    -- mang `region` NULL, và vì thế `ALTER COLUMN region SET NOT NULL` không
    -- bao giờ chạy được — một vòng tự nuôi mình qua mỗi lượt chạy suite.
    -- Literal, khớp với `DEFAULT 'unclassified'` trong DDL của chính cột này.
    -- Không import `dataset_manager.REGION_UNCLASSIFIED`: module ấy import
    -- ngược lại tệp này.
    COALESCE(%(region)s, 'unclassified')
)
ON CONFLICT (class_uid) DO UPDATE SET
    class_idx = EXCLUDED.class_idx,
    slug = EXCLUDED.slug,
    label_original = EXCLUDED.label_original,
    language = EXCLUDED.language,
    dialect = EXCLUDED.dialect,
    is_common_global = EXCLUDED.is_common_global,
    is_common_language = EXCLUDED.is_common_language,
    folder_name = EXCLUDED.folder_name,
    created_at = EXCLUDED.created_at,
    migrated_at = EXCLUDED.migrated_at,
    hands_required = COALESCE(EXCLUDED.hands_required, classes.hands_required),
    semantic_label = COALESCE(EXCLUDED.semantic_label, classes.semantic_label),
    vocabulary_scope = COALESCE(EXCLUDED.vocabulary_scope, classes.vocabulary_scope),
    recognition_profile = COALESCE(EXCLUDED.recognition_profile, classes.recognition_profile),
    vocabulary_group = COALESCE(EXCLUDED.vocabulary_group, classes.vocabulary_group),
    collection_campaign = COALESCE(EXCLUDED.collection_campaign, classes.collection_campaign),
    is_active = COALESCE(EXCLUDED.is_active, classes.is_active),
    motion_type = COALESCE(EXCLUDED.motion_type, classes.motion_type),
    -- Parameter, not EXCLUDED — see the note on samples.tenant_id above.
    tenant_id = COALESCE(%(tenant_id)s, classes.tenant_id),
    -- GIỮ NGUYÊN khi hiện vật không nói gì về vùng.
    --
    -- `EXCLUDED.region` là NULL đúng khi gói không mang cột `region`, và khi đó
    -- giá trị đang có trên máy này là thứ ĐÚNG duy nhất còn lại. Ghi đè bằng
    -- rỗng sẽ biến `tom|hoa-de|nam` thành `tom|hoa-de|NULL` mỗi lượt sync — một
    -- gói cũ lặng lẽ gỡ bỏ công phân loại vùng.
    --
    -- THAM SỐ, không phải `EXCLUDED` — cùng lý do đã ghi ở `tenant_id`.
    --
    -- `EXCLUDED.region` là giá trị đã đi qua `COALESCE(%(region)s,'unclassified')`
    -- ở phần VALUES, nên nó KHÔNG BAO GIỜ NULL. Dùng nó ở đây thì mọi lượt
    -- upsert của một hiện vật không biết vùng sẽ ghi đè `nam` thành
    -- `unclassified` — vẫn là mất dữ liệu, chỉ đổi từ NULL sang một giá trị
    -- trông hợp lệ, tức là khó thấy hơn. Bài kiểm
    -- `test_hien_vat_cu_KHONG_co_khoa_region_thi_GIU_NGUYEN` bắt được đúng chỗ
    -- này ở bản vá đầu.
    region = COALESCE(%(region)s, classes.region)
"""

SQL_UPSERT_SIGNER = """
INSERT INTO signers(signer_id, display_name, regional_group, external_user_id, is_active, created_at)
VALUES(%(signer_id)s, %(display_name)s, %(regional_group)s, %(external_user_id)s, %(is_active)s, %(created_at)s)
ON CONFLICT (signer_id) DO UPDATE SET
    display_name = COALESCE(EXCLUDED.display_name, signers.display_name),
    regional_group = COALESCE(EXCLUDED.regional_group, signers.regional_group),
    external_user_id = COALESCE(EXCLUDED.external_user_id, signers.external_user_id),
    is_active = EXCLUDED.is_active
"""

SQL_UPSERT_SAMPLE = f"""
INSERT INTO samples(
    sample_uid, class_uid, slug, label_original, language, dialect,
    source_type, user_id, auth_user_id, session_id, fps_original, fps_processed,
    seq_len, augment_id, completeness, file_path, storage_url, checksum, created_at, gdrive_synced,
    left_hand_ratio, right_hand_ratio, both_hands_ratio, jitter, quality_flags,
    signer_id, collection_campaign, raw_landmarks_available, normalization_version,
    preprocess_contract_version, sequence_length_original, quality_status, tenant_id
)
VALUES(
    %(sample_uid)s, %(class_uid)s, %(slug)s, %(label_original)s, %(language)s, %(dialect)s,
    %(source_type)s, %(user_id)s, %(auth_user_id)s, %(session_id)s, %(fps_original)s, %(fps_processed)s,
    %(seq_len)s, %(augment_id)s, %(completeness)s, %(file_path)s, %(storage_url)s, %(checksum)s, %(created_at)s, %(gdrive_synced)s,
    %(left_hand_ratio)s, %(right_hand_ratio)s, %(both_hands_ratio)s, %(jitter)s, %(quality_flags)s,
    %(signer_id)s, %(collection_campaign)s, %(raw_landmarks_available)s, %(normalization_version)s,
    %(preprocess_contract_version)s, %(sequence_length_original)s, %(quality_status)s,
    -- A brand-new row with no stated tenant belongs to the bootstrap tenant.
    -- An explicit NULL would violate NOT NULL rather than fall back to the
    -- column DEFAULT, so the fallback is spelled out here.
    COALESCE(%(tenant_id)s, '{DEFAULT_TENANT_ID}')
)
ON CONFLICT (sample_uid) DO UPDATE SET
    class_uid = EXCLUDED.class_uid,
    slug = EXCLUDED.slug,
    label_original = EXCLUDED.label_original,
    language = EXCLUDED.language,
    dialect = EXCLUDED.dialect,
    source_type = EXCLUDED.source_type,
    user_id = EXCLUDED.user_id,
    auth_user_id = COALESCE(EXCLUDED.auth_user_id, samples.auth_user_id),
    session_id = EXCLUDED.session_id,
    fps_original = EXCLUDED.fps_original,
    fps_processed = EXCLUDED.fps_processed,
    seq_len = EXCLUDED.seq_len,
    augment_id = EXCLUDED.augment_id,
    completeness = EXCLUDED.completeness,
    file_path = COALESCE(EXCLUDED.file_path, samples.file_path),
    storage_url = COALESCE(EXCLUDED.storage_url, samples.storage_url),
    checksum = COALESCE(EXCLUDED.checksum, samples.checksum),
    created_at = EXCLUDED.created_at,
    gdrive_synced = EXCLUDED.gdrive_synced,
    left_hand_ratio = COALESCE(EXCLUDED.left_hand_ratio, samples.left_hand_ratio),
    right_hand_ratio = COALESCE(EXCLUDED.right_hand_ratio, samples.right_hand_ratio),
    both_hands_ratio = COALESCE(EXCLUDED.both_hands_ratio, samples.both_hands_ratio),
    jitter = COALESCE(EXCLUDED.jitter, samples.jitter),
    quality_flags = COALESCE(EXCLUDED.quality_flags, samples.quality_flags),
    signer_id = COALESCE(EXCLUDED.signer_id, samples.signer_id),
    collection_campaign = COALESCE(EXCLUDED.collection_campaign, samples.collection_campaign),
    raw_landmarks_available = COALESCE(EXCLUDED.raw_landmarks_available, samples.raw_landmarks_available),
    normalization_version = COALESCE(EXCLUDED.normalization_version, samples.normalization_version),
    preprocess_contract_version = COALESCE(EXCLUDED.preprocess_contract_version, samples.preprocess_contract_version),
    sequence_length_original = COALESCE(EXCLUDED.sequence_length_original, samples.sequence_length_original),
    quality_status = COALESCE(EXCLUDED.quality_status, samples.quality_status),
    -- Reads the PARAMETER, not EXCLUDED. EXCLUDED.tenant_id is the value after
    -- the VALUES clause already substituted the bootstrap tenant, so using it
    -- here would rewrite every existing row to 'default' whenever the incoming
    -- mirror row is silent about its tenant. Reading the parameter preserves
    -- the distinction between "no opinion" (keep what the DB has) and
    -- "belongs to X". (Spelled in prose on purpose: psycopg2 substitutes
    -- placeholders inside comments too, so writing one here would interpolate.)
    tenant_id = COALESCE(%(tenant_id)s, samples.tenant_id)
"""

SQL_UPSERT_RAW_UPLOAD = f"""
INSERT INTO raw_uploads(
    upload_uid, class_uid, slug, label_original, language, dialect,
    source_type, user_id, auth_user_id, session_id, original_filename,
    local_path, storage_key, storage_url, created_at, updated_at, tenant_id
)
VALUES(
    %(upload_uid)s, %(class_uid)s, %(slug)s, %(label_original)s, %(language)s, %(dialect)s,
    %(source_type)s, %(user_id)s, %(auth_user_id)s, %(session_id)s, %(original_filename)s,
    %(local_path)s, %(storage_key)s, %(storage_url)s, %(created_at)s, %(updated_at)s,
    -- raw_uploads is the third table the startup sync writes and the third
    -- table A3 puts under RLS. Leaving it without a tenant column here would
    -- keep the silent-reassignment bug alive in exactly one of the three.
    COALESCE(%(tenant_id)s, '{DEFAULT_TENANT_ID}')
)
ON CONFLICT (upload_uid) DO UPDATE SET
    class_uid = EXCLUDED.class_uid,
    slug = EXCLUDED.slug,
    label_original = EXCLUDED.label_original,
    language = EXCLUDED.language,
    dialect = EXCLUDED.dialect,
    source_type = EXCLUDED.source_type,
    user_id = EXCLUDED.user_id,
    auth_user_id = COALESCE(EXCLUDED.auth_user_id, raw_uploads.auth_user_id),
    session_id = EXCLUDED.session_id,
    original_filename = EXCLUDED.original_filename,
    local_path = COALESCE(EXCLUDED.local_path, raw_uploads.local_path),
    storage_key = COALESCE(EXCLUDED.storage_key, raw_uploads.storage_key),
    storage_url = COALESCE(EXCLUDED.storage_url, raw_uploads.storage_url),
    created_at = EXCLUDED.created_at,
    updated_at = EXCLUDED.updated_at,
    -- Parameter, not EXCLUDED — see the note on samples.tenant_id above.
    tenant_id = COALESCE(%(tenant_id)s, raw_uploads.tenant_id)
"""


def insert_user(row: Dict[str, Any]):
    """`tenant_id` là tham số BẮT BUỘC, không có mặc định trong Python.

    Đặt `tenant_id=DEFAULT_TENANT_ID` làm mặc định của hàm này chỉ chuyển phép
    rơi-về-default từ PostgreSQL lên Python — cùng một lỗ, khác tầng, và khó
    thấy hơn vì không còn nằm trong lược đồ. Người gọi nào thật sự muốn tenant
    khởi tạo thì phải viết ra, và khi ấy `grep DEFAULT_TENANT_ID` sẽ liệt kê
    đúng những chỗ cố ý dùng nguồn seed.
    """
    tenant = str(row.get("tenant_id") or "").strip()
    if not tenant:
        raise ValueError(
            "insert_user() can tenant_id tuong minh. Duong bootstrap thuoc "
            "tenant khoi tao thi truyen DEFAULT_TENANT_ID; dung de trong.")
    payload = {
        **row,
        "tenant_id": tenant,
        "is_active": _bool_value(row.get("is_active", True)),
        "is_admin": _bool_value(row.get("is_admin", False)),
    }
    _execute(SQL_UPSERT_USER, payload)


_CLASS_DB_KEYS = (
    "class_uid", "class_idx", "slug", "label_original", "language", "dialect",
    "is_common_global", "is_common_language", "folder_name", "created_at", "migrated_at",
    "hands_required",
    # vocabulary schema v2
    "semantic_label", "vocabulary_scope", "recognition_profile", "vocabulary_group",
    "collection_campaign", "is_active", "motion_type",
    # Vùng miền của ký hiệu — trục riêng, tách khỏi `dialect`. Xem
    # app/dataset_manager.py VALID_REGIONS.
    "region",
    # Spelled as a literal, not TENANT_COLUMN, on purpose: tests/
    # test_sot_schema_coverage.py reads these three tuples as SOURCE TEXT (so it
    # runs on a bare checkout with no DB), and a symbol here makes it extract the
    # identifier instead of the column name. The constant is still the single
    # source for dict keys and CSV headers, where nothing parses source.
    "tenant_id",
)


def _text_or_none(value: Any) -> Any:
    """"" and whitespace-only -> NULL, so ON CONFLICT COALESCE keeps the old value."""
    if value is None:
        return None
    return str(value).strip() or None


_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _uuid_or_none(value: Any) -> Any:
    """Anything that is not a well-formed UUID -> NULL.

    samples.csv now carries auth_user_id, and a CSV cell is a string: "" for
    every row written before the column existed, and a display name for rows a
    human edited by hand. Postgres rejects both against a UUID column with
    'invalid input syntax for type uuid', which would abort the whole
    CSV->Postgres sync on the first legacy row. NULL is the honest value —
    the owner is genuinely unknown, and the backfill CLI is what resolves it.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text if _UUID_RE.match(text) else None


def upsert_class(row: Dict[str, Any]):
    # Build defensively (row.get) so a partial dict - e.g. a labels.csv that is
    # missing an optional column - never raises KeyError mid-CRUD. Mirrors
    # insert_sample; ON CONFLICT DO UPDATE keeps existing behavior for full rows.
    # Keep the explicit key whitelist rather than **row: labels.csv rows arrive
    # with extra CSV-only cells, and a row missing one of these would otherwise
    # blow up inside _execute with a bare KeyError.
    payload = {k: row.get(k) for k in _CLASS_DB_KEYS}
    payload["class_idx"] = _int_or_none(payload.get("class_idx"))
    payload["is_common_global"] = _bool_value(payload.get("is_common_global"))
    payload["is_common_language"] = _bool_value(payload.get("is_common_language"))
    payload["created_at"] = _ts_or_none(payload.get("created_at"))
    payload["migrated_at"] = _ts_or_none(payload.get("migrated_at"))
    # CSV-derived rows may lack the column entirely or carry "" -> NULL;
    # ON CONFLICT COALESCEs so a lossy mirror upsert never wipes the value.
    payload["hands_required"] = _int_or_none(payload.get("hands_required"))
    for key in ("semantic_label", "vocabulary_scope", "recognition_profile",
                "vocabulary_group", "collection_campaign", "motion_type"):
        payload[key] = _text_or_none(payload.get(key))
    # is_active: absent -> NULL (COALESCE keeps DB value); present -> the bool.
    payload["is_active"] = (
        _bool_value(row.get("is_active", True))
        if str(row.get("is_active", "")).strip() != "" else None
    )
    # Same "absent means absent" rule as insert_sample.
    payload[TENANT_COLUMN] = optional_tenant_id(payload.get(TENANT_COLUMN))
    # `region`: VẮNG MẶT -> NULL (SQL COALESCE giữ giá trị đang có / đặt
    # 'unclassified' khi tạo mới); CÓ MẶT -> chuẩn hoá rồi ghi.
    #
    # Quy tắc tương thích ngược tổng quát, không riêng cột này:
    #
    #     KHÔNG CÓ TRƯỜNG  =  hiện vật không biết chiều thông tin này
    #                      ≠  NULL tường minh
    #                      ≠  đặt lại giá trị đang có
    #
    # `Ver5_06082026` publish trước khi cột `region` ra đời nên `labels.csv` của
    # nó không có cột ấy. Đọc sự vắng mặt đó thành "ghi NULL" là để một gói cũ
    # xoá một chiều thông tin nó chưa từng biết là có tồn tại.
    #
    # Chuỗi rỗng cũng tính là vắng mặt: CSV không phân biệt được "ô trống" với
    # "không có cột", và cả hai đều nghĩa là hiện vật không nói gì.
    # Import trong hàm: `dataset_manager` import ngược tệp này, nên import ở
    # đầu module sẽ thành vòng. Chuẩn hoá phải dùng CHUNG một hàm — hai bảng
    # ánh xạ vùng sẽ trôi khỏi nhau đúng như mọi danh sách chép tay khác.
    from app.dataset_manager import normalize_region

    # Ba trạng thái, không phải hai. `COALESCE` trong SQL chỉ thấy NULL, nên nếu
    # tầng này không tách chúng ra thì "gói cũ không biết vùng" và "gói mới cố ý
    # xoá vùng" nhập làm một — và cái sau lặng lẽ được đối xử như "giữ nguyên".
    if "region" not in row:
        # VẮNG MẶT: hiện vật không biết chiều này. SQL COALESCE giữ giá trị đang
        # có, hoặc đặt 'unclassified' khi tạo mới.
        payload["region"] = None
    elif row["region"] is None:
        # NULL TƯỜNG MINH: người gọi biết trường này và gửi rỗng. `csv` không bao
        # giờ sinh ra `None` — nó cho chuỗi rỗng — nên giá trị này chỉ đến từ một
        # payload có cấu trúc, tức là một khẳng định. Cột là NOT NULL và
        # `unclassified` đã là cách nói "chưa phân loại", nên không có nghĩa hợp
        # lệ nào cho NULL ở đây.
        raise ValueError(
            f"upsert_class({row.get('class_uid')!r}): region=None là NULL tường "
            f"minh, không phải 'không biết'. Bỏ hẳn khoá 'region' nếu hiện vật "
            f"không mang thông tin vùng, hoặc gửi 'unclassified'.")
    else:
        _vung = str(row["region"]).strip()
        # Ô TRỐNG của CSV: cùng nghĩa với vắng mặt. Một tệp CSV không phân biệt
        # được "cột không tồn tại" với "ô để trống", nên đọc nó thành một khẳng
        # định là đọc quá lời.
        payload["region"] = normalize_region(_vung) if _vung else None
    _execute(SQL_UPSERT_CLASS, payload)


def upsert_signer(row: Dict[str, Any]):
    payload = {
        "signer_id": row.get("signer_id"),
        "display_name": row.get("display_name"),
        "regional_group": _text_or_none(row.get("regional_group")),
        "external_user_id": _text_or_none(row.get("external_user_id")),
        "is_active": _bool_value(row.get("is_active", True)),
        "created_at": _ts_or_none(row.get("created_at")),
    }
    _execute(SQL_UPSERT_SIGNER, payload)


_SAMPLE_DB_KEYS = (
    "sample_uid", "class_uid", "slug", "label_original", "language", "dialect",
    "source_type", "user_id", "auth_user_id", "session_id", "fps_original", "fps_processed",
    "seq_len", "augment_id", "completeness", "file_path", "storage_url", "checksum",
    "created_at", "gdrive_synced",
    "left_hand_ratio", "right_hand_ratio", "both_hands_ratio", "jitter", "quality_flags",
    "signer_id", "collection_campaign", "raw_landmarks_available", "normalization_version",
    "preprocess_contract_version", "sequence_length_original", "quality_status",
    "tenant_id",   # literal — see the note in _CLASS_DB_KEYS
)


def insert_sample(row: Dict[str, Any]):
    # Rows can arrive from the CSV mirror, which lacks DB-only columns
    # (auth_user_id) and names the session column differently (session_uid).
    # Build the payload defensively so a missing key never raises KeyError
    # mid-CRUD; ON CONFLICT COALESCEs auth_user_id so a lossy mirror upsert
    # doesn't wipe the real value.
    payload = {k: row.get(k) for k in _SAMPLE_DB_KEYS}
    payload["auth_user_id"] = _uuid_or_none(payload.get("auth_user_id"))
    # None (not the bootstrap tenant) when the source says nothing — the SQL
    # substitutes on INSERT and preserves on CONFLICT. A malformed value raises
    # instead of being repaired, so a typo cannot become a new partition.
    payload[TENANT_COLUMN] = optional_tenant_id(payload.get(TENANT_COLUMN))
    if not payload.get("session_id"):
        payload["session_id"] = row.get("session_id") or row.get("session_uid") or ""
    # Numeric columns are empty strings in the CSV mirror; coerce "" -> NULL so
    # Postgres doesn't reject them ("invalid input syntax for type real/integer").
    payload["seq_len"] = _int_or_none(payload.get("seq_len"))
    payload["augment_id"] = _int_or_none(payload.get("augment_id"))
    payload["completeness"] = _float_or_none(payload.get("completeness"))
    for qc_key in ("left_hand_ratio", "right_hand_ratio", "both_hands_ratio", "jitter"):
        payload[qc_key] = _float_or_none(payload.get(qc_key))
    if payload.get("quality_flags") == "":
        payload["quality_flags"] = None
    # Same lossy-mirror rule as auth_user_id: a CSV/SOT row that carries no
    # checksum/URL/path must not blank the one already in the DB. A machine that
    # never computed these publishes them empty, and without this the snapshot
    # wipes them on every reader that did have them.
    for keep_key in ("checksum", "storage_url", "file_path"):
        payload[keep_key] = (str(payload.get(keep_key) or "").strip() or None)
    payload["sequence_length_original"] = _int_or_none(payload.get("sequence_length_original"))
    raw_avail = payload.get("raw_landmarks_available")
    payload["raw_landmarks_available"] = (
        None if raw_avail is None or str(raw_avail).strip() == "" else _bool_value(raw_avail)
    )
    for txt_key in ("signer_id", "collection_campaign", "normalization_version",
                    "preprocess_contract_version", "quality_status"):
        payload[txt_key] = (str(payload.get(txt_key) or "").strip() or None)
    payload["created_at"] = _ts_or_none(payload.get("created_at"))
    if payload.get("gdrive_synced") is None:
        payload["gdrive_synced"] = True
    _execute(SQL_UPSERT_SAMPLE, payload)


def upsert_sample(row: Dict[str, Any]):
    # backward-compatible name expected by catalog_sync
    insert_sample(row)


def delete_sample(sample_uid: str):
    _execute("DELETE FROM samples WHERE sample_uid = %s", (sample_uid,))


def update_sample_gdrive_url(sample_uid: str, storage_url: str):
    _execute(
        "UPDATE samples SET storage_url = %s, gdrive_synced = TRUE WHERE sample_uid = %s",
        (storage_url, sample_uid)
    )


def delete_samples_by_class(class_uid: str):
    _execute("DELETE FROM samples WHERE class_uid = %s", (class_uid,))


_RAW_UPLOAD_DB_KEYS = (
    "upload_uid", "class_uid", "slug", "label_original", "language", "dialect",
    "source_type", "user_id", "auth_user_id", "session_id", "original_filename",
    "local_path", "storage_key", "storage_url", "created_at", "updated_at",
    "tenant_id",   # literal — see the note in _CLASS_DB_KEYS
)


def insert_raw_upload(row: Dict[str, Any]):
    payload = {k: row.get(k) for k in _RAW_UPLOAD_DB_KEYS}
    payload["auth_user_id"] = _uuid_or_none(payload.get("auth_user_id"))
    payload[TENANT_COLUMN] = optional_tenant_id(payload.get(TENANT_COLUMN))
    if not payload.get("session_id"):
        payload["session_id"] = row.get("session_id") or row.get("session_uid") or ""
    payload["created_at"] = _ts_or_none(payload.get("created_at"))
    payload["updated_at"] = _ts_or_none(payload.get("updated_at"))
    for keep_key in ("local_path", "storage_key", "storage_url"):
        payload[keep_key] = (str(payload.get(keep_key) or "").strip() or None)
    _execute(SQL_UPSERT_RAW_UPLOAD, payload)


def update_raw_upload_gdrive_url(upload_uid: str, storage_url: str):
    from datetime import datetime

    _execute(
        "UPDATE raw_uploads SET storage_url = %s, updated_at = %s WHERE upload_uid = %s",
        (storage_url, datetime.utcnow().isoformat() + "Z", upload_uid),
    )


# ============================================================================
# Training jobs persistence
#
# Source of truth for training job history — the in-memory dict in the
# training router is only a hot cache. All writes are idempotent upserts so
# the router can call them from any state transition without ordering bugs.
# ============================================================================

SQL_UPSERT_TRAINING_JOB = f"""
INSERT INTO training_jobs(
    job_id, status, model_type, config, auth_user_id, {TENANT_COLUMN},
    created_at, started_at, completed_at,
    current_epoch, total_epochs, checkpoint_path,
    test_acc, test_f1, error_message, promoted_at, evaluation
)
VALUES(
    %(job_id)s, %(status)s, %(model_type)s, %(config)s, %(auth_user_id)s,
    %({TENANT_COLUMN})s,
    %(created_at)s, %(started_at)s, %(completed_at)s,
    %(current_epoch)s, %(total_epochs)s, %(checkpoint_path)s,
    %(test_acc)s, %(test_f1)s, %(error_message)s, %(promoted_at)s, %(evaluation)s
)
ON CONFLICT (job_id) DO UPDATE SET
    status = EXCLUDED.status,
    started_at = EXCLUDED.started_at,
    completed_at = EXCLUDED.completed_at,
    current_epoch = EXCLUDED.current_epoch,
    checkpoint_path = EXCLUDED.checkpoint_path,
    test_acc = EXCLUDED.test_acc,
    test_f1 = EXCLUDED.test_f1,
    error_message = EXCLUDED.error_message,
    promoted_at = EXCLUDED.promoted_at,
    evaluation = COALESCE(EXCLUDED.evaluation, training_jobs.evaluation)
"""


def upsert_training_job(row: Dict[str, Any]):
    """Persist a job. The tenant comes from the AMBIENT SCOPE, not from `row`.

    This statement never carried `tenant_id`, so every job relied on the column
    default and landed in the bootstrap tenant. Harmless while one tenant
    existed; wrong the moment a second one did, and — once RLS is on the table —
    an outright failure, because WITH CHECK would refuse a row whose tenant does
    not match the scope writing it.

    Phạm vi đang hành động — chứ không phải một giá trị do người gọi đưa vào —
    vì cùng lý do `apply_scope` đọc ContextVar: người gọi không được lập hồ sơ
    job dưới một tenant khác tenant mình đang hành động.

    KHÔNG rơi về `default` ở CẢ HAI nhánh — sửa 16/08/2026
    -----------------------------------------------------
    Bản trước:

        system scope  ->  row.tenant  or DEFAULT_TENANT_ID
        request scope ->  ambient_tenant()   (= current_tenant() or DEFAULT_TENANT_ID)

    tức cả hai nhánh đều hạ cánh xuống tenant khởi tạo khi không biết tenant.
    Với một tác vụ Celery mất `tenant_id`, job của tổ chức A được lập hồ sơ
    dưới `default` — và mọi thứ móc vào job đó (hợp đồng lớp, hiện vật, sự
    kiện) đi theo.

    Ý định gốc vẫn giữ nguyên và vẫn đúng: người gọi KHÔNG được tự khai một
    tenant khác tenant mình đang hành động. Chỉ đổi cách xử khi không biết —
    từ "đoán là `default`" thành "từ chối".
    """
    from app.tenant_context import in_system_scope, require_tenant

    payload = dict(row)
    payload.setdefault("evaluation", None)
    if in_system_scope():
        # Tác vụ nền không có request, nên tenant phải đi theo CHÍNH HÀNG job.
        # Thiếu thì đó là vi phạm hợp đồng, không phải chỗ để đoán.
        tenant = optional_tenant_id(payload.get(TENANT_COLUMN))
        if not tenant:
            raise ValueError(
                "upsert_training_job: hang job khong mang tenant_id va dang "
                "chay trong system scope. Khong suy ra 'default' — mot job "
                "thieu pham vi phai hong, khong duoc doi chu.")
        payload[TENANT_COLUMN] = tenant
    else:
        # Đường request: lấy từ phạm vi đang hành động, và `require_tenant()`
        # ném lỗi khi không có — khác `ambient_tenant()` vốn trả `default`.
        payload[TENANT_COLUMN] = require_tenant()
    for jsonb_field in ("config", "evaluation"):
        value = payload.get(jsonb_field)
        if isinstance(value, (dict, list)):
            payload[jsonb_field] = Json(value)
    _execute(SQL_UPSERT_TRAINING_JOB, payload)


def insert_training_metric(row: Dict[str, Any]):
    """Tenant của chỉ số được SUY RA từ hàng job cha, ngay tại chỗ ghi.

    Chữ ký cố ý KHÔNG nhận `tenant_id`. Người gọi tự khai tenant thì giá trị ấy
    trở thành thẩm quyền, và thẩm quyền của đầu ra phải là hàng job đã lưu —
    không phải điều mà lượt gọi đang chạy tuyên bố. Đây là cùng một luật đã áp
    cho `upsert_training_job` ở C2a và cho hiện vật chia dữ liệu ở C2b:

    ```
    output.tenant_id  <-  PersistedTrainingJob.tenant_id
    ```

    `INSERT ... SELECT ... FROM training_jobs` làm việc suy ra đó xảy ra bên
    trong CSDL, nên không có khoảng nào để một giá trị khác chen vào giữa lúc
    đọc job và lúc ghi chỉ số.

    Hệ quả phụ mà ta MUỐN: job không tồn tại thì `SELECT` không ra dòng nào và
    lượt ghi lặng lẽ không làm gì — thay vì tạo một chỉ số mồ côi không tra
    được chủ. Và vì `training_jobs` nằm dưới RLS, câu `SELECT` này chỉ nhìn
    thấy job trong phạm vi đang chạy: một tiến trình thuộc tổ chức khác không
    ghi được chỉ số vào job của A.
    """
    _execute(
        """
        INSERT INTO training_metrics(
            job_id, epoch, train_loss, train_acc, val_loss, val_acc, val_f1,
            tenant_id)
        SELECT %(job_id)s, %(epoch)s, %(train_loss)s, %(train_acc)s,
               %(val_loss)s, %(val_acc)s, %(val_f1)s, j.tenant_id
        FROM training_jobs j WHERE j.job_id = %(job_id)s
        ON CONFLICT (job_id, epoch) DO NOTHING
        """,
        row,
    )


def _fetch_all(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    conn = get_pooled_conn()
    broken = False
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                apply_scope(cur)  # see _cursor(); same reasoning, read path
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]
    except Exception:
        broken = bool(getattr(conn, "closed", 0))
        raise
    finally:
        put_pooled_conn(conn, close=broken)


def get_training_job(job_id: str) -> Optional[Dict[str, Any]]:
    rows = _fetch_all("SELECT * FROM training_jobs WHERE job_id = %s", (job_id,))
    return rows[0] if rows else None


def list_training_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    return _fetch_all(
        "SELECT * FROM training_jobs ORDER BY created_at DESC LIMIT %s", (limit,)
    )


def list_training_jobs_with_user(limit: int = 100) -> List[Dict[str, Any]]:
    """Job history rows + username of who started each job (for the history UI).

    Excludes the heavy `evaluation` JSONB — the list view doesn't need
    confusion matrices; the detail view fetches them per job.
    """
    return _fetch_all(
        """
        SELECT
            t.job_id, t.status, t.model_type, t.config, t.auth_user_id,
            t.created_at, t.started_at, t.completed_at,
            t.current_epoch, t.total_epochs, t.checkpoint_path,
            t.test_acc, t.test_f1, t.error_message, t.promoted_at, t.superseded_at,
            u.username
        FROM training_jobs t
        LEFT JOIN users u ON u.id = t.auth_user_id
        ORDER BY t.created_at DESC
        LIMIT %s
        """,
        (limit,),
    )


_VOCAB_FK_TARGETS = (
    ("classes", "classes_dialect_fkey"),
    ("samples", "samples_dialect_fkey"),
)


def ensure_vocabulary_foreign_keys() -> Dict[str, str]:
    """Point `classes.dialect` and `samples.dialect` at the dialect registry.

    This is the constraint the whole registry design rests on: an allow-list
    checked in Python can be bypassed or fail open, but a FOREIGN KEY refuses a
    bad value at write time, every time, from every code path.

    The key is COMPOSITE. `dialects` is keyed `(tenant_id, dialect_id)` for
    multitenancy, so `REFERENCES dialects(dialect_id)` is rejected by Postgres
    with "there is no unique constraint matching given keys" — the plan
    recorded in MERGE_WORK_LOG.md was wrong on this point.

    Must run AFTER the registry is seeded: a foreign key cannot be added while
    referencing rows do not exist yet.

    Every failure is caught and reported rather than raised — a missing
    constraint degrades enforcement, but a raise here would block startup, and
    the most likely cause (a row naming an unregistered dialect) is exactly the
    situation where the operator needs the app up to go fix the data.

    Returns {table: "added" | "exists" | "<error>"}.
    """
    result: Dict[str, str] = {}
    for table, constraint in _VOCAB_FK_TARGETS:
        try:
            # ALTER TABLE — migration role, not the application pool.
            with _migration_cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_constraint WHERE conname = %s", (constraint,)
                )
                if cur.fetchone():
                    result[table] = "exists"
                    continue
                cur.execute(
                    f"""
                    ALTER TABLE {table}
                      ADD CONSTRAINT {constraint}
                      FOREIGN KEY (tenant_id, dialect)
                      REFERENCES dialects(tenant_id, dialect_id)
                      ON UPDATE CASCADE
                    """
                )
            result[table] = "added"
            logger.info("[VOCAB_FK] %s.dialect -> dialects(dialect_id) đã cắm", table)
        except Exception as exc:
            msg = str(getattr(exc, "pgerror", None) or exc).strip().splitlines()[0]
            result[table] = msg
            logger.warning(
                "[VOCAB_FK] không cắm được FK cho %s (%s). Danh mục vẫn chạy, "
                "nhưng giá trị dialect lạ sẽ KHÔNG bị chặn ở tầng DB.", table, msg,
            )
    return result


def unregistered_dialects_in_use() -> List[Dict[str, Any]]:
    """Rows whose (tenant_id, dialect) has no row in the registry.

    Run this before adding the foreign keys: it names exactly what would block
    them, instead of leaving the operator with a bare Postgres error.
    """
    return _fetch_all(
        """
        SELECT 'classes' AS src, c.tenant_id, c.dialect, COUNT(*) AS n
          FROM classes c
         WHERE NOT EXISTS (SELECT 1 FROM dialects d
                            WHERE d.tenant_id = c.tenant_id AND d.dialect_id = c.dialect)
         GROUP BY 1, 2, 3
        UNION ALL
        SELECT 'samples', s.tenant_id, s.dialect, COUNT(*)
          FROM samples s
         WHERE NOT EXISTS (SELECT 1 FROM dialects d
                            WHERE d.tenant_id = s.tenant_id AND d.dialect_id = s.dialect)
         GROUP BY 1, 2, 3
        ORDER BY 4 DESC
        """
    )


def supersede_other_promotions(job_id: str, dialect: str) -> List[str]:
    """Record that `job_id` is now THE promoted model for `dialect`.

    The realtime registry keys one slot per dialect, so promoting a new job
    silently deletes the previous job's entry from models.json. Nothing used to
    update the database to match, leaving two jobs both flagged as promoted for
    one dialect — the history UI showed both as live, and a retention sweep that
    keeps "promoted" checkpoints could never retire the old one.

    Both statements share one `_cursor()`, hence one transaction: a crash
    between them would otherwise leave the dialect with zero current models.

    `dialect` is read out of the config JSONB because training_jobs has no
    dialect column; `COALESCE(..., 'multi')` mirrors the router's own default
    for a job that names no dialect.

    Returns the ids that were just superseded, so the caller can update its
    in-memory job cache (which does not re-read terminal jobs from the DB).
    """
    with _cursor() as cur:
        cur.execute(
            """
            UPDATE training_jobs
               SET superseded_at = NOW()
             WHERE job_id <> %(job_id)s
               AND promoted_at IS NOT NULL
               AND superseded_at IS NULL
               AND COALESCE(config->'dialects'->>0, 'multi') = %(dialect)s
            RETURNING job_id
            """,
            {"job_id": job_id, "dialect": dialect},
        )
        superseded = [str(r[0]) for r in cur.fetchall()]
        # Re-promoting a job that was itself superseded earlier must clear its
        # own marker, otherwise it would display as retired while serving.
        cur.execute(
            "UPDATE training_jobs SET superseded_at = NULL WHERE job_id = %s",
            (job_id,),
        )
    return superseded


def list_training_metrics(job_id: str) -> List[Dict[str, Any]]:
    return _fetch_all(
        "SELECT * FROM training_metrics WHERE job_id = %s ORDER BY epoch ASC", (job_id,)
    )


def delete_training_job(job_id: str) -> None:
    """Xóa training job khỏi lịch sử (kèm metrics liên quan).

    Không xóa checkpoint file trên đĩa — job đã promote có thể vẫn đang
    được realtime service dùng; chỉ dọn bản ghi lịch sử.
    """
    _execute("DELETE FROM training_metrics WHERE job_id = %s", (job_id,))
    _execute("DELETE FROM training_jobs WHERE job_id = %s", (job_id,))


def upsert_raw_upload(row: Dict[str, Any]):
    # backward-compatible name expected by catalog_sync
    insert_raw_upload(row)


def delete_raw_upload(upload_uid: str):
    _execute("DELETE FROM raw_uploads WHERE upload_uid = %s", (upload_uid,))


def delete_raw_uploads_by_class(class_uid: str):
    _execute("DELETE FROM raw_uploads WHERE class_uid = %s", (class_uid,))


def delete_class(class_uid: str):
    _execute("DELETE FROM classes WHERE class_uid = %s", (class_uid,))


# ---------------------------------------------------------------------------
# Soft delete / restore (Trash) — sets deleted_at instead of removing the row.
# Files and Drive content are kept; a purge (hard delete) removes them later.
# ---------------------------------------------------------------------------

def soft_delete_class(class_uid: str):
    _execute("UPDATE classes SET deleted_at = NOW() WHERE class_uid = %s AND deleted_at IS NULL", (class_uid,))


def soft_delete_samples_by_class(class_uid: str):
    _execute("UPDATE samples SET deleted_at = NOW() WHERE class_uid = %s AND deleted_at IS NULL", (class_uid,))


def soft_delete_raw_uploads_by_class(class_uid: str):
    _execute("UPDATE raw_uploads SET deleted_at = NOW() WHERE class_uid = %s AND deleted_at IS NULL", (class_uid,))


def restore_class(class_uid: str):
    _execute("UPDATE classes SET deleted_at = NULL WHERE class_uid = %s", (class_uid,))


def restore_samples_by_class(class_uid: str):
    _execute("UPDATE samples SET deleted_at = NULL WHERE class_uid = %s", (class_uid,))


def restore_raw_uploads_by_class(class_uid: str):
    _execute("UPDATE raw_uploads SET deleted_at = NULL WHERE class_uid = %s", (class_uid,))


def soft_delete_sample(sample_uid: str):
    _execute("UPDATE samples SET deleted_at = NOW() WHERE sample_uid = %s AND deleted_at IS NULL", (sample_uid,))


def restore_sample(sample_uid: str):
    _execute("UPDATE samples SET deleted_at = NULL WHERE sample_uid = %s", (sample_uid,))


def list_deleted_classes() -> List[Dict[str, Any]]:
    """Soft-deleted classes for the Trash view, with their live sample counts."""
    return _fetch_all(
        """
        SELECT c.class_uid, c.class_idx, c.slug, c.label_original, c.language,
               c.dialect, c.is_common_global, c.is_common_language, c.folder_name,
               c.created_at, c.migrated_at, c.deleted_at,
               (SELECT COUNT(*) FROM samples s WHERE s.class_uid = c.class_uid) AS sample_count
        FROM classes c
        WHERE c.deleted_at IS NOT NULL
        ORDER BY c.deleted_at DESC
        """
    )


def get_deleted_class(class_uid: str) -> Optional[Dict[str, Any]]:
    rows = _fetch_all("SELECT * FROM classes WHERE class_uid = %s AND deleted_at IS NOT NULL", (class_uid,))
    return rows[0] if rows else None


def list_samples_by_class(class_uid: str, include_deleted: bool = True) -> List[Dict[str, Any]]:
    where = "class_uid = %s" if include_deleted else "class_uid = %s AND deleted_at IS NULL"
    return _fetch_all(f"SELECT * FROM samples WHERE {where}", (class_uid,))


def list_deleted_samples() -> List[Dict[str, Any]]:
    """Soft-deleted samples whose CLASS is still active (class-level trash lists
    classes separately, so this avoids double-listing a whole deleted class)."""
    return _fetch_all(
        """
        SELECT s.sample_uid, s.class_uid, s.slug, s.label_original, s.language,
               s.dialect, s.source_type, s.user_id, u.username, s.file_path,
               s.storage_url, s.seq_len, s.created_at, s.deleted_at
        FROM samples s
        JOIN classes c ON c.class_uid = s.class_uid
        LEFT JOIN users u ON u.id = s.auth_user_id
        WHERE s.deleted_at IS NOT NULL AND c.deleted_at IS NULL
        ORDER BY s.deleted_at DESC
        """
    )


def list_active_samples() -> List[Dict[str, Any]]:
    """Every non-deleted sample with the columns needed to rebuild a samples.csv
    row. Used by the reconcile safety-net (Postgres is authoritative; samples.csv
    can rarely lose an appended row to a catalog-rewrite race)."""
    # tenant_id is REQUIRED here, not optional: _db_row_to_csv_row() projects
    # onto SAMPLE_FIELDS and writes "" for any column this query omits, so
    # leaving it out would have the safety-net heal a lost row back into the
    # source of truth with no tenant at all.
    #
    # The other omissions (auth_user_id, the quality columns, signer_id,
    # normalization_version) predate A1 and are left alone deliberately — a
    # reconciled row is already lossy in those fields and widening this query is
    # a separate change with its own test surface. Recorded in the A1 report.
    return _fetch_all(
        """
        SELECT sample_uid, class_uid, slug, label_original, language, dialect,
               source_type, user_id, session_id, fps_original, fps_processed,
               seq_len, augment_id, completeness, file_path, storage_url,
               checksum, created_at, tenant_id
        FROM samples
        WHERE deleted_at IS NULL
        """
    )


def list_all_deleted_samples() -> List[Dict[str, Any]]:
    """EVERY soft-deleted sample (regardless of whether its class is also deleted),
    projected to the samples.csv columns + deleted_at. Used by the Google Sheets
    mirror so a soft-deleted row stays on the sheet WITH a deleted_at marker
    instead of vanishing and shifting every row below it up by one.
    storage_key mirrors file_path (not a stored column)."""
    return _fetch_all(
        """
        SELECT sample_uid, class_uid, slug, label_original, language, dialect,
               source_type, user_id, session_id, fps_original, fps_processed,
               seq_len, augment_id, completeness, file_path,
               file_path AS storage_key, storage_url, checksum,
               created_at, deleted_at
        FROM samples
        WHERE deleted_at IS NOT NULL
        """
    )


def list_deleted_samples_for_user(auth_user_id: str) -> List[Dict[str, Any]]:
    """Soft-deleted samples OWNED by one user (auth_user_id), whose class is
    still active. Powers each contributor's own Trash — ownership is by UUID, not
    by the display name in user_id/username."""
    return _fetch_all(
        """
        SELECT s.sample_uid, s.class_uid, s.slug, s.label_original, s.language,
               s.dialect, s.source_type, s.user_id, u.username, s.file_path,
               s.storage_url, s.seq_len, s.created_at, s.deleted_at
        FROM samples s
        JOIN classes c ON c.class_uid = s.class_uid
        LEFT JOIN users u ON u.id = s.auth_user_id
        WHERE s.deleted_at IS NOT NULL AND c.deleted_at IS NULL
          AND s.auth_user_id = %s
        ORDER BY s.deleted_at DESC
        """,
        (auth_user_id,),
    )


def get_deleted_sample(sample_uid: str) -> Optional[Dict[str, Any]]:
    rows = _fetch_all("SELECT * FROM samples WHERE sample_uid = %s AND deleted_at IS NOT NULL", (sample_uid,))
    return rows[0] if rows else None


def get_sample_owner(sample_uid: str):
    """Return auth_user_id (str or None) for a sample. Used for ownership checks."""
    try:
        with _cursor() as cur:
            cur.execute(
                "SELECT auth_user_id FROM samples WHERE sample_uid = %s",
                (sample_uid,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return str(row[0]) if row[0] is not None else None
    except Exception:
        return None


def get_sample_owners(sample_uids: list) -> Dict[str, Any]:
    """Batch variant of get_sample_owner — one query for many uids.

    Returns {sample_uid: auth_user_id_str_or_None}. Missing uids are simply
    absent from the dict. Avoids the N+1 query when a page lists many sessions.
    """
    uids = [u for u in (sample_uids or []) if u]
    if not uids:
        return {}
    try:
        with _cursor() as cur:
            cur.execute(
                "SELECT sample_uid, auth_user_id FROM samples WHERE sample_uid = ANY(%s)",
                (uids,),
            )
            return {
                str(row[0]): (str(row[1]) if row[1] is not None else None)
                for row in cur.fetchall()
            }
    except Exception:
        return {}


class OwnershipSplit(NamedTuple):
    """How a batch of sample_uids relates to one caller.

    Four buckets, not two, because "not yours" has three different causes and
    the API must be able to say which one. `unowned` in particular is the
    historical data whose auth_user_id was never recorded (see
    cli/backfill_sample_owners.py) — reporting those as "foreign" would tell a
    contributor their own recordings belong to someone else.
    """

    owned: List[str]
    foreign: List[str]     # belongs to a different account
    unowned: List[str]     # auth_user_id IS NULL — legacy/guest, admin only
    missing: List[str]     # no such sample_uid in Postgres

    @property
    def skipped(self) -> List[str]:
        return [*self.foreign, *self.unowned, *self.missing]


def partition_sample_ownership(sample_uids: list, owner_id: str) -> OwnershipSplit:
    """Split uids by ownership using ONE query (the batch form of an ownership
    check). Order within each bucket follows the caller's input order so error
    messages can quote uids the user recognises.

    A DB failure yields everything in `missing`: refusing the whole batch is the
    safe direction — the alternative (treating an unreadable owner as "yours")
    would let one contributor purge another's samples during an outage.
    """
    uids: List[str] = []
    seen = set()
    for u in (sample_uids or []):
        u = str(u or "").strip()
        if u and u not in seen:
            seen.add(u)
            uids.append(u)
    if not uids:
        return OwnershipSplit([], [], [], [])

    owners = get_sample_owners(uids)
    me = str(owner_id or "")
    owned, foreign, unowned, missing = [], [], [], []
    for u in uids:
        if u not in owners:
            missing.append(u)
        elif owners[u] is None:
            unowned.append(u)
        elif str(owners[u]) == me:
            owned.append(u)
        else:
            foreign.append(u)
    return OwnershipSplit(owned, foreign, unowned, missing)


# ---------------------------------------------------------------------------
# Sample ownership backfill support
#
# samples.csv historically had no auth_user_id column, so every row imported
# from a CSV lands with a NULL owner and disappears from its contributor's
# Trash. These helpers let cli/backfill_sample_owners.py reconstruct the link
# from the display name / UUID left behind in samples.user_id.
# ---------------------------------------------------------------------------

def list_users_basic() -> List[Dict[str, Any]]:
    """id/username/email for every user — the lookup table a backfill matches
    display names against. Small table; no paging needed."""
    return _fetch_all("SELECT id, username, email, is_admin FROM users ORDER BY created_at")


def sample_owner_gap_report() -> List[Dict[str, Any]]:
    """Per `user_id` value: how many samples still have no auth_user_id.

    Grouping by the raw user_id is what makes the gap actionable — it turns
    "3855 rows have no owner" into "Khoa: 110, Trâm: 45, …", which a human can
    confirm account by account.
    """
    return _fetch_all(
        """
        SELECT COALESCE(NULLIF(TRIM(user_id), ''), '(trống)') AS user_key,
               COUNT(*) AS n,
               MIN(created_at) AS first_seen,
               MAX(created_at) AS last_seen
        FROM samples
        WHERE auth_user_id IS NULL
        GROUP BY user_key
        ORDER BY n DESC
        """
    )


def observed_owner_by_user_id() -> List[Dict[str, Any]]:
    """For each `user_id` value, which account(s) ALREADY own rows carrying it.

    This is the only evidence-based way to guess an owner on this machine, and
    the query exists to show how weak the guess is. Measured 2026-08-01 on the
    dev database (3692 owned rows):

        user_id 'Khoa'  -> account Khoa 340 rows, account Minh 129 rows
        user_id 'Trân'  -> account Minh 620 rows   (the Trân ACCOUNT owns none)
        user_id 'Ảnh'   -> account Minh 405 rows

    So `user_id` is the person who SIGNED and `auth_user_id` is the account that
    ran the capture station — different questions. Matching a name to the
    same-named account would have handed 620 of Minh's recordings to Trân.

    Only a value whose rows are unanimous on one account is a usable proposal;
    `accounts > 1` means refuse.
    """
    return _fetch_all(
        """
        SELECT TRIM(COALESCE(user_id, '')) AS user_key,
               COUNT(DISTINCT auth_user_id) AS accounts,
               MIN(auth_user_id::text)      AS only_account,
               COUNT(*)                     AS n
        FROM samples
        WHERE auth_user_id IS NOT NULL
        GROUP BY user_key
        ORDER BY n DESC
        """
    )


def backfill_sample_owner(user_id_value: str, auth_user_id: str) -> int:
    """Attach an owner to every still-unowned sample whose user_id matches.

    `auth_user_id IS NULL` in the WHERE clause makes this idempotent and makes
    it impossible to overwrite an owner that was recorded correctly — a rerun
    with a wrong mapping can only affect rows that had no owner to lose.
    Returns the number of rows updated.
    """
    with _cursor() as cur:
        cur.execute(
            """
            UPDATE samples
               SET auth_user_id = %s
             WHERE auth_user_id IS NULL
               AND TRIM(COALESCE(user_id, '')) = %s
            """,
            (auth_user_id, str(user_id_value or "").strip()),
        )
        return cur.rowcount or 0


def resolve_absolute_path(db_path_str: str) -> 'Path':
    """Resolve a file path from the database to an absolute path.

    Handles both absolute paths (legacy data) and relative paths (new data).
    Relative paths are resolved relative to DATASET_ROOT.
    """
    from pathlib import Path
    from app.config import settings
    path = Path(db_path_str)
    if path.is_absolute():
        return path
    return settings.dataset_root / path


def mark_samples_synced(sample_uids: list) -> None:
    """Mark a batch of samples as synced to Google Sheets."""
    if not sample_uids:
        return
    with _cursor() as cur:
        cur.execute(
            "UPDATE samples SET sheets_synced = TRUE WHERE sample_uid = ANY(%s)",
            (sample_uids,),
        )


def fetch_unsynced_samples(limit: int = 5000) -> list:
    """Fetch samples not yet synced to Google Sheets, ordered by creation time."""
    with _cursor() as cur:
        cur.execute(
            """
            SELECT sample_uid, class_uid, slug, label_original, language, dialect,
                   source_type, user_id, session_id, fps_original, fps_processed,
                   seq_len, augment_id, completeness, file_path, storage_url,
                   checksum, created_at
            FROM samples
            WHERE sheets_synced = FALSE AND gdrive_synced = TRUE
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (limit,),
        )
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def insert_audit_log(
    *,
    tenant_id: Optional[str],
    actor_user_id: Optional[str],
    actor_label: Optional[str],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
    ip_hash: Optional[str] = None,
) -> None:
    """Chèn một dòng vào `audit_log`.

    Lối vào DUY NHẤT của bảng này, và cố ý không public: gọi qua
    `app.audit.record()`, chỗ làm sạch `detail` khỏi bí mật. Gọi thẳng vào đây
    là đi vòng qua bộ lọc đó.

    `audit_id` là BIGSERIAL nên không truyền; `created_at` để DEFAULT NOW() vì
    thời điểm ghi phải do cơ sở dữ liệu quyết định, không do đồng hồ của tiến
    trình gọi — hai worker lệch giờ sẽ tạo ra một dòng thời gian nói dối.
    """
    _execute(
        "INSERT INTO audit_log (tenant_id, actor_user_id, actor_label, action, "
        "target_type, target_id, detail, ip_hash) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (tenant_id, actor_user_id, actor_label, action,
         target_type, target_id, Json(detail) if detail is not None else None,
         ip_hash),
    )


def replace_training_job_classes(
    *, job_id: str, tenant_id: str, pairs: List[tuple]
) -> None:
    """Ghi hợp đồng đầu ra của một job: [(class_idx, label), ...].

    Thay thế toàn bộ chứ không chèn thêm: một job train lại (Celery giao trùng,
    hoặc người dùng chạy lại) phải cho ra đúng một tập lớp, không phải hai tập
    chồng lên nhau. Xoá-rồi-chèn trong một giao dịch nên không có khoảnh khắc
    nào bảng ở trạng thái nửa vời.

    `class_uid` được tra ngược từ nhãn TẠI THỜI ĐIỂM NÀY và để NULL nếu không
    khớp. Cố ý dùng LEFT JOIN thay vì bắt buộc khớp: một nhãn không tra được
    vẫn phải lưu — `label` mới là hợp đồng, `class_uid` chỉ là đường dẫn tiện
    lợi về danh mục và nó được phép mất khi lớp bị xoá.
    """
    if not pairs:
        return
    with _cursor() as cur:
        cur.execute("DELETE FROM training_job_classes WHERE job_id = %s", (job_id,))
        cur.executemany(
            "INSERT INTO training_job_classes (job_id, class_idx, label, tenant_id, class_uid) "
            "VALUES (%s, %s, %s, %s, ("
            "    SELECT c.class_uid FROM classes c "
            "    WHERE c.tenant_id = %s AND c.deleted_at IS NULL "
            "      AND (c.label_original = %s OR c.slug = %s) LIMIT 1))",
            [(job_id, idx, label, tenant_id, tenant_id, label, label)
             for idx, label in pairs],
        )


def list_training_job_classes(job_id: str) -> List[Dict[str, Any]]:
    """Hợp đồng đầu ra của một job, theo đúng thứ tự chỉ số."""
    return _fetch_all(
        "SELECT class_idx, label, class_uid FROM training_job_classes "
        "WHERE job_id = %s ORDER BY class_idx",
        (job_id,),
    )


def list_audit_log(limit: int = 100, action_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
    """Đọc nhật ký kiểm toán, mới nhất trước.

    Chịu RLS như mọi bảng có tenant_id: quản trị viên tenant thấy phần của
    mình, dòng tầng nền tảng (tenant_id NULL) chỉ hiện trong system scope.
    """
    limit = max(1, min(int(limit), 1000))
    if action_prefix:
        return _fetch_all(
            "SELECT * FROM audit_log WHERE action LIKE %s "
            "ORDER BY created_at DESC, audit_id DESC LIMIT %s",
            (f"{action_prefix}%", limit),
        )
    return _fetch_all(
        "SELECT * FROM audit_log ORDER BY created_at DESC, audit_id DESC LIMIT %s",
        (limit,),
    )


def get_sync_status(table_name: str) -> dict | None:
    """Get Google Sheets sync pointer for a table."""
    try:
        with _cursor() as cur:
            cur.execute(
                "SELECT current_spreadsheet_id, current_sheet_index, current_data_rows, max_rows_per_sheet "
                "FROM google_sheets_sync_status WHERE table_name = %s",
                (table_name,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "current_spreadsheet_id": row[0],
                "current_sheet_index": row[1],
                "current_data_rows": row[2],
                "max_rows_per_sheet": row[3],
            }
    except Exception:
        return None


def upsert_sync_status(table_name: str, spreadsheet_id: str, sheet_index: int, data_rows: int) -> None:
    """Create or update Google Sheets sync pointer."""
    _execute(
        """
        INSERT INTO google_sheets_sync_status (table_name, current_spreadsheet_id, current_sheet_index, current_data_rows, updated_at)
        VALUES (%(table_name)s, %(spreadsheet_id)s, %(sheet_index)s, %(data_rows)s, NOW())
        ON CONFLICT (table_name) DO UPDATE SET
            current_spreadsheet_id = EXCLUDED.current_spreadsheet_id,
            current_sheet_index = EXCLUDED.current_sheet_index,
            current_data_rows = EXCLUDED.current_data_rows,
            updated_at = NOW()
        """,
        {
            "table_name": table_name,
            "spreadsheet_id": spreadsheet_id,
            "sheet_index": sheet_index,
            "data_rows": data_rows,
        },
    )


# ---------------------------------------------------------------------------
# SOT authorized-key registry (DB-backed, admin-managed via the SOT admin page)
# ---------------------------------------------------------------------------

def sot_list_authorized_keys(include_revoked: bool = False) -> List[Dict[str, Any]]:
    """Registered writer machines. Active-only by default (revoked ones hidden)."""
    where = "" if include_revoked else "WHERE revoked_at IS NULL"
    return _fetch_all(
        "SELECT public_key, name, fingerprint, note, added_by, added_at, revoked_at "
        f"FROM sot_authorized_keys {where} ORDER BY added_at DESC"
    )


def sot_get_authorized_key(fingerprint: str) -> Optional[Dict[str, Any]]:
    rows = _fetch_all(
        "SELECT public_key, name, fingerprint, note, added_by, added_at, revoked_at "
        "FROM sot_authorized_keys WHERE fingerprint = %s",
        (fingerprint,),
    )
    return rows[0] if rows else None


def sot_add_authorized_key(
    *, name: str, public_key: str, fingerprint: str,
    added_by: Optional[str] = None, note: Optional[str] = None,
) -> None:
    """Insert a writer key. Re-adding the SAME public key un-revokes + updates it.

    Raises psycopg2.IntegrityError on a duplicate NAME that maps to a different
    public key (the UNIQUE(name) constraint) — callers validate names up front to
    turn that into a friendly 409.
    """
    _execute(
        """
        INSERT INTO sot_authorized_keys (public_key, name, fingerprint, note, added_by, revoked_at)
        VALUES (%(public_key)s, %(name)s, %(fingerprint)s, %(note)s, %(added_by)s, NULL)
        ON CONFLICT (public_key) DO UPDATE SET
            name = EXCLUDED.name,
            fingerprint = EXCLUDED.fingerprint,
            note = EXCLUDED.note,
            added_by = EXCLUDED.added_by,
            added_at = NOW(),
            revoked_at = NULL
        """,
        {"public_key": public_key, "name": name, "fingerprint": fingerprint,
         "note": note, "added_by": added_by},
    )


def sot_revoke_authorized_key(fingerprint: str) -> bool:
    """Soft-revoke (keeps the row for audit). Returns False if not found / already revoked."""
    existing = sot_get_authorized_key(fingerprint)
    if not existing or existing.get("revoked_at") is not None:
        return False
    _execute(
        "UPDATE sot_authorized_keys SET revoked_at = NOW() "
        "WHERE fingerprint = %s AND revoked_at IS NULL",
        (fingerprint,),
    )
    return True
