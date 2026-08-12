/**
 * Trung tâm thông báo và chuông.
 *
 * Hai tính chất được ghim kỹ nhất, vì cả hai đều là chỗ giao diện *trông như*
 * chạy được mà vẫn sai:
 *
 *  1. Mở một thông báo phải đánh dấu đã đọc NGAY. Nếu không, số trên chuông
 *     không bao giờ về 0 và người dùng học cách bỏ qua nó.
 *  2. Chuông phải mang con số vào `aria-label`. Chấm tròn đỏ không được trình
 *     đọc màn hình đọc ra, nên nhãn là chỗ DUY NHẤT người khiếm thị biết có gì
 *     mới.
 */

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api/account", async () => {
  const actual = await vi.importActual<typeof import("../../api/account")>(
    "../../api/account",
  );
  return {
    ...actual,
    fetchNotifications: vi.fn(),
    fetchUnreadCount: vi.fn(),
    markRead: vi.fn(),
    markAllRead: vi.fn(),
  };
});

import * as api from "../../api/account";
import NotificationBell from "../../components/NotificationBell";
import NotificationsPage from "../NotificationsPage";

const mocked = api as unknown as {
  fetchNotifications: ReturnType<typeof vi.fn>;
  fetchUnreadCount: ReturnType<typeof vi.fn>;
  markRead: ReturnType<typeof vi.fn>;
  markAllRead: ReturnType<typeof vi.fn>;
};

function makeNotification(over: Partial<api.AppNotification> = {}): api.AppNotification {
  return {
    notification_id: "n1",
    kind: "security",
    title: "Đăng nhập từ thiết bị lạ",
    body: "Máy tính, Cần Thơ",
    link: null,
    severity: "warning",
    read_at: null,
    created_at: "2026-08-10T02:00:00Z",
    ...over,
  };
}

const renderPage = () =>
  render(
    <MemoryRouter>
      <NotificationsPage />
    </MemoryRouter>,
  );

beforeEach(() => {
  vi.clearAllMocks();
  mocked.markRead.mockResolvedValue(1);
  mocked.markAllRead.mockResolvedValue(1);
});

describe("NotificationsPage", () => {
  it("hiện danh sách và số chưa đọc", async () => {
    mocked.fetchNotifications.mockResolvedValue({
      items: [makeNotification()],
      unread: 1,
    });
    renderPage();

    expect(await screen.findByText("Đăng nhập từ thiết bị lạ")).toBeInTheDocument();
    expect(screen.getByText("1 thông báo chưa đọc")).toBeInTheDocument();
  });

  it("nói rõ khi đã đọc hết thay vì để trống", async () => {
    mocked.fetchNotifications.mockResolvedValue({ items: [], unread: 0 });
    renderPage();

    expect(await screen.findByText("Bạn đã đọc hết")).toBeInTheDocument();
    expect(screen.getByText("Chưa có thông báo nào")).toBeInTheDocument();
  });

  it("mở một thông báo thì đánh dấu đã đọc ngay", async () => {
    mocked.fetchNotifications.mockResolvedValue({
      items: [makeNotification()],
      unread: 1,
    });
    renderPage();

    fireEvent.click(await screen.findByText("Đăng nhập từ thiết bị lạ"));
    await waitFor(() => expect(mocked.markRead).toHaveBeenCalledWith(["n1"]));
    // Số giảm ngay tại chỗ, không chờ lượt tải lại: người vừa bấm phải thấy
    // màn hình phản hồi.
    expect(screen.getByText("Bạn đã đọc hết")).toBeInTheDocument();
  });

  it("KHÔNG gọi lại khi mở một thông báo đã đọc", async () => {
    mocked.fetchNotifications.mockResolvedValue({
      items: [makeNotification({ read_at: "2026-08-10T03:00:00Z" })],
      unread: 0,
    });
    renderPage();

    fireEvent.click(await screen.findByText("Đăng nhập từ thiết bị lạ"));
    expect(mocked.markRead).not.toHaveBeenCalled();
  });

  it("đánh dấu tất cả đã đọc", async () => {
    mocked.fetchNotifications.mockResolvedValue({
      items: [makeNotification()],
      unread: 1,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /Đánh dấu tất cả đã đọc/ }),);
    expect(mocked.markAllRead).toHaveBeenCalled();
  });

  it("nút đánh dấu tất cả biến mất khi không còn gì chưa đọc", async () => {
    mocked.fetchNotifications.mockResolvedValue({ items: [], unread: 0 });
    renderPage();

    await screen.findByText("Bạn đã đọc hết");
    expect(
      screen.queryByRole("button", { name: /Đánh dấu tất cả đã đọc/ }),
    ).not.toBeInTheDocument();
  });

  it("báo lỗi bằng role=alert chứ không im lặng", async () => {
    mocked.fetchNotifications.mockRejectedValue(new Error("mạng hỏng"));
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Không tải được thông báo/,
    );
  });
});

describe("NotificationBell", () => {
  const renderBell = () =>
    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>,
    );

  it("đưa số chưa đọc vào nhãn cho trình đọc màn hình", async () => {
    mocked.fetchUnreadCount.mockResolvedValue(3);
    renderBell();

    expect(
      await screen.findByRole("link", { name: "Thông báo, 3 chưa đọc" }),
    ).toBeInTheDocument();
  });

  it("nhãn gọn khi không có gì mới", async () => {
    mocked.fetchUnreadCount.mockResolvedValue(0);
    renderBell();

    expect(await screen.findByRole("link", { name: "Thông báo" })).toBeInTheDocument();
  });

  it("chặn trên ở 99+ để không phá bố cục thanh điều hướng", async () => {
    mocked.fetchUnreadCount.mockResolvedValue(1234);
    renderBell();

    expect(await screen.findByText("99+")).toBeInTheDocument();
  });

  it("lỗi mạng không làm hỏng thanh điều hướng", async () => {
    mocked.fetchUnreadCount.mockRejectedValue(new Error("401"));
    renderBell();

    expect(await screen.findByRole("link", { name: "Thông báo" })).toBeInTheDocument();
  });
});
