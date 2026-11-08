# Data Collection Protocol — ISDS 2026 campaign

> Áp dụng cho chiến dịch thu live-capture sau tag `isds2026-paper-pipeline-v1`.
> Mô tả đúng hành vi hệ thống hiện tại. Chỗ nào hệ thống **không** làm, tài liệu
> nói rõ là trách nhiệm con người.

---

## 1. Danh tính: signer ID và session ID

### Signer ID

- Signer là **con người**, không phải tài khoản. Một người dùng hai tài khoản vẫn
  là một signer.
- Registry: `dataset/signers.csv` (`signer_id`, `display_name`, `regional_group`,
  `external_user_id`, `is_active`, `created_at`).
- ID do hệ thống cấp dạng `S001`, `S002`, … Backend resolve qua
  `app/signers.resolve_signer_for_user` và đóng dấu vào sidecar của từng mẫu.

**Bắt buộc trước khi thu:** thêm mọi signer mới vào registry với `is_active=1`.
Pilot gate từ chối mẫu có `signer_id` không nằm trong registry active.

> **Cảnh báo từ dữ liệu cũ.** Registry từng có `Trân` (S001), `Tran` (S003),
> `trân` (S006) — cùng một người thành 3 signer. Điều này làm hỏng mọi ràng buộc
> signer-disjoint một cách âm thầm. Đã hợp nhất bằng `scripts/apply_signer_merges.py`.
> **Không tạo signer mới cho một người đã có ID.** Kiểm tra registry trước.

### Session ID

- Một session = một lượt ngồi thu liên tục của **một** signer.
- Sinh bởi frontend, đóng dấu vào từng mẫu.
- Đổi session khi: đổi người, đổi thiết bị/camera, đổi vị trí/ánh sáng, hoặc nghỉ
  giữa chừng rồi quay lại.

Vì sao quan trọng: session là đơn vị để phát hiện near-duplicate và để giải thích
tương quan giữa các mẫu. Mẫu cùng session **không** độc lập.

---

## 2. Chọn profile và label

- Chọn `recognition_profile` **trước** khi thu: `alphabet` hoặc `hoa_de`.
- Mỗi label phải có `vocabulary_scope` + `recognition_profile` hợp lệ trong
  `dataset/labels.csv` (schema v2). Label `legacy_unassigned` hoặc scope rỗng
  **không** được thu thêm cho tới khi owner gán xong.
- Không thu cùng một slug ở cả `common` và một profile — pipeline sẽ fail với
  "label collision" lúc split.

`collection_campaign` khoá theo chiến dịch qua env `COLLECTION_CAMPAIGN`
(vd `isds2026_v4`). Đặt **trước** khi mở thu, không đổi giữa chừng.

---

## 3. Hướng dẫn thu mẫu

| Mục | Yêu cầu |
|---|---|
| Độ dài | 60 frame, lấy mẫu 30 fps (`frontend/src/config/capture.ts`) |
| Khung hình | Cả hai bàn tay trong khung suốt thời gian thực hiện ký hiệu |
| Ánh sáng | Đều, tránh ngược sáng; nền tương phản với tay |
| Camera | Cố định trong suốt một session |
| Số lần lặp / lớp / signer | **≥5**, tốt nhất 8–10 |
| Biến thiên | Giữa các lần lặp nên đổi nhẹ tốc độ và vị trí tay; **không** giữ nguyên hệt |

### Khác biệt static và dynamic

Pipeline hiện tại **xử lý hai loại như nhau** (cùng 60 frame, cùng augmentation,
cùng kiến trúc). Khác biệt nằm ở hướng dẫn cho người thu:

- **`alphabet` (static)**: giữ hình tay ổn định suốt cửa sổ thu. Tránh trôi tay.
- **`hoa_de` (dynamic)**: thực hiện trọn vẹn chuyển động trong 60 frame; bắt đầu
  và kết thúc ở tư thế nghỉ.

---

## 4. Quality gate

Chạy ở backend, trên chuỗi **trước khi** normalize (toạ độ còn ở không gian ảnh
0..1 nên ngưỡng jitter có ý nghĩa vật lý). Config version hiện tại:
`qc_v1_heuristic_2026-07`.

| Tier | Điều kiện | Hệ quả |
|---|---|---|
| **REJECT** | `any_hand_ratio < 0.7` | HTTP 422, mẫu **không** được lưu |
| | `completeness < 0.30` (khi biết số tay yêu cầu) | |
| | `jitter_p95 > 0.35` | |
| **WARN** | `completeness < 0.80` | Mẫu **được lưu**, `quality_status = flagged` |
| | `jitter_p95 > 0.12` | |
| **PASS** | còn lại | `quality_status = ok` |

- Mẫu REJECT **không lưu landmark, không lưu video**. Chỉ ghi một audit record
  (`dataset/quality_attempts.jsonl`): identity, label, verdict, metrics, thresholds.
  Log này **không bao giờ** được manifest builder đọc.
- Ngưỡng được **snapshot vào từng mẫu** (`quality_thresholds`), không chỉ lưu tên
  version — vì mọi `QC_*` đều override được bằng env.

> **Không đổi ngưỡng giữa chiến dịch.** Nếu buộc phải đổi: bump
> `QUALITY_CONFIG_VERSION` và coi dữ liệu trước/sau là hai nhóm riêng. Không gộp
> chúng trong một QC ablation.

Thống kê pass/warn/reject:
```bash
python scripts/report_quality_stats.py --campaign isds2026_v4
```

---

## 5. Pilot bắt buộc trước khi mở chiến dịch

Thu một lô nhỏ rồi kiểm tra **trước khi** thu hàng loạt. Đây là cổng chặn duy nhất
phát hiện sai hợp đồng lưu trữ trước khi nó nhân lên hàng trăm mẫu.

### Yêu cầu tối thiểu của pilot

| Mục | Tối thiểu |
|---|---|
| Signer | 2 người khác nhau, đều có trong registry |
| Session | 2 session khác nhau |
| Profile | 2 nếu khả thi (`alphabet` + `hoa_de`) |
| Lớp | 2–3 lớp mỗi profile |
| Mẫu được chấp nhận | 20–30 |
| Mẫu cố tình kém | Vài lần thử (tay ra khỏi khung, giật mạnh) để quan sát WARN/REJECT |

### Chạy gate

```bash
python scripts/validate_pilot_samples.py --campaign isds2026_v4
```

Pilot chỉ PASS khi **mọi** mẫu được chấp nhận có đủ:

- `landmarks_raw [T,126]`, `landmarks_normalized [60,126]`, khoá `sequence`
- `frame_valid_mask`, `left_hand_valid_mask`, `right_hand_valid_mask` (đều `[60]` bool)
- mask nhất quán với mảng normalized (cả frame mask lẫn hai mask theo tay)
- `signer_id` (active trong registry), `session_id`, `collection_campaign`
- `recognition_profile` hợp lệ + label key phân giải được
- `quality_status` ∈ {ok, flagged} + `quality_config_version` + `quality_thresholds`
- metric QC: `completeness`, `jitter_p95`, `any_hand_ratio`, `left_hand_ratio`,
  `right_hand_ratio`, `both_hands_ratio`
- `normalization_version = hands126_v1`, `preprocess_contract_version = v2`,
  `storage_contract_version = npz_v2`
- **golden check**: `landmarks_normalized` tái tạo được từ `landmarks_raw` qua
  `processed/shared/normalization`

Gate cũng in cảnh báo nếu số signer < 6.

---

## 6. Mục tiêu signer coverage

Đây là ràng buộc quyết định thí nghiệm nào chạy được.

| Mục tiêu | Vì sao |
|---|---|
| **≥6 signer khác nhau mỗi profile** | Dưới mức này, strict signer-disjoint split fail (đã xảy ra: `hoa_de_signer_disjoint_v1/_v3` cho val=0, test=0) |
| **≥3 signer cho MỖI lớp** | Cần đủ để chia signer vào cả train, val và test |
| **Không signer nào >40% tổng mẫu** | Hiện tại 2 người chiếm 85% — kết quả sẽ phản ánh 2 người đó |
| **≥5 lần lặp / lớp / signer** | Để có variance trong mỗi nhóm |

Kiểm tra bất cứ lúc nào:
```bash
python scripts/report_dataset_coverage.py --version <manifest-version>
```

---

## 7. Đóng băng chiến dịch

Khi thu xong:

```bash
python scripts/prepare_research_release.py \
  --campaign isds2026_v4 --manifest-version isds2026_v4 \
  --profiles alphabet hoa_de
```

Chuỗi này dừng ngay ở bước đầu tiên fail, không bao giờ dùng `--force`, và không
bao giờ ghi đè manifest hay split version đã tồn tại. Nó ghi
`reports/release_log_<version>.json` với toàn bộ command và checksum.

Sau khi manifest đóng băng: **không sửa, không xoá, không thêm file** trong
`dataset/features/` cho version đó. Dữ liệu mới → manifest version mới.

---

## 8. Trách nhiệm con người (hệ thống KHÔNG làm thay)

Đây là những việc hệ thống không kiểm được. Ghi ra để không ai tưởng là đã có.

| Việc | Trạng thái hệ thống | Ai chịu trách nhiệm |
|---|---|---|
| **Đồng ý tham gia (consent)** | Không có luồng consent trong ứng dụng | Nhóm thu thập — thu consent ngoài hệ thống, lưu riêng, trước khi thu |
| **Đúng/sai nhãn** | Không kiểm. Người thu chọn label, hệ thống tin tuyệt đối | Cần người biết VSL rà soát |
| **Xác minh annotation** | Không có luồng review/duyệt | Quy trình thủ công |
| **Trùng lặp** | Chỉ **báo cáo** sau khi thu (`audit_duplicate_samples.py`), không chặn lúc thu | Người rà soát quyết định |
| **Chất lượng thực hiện ký hiệu** | QC chỉ đo hình học (có tay không, giật không), **không** đo ký hiệu đúng hay không | Người có chuyên môn VSL |

> QC gate đo *tín hiệu có dùng được không*, không đo *ký hiệu có đúng không*.
> Đừng nhầm hai điều này khi viết bài báo.
