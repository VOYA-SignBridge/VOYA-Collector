# Known Issues & Pending Decisions

> Cập nhật 2026-07-21 (pre-freeze). Mục nào cần quyết định nghiệp vụ thì KHÔNG tự xử lý bằng code.

## Test đỏ đã biết — NGOÀI phạm vi release `isds2026-paper-pipeline-v1`

Hai test dưới đây fail và **được quyết định là ngoài phạm vi** release này. Cả hai
đều nằm ngoài đường đi của research pipeline (manifest → split → train → aggregate),
không ảnh hưởng tới bất kỳ artifact nào dùng cho bài báo.

| # | Test | Triệu chứng | Nguyên nhân gốc | Vì sao không chặn release |
|---|---|---|---|---|
| T1 | `backend/tests/test_schema_evolution.py::test_backward_compatibility_defaults` | `assert rows[0]["gdrive_synced"] is True` → nhận `False` | Schema tự mâu thuẫn: `metadata_db.py:120` (CREATE TABLE) khai `gdrive_synced BOOLEAN DEFAULT FALSE`, còn `metadata_db.py:214` (ALTER migration) khai `DEFAULT TRUE`. DB dựng mới đi theo nhánh CREATE nên nhận `FALSE`; DB migrate từ bản cũ nhận `TRUE`. | Cột này chỉ điều khiển mirror lên Google Drive (`sync_tasks`). Manifest builder quét filesystem (`dataset/features/**.npz`), **không** đọc cột này. Sửa default sẽ đổi hành vi sync (có thể gây re-upload hàng loạt hoặc bỏ sót upload) → cần owner quyết, không tự sửa trong vòng freeze. |
| T2 | `frontend/src/hooks/useTrainingAPI.test.ts` (2 test) | `expect(axiosClient.post).toHaveBeenCalledWith(...)` → `Number of calls: 0` | Test viết 2026-07-15 (`1be7f25`) khẳng định hook phải dùng `axiosClient`. Thiết kế sau đó **cố ý** đổi sang raw `fetch` + CSRF double-submit + `credentials:'include'` (commit `3f63161`). Test lỗi thời, đang khẳng định điều ngược với thiết kế hiện hành. | Thuần frontend, không đụng research pipeline. Sửa test = viết lại assertion cho luồng fetch — là product work, cố tình không làm trong vòng freeze. **Không** xoá/sửa test để làm xanh cổng. |

## Regression từ commit `cb46a07` (2026-07-21) — đã phát hiện, một phần đã khôi phục

`cb46a07 "Update training for long sequence"` đã đưa nhiều file về trạng thái cũ hơn.
Ba trường hợp đã xác nhận:

| File | Mất gì | Trạng thái |
|---|---|---|
| `processed/splits/make_splits.py` | 229 dòng: `split_from_manifest`, `run_manifest_mode`, `_assert_signer_disjoint`, 6 CLI flag manifest-mode | **Đã khôi phục** (working tree bị revert về blob của `a0bb4c1`, 2026-07-05) |
| `frontend/vite.config.ts` | Toàn bộ block `test:` (`environment: 'jsdom'`, `setupFiles`) → vitest chạy ở môi trường node, mọi test chết vì `window is not defined`; **cả suite frontend im lặng không chạy** | **Đã khôi phục** block `test:` |
| `frontend/vite.config.ts` | `base: ''` và manual chunk `vendor_react` / `vendor_router` | **CHƯA khôi phục** — đổi output build có rủi ro về đường dẫn deploy và cache; cần owner xác nhận |
| `frontend/src/hooks/useTrainingAPI.ts` | CSRF token header + `credentials:'include'` + surface backend error detail | Working tree đã bị revert về bản không CSRF; **đã restore về HEAD** |

**Bài học:** `git status` sạch không đủ — cần so blob với HEAD. Test đã bắt được
trường hợp 1 (`ImportError`) nhưng KHÔNG bắt được trường hợp 2, vì mất cấu hình test
làm cho suite biến mất thay vì fail. Đó là lý do có `backend/tests/test_research_suites.py`.

## Xung đột hợp đồng: ba tệp split legacy phục vụ HAI contract (2026-08-14)

`processed/splits/{train,val,test}.csv` đang đồng thời là:

| Vai | Nguồn khẳng định | Hệ quả |
|---|---|---|
| Mốc nghiên cứu **đóng băng** | `docs/02-data/VOCABULARY_SCHEMA_V2.md:107` — *"giữ nguyên, **không regenerate**; chỉ dùng để so sánh nghiên cứu"* | Chia lại là mất mốc so sánh |
| Đầu vào huấn luyện **vận hành** | `processed/train_utils/train_tcn.py:989` lấy đúng ba tệp này làm mặc định; `training_tasks.py::_build_cmd` ở nhánh legacy KHÔNG truyền `--train_csv` | Không chia lại thì lớp chưa đủ mẫu vẫn vào mọi lượt huấn luyện |

Hai vai này là hai contract khác nhau — *operational validity* so với
*experimental reproducibility* — nên chúng không được ở chung ba tệp. Hiện
không thể vừa giữ mốc vừa áp sàn 25 mẫu/lớp.

Đo ngày 14/08 (tổng train+val+test, sàn 25):

| dialect | lớp | đạt sàn | yếu |
|---|---|---|---|
| `bang-chu-cai` | 23 | 22 | 1 (5 mẫu) |
| `hoa-de` | 8 | 7 | 1 (14 mẫu) |
| `can-tho` | 8 | 1 | 7 (4 mẫu/lớp) |

**Đã tách không gian tên (15/08) — còn một nửa.** Hiện vật vận hành giờ nằm ở
`processed/splits/operational/<split_id>/`, bất biến và chỉ-tạo-mới; ba tệp
legacy đứng yên (đã đối chiếu sha256 và `git diff` trước/sau: không đổi). Hai
hiện vật thật đầu tiên đã dựng và đã chạy huấn luyện thật:

| split_id | lớp | target_idx | test acc |
|---|---|---|---|
| `hoa-de-20260815-floor25` | 7/8 | 0..6 | 0.970 |
| `bang-chu-cai-20260815-floor25` | 30/30 | 0..29 | 0.939 |
| `can-tho` | 1/9 → **DỪNG**, không sinh hiện vật | — | — |

**Nửa còn lại đã làm (15/08 muộn) — ĐÃ ĐÓNG.** `_build_cmd` giờ đi qua
`_resolve_for_run()`, một cửa duy nhất:

| `run_purpose` | nguồn dữ liệu | hành vi khi thiếu |
|---|---|---|
| `operational` | `operational/<split_id>/` đã xác minh | **DỪNG** (400 ở API, job `failed` ở worker) |
| `research` | `versions/<split_version>/` | 400, giữ nguyên như cũ |
| `smoke_test` (legacy) | ba tệp nghiên cứu đóng băng, **nói tường minh** | ghi ERROR, chạy tiếp bằng mặc định trainer |

Kèm theo, cùng thay đổi bịt luôn lỗ thứ hai: `_split_csvs_of(cmd)` trước đây
trả rỗng cho nhánh legacy, nên **cổng đồng thuận không soi lượt huấn luyện
legacy nào**. Giờ cả hai nhánh đều truyền đường dẫn tường minh, và cổng đồng
thuận đọc lại từ chính `cmd` — tức là từ argv của tiến trình con, dạng mạnh
nhất của bất biến *"hiện vật được preflight == hiện vật trainer thật sự đọc"*.

Bốn cổng kiểm dữ liệu (`_trainable_dialects_from_splits`,
`_split_classes_below_floor`, `_split_evidence_problems`, `_split_snapshot`)
giờ nhận `thu_muc` và soi đúng hiện vật đã ghim. Trước đó chúng luôn đọc ba
tệp gốc, nên một lượt ghim hiện vật `hoa-de` (7 lớp) vẫn được duyệt dựa trên
ảnh chụp cũ 8 lớp.

### `smoke_test` rơi về mặc định trainer — NGOẠI LỆ TẠM THỜI ĐÃ RÀ

Khi `resolve_research()` không xác minh được ba tệp đóng băng (thiếu sổ băm,
sai mã băm), nhánh `smoke_test` ghi ERROR rồi **chạy tiếp** bằng mặc định của
trainer. Đây là ngoại lệ có chủ ý, **không phải kiến trúc được chấp nhận** —
ghi ở đây theo đúng khuôn đã dùng cho hai đường cascade của `plans`.

Lý lẽ giữ: ba tệp đó vốn đã là mặc định của `train_tcn`, nên chặn lại sẽ giết
mọi lượt chạy cũ vì một sổ băm thiếu, mà không thay đổi tệp nào được đọc.

Lý lẽ bỏ, và nó mạnh hơn: vấn đề không phải cô lập tenant mà là **nguồn gốc**.
`smoke_test` nghe như một lượt chạy MỚI, không phải "dựng lại một checkpoint
lịch sử". Một hiện vật được tuyên bố là đầu vào nghiên cứu đóng băng mà không
xác minh được, vẫn sinh ra checkpoint mới, nghĩa là có checkpoint sinh từ đầu
vào chưa được chứng minh.

Hướng đúng là tách hai ngữ nghĩa đang bị gộp dưới một cái tên:

| tên | hành vi |
|---|---|
| `legacy_research_compat` | được phép hành vi lịch sử, có cảnh báo |
| `smoke_test` (mới) | fail-closed nếu hiện vật đóng băng không xác minh được |

**Đã rà nơi gọi (15/08):** ngoài mặc định của `TrainingConfig`, chỉ có **một**
nơi đặt giá trị này — `frontend/src/pages/training/components/TrainingSettings.tsx:113`
(`run_purpose: 'smoke_test'`). Nghĩa là mọi lượt huấn luyện đặt từ giao diện
hôm nay đều là `smoke_test`, và tất cả đều là lượt chạy MỚI — không nơi nào
đang dựa vào hành vi lịch sử.

**ĐIỀU KIỆN GỠ:** vì không có caller lịch sử, việc đúng là đổi thẳng sang
fail-closed và xoá mục này; không cần tách tên. Chi phí: nếu sổ băm hoặc ba
tệp đóng băng lệch, mọi lượt huấn luyện từ giao diện dừng cho tới khi sửa —
đó là chủ ý, nhưng là quyết định của chủ sở hữu chứ không phải của tôi.

Bằng chứng: `backend/tests/test_api_operational_contract.py` (16 ca), ca cuối
chạy `train_tcn` THẬT bằng **chính `cmd` mà API dựng ra**, rồi đối chiếu
`split_id` + hai mã băm trong checkpoint. Đột biến (cho nhánh vận hành rơi về
mặc định) làm 4 ca đỏ.

Lưu ý về bộ kiểm: `test_frozen_artifacts.py` mục **F2** giờ đối chiếu sha256
thật (trước đây chỉ khẳng định ba tệp còn tồn tại — tên mạnh hơn thứ nó chứng
minh). Sổ băm `processed/splits/FROZEN_RESEARCH_SPLITS.json` đã được
`git add -f` (15/08) — trước đó `.gitignore:93` bỏ cả `processed/splits/`, nên
ba tệp CSV được theo dõi mà **sổ băm thì không**: trên một bản clone sạch, F2
không có gì để đối chiếu. Thư mục `operational/` vẫn cố ý nằm ngoài Git.

**Số liệu trong bảng đo 14/08 phía trên là của ba tệp nghiên cứu đóng băng
(771 hàng), KHÔNG phải của dữ liệu hiện tại.** Đo lại trên `signdb` ngày 15/08
(3.860 mẫu): `bang-chu-cai` **30 lớp, cả 30 đạt sàn 25**; `hoa-de` 8→7;
`can-tho` 9→1. Khi trích số lớp, luôn nói rõ nguồn là đĩa hay cơ sở dữ liệu.

## Chờ quyết định nghiệp vụ (owner)

| # | Vấn đề | Hành động khi quyết |
|---|---|---|
| 1 | **7 file orphan/invalid** đang `pending` trong `config/orphan_file_decisions.json` (5 npz lớp `vo-tay` không có dòng nhãn; 1 bản copy `sample_d6ef358990(1).npz`; 1 file không có provenance signer) | Sửa `decision` → `quarantine`/`keep`, chạy `python scripts/quarantine_files.py --confirm` |
| 2 | **spa** (2 lớp) chưa gán scope/profile | Sửa `config/legacy_vocabulary_mapping.json` → chạy lại migration → manifest version mới |
| 3 | **can-tho** (40 mẫu, 8 lớp) đã revert về needs_review theo chỉ thị 2026-07-19; đồng thời KHÔNG có signer provenance | Xác nhận profile + xác nhận ai ký (hoặc thu mới) |
| 4 | Mảnh UUID lạc `d70872b4-...` từng dính vào `migrated_at` của lớp `vao-lop` (đã tách ra, lưu tại backup `labels_pre_row41_fix_*`) — có thể là tàn dư một dòng nhãn bị mất (nghi liên quan lớp `vo-tay` mồ côi) | Đối chiếu thủ công nếu muốn khôi phục nhãn vo-tay |
| 5 | **`normalize_single_hand` không chia z** (đã có bản vá `hands126_v2`, **chưa bật**) | Xem mục riêng bên dưới — quyết định còn lại là *khi nào lật*, không phải *sửa thế nào*. |

## Giới hạn dữ liệu hiện tại (chặn thí nghiệm)

- **Signer-disjoint**: alphabet bị chặn bởi `vn/alphabet/p` (1 signer); hoa_de chỉ có 2 signer thực sau merge (3 tập cần ≥3); central 0 mẫu. → Cần chiến dịch thu isds2026 với nhiều signer/label.
- **Raw landmarks**: 865/865 mẫu legacy không có raw (`raw_landmarks_available=0`) — ablation tiền xử lý chỉ khả thi trên dữ liệu thu MỚI (npz_v2 đã bật cho luồng camera).
- **Session metadata**: 38 lớp legacy không có session_id.

## Kiến trúc — biết trước, chưa xử lý (có chủ đích)

- `app/routers/experiments.py` (hệ model_versions) vẫn dormant; nếu kích hoạt phải thêm `from app import train_task` vào `worker.py` (nếu không task treo im lặng).
- Realtime service chỉ hỗ trợ TCN khi promote; Phase 4 (profile routing) chưa triển khai.
- `nginx :8000` chỉ route một phần API — dev FE dùng vite proxy (same-origin); **không** đặt `VITE_API_URL` tuyệt đối trong dev (xem `frontend/.env.example`).
- CORS `allow_credentials=False` là chủ đích (cookie auth chạy same-origin qua gateway/proxy).
- File `*_backup.py` / `verify_refactor.py` / `run_kfold_cv.py` trong `processed/train_utils` là scratch cũ — cân nhắc dọn trước khi nộp báo cáo.

## Đã sửa gần đây (tham chiếu)

- **Samples catalog bị tách 2 file** (2026-07-20): layout cũ `dataset/samples.csv`
  (879 dòng lịch sử, khớp bản trên Drive) vs layout tạm `dataset/samples/samples.csv`
  (chỉ dòng mới) — mirror Drive đè bản thiếu lên bản đủ. Đã merge (886 dòng,
  header union 21 cột), code trỏ về `dataset/samples.csv` duy nhất, file tạm
  đổi tên `.pre_merge_bak`, backup tại `dataset/backups/`. Hệ quả tốt: bí ẩn
  "samples.csv bị reset còn 3 dòng" trong audit trước thực ra là do tách file —
  nguồn dữ liệu lịch sử VẪN CÒN ĐỦ, legacy splits giờ có thể tái tạo được.

- Login bounce ở dev 5173 (stale Bearer đè cookie) — fix 2 tầng, commit `3f63161`.
- `migrated_at` hỏng của `vao-lop` làm STARTUP_SYNC fail mỗi lần khởi động — đã sửa, DB sync đủ 43 lớp.
- `normalize_dialect` bị định nghĩa trùng (bản đầu bị shadow) — đã xóa bản chết.

## Chuẩn hoá bàn tay: `hands126_v1` → `hands126_v2` (bản vá đã có, chưa bật)

### Lỗi

`normalize_single_hand` dời x,y về cổ tay rồi chia cho bề ngang bàn tay, nhưng
**z đi thẳng qua** — vẫn ở đơn vị MediaPipe thô. Ba trục vì thế không cùng đơn vị.
Đo trên **1997 mẫu thật** dựng lại từ kho raw:

| | span_xy / span_z (trung vị) |
|---|---|
| `hands126_v1` (hiện hành) | **21,76×** |
| `hands126_v2` (bản vá) | **5,25×** |

21,76× nghĩa là trục thứ ba đến tay mô hình nhỏ hơn hai trục kia hơn hai chục lần
— đọc như nhiễu, bất kể nó mã hoá cái gì. Phần 5,25× còn lại **không phải lỗi**:
đó là độ nông thật của z, khớp độc lập với phép đo z-span ≈ 0,203 bề ngang bàn
tay ở đợt sửa viewer.

### Bản vá

`hands126_v2` — giống hệt v1, chỉ khác z được dời về cổ tay và chia **cùng một
scale**. Span vẫn chỉ đo trên x/y ở cả hai bản: z là trục MediaPipe không cam kết
về độ lớn (hồi quy, không đo đạc), để nó tham gia quyết định scale là giao thang
đo của bàn tay cho con số kém tin cậy nhất trong khung hình.

**v1 vẫn là mặc định.** Đổi hành vi mặc định sẽ âm thầm định nghĩa lại đặc trưng
dưới chân mọi checkpoint đã huấn luyện — checkpoint vẫn nạp được, vẫn dự đoán
được, chỉ là trên đầu vào không còn mang nghĩa nó đã học. Không gì báo lỗi.

Hạ tầng để lật đã có sẵn từ trước: `normalization_version` được ghi theo **từng
mẫu** lẫn **từng checkpoint**, và `realtime_service/app/contracts.py` **đã** từ
chối phục vụ checkpoint có version lệch với registry.

### Vì sao chưa lật — đây mới là ràng buộc thật

Chỉ mẫu nào còn `landmarks_raw` mới dựng lại được: v1 vứt toạ độ gốc đi, mà không
có nó thì **không lấy lại được scale đã chia**.

```
tổng 3871 mẫu
  1997 (51,6%)  dựng được sang v2
  1874 (48,4%)  kẹt lại ở v1 — vĩnh viễn, trừ khi thu lại
```

Theo phương ngữ: `bang-chu-cai` 60,0% · `hoa-de` 50,5% · `common` 22,9% ·
`can-tho` 0% · `spa` 0%.

**Trộn v1 với v2 trong một mô hình là tái dựng lại đúng lỗi đã trả giá ở đợt
3431-vs-440 mẫu.** Nên lật hôm nay = huấn luyện lại toàn bộ **và** corpus tụt còn
1997 mẫu, với hai phương ngữ mất sạch.

Mọi mẫu thu MỚI đều có raw, nên tỉ lệ này chỉ tăng theo thời gian.

Chạy lại số liệu bất cứ lúc nào (chỉ đọc, không ghi gì):

```
python scripts/report_normalization_v2_readiness.py --json reports/normalization_v2_readiness.json
```

### Lỗi con đi kèm (cả v1 lẫn v2, chưa sửa)

`valid = norm(h[:, :2]) > 1e-6` **loại cổ tay ra khỏi phép tính span** — sau khi
dời, cổ tay đúng bằng 0 nên bị lọc. Nếu cổ tay là điểm cực biên theo x hoặc y thì
span bị tính thiếu và bàn tay bị phóng to hơn thực tế. Đây **cùng một họ** với lỗi
"mất cổ tay 100% khung" đã sửa ở viewer. Cố ý giữ nguyên trong v2 để v2 chỉ khác
v1 đúng **một** điều — sửa nốt là lần đổi đặc trưng thứ hai, gộp vào cùng đợt lật.

Kiểm thử: `backend/tests/test_normalization_parity.py` (26 test) ghim cả hai bản
mã, ghim hành vi z của v1, ghim hợp đồng của v2, và **từ chối version lạ** —
rơi ngầm về v1 khi gõ sai tên sẽ tạo ra đặc trưng v1 mang nhãn v2, đúng thứ mà cả
cơ chế version sinh ra để chặn.

### Thí nghiệm đối chứng (đang chạy) — quyết định 2026-08-06: đo trước khi lật

Chủ dự án chốt: **không lật theo lý lẽ, lật theo số đo.** Ba bước, tái lập được
hoàn toàn từ repo:

```bash
# 1. Dựng hai nhánh + manifest dùng chung (dry-run mặc định, --confirm mới ghi)
python scripts/build_zfix_ablation.py --confirm \
    --manifest  /dataset/manifests/dataset_manifest_ctu_20260806_v1.csv \
    --manifest-out /dataset/manifests/dataset_manifest_zfix.csv

# 2. MỘT split, dùng cho CẢ HAI nhánh
python processed/splits/make_splits.py \
    --dataset_manifest /dataset/manifests/dataset_manifest_zfix.csv \
    --unified --output_version zfix --seed 42

# 3. Lưới seed × nhánh
python scripts/run_zfix_ablation.py --seeds 42,43,44 --epochs 80
```

**Bảo chứng đúng đắn:** với mỗi mẫu, nhánh v1 được dựng lại **từ raw** rồi so với
`sequence` đã lưu trên đĩa; mẫu nào không tái tạo **chính xác** thì bị loại khỏi
cả hai nhánh. Trên toàn corpus: **1997/1997 khớp tuyệt đối, 0 lệch.** Nghĩa là
nhánh v1 đúng là baseline chứ không phải một thứ gần giống baseline.

**Vì sao hai nhánh đều dựng lại từ raw** thay vì lấy thẳng `dataset/features` làm
v1: so cây v2 với cây features hiện có sẽ trộn lẫn tác dụng của bản vá với việc
hai bên khác tập mẫu (v2 chỉ phủ được 51,6%) và khác cả cách đóng gói file. Hai
nhánh phải chỉ khác **đúng một biến**. Đã kiểm: x,y giống hệt ở 120/120 mẫu lấy
ngẫu nhiên, z khác ở 120/120.

**Vì sao một split duy nhất:** chạy splitter hai lần cho ra cùng phân hoạch chỉ
khi mọi thứ đầu vào giống nhau — tách ra là cách âm thầm nhất để cuối cùng đem so
hai mô hình huấn luyện trên hai tập train khác nhau.

Split `zfix`: 37 lớp, 1334/290/290, coverage 1.0 cả ba tập.

**Vì sao 3 seed chứ không phải 1:** trên 1334 mẫu huấn luyện, độ trải giữa các
seed rất dễ lớn hơn chính hiệu ứng đang đo. Runner in số từng seed cạnh trung
bình và **tự nói ra** khi chênh lệch nhỏ hơn độ trải — chênh lệch dưới ngưỡng đó
không phải kết quả, mà là chưa đo được.

### KẾT QUẢ thí nghiệm (2026-08-06) — KHÔNG lật sang v2

```
  seed    v1 acc    v2 acc     delta     v1 f1    v2 f1
    42    0.9448    0.9483   +0.0034    0.9348   0.9435
    43    0.9414    0.9172   -0.0241    0.9187   0.8917
    44    0.9483    0.9379   -0.0103    0.9359   0.9306
  ----------------------------------------------------
  mean    0.9448    0.9345   -0.0103

  độ trải seed-to-seed:  v1 0.0069    v2 0.0310
  dấu của delta nhất quán qua các seed:  KHÔNG
```

**Kết luận: chưa có bằng chứng nào cho thấy sửa z giúp ích. Trung bình còn âm.**
Không lật.

Hai điều đáng chú ý hơn cả con số trung bình:

1. **v2 nhiễu gấp ~4,5 lần v1** (0,0310 vs 0,0069). Đây mới là tín hiệu có nội
   dung, không phải chênh lệch trung bình.
2. **Delta đổi dấu giữa các seed.** Một seed nghiêng v2, hai seed nghiêng v1. Với
   3 seed thì đó là chưa đo được, không phải "v1 thắng".

**Vì sao kết quả này hợp lý — và vì sao nó không có nghĩa là z vô dụng:** z của
MediaPipe là **độ sâu hồi quy 2.5D, không phải đo đạc**. v1 vô tình bóp nó nhỏ đi
~21,8 lần, tức gần như tắt nó. v2 đưa nó lên ngang hàng x/y — và mô hình bắt đầu
chú ý tới một kênh vốn nhiễu. Sửa đúng đơn vị **không** làm số liệu đúng lên.

**Hệ quả cho hướng đi:** nếu muốn khai thác chiều sâu thì đường đi không phải v2,
mà là `landmarks_world` — toạ độ **mét thật**, đã đấu dây ở khâu thu và ở viewer
nhưng **chưa mẫu nào lưu**. Đó mới là thí nghiệm đáng làm tiếp, không phải chia z
cho span.

**Giữ nguyên v1 làm mặc định.** Corpus giữ đủ 3871 mẫu, `can-tho` và `spa` không
mất, không phải huấn luyện lại gì. `hands126_v2` ở lại trong mã như một version
đã cài + đã kiểm chứng, tốn 0 chi phí bảo trì, sẵn sàng nếu sau này có lý do khác
để dùng.

Chạy lại bảng bất cứ lúc nào, không cần huấn luyện lại:
`python scripts/run_zfix_ablation.py --summarize-only`

### Lỗi tìm được NHỜ thí nghiệm này (nghiêm trọng hơn chính lỗi z)

Lượt chạy đầu cho hai trong ba seed kết quả **giống nhau đến chữ số thứ 16**. Hai
đầu vào khác nhau không cho ra thế.

`NPZSignDataset._resolve_feature_path` đọc cột `file_path` của split CSV **trước**
`--features_root`, mà cột đó luôn phân giải được với split vừa dựng — nên
`--features_root` **bị nuốt hoàn toàn**: cả hai nhánh đọc `dataset/features/` gốc.

Lỗi này không crash, không cảnh báo, không cho ra số lạ. Cờ được nhận, được ghi
vào run config, rồi bị bỏ qua. **Mọi** thí nghiệm đổi cây đặc trưng — ablation
tiền xử lý, corpus dựng lại, backup phục hồi — đều âm thầm huấn luyện hai nhánh
trên cùng dữ liệu rồi kết luận "thay đổi không có tác dụng". Nếu cả ba seed lệch
nhẹ thay vì trùng khớp hoàn hảo thì không ai phát hiện ra.

Đã sửa: root truyền tường minh thắng `file_path`; không truyền thì hành vi y như
cũ. Test hồi quy: `backend/tests/test_features_root_override.py` (5 test), trong
đó có một test khẳng định thẳng thứ ablation phụ thuộc vào — hai root phải cho ra
**byte khác nhau**.

---

## Việc còn treo sau đợt 2026-08-09 (sao lưu / kiểm toán / tenant)

| # | Việc | Trạng thái | Cần ai quyết |
|---|---|---|---|
| B1 | **Service `pg-backup` chưa được tạo.** Mã, cấu hình compose và sổ tay đã xong; đã chạy thử bằng container một-lần và diễn tập khôi phục ĐẠT. Nhưng `docker compose ps -a` vẫn không có container này, tức **chưa có lịch sao lưu tự động**. | Chờ chạy `docker compose up -d --no-deps pg-backup` | Không cần quyết định nghiệp vụ — chỉ cần một lệnh |
| B2 | Mã backend/frontend của đợt này **chưa được triển khai**. Mã nằm trong image (`COPY app/`), nên `/admin/audit-log` và trang `/admin/tenants` chưa tồn tại trên bản đang chạy cho tới khi build lại image và `up -d --force-recreate`. | Chờ build lại | — |
| B3 | `./backups` nằm **cùng ổ đĩa** với `./dataset`. Một sự cố ổ đĩa mất cả dữ liệu lẫn bản sao lưu. | Chưa có bản sao ngoài máy | Cần quyết nơi lưu (ổ ngoài? máy khác? dịch vụ đám mây?) — có ràng buộc về dữ liệu cá nhân |
| B4 | Bản dump **không mã hoá**, chứa dữ liệu cá nhân ở dạng rõ. | Chưa làm | Cần quyết cách quản lý khoá trước khi viết mã |
| B5 | Không có cảnh báo khi `audit_log` ngừng tăng, và `[AUDIT-FAIL]` chỉ nằm trong log ứng dụng. `audit.count_since()` đã có sẵn cho việc này. | Chưa nối Prometheus | — |
| B6 | Nợ cũ chưa đụng tới: `metadata_db.py` 3.694 dòng; 102 `refresh_tokens` hết hạn không ai dọn; thiếu chỉ mục hàm `lower(email)`; 681 dòng router chết (`experiments.py`, `dataset_exporter.py`). | Chưa làm | — |

Sổ tay đầy đủ cho B1–B4: [BACKUP_RESTORE.md](../06-operations/BACKUP_RESTORE.md).
Chi tiết B5: [OBSERVABILITY_PLAN.md](../06-operations/OBSERVABILITY_PLAN.md) §10.4.

---

## Việc còn treo sau đợt 2026-08-09 (giao diện OTP / lời mời / tiếng Việt)

| # | Việc | Trạng thái | Cần ai quyết |
|---|---|---|---|
| C1 | **`/verify/confirm` không nhận tham số `purpose`.** Nó thử `verify_phone` trước rồi `verify_email`, nên hai thử thách cùng sống sẽ ăn mòn lượt thử của nhau (chi tiết: `TENANT_LIFECYCLE_AND_OTP.md` §6.1). Hiện `VerifyContactPage` chặn bằng cách giữ đúng một luồng mở. **Client thứ hai — ứng dụng di động, hay một tích hợp — sẽ dính lại.** | Đã chặn ở giao diện, chưa chặn ở API | Chỉ cần quyết khi có client thứ hai |
| C2 | Liên kết mời hiện được **dựng ở giao diện** (`AdminTenantsPage.invitationLink`) chứ không do máy chủ trả về. Nếu đổi đường dẫn `/invitation` mà quên chỗ này, mọi thư mời phát ra sau đó đều chết. | Chấp nhận được lúc này | — |
| C3 | Thư mời **chưa được gửi tự động**. `create_invitation` trả mã, quản trị viên tự chép liên kết và gửi bằng tay. `email_service` đã có sẵn đường gửi. | Chưa làm | Cần quyết nội dung thư |
| C4 | **146 ký hiệu tượng hình** vẫn dùng làm biểu tượng giao diện (nhiều nhất `FullscreenCaptureModal` 30, `UploadVideoForm` 17). Ba thành phần dùng chung đã sạch. | Chưa làm | — |
| C5 | Mã của đợt này **chưa triển khai** — cùng lý do B2: mã backend nằm trong image, và `frontend/dist` phải build lại. Ba tuyến mới (`/verify`, `/recover`, `/invitation`) và `GET /auth/verification-status` chưa tồn tại trên bản đang chạy. | Chờ build lại | — |

### Cập nhật 2026-08-09 (sau lượt build lại image)

| # | Trạng thái mới |
|---|---|
| B1 | **XONG.** `voya_pg_backup` đã chạy (`Up`, healthy). Lượt sao lưu đầu tiên tự chạy lúc khởi động, tự kiểm đạt, và diễn tập khôi phục trên chính bản đó ĐẠT (44 bảng, 0 bảng lệch, 4/4 bản văn khớp băm). Chu kỳ 24 giờ, giữ 14 ngày. |
| B2 / C5 | **XONG.** Đã build lại `voya_backend` + `voya_frontend` và dựng lại toàn bộ 14 container — 14/14 healthy. `verify_deployment`: 22 PASS / 1 WARN / 0 FAIL. |
| C1 | Vẫn treo — `/verify/confirm` chưa nhận `purpose`. Chỉ thành vấn đề khi có client thứ hai. |
| C2 | Vẫn treo — liên kết mời dựng ở giao diện. |
| C3 | Vẫn treo — thư mời chưa gửi tự động. |
| C4 | Vẫn treo — 146 ký hiệu tượng hình. |

**Việc mới làm xong trong lượt này:**

* **Dùng thử ẩn danh có mặt giao diện.** Đây là một tính năng **chết hoàn toàn**
  trước hôm nay: cổng gác cho `/realtime/*` chạy bằng phiếu dùng thử, nhưng
  không chỗ nào trong giao diện gọi `POST /trial/start`, nên khách vãng lai mở
  `/realtime` là nhận 401 ở mọi lời gọi. Đã kiểm trên bản đang chạy: trước khi
  xin phiếu `GET /realtime/models` trả **401**, sau khi xin trả **200** kèm
  `x-trial-minutes-remaining: 60`.
* **Trang `/admin/billing`** — mặt giao diện cho bốn endpoint nền tảng của
  `routers/billing.py`. Trước đó, đổi gói một tổ chức hay treo tổ chức quá hạn
  chỉ làm được bằng `curl`, còn sửa hạn mức của một gói chỉ làm được bằng cách
  gõ SQL vào cơ sở dữ liệu sản xuất.
* **`PUT /tenants/home-assignment/{user_id}`** đã có nút ở trang Tổ chức.
* **`hooks/useSudo.ts`** — gộp hai bản `ensureSudo` viết tay thành một.
* `tenant_usage_daily` đã gộp lại 120 ngày (`app.cli.backfill_usage`).

**Còn nợ, đã đo:** `GET /health/config|deps|status` và một vài endpoint hạ tầng
không có mặt giao diện, và đó là **đúng** — chúng dành cho Prometheus và cho
người vận hành gọi bằng `curl`, không phải cho trình duyệt.

---

## Đợt trả nợ 2026-08-09 (lượt hai) — B3/B4/B5 và C1–C4 đã đóng

| # | Trạng thái mới |
|---|---|
| **C1** | **XONG.** `POST /auth/verify/confirm` nhận `purpose` không bắt buộc. Có thì chỉ thử đúng thử thách đó; không có thì giữ nguyên lối dò cũ, nên client cũ không gãy. `VerifyContactPage` gửi kèm ở cả hai luồng. 5 test ghim, trong đó một test **cố ý chốt cái giá của lối cũ** — bỏ `purpose` vẫn ăn mòn lượt thử của cả hai — để nó là chi phí đã biết chứ không phải thứ âm thầm đổi. |
| **C2** | **XONG.** `accept_url` do máy chủ dựng, qua `public_url.frontend_url()`, và trả về trong phản hồi tạo lời mời. Giao diện không còn ghép chuỗi. Ghim cả ba tính chất: là URL đầy đủ, mã nằm **sau dấu thăng** (không có `?`), và một `Host` giả mạo **không** chọn được tên miền. |
| **C3** | **XONG.** Thư mời gửi tự động qua `send_invitation_email`. `loggable=False` — khác với liên kết đặt lại mật khẩu ngay cạnh, vì quản trị viên **đang cầm liên kết trong tay** nên ghi nó vào Loki không mua được gì. Gửi hỏng **không** huỷ lời mời; phản hồi mang `email_sent` và trang nói ra sự khác biệt. |
| **C4** | **XONG.** 0 ký hiệu tượng hình còn lại trong giao diện được vẽ ra (từ 194 chỗ / 30 tệp). 16 chỗ còn lại nằm trong **chú thích và docstring** — hai trong số đó đang giải thích chính những emoji đã bị thay, xoá đi là xoá mất lời giải thích. Thêm 33 biểu tượng SVG vào `components/ui/Icons.tsx`. |
| **B3** | **CƠ CHẾ XONG, CHÍNH SÁCH CHỜ NGƯỜI VẬN HÀNH.** `BACKUP_MIRROR_HOST_DIR` + `BACKUP_MIRROR_DIR` chép lượt sao lưu sang nơi thứ hai. Để trống = bỏ qua, kèm cảnh báo **mỗi lần khởi động**. Chọn ổ ngoài / máy khác / đám mây vẫn là quyết định có ràng buộc dữ liệu cá nhân — script không chọn hộ. |
| **B4** | **CƠ CHẾ XONG, CHỜ NGƯỜI VẬN HÀNH ĐẶT KHOÁ.** `BACKUP_PASSPHRASE` bật AES-256 (gpg đối xứng, có kiểm toàn vẹn MDC). Tối thiểu 16 ký tự, ngắn hơn thì service **từ chối khởi động**. Đã kiểm vòng tròn đầy đủ trên bản sao: mã hoá → giải mã thử → diễn tập khôi phục **ĐẠT** (44 bảng, 0 lệch, 4/4 băm). Sai mật khẩu và thiếu mật khẩu đều thoát 1 kèm câu giải thích. |
| **B5** | **XONG.** Ba chỉ số (`voya_audit_write_failures_total`, `voya_audit_log_age_seconds`, `voya_audit_log_entries_1h`) và ba cảnh báo Grafana. |

### Những thứ tìm được TRONG lúc trả nợ — đáng chú ý hơn chính các mục nợ

**1. Ô chọn vai trong trang Tổ chức mời được ba vai, hai trong ba gửi đi là 422.**
Giao diện khai `MemberRole = "owner" | "admin" | "member"`; máy chủ và ràng buộc
`CHECK` trên hai bảng đều là `admin | editor | viewer`. Chỉ "Quản trị viên"
trùng tên. Một lời mời vai `viewer` do máy chủ trả về thì tra bảng nhãn ra
`undefined` và hiện ra ô trống. Đây là thứ một lượt chạy thử sẽ đâm vào ở phút
thứ nhất.

Gốc rễ không nằm ở mã sản phẩm mà ở **bản giả lập trong test**: nó liệt kê đầy
đủ mọi export, trong đó có một `ROLE_LABEL` giả mang đúng ba vai sai. Test xanh,
sản phẩm hỏng. Đã đổi sang `importOriginal` để hằng số dùng bản thật.

**2. `npx tsc --noEmit` ở thư mục `frontend` kiểm ĐÚNG KHÔNG TỆP NÀO.**
`tsconfig.json` gốc là `{"files": [], "references": [...]}`, và không có `-b`
thì tsc đọc đúng tệp đó rồi thoát 0. Nhìn y hệt một lượt kiểm sạch.

Đây là lời giải cho một chuyện đã ghi trong sổ tay từ trước mà chưa ai tìm ra
nguyên nhân: *"`npm run build` từng hỏng mà `tsc --noEmit` không bắt"*. Lượt
sweep này giấu **14 lỗi kiểu** sau nó. Đã thêm `npm run typecheck`
(= `tsc -b --noEmit`) và ghi lý do ngay trong `package.json`.

**3. Năm ràng buộc `Field(pattern=...)` trong backend chưa từng được cưỡng chế.**
Dự án chạy pydantic 1.10, nơi từ khoá là `regex`; `pattern` lạ được nhận vào
lặng lẽ, xếp vào phần phụ của schema, và không kiểm gì cả. Năm chỗ: `channel`
(hai chỗ), `mode` của SOT, `scope` của bản xuất, và tham số `purpose` mới thêm.

Không chỗ nào thành lỗ hổng thật — cả bốn chỗ cũ đều được kiểm lại ở tầng dưới
và trả 422 — nhưng **schema đang hứa một điều nó không làm**, và tài liệu
OpenAPI sinh ra từ đó cũng nói dối theo. Đã đổi sang `Literal`, thứ mà cả hai
phiên bản pydantic đều cưỡng chế.

**4. `audit.count_since()` được nhắc tới ở hai nơi nhưng KHÔNG TỒN TẠI.**
Docstring của `app/audit.py` và mục B5 ở trên đều viết như thể nó đã có sẵn. Nó
chưa từng được viết. Giờ đã có, cùng với `seconds_since_last_entry()`.

**5. Thư cảnh báo gửi ra là mã HTML thô.**
Người nhận thấy nguyên văn `<div style="font-family: Arial…">` in thành chữ,
dài hai màn hình. Nguyên nhân: `message` của contact point kiểu email **không
phải thân thư** — Grafana có khuôn HTML riêng và chèn `message` vào đó qua
`html/template`, tức là escape mọi dấu ngoặc nhọn. Không tắt được ở Grafana OSS.
Đã viết lại thành văn bản thuần, và duyệt `.Alerts` thay vì `.CommonLabels` để
một nhóm gộp nhiều sự cố không còn hiện ra các ô trống.

Cùng lúc: 7 quy tắc cảnh báo phần cứng/hạ tầng có tiêu đề và mô tả bằng tiếng
Anh (`Hardware disconnected`, `Possible DDoS`) — đã dịch và viết lại thành câu
nói rõ phải làm gì.

**6. Cảnh báo phía Prometheus sẽ không tới tay ai.**
Bản triển khai này **không chạy Alertmanager**, nên một quy tắc trong
`rule_files` chỉ chuyển sang trạng thái ĐANG KÊU trên trang `/alerts` rồi nằm
im. Ba cảnh báo kiểm toán vì thế đặt trong hệ hợp nhất của Grafana
(`logging/grafana/alerting/audit-alerts.yml`), nơi đã có contact point gửi thư
thật. Một quy tắc không gửi được cho ai còn tệ hơn không có quy tắc — nó tạo
cảm giác đang có người canh.

**7. Ổ dữ liệu ở 96%, và cơ chế chống tràn đã âm thầm kích hoạt.**
`sync_tasks._disk_over_watermark()` dừng tải tệp thiếu ở ngưỡng 95%, cố ý, để
bảo vệ cơ sở dữ liệu và hệ tệp. Nhưng **không ai được báo**: tác vụ trả
`stopped_disk_full` vào một kết quả Celery không ai đọc, còn triệu chứng tới
tay người là "vài bản xem trước bị hỏng".

Nó lộ ra chỉ vì hai test không liên quan chuyển đỏ. Đã thêm mục
`cho trong o du lieu` vào `verify_deployment` — **FAIL** khi chạm ngưỡng, WARN
khi còn cách 5 điểm phần trăm, và dùng **chính hằng số** mà cơ chế chống tràn
dùng (hai con số cùng nghĩa "đĩa đầy" sẽ lệch nhau, và hôm chúng lệch thì cái
báo xanh là cái người vận hành sẽ tin).

> **Cần người vận hành xử lý trước khi chạy thử:** ổ E còn **22,8 GB / 466 GB**.
> Đây không phải thứ sửa được bằng mã.

**8. Thư cảnh báo Grafana KHÔNG gửi được — chặn ở tầng máy chủ, không phải mã.**
Khuôn thư đã sửa xong và đã nạp (kiểm qua API provisioning), nhưng **không
kiểm chứng được đầu-cuối** vì máy này chặn outbound **UDP cổng 53**:

```
container → 8.8.8.8 UDP/53           hết giờ
container → 8.8.8.8 TCP/53           chạy
container → smtp.gmail.com:587 TCP   mở
```

DNS nhúng của Docker chuyển tiếp bằng UDP, nên container không phân giải được
tên ngoài. `voya_backend` (Debian/glibc) **không bị ảnh hưởng** — glibc lùi sang
TCP, nên thư OTP / lời mời / đặt lại mật khẩu vẫn gửi bình thường. Grafana chạy
trên Alpine, dùng bộ phân giải thuần Go, và Go **không** lùi sang TCP khi UDP
hết giờ.

Tệ hơn: Grafana coi lỗi này là "unrecoverable after 1 attempts" và **bỏ luôn**
thông báo đó — lần thử kế tiếp phải chờ hết `repeat_interval` (4 giờ).

> **Cần người vận hành xử lý:** mở outbound UDP/53 cho card mạng Docker/WSL,
> hoặc kiểm tra VPN / phần mềm diệt virus. Chi tiết + lệnh kiểm nhanh:
> `docs/06-operations/OBSERVABILITY_PLAN.md` §9bis.

**9. Cảnh báo phần cứng đang KÊU THẬT: `voya_hardware_error{resource="gpu"}=1`.**
Backend báo `gpu.available = False` — stack đang chạy **không có overlay GPU**,
nên container không thấy card, dù máy có card thật (xem ghi chú cũ về
`gpu.yml`). Đây chính là nội dung lá thư "Hardware Error Alert" đã nhận được.

Sửa khuôn thư **không làm cảnh báo này im**: nó sẽ tiếp tục kêu 4 giờ một lần
cho tới khi một trong hai việc xảy ra — dựng stack kèm overlay GPU, hoặc bấm
"Bỏ qua" ở trang Tài nguyên (`POST /admin/config/ignore-hardware`). Cả hai đều
là quyết định vận hành, không tự làm thay.
---

## Đợt 2026-08-09 (lượt ba) — đồng thuận, ngưỡng đĩa, GPU, stack lệch

### Đã đóng

| Việc | Chi tiết |
|---|---|
| **Đồng thuận được thực thi** | `app/consent_gate.py` + ảnh chụp + CLI, nối vào huấn luyện / manifest / LOSO. Xem `docs/04-legal/CONSENT_ENFORCEMENT.md`. 43 test. |
| **Ngưỡng đĩa một nguồn** | Trước đây cùng một ngưỡng viết ở **ba** nơi với **ba** giá trị: 85 (`monitoring.DISK_WARN_PCT`), 0.95 (`sync_tasks.DISK_HIGH_WATERMARK`), và một phép trừ `watermark − 5` = 90 trong `verify_deployment`. Bảng quản trị cảnh báo ở 85 trong khi kiểm tra sau triển khai im lặng tới 90. Giờ `monitoring` giữ cả hai con số (85 / 95) và hai nơi kia nhập từ đó. |
| **Chẩn đoán GPU nói được việc cần làm** | Thư cảnh báo cũ gửi đúng một câu cho mọi nguyên nhân — *"Nvidia GPU is missing or unreadable"* — nên nó bảo đi tìm cái card đang nằm yên trong máy. Thêm ngọn đèn báo vắng mặt (`monitor:gpu:absent`, chỉ trainer thắp) để tách "máy không có GPU" khỏi "container không được cấp thiết bị" khỏi "trainer chết". |
| **Bắt được stack dựng thiếu overlay** | `verify_deployment` kiểm tra #8 đọc cgroup **của chính nó**: `memory.max = max` nghĩa là `docker-compose.prod.yml` không được áp. Không cần docker socket, và một phép đo từ bên trong không lệch được so với thực tế đang chạy. |

### Phát hiện lúc làm

**Stack đang chạy bị lệch — 11/14 container mất giới hạn bộ nhớ, trainer mất GPU.**
`docker compose ls` báo đủ ba tệp cấu hình, nhưng nhãn trên từng container kể
chuyện khác: `prometheus`/`promtail`/`loki` được dựng bằng lệnh ba tệp, 11
container còn lại được dựng lại sau đó bằng `docker compose up -d` chỉ với tệp
gốc. Hậu quả đo được:

```
voya_backend  HostConfig.Memory = 0      (không giới hạn)
voya_worker   HostConfig.Memory = 0
voya_trainer  HostConfig.Memory = 0, DeviceRequests = null
```

Đây **chính là** regression mà `stack-missing-prod-override` ghi là đã xử lý
2026-07-22. Nó quay lại vì không có gì canh. Kiểm tra #8 giờ canh nó.

Cách triển khai đúng — `scripts/deploy.sh` đã tự dò GPU và thêm overlay:

```bash
bash scripts/deploy.sh
```

**Máy chủ CÓ GPU và NVIDIA Container Toolkit chạy được.**
`docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` in ra
bảng GPU (RTX 3050 Laptop, 4 GB). Nên cảnh báo GPU trước đây **đúng về trạng
thái nhưng sai về nguyên nhân**: không có GPU nào trong stack, vì trainer được
dựng thiếu overlay — không phải vì máy thiếu card.

### Còn treo

- ~~**Không có giao diện thu đồng thuận.**~~ **Xong 2026-08-09 (lượt hai):**
  `/account` → "Chấp thuận của tôi" (`frontend/src/pages/AccountPage.tsx`) ký và
  rút được, kèm đường đọc lại đúng bản đã ký. Việc còn lại là **dữ liệu**: chừng
  nào chưa ai bấm đồng ý thì `signer_consents` vẫn 0 dòng và bản phát hành
  nghiên cứu vẫn rỗng — kết quả đúng của cơ chế, không phải lỗi.
- **56,6% mẫu không có `signer_id`** → không phát hành được và không thi hành
  được lời rút. `verify_deployment` #10 theo dõi con số.
- **Chưa có cột phân biệt "người thu" với "người ký"** — lý do hoãn nằm ở §6 của
  `docs/04-legal/CONSENT_ENFORCEMENT.md`.

---

## Đợt 2026-08-10

### Lược đồ máy dựng mới KHÁC máy đang chạy — đã vá

Phát hiện khi lần đầu chạy bộ test trên một CSDL trống (để dựng CI). Suốt từ
trước suite luôn chạy trên **bản sao của sản xuất**, nơi món nợ này đã được trả
bằng tay từ lâu, nên nó vô hình.

Một máy dựng mới nhận: thiếu **2 bảng** (`languages`, `roles` — chỉ tồn tại
trong `backup.sql`, không dòng mã nào tạo), thiếu **7 khoá ngoại**, thiếu **14
cột** (gồm `users.phone_number` mà luồng OTP đang đọc), và **1 giá trị mặc định
sai**.

Chúng không chết ồn ào: vòng áp khoá ngoại chỉ bảo vệ bảng *đang sửa*, không
kiểm bảng *được tham chiếu*, nên lỗi bị `EXCEPTION WHEN others` hạ xuống
WARNING. Máy khởi động khoẻ mạnh và thiếu 7 ràng buộc toàn vẹn.

Bẫy đáng nhớ nhất: `samples.gdrive_synced` được khai **hai lần với hai mặc định
trái ngược** — `CREATE TABLE` nói `FALSE`, migration nói `TRUE`. Máy cũ ăn ALTER
nên TRUE; máy mới ăn CREATE nên FALSE và ALTER thành no-op. Vòng đồng bộ Sheets
lọc `gdrive_synced = TRUE`, nên trên máy mới **mọi mẫu mới vô hình với nó**.

Sau khi vá: bản dựng mới ra đúng **44 bảng, 88 khoá ngoại, `schema_debt()` rỗng,
0 cột lệch**, sạch qua ba lần boot liên tiếp. Suite trên CSDL trống 22 đỏ → 0.

### Vòng đời đăng ký — 0/9 bước thành 7/9

Xem `docs/07-business/SUBSCRIPTION_LIFECYCLE.md`. Kỳ hạn, tự gia hạn, nhắc 7/3/1 ngày, ân
hạn, khoá mềm, hạ gói tự động, rời nền tảng. Hai bước còn thiếu (thanh toán,
hoá đơn) cần một cổng thanh toán và một pháp nhân — nằm ngoài phần mềm, và
**không được viết là "sắp có"**.

### CI — có thật, và chạy test

`.github/workflows/ci.yml`: lint kiểu → dựng frontend → hai bộ test → xuất
`junit-*.xml` làm artifact. `build_docker.yml` chuyển sang `on: push` vào `main`
(PR hết ghi đè ảnh sản xuất) và gắn tag `sha-<commit>`.

### Còn treo sau đợt này

- **Không có môi trường thử (staging)** — ba tệp compose đều nhắm sản xuất.
- **Migration không có đường lùi** — không hàm `downgrade` nào.
- **Không có quy trình xoay khoá bí mật** (SOT, JWT, API key).
- **Không có trung tâm thông báo, kênh hỗ trợ, 2FA/SSO, khung đa ngôn ngữ.**
- **Thanh toán và hoá đơn** — xem trên.

### Sáu test đỏ trong đợt này — nguyên nhân và cách sửa

Suite lượt đầu: **1.643 xanh / 6 đỏ**. Không cái nào là hồi quy chức năng.

| Test | Nguyên nhân | Sửa |
|---|---|---|
| `test_tenant_isolation::test_boundary_crossings_are_an_allowlist` | `cli/consent_snapshot.py` dùng `system_scope` — cổng làm **đúng việc của nó** | thêm mục kèm lý do; ghi rõ vì sao `consent_gate.py` KHÔNG nằm trong danh sách |
| `test_observability::…_missing_resources` | ghim đúng chuỗi `"Nvidia GPU is missing or unreadable."` — chính câu vừa bị thay | khẳng định lý do được **mang theo**, không khẳng định một câu cố định |
| `test_research_suites[test_manifest.py]` | cổng đồng thuận mới từ chối dựng manifest trong thư mục tạm không có ảnh chụp | `--skip-consent-gate` ở hàm trợ giúp + **thêm MF5** kiểm chính cái cổng, để cờ đó không biến bộ này thành bộ không bao giờ chạm cổng |
| 3 test pháp lý | **bản nháp `data_contribution` THẬT đang mở trong `signdb`** — bản sao mang theo, ba test viết cứng đúng loại đó | fixture `free_legal_kinds` chọn động một loại còn trống; **không xoá, không sửa** bản nháp thật của người soạn |

Bẫy khi chẩn đoán cái cuối: `status='open'` không tồn tại trong lược đồ —
`OPEN_DRAFT_STATUSES = ("draft", "in_review", "approved")`. Hỏi sai trạng thái
trả về rỗng và làm ta kết luận nhầm là cơ sở dữ liệu sạch.

---

## Đợt 2026-08-09 (lượt bốn) — chấp thuận nối được, đổi tên kéo được, GPU hai máy

| Việc | Chi tiết |
|---|---|
| **Chấp thuận tài khoản nối sang đồng thuận người ký** | `consent_gate.sync_signer_consent`, gọi từ `legal.record_consent` và `signers.resolve_signer_for_user`. Ký `data_contribution` cấp đúng `internal_training` — chính là ranh giới bản văn 2026-08-08 mục 4 đã vạch. |
| **API tự ký / tự rút** | `GET /legal/me/consents`, `POST /legal/{kind}/accept`, `POST /legal/{kind}/withdraw`. Ký rồi thì **ở lại**: một dòng còn hiệu lực cho mỗi (người, loại), bấm hai lần không dời `granted_at`. |
| **Đổi tên tài khoản kéo theo dữ liệu** | `app/account_rename.py` + `PATCH /auth/me`. Cập nhật `samples.user_id/username`, `raw_uploads.*`, `signers.display_name`, và cột `user_id` trong `dataset/samples.csv` (nguồn sự thật, ghi TRƯỚC Postgres). |
| **GPU: torch có kernel cho chip này không** | Ảnh chụp GPU mang thêm `compute_capability` + `torch_arch_list`; `verify_deployment` **FAIL** nếu torch không có kernel cho card đang cắm. |

### Hai máy, hai chip — và bản dựng hiện tại chạy được cả hai

```
máy A  RTX 3050 Laptop   Ampere     sm_86
máy B  RTX 5060 Ti       Blackwell  sm_120

torch 2.7.1+cu128  ->  sm_75 sm_80 sm_86 sm_90 sm_100 sm_120 compute_120
```

Cả hai đều nằm trong danh sách, nên **không cần đổi gì cho máy B**. Điều đó
không hiển nhiên và không vĩnh viễn: hạ về một wheel `cu121` là máy B lặng lẽ
rơi xuống CPU — `pick_device` lùi về CPU nên job **vẫn chạy**, chỉ chậm gấp
nhiều lần và không ai được báo. Vì thế phép so khớp giờ được **đo** ở nơi có
card rồi gửi kèm ảnh chụp, thay vì để ai đó nhớ.

### Hai loại bản sao của `username` — và chỉ một loại được cập nhật

Đây là phần dễ làm sai nhất của việc đổi tên:

- **Ảnh chụp trạng thái hiện tại — PHẢI đổi:** `samples.user_id`,
  `samples.username`, `raw_uploads.user_id`, `raw_uploads.username`,
  `signers.display_name`. Chúng trả lời "dữ liệu này của ai".
- **Bằng chứng lịch sử — TUYỆT ĐỐI KHÔNG đổi:** `audit_log.actor_label`,
  `legal_document_events.actor_label`. Chúng trả lời "lúc đó AI đã bấm nút".
  Sửa theo tên mới là viết lại lịch sử.

Cả hai chiều đều có test ghim (`tests/test_account_rename.py`).

### Lỗi cổng ranh giới tenant bắt được trong lúc làm

`account_rename.rename_user` chạy trong `system_scope` (mặt phẳng danh tính,
gọi được từ dòng lệnh). Bản đầu có nhánh "hàng vô chủ, khớp theo tên hiển thị"
**không** kèm `tenant_id`, tức là sẽ đổi tên cả dữ liệu vô chủ của tenant khác
trùng tên. Vô hình trên bản triển khai một tenant — đúng loại lỗi chỉ lộ ra khi
có khách hàng thứ hai. Cổng allowlist buộc phải viết lý do, và viết lý do là lúc
lỗi lộ ra.

---

## Đợt 2026-08-10 (lượt hai) — vòng đời phiên, 2FA, thông báo, hỗ trợ, đa ngôn ngữ

Bốn lỗ ở `docs/03-security/AUTH_TOKEN_LIFECYCLE.md` (rà 31/07) đã đóng, cộng bốn
tính năng của Mục 12. Chi tiết ở `docs/03-security/SESSION_LIFECYCLE.md`,
`docs/03-security/TWO_FACTOR.md`, `docs/06-operations/NOTIFICATIONS_AND_SUPPORT.md`.

### Năm lỗi tìm được TRONG lúc vá — bốn nghiêm trọng hơn thứ đang được sửa

| Lỗi | Vì sao nó im lặng |
|---|---|
| **Bế tắc CSDL** ở đường phát hiện tái sử dụng token | `_burn_token_family` chạy trong giao dịch đang giữ khoá, rồi gọi `force_logout_user` — hàm này mở kết nối Postgres **thứ hai** chờ đúng khoá đó. Treo vĩnh viễn, mỗi lần phát hiện tái sử dụng. Ghim bằng test có trần thời gian. |
| **Vé bước hai dùng thay access token được** | Mọi token ký bằng cùng một khoá; `_decode_token` chỉ kiểm `sub`. Người vừa nhập đúng mật khẩu vào thẳng hệ thống **chưa qua bước hai** — 2FA tự vô hiệu hoá chính nó. |
| **Mốc thu hồi phiên ghi hụt** | Kết nối không có scope + `users` có RLS ⇒ `UPDATE` khớp **0 dòng**, không lỗi. Lệnh thu hồi của quản trị viên trông như thành công. |

| **Rò băm mật khẩu bcrypt** | Bỏ `response_model=UserOut` để `/auth/login` trả được hai hình dạng đã gỡ luôn bộ lọc DUY NHẤT chặn `password_hash`. Băm đi ra theo mọi lượt đăng nhập thành công. Do **tự soát lại** mà thấy, không phải do test. |
| **Truy vấn thêm ở đường nóng, fail-CLOSED** | `login` gọi `two_factor.is_enabled()` và trả 503 nếu hỏng ⇒ một trục trặc CSDL thoáng qua = "không ai đăng nhập được". Sửa bằng `LEFT JOIN user_totp` vào truy vấn đã có. |

**Fail-closed chỉ đúng khi thứ có thể hỏng là một QUYẾT ĐỊNH VỀ QUYỀN.** Nếu thứ
hỏng là một lượt ĐỌC PHỤ, câu trả lời không phải chọn hướng hỏng — mà là bỏ lượt
đọc đó đi.

Cộng hai lỗi nhỏ hơn: chống phát lại TOTP **không hề chạy** (ghi rồi đọc lại
thay vì dùng `RETURNING`), và `notification_id = ANY(%s)` thiếu `::uuid[]`.

### Bài học lặp lại lần thứ ba: RLS fail-OPEN ở mặt phẳng danh tính

Ba lần trong hai ngày, cùng một hình dạng: một truy vấn chạy **trước khi biết
tenant**, gặp RLS, khớp 0 dòng, và hệ thống kết luận "không có gì" thay vì báo
lỗi. Vì thế `user_totp` và `user_recovery_codes` **cố ý** không có `tenant_id` và
không có RLS — nếu có, truy vấn kiểm 2FA lúc đăng nhập sẽ bỏ qua lớp bảo vệ thứ
hai trong im lặng.

### Hai bẫy về BỘ TEST, không phải về mã

- **Đừng gọi `rename_user` trong test.** Nó viết lại `dataset/samples.csv` —
  tệp SẢN XUẤT, không phải bản sao. Bản đầu của một test có gọi và làm treo bộ
  test 8 phút vì phải viết lại 3.860 dòng. Kiểm bằng **cấu trúc** thay thế
  (khẳng định `support_messages` không có tên trong `account_rename.py`) vừa an
  toàn vừa chứng minh mạnh hơn.
- **jsdom báo `navigator.language = "en-US"`.** Test khung đa ngôn ngữ phải ghim
  giá trị đó, không thì kết quả đổi tuỳ máy chạy.

## Hiện vật chia dữ liệu — nợ phát hiện trong C2b (16/08/2026)

### `purpose` đang mang HAI nghĩa

`write_legacy_snapshot` ghi `"purpose": "operational"` vào **mọi** bản khai nó
tạo ra — kể cả bản ở gốc `processed/splits/` và bản theo `--by_language`. Nhưng
trường đó đang làm hai việc khác nhau:

| Nghĩa | Ai đọc | Hệ quả nếu đổi |
|---|---|---|
| Không gian tên hợp đồng: "đây là hiện vật vận hành, phân biệt với mốc nghiên cứu đóng băng" | `split_artifact.resolve_operational` | — |
| Cờ tính năng: "trainer hãy đi đường `class_uid → target_idx`" | `train_tcn.py` | Đổi chữ này ở bản khai gốc sẽ **âm thầm đổi cách đánh chỉ số lớp** của các lượt legacy |

Vì vậy cổng sở hữu của C2b lấy điều kiện là **có `split_id`** (tức "hiện vật vận
hành CÓ ĐỊA CHỈ", thứ mà resolver có thể trả về cho một lượt huấn luyện), chứ
không phải `purpose == "operational"` một mình. Đây là sai lệch có chủ ý so với
quy tắc "phân biệt theo `purpose`", và lý do là trường `purpose` hiện chưa đủ tin
cậy để làm điều kiện duy nhất.

Không có rủi ro bỏ lọt: bản khai không có `split_id` thì `resolve_operational`
không bao giờ trả về được nó — nó đối chiếu `split_id` trong bản khai với tên thư
mục — nên nó không phải hiện vật mà một lượt huấn luyện tiêu thụ được.

**Việc cần làm sau:** tách hai nghĩa thành hai trường, rồi mới thu điều kiện về
đúng `purpose`. Không làm trong C2b vì nó đổi hành vi đánh chỉ số lớp của đường
legacy — thay đổi đó cần lượt đo riêng, không phải phần phụ của một bước tenant.

### Hai hiện vật vận hành KHÔNG BIẾT CHỦ — đã quyết 16/08

`hoa-de-20260815-floor25` và `bang-chu-cai-20260815-floor25` được dựng trước hợp
đồng sở hữu nên không khai `tenant_id`. Cách gọi đúng **không phải** "dữ liệu
hỏng" mà là:

```
nội dung hợp lệ, provenance không đủ để chứng minh phạm vi tenant
```

Phân biệt này quyết định việc phải làm: một bên cần dựng lại hiện vật, một bên
cần tra lại lịch sử tạo.

| | Quyết định |
|---|---|
| Hai hiện vật | **GIỮ** — bằng chứng lịch sử rằng hiện vật vận hành có trước hợp đồng sở hữu |
| Chủ sở hữu | **KHÔNG gán** — `ownership_state = unknown`, giữ nguyên |
| Dùng lúc chạy | **KHÔNG** — từ C2c resolver từ chối, fail-closed |
| Xoá | **Chưa** |

**Vì sao không dựng lại chúng với một tenant nào đó:** làm vậy chính là điều
C2b vừa cấm —

```
owner unknown  ->  con người đoán owner  ->  thành owned
```

Khác duy nhất là người tự cấp quyền sẽ là chúng ta thay vì job đang gọi. Về
provenance thì vẫn không hợp lệ.

**Backfill có chứng cứ vẫn để ngỏ.** Nếu sau này tìm được nguồn gốc đáng tin —
manifest cũ, nhật ký tạo split, bản ghi job, lệnh đã chạy, hiện vật đo đạc — thì
lúc đó mới làm một lượt chuyển quyền có ghi vết. Không chứng cứ thì không
backfill.

**`test_api_operational_contract.py` giờ tự dựng hiện vật của nó**
(`test-owned-operational-a`, chủ tường minh, dọn sau khi chạy) thay vì mượn
`hoa-de-…`. Chiều phụ thuộc cũ mới là vấn đề thật: bộ ca vay một hiện vật lịch
sử, rồi khi hợp đồng bảo mật siết lại, 19 ca đỏ trở thành sức ép phải NỚI hợp
đồng. Đầu vào của bộ ca phải do chính nó sở hữu.

## Mặt phẳng đầu ra huấn luyện — C3 (16/08/2026)

### Đã vá: `training_jobs` là cache TOÀN TIẾN TRÌNH, RLS không với tới

`routers/training.py:235` giữ `training_jobs: Dict[str, Dict]` khoá theo
`job_id`, và `_ensure_job_loaded` trả thẳng bản sao khi job ở trạng thái cuối —
**không hỏi Postgres**, nên không gặp RLS. Một tiến trình backend phục vụ mọi tổ
chức, nên tổ chức B chỉ cần biết `job_id` của A là đọc được cấu hình, chỉ số, và
`checkpoint_path` của A.

Hai đường vào, đường thứ hai nặng hơn:

```
A xem job của mình  ->  nạp cache  ->  B hỏi cùng job_id  ->  ĐỌC ĐƯỢC
backend KHỞI ĐỘNG   ->  `_restore_jobs_from_db` nạp job của MỌI tenant
                    ->  B đọc được ngay, không cần A làm gì
```

Đo được ở `test_c3_job_read_confinement.py`: B nhận **200 + toàn bộ thân job**,
gồm `checkpoint_path`. Vá bằng cách gắn chủ sở hữu vào từng mục cache và đối
chiếu trước khi phục vụ; cả ba nơi ghi cache đều đã stamp.

### Đã vá: WebSocket chạy NGOÀI mọi phạm vi tenant

`TenantScopeMiddleware` thoát sớm ở `scope["type"] != "http"` — có chủ ý, và
đúng với `lifespan`. Nhưng endpoint WS phát tiến độ huấn luyện dùng chung
`_ensure_job_loaded` và `list_training_metrics` với đường HTTP, nên mọi truy vấn
trong đó chạy không phạm vi. Nay endpoint tự bind phạm vi từ tài khoản đã xác
thực.

Đo được: `training_jobs` **fail-CLOSED** khi không phạm vi (tốt);
`training_metrics` thì không.

### ĐÃ vá: `training_metrics` nhận quyền sở hữu

Trước 16/08/2026 bảng con không có `tenant_id` và không có RLS, trong khi bảng
cha có cả hai — quyền sở hữu của đầu ra đứt đúng ở đó.

| bảng | tenant_id | RLS | FORCE | policy |
|---|---|---|---|---|
| `training_jobs` | có | có | có | 1 |
| `training_job_classes` | có | có | có | 1 |
| `training_metrics` | **có (mới)** | **có** | **có** | **1** |

**Thứ tự migration là hợp đồng, không phải sở thích:**

```
1  ADD COLUMN nullable          chưa ràng buộc gì, chưa hỏng được gì
2  BACKFILL từ job cha          bước dữ liệu, hậu điều kiện HAI vế
3  SET NOT NULL                 chỉ hợp lệ sau khi (2) đã chứng minh
4  UNIQUE(tenant_id, job_id)    đích cho khoá ngoại ghép
5  khoá ngoại GHÉP              CSDL tự chặn metric.tenant ≠ job.tenant
```

Hậu điều kiện có **hai vế**, và vế thứ hai mới là vế bảo mật: (1) không còn chỉ
số thiếu tenant, (2) không chỉ số nào LỆCH tenant cha. Chỉ kiểm vế một thì một
bản vá gán tất cả về `default` vẫn "đạt". Chỉ số mồ côi làm migration **DỪNG**,
không suy về `default`.

`SET NOT NULL` nằm trong `MIGRATION_MUST_SUCCEED`: nuốt lỗi ở đây để lại cột
NULLABLE trên bảng vừa bật RLS, và vị từ policy so `NULL = 'iso_a'` cho ra NULL
chứ không phải FALSE — hàng đó **vô hình với mọi tenant, kể cả chủ của nó**. Một
lỗi im lặng biến thành mất dữ liệu.

**Backfill này hợp lệ**, khác hẳn hai hiện vật vận hành mất chủ: khoá ngoại
`training_metrics.job_id → training_jobs.job_id` cho ra chủ sở hữu THẬT chứ
không phải phỏng đoán. Có provenance thì có quyền backfill.

**Hai lưới, không phải một:**

```
lưới 1  `insert_training_metric` suy tenant từ job cha NGAY trong câu INSERT
lưới 2  khoá ngoại GHÉP — không phụ thuộc mã ứng dụng
```

Chữ ký hàm cố ý **không** nhận `tenant_id`: người gọi tự khai thì giá trị ấy
thành thẩm quyền, mà thẩm quyền phải là hàng job đã lưu. Hệ quả phụ ta MUỐN:
job không tồn tại thì `SELECT` không ra dòng nào và lượt ghi lặng lẽ không làm
gì, thay vì tạo chỉ số mồ côi. Và vì `training_jobs` dưới RLS, một tiến trình
thuộc tổ chức khác **không ghi được** chỉ số vào job của A — cách ly cả chiều
ghi.

Đột biến: đổi `j.tenant_id` thành `%(tenant_id)s` → **8/13 ca đỏ**.

Bằng chứng: `test_c3_metric_ownership.py` (13 ca, C3-M1..M6).

### Hai mặt phẳng registry KHÔNG TỒN TẠI trong hệ thống này

`experiments`, `experiment_metrics`, `model_versions` chỉ có DDL trong
`backend/migrations/001_…sql` và `002_…sql`, **không** có trong `ensure_tables()`.
`experiment_tracking_api.py` ghi vào chúng (0 lần nhắc `tenant`), nhưng
`routers/experiments.py` **không được mount** — `main.py:18` nói rõ là cố ý.
Không URL nào tới được.

Nên C3 không đi tìm rò rỉ tenant ở đó: không có gì để rò. "Chưa kiểm" và "kiểm
rồi, không tồn tại" là hai trạng thái khác nhau, và chỉ trạng thái thứ hai đóng
được ô trong ma trận cam kết. `test_c3_output_ledger.py` canh kết luận phủ định
này: ngày các bảng xuất hiện, ca đỏ.

### Mặt phẳng LƯU TRỮ VẬT LÝ — đo xong 16/08, hai lỗi thật

Layout **không đổi**, và kết luận không đến từ hình dạng thư mục mà từ NĂNG LỰC
đo được.

```
processed/train_utils/outputs/
    <model_type>_<stamp>.pt        <- phẳng; tên KHÔNG mang job_id/tenant_id
    job_artifacts/<job_id>.log     <- tên CÓ mang job_id
```

**Đường ĐỌC: PASS.** Không endpoint nào nhận đường dẫn từ người gọi;
`TrainingJob` (mang `checkpoint_path`) không bao giờ là thân yêu cầu; đường dẫn
chỉ tới tay người gọi qua hàng job của chính họ, vốn đã dưới RLS + cổng cache đã
vá. **C3-S3 = NOT APPLICABLE**, và nay có guard: ngày ai thêm một tham số
đường dẫn vào endpoint, ca đó đỏ.

**Lỗi 1 — đường dự phòng chọn checkpoint của tổ chức khác** (Trường hợp B).

```python
candidates = sorted(OUTPUTS_DIR.glob("*.pt"), key=mtime, reverse=True)
checkpoint_path = str(candidates[0])
```

Job của A kết thúc mà bản ghi `final` thiếu `checkpoint_path` (trainer bị giết,
tệp chỉ số cụt) → chọn tệp `.pt` mới nhất → tệp đó của B → **hàng job của A ghi
checkpoint của B**. Từ đó mọi phép kiểm phạm vi đều ĐẠT, vì hàng job thuộc A
thật. A tải về và đưa vào sản xuất trọng số của B qua một đường hoàn toàn hợp
lệ. Không cần ai tấn công.

Vá: **không đoán nữa**. Lọc theo tenant là bất khả — tên tệp không mang định
danh — nên lựa chọn duy nhất đúng là DỪNG. Job thành `failed` với lý do
`checkpoint_missing`, không phải `completed` không-checkpoint.

**Lỗi 2 — lượt dọn định kỳ xoá hiện vật xuyên tổ chức** (Trường hợp C).

"Giữ 20 bản mới nhất" áp trên thư mục DÙNG CHUNG. Tổ chức train nhiều hơn đẩy
checkpoint của tổ chức khác ra khỏi cửa sổ giữ, và lượt dọn xoá chúng — theo
lịch. B không đọc được hiện vật của A nhưng **xoá được**: rủi ro TOÀN VẸN,
không kém nghiêm trọng hơn rò rỉ.

Vá: nhóm theo chủ sở hữu (tra từ `training_jobs.checkpoint_path → tenant_id`)
rồi mới áp N. Tệp không tra được chủ **để nguyên** — cùng luật C2c, đổi chiều:
ở đó không biết chủ thì không cho đọc, ở đây không biết chủ thì không được xoá.
Tra chủ thất bại → bỏ qua cả lượt dọn, không quay về quét mù.

**Còn lại là nợ gia cố, không phải lỗ hổng:** tên checkpoint không mang định
danh, và thư mục vẫn phẳng. Đề xuất `OUTPUTS_DIR/<tenant_id>/<job_id>/` **chỉ
cho hiện vật mới**, không di chuyển tệp cũ. Và đường dẫn không bao giờ là thẩm
quyền: `/outputs/iso_a/...` không chứng minh tệp thuộc `iso_a` — thẩm quyền vẫn
là `training_jobs.tenant_id`.

Bằng chứng: `test_c3_storage_confinement.py` (12 ca).

### Một lỗi teardown xuất hiện MỘT lần, không tái hiện

Trong một lượt chạy 26 tệp, `test_c3_ws_unscoped_read.py::test_pham_vi_khac…`
báo ERROR ở teardown và sổ dấu vết ghi `training_jobs +1`. Chạy lại tệp đó ba
lượt riêng và hai lượt đầy đủ 26 tệp: **không tái hiện** (349 xanh).

Ghi ở đây thay vì bỏ qua: chưa tìm ra nguyên nhân thì chưa được gọi là đã sửa.
Nghi ngờ đầu tiên là đua giữa teardown của fixture và lượt dọn của conftest.
Nếu thấy lại, bắt đầu từ đó.

### Bộ ca đứng ngoài nhóm B vẫn đỏ âm thầm

Hai tệp — `test_api_operational_contract.py` và `test_training_lifecycle.py` —
dùng người dùng giả thiếu `tenant_id`, nên `quota_deps.tenant_of` fail-closed từ
nhóm B làm chúng đỏ, và không ai biết vì chúng không nằm trong bộ ca của nhóm B.
**Bài học cho nhóm H:** mỗi nhóm đóng bằng bộ ca của riêng nó chỉ chứng minh
được đúng những tệp nó mở ra. Chạy một lượt gom các tệp liên quan sau mỗi nhóm
lớn, đừng dồn tới cuối.

### Còn treo sau đợt này

- **SSO** — thiết kế đầy đủ ở `docs/01-architecture/SSO_OIDC_DESIGN.md`, **chưa hiện
  thực**. Không kiểm chứng được nếu không có một IdP thật, và CTU chưa cấp
  `client_id`. Phần đáng giá nhất (§6, huỷ kích hoạt khi tài khoản bị tắt ở phía
  IdP) cũng là phần hầu hết bản cài đặt SSO bỏ qua.
- **Không có quy trình xoay khoá bí mật**, và giờ nó đắt hơn trước: đổi
  `SECRET_KEY` làm mọi bí mật TOTP không giải mã được, **toàn bộ người dùng phải
  đăng ký lại 2FA**.
- **Chưa nối thông báo vào các sự kiện đang có.** Chỉ `support.reply` gọi
  `notify()`; vòng đời đăng ký, huấn luyện và đồng thuận chưa nối. Rẻ — mỗi chỗ
  một dòng.
- **Từ điển tiếng Anh không đầy đủ và không giả vờ là đầy đủ.** Phủ điều hướng,
  xác thực và ba màn hình v6. Chuỗi chưa dịch hiển thị nguyên tiếng Việt — hướng
  hỏng đúng chiều, và đó là lý do khoá là câu tiếng Việt chứ không phải mã.
- **Thanh toán và hoá đơn** — vẫn cần cổng thanh toán và một pháp nhân.
- **2FA chưa bắt buộc được theo tổ chức**; chưa có SMS/email làm bước hai (cố ý:
  cả hai yếu hơn TOTP và tạo cảm giác an toàn sai).

## Đợt 2026-08-16 — RLS fail-open ở console, chuông rỗng, bộ đo i18n mù

Xuất phát từ một danh sách phàn nàn của người dùng, không phải từ một lượt rà mã.
Điều đáng ghi lại nhất: **ba trong bốn lỗi dưới đây đều có cách hỏng trông y hệt
"chưa có dữ liệu"**, nên không có gì trong nhật ký hay bảng số bắt được chúng.

### Đã sửa

| # | Triệu chứng người dùng thấy | Nguyên nhân gốc | Neo lại bằng |
|---|---|---|---|
| A1 | "Quản lý người dùng" ghi *Không có người dùng* trong khi `users` có 10 dòng | `routers/admin.py` mở kết nối bằng `connect_postgres()` rồi truy vấn thẳng. `users` có RLS đọc GUC `app.tenant_id`; kết nối chưa gọi `apply_scope()` có GUC rỗng → **khớp 0 dòng, không phải lỗi** | `test_admin_console_reads_under_rls.py`, chạy ở phạm vi **tenant** chứ không system |
| A2 | Đổi quyền admin trả 404 cho tài khoản có thật | Cùng A1 — câu `UPDATE ... RETURNING` khớp 0 dòng | cùng trên |
| A3 | Bảng "Phiên đang hoạt động" hiện **Khách** cho mọi dòng, kể cả phiên của chính quản trị viên | `activity._resolve_usernames` cũng mở kết nối trần → trả `{}` | cùng trên |
| B1 | Chuông thông báo không bao giờ sáng | Cả backend chỉ có **một** chỗ gọi `notifications.notify()`: `app/support.py`. 7 loại được khai, 6 loại không ai phát. Sản xuất: 2 dòng, cả hai `kind='support'` | `test_training_notifies_owner.py` |
| C1 | Chọn tiếng Anh vẫn thấy chữ Việt, trong khi `i18n-coverage.mjs` báo **100,0%** | Hai chỗ mù ở bước tiền xử lý: (1) `accept="video/*"` mở một **chú thích khối ma** nuốt 65 dòng; (2) luật 1 đòi chữ nằm ngay sau `>` **cùng dòng**, nên mọi nút văn bản JSX xuống dòng đều lọt | `stripComments` viết lại có nhận biết chuỗi + regex; thêm luật 1b |
| D1 | *"tôi còn gửi tin nhắn không được nữa"* ở cửa sổ hỗ trợ | `SupportPage` truyền `disabled={busy \|\| !ready}` vào `Composer`, và `disabled` khoá **cả ô nhập**. `ready` đòi chính nội dung ô đó → vòng luẩn quẩn, textarea không nhận phím | `SupportPage.composer.test.tsx` |
| D2 | Bàn trực hỗ trợ hiện hàng đợi rỗng | Bộ lọc mặc định `open`, còn hai phiếu thật ở `pending`/`closed` | mặc định đổi thành "Tất cả" |

### Con số thật sau khi sửa bộ đo

`i18n-coverage.mjs` từ **100,0% (sai)** về **96,6% (thật)**: còn **63 chuỗi trần ở
32 tệp**. Đây là lần thứ **ba** bảng số này báo 100% trong khi màn hình còn chữ
Việt — hai lần trước là marker che cả tệp và các luật thiếu.

### Còn treo

- **63 chuỗi i18n còn trần.** Phần lớn là mảnh câu quanh `{biến}`, phải gom
  thành câu trọn bằng `<Trans>`. Cơ học nhưng nhiều việc tay.
- **Chuỗi do BACKEND sinh chưa qua i18n** — ví dụ `activity.py:181` trả
  `"Nội bộ / LAN"` thẳng cho bảng phiên. Không có cơ chế nào cho nhóm này.
- **Ba loại thông báo còn lại chưa có nguồn phát**: `data`, `system`, và phần
  còn lại của `security` (đăng nhập từ thiết bị lạ).
- **`change_email` dùng lại `purpose='verify_email'`** thay vì có mục đích
  riêng, vì `verification_codes.purpose` có ràng buộc CHECK và một mục đích mới
  là bước migration một chiều trên sản xuất. An toàn vì `otp.mark_verified` chỉ
  đánh dấu khi địa chỉ trùng email hiện tại — nhưng đây là chỗ cần đọc kỹ trước
  khi ai đó nới `mark_verified`.

## Đợt C3 chưa đóng: `training_metrics` có `tenant_id` nhưng purge bỏ sót (17/08/2026)

Tìm được khi chạy lại bộ test để lấy số liệu cho quyển luận văn. **Hai test đỏ,
một nguyên nhân gốc** — tái hiện chắc chắn khi chạy riêng (2 failed, 26 passed):

```
test_schema_shape.py::test_tenant_purge_order_covers_every_tenant_table
  AssertionError: những bảng này có tenant_id nhưng purge_tenant không xoá:
  ['training_metrics']

test_schema_constraints.py::test_training_metrics_cannot_orphan_itself
  psycopg2.errors.NotNullViolation: null value in column "tenant_id" of
  relation "training_metrics" violates not-null constraint
```

Đợt C3 gắn `tenant_id NOT NULL` cho `training_metrics` nhưng **chưa** làm hai
việc đi kèm:

1. Thêm bảng vào `_TENANT_PURGE_ORDER` — **đúng vị trí phụ thuộc**, không nối vào
   cuối (con phải đi trước cha, đúng như thông báo của test nói).
2. Cập nhật `test_training_metrics_cannot_orphan_itself`: nó còn chèn theo lược
   đồ cũ, không truyền `tenant_id`.

**Hệ quả nghiệp vụ, đây mới là phần nặng:** `purge_tenant` (UC508 "Dọn sạch dữ
liệu tổ chức") hiện **để sót** chỉ số huấn luyện. Một tổ chức yêu cầu xoá dữ liệu
được báo là đã xoá xong trong khi `training_metrics` của họ còn nguyên. Không có
triệu chứng nào khi dùng bình thường — thao tác dọn vẫn chạy xong và vẫn báo
thành công.

Chưa sửa: phát hiện trong lúc đo thì ghi, không sửa ngay.

## Bộ test bị chặn bởi thời hạn Drive, không phải treo (17/08/2026)

Lượt chạy hồi quy dừng tiến ở 62 %, CPU container 0,4–1,2 %, bên trong có kết nối
HTTPS mở tới Google. Không phải treo — đang chờ **đúng như cấu hình**:

```
GOOGLE_DRIVE_TIMEOUT_SECONDS  mặc định 180
GOOGLE_DRIVE_NUM_RETRIES      mặc định   5
                              ─────────────
  một lượt gọi hụt đích        tối đa 900 giây = 15 phút
```

`docs/08-testing/TESTING.md` chỉ cảnh báo `test_sot_integration.py`. Loại trừ
đúng tệp đó rồi chạy lại thì lượt chạy dừng ở **cùng mốc 62 %** — có ít nhất một
tệp khác cũng gọi ra ngoài (`test_optimizations.py` gọi Drive trực tiếp; còn có
đường gọi gián tiếp qua module ứng dụng nên `grep` theo tên thư viện KHÔNG phủ
hết).

Cách sửa đúng là **hạ thời hạn và số lần thử cho lượt chạy test**, không phải loại
dần từng tệp — loại tệp là chữa triệu chứng và triệu chứng mọc lại ở tệp sau.

Cách chẩn đoán tái dùng được (pytest ở chế độ `-q` chỉ in dấu chấm cho ca **đã
xong**, nên ca đang chờ không bao giờ hiện ra trong log):

```bash
docker stats <container> --no-stream --format "{{.CPUPerc}}"      # ~0% => đang chờ
docker exec <container> sh -c "cat /proc/1/net/tcp | awk 'NR>1 && \$4==\"01\"'"
```

## ĐÃ VÁ 17/08/2026 — đợt đưa bộ test về xanh

Tám bản vá, bảy trong tám thuộc **cùng một lớp lỗi**: đợt chuyển sang đọc
fail-closed theo phạm vi tenant đổi tên hàm ở nhiều seam, và các test còn vá tên
cũ. Bản vá trượt trong im lặng → hàm thật chạy → trả rỗng → test đỏ ở một khẳng
định cách xa nguyên nhân (`assert [] == [7]`, `assert 0 == 1`,
`['B'] != ['A','B','C']`).

### Lỗi ở MÃ SẢN XUẤT (2)

1. **`app/db.py` — `sync_missing_data_on_startup` gọi `list_samples()` bỏ trống
   tham số.** Dòng ngay trên đã chuyển sang `_load_all_labels_unscoped()`; dòng
   samples thì chưa. `list_samples()` **ném `TenantScopeRequired`** khi không có
   phạm vi, mà đồng bộ đầu vòng đời chạy trước khi có phạm vi nào → đường này
   chết. Ba test của nó KHÔNG bắt được vì cả ba đều mock chính hàm ấy.
   → vá: gọi `_load_all_samples_unscoped()`.

2. **`app/export_tasks.py` — `export_samples_to_sheets` cùng lỗi**, bản đối xứng
   của `export_labels_to_sheets` vốn đã chuyển đúng. Tìm ra bởi bất biến tĩnh mới
   (dưới), không phải bởi người.
   → vá: gọi `_load_all_samples_unscoped()`.

3. **`app/tenant_lifecycle.py` — `PURGE_ORDER` thiếu `training_metrics`**
   (xem mục trước). → vá: chèn TRƯỚC `training_jobs`.

### Bất biến chặn tái diễn

`test_read_scope_fail_closed.py::test_khong_noi_nao_goi_helper_co_pham_vi_ma_bo_trong_tham_so`
quét AST toàn bộ `backend/app/`: **không nơi nào được gọi `list_samples()` hay
`load_labels()` với danh sách tham số RỖNG**. Luật không có ngoại lệ hợp lệ —
hoặc thiếu phạm vi, hoặc là đường bảo trì và phải gọi `_load_all_*_unscoped()` —
nên nó không cần danh sách miễn trừ. Nó tìm ra lỗi số 2 ngay lượt chạy đầu.

Vì sao phải là phép kiểm TĨNH: thứ cần canh là *hàm nào được gọi*, và mock xoá
đúng thông tin ấy đi.

### Test lạc hậu đã cập nhật (5 tệp)

| Tệp | Vá sai chỗ | Phải vá |
|---|---|---|
| `test_startup_sync.py` (3 ca) | `app.dataset_manager.load_labels` | `_load_all_labels_unscoped` |
| `test_reassign_sheets_owner.py` (4 ca) | `ds.list_samples`, `dm.load_labels` | `_load_all_*_unscoped` |
| `test_tenant_sot_column.py` (2 ca) | `ds.list_samples`, `dm.load_labels` | `_load_all_*_unscoped` |
| `test_subscription_lifecycle.py` (2 ca) | `sub._tenant_admin_emails` | `sub._tenant_admins` (seam mới, cần cả `id` cho notification) |
| `test_upload_camera_training.py` (2 ca) | gieo job thiếu `tenant_id` | thêm `"tenant_id": u["tenant_id"]` |

**Sửa một lỗi làm lộ hai lỗi:** hai ca ở `test_tenant_sot_column.py` vốn xanh vì
chúng mock đúng cái tên cũ mà `db.py` còn gọi nhầm. Vá `db.py` cho đúng thì mock
của chúng thành trượt. Chúng đang xanh **nhờ một lỗi**.

### Hạ trần chờ Drive cho lượt chạy test

`scripts/run_tests.sh` nay đặt `GOOGLE_DRIVE_TIMEOUT_SECONDS=5` và
`GOOGLE_DRIVE_NUM_RETRIES=1` (đổi qua `VOYA_TEST_GDRIVE_TIMEOUT` /
`VOYA_TEST_GDRIVE_RETRIES`). Trước đó 180×5 = tối đa 15 phút mỗi lượt gọi hụt
đích, và suite không bao giờ chạy hết.

**Kết quả:** `2.528 ca · 2.522 xanh · 6 đỏ · 1 skip` (26 phút) → sau tám bản vá:
**0 đỏ**.

## ĐÃ VÁ 17/08/2026 — dụng cụ đo không tự khai phiên bản mã

`adversarial_isolation.py` đọc `VOYA_GIT_COMMIT`, rồi thử `git rev-parse`. Trong
container đo không có `.git` và **không ai đặt biến đó** — cả hai đường cùng hụt,
artefact mang `git_commit: null`, và phiên bản chỉ còn truy được nhờ THẺ ẢNH
container (`voya_backend_iso:e5d804c`), một chỗ nằm ngoài artefact.

Ghi null rồi chạy tiếp là fail-open đúng vào thứ làm con số có nghĩa.

→ vá: `cong_bo_duoc` nay có **hai vế**. Ngoài "không còn ca mờ", artefact phải
xác định được phiên bản mã và cây làm việc phải sạch; thiếu vế nào thì hạ cờ và
in `ly_do_khong_cong_bo`. Áp lên artefact 16/08 (mo=0, commit=None) → `False`.

`measure_api_latency.py` cùng khiếm khuyết, chưa có cờ công bố để hạ → thêm cảnh
báo ra stderr.

## P0-B ĐÓNG 17/08/2026 — và ba lỗi tìm được trên đường tới đó

```
CTIVR 0/450 · UASR 0/180 · SVSR 0/630 · 0 ca mờ · đối chứng dương 4/4
ảnh chụp mã  P0B-20260817T011910-4e9611  (tree 4e961192f079835b…)
hậu điều kiện CSDL + CSV + tệp: đạt
cong_bo_duoc = true
```

### 1. `-o /dev/null` + `MSYS_NO_PATHCONV=1` — health probe báo hỏng cho container khoẻ

`isolation_backend.sh` và `perf_backend.sh` đặt `MSYS_NO_PATHCONV=1` (cần cho
`-w /src`), và chính dòng đó trao `/dev/null` NGUYÊN VĂN cho `curl.exe` — thành
một đường dẫn tệp không tồn tại, **thoát 23 (write error)** dù máy chủ trả 200.

Hai bản vá trong cùng một tệp đánh nhau, và triệu chứng không giống nguyên nhân:

```
ban dau           -> 23 la loi vinh vien -> bo thu lai  -> hong sau 2 GIAY
them --retry-all  -> 23 thanh loi tam    -> thu du 60   -> hong sau 68 GIAY
                     (nhat ky container: 60 dong GET /health 200)
```

→ vá: dùng chuyển hướng của shell. `--retry-all-errors` vẫn giữ, cho ca Docker
publish cổng trước khi gunicorn bind (kết nối bị **reset**, không phải refused).
`test_nginx_voya.sh`: vòng chờ `curl ... && break` không bao giờ break, luôn chạy
đủ 20 lượt và không gác gì.

### 2. `hau_dieu_kien` sập vì hình dạng fixture, SAU khi đã bắn 811 lượt

Nhánh `--fixture` đọc `ben[<tenant>]["class_uid"]` — hình dạng của bộ gieo CŨ. Bộ
gieo xuyên-kho hiện hành để đối tượng ở `doi_tuong` (danh sách, khoá theo tenant
× vai trò). Kết quả: `KeyError: 'class_uid'` ném ra **sau** pha đối kháng và
**trước** khi ghi artefact — mất trắng 15 phút đo. Artefact 16/08 mang
`hau_dieu_kien: null` chính vì nhánh này chưa từng chạy được.

→ vá: lớp chuyển đổi (như `_doc_fixture_dataset` đã có cho `--dataset-fixture`),
**và** bọc bước hậu điều kiện trong try/except ghi lỗi vào artefact + hạ cờ công
bố. Một bước phụ hỏng không được phá bằng chứng vừa thu.

### 3. Cổng công bố khoá nhầm biến

Bản đầu chặn theo `git status --porcelain`, và chặn một lượt đo hợp lệ vì **một
tệp markdown chưa theo dõi**. Mã được đo nằm trong ảnh chụp chỉ-đọc, nên trạng
thái cây làm việc không chạm tới nó được.

→ vá: ghim theo `tree_sha256` của ảnh chụp; git sạch chỉ là đường dự phòng khi đo
mã nung trong ảnh. Một cổng chặn nhầm là một cổng sẽ bị tắt.

### Ghi chú vận hành: một lượt chạy sai token đã xoá thật tenant `iso_b`

Lượt thử đầu trao `--token-a` cho `iso_admin_a` — tài khoản **quản trị nền tảng**
mà bộ gieo tạo riêng cho phép đo cổng reassign. Với token đó, `GET /tenants`,
`POST /tenants`, `DELETE /tenants/iso_b` đều 200/201 **một cách hợp lệ**, và bộ đo
chấm chúng là vi phạm: CTIVR 0.2689, UASR 0.8013 — toàn bộ là hiện vật của việc
trao nhầm vai, không phải phát hiện về hệ thống.

Hệ quả thật: tenant `iso_b` bị xoá mềm và một tenant rác được tạo. Sửa xong bằng
`UPDATE tenants SET deleted_at = NULL` và một lượt purge theo `PURGE_ORDER`.

Đây đúng là lý do phép đo **không bao giờ** chạy trên `signdb`: bộ thử cố tình
phát lệnh xoá, và hôm nay một trong số đó đã thực thi.

Hai bài học nhỏ đi kèm: `--token-a` phải là **thành viên tổ chức**, không phải
quản trị nền tảng; và `psql -c "a; b; c"` chạy cả chuỗi trong MỘT giao dịch ngầm
— lỗi ở `c` cuốn ngược cả `a`, nên bản sửa `deleted_at` đầu tiên đã âm thầm bị
huỷ.
