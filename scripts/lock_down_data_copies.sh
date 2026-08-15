#!/usr/bin/env sh
# Mặc-định-từ-chối cho các cơ sở dữ liệu là BẢN SAO của dữ liệu sản xuất.
#
# Ngày 13/08/2026, sau khi dựng ba lớp cô lập quanh `signdb`, một phép đo cho
# thấy cụm còn bốn cơ sở dữ liệu khác mà mọi role đều nối được:
#
#     authz_v5       17 MB   57 bảng   3.860 mẫu   <- dữ liệu thật
#     signdb_goc     12 MB   29 bảng   3.860 mẫu   <- dữ liệu thật
#     signdb_v3test  14 MB   34 bảng   3.860 mẫu   <- dữ liệu thật
#     signdb_ci      12 MB   49 bảng       0 mẫu   <- chỉ lược đồ
#
# Ba cái đầu mang đúng số mẫu của sản xuất. Chúng không phải sản xuất, nên một
# lần ghi nhầm vào đó không gây sự cố — nhưng chúng là dữ liệu người dùng thật
# nằm ngoài mọi hàng rào vừa dựng, và "ngoài hàng rào" là chỗ dữ liệu bị quên.
#
# Đây CHỈ khoá đường vào, không xoá gì. Quyết định bỏ hay giữ cần biết mỗi bản
# sao ra đời để làm gì — `signdb_goc` ("gốc") nghe như một mốc ai đó cố ý giữ,
# và xoá một thứ như vậy vì nó trông thừa là cách mất nó.
#
# Đảo ngược:  GRANT CONNECT ON DATABASE <db> TO PUBLIC;
set -eu

export MSYS_NO_PATHCONV=1

PG="${VOYA_PG_CONTAINER:-voya_postgres}"
DATABASES="${VOYA_DATA_COPIES:-authz_v5 signdb_ci signdb_goc signdb_v3test}"

psql_admin() { docker exec -i "$PG" psql -U admin -v ON_ERROR_STOP=1 -P pager=off "$@"; }

for db in $DATABASES; do
  echo "==> $db"
  # Một giao dịch cho mỗi cơ sở dữ liệu, có khẳng định trước khi COMMIT: nếu
  # `admin` mất đường vào thì không ai gỡ lại được nữa.
  psql_admin -d postgres <<SQL
BEGIN;
REVOKE CONNECT ON DATABASE ${db} FROM PUBLIC;
GRANT  CONNECT ON DATABASE ${db} TO admin;
DO \$\$
BEGIN
    IF NOT has_database_privilege('admin', '${db}', 'CONNECT') THEN
        RAISE EXCEPTION 'admin MAT duong vao ${db} — quay lui';
    END IF;
    IF has_database_privilege('voya_test_app', '${db}', 'CONNECT') THEN
        RAISE EXCEPTION 'voya_test_app VAN noi duoc vao ${db}';
    END IF;
END \$\$;
COMMIT;
SQL
done

echo
echo "==> do lai"
psql_admin -d postgres -c "
SELECT d.datname,
       has_database_privilege('admin',           d.datname, 'CONNECT') AS admin,
       has_database_privilege('voya_app',        d.datname, 'CONNECT') AS voya_app,
       has_database_privilege('voya_test_app',   d.datname, 'CONNECT') AS test_app,
       has_database_privilege('voya_test_owner', d.datname, 'CONNECT') AS test_owner
  FROM pg_database d
 WHERE NOT d.datistemplate
 ORDER BY d.datname;"
