import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import LabelDetailPage from "../LabelDetailPage";
import * as api from "../../api/labelDetail";
import * as useAuthHook from "../../hooks/useAuth";
import { ECO_MODE_KEY } from "../../components/viewer/useRenderTier";

vi.mock("../../api/labelDetail", async () => {
  const actual = await vi.importActual<typeof api>("../../api/labelDetail");
  return {
    ...actual,
    getLabelSessions: vi.fn(),
    getSessionFrames: vi.fn(),
    getPreviewStatus: vi.fn(),
  };
});

vi.mock("../../hooks/useAuth", () => ({ useAuth: vi.fn() }));

vi.mock("react-router-dom", () => ({
  useParams: () => ({ id: "cls123" }),
  Link: ({ to, children }: { to: string; children: React.ReactNode }) => (
    <a href={to}>{children}</a>
  ),
}));

// Player 3D kéo theo three.js + WebGL — không chạy được trong jsdom, stub lại.
vi.mock("../../components/viewer/Hand3DPlayer", () => ({
  default: () => <div data-testid="hand-3d-stub" />,
}));

const SESSIONS = {
  class_uid: "cls123",
  label_original: "Xin chào",
  slug: "xin-chao",
  language: "vn",
  dialect: "mienTay",
  count: 2,
  sessions: [
    {
      session_id: "sess-2",
      user_id: "nguoi-b",
      username: "Người B",
      created_at: "2026-07-02T00:00:00Z",
      sample_count: 5,
      original_sample_uid: "uid-2",
      seq_len: 60,
      fps: 15,
      source_type: "camera",
      has_preview: true,
      // Permission is server-computed per session (owner OR admin). The default
      // mock represents a manager view — the "Tải .npz" button is gated on this.
      is_owner: true,
      can_manage: true,
    },
    {
      session_id: "sess-1",
      user_id: "nguoi-a",
      username: "Người A",
      created_at: "2026-07-01T00:00:00Z",
      sample_count: 5,
      original_sample_uid: "uid-1",
      seq_len: 60,
      fps: 15,
      source_type: "camera",
      has_preview: false,
      is_owner: true,
      can_manage: true,
    },
  ],
};

const FRAMES = {
  class_uid: "cls123",
  session_id: "sess-2",
  sample_uid: "uid-2",
  frames: 60,
  dim: 126,
  fps: 15,
  sequence: Array.from({ length: 60 }, () => new Array(126).fill(0.5)),
};

function setHardware(cores: number) {
  Object.defineProperty(navigator, "hardwareConcurrency", {
    value: cores,
    configurable: true,
  });
  Object.defineProperty(navigator, "deviceMemory", {
    value: 8,
    configurable: true,
  });
}

describe("LabelDetailPage — màn hình Chi tiết nhãn (Phase 2)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    setHardware(2); // mặc định: máy trung bình → Tier 2D (deterministic, không cần WebGL)

    vi.mocked(useAuthHook.useAuth).mockReturnValue({
      loading: false,
      isAdmin: true,
      user: { id: "1", username: "admin" },
      login: vi.fn(),
      logout: vi.fn(),
      checkStatus: vi.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(api.getLabelSessions).mockResolvedValue(SESSIONS);
    vi.mocked(api.getSessionFrames).mockResolvedValue(FRAMES);
    vi.mocked(api.getPreviewStatus).mockResolvedValue("ready");
  });

  it("hiển thị tên nhãn + danh sách lần quay, session mới nhất được chọn sẵn", async () => {
    render(<LabelDetailPage />);
    expect((await screen.findAllByText("Xin chào")).length).toBeGreaterThan(0);
    expect(screen.getByText(/Lần quay 2/)).toBeInTheDocument();
    expect(screen.getByText(/Lần quay 1/)).toBeInTheDocument();
    expect(screen.getByText(/Người đóng góp: Người B/)).toBeInTheDocument();
    // Tier 2D: canvas skeleton được render với dữ liệu frames
    expect(await screen.findByTestId("skeleton-2d-canvas")).toBeInTheDocument();
    expect(api.getSessionFrames).toHaveBeenCalledWith("cls123", "sess-2");
  });

  it("API sập (500) → hiện lỗi + nút Thử lại gọi API lần nữa", async () => {
    vi.mocked(api.getLabelSessions).mockRejectedValueOnce(
      Object.assign(new Error("boom"), { userMessage: "Hệ thống không thể kết nối, vui lòng thử lại sau." }),
    );
    render(<LabelDetailPage />);
    expect(
      await screen.findByText("Hệ thống không thể kết nối, vui lòng thử lại sau."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Thử lại/ }));
    expect((await screen.findAllByText("Xin chào")).length).toBeGreaterThan(0);
    expect(api.getLabelSessions).toHaveBeenCalledTimes(2);
  });

  it("chọn lần quay khác → tải frames của session đó", async () => {
    render(<LabelDetailPage />);
    await screen.findByTestId("skeleton-2d-canvas");
    fireEvent.click(screen.getByTestId("session-card-sess-1"));
    await waitFor(() =>
      expect(api.getSessionFrames).toHaveBeenCalledWith("cls123", "sess-1"),
    );
  });

  it("Eco mode → Tier video: hỏi server preview, KHÔNG tải frames", async () => {
    localStorage.setItem(ECO_MODE_KEY, "1");
    render(<LabelDetailPage />);
    await screen.findAllByText("Xin chào");
    const video = await screen.findByTestId("preview-video");
    expect(video).toHaveAttribute("src", expect.stringContaining("/preview.mp4"));
    expect(api.getPreviewStatus).toHaveBeenCalledWith("cls123", "sess-2");
    expect(api.getSessionFrames).not.toHaveBeenCalled();
  });

  it("server đang render (202) → hiện trạng thái chờ thay vì video", async () => {
    localStorage.setItem(ECO_MODE_KEY, "1");
    vi.mocked(api.getPreviewStatus).mockResolvedValue("rendering");
    render(<LabelDetailPage />);
    expect(await screen.findByTestId("preview-rendering")).toBeInTheDocument();
    expect(screen.queryByTestId("preview-video")).not.toBeInTheDocument();
  });

  it("Người quản lý (can_manage) thấy nút Tải .npz; người thường thì không", async () => {
    // Mặc định mock: cả 2 session can_manage=true (admin/chủ sở hữu) → 2 nút.
    const { unmount } = render(<LabelDetailPage />);
    expect((await screen.findAllByText("Tải .npz")).length).toBe(2);
    unmount();

    // Người thường không sở hữu: server trả can_manage=false cho mọi session →
    // nút Tải .npz không hiển thị (quyền do server quyết định, không phải client).
    vi.mocked(api.getLabelSessions).mockResolvedValue({
      ...SESSIONS,
      sessions: SESSIONS.sessions.map((s) => ({ ...s, is_owner: false, can_manage: false })),
    });
    vi.mocked(useAuthHook.useAuth).mockReturnValue({
      loading: false,
      isAdmin: false,
      user: { id: "2", username: "member" },
      login: vi.fn(),
      logout: vi.fn(),
      checkStatus: vi.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);
    render(<LabelDetailPage />);
    await screen.findAllByText("Xin chào");
    expect(screen.queryByText("Tải .npz")).not.toBeInTheDocument();
  });

  it("nhãn không có lần quay nào → hiện trạng thái rỗng", async () => {
    vi.mocked(api.getLabelSessions).mockResolvedValue({ ...SESSIONS, count: 0, sessions: [] });
    render(<LabelDetailPage />);
    expect(await screen.findByText("Chưa có lần quay nào")).toBeInTheDocument();
  });

  it("polling: 202 (đang render) → poll lại → 200 (ready) → hiện video", async () => {
    localStorage.setItem(ECO_MODE_KEY, "1");
    vi.mocked(api.getPreviewStatus)
      .mockResolvedValueOnce("rendering") // lần probe đầu: server mới enqueue
      .mockResolvedValue("ready"); // lần poll sau: worker đã render xong

    render(<LabelDetailPage />);
    expect(await screen.findByTestId("preview-rendering")).toBeInTheDocument();

    // Chu kỳ poll là 3s — chờ vòng poll kế tiếp chuyển sang video
    expect(await screen.findByTestId("preview-video", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(api.getPreviewStatus).toHaveBeenCalledTimes(2);
  }, 10000);

  it("đổi chất lượng thủ công từ dropdown → chuyển tier ngay (video → 2D)", async () => {
    localStorage.setItem(ECO_MODE_KEY, "1"); // đang ở tier video
    render(<LabelDetailPage />);
    await screen.findByTestId("preview-video");

    fireEvent.change(screen.getByLabelText("Chất lượng hiển thị"), {
      target: { value: "2d" },
    });
    expect(await screen.findByTestId("skeleton-2d-canvas")).toBeInTheDocument();
    expect(api.getSessionFrames).toHaveBeenCalledWith("cls123", "sess-2");
  });
});
