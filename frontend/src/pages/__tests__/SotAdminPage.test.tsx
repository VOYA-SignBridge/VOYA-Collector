/**
 * Trang "Dữ liệu chuẩn & đồng bộ" — SOT-02 và bố cục Đợt 2.
 *
 * Ba điều được khoá: (1) lỗi tải tổng quan GIỮ trên trang, không chỉ toast;
 * (2) kết luận một câu đứng đầu và đổi đúng theo trạng thái kho; (3) chi tiết
 * kỹ thuật (fingerprint, sha256, schema) nằm sau một mục gấp, không chắn trước.
 */
import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api/sot", () => ({
  getSotOverview: vi.fn(),
  getSotRemote: vi.fn(),
  getSotSchema: vi.fn(),
  runSotVerify: vi.fn(),
  registerSotMachine: vi.fn(),
  revokeSotMachine: vi.fn(),
}));

import SotAdminPage from "../SotAdminPage";
import { I18nProvider } from "../../i18n";
import { ToastProvider } from "../../hooks/useToast";
import { getSotOverview, getSotRemote, getSotSchema, runSotVerify } from "../../api/sot";

const OVERVIEW = {
  machines: [
    { name: "SignBridge_SE", fingerprint: "ab12cd34", public_key: "k", source: "committed", revocable: false },
    { name: "may-lab", fingerprint: "ef56", public_key: "k2", source: "db", revocable: true, added_by: "admin", added_at: "2026-09-01T00:00:00Z" },
  ],
  db_counts: { classes: 63, samples: 3864, raw_uploads: 1 },
  schema_version: 8,
  this_machine: { is_writer: false, fingerprint: null, public_key: null },
};
const PUBLISHED = { available: true, published: true, version: "Ver5_06082026", trusted: true, signed_by: "desktop-admin", files: [{ name: "samples.csv", sha256: "0123456789abcdef0123", rows: 3860 }] };

function show() {
  window.localStorage.setItem("voya.lang", "vi");
  return render(
    <I18nProvider>
      <ToastProvider>
        <SotAdminPage />
      </ToastProvider>
    </I18nProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getSotOverview).mockResolvedValue(OVERVIEW as never);
  vi.mocked(getSotRemote).mockResolvedValue(PUBLISHED as never);
  vi.mocked(getSotSchema).mockResolvedValue({ required_columns: { samples: ["sample_uid", "class_uid"] } } as never);
});

describe("SotAdminPage", () => {
  it("có bản công bố từ máy tin cậy nhưng chưa kiểm tra → kết luận 'chưa kiểm tra' + việc cần làm", async () => {
    show();
    const box = await screen.findByTestId("sot-conclusion");
    expect(box).toHaveAttribute("data-kind", "unchecked");
    expect(box).toHaveTextContent(/CHƯA kiểm tra toàn vẹn/);
    expect(box).toHaveTextContent(/Việc cần làm/);
  });

  it("bấm kiểm tra → đạt → kết luận đổi và có thời điểm kiểm tra", async () => {
    vi.mocked(runSotVerify).mockResolvedValue({ ok: true, version: "Ver5_06082026" } as never);
    show();
    await screen.findByTestId("sot-conclusion");
    fireEvent.click(screen.getByRole("button", { name: "Kiểm tra bản dữ liệu chuẩn" }));
    await waitFor(() => expect(screen.getByTestId("sot-conclusion")).toHaveAttribute("data-kind", "verified"));
    expect(screen.getByTestId("sot-conclusion")).toHaveTextContent(/Kiểm tra lúc/);
  });

  it("kho không kết nối được → nói đúng như vậy, KHÔNG nói 'chưa công bố'", async () => {
    vi.mocked(getSotRemote).mockResolvedValue({ available: false } as never);
    show();
    const box = await screen.findByTestId("sot-conclusion");
    expect(box).toHaveAttribute("data-kind", "unreachable");
    expect(box).not.toHaveTextContent(/chưa có bản/);
  });

  it("lỗi tải tổng quan GIỮ trên trang với nút Thử lại — SOT-02", async () => {
    vi.mocked(getSotOverview).mockRejectedValueOnce(new Error("boom"));
    show();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Không tải được thông tin máy và dữ liệu/);
    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    expect((await screen.findAllByText("may-lab")).length).toBeGreaterThan(0);
  });

  it("nói bằng chữ thường: 'Có quyền công bố / Chỉ đọc', 'mẫu · nhãn · tệp ghi hình gốc'", async () => {
    show();
    expect(await screen.findByText("Chỉ đọc")).toBeInTheDocument();
    expect(screen.getByText("3.864")).toBeInTheDocument();
    expect(screen.queryByText(/raw_uploads/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Read-only/)).not.toBeInTheDocument();
  });

  it("máy khai báo trong mã nguồn không có nút thu hồi; máy đăng ký qua giao diện thì có", async () => {
    show();
    await screen.findAllByText("SignBridge_SE");
    expect(screen.getAllByRole("button", { name: "Thu hồi quyền" })).toHaveLength(1);
  });

  it("chi tiết kỹ thuật (sha256, fingerprint) nằm sau mục gấp 'Chi tiết kỹ thuật'", async () => {
    show();
    await screen.findAllByText("SignBridge_SE");
    const details = screen.getByText("Chi tiết kỹ thuật").closest("details") as HTMLDetailsElement;
    expect(details).not.toHaveAttribute("open");
    expect(details).toHaveTextContent("0123456789abcdef");
    expect(details).toHaveTextContent("ab12cd34");
  });
});
