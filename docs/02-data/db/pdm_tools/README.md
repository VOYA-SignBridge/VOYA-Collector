# Bộ sinh tài liệu PDM v8

Ba tài liệu PDM ở thư mục cha **không được sửa tay**. Chúng sinh từ catalog của
cơ sở dữ liệu sản xuất, và toàn bộ số liệu trong đó — 62 bảng, 660 cột, 131 khoá
ngoại, 68 CHECK, 108 khoá duy nhất, 6 trigger — là thứ hệ thống nói, không phải
thứ ai gõ.

## Cái gì sinh ra cái gì

```
6 câu truy vấn catalog          ->  evidence/pdm_v8_*.csv
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
| `trg.sql` | 6 trigger người dùng — nguồn bằng chứng THỨ SÁU, thêm 27/08/2026 |
| `groups.txt` | 62 bảng -> 8 nhóm A–H |
| `gen_tables.py` | dựng `PDM_V8_TABLES.md` |
| `gen_relationships.py` | dựng `PDM_V8_RELATIONSHIPS.md`; giữ **tên quan hệ do người chốt** |
| `gen_dictionary.py` | dựng `PDM_V8_DATA_DICTIONARY.md`; hợp catalog với lớp phủ mô tả |

## Chạy lại

Tên tệp CSV đích **không** trùng tên câu truy vấn, nên vòng lặp phải mang theo
bảng ánh xạ. Bản trước viết `> ../evidence/pdm_v8_$q.csv` và sinh ra
`pdm_v8_tbl.csv`, `pdm_v8_trg.csv`… — những tên mà không generator nào đọc. Khối
dưới đây đã được chạy thử và dựng lại đúng sáu tệp bằng chứng, byte y hệt:

```bash
cd <thư mục này>
for pair in tbl:tables cols:columns fk:foreign_keys chk:checks uq:uniques trg:triggers; do
  q="${pair%%:*}"; out="${pair##*:}"
  docker exec -i voya_postgres psql -U admin -d signdb -f - < "$q.sql" \
    | sed '/^Output format is csv\.$/d' | sed 's/\r$//' > "../evidence/pdm_v8_$out.csv"
done
python gen_tables.py && python gen_relationships.py && python gen_dictionary.py
```

Câu `sed` gỡ dòng `Output format is csv.` mà `\pset format csv` in ra trước dữ
liệu; để nguyên thì dòng đầu tệp không phải tiêu đề cột và `csv.DictReader` đọc
lệch toàn bộ.

Câu `sed 's/\r$//'` là bảo hiểm, không phải bản vá cho một lỗi đã quan sát: đo
trên máy Windows này, `psql` qua `docker exec` rồi chuyển hướng ra tệp cho LF thuần
(CR=0). Giữ nó để chuỗi lệnh cho cùng một chuỗi byte bất kể nền tảng hay phiên bản
`psql`, vì `.gitattributes` chỉ chuẩn hoá lúc `git add` — nếu tệp trong cây làm việc
khác nhau tuỳ máy thì phép so byte không còn phát hiện được gì.

**Không dùng `tr -d '\r'`.** Nó xoá MỌI byte CR ở bất kỳ đâu, kể cả một CR nằm
bên trong giá trị của một trường — tức lặng lẽ sửa nội dung catalog trong chính
đường ống lấy byte làm bằng chứng. `sed 's/\r$//'` chỉ chạm CR ở cuối dòng.

Góc hẹp còn lại, nói cho rõ: một CRLF nằm bên TRONG một trường có dấu nháy cũng
đứng cuối một dòng vật lý, nên `sed` vẫn chạm tới nó. Đo hiện tại: **0/8 tệp có
trường nào chứa CR**, nên góc ấy chưa xảy ra. Nếu về sau một biểu thức CHECK hay
một mô tả mang xuống dòng thật, phải thay bước này bằng một lượt đọc–ghi qua
`csv` thay vì lọc theo dòng.

Hai generator sau in **cổng máy** và thoát khác 0 khi lệch, nên `&&` ở trên dừng
đúng chỗ thay vì đi tiếp trên một bộ số sai.

## Vì sao có nguồn bằng chứng thứ sáu

Năm câu truy vấn đầu (bảng, cột, khoá ngoại, CHECK, khoá duy nhất) **không thu
trigger**, và lỗ ấy để `trg_legal_documents_freeze` đi qua bốn nhóm QA mà không
cổng nào thấy. Nó cưỡng chế tính bất biến của `legal_documents.content_hash` ở
tầng cơ sở dữ liệu — nhưng nó không nằm trong `pg_constraint`, nên mọi phép kiểm
CHECK đều báo "sạch" cho một bảng đang có ràng buộc mạnh nhất lược đồ.

Cùng lượt rà lôi ra bốn trigger nữa trên nhóm A, trong đó
`ct_role_permissions_dominance` là một rào chắn **leo thang quyền** ở tầng CSDL.

`gen_dictionary.py` vì thế hỏng (thoát 1) nếu sản xuất có một trigger mà không
mô tả nào dẫn tên nó. Bài học tổng quát: **ràng buộc của một lược đồ không chỉ
nằm trong `pg_constraint`.**

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
