/**
 * Quản trị tenant.
 *
 * Backend đã có 20 endpoint ở `routers/tenants.py` từ đợt v4 nhưng **không có
 * mặt giao diện nào** — nghĩa là cơ chế cô lập hai mặt phẳng, thứ được lấy làm
 * lõi của luận văn, chỉ chạy được qua curl. Module này là mặt còn lại.
 *
 * Hai vòng quyền, và phân biệt được chúng là điều quan trọng nhất ở đây
 * ---------------------------------------------------------------------
 * Backend dùng hai dependency khác nhau, không phải một:
 *
 *   `require_admin`        — quản trị viên NỀN TẢNG. Tạo/xoá tenant, gắn một
 *                            tài khoản có sẵn vào tenant, xoá sạch dữ liệu.
 *   `require_tenant_admin` — quản trị viên CỦA TENANT ĐÓ. Đọc, đổi vai thành
 *                            viên, mời, gỡ thành viên, xuất dữ liệu.
 *
 * Ranh giới đó có lý do cụ thể: `add_member` gắn một tài khoản **theo id**, và
 * id tài khoản không phải bí mật. Nếu quản trị viên tenant làm được việc đó,
 * họ kéo được bất kỳ ai trên hệ thống vào tenant của mình. Đường đưa người vào
 * dành cho họ là lời mời, thứ đòi hỏi chính người kia phải hành động.
 *
 * Giao diện KHÔNG được tự suy ra quyền — backend mới là nơi cưỡng chế. Nhưng
 * nó nên ẩn nút mà người dùng chắc chắn không bấm được, nên các hàm dưới đây
 * ghi rõ vòng quyền trong chú thích để trang gọi biết mình đang gọi cái gì.
 *
 * @i18n-key-table — `ROLE_LABEL` là bảng KHOÁ, dịch tại chỗ đọc.
 */

import axiosClient from "./axiosClient";

const API_PREFIX = "/api/v1/tenants";

/**
 * Hai vai, đúng hai tên mà máy chủ chấp nhận.
 *
 * Bản trước ghi `"owner" | "admin" | "member"` — hai trong ba tên đó không tồn
 * tại ở phía sau. Bản sau đó ghi `admin|editor|viewer`, đúng vào lúc đó. Bài
 * học chung của cả hai lần: bảng nhãn phải phủ ĐÚNG tập tên của máy chủ, và
 * `Record<MemberRole, string>` là thứ bắt được sai lệch lúc biên dịch — nhưng
 * chỉ khi `MemberRole` nói thật.
 *
 * `viewer` đã nghỉ. `tenant_admin.ROLES` giờ là `("admin", "editor")`, và ràng
 * buộc CHECK trên `tenant_members`/`tenant_invitations` cũng vậy.
 */
export type MemberRole = "admin" | "editor";

/**
 * Vai của một thành viên, kể cả khi họ chưa có vai nào.
 *
 * `null` KHÔNG phải "chưa tải xong" hay "lỗi": nó là một trạng thái của máy
 * chủ — người này là thành viên đang hoạt động của tổ chức và chưa được cấp vai
 * nào ở tầng tenant. Kiểu riêng để nơi nào phải xử lý `null` thì trình biên
 * dịch bắt được, thay vì để nó lọt vào `ROLE_LABEL[...]` và hiện ra ô trống.
 */
export type MemberRoleOrNone = MemberRole | null;

/** Thứ tự quyền giảm dần. Dùng cho mọi ô chọn vai, để ba trang không tự xếp
 *  mỗi trang một kiểu. `null` không có mặt ở đây — nó là mục rỗng đứng đầu mỗi
 *  ô chọn, xem `NO_ROLE_LABEL`. */
export const ROLES: MemberRole[] = ["admin", "editor"];

/**
 * Tên vai bằng tiếng Việt.
 *
 * Ở một chỗ chứ không phải mỗi trang một bản: `editor` hiện là "Biên tập viên"
 * ở trang quản trị và "Người sửa" ở trang nhận lời mời thì người đọc phải tự
 * đoán xem đó có phải cùng một thứ không.
 */
export const ROLE_LABEL: Record<MemberRole, string> = {
  admin: "Quản trị viên",
  editor: "Biên tập viên",
};

/**
 * Nhãn cho "chưa có vai".
 *
 * Phải nói ra thành chữ. Một ô trống ở cột Vai đọc như dữ liệu bị thiếu, và
 * người quản trị sẽ đi cấp một vai để "sửa" nó — tức là giao diện vừa thuyết
 * phục họ nới quyền cho một người mà không ai yêu cầu.
 */
export const NO_ROLE_LABEL = "Chưa có vai";

/**
 * Nhãn của một vai có thể vắng. Dùng ở mọi chỗ hiển thị vai đọc từ máy chủ.
 *
 * `ROLE_LABEL[r]` trực tiếp thì `null` cho ra `undefined` và React vẽ ra một
 * chuỗi rỗng — cùng triệu chứng "ô trống" mà bản `owner|admin|member` từng gây
 * ra, chỉ khác nguyên nhân.
 */
export function roleLabel(role: MemberRoleOrNone | undefined): string {
  return role ? ROLE_LABEL[role] : NO_ROLE_LABEL;
}

/** Giá trị của mục "chưa có vai" trong `<select>`. DOM không giữ được `null`,
 *  nên chuỗi rỗng đi ra và `parseRole` đưa nó về `null` khi gửi đi. */
export const NO_ROLE_OPTION = "";

/** Giá trị thô từ một `<select>` → thứ máy chủ hiểu. */
export function parseRole(value: string): MemberRoleOrNone {
  return value === NO_ROLE_OPTION ? null : (value as MemberRole);
}

export interface Tenant {
  tenant_id: string;
  display_name: string;
  slug: string | null;
  is_active: boolean;
  created_at: string;
  created_by: string | null;
  deleted_at: string | null;
  /** Đếm sẵn ở máy chủ bằng một phép nối gộp, không phải N+1 từ giao diện. */
  member_count: number;
}

export interface TenantMember {
  tenant_id: string;
  user_id: string;
  username: string | null;
  email: string | null;
  role: MemberRoleOrNone;
  is_active: boolean;
  created_at: string;
}

/** Mã mời KHÔNG có ở đây — xem `InvitationCreated`. */
export interface TenantInvitation {
  invitation_id: string;
  tenant_id: string;
  email: string;
  role: MemberRoleOrNone;
  created_at: string;
  expires_at: string | null;
  accepted_at: string | null;
  revoked_at: string | null;
}

/**
 * Chỉ trả về MỘT lần, ở đúng lượt tạo.
 *
 * Cùng khuôn với `ApiKeyCreated` ở `api/integrations.ts`: máy chủ chỉ lưu băm
 * của mã mời và không endpoint nào đọc lại được. Tách kiểu để trình biên dịch
 * chặn mọi chỗ định hiển thị `token` từ danh sách.
 */
export interface InvitationCreated extends TenantInvitation {
  token: string;
  /**
   * Đường liên kết hoàn chỉnh để gửi cho người được mời — **do máy chủ dựng**.
   *
   * Trước đây trang quản trị tự ghép chuỗi này từ `window.location.origin` và
   * đường dẫn `/invitation`. Nghĩa là tên tuyến đó sống ở hai nơi cùng lúc, và
   * đổi tên ở một nơi sẽ giết mọi lời mời phát ra sau đó — hỏng lặng lẽ, hiện
   * ra vài ngày sau dưới dạng một trang trắng trên máy người lạ.
   *
   * Đừng ghép lại từ `token`. Máy chủ biết tên miền công khai đã được duyệt và
   * biết mình có đang nằm dưới đường dẫn con hay không; trình duyệt thì không
   * biết chắc cả hai.
   */
  accept_url: string;
  /**
   * Thư đã gửi đi được hay chưa. `false` là chuyện bình thường khi bản triển
   * khai chưa cấu hình SMTP — lời mời VẪN hợp lệ, chỉ là phải chép liên kết
   * gửi tay. Giao diện phải nói ra sự khác biệt này.
   */
  email_sent: boolean;
}

/**
 * Xem trước một lượt xoá sạch: bao nhiêu dòng ở mỗi bảng sẽ mất, và những gì
 * đang chặn.
 *
 * Chỉ số này là thứ đứng giữa người bấm nút và một lượt xoá không hồi được.
 * "Bạn có chắc không?" mà không kèm "3.860 mẫu, 63 lớp, 10 tài khoản" là một
 * câu hỏi người ta bấm qua theo phản xạ.
 */
export interface PurgePreview {
  tenant_id: string;
  display_name: string;
  deleted_at: string | null;
  row_counts: Record<string, number>;
  total_rows: number;
  has_ready_export: boolean;
  /** Lý do chưa xoá được, bằng tiếng Việt, do máy chủ soạn. Rỗng = xoá được. */
  blockers: string[];
  can_purge: boolean;
}

export interface TenantExport {
  export_id: string;
  tenant_id: string;
  status: "pending" | "running" | "ready" | "failed" | string;
  scope: "metadata" | "full" | string;
  size_bytes: number | null;
  row_counts: Record<string, number> | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  expires_at: string | null;
}

// --------------------------------------------------------------- tenants

/** Vòng nền tảng. */
export async function fetchTenants(includeDeleted = false): Promise<Tenant[]> {
  const res = await axiosClient.get<Tenant[]>(API_PREFIX, {
    params: { include_deleted: includeDeleted },
  });
  return res.data;
}

/** Vòng nền tảng. */
export async function createTenant(input: {
  tenant_id: string;
  display_name: string;
  slug?: string;
}): Promise<Tenant> {
  const res = await axiosClient.post<Tenant>(API_PREFIX, input);
  return res.data;
}

/** Vòng tenant. */
export async function fetchTenant(tenantId: string): Promise<Tenant> {
  const res = await axiosClient.get<Tenant>(`${API_PREFIX}/${tenantId}`);
  return res.data;
}

/** Vòng nền tảng. */
export async function updateTenant(
  tenantId: string,
  patch: { display_name?: string; is_active?: boolean },
): Promise<Tenant> {
  const res = await axiosClient.patch<Tenant>(`${API_PREFIX}/${tenantId}`, patch);
  return res.data;
}

/**
 * Vòng nền tảng. Xoá MỀM — tenant chuyển sang trạng thái đã xoá, dữ liệu còn
 * nguyên. Xoá thật là `purgeTenant`.
 */
export async function deleteTenant(tenantId: string): Promise<Tenant> {
  const res = await axiosClient.delete<Tenant>(`${API_PREFIX}/${tenantId}`);
  return res.data;
}

// --------------------------------------------------------------- members

/** Vòng tenant. */
export async function fetchMembers(tenantId: string): Promise<TenantMember[]> {
  const res = await axiosClient.get<TenantMember[]>(`${API_PREFIX}/${tenantId}/members`);
  return res.data;
}

/** Vòng NỀN TẢNG — xem chú thích đầu tệp về vì sao không phải vòng tenant. */
export async function addMember(
  tenantId: string,
  userId: string,
  role: MemberRoleOrNone = null,
): Promise<TenantMember> {
  const res = await axiosClient.post<TenantMember>(
    `${API_PREFIX}/${tenantId}/members`,
    { user_id: userId, role },
  );
  return res.data;
}

/** Vòng tenant. */
export async function updateMemberRole(
  tenantId: string,
  userId: string,
  role: MemberRoleOrNone,
): Promise<TenantMember> {
  const res = await axiosClient.patch<TenantMember>(
    `${API_PREFIX}/${tenantId}/members/${userId}`,
    { role },
  );
  return res.data;
}

/**
 * Vòng NỀN TẢNG. Chuyển **tổ chức nhà** của một tài khoản.
 *
 * Khác `addMember`, và khác biệt này quan trọng: `addMember` cho tài khoản một
 * chỗ ngồi trong tổ chức, còn hàm này quyết định **dữ liệu tương lai của họ đổ
 * vào đâu**. Một người có thể là thành viên của nhiều tổ chức nhưng chỉ có một
 * tổ chức nhà.
 *
 * Máy chủ ghi cả hai việc hoặc không ghi gì: nó tự thêm hàng thành viên nếu
 * thiếu. Không có phần đó thì tài khoản trỏ về một tổ chức mà nó không thuộc
 * về — đọc không thấy gì và ghi vào một nơi nó không phải thành viên.
 *
 * KHÔNG nằm dưới `/{tenant_id}/` vì đây không phải thao tác trên một tổ chức:
 * nó lấy một tài khoản ra khỏi tổ chức này và trỏ sang tổ chức kia.
 */
export async function setHomeTenant(
  userId: string,
  tenantId: string,
  // Cùng mặc định với máy chủ (`set_home_tenant(..., role=NO_ROLE)`): gắn
  // người vào tổ chức, không kèm vai. Cấp vai là một hành động riêng.
  role: MemberRoleOrNone = null,
): Promise<Record<string, unknown>> {
  const res = await axiosClient.put(`${API_PREFIX}/home-assignment/${userId}`, {
    tenant_id: tenantId,
    role,
  });
  return res.data;
}

/** Vòng tenant. */
export async function removeMember(tenantId: string, userId: string): Promise<void> {
  await axiosClient.delete(`${API_PREFIX}/${tenantId}/members/${userId}`);
}

// ----------------------------------------------------------- invitations

/** Vòng tenant. */
export async function fetchInvitations(
  tenantId: string,
  includeClosed = false,
): Promise<TenantInvitation[]> {
  const res = await axiosClient.get<TenantInvitation[]>(
    `${API_PREFIX}/${tenantId}/invitations`,
    { params: { include_closed: includeClosed } },
  );
  return res.data;
}

/** Vòng tenant. */
export async function createInvitation(
  tenantId: string,
  email: string,
  role: MemberRoleOrNone = null,
): Promise<InvitationCreated> {
  const res = await axiosClient.post<InvitationCreated>(
    `${API_PREFIX}/${tenantId}/invitations`,
    { email, role },
  );
  return res.data;
}

/**
 * Những gì một biểu mẫu đăng ký được phép hiện TRƯỚC khi tài khoản tồn tại.
 *
 * Cố ý mỏng: tên tổ chức và địa chỉ lời mời được phát cho, đủ để nói "bạn đang
 * gia nhập X". Không có danh sách thành viên, không có gì khác.
 */
export interface InvitationPreview {
  tenant_id: string;
  tenant_display_name: string;
  email: string;
  role: MemberRoleOrNone;
  expires_at: string | null;
}

/**
 * Đọc một lời mời từ mã của nó. **Không cần đăng nhập** — người nhận chưa có
 * tài khoản, đó là lý do có lời mời.
 *
 * POST chứ không phải GET, và khác biệt đó không phải chuyện thẩm mỹ: mã nằm
 * trong query string sẽ đọng lại ở nhật ký truy cập, lịch sử trình duyệt và
 * mọi proxy trên đường. Cùng lý do đó, đường liên kết mời mang mã trong
 * **fragment** (`#token=…`), thứ trình duyệt không bao giờ gửi lên máy chủ.
 *
 * Mã lạ và mã hết hạn đều nhận 404 giống hệt nhau, nên đừng cố phân biệt.
 */
export async function inspectInvitation(token: string): Promise<InvitationPreview> {
  const res = await axiosClient.post<InvitationPreview>(
    `${API_PREFIX}/invitations/inspect`,
    { token },
  );
  return res.data;
}

/** Vòng tenant. */
export async function revokeInvitation(
  tenantId: string,
  invitationId: string,
): Promise<void> {
  await axiosClient.delete(`${API_PREFIX}/${tenantId}/invitations/${invitationId}`);
}

// ----------------------------------------------------------------- đăng ký

/**
 * Kỳ hạn của tổ chức, đã được máy chủ tính sẵn.
 *
 * `days_left` là `null` khi gói KHÔNG có kỳ hạn — không phải `0`. Vẽ "còn 0
 * ngày" cho một gói vĩnh viễn là một câu sai đủ để người dùng gọi điện.
 *
 * `read_only` cũng do máy chủ tính. Giao diện không được tự suy từ
 * `billing_status`: danh sách trạng thái còn-ghi-được sống ở
 * `plans.WRITABLE_BILLING_STATUSES`, và mỗi màn hình tự chép lại nó là mỗi màn
 * hình một cách hiểu.
 */
export interface SubscriptionInfo {
  has_subscription: boolean;
  plan_code?: string;
  billing_status: string;
  auto_renew: boolean | null;
  current_period_start?: string | null;
  current_period_end: string | null;
  grace_until: string | null;
  trial_ends_at?: string | null;
  days_left: number | null;
  read_only: boolean;
}

/** Vòng tenant. */
export async function fetchSubscription(tenantId: string): Promise<SubscriptionInfo> {
  const res = await axiosClient.get<SubscriptionInfo>(
    `${API_PREFIX}/${tenantId}/subscription`,
  );
  return res.data;
}

/**
 * Vòng tenant. Bật/tắt tự gia hạn.
 *
 * Tắt KHÔNG đóng đăng ký ngay — kỳ đang chạy vẫn chạy hết. Giao diện phải nói
 * ra điều đó, nếu không người dùng tưởng mình vừa mất quyền ghi ngay lập tức.
 */
export async function setAutoRenew(
  tenantId: string,
  enabled: boolean,
): Promise<SubscriptionInfo> {
  const res = await axiosClient.post<SubscriptionInfo>(
    `${API_PREFIX}/${tenantId}/subscription/auto-renew`,
    { enabled },
  );
  return res.data;
}

// ---------------------------------------------------------- exports/purge

/** Vòng tenant. */
export async function fetchExports(tenantId: string): Promise<TenantExport[]> {
  const res = await axiosClient.get<TenantExport[]>(`${API_PREFIX}/${tenantId}/exports`);
  return res.data;
}

/**
 * Vòng tenant. Chạy bất đồng bộ; theo dõi bằng `fetchExports`.
 *
 * Máy chủ trả 202 chứ không phải 201, và khác biệt đó có nghĩa: chưa có gì tải
 * được. Đừng hiện nút Tải về cho tới khi `status === "ready"`.
 */
export async function requestExport(
  tenantId: string,
  scope: "metadata" | "full" = "metadata",
): Promise<TenantExport> {
  const res = await axiosClient.post<TenantExport>(
    `${API_PREFIX}/${tenantId}/exports`, null, { params: { scope } },
  );
  return res.data;
}

/** Đường tải trực tiếp; chỉ dùng khi bản xuất đã `ready`. */
export function exportDownloadUrl(tenantId: string, exportId: string): string {
  return `${API_PREFIX}/${tenantId}/exports/${exportId}/download`;
}

/** Vòng nền tảng. Chỉ ĐẾM, không xoá gì. */
export async function fetchPurgePreview(tenantId: string): Promise<PurgePreview> {
  const res = await axiosClient.get<PurgePreview>(`${API_PREFIX}/${tenantId}/purge-preview`);
  return res.data;
}

/**
 * Vòng nền tảng, **và cần chế độ sudo**. Không hồi được.
 *
 * `confirm_tenant_id` phải gõ đúng bằng `tenant_id`. Đó là một chuỗi chứ không
 * phải cờ true/false, và lý do nằm ở `tenant_lifecycle.purge_tenant`: một cờ
 * boolean bị vượt qua bởi mọi thứ, từ lỡ tay tới một script chạy sai biến.
 *
 * Phép kiểm ấy do BACKEND cưỡng chế. Hộp thoại ở giao diện chỉ là lớp lịch sự
 * — nó bị bỏ qua bằng một lệnh curl, phép kiểm ở máy chủ thì không.
 */
export async function purgeTenant(
  tenantId: string,
  confirmTenantId: string,
  reason = "",
): Promise<Record<string, unknown>> {
  const res = await axiosClient.post(`${API_PREFIX}/${tenantId}/purge`, {
    confirm_tenant_id: confirmTenantId,
    reason,
  });
  return res.data;
}
