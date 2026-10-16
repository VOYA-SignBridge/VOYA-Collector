# Hệ thiết kế giao diện

*Cập nhật 2026-08-09.*

## 1. Bảng màu: bốn sắc thái, ba lấy từ con dấu CTU

`src/index.css` đã có sẵn bảng màu thương hiệu lấy trực tiếp từ con dấu trường
(`public/logo.png`). Bảng màu **trạng thái** giờ trùng với nó:

| Sắc thái | Màu | Nguồn | Dùng cho |
|---|---|---|---|
| `success` | `#0e7bc2` (chữ đậm `#0a5c8f`) | **CTU blue** | thành công, đang hoạt động, đã sẵn sàng, mọi ý nghĩa tích cực |
| `warning` | `#d97706` (mảng nhấn `#fbd91a`) | CTU yellow | đang chạy, chờ xử lý, cần chú ý |
| `danger` | `#ea3137` (chữ đậm `#b91c1c`) | CTU red | hỏng, thu hồi, và mọi hành động **không hồi được** |
| `neutral` | slate | — | thông tin, trạng thái không rõ |

**Thành công là XANH DƯƠNG, không phải xanh lá.** Đây là quyết định của chủ dự
án, và nó cũng đúng về thương hiệu: xanh lá là màu duy nhất từng xuất hiện
trong giao diện mà **không** có trong con dấu.

### Hệ quả phải xử lý, không được bỏ qua

Thương hiệu của hệ thống vốn đã là xanh dương. Nên một chip xanh dương **tự nó
không nói "thành công"** — nó chỉ nói "thuộc về ứng dụng này". Vì vậy:

* **Sắc thái không bao giờ đi một mình.** Mọi `Badge`, `Toast`, `ErrorBanner`
  đều kèm biểu tượng. Đây cũng là WCAG 1.4.1 (không truyền đạt thông tin bằng
  riêng màu sắc) — khoảng 8% nam giới không phân biệt được đỏ–lục.
* **`neutral` là xám đá, không phải xanh nhạt.** Nếu "thông tin" cũng xanh thì
  xanh mất hết sức nặng.
* **Chữ đậm hơn nền một bậc.** `#0e7bc2` trên nền trắng chỉ đạt 4,53:1 — vừa đủ
  AA cho chữ thường và **trượt** cho chữ nhỏ. Dùng `text-sky-700` trở lên cho
  chữ; `sky-600` chỉ dùng cho mảng đặc và viền.

### Nguồn sự thật

`src/theme/status.ts`. Đừng viết tay `bg-sky-50 text-sky-800 …` ở trang mới:

```tsx
import { toneClasses, toneForStatus, FOCUS_RING } from "../theme/status";

<span className={`border rounded px-2 ${toneClasses("success", "soft")}`}>…</span>
<button className={`border ${toneClasses("danger", "solid")} ${FOCUS_RING}`}>Xoá</button>
<Badge variant={toneForStatus(job.status)}>{job.status}</Badge>
```

Ba biến thể: `soft` (nhãn, chip, dải thông báo) · `solid` (nút chính) ·
`outline` (nút phụ).

### Hai chỗ được MIỄN TRỪ

`DialectBadge` và `DataSplitVisualization` giữ xanh lá, và đó là đúng: chúng
dùng màu **phân loại** chứ không phải trạng thái — một bảng chip băm theo id
phương ngữ, và ba chuỗi dữ liệu train/val/test trên cùng một thanh. Quy chúng
về xanh dương sẽ làm các mục trùng màu nhau và xoá đúng thứ chúng tồn tại để
hiển thị. Cả hai tệp có chú thích miễn trừ ở đầu.

## 2. Biểu tượng: SVG nội tuyến, không emoji

`src/components/ui/Icons.tsx` — 70 biểu tượng nét, hình học theo bộ **Lucide**
(giấy phép ISC, bộ đứng sau shadcn/ui). Tất cả dùng chung một thành phần `Icon`,
nên chúng thừa kế `currentColor` và cỡ chữ của chỗ đặt vào.

**Không nhúng gói npm**: vài chục biểu tượng thì một phụ thuộc mới tốn nhiều
byte hơn phần dùng tới. **Không dùng CDN**: biểu tượng tải từ ngoài sẽ vỡ sau
tường lửa của trường.

Vì sao không dùng emoji làm biểu tượng giao diện:

* Emoji do **hệ điều hành** dựng — cùng một dải thông báo ra bốn kiểu khác
  nhau trên bốn máy, và trên máy thiếu phông thì ra ô vuông rỗng.
* Emoji **không đổi màu theo `currentColor`**, nên một cảnh báo vàng vẫn kèm
  dấu đỏ.
* Emoji không nhận `aria-hidden` một cách nhất quán, nên trình đọc màn hình
  đọc cả "dấu kiểm màu xanh" giữa câu.

**Ngoại lệ có chủ ý:** mũi tên chữ `→` và `↗` trong văn bản là **dấu chữ**, không
phải biểu tượng giao diện. Chúng dựng bằng phông chữ của trang, ăn màu theo
`currentColor`, và là quy ước sắp chữ phổ biến. Giữ nguyên.

## 3. Thông báo lỗi: không bao giờ hiện chuỗi thô của máy chủ

`src/lib/errors.ts` → `friendlyError(err, "câu dự phòng theo ngữ cảnh")`.

Đây vừa là UX vừa là **bảo mật**. Một `detail` chưa lọc mang được tên bảng, tên
cột, ràng buộc khoá ngoại, đường dẫn tệp trong container, tên máy chủ nội bộ và
tên lớp ngoại lệ. Với người đang dò hệ thống thì đó là bản đồ miễn phí.

Thứ tự quyết định:

1. Có `error_code` biết trước → câu do giao diện soạn.
2. Không có mã, nhưng `detail` **trông như câu viết cho người đọc** → cho qua.
   Backend soạn nhiều thông báo tiếng Việt tử tế, chôn hết đi thì tệ hơn.
3. Còn lại → câu chung theo mã HTTP.

Bước 2 **mặc định từ chối**: chuỗi dính bất kỳ dấu hiệu hệ thống nào (vết ngăn
xếp, SQL, đường dẫn, IP, tên lớp `*Error`, dài quá 200 ký tự, nhiều dòng) đều bị
thay. **Nhóm 5xx không bao giờ cho `detail` đi qua** — đó là lỗi chưa lường
trước, đúng nhóm hay mang theo nội dung tầng dưới.

Thêm dấu hiệu mới vào `SYSTEM_MARKERS` thì thêm một test "không lộ" ở
`src/lib/__tests__/errors.test.ts` trước.

`isRetryable(err)` quyết định có nên hiện nút "Thử lại" hay không — nút đó cạnh
một lỗi 403 là lời mời làm một việc chắc chắn hỏng lần nữa.

## 4. Hiệu năng

| Việc | Trạng thái |
|---|---|
| Chunk khởi động | ~131 kB gzip (index 21,8 + react 61,3 + axios 16,6 + router 13,5 + CSS 18,4) |
| three.js (535 kB) | nạp lười qua `Hand3DPlayer`, chỉ khi mở khung xem 3D |
| recharts (338 kB) | `SessionSumary` tự `import("recharts")` trong effect |
| Nạp trước tuyến | `src/routes/prefetch.ts`, kích hoạt ở `mouseenter`/`focus`/`touchstart` của mục điều hướng |
| Chờ sau đăng nhập | trước: **chờ cứng 3 giây**; nay: nạp trước chunk `/upload`, sàn 400 ms, trần 2,5 giây |

Nạp trước tuyến tận dụng 100–300 ms giữa lúc con trỏ chạm vào mục và lúc bấm
xuống — đủ tải một chunk 10–40 kB, và không tốn byte nào cho người không bấm.
Có cả `onFocus` vì người dùng bàn phím không bao giờ phát ra `mouseenter`.

## 5. Ngôn ngữ: giao diện thuần tiếng Việt

*Rà xong 2026-08-09.*

Mọi chuỗi người dùng đọc được đều là tiếng Việt. Đã sửa 20 tệp: `SessionPanel`,
`SessionSumary`, bốn thành phần trong `pages/training/components`,
`RealtimeRuntime`, `SotAdminPage`, `LabelsPage`, `AdminResourcesPage`,
`AdminUsersPage`, `AdminActivityPage`, `UploadPage`, `LabelDetailPage`,
`UploadVideoForm`, `FullscreenCaptureModal`, `Modal`, `ToastContainer`,
`Layout`, `RegisterPage`.

### Chỗ rò kín nhất, và nó không nằm trong JSX

`api/validators.ts` ném `new Error("Invalid labels response")`, chuỗi đó chảy
qua `useFetch` rồi `setError` rồi **hiện thẳng lên màn hình**. Cùng đường đó ở
`api/realtime.ts`. Người dùng thấy một câu tiếng Anh nói về hình dạng JSON,
thứ họ không sửa được và cũng không nên biết.

Nay các hàm ấy trả câu tiếng Việt theo ngữ cảnh; chi tiết kỹ thuật xuống
`console.warn`. Đây là chỗ **thứ hai** cùng loại với `lib/errors.friendlyError`
— hai chỗ vì hai loại lỗi khác nhau: ở đó máy chủ **từ chối** (có mã HTTP để
tra), ở đây máy chủ **trả sai hình dạng** (không có gì để tra).

Rà giao diện mới thì rà cả `.ts` trong `api/`, không chỉ `.tsx`.

### Được giữ nguyên, có chủ ý

* **Tên riêng và định danh kỹ thuật**: CTU, SignBridge, VSL, Grafana,
  Prometheus, Redis, Python, PyTorch, NumPy, `sha256`, `dialect_id`,
  `samples.csv`, `X-Voya-Signature`, đường dẫn tệp.
* **Phím trên bàn phím**: `Enter`, `Esc` — đó là chữ in trên chính phím đó.
* **`Email`** — từ mượn đã vào tiếng Việt phổ thông; "thư điện tử" ở nhãn biểu
  mẫu đọc cứng hơn chứ không rõ hơn.
* **`components/DebugPanel.tsx`** — công cụ gỡ lỗi, đã bị chú thích khỏi
  `App.tsx`, không bao giờ hiện cho người dùng.

### Quét sạch emoji — xong 2026-08-09

Từ **194 chỗ trong 30 tệp** xuống **0 chỗ trong giao diện được vẽ ra**. Thêm 33
biểu tượng mới vào `Icons.tsx` cho đợt này.

16 chỗ còn lại nằm trong **chú thích và docstring**, và chúng ở lại có chủ ý:
docstring của `ErrorBanner` và `Toast` đang *giải thích chính những emoji đã bị
thay*, nên xoá đi là xoá mất lời giải thích.

Ba dạng thay, và dạng thứ ba là dạng dễ làm hỏng nhất:

1. **JSX thẳng** — `<span>📋</span>` → `<ClipboardIcon className="h-4 w-4" aria-hidden="true" />`.
2. **Emoji đầu câu** — `💡 Mẹo nhanh` → biểu tượng `inline` cộng khoảng cách.
3. **Emoji trong một CHUỖI truyền vào prop** — `label="🌐 Ngôn ngữ"`,
   `trend='↘️ Giảm'`, `icon: '📊'`. Không chèn JSX vào chuỗi được. Hai lối xử
   lý: bỏ hẳn emoji khi chữ đã đủ nghĩa (`label="Ngôn ngữ"`), hoặc đổi kiểu của
   chính prop đó từ `string` sang một thành phần (`Icon: ChartBarIcon`, rồi
   `<aug.Icon />` ở chỗ dựng).

Dạng thứ ba là chỗ TypeScript đáng lẽ phải bắt được — và **nó không bắt**, vì
`npx tsc --noEmit` ở thư mục này kiểm đúng không tệp nào. Xem `§7`.

### Ba chỗ màu mang thông tin, xử lý riêng

`🔴 / 🟠 / 🟢` ở trang Tài nguyên và `🥇 / 🥈 / 🥉` ở bảng xếp hạng **không phải
trang trí** — màu chính là nội dung. Thay bằng ba biểu tượng khác nhau là đổi
nghĩa, còn thay bằng một biểu tượng đơn sắc là mất nghĩa.

Cách xử lý: giữ nguyên màu, đổi cách vẽ. Ba chấm trạng thái thành
`<span className="h-2.5 w-2.5 rounded-full bg-red-500" />`; ba huy chương thành
**cùng một** `MedalIcon` với ba lớp màu (`text-amber-500` / `text-slate-400` /
`text-orange-700`). Ba emoji huy chương trên một máy thiếu phông màu ra ba ô
vuông giống hệt nhau — tức là mất sạch thứ tự hạng, đúng thứ duy nhất hình đó
để nói.

## 6. Còn lại

* Ba thành phần dùng chung — `Toast`, `Badge`, `ErrorBanner` — đã sạch từ trước,
  nên mọi phản hồi trạng thái đi qua chúng đều đã đúng chuẩn.
* Đảo mã chết `components/dashboard/{DashboardPage,SessionList,DatasetStats}.tsx`
  **đã xoá** ngày 2026-08-09 — không tệp nào import chúng, và trùng tên với
  `src/pages/DashboardPage.tsx` là cái bẫy đã một lần khiến tối ưu nhầm tệp.

## 7. `npx tsc --noEmit` KHÔNG kiểm gì cả — dùng `npm run typecheck`

`frontend/tsconfig.json` là `{"files": [], "references": [...]}`. Không có `-b`
thì tsc đọc đúng tệp đó, thấy không có tệp nguồn nào, và **thoát 0**. Nhìn y hệt
một lượt kiểm sạch.

Đây là lời giải cho câu ghi trong sổ tay từ trước: *"`npm run build` từng hỏng
mà `tsc --noEmit` không bắt"*. `build` chạy `tsc -b`, nên nó theo project
reference và kiểm thật; lệnh gõ tay thì không.

Đợt quét emoji giấu **14 lỗi kiểu** sau lỗ hổng này — trong đó có một biểu tượng
được dùng mà chưa import, và sáu chỗ gán `Icon:` vào một kiểu vẫn khai
`icon: string`.

```bash
npm run typecheck     # = tsc -b --noEmit   ← dùng cái này
npx tsc --noEmit      # kiểm KHÔNG tệp nào, luôn xanh
```

## 8. Ba vai, và chúng phải trùng tên với máy chủ

`MemberRole` là `admin | editor | viewer`. Không phải `owner`/`member` — hai tên
đó từng nằm trong `api/tenants.ts` và **không tồn tại ở phía sau**:
`tenant_admin.ROLES` cùng ràng buộc `CHECK` trên `tenant_members` và
`tenant_invitations` đều chỉ nhận ba tên trên.

Hệ quả khi lệch: ô chọn vai mời được ba dòng, hai dòng nhận 422; và một lời mời
vai `viewer` do máy chủ trả về thì `ROLE_LABEL[role]` ra `undefined`, hiện thành
ô trống.

`Record<MemberRole, string>` là thứ bắt được sai lệch này lúc biên dịch — **nhưng
chỉ khi `MemberRole` nói thật**. Ở đây nó nói dối, nên trình biên dịch xác nhận
một bảng nhãn phủ đúng ba vai không tồn tại.

Thứ giữ cho lỗi này sống được là **bản giả lập trong test**: nó liệt kê đầy đủ
mọi export của `api/tenants`, kể cả một `ROLE_LABEL` giả mang đúng ba vai sai.
Test xanh, sản phẩm hỏng. Bản giả lập giờ dùng `importOriginal`, nên hằng số là
hằng số thật:

```ts
vi.mock('../../api/tenants', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/tenants')>()),
  fetchTenants: vi.fn(),   // chỉ giả lập HÀM GỌI MẠNG
}));
```

Quy tắc rút ra: **giả lập lời gọi mạng, đừng giả lập hằng số.** Một hằng số giả
là một cơ hội để test và sản phẩm bất đồng ý kiến mà không ai biết.
