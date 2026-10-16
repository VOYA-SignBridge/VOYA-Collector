import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import TrainingProgress from "../TrainingProgress";
import type { TrainingJob } from "../../../../hooks/useTrainingAPI";

/**
 * Regression + phân quyền hiển thị lỗi:
 *  - Một run THẤT BẠI (lỗi lúc dispatch — chưa có epoch) không được kẹt spinner.
 *  - Lỗi HỆ THỐNG: ADMIN thấy chi tiết kỹ thuật + cách khắc phục; USER thường
 *    chỉ thấy thông báo gọn "quản trị viên đã được thông báo", KHÔNG lộ nội bộ.
 *  - Lỗi DỮ LIỆU (user tự sửa được) thì user vẫn thấy hướng dẫn.
 */

const baseJob: TrainingJob = {
  id: "job-1",
  status: "running",
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: { model_type: "tcn", dialects: ["bac"] } as any,
  created_at: "2026-07-22T00:00:00Z",
  started_at: "2026-07-22T00:00:00Z",
  current_epoch: 0,
  total_epochs: 80,
};

const systemFail: TrainingJob = {
  ...baseJob,
  status: "failed",
  completed_at: "2026-07-22T00:01:45Z",
  error_message: "Không gửi được job tới trainer (Redis/Celery down?): redis down",
};

describe("TrainingProgress — trạng thái kết thúc & phiên bản lỗi", () => {
  it("running + chưa có metric → vẫn hiện spinner chờ epoch đầu", () => {
    render(<TrainingProgress job={baseJob} metrics={[]} />);
    expect(screen.getByText(/Đang chờ epoch đầu tiên/)).toBeInTheDocument();
  });

  it("failed → NGẮT spinner (không còn dòng chờ epoch)", () => {
    render(<TrainingProgress job={systemFail} metrics={[]} isAdmin={false} />);
    expect(screen.queryByText(/Đang chờ epoch đầu tiên/)).not.toBeInTheDocument();
  });

  it("lỗi hệ thống + ADMIN → thấy chi tiết kỹ thuật + cách khắc phục", () => {
    const onBack = vi.fn();
    const onRetry = vi.fn();
    render(
      <TrainingProgress job={systemFail} metrics={[]} isAdmin onBack={onBack} onRetry={onRetry} />,
    );
    expect(screen.getByText(/Chi tiết kỹ thuật/)).toBeInTheDocument();
    expect(screen.getByText(/redis down/)).toBeInTheDocument();
    expect(screen.getByText(/Cách khắc phục/)).toBeInTheDocument();
    expect(screen.getByText(/ghi vào nhật ký quản trị/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Quay về/ }));
    expect(onBack).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: /Thử lại/ }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("lỗi hệ thống + USER thường → thông báo gọn, KHÔNG lộ chi tiết kỹ thuật", () => {
    render(<TrainingProgress job={systemFail} metrics={[]} isAdmin={false} onBack={vi.fn()} onRetry={vi.fn()} />);
    // Bản dành cho user: báo đã thông báo admin, ẩn nội bộ.
    expect(screen.getAllByText(/Quản trị viên đã được thông báo/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Chi tiết kỹ thuật/)).not.toBeInTheDocument();
    expect(screen.queryByText(/redis down/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Cách khắc phục/)).not.toBeInTheDocument();
    // Vẫn còn nút hành động
    expect(screen.getByRole("button", { name: /Thử lại/ })).toBeInTheDocument();
  });

  it("lỗi DỮ LIỆU + USER thường → vẫn thấy hướng dẫn tự khắc phục", () => {
    const dataFail: TrainingJob = {
      ...baseJob,
      status: "failed",
      completed_at: "2026-07-22T00:00:10Z",
      error_message: "Không có dữ liệu: splits train.csv rỗng cho phương ngữ đã chọn",
    };
    render(<TrainingProgress job={dataFail} metrics={[]} isAdmin={false} onBack={vi.fn()} />);
    expect(screen.getByText(/Thiếu dữ liệu huấn luyện/)).toBeInTheDocument();
    expect(screen.getByText(/Cách khắc phục/)).toBeInTheDocument();
    // Không phải lỗi hệ thống nên không có banner "đã báo admin"
    expect(screen.queryByText(/Quản trị viên đã được thông báo/)).not.toBeInTheDocument();
  });

  it("cancelled → panel 'đã bị hủy', không hiện danh sách nguyên nhân", () => {
    const job: TrainingJob = { ...baseJob, status: "cancelled", completed_at: "2026-07-22T00:00:30Z" };
    render(<TrainingProgress job={job} metrics={[]} isAdmin onBack={vi.fn()} />);
    expect(screen.getByText(/Huấn luyện đã bị hủy/)).toBeInTheDocument();
    expect(screen.queryByText(/Nguyên nhân có thể/)).not.toBeInTheDocument();
  });
});
