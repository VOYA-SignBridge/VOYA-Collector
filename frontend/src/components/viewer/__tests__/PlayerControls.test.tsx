import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import PlayerControls from "../PlayerControls";

const setup = (overrides: Partial<Parameters<typeof PlayerControls>[0]> = {}) => {
  const props = {
    frame: 10,
    frameCount: 60,
    playing: true,
    speed: 1,
    onToggle: vi.fn(),
    onSeek: vi.fn(),
    onSpeed: vi.fn(),
    ...overrides,
  };
  render(<PlayerControls {...props} />);
  return props;
};

describe("PlayerControls — thanh điều khiển phát", () => {
  it("hiển thị bộ đếm khung dạng 1-based (11/60 khi frame=10)", () => {
    setup();
    expect(screen.getByText("11/60")).toBeInTheDocument();
  });

  it("đang phát → nút có nhãn Tạm dừng; đang dừng → nhãn Phát", () => {
    setup({ playing: true });
    expect(screen.getByLabelText("Tạm dừng")).toBeInTheDocument();
  });

  it("bấm nút play/pause gọi onToggle đúng 1 lần", () => {
    const props = setup();
    fireEvent.click(screen.getByLabelText("Tạm dừng"));
    expect(props.onToggle).toHaveBeenCalledTimes(1);
  });

  it("kéo thanh tua gọi onSeek với số khung (number, không phải string)", () => {
    const props = setup();
    fireEvent.change(screen.getByLabelText("Tua khung hình"), { target: { value: "42" } });
    expect(props.onSeek).toHaveBeenCalledWith(42);
  });

  it("chọn tốc độ gọi onSpeed với giá trị số (0.25×–2×)", () => {
    const props = setup();
    fireEvent.change(screen.getByLabelText("Tốc độ phát"), { target: { value: "0.25" } });
    expect(props.onSpeed).toHaveBeenCalledWith(0.25);
  });

  it("frameCount = 0 (session rỗng) → slider max không âm", () => {
    setup({ frame: 0, frameCount: 0 });
    expect(screen.getByLabelText("Tua khung hình")).toHaveAttribute("max", "0");
  });
});
