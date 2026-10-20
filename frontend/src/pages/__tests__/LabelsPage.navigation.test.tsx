import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import LabelsPage from "../LabelsPage";
import * as datasetApi from "../../api/dataset";
import * as useAuthHook from "../../hooks/useAuth";

/**
 * Integration: nút "Chi tiết" ở Thư viện nhãn (Phase 1) phải điều hướng
 * sang màn hình Chi tiết nhãn (Phase 2) — thay cho alert placeholder cũ.
 */

vi.mock("../../api/dataset", () => ({
  getLabels: vi.fn(),
  getClassesList: vi.fn(),
  getClassesStats: vi.fn(),
  updateClass: vi.fn(),
  deleteClass: vi.fn(),
  registerClass: vi.fn(),
}));

vi.mock("../../hooks/useAuth", () => ({ useAuth: vi.fn() }));

const mockNavigate = vi.fn();
// `Link` too — PageHeader's breadcrumb renders one, and a partial mock of this
// module throws rather than falling back to the real export.
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  Link: ({ to, children }: { to: string; children: React.ReactNode }) => (
    <a href={to}>{children}</a>
  ),
}));

describe("LabelsPage → LabelDetailPage — điều hướng Chi tiết (Phase 1 → Phase 2)", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(useAuthHook.useAuth).mockReturnValue({
      loading: false,
      isAdmin: true,
      user: { id: "1", username: "admin" },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(datasetApi.getClassesList).mockResolvedValue({
      ok: true,
      data: {
        count: 1,
        items: [
          {
            class_uid: "7246af3c-d9b8-4919-afff-9b21ad3f8d93",
            class_idx: 1,
            slug: "hello",
            label_original: "Xin chào",
            language: "vn",
            dialect: "common",
            is_common_language: true,
            is_common_global: false,
          },
        ],
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(datasetApi.getClassesStats).mockResolvedValue({
      ok: true,
      data: {
        total_classes: 1,
        max_count: 5,
        distribution: [{ class_uid: "7246af3c-d9b8-4919-afff-9b21ad3f8d93", count: 5, samples_count: 25 }],
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(datasetApi.getLabels).mockResolvedValue({
      ok: true,
      data: [{ class_idx: 1, label_original: "Xin chào", slug: "hello" }],
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);
  });

  it("bấm 'Chi tiết' → navigate tới /labels/{class_uid}, KHÔNG còn alert", async () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    render(<LabelsPage />);
    await waitFor(() => expect(screen.getByText("Xin chào")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Chi tiết")[0]);

    // Trang chi tiết đã chuyển từ /admin/labels/:id sang /labels/:id (mở cho
    // user thường); /admin/labels/:id chỉ còn là redirect back-compat.
    expect(mockNavigate).toHaveBeenCalledWith(
      "/labels/7246af3c-d9b8-4919-afff-9b21ad3f8d93",
    );
    expect(alertSpy).not.toHaveBeenCalled();
  });

  it("class thiếu class_uid (dữ liệu cũ) → fallback dùng class_idx trong URL", async () => {
    vi.mocked(datasetApi.getClassesList).mockResolvedValue({
      ok: true,
      data: {
        count: 1,
        items: [
          {
            class_uid: "",
            class_idx: 7,
            slug: "legacy",
            label_original: "Nhãn cũ",
            language: "vn",
            dialect: "common",
          },
        ],
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);
    vi.mocked(datasetApi.getClassesStats).mockResolvedValue({
      ok: true,
      data: { total_classes: 1, max_count: 5, distribution: [] },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    render(<LabelsPage />);
    await waitFor(() => expect(screen.getByText("Nhãn cũ")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Chi tiết")[0]);
    expect(mockNavigate).toHaveBeenCalledWith("/labels/7");
  });
});
