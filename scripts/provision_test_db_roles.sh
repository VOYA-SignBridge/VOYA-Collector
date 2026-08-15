#!/usr/bin/env sh
# Lớp 3 của việc cô lập bộ test: ranh giới quyền ở tầng PostgreSQL.
#
# Lớp 1 (`run_tests.sh`) đổi tên cơ sở dữ liệu trong DSN. Lớp 2 (`conftest`)
# từ chối chạy nếu `current_database()` sai. Cả hai đều là mã Python/shell, và
# sự cố 13/08/2026 đã chứng minh mã đó viết sai được. Lớp 3 làm cho một lỗi
# nữa cũng không đi tới đâu: danh tính mà bộ test dùng KHÔNG kết nối được vào
# cơ sở dữ liệu sản xuất, dù DSN có trỏ vào đó.
#
# Vì sao phải REVOKE khỏi PUBLIC chứ không khỏi role
# --------------------------------------------------
# `pg_database.datacl` của `signdb` là NULL, tức ACL MẶC ĐỊNH, tức PUBLIC có
# CONNECT. Trong PostgreSQL không có cách nào trừ quyền của PUBLIC ở mức một
# role: viết `REVOKE CONNECT ON DATABASE signdb FROM voya_test_app` sẽ chạy
# thành công, không báo lỗi gì, và `has_database_privilege` vẫn trả về TRUE.
# Một lớp bảo vệ trông như đã dựng mà không chặn gì là tệ hơn không có.
#
# Nên đường duy nhất là mặc-định-từ-chối: bỏ CONNECT khỏi PUBLIC rồi cấp lại
# tường minh. Phạm vi ảnh hưởng liệt kê được hết — cụm này có ĐÚNG hai role
# đăng nhập được (`admin` sở hữu cả hai cơ sở dữ liệu nên không mất gì,
# `voya_app` được cấp tường minh) — và đo được bằng `has_database_privilege`,
# không suy luận từ câu lệnh đã gõ.
#
# Vì sao KHÔNG nằm trong conftest
# -------------------------------
# `CREATE ROLE` và `ALTER DATABASE` là thay đổi hạ tầng. Chuỗi sự cố vừa rồi
# xảy ra đúng vì một hook khởi động của pytest có quyền đổi thứ nằm ngoài cơ
# sở dữ liệu test. Cấp phát là một bước có người gõ, chạy một lần.
#
# Dùng:  bash scripts/provision_test_db_roles.sh
#
# Trên Windows/PowerShell phải gõ `bash`, không phải `sh`: Git Bash cài
# /usr/bin/bash nhưng KHÔNG tạo alias `sh` trên PATH của PowerShell, nên
# `sh scripts/...` báo CommandNotFoundException chứ không phải lỗi script.
set -eu

export MSYS_NO_PATHCONV=1

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$REPO/.env"
PROD_DB="${VOYA_PROD_DATABASE:-signdb}"
TEST_DB="${VOYA_TEST_DATABASE:-signdb_test}"
PG="${VOYA_PG_CONTAINER:-voya_postgres}"

[ -f "$ENV_FILE" ] || { echo "khong thay $ENV_FILE"; exit 2; }

read_env() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2-; }

OWNER_PW=$(read_env VOYA_TEST_OWNER_PASSWORD)
APP_PW=$(read_env VOYA_TEST_APP_PASSWORD)

if [ -z "$OWNER_PW" ] || [ -z "$APP_PW" ]; then
  echo "Thieu mat khau role test trong $ENV_FILE. Them hai dong nay roi chay lai:"
  echo
  echo "VOYA_TEST_OWNER_PASSWORD=$(openssl rand -hex 24 2>/dev/null || date +%s%N)"
  echo "VOYA_TEST_APP_PASSWORD=$(openssl rand -hex 24 2>/dev/null || date +%s%N)"
  exit 2
fi

psql_admin() { docker exec -i "$PG" psql -U admin -v ON_ERROR_STOP=1 -P pager=off "$@"; }

echo "==> 1/4  hai role test (NOSUPERUSER, NOBYPASSRLS)"
psql_admin -d postgres <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'voya_test_owner') THEN
        CREATE ROLE voya_test_owner;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'voya_test_app') THEN
        CREATE ROLE voya_test_app;
    END IF;
END \$\$;

-- Viết đầy đủ mọi thuộc tính, không dựa vào mặc định: một role đã tồn tại có
-- thể mang thuộc tính mà ai đó bật lên từ lần trước, và BYPASSRLS bật nhầm sẽ
-- làm toàn bộ suite RLS xanh giả.
--
-- CREATEDB: BẬT ở vai chủ sở hữu. CREATEROLE: TẮT. Hai quyền này khác hẳn nhau
-- về hậu quả, và gộp chúng làm một là lý do lần vá đầu đi sai.
-- ---------------------------------------------------------------------------
-- `test_tenant_isolation.py` dựng CSDL nháp `voya_rls_proof_*` cho mỗi module,
-- cài lược đồ thật và chính sách RLS thật lên đó rồi kiểm. Không chạy chung
-- CSDL được, vì phép kiểm đụng tới chính các câu DDL sửa chính sách.
--
-- Vì sao CREATEDB không mở đường nào sang sản xuất — ba lối, chặn cả ba:
--   * CONNECT vào `${PROD_DB}` đã bỏ khỏi PUBLIC ở bước 2, cấp lại tường minh
--     chỉ cho `admin` và `voya_app`. Đo ở bước 4, không suy luận.
--   * `CREATE DATABASE ... TEMPLATE ${PROD_DB}` không đi được: PostgreSQL chỉ
--     cho nhân bản khi template có `datistemplate = true` hoặc người gọi là
--     chủ sở hữu/superuser. `${PROD_DB}` không phải template và thuộc `admin`.
--   * CSDL mới sinh ra từ `template1`, rỗng. Tạo được CSDL MỚI không cho đọc
--     CSDL CŨ.
--
-- CREATEROLE thì NGƯỢC LẠI, và đây mới là quyền phải giữ tắt: nó cho đổi mật
-- khẩu của một vai không-superuser khác — kể cả `voya_app`, vai DUY NHẤT còn
-- CONNECT được vào sản xuất. Đó là một đường leo thang thật, chỉ hai bước.
--
-- Ghi lại lần vá hụt 14/08 để không ai đi lại: chỉ cấp CREATEDB thôi thì fixture
-- vẫn đổ, vì nó còn gọi `provision_db_roles.provision()`, mà câu
-- `ALTER ROLE ... NOSUPERUSER` trong đó đòi SUPERUSER. Nửa còn lại của lời giải
-- nằm ở `provision()`: vai là đối tượng toàn cụm nên khi chạy lần hai trên CSDL
-- nháp, hai câu ALTER ROLE ấy không còn việc gì để làm; nay chúng được phép
-- thất bại ĐÚNG KHI trạng thái mong muốn đã hợp lệ, đo bằng `pg_roles`.
ALTER ROLE voya_test_owner WITH LOGIN NOSUPERUSER NOBYPASSRLS CREATEDB
    NOCREATEROLE NOREPLICATION INHERIT PASSWORD '${OWNER_PW}';
ALTER ROLE voya_test_app   WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB
    NOCREATEROLE NOREPLICATION INHERIT PASSWORD '${APP_PW}';
SQL

echo "==> 2/4  mac dinh-tu-choi tren '${PROD_DB}' (mot giao dich, co khang dinh)"
psql_admin -d postgres <<SQL
BEGIN;

REVOKE CONNECT ON DATABASE ${PROD_DB} FROM PUBLIC;
GRANT  CONNECT ON DATABASE ${PROD_DB} TO admin;
GRANT  CONNECT ON DATABASE ${PROD_DB} TO voya_app;

DO \$\$
BEGIN
    IF NOT has_database_privilege('voya_app', '${PROD_DB}', 'CONNECT') THEN
        RAISE EXCEPTION 'voya_app MAT quyen CONNECT vao ${PROD_DB} — quay lui';
    END IF;
    IF NOT has_database_privilege('admin', '${PROD_DB}', 'CONNECT') THEN
        RAISE EXCEPTION 'admin MAT quyen CONNECT vao ${PROD_DB} — quay lui';
    END IF;
    IF has_database_privilege('voya_test_owner', '${PROD_DB}', 'CONNECT') THEN
        RAISE EXCEPTION 'voya_test_owner VAN CONNECT duoc vao ${PROD_DB}';
    END IF;
    IF has_database_privilege('voya_test_app', '${PROD_DB}', 'CONNECT') THEN
        RAISE EXCEPTION 'voya_test_app VAN CONNECT duoc vao ${PROD_DB}';
    END IF;
END \$\$;

COMMIT;
SQL

echo "==> 3/4  quyen tren '${TEST_DB}'"
psql_admin -d postgres <<SQL
GRANT CONNECT ON DATABASE ${TEST_DB} TO voya_test_owner, voya_test_app;
SQL

psql_admin -d "${TEST_DB}" <<SQL
-- Migration cần ALTER TABLE, và ALTER TABLE đòi QUYỀN SỞ HỮU chứ không phải
-- một GRANT. Nên role migration phải thực sự sở hữu các bảng.
--
-- KHÔNG dùng REASSIGN OWNED BY admin: admin là superuser khởi tạo của cụm và
-- sở hữu cả những đối tượng mà hệ thống cần, nên PostgreSQL từ chối nguyên
-- lượt ("cannot reassign ownership of objects owned by role admin because
-- they are required by the database system"). Chỉ chuyển đúng những gì nằm
-- trong schema public.
DO \$\$
DECLARE r record;
BEGIN
    FOR r IN SELECT c.oid::regclass AS obj, c.relkind
               FROM pg_class c
               JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE n.nspname = 'public'
                AND c.relowner = 'admin'::regrole
                AND c.relkind IN ('r', 'p', 'v', 'm', 'S')
                -- Sequence sinh ra từ SERIAL/IDENTITY thuộc về bảng của nó và
                -- đổi chủ theo bảng; đổi riêng thì PostgreSQL từ chối.
                AND NOT (c.relkind = 'S' AND EXISTS (
                        SELECT 1 FROM pg_depend d
                         WHERE d.objid = c.oid AND d.deptype = 'a'))
              ORDER BY CASE c.relkind WHEN 'r' THEN 0 WHEN 'p' THEN 0 ELSE 1 END
    LOOP
        CASE r.relkind
            WHEN 'r', 'p' THEN
                EXECUTE format('ALTER TABLE %s OWNER TO voya_test_owner', r.obj);
            WHEN 'v' THEN
                EXECUTE format('ALTER VIEW %s OWNER TO voya_test_owner', r.obj);
            WHEN 'm' THEN
                EXECUTE format('ALTER MATERIALIZED VIEW %s OWNER TO voya_test_owner', r.obj);
            WHEN 'S' THEN
                EXECUTE format('ALTER SEQUENCE %s OWNER TO voya_test_owner', r.obj);
        END CASE;
    END LOOP;

    FOR r IN SELECT p.oid::regprocedure AS obj
               FROM pg_proc p
               JOIN pg_namespace n ON n.oid = p.pronamespace
              WHERE n.nspname = 'public' AND p.proowner = 'admin'::regrole
    LOOP
        EXECUTE format('ALTER FUNCTION %s OWNER TO voya_test_owner', r.obj);
    END LOOP;
END \$\$;

ALTER DATABASE ${TEST_DB} OWNER TO voya_test_owner;
GRANT ALL ON SCHEMA public TO voya_test_owner;

-- Vai ứng dụng: đúng những gì voya_app có trên sản xuất — USAGE trên schema
-- và bốn quyền CRUD, không hơn. Không DDL.
GRANT USAGE ON SCHEMA public TO voya_test_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO voya_test_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO voya_test_app;

-- Danh mục THAM CHIẾU toàn cục: chỉ đọc, y như `voya_app` trên sản xuất.
-- `regions` và `languages` không mang tenant_id nên nằm ngoài RLS — đúng, vì
-- chúng không phải dữ liệu của ai. Nhưng cả hai được `classes` trỏ tới bằng
-- ON UPDATE CASCADE, nên ghi được chúng là ghi lại `classes` của MỌI tenant
-- mà không policy nào của `classes` được hỏi tới. Xem REFERENCE_TABLES trong
-- app/cli/provision_db_roles.py.
REVOKE INSERT, UPDATE, DELETE ON regions   FROM voya_test_app;
REVOKE INSERT, UPDATE, DELETE ON languages FROM voya_test_app;

-- Bảng do migration tạo ra SAU này cũng phải tới được tay vai ứng dụng, nếu
-- không thì lượt chạy đầu sau mỗi migration sẽ đỏ vì "permission denied" —
-- và người ta sẽ chữa bằng cách cho voya_test_app nhiều quyền hơn cần.
ALTER DEFAULT PRIVILEGES FOR ROLE voya_test_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO voya_test_app;
ALTER DEFAULT PRIVILEGES FOR ROLE voya_test_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO voya_test_app;
SQL

echo "==> 4/4  do lai bang has_database_privilege (khong suy luan tu lenh da go)"
psql_admin -d postgres -c "
SELECT r.rolname AS role,
       has_database_privilege(r.rolname, '${PROD_DB}',  'CONNECT') AS connect_prod,
       has_database_privilege(r.rolname, '${TEST_DB}', 'CONNECT') AS connect_test,
       r.rolsuper, r.rolbypassrls, r.rolcreaterole, r.rolcreatedb
  FROM pg_roles r
 WHERE r.rolname IN ('admin','voya_app','voya_test_owner','voya_test_app')
 ORDER BY r.rolname;"

echo
echo "Xong. Buoc kiem chung THAT SU (thu ket noi bang chinh credential do) nam o"
echo "backend/tests/test_db_role_isolation.py::TestTestRolesCannotReachProduction"
