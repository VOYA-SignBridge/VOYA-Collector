"""Mặt phẳng ĐIỀU KHIỂN: ranh giới tin cậy thật ở PostgreSQL, không phải trên giấy.

Vì sao tệp này tồn tại
======================
`tenant_purges` là sổ cái ghi việc một tổ chức đã bị xoá vĩnh viễn. Tới
15/08/2026 vai ứng dụng có đủ bốn quyền trên nó:

    voya_app   SELECT INSERT UPDATE DELETE

Nghĩa là bất kỳ đường ghi nào chạy dưới vai ứng dụng — hoặc một lỗ SQL — vừa
**xoá được lịch sử purge**, vừa **ghi được "đã purge"** cho một tổ chức chưa hề
bị xoá. Đó là lỗ TOÀN VẸN sổ cái, nên RLS không phải công cụ đúng: bảng này
không có tenant để phạm vi hoá (dòng `tenants` bị xoá TRƯỚC khi sổ được ghi).

Cách sửa là một danh tính cơ sở dữ liệu thứ hai, `voya_control`, mang đúng
`INSERT` trên đúng bảng này — và vai ứng dụng mất sạch quyền.

Điều tệp này KHÔNG chứng minh
=============================
Đây là tách biệt ở tầng **DB principal**, chưa phải tầng **tiến trình**. Tiến
trình API vẫn giữ cả hai DSN, nên kẻ chiếm được toàn quyền thực thi mã vẫn đọc
được biến môi trường. Không phép kiểm nào ở đây khẳng định ngược lại.

Thứ được chứng minh, và nó vẫn đáng giá: một câu SQL chạy dưới vai ứng dụng
KHÔNG chạm được sổ cái, đường ghi hợp lệ chạy dưới đúng danh tính hẹp, và một
DSN cấu hình nhầm thành `admin` bị TỪ CHỐI thay vì âm thầm chạy được.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytestmark = pytest.mark.integration

BANG = "tenant_purges"


@pytest.fixture
def cur_owner():
    from app.storage.metadata_db import _migration_cursor

    with _migration_cursor() as c:
        yield c


@pytest.fixture
def cur_app():
    """Con trỏ dưới vai ỨNG DỤNG — đúng vai phục vụ request."""
    from app.storage.metadata_db import _cursor

    with _cursor() as c:
        yield c


def _sach(cur_owner, purge_id: str) -> None:
    cur_owner.execute("DELETE FROM tenant_purges WHERE purge_id = %s", (purge_id,))


# ---------------------------------------------------------------------------
# 1. Hợp đồng của vai
# ---------------------------------------------------------------------------


class TestHopDongVai:
    def test_ket_noi_dieu_khien_chay_dung_vai_dieu_khien(self):
        """Không đọc lại chuỗi DSN — hỏi cơ sở dữ liệu xem nó là AI."""
        from app.storage.control_plane import TEST_CONTROL_ROLE, control_cursor

        with control_cursor() as cur:
            cur.execute("SELECT current_user")
            assert cur.fetchone()[0] == TEST_CONTROL_ROLE

    def test_vai_dieu_khien_khong_mang_thuoc_tinh_bi_cam(self, cur_owner):
        """Nó KHÔNG phải một vai quản trị mới.

        Bốn thuộc tính này là bốn đường leo thang khác nhau. `rolcreaterole`
        đáng sợ nhất: nó cho đổi mật khẩu của một vai không-superuser khác — kể
        cả `voya_app`.
        """
        from app.storage.control_plane import TEST_CONTROL_ROLE

        cur_owner.execute(
            "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole "
            "FROM pg_roles WHERE rolname = %s", (TEST_CONTROL_ROLE,))
        hang = cur_owner.fetchone()
        assert hang is not None, f"{TEST_CONTROL_ROLE} chua duoc cap phat"
        assert not any(hang), f"thuoc tinh bi cam dang bat: {hang}"

    def test_vai_dieu_khien_khong_so_huu_bang_nao(self, cur_owner):
        """Sở hữu bảng là DDL trá hình: chủ sở hữu tắt được RLS của chính bảng."""
        from app.storage.control_plane import TEST_CONTROL_ROLE

        cur_owner.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n "
            "ON n.oid = c.relnamespace WHERE n.nspname = 'public' "
            "AND c.relkind IN ('r','p','v','m') AND c.relowner = %s::regrole",
            (TEST_CONTROL_ROLE,))
        assert cur_owner.fetchall() == []

    def test_vai_dieu_khien_KHONG_cham_duoc_bang_nao_ngoai_khai_bao(self, cur_owner):
        """"Làm được purge" chưa chứng minh "chỉ làm được purge".

        Không có ca này thì `GRANT ... ON ALL TABLES TO voya_control` — một dòng
        rất dễ viết cho tiện — sẽ làm mọi ca dương xanh, và vai điều khiển lặng
        lẽ trở thành một `voya_app` mạnh hơn. Đó chính là thứ thiết kế này sinh
        ra để ngăn.

        Quét TOÀN BỘ bảng trong `public` chứ không một danh sách mẫu: một bảng
        mới sinh ra sau này cũng phải nằm ngoài tầm với, và một danh sách mẫu
        viết tay sẽ không bao giờ nhắc tới nó.
        """
        from app.storage.control_plane import (
            APP_TABLE_PRIVILEGES, CONTROL_PLANE_TABLES, TEST_CONTROL_ROLE)

        cur_owner.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n "
            "ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind IN ('r','p')")
        moi_bang = [r[0] for r in cur_owner.fetchall()]
        assert len(moi_bang) > 30, "khong doc duoc danh sach bang — tien de sai"

        thua = {}
        for bang in moi_bang:
            co = set()
            for q in APP_TABLE_PRIVILEGES:
                cur_owner.execute("SELECT has_table_privilege(%s, %s, %s)",
                                  (TEST_CONTROL_ROLE, bang, q))
                if cur_owner.fetchone()[0]:
                    co.add(q)
            mong_doi = set(CONTROL_PLANE_TABLES.get(bang, frozenset()))
            if co != mong_doi:
                thua[bang] = {"co": sorted(co), "khai_bao": sorted(mong_doi)}

        assert not thua, (
            f"vai dieu khien co quyen tren bang NGOAI khai bao: {thua}. "
            f"No dang tro thanh mot voya_app manh hon, khong phai mot nang luc "
            f"chuyen dung.")

    def test_vai_dieu_khien_khong_doc_duoc_do_thi_authority_cua_Casbin(self, cur_owner):
        """Tách riêng vì nó là điều kiện tiên quyết của Casbin cutover.

        `AUTHZ_MODE=casbin` chỉ đổi ĐỘNG CƠ quyết định. Nếu một vai runtime bất
        kỳ còn sửa trực tiếp được các bảng tạo nên đồ thị authority mà Casbin
        đọc, thì ranh giới tin cậy không đổi — chỉ có nơi ra quyết định đổi.

        Ca này khoá vế đó lại cho vai điều khiển; vế của `voya_app` là việc của
        nhánh "6 nguồn effective-authz" còn đang mở.
        """
        from app.storage.control_plane import TEST_CONTROL_ROLE

        do_thi = ("roles", "permissions", "role_permissions", "memberships",
                  "tenant_members", "users")
        cham_duoc = {}
        for bang in do_thi:
            cur_owner.execute("SELECT to_regclass(%s)", (f"public.{bang}",))
            if cur_owner.fetchone()[0] is None:
                continue
            for q in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                cur_owner.execute("SELECT has_table_privilege(%s, %s, %s)",
                                  (TEST_CONTROL_ROLE, bang, q))
                if cur_owner.fetchone()[0]:
                    cham_duoc.setdefault(bang, []).append(q)

        assert not cham_duoc, (
            f"vai dieu khien cham duoc do thi authority: {cham_duoc}")

    def test_khong_vai_nao_la_thanh_vien_cua_vai_kia(self, cur_owner):
        """Tư cách thành viên là đường thừa hưởng quyền — và nó im lặng.

        `voya_test_app` là thành viên của `voya_test_control` thì mọi REVOKE ở
        trên vô nghĩa, mà `information_schema.role_table_grants` vẫn hiện đúng
        như ta mong đợi.
        """
        from app.storage.control_plane import TEST_CONTROL_ROLE

        for a, b in ((TEST_CONTROL_ROLE, "voya_test_app"),
                     ("voya_test_app", TEST_CONTROL_ROLE),
                     (TEST_CONTROL_ROLE, "voya_test_owner"),
                     (TEST_CONTROL_ROLE, "admin")):
            cur_owner.execute("SELECT pg_has_role(%s, %s, 'USAGE')", (a, b))
            assert cur_owner.fetchone()[0] is False, \
                f"{a} thua huong duoc quyen cua {b}"


# ---------------------------------------------------------------------------
# 2. Quyền trực tiếp — bốn cửa, đóng cả bốn
# ---------------------------------------------------------------------------


class TestVaiUngDungKhongChamDuoc:
    """Bốn ca riêng chứ không gộp một: mỗi quyền là một cửa khác nhau, và gộp
    lại thì một cửa mở vẫn cho cả ca đỏ mà không nói cửa nào."""

    def test_SELECT_bi_tu_choi(self, cur_app):
        with pytest.raises(Exception) as loi:
            cur_app.execute(f"SELECT count(*) FROM {BANG}")
        assert getattr(loi.value, "pgcode", None) == "42501"

    def test_INSERT_bi_tu_choi(self, cur_app):
        with pytest.raises(Exception) as loi:
            cur_app.execute(
                f"INSERT INTO {BANG}(purge_id, tenant_id) VALUES(%s, %s)",
                (str(uuid.uuid4()), "gia-mao"))
        assert getattr(loi.value, "pgcode", None) == "42501"

    def test_UPDATE_bi_tu_choi(self, cur_app):
        with pytest.raises(Exception) as loi:
            cur_app.execute(f"UPDATE {BANG} SET reason = 'sua trom'")
        assert getattr(loi.value, "pgcode", None) == "42501"

    def test_DELETE_bi_tu_choi(self, cur_app):
        """Cửa nguy hiểm nhất: xoá được sổ là xoá được bằng chứng."""
        with pytest.raises(Exception) as loi:
            cur_app.execute(f"DELETE FROM {BANG}")
        assert getattr(loi.value, "pgcode", None) == "42501"

    def test_vai_ung_dung_khong_SET_ROLE_sang_vai_dieu_khien(self, cur_app):
        """Đường vòng hiển nhiên nhất, và nó phải đóng."""
        from app.storage.control_plane import TEST_CONTROL_ROLE

        with pytest.raises(Exception) as loi:
            cur_app.execute(f'SET ROLE "{TEST_CONTROL_ROLE}"')
        assert getattr(loi.value, "pgcode", None) == "42501"


class TestVaiDieuKhienChiCoDungQuyenCanThiet:
    def test_INSERT_chay_duoc(self, cur_owner):
        from app.storage.control_plane import control_cursor

        pid = str(uuid.uuid4())
        try:
            with control_cursor() as cur:
                cur.execute(
                    f"INSERT INTO {BANG}(purge_id, tenant_id, reason) "
                    f"VALUES(%s, %s, %s)", (pid, "kiem-tra", "ca duong"))
            cur_owner.execute(
                f"SELECT tenant_id FROM {BANG} WHERE purge_id = %s", (pid,))
            assert cur_owner.fetchone()[0] == "kiem-tra"
        finally:
            _sach(cur_owner, pid)

    @pytest.mark.parametrize("cau", [
        f"SELECT count(*) FROM {BANG}",
        f"UPDATE {BANG} SET reason = 'x'",
        f"DELETE FROM {BANG}",
    ])
    def test_moi_quyen_KHONG_can_deu_bi_tu_choi(self, cau):
        """Chiều "thừa" của least privilege.

        Vai điều khiển chỉ cần ghi. Không đọc được sổ nghĩa là ngay cả đường
        điều khiển cũng không dùng nó để lọc dữ liệu tenant, và không xoá được
        nghĩa là sổ chỉ thêm chứ không bớt — kể cả từ phía điều khiển.
        """
        from app.storage.control_plane import control_cursor

        with pytest.raises(Exception) as loi:
            with control_cursor() as cur:
                cur.execute(cau)
        assert getattr(loi.value, "pgcode", None) == "42501", \
            f"cau nay KHONG bi tu choi vi thieu quyen: {cau}"


# ---------------------------------------------------------------------------
# 3. Cấu hình sai phải HỎNG, không được âm thầm chạy
# ---------------------------------------------------------------------------


class TestCauHinhSaiBiTuChoi:
    def test_M_C5_DSN_dieu_khien_tro_vao_vai_ung_dung_bi_TU_CHOI(self, monkeypatch):
        """ĐỘT BIẾN M-C5.

        Nếu ca này xanh khi DSN trỏ nhầm, thì toàn bộ thiết kế least-privilege
        chỉ là trang trí: đường ghi vẫn chạy, mọi phép kiểm hành vi vẫn xanh, và
        ranh giới tin cậy biến mất mà không ai được báo.
        """
        import os

        from app.storage.control_plane import CONTROL_DSN_ENV, control_cursor
        from app.storage.postgres_connection import ControlPlaneMisconfigured

        monkeypatch.setenv(CONTROL_DSN_ENV, os.environ["DATABASE_URL"])

        with pytest.raises(ControlPlaneMisconfigured) as loi:
            with control_cursor() as cur:
                cur.execute("SELECT 1")
        assert "voya_test_app" in str(loi.value) or "voya_app" in str(loi.value)

    def test_DSN_dieu_khien_tro_vao_vai_chu_so_huu_bi_TU_CHOI(self, monkeypatch):
        """Vai migration cũng không được nhận nhầm làm vai điều khiển.

        Nó sở hữu bảng, nên nó có MỌI quyền — chấp nhận nó ở đây là mở lại đúng
        cái cửa vừa đóng, chỉ bằng một biến môi trường khác.
        """
        import os

        from app.storage.control_plane import CONTROL_DSN_ENV, control_cursor
        from app.storage.postgres_connection import ControlPlaneMisconfigured

        monkeypatch.setenv(CONTROL_DSN_ENV, os.environ["MIGRATION_DATABASE_URL"])

        with pytest.raises(ControlPlaneMisconfigured):
            with control_cursor() as cur:
                cur.execute("SELECT 1")

    def test_thieu_DSN_thi_NOI_RA_chu_khong_lui_ve_vai_ung_dung(self, monkeypatch):
        """Khác `migration_dsn()` một cách CỐ Ý.

        Vai migration lùi được về DSN ứng dụng vì bản cài chưa tách vai vẫn phải
        chạy DDL. Ở đây lùi về nghĩa là đúng thứ ranh giới này sinh ra để ngăn
        lại xảy ra trong im lặng.
        """
        from app.storage.control_plane import CONTROL_DSN_ENV, control_cursor
        from app.storage.postgres_connection import ControlPlaneMisconfigured

        monkeypatch.delenv(CONTROL_DSN_ENV, raising=False)

        with pytest.raises(ControlPlaneMisconfigured) as loi:
            with control_cursor() as cur:
                cur.execute("SELECT 1")
        assert CONTROL_DSN_ENV in str(loi.value)


# ---------------------------------------------------------------------------
# 4. Đường ghi SẢN XUẤT — không phải một helper song song
# ---------------------------------------------------------------------------


class TestDuongGhiThat:
    """Bài học từ `clone_catalog_to_tenant`: kiểm khuôn thì khuôn đúng, mà chỗ
    gọi thật vẫn có thể không dùng khuôn ấy. Nên ở đây gọi đúng hàm sản xuất."""

    def test_record_purge_ghi_qua_vai_dieu_khien(self, cur_owner):
        from app import tenant_lifecycle

        pid = str(uuid.uuid4())
        try:
            tenant_lifecycle._record_purge(
                purge_id=pid, tenant="to-chuc-da-dong", display_name="Đã đóng",
                requested_by=None, counts={"samples": 3},
                files_removed=1, bytes_removed=2048, reason="ca duong",
            )
            cur_owner.execute(
                f"SELECT tenant_id, reason, files_removed FROM {BANG} "
                f"WHERE purge_id = %s", (pid,))
            hang = cur_owner.fetchone()
            assert hang == ("to-chuc-da-dong", "ca duong", 1)
        finally:
            _sach(cur_owner, pid)

    def test_M_C2_doi_duong_ghi_ve_vai_ung_dung_thi_DO(self, monkeypatch, cur_owner):
        """ĐỘT BIẾN M-C2 — đường sản xuất quay lại dùng con trỏ ứng dụng.

        Đây là đột biến quan trọng nhất của tệp: nó chứng minh đường ghi THẬT
        đang đi qua kết nối điều khiển, chứ không phải một helper được kiểm
        riêng còn chỗ gọi thì vẫn như cũ.
        """
        from app import tenant_lifecycle
        from app.storage import control_plane
        from app.storage.metadata_db import _cursor

        monkeypatch.setattr(control_plane, "control_cursor", _cursor)

        pid = str(uuid.uuid4())
        try:
            with pytest.raises(Exception) as loi:
                tenant_lifecycle._record_purge(
                    purge_id=pid, tenant="to-chuc-da-dong", display_name="x",
                    requested_by=None, counts={}, files_removed=0,
                    bytes_removed=0, reason="dot bien",
                )
            assert getattr(loi.value, "pgcode", None) == "42501"
        finally:
            _sach(cur_owner, pid)

    def test_M_C1_cap_lai_INSERT_cho_vai_ung_dung_thi_bat_bien_quyen_DO(
            self, cur_owner, cur_app):
        """ĐỘT BIẾN M-C1 — cấp lại `INSERT` trên sổ cái cho vai ứng dụng.

        Đột biến ở tầng CƠ SỞ DỮ LIỆU, không phải tầng mã: đây là loại trôi hay
        xảy ra nhất trong thực tế (ai đó chạy một câu GRANT để chữa một lỗi
        khác), và không có phép kiểm nào ở tầng Python bắt được nó.

        Hoàn nguyên trong `finally`, và phép kiểm cuối xác nhận đã hoàn nguyên —
        một đột biến rò rỉ sẽ làm cả bộ kiểm sau đó xanh giả.
        """
        from app.storage.control_plane import CONTROL_PLANE_TABLES

        try:
            cur_owner.execute(f"GRANT INSERT ON {BANG} TO voya_test_app")
            cur_owner.execute(
                "SELECT has_table_privilege(%s, %s, 'INSERT')",
                ("voya_test_app", BANG))
            assert cur_owner.fetchone()[0] is True, "dot bien KHONG duoc ap dung"

            # Chính là điều bất biến cấu trúc phải bắt.
            vi_pham = {}
            for bang in CONTROL_PLANE_TABLES:
                cur_owner.execute(
                    "SELECT has_table_privilege(%s, %s, 'INSERT')",
                    ("voya_test_app", bang))
                if cur_owner.fetchone()[0]:
                    vi_pham[bang] = "INSERT"
            assert vi_pham, "bat bien khong phat hien duoc quyen vua cap"
        finally:
            cur_owner.execute(f"REVOKE INSERT ON {BANG} FROM voya_test_app")

        cur_owner.execute(
            "SELECT has_table_privilege(%s, %s, 'INSERT')", ("voya_test_app", BANG))
        assert cur_owner.fetchone()[0] is False, "dot bien CHUA duoc hoan nguyen"

    def test_M_C4_cap_thua_quyen_cho_vai_dieu_khien_thi_DO(self, cur_owner):
        """ĐỘT BIẾN M-C4 — vai điều khiển được cấp thêm `DELETE`.

        Chiều "thừa" của least privilege. Không có ca này thì `GRANT ALL` cho
        vai điều khiển vẫn làm mọi ca dương xanh, và không ai thấy sổ cái đã
        xoá được trở lại.
        """
        from app.storage.control_plane import (
            CONTROL_PLANE_TABLES, TEST_CONTROL_ROLE)

        try:
            cur_owner.execute(f'GRANT DELETE ON {BANG} TO "{TEST_CONTROL_ROLE}"')

            lech = {}
            for bang, khai_bao in CONTROL_PLANE_TABLES.items():
                co = set()
                for q in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    cur_owner.execute(
                        "SELECT has_table_privilege(%s, %s, %s)",
                        (TEST_CONTROL_ROLE, bang, q))
                    if cur_owner.fetchone()[0]:
                        co.add(q)
                if co != set(khai_bao):
                    lech[bang] = sorted(co)
            assert lech, "bat bien khong phat hien duoc quyen THUA"
        finally:
            cur_owner.execute(f'REVOKE DELETE ON {BANG} FROM "{TEST_CONTROL_ROLE}"')

    def test_duong_ghi_khong_dung_system_scope(self):
        """Năng lực đến từ QUYỀN, không từ sentinel.

        `app.system_scope` là biến mà chính `voya_app` cũng tự đặt được. Nếu
        đường điều khiển quay lại dựa vào nó thì ta đã đổi một ranh giới thật
        lấy một ranh giới tự khai báo — và mất đúng thứ vừa xây.
        """
        import inspect

        from app import tenant_lifecycle

        than = inspect.getsource(tenant_lifecycle._record_purge)
        # Bỏ phần chú thích: chúng nhắc tới `system_scope` để GIẢI THÍCH vì sao
        # không dùng nó, và một phép kiểm bắt nhầm chú thích sẽ dạy người ta gỡ
        # chú thích thay vì giữ mã đúng.
        ma = "\n".join(d for d in than.splitlines()
                       if not d.lstrip().startswith("#"))
        ma = ma.split('"""')[0] + ma.split('"""')[-1] if ma.count('"""') >= 2 else ma

        assert "system_scope" not in ma, \
            "duong ghi so cai da quay lai dua vao sentinel thay vi quyen vai"


# ---------------------------------------------------------------------------
# 5. Endpoint thật, hai chiều
# ---------------------------------------------------------------------------


def _dem_so_cai(cur_owner, tenant: str) -> int:
    cur_owner.execute(f"SELECT count(*) FROM {BANG} WHERE tenant_id = %s", (tenant,))
    return cur_owner.fetchone()[0]


@pytest.fixture
def client_quan_tri():
    from app.auth import require_admin
    from app.main import app
    from fastapi.testclient import TestClient

    uid = str(uuid.uuid4())
    app.dependency_overrides[require_admin] = lambda: {
        "id": uid, "username": "quan-tri", "is_admin": True}
    yield TestClient(app), uid
    app.dependency_overrides.pop(require_admin, None)


class TestEndpointHaiChieu:
    def test_nguoi_KHONG_du_quyen_bi_tu_choi_va_KHONG_co_dong_so_cai_nao(
            self, client_quan_tri, cur_owner):
        """Phía ÂM, và nó phải khẳng định CẢ HAI vế.

        "Bị từ chối" một mình là chưa đủ: một bản vá hỏng có thể trả 403 SAU KHI
        đã ghi sổ. Nên đếm dòng sổ cái trước và sau.

        `AUTHZ_MODE` hiện là `shadow`, nên đường đang thật sự cưỡng chế là
        `require_sudo` — không giả định Casbin đã là bên cưỡng chế.
        """
        from app import sudo_mode

        client, uid = client_quan_tri
        sudo_mode.revoke(uid)          # quản trị viên, nhưng CHƯA nâng quyền
        muc_tieu = f"khong-ton-tai-{uuid.uuid4().hex[:8]}"
        truoc = _dem_so_cai(cur_owner, muc_tieu)

        r = client.post(f"/tenants/{muc_tieu}/purge",
                        json={"confirm_tenant_id": muc_tieu, "reason": "thu"})

        assert r.status_code == 403, f"{r.status_code}: {r.text[:200]}"
        assert _dem_so_cai(cur_owner, muc_tieu) == truoc == 0, \
            "bi tu choi nhung VAN ghi so cai"

    def test_M_C3_go_hang_rao_phan_quyen_thi_phia_AM_khong_con_403(
            self, client_quan_tri, cur_owner):
        """ĐỘT BIẾN M-C3 — gỡ `require_sudo` khỏi endpoint purge.

        Chứng minh cái 403 ở ca âm đến từ HÀNG RÀO, chứ không phải tình cờ đến
        từ một lỗi khác. Không có ca này thì ca âm vẫn xanh cả khi hàng rào đã
        biến mất — miễn là có thứ gì đó khác cũng trả 403.

        Và nó khẳng định thêm một điều: dù hàng rào bị gỡ, sổ cái VẪN không có
        dòng nào, vì đường ghi nằm sau các phép kiểm nghiệp vụ.
        """
        from app.main import app
        from app.sudo_mode import require_sudo

        client, uid = client_quan_tri
        muc_tieu = f"khong-ton-tai-{uuid.uuid4().hex[:8]}"
        app.dependency_overrides[require_sudo] = lambda: {
            "id": uid, "username": "quan-tri", "is_admin": True}
        try:
            r = client.post(f"/tenants/{muc_tieu}/purge",
                            json={"confirm_tenant_id": muc_tieu, "reason": "thu"})
            assert r.status_code != 403, (
                "go hang rao roi ma VAN 403 — cai 403 o ca am den tu cho khac, "
                "va ca am dang khong kiem thu no tuong")
            assert _dem_so_cai(cur_owner, muc_tieu) == 0
        finally:
            app.dependency_overrides.pop(require_sudo, None)

    def test_nguoi_du_quyen_purge_duoc_va_so_cai_co_dung_MOT_dong(
            self, client_quan_tri, cur_owner):
        """Phía DƯƠNG, đi qua đúng endpoint sản xuất.

        Đây là ca chứng minh ranh giới mới không làm hỏng nghiệp vụ: sau khi vai
        ứng dụng mất sạch quyền trên sổ cái, một lượt purge hợp lệ vẫn ghi được
        — qua vai điều khiển.
        """
        from app import plans, sudo_mode, tenant_admin, tenant_lifecycle
        from conftest import purge_tenant as _don

        client, uid = client_quan_tri
        sudo_mode.grant(uid)
        tid = f"cp{uuid.uuid4().hex[:10]}"
        tenant_admin.create_tenant(tid, display_name="Đóng Cửa",
                                   clone_catalog=False, plan_code="plus")
        plans._clear_caches()
        try:
            job = tenant_lifecycle.request_export(tid, export_purpose="tenant_portability")
            tenant_lifecycle.run_export(job["export_id"])
            # Phạm vi hệ thống là BẮT BUỘC ở đây: `tenants` bật FORCE RLS từ
            # 15/08/2026, nên `voya_test_owner` — dù là chủ sở hữu bảng — cũng
            # chịu chính sách. Không có nó thì câu này `UPDATE 0` mà KHÔNG ném
            # lỗi, và bài kiểm đỏ ở tận endpoint với thông điệp "chưa xoá mềm",
            # trỏ vào một nguyên nhân hoàn toàn khác.
            cur_owner.execute("SELECT set_config('app.system_scope', 'on', false)")
            try:
                cur_owner.execute(
                    "UPDATE tenants SET deleted_at = NOW() - INTERVAL '999 day', "
                    "is_active = FALSE WHERE tenant_id = %s", (tid,))
                assert cur_owner.rowcount == 1, "khong xoa mem duoc tenant thu"
            finally:
                cur_owner.execute("SELECT set_config('app.system_scope', '', false)")

            r = client.post(f"/tenants/{tid}/purge",
                            json={"confirm_tenant_id": tid, "reason": "ca duong e2e"})

            assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
            assert _dem_so_cai(cur_owner, tid) == 1
            cur_owner.execute(
                f"SELECT reason FROM {BANG} WHERE tenant_id = %s", (tid,))
            assert cur_owner.fetchone()[0] == "ca duong e2e"
        finally:
            sudo_mode.revoke(uid)
            cur_owner.execute(f"DELETE FROM {BANG} WHERE tenant_id = %s", (tid,))
            try:
                _don(tid)
            except Exception:  # noqa: BLE001 — tenant có thể đã bị purge thật
                pass
            plans._clear_caches()
