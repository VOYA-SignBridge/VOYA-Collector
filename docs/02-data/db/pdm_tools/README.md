# Bộ sinh tài liệu PDM v8

Ba tài liệu PDM ở thư mục cha **không được sửa tay**. Chúng sinh từ catalog của
cơ sở dữ liệu sản xuất, và toàn bộ số liệu trong đó — 62 bảng, 660 cột, 131 khoá
ngoại, 68 CHECK, 108 khoá duy nhất — là thứ hệ thống nói, không phải thứ ai gõ.

## Cái gì sinh ra cái gì

```
5 câu truy vấn catalog          ->  evidence/pdm_v8_*.csv
        + groups.txt                (phân 62 bảng vào 8 nhóm A–H)
        + evidence/pdm_v8_descriptions.csv   (mô tả do NGƯỜI viết)
                                ->  PDM_V8_TABLES.md
                                    PDM_V8_RELATIONSHIPS.md
                                    PDM_V8_DATA_DICTIONARY.md
```

| tệp | vai trò |
|---|---|
| `tbl.sql` | 62 bảng: khoá chính, số cột, số FK ra/vào, RLS, có `tenant_id` không |
| `cols.sql` | 660 cột: kiểu, NULL, mặc định, PK/FK, identity/generated |
| `fk.sql` | 131 khoá ngoại kèm **cardinality suy từ catalog** và `ON DELETE` |
| `chk.sql` | 68 CHECK, đánh dấu cái nào phủ nhiều cột |
| `uq.sql` | 108 khoá duy nhất, phân biệt constraint với **chỉ mục một phần** |
| `groups.txt` | 62 bảng -> 8 nhóm A–H |
| `gen_tables.py` | dựng `PDM_V8_TABLES.md` |
| `gen_relationships.py` | dựng `PDM_V8_RELATIONSHIPS.md`; giữ **tên quan hệ do người chốt** |
| `gen_dictionary.py` | dựng `PDM_V8_DATA_DICTIONARY.md`; hợp catalog với lớp phủ mô tả |

## Chạy lại

```bash
cd <thư mục này>
for q in tbl cols fk chk uq; do
  docker exec -i voya_postgres psql -U admin -d signdb -f - < $q.sql \
    > ../evidence/pdm_v8_$q.csv
done
python gen_tables.py && python gen_relationships.py && python gen_dictionary.py
```

Tên tệp CSV đích không trùng tên câu truy vấn (`tbl.sql` -> `pdm_v8_tables.csv`,
`fk.sql` -> `pdm_v8_foreign_keys.csv`); ba generator đọc tên đầy đủ.

## Ba ranh giới bộ này giữ, và vì sao

**Máy sinh cấu trúc. Người đặt tên.** `Entity`, cột khoá ngoại, cardinality,
`ON DELETE` là dữ liệu hệ thống. **Tên quan hệ thì không** — đặt tên là việc mô
hình hoá. Bản đầu của `gen_relationships.py` tự sinh động từ cho mọi khoá ngoại
và cho ra *"Signer contains Capture Session"*, *"Dialect contains Raw Upload"*:
sai nghĩa, mà lại đọc trôi chảy nên gần như không bị bắt trong một bảng 131
dòng. Từ đó công cụ chỉ tự đặt tên khi **tên cột tự chứa động từ** (loại A:
`created_by`, `reviewed_by`, `opened_by_user_id`); loại B và C phải do người
chốt, và `DA_CHOT`/`NHOM_*` trong `gen_relationships.py` là nơi giữ 131 tên ấy.

**Mô tả nghiệp vụ tách khỏi catalog.** Cơ sở dữ liệu có **0** `COMMENT ON
COLUMN`, nên catalog không có nguồn mô tả nào. Mô tả sống ở
`evidence/pdm_v8_descriptions.csv` — người viết, người duyệt — và mỗi dòng mang
`semantic_status`: `VERIFIED` (có bằng chứng từ mã hoặc từ dữ liệu đã đo),
`LEGACY`, `DERIVED`, `NEEDS_REVIEW` (suy ra, chưa xác nhận). Suy mô tả từ tên
cột là bịa: người đọc không phân biệt được dòng lấy từ hệ thống với dòng đoán ra.

**Cardinality suy từ catalog, không mặc định.** Phía cha là `1` khi mọi cột khoá
ngoại `NOT NULL`, `0..1` khi có cột nullable. Phía con **không** mặc định `0..N`:
nếu bảng con có một khoá duy nhất **vô điều kiện** mà tập cột nằm gọn trong tập
cột khoá ngoại thì mỗi cha có nhiều nhất một con — quan hệ 1–1. Điều kiện *vô
điều kiện* là mấu chốt: hệ này có **22 chỉ mục một phần**, và bỏ qua `indpred IS
NULL` sẽ biến hàng loạt quan hệ 1–N thành 1–1 trong im lặng. Năm quan hệ 1–1
thật: `tenant_storage`, `user_action_passcodes`, `user_totp`, và hai đường tới
`vocabulary_registry_meta`.
