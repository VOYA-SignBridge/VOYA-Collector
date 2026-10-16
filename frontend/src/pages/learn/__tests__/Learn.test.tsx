/**
 * Học ký hiệu — hai trang công khai, tối giản. Điều được khoá: tìm được, ba
 * miền là ba biến thể ngang nhau, video mở ở trang chính thức (không nhúng),
 * và hai nút nhỏ nối sang phần dữ liệu — không hơn.
 */
import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/learn", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../api/learn")>()),
  searchSigns: vi.fn(),
  fetchSign: vi.fn(),
}));

import LearnPage from "../LearnPage";
import SignPage from "../SignPage";
import { I18nProvider } from "../../../i18n";
import { fetchSign, searchSigns } from "../../../api/learn";

const DIA_CHI = {
  slug: "dia-chi", word: "địa chỉ", pos: "Danh từ", kind: "tu_thuong",
  definition: "Những thông tin cụ thể về chỗ ở.",
  variants: [
    { code: "D0001B", region: "bac", region_name: "Bắc", video_url: "https://qipedc.moet.gov.vn/videos/D0001B.mp4" },
    { code: "D0001N", region: "nam", region_name: "Nam", video_url: "https://qipedc.moet.gov.vn/videos/D0001N.mp4" },
  ],
  own: [{ class_uid: "c1", label: "Địa chỉ", region: "bac", dialect: "bac", sample_count: 12 }],
  own_sample_count: 12,
  attribution: "Từ vựng và định nghĩa: QIPEDC",
  dictionary_url: "https://qipedc.moet.gov.vn/dictionary",
};

function show(path: string) {
  window.localStorage.setItem("voya.lang", "vi");
  return render(
    <I18nProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/learn" element={<LearnPage />} />
          <Route path="/learn/:slug" element={<SignPage />} />
        </Routes>
      </MemoryRouter>
    </I18nProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(searchSigns).mockResolvedValue({ items: [DIA_CHI], total_words: 3206, attribution: "Từ vựng và định nghĩa: QIPEDC", dictionary_url: "" } as never);
  vi.mocked(fetchSign).mockResolvedValue(DIA_CHI as never);
});

describe("LearnPage", () => {
  it("gõ từ → tìm (không dấu), kết quả là liên kết tới thẻ, miền hiện thành chữ", async () => {
    show("/learn");
    fireEvent.change(screen.getByPlaceholderText(/Gõ một từ/), { target: { value: "dia chi" } });
    await waitFor(() => expect(searchSigns).toHaveBeenLastCalledWith("dia chi", "", 60));
    const link = await screen.findByRole("link", { name: /địa chỉ/ });
    expect(link).toHaveAttribute("href", "/learn/dia-chi");
    expect(link).toHaveTextContent("Bắc");
    expect(link).toHaveTextContent("Nam");
    expect(link).toHaveTextContent("thử được");
  });

  it("lọc theo miền đi qua URL (?vung=) và tới API", async () => {
    show("/learn");
    fireEvent.click(await screen.findByRole("button", { name: "Miền Trung" }));
    await waitFor(() => expect(searchSigns).toHaveBeenLastCalledWith("", "trung", 60));
    expect(screen.getByRole("button", { name: "Miền Trung" })).toHaveAttribute("aria-pressed", "true");
  });

  it("ghi nguồn QIPEDC ở cuối trang", async () => {
    show("/learn");
    expect(await screen.findByText(/QIPEDC/)).toBeInTheDocument();
  });
});

describe("SignPage", () => {
  it("video nhúng thẳng; nhiều miền thì một hàng nút đổi video, vẫn có liên kết gốc", async () => {
    // Chủ dự án chốt nhúng 15/09/2026 (máy chủ QIPEDC hỗ trợ Range, không chặn Referer).
    show("/learn/dia-chi");
    const video = await screen.findByTestId("sign-video");
    expect(video).toHaveAttribute("src", "https://qipedc.moet.gov.vn/videos/D0001B.mp4");
    expect(video).toHaveAttribute("controls");
    expect(screen.getByRole("tab", { name: "Bắc" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: "Nam" }));
    expect(screen.getByTestId("sign-video")).toHaveAttribute("src", expect.stringMatching(/videos\/.+\.mp4$/));
    expect(screen.getByTestId("sign-video").getAttribute("src")).not.toBe("https://qipedc.moet.gov.vn/videos/D0001B.mp4");
    expect(screen.getByRole("link", { name: /Mở video gốc/ })).toHaveAttribute("target", "_blank");
    expect(screen.getByText(/Cả ba đều đúng/)).toBeInTheDocument();
  });

  it("có mẫu → 'Thử ký với camera' + 'Đóng góp mẫu'; nghĩa hiện đầy đủ", async () => {
    show("/learn/dia-chi");
    expect(await screen.findByRole("link", { name: /Thử ký với camera/ })).toHaveAttribute("href", "/realtime");
    expect(screen.getByRole("link", { name: /Đóng góp mẫu/ })).toHaveAttribute("href", "/upload");
    expect(screen.getByText("Những thông tin cụ thể về chỗ ở.")).toBeInTheDocument();
  });

  it("chưa có mẫu → không có nút thử, nói rõ và mời đóng góp; thiếu nghĩa thì nói thiếu", async () => {
    vi.mocked(fetchSign).mockResolvedValue({ ...DIA_CHI, own: [], own_sample_count: 0, definition: "" } as never);
    show("/learn/dia-chi");
    await screen.findByRole("heading", { name: "địa chỉ" });
    expect(screen.queryByRole("link", { name: /Thử ký với camera/ })).toBeNull();
    expect(screen.getByText(/chưa có mẫu cho ký hiệu này/)).toBeInTheDocument();
    expect(screen.getByText(/chưa có phần giải nghĩa/)).toBeInTheDocument();
  });

  it("404 → câu tiếng Việt, không trang trắng", async () => {
    vi.mocked(fetchSign).mockRejectedValue({ response: { status: 404 } });
    show("/learn/khong-co");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Không có ký hiệu này/);
  });
});
