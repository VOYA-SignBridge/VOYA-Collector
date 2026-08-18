/**
 * Workspace và Project — hai tầng phạm vi dưới tổ chức.
 *
 * Vì sao module này ra đời sau lược đồ khá lâu
 * ---------------------------------------------
 * Hai bảng `workspaces` và `projects` đã có từ bản v5 của mô hình phân quyền,
 * cùng 13 vai dựng sẵn trải trên bốn miền. Nhưng cho tới trước đợt này backend
 * **không có endpoint nào** cho chúng — `/openapi.json` cho 0 đường chứa
 * `workspace` hay `project`. Vì thế mọi phát biểu trong tài liệu phải kèm mệnh
 * đề "hai cấp dưới có cấu trúc dữ liệu, chưa có bề mặt vận hành".
 *
 * Module này là mặt giao diện của `routers/workspaces.py`.
 *
 * Hai giới hạn PHẢI hiển thị, không được giấu
 * --------------------------------------------
 * `summary` trả về hai cờ mà trang bắt buộc phải in ra:
 *
 *   `data_carries_project_id: false` — `samples`/`classes`/`training_jobs` vẫn
 *       chỉ mang `tenant_id`. Tạo project KHÔNG làm dữ liệu tự phân về project.
 *   `authz_mode: "shadow"` — Casbin quan sát, hệ cũ hai phạm vi quyết định. Một
 *       vai cấp workspace ghi đúng dữ liệu nhưng chưa đổi được kết quả kiểm quyền.
 *
 * Một trang tạo được workspace mà không nói hai điều này sẽ được đọc thành
 * "phân quyền bốn cấp đã chạy" — đúng điều không được để xảy ra trong tài liệu.
 */

import axiosClient from "./axiosClient";

const API_PREFIX = "/api/v1/workspaces";

export type ContainerStatus = "ACTIVE" | "ARCHIVED" | "DELETED";

export interface Workspace {
  workspace_id: string;
  name: string;
  description: string;
  status: ContainerStatus;
  is_default: boolean;
  created_at: string | null;
  archived_at: string | null;
  project_count: number;
  member_count: number;
}

export interface Project {
  project_id: string;
  workspace_id: string;
  name: string;
  description: string;
  status: ContainerStatus;
  is_default: boolean;
  created_at: string | null;
  archived_at: string | null;
  member_count: number;
}

export interface ScopeRole {
  role_id: string;
  role_code: string;
  role_name: string | null;
  description: string | null;
  scope_level: "WORKSPACE" | "PROJECT";
}

export interface ScopeMember {
  assignment_id: string;
  user_id: string;
  username: string | null;
  email: string | null;
  role_code: string;
  role_name: string | null;
  scope_level: "WORKSPACE" | "PROJECT";
  membership_id: string;
  workspace_id: string;
  project_id: string | null;
  assigned_at: string | null;
}

export interface ScopeSummary {
  tenant_id: string;
  workspaces: number;
  projects: number;
  workspace_members: number;
  project_members: number;
  /** `false` hôm nay — xem chú thích đầu tệp. */
  data_carries_project_id: boolean;
  /** `"shadow"` hôm nay — Casbin chưa phải bên quyết định. */
  authz_mode: string;
}

export const getScopeSummary = async (): Promise<ScopeSummary> => {
  const res = await axiosClient.get<ScopeSummary>(`${API_PREFIX}/summary`);
  return res.data;
};

export const listWorkspaces = async (includeArchived = false): Promise<Workspace[]> => {
  const res = await axiosClient.get<Workspace[]>(API_PREFIX, {
    params: { include_archived: includeArchived },
  });
  return res.data;
};

export const createWorkspace = async (
  name: string,
  description = "",
): Promise<Workspace> => {
  const res = await axiosClient.post<Workspace>(API_PREFIX, { name, description });
  return res.data;
};

export const updateWorkspace = async (
  workspaceId: string,
  patch: { name?: string; description?: string; status?: ContainerStatus },
): Promise<Workspace> => {
  const res = await axiosClient.patch<Workspace>(
    `${API_PREFIX}/${encodeURIComponent(workspaceId)}`,
    patch,
  );
  return res.data;
};

export const listProjects = async (
  workspaceId: string,
  includeArchived = false,
): Promise<Project[]> => {
  const res = await axiosClient.get<Project[]>(
    `${API_PREFIX}/${encodeURIComponent(workspaceId)}/projects`,
    { params: { include_archived: includeArchived } },
  );
  return res.data;
};

export const createProject = async (
  workspaceId: string,
  name: string,
  description = "",
): Promise<Project> => {
  const res = await axiosClient.post<Project>(
    `${API_PREFIX}/${encodeURIComponent(workspaceId)}/projects`,
    { name, description },
  );
  return res.data;
};

export const updateProject = async (
  workspaceId: string,
  projectId: string,
  patch: { name?: string; description?: string; status?: ContainerStatus },
): Promise<Project> => {
  const res = await axiosClient.patch<Project>(
    `${API_PREFIX}/${encodeURIComponent(workspaceId)}/projects/${encodeURIComponent(projectId)}`,
    patch,
  );
  return res.data;
};

export const listScopeRoles = async (
  scopeLevel: "WORKSPACE" | "PROJECT",
): Promise<ScopeRole[]> => {
  const res = await axiosClient.get<ScopeRole[]>(`${API_PREFIX}/roles`, {
    params: { scope_level: scopeLevel },
  });
  return res.data;
};

export const listScopeMembers = async (
  workspaceId: string,
  projectId?: string | null,
): Promise<ScopeMember[]> => {
  const res = await axiosClient.get<ScopeMember[]>(
    `${API_PREFIX}/${encodeURIComponent(workspaceId)}/members`,
    { params: projectId ? { project_id: projectId } : {} },
  );
  return res.data;
};

export const grantScopeRole = async (
  workspaceId: string,
  payload: { user_id: string; role_code: string; project_id?: string | null },
): Promise<ScopeMember> => {
  const res = await axiosClient.post<ScopeMember>(
    `${API_PREFIX}/${encodeURIComponent(workspaceId)}/members`,
    payload,
  );
  return res.data;
};

/** Một ô trong bảng cấp phát. `allocated === null` nghĩa là KHÔNG GIỚI HẠN. */
export interface AllocationCell {
  allocated: number | null;
  note: string;
  updated_at: string | null;
}

export interface ProjectAllocations {
  project_id: string;
  name: string;
  status: ContainerStatus;
  is_default: boolean;
  allocations: Record<string, AllocationCell>;
}

export interface AllocationTable {
  workspace_id: string;
  metrics: string[];
  /** Trần của gói cước. `null` = không giới hạn. */
  tenant_ceiling: Record<string, number | null>;
  allocated_total: Record<string, number>;
  remaining: Record<string, number | null>;
  projects: ProjectAllocations[];
}

export const listAllocations = async (workspaceId: string): Promise<AllocationTable> => {
  const res = await axiosClient.get<AllocationTable>(
    `${API_PREFIX}/${encodeURIComponent(workspaceId)}/allocations`,
  );
  return res.data;
};

export const setAllocation = async (
  workspaceId: string,
  payload: { project_id: string; metric: string; allocated: number | null; note?: string },
): Promise<{ project_id: string; metric: string; allocated: number | null }> => {
  const res = await axiosClient.put(
    `${API_PREFIX}/${encodeURIComponent(workspaceId)}/allocations`,
    payload,
  );
  return res.data;
};

export const revokeScopeRole = async (
  workspaceId: string,
  assignmentId: string,
  reason = "",
): Promise<{ assignment_id: string; revoked: boolean }> => {
  /* `axios.delete` gửi thân yêu cầu qua `data`, không phải tham số thứ hai —
     một khác biệt đã từng làm lý do thu hồi im lặng không tới máy chủ. */
  const res = await axiosClient.delete<{ assignment_id: string; revoked: boolean }>(
    `${API_PREFIX}/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(assignmentId)}`,
    { data: { reason } },
  );
  return res.data;
};
