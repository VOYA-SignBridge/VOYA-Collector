import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Ô soạn hội thoại mới ở kênh hỗ trợ.
 *
 * Vì sao tệp này tồn tại
 * -----------------------
 * Báo cáo người dùng ngày 16/08/2026: *"thiết kế cửa sổ hỗ trợ dở quá tôi còn
 * gửi tin nhắn không được nữa"*. Không phải chuyện thẩm mỹ — đó là một vòng
 * luẩn quẩn có thật:
 *
 *     mô tả rỗng  ->  !ready  ->  <textarea disabled>  ->  không gõ được mô tả
 *
 * `SupportPage` truyền `disabled={busy || !ready}` vào `Composer`, và `disabled`
 * khoá CẢ ô nhập. Vì `ready` đòi chính nội dung của ô đó, người dùng gõ được
 * tiêu đề (một `<input>` riêng) rồi phát hiện ô nhắn tin không nhận phím. Không
 * có lỗi nào hiện ra; màn hình chỉ đơn giản không phản ứng.
 *
 * Bài đầu tiên dưới đây là bài mà bản hỏng TRƯỢT. Ba bài còn lại canh phần
 * người dùng phàn nàn tiếp: cái nút mờ đi mà không nói vì sao.
 */

vi.mock("../../api/account", async () => {
  const actual = await vi.importActual<typeof import("../../api/account")>(
    "../../api/account",
  );
  return {
    ...actual,
    fetchTickets: vi.fn(),
    fetchTicket: vi.fn(),
    createTicket: vi.fn(),
    replyToTicket: vi.fn(),
    setTicketStatus: vi.fn(),
    fetchSupportStarters: vi.fn(),
  };
});

import * as api from "../../api/account";
import SupportPage from "../SupportPage";

const mocked = api as unknown as {
  fetchTickets: ReturnType<typeof vi.fn>;
  fetchSupportStarters: ReturnType<typeof vi.fn>;
  createTicket: ReturnType<typeof vi.fn>;
};

function renderPage() {
  return render(
    <MemoryRouter>
      <SupportPage />
    </MemoryRouter>,
  );
}

async function openComposer() {
  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: /Hội thoại mới/ }));
  return screen.getByLabelText("Nội dung lời nhắn");
}

beforeEach(() => {
  vi.clearAllMocks();
  mocked.fetchTickets.mockResolvedValue([]);
  mocked.fetchSupportStarters.mockResolvedValue({ starters: [], escape: "" });
});

describe("Ô soạn hội thoại mới", () => {
  it("GÕ ĐƯỢC mô tả ngay cả khi chưa đủ điều kiện gửi", async () => {
    // Bài mà bản hỏng trượt. `disabled` khoá việc gõ; điều kiện gửi thì không
    // được phép khoá việc gõ, vì chính việc gõ mới thoả được điều kiện.
    const box = await openComposer();
    expect(box).not.toBeDisabled();

    fireEvent.change(box, { target: { value: "Tôi không tải được mẫu" } });
    expect(box).toHaveValue("Tôi không tải được mẫu");
  });

  it("nói ra ĐÚNG thứ còn thiếu, không đọc cả hai điều kiện một lượt", async () => {
    const box = await openComposer();
    fireEvent.change(box, { target: { value: "Tôi không tải được mẫu nào cả" } });

    // Mô tả đã đủ dài, nên thứ còn thiếu là tiêu đề — và câu nhắc phải nói đúng
    // cái đó. Người đang bực vì một sự cố không tự đối chiếu hai vế với hai ô.
    expect(await screen.findByText(/Còn thiếu tiêu đề/)).toBeInTheDocument();
  });

  it("không mắng khi người dùng chưa gõ gì", async () => {
    // Hiện lý do ngay từ ô trống là chê trách trước khi người ta làm gì.
    await openComposer();
    expect(screen.queryByText(/Còn thiếu tiêu đề/)).not.toBeInTheDocument();
  });

  it("đủ tiêu đề và mô tả thì gửi được", async () => {
    mocked.createTicket.mockResolvedValue({
      ticket_id: "t1",
      subject: "Không tải được mẫu",
      category: "other",
      status: "open",
      created_at: "2026-08-16T00:00:00Z",
      updated_at: "2026-08-16T00:00:00Z",
      messages: [],
      bot_suggestions: [],
    });
    const box = await openComposer();

    fireEvent.change(screen.getByPlaceholderText("Bạn cần giúp việc gì?"), {
      target: { value: "Không tải được mẫu" },
    });
    fireEvent.change(box, { target: { value: "Bấm tải về thì không có gì xảy ra." } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi" }));

    await waitFor(() => expect(mocked.createTicket).toHaveBeenCalled());
  });

  it("danh sách điều kiện tick dần theo từng ô đã điền", async () => {
    // Người dùng thấy tiến độ của mình thay vì đoán xem cái nút mờ đang chờ gì.
    const box = await openComposer();
    expect(screen.getByText("Tiêu đề, từ 5 ký tự")).toBeInTheDocument();
    expect(screen.getByText("Mô tả, từ 10 ký tự")).toBeInTheDocument();

    fireEvent.change(box, { target: { value: "Một mô tả đủ dài để qua ngưỡng" } });
    // Dấu tick là ký hiệu chứ không chỉ là màu — người mù màu vẫn đọc được.
    expect(screen.getAllByText("✓").length).toBeGreaterThan(0);
  });
});
