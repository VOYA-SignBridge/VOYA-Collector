import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api/tenants", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/tenants")>()),
  fetchMyTenant: vi.fn(),
}));

import WorkingContextChip from "../WorkingContextChip";
import { I18nProvider } from "../../i18n";
import { fetchMyTenant } from "../../api/tenants";

function show() {
  window.localStorage.setItem("voya.lang", "vi");
  return render(
    <I18nProvider>
      <MemoryRouter>
        <WorkingContextChip />
      </MemoryRouter>
    </I18nProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("WorkingContextChip", () => {
  it("hiện TÊN tổ chức máy chủ đang lấy phạm vi và đường 'Đổi' tới /org", async () => {
    vi.mocked(fetchMyTenant).mockResolvedValue({ tenant_id: "truong-a", display_name: "Trường A" } as never);
    show();
    const chip = await screen.findByTestId("working-context");
    expect(chip).toHaveTextContent("Trường A");
    expect(chip).not.toHaveTextContent("truong-a");
    expect(screen.getByRole("link", { name: "Đổi" })).toHaveAttribute("href", "/org");
  });

  it("tổ chức cộng đồng hiện là 'Cộng đồng', không phải mã", async () => {
    vi.mocked(fetchMyTenant).mockResolvedValue({ tenant_id: "community", display_name: "Cộng đồng" } as never);
    show();
    expect(await screen.findByTestId("working-context")).toHaveTextContent("Cộng đồng");
  });

  it("API lỗi thì chip vắng mặt, thanh đầu trang không vỡ", async () => {
    vi.mocked(fetchMyTenant).mockRejectedValue(new Error("401"));
    show();
    await waitFor(() => expect(fetchMyTenant).toHaveBeenCalled());
    expect(screen.queryByTestId("working-context")).toBeNull();
  });
});
