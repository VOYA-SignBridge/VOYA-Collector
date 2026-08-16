from __future__ import annotations

import logging
import os
import re
import threading
from typing import Iterable, NamedTuple
from urllib.parse import urlsplit, urlunsplit

import psycopg2
from psycopg2 import pool as _pg_pool

from app.config import settings

logger = logging.getLogger(__name__)


def _format_host_part(parts, host: str) -> str:
    port = f":{parts.port}" if parts.port else ""
    if ":" in host and not host.startswith("["):
        return f"[{host}]{port}"
    return f"{host}{port}"


def _rewrite_host(database_url: str, host: str) -> str:
    parts = urlsplit(database_url)
    netloc = parts.netloc

    if "@" in netloc:
        auth_part, _ = netloc.rsplit("@", 1)
        host_part = _format_host_part(parts, host)
        return urlunsplit((parts.scheme, f"{auth_part}@{host_part}", parts.path, parts.query, parts.fragment))

    host_part = _format_host_part(parts, host)
    return urlunsplit((parts.scheme, host_part, parts.path, parts.query, parts.fragment))


def migration_dsn() -> str:
    """DSN for schema changes.

    Falls back to the application DSN when MIGRATION_DATABASE_URL is unset, so a
    deployment that has not split the roles yet behaves exactly as before. Once
    split, this is the only DSN in the process that may run DDL — see
    `settings.migration_database_url` for why the split matters.
    """
    return (settings.migration_database_url or "").strip() or settings.database_url


class ControlPlaneMisconfigured(RuntimeError):
    """DSN điều khiển không trỏ tới một vai điều khiển hợp lệ."""


def control_dsn() -> str:
    """DSN cho thao tác MẶT PHẲNG ĐIỀU KHIỂN.

    KHÔNG có đường lùi về `database_url`, và đây là khác biệt cố ý so với
    `migration_dsn()`. Vai migration lùi được vì một bản cài chưa tách vai vẫn
    phải chạy DDL; còn ở đây, lùi về vai ứng dụng nghĩa là **đúng thứ mà ranh
    giới này sinh ra để ngăn** lại xảy ra trong im lặng, và mọi phép kiểm quyền
    vẫn xanh vì chúng đo vai điều khiển ở nơi khác.

    Chưa cấu hình thì đường gọi phải NÓI RA, không tự xoay xở.
    """
    import os

    from app.storage.control_plane import CONTROL_DSN_ENV

    dsn = (os.getenv(CONTROL_DSN_ENV) or "").strip()
    if not dsn:
        raise ControlPlaneMisconfigured(
            f"{CONTROL_DSN_ENV} chua duoc dat. Thao tac mat phang dieu khien "
            f"KHONG duoc chay bang vai ung dung — chay "
            f"`python -m app.cli.provision_db_roles` roi dat bien nay."
        )
    return dsn


#: Bốn thuộc tính vai mà một danh tính điều khiển KHÔNG được có.
_CAM_O_VAI_DIEU_KHIEN = ("rolsuper", "rolbypassrls", "rolcreatedb", "rolcreaterole")


def _assert_control_identity(conn) -> None:
    """Kết nối này có thật sự là vai điều khiển không — hỏi cơ sở dữ liệu.

    Vì sao phải kiểm chứ không tin cấu hình
    ---------------------------------------
    Toàn bộ giá trị của lượt tách vai này nằm ở chỗ `CONTROL_DATABASE_URL` mang
    một danh tính HẸP HƠN `voya_app`. Nếu ai đó cấu hình nhầm nó thành `admin`
    — hoặc thành chính `voya_app` — thì:

      * đường ghi vẫn chạy,
      * mọi phép kiểm hành vi vẫn xanh,
      * và ranh giới tin cậy biến mất mà không ai được báo.

    Đó là kiểu hỏng tệ nhất: thiết kế least-privilege trở thành trang trí. Nên
    kiểm ở đây, ngay lúc mở kết nối, bằng `current_user` và `pg_roles` chứ
    không bằng cách đọc lại chuỗi DSN đã cấu hình.

    Kiểm mỗi lần mở kết nối chứ không một lần cho cả tiến trình: thao tác điều
    khiển hiếm (một lượt purge), nên cái giá là một lượt khứ hồi không đáng kể,
    đổi lại một thay đổi cấu hình giữa chừng cũng không lọt.
    """
    from app.storage.control_plane import CONTROL_ROLE, TEST_CONTROL_ROLE

    duoc_phep = {CONTROL_ROLE, TEST_CONTROL_ROLE}
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT current_user, current_database(), "
            f"{', '.join(_CAM_O_VAI_DIEU_KHIEN)} "
            f"FROM pg_roles WHERE rolname = current_user"
        )
        hang = cur.fetchone()

    if hang is None:
        raise ControlPlaneMisconfigured("khong doc duoc danh tinh cua ket noi dieu khien")

    vai, csdl, *co_cam = hang
    if vai not in duoc_phep:
        raise ControlPlaneMisconfigured(
            f"CONTROL_DATABASE_URL noi toi vai {vai!r}, phai la mot trong "
            f"{sorted(duoc_phep)}. Mot DSN tro vao admin hoac voya_app lam ranh "
            f"gioi tin cay bien mat trong im lang."
        )
    if any(co_cam):
        vi_pham = [ten for ten, bat in zip(_CAM_O_VAI_DIEU_KHIEN, co_cam) if bat]
        raise ControlPlaneMisconfigured(
            f"vai dieu khien {vai!r} dang mang thuoc tinh bi cam: {vi_pham}"
        )

    # Và ĐÚNG cơ sở dữ liệu.
    #
    # Vai đúng mà cơ sở dữ liệu sai thì sổ cái purge được ghi vào một nơi không
    # ai đọc: lượt xoá vẫn báo thành công, `tenant_purges` ở cơ sở dữ liệu thật
    # vẫn trống, và mọi phép kiểm quyền vẫn xanh vì chúng đo ở chỗ khác.
    #
    # KHÔNG so với hằng số `'signdb'`: bộ test chạy trên `signdb_test`, nên một
    # hằng số cứng sẽ biến phép kiểm này thành thứ phải tắt đi khi chạy test —
    # tức tắt đúng lúc cần nhất. Bất biến đúng là "cùng cơ sở dữ liệu với ứng
    # dụng": sổ cái phải nằm cạnh chính dữ liệu mà nó ghi lại việc xoá.
    mong_doi = _database_name(settings.database_url)
    if mong_doi and csdl != mong_doi:
        raise ControlPlaneMisconfigured(
            f"CONTROL_DATABASE_URL noi toi co so du lieu {csdl!r} nhung ung dung "
            f"dung {mong_doi!r}. So cai dieu khien phai nam cung noi voi du lieu "
            f"ma no ghi lai viec xoa."
        )


def _database_name(dsn: str) -> str:
    """Tên cơ sở dữ liệu trong một DSN, hoặc chuỗi rỗng nếu không đọc được."""
    return (urlsplit(dsn).path or "").lstrip("/").split("?")[0]


def connect_control(*, connect_timeout: int = 10):
    """Kết nối bằng vai ĐIỀU KHIỂN, đã xác minh danh tính.

    Không dùng nhóm kết nối, cùng lý do với `connect_migration`: một kết nối
    mang năng lực điều khiển không được nằm trong nhóm dùng chung để rồi một
    request thường mượn trúng nó.
    """
    conn = connect_postgres(
        connect_timeout=connect_timeout,
        application_name="voya_control",
        database_url=control_dsn(),
    )
    try:
        _assert_control_identity(conn)
    except Exception:
        conn.close()
        raise
    return conn


def _candidate_hosts(database_url: str | None = None) -> Iterable[str]:
    current_url = database_url or settings.database_url
    parsed = urlsplit(current_url)
    current_host = parsed.hostname or ""

    raw_candidates = [
        current_host,
        getattr(settings, "postgres_host", ""),
        "postgres",
        "voya_postgres",
        "localhost",
        "127.0.0.1",
    ]

    seen: set[str] = set()
    for host in raw_candidates:
        host = (host or "").strip()
        if not host or host in seen:
            continue
        seen.add(host)
        yield host


def connect_postgres(
    *,
    connect_timeout: int = 5,
    application_name: str | None = None,
    database_url: str | None = None,
):
    """Connect to Postgres with host fallbacks.

    This keeps containerized deployments resilient when the configured host name
    differs from the runtime DNS alias that is actually available.
    """
    base_url = database_url or settings.database_url
    errors: list[str] = []

    for host in _candidate_hosts(base_url):
        dsn = _rewrite_host(base_url, host)
        try:
            kwargs = {"connect_timeout": connect_timeout}
            if application_name:
                kwargs["application_name"] = application_name
            return psycopg2.connect(dsn, **kwargs)
        except Exception as exc:
            message = str(exc)
            errors.append(f"{host}: {message}")

            if not re.search(r"could not translate host name|Name or service not known", message, re.IGNORECASE):
                raise

            logger.warning("Postgres host lookup failed for %s, trying next candidate", host)

    raise psycopg2.OperationalError(
        "Unable to connect to Postgres using any configured host candidate: " + "; ".join(errors)
    )


def connect_migration(*, connect_timeout: int = 10):
    """Connect using the DDL role.

    Deliberately unpooled: schema changes run once at boot (`ensure_tables`) or
    from a CLI, so the handshake cost is irrelevant, and keeping DDL off the
    shared pool means a pooled connection can never be holding DDL rights when a
    request borrows it.
    """
    return connect_postgres(
        connect_timeout=connect_timeout,
        application_name="voya_migration",
        database_url=migration_dsn(),
    )


class RolePrivileges(NamedTuple):
    """What the connected role is allowed to ignore."""

    rolname: str
    is_superuser: bool
    bypasses_rls: bool

    @property
    def can_bypass_rls(self) -> bool:
        # Superuser implies BYPASSRLS in PostgreSQL even when rolbypassrls is
        # false, so the two must be OR-ed rather than checked independently.
        return self.is_superuser or self.bypasses_rls


def current_role_privileges(conn) -> RolePrivileges:
    """Read the RLS-relevant attributes of the role `conn` is authenticated as."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
        row = cur.fetchone()
    if not row:  # pragma: no cover - current_user always exists in pg_roles
        return RolePrivileges("unknown", False, False)
    return RolePrivileges(str(row[0]), bool(row[1]), bool(row[2]))


def rls_enabled_tables(conn, tables: Iterable[str]) -> list[str]:
    """Which of `tables` currently have row-level security switched on."""
    names = [t for t in tables]
    if not names:
        return []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' AND rowsecurity AND tablename = ANY(%s) "
            "ORDER BY tablename",
            (names,),
        )
        return [str(r[0]) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Connection pool (for the high-frequency metadata_db path)
#
# Why: metadata_db opened a brand-new psycopg2 connection for every query and
# closed it. Under the npz upload flow (hundreds of insert/update per video)
# that meant hundreds of TCP+auth handshakes. A ThreadedConnectionPool reuses
# connections instead.
#
# Fork-safety: Celery prefork forks worker children. psycopg2 connections are
# NOT fork-safe, so the pool is keyed by PID and rebuilt in each child on first
# use (the pool is created lazily during a task, i.e. after the fork).
# ---------------------------------------------------------------------------

_pool: _pg_pool.ThreadedConnectionPool | None = None
_pool_pid: int | None = None
_pool_lock = threading.Lock()


def _resolve_working_dsn(connect_timeout: int) -> str:
    """Find the first host candidate that actually accepts a connection.

    Resolved once when the pool is built so every pooled connection targets a
    host we know is reachable (keeps the existing Docker DNS-fallback behavior).
    """
    base_url = settings.database_url
    errors: list[str] = []
    for host in _candidate_hosts():
        dsn = _rewrite_host(base_url, host)
        try:
            probe = psycopg2.connect(dsn, connect_timeout=connect_timeout)
            probe.close()
            return dsn
        except Exception as exc:
            message = str(exc)
            errors.append(f"{host}: {message}")
            if not re.search(r"could not translate host name|Name or service not known", message, re.IGNORECASE):
                raise
    raise psycopg2.OperationalError(
        "Unable to resolve a working Postgres host for the pool: " + "; ".join(errors)
    )


def _build_pool() -> _pg_pool.ThreadedConnectionPool:
    minconn = max(1, int(getattr(settings, "db_pool_min", 1)))
    maxconn = max(minconn, int(getattr(settings, "db_pool_max", 8)))
    connect_timeout = int(getattr(settings, "db_connect_timeout", 5))
    dsn = _resolve_working_dsn(connect_timeout)
    logger.info("[DB_POOL] building pool min=%d max=%d pid=%d", minconn, maxconn, os.getpid())
    return _pg_pool.ThreadedConnectionPool(
        minconn,
        maxconn,
        dsn,
        connect_timeout=connect_timeout,
        application_name="voya_pool_metadata_db",
    )


def get_pool() -> _pg_pool.ThreadedConnectionPool:
    """Return the process-local pool, (re)building it after a fork."""
    global _pool, _pool_pid
    pid = os.getpid()
    if _pool is None or _pool_pid != pid:
        with _pool_lock:
            if _pool is None or _pool_pid != pid:
                # A pool inherited across fork must not be reused; drop the ref.
                _pool = _build_pool()
                _pool_pid = pid
    return _pool


def get_pooled_conn():
    """Borrow a connection from the process-local pool."""
    return get_pool().getconn()


def put_pooled_conn(conn, *, close: bool = False) -> None:
    """Return a connection to the pool (or discard it if broken)."""
    if conn is None:
        return
    try:
        pool = get_pool()
        # A closed/broken connection must not go back into the pool.
        broken = close or bool(getattr(conn, "closed", 0))
        pool.putconn(conn, close=broken)
    except Exception as exc:
        logger.warning("[DB_POOL] putconn failed (%s); closing connection", exc)
        try:
            conn.close()
        except Exception:
            pass