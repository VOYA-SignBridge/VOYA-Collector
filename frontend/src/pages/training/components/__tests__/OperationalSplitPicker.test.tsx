import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import OperationalSplitPicker from "../OperationalSplitPicker";
import type { OperationalSplit } from "../../../../hooks/useTrainingAPI";

const SPLITS: OperationalSplit[] = [
  {
    split_id: "pn-a-20260915-floor25",
    dialects: ["pn-a"],
    num_classes: 7,
    min_samples_per_class: 25,
    generated_at: "2026-09-14T17:56:50Z",
    split_mode: "sample",
    counts: { train: 570, val: 122, test: 122 },
  },
  {
    split_id: "pn-a-20260901-floor25",
    dialects: ["pn-a"],
    num_classes: 7,
    min_samples_per_class: 25,
    generated_at: "2026-09-01T00:00:00Z",
    split_mode: "sample",
    counts: { train: 500, val: 100, test: 100 },
  },
  {
    split_id: "pn-b-20260915-floor25",
    dialects: ["pn-b"],
    num_classes: 30,
    min_samples_per_class: 25,
    generated_at: "2026-09-14T18:00:00Z",
    split_mode: "sample",
    counts: { train: 1400, val: 300, test: 300 },
  },
];

describe("OperationalSplitPicker — ghim tập chia vận hành ở bước Chia Tập", () => {
  it("chọn sẵn hiện vật mới nhất KHỚP phương ngữ đã chọn", () => {
    const onChange = vi.fn();
    render(
      <OperationalSplitPicker splits={SPLITS} loading={false} selectedDialects={["pn-a"]} value={null} onChange={onChange} />,
    );
    // Server xếp mới nhất lên đầu; hiện vật bảng chữ cái không được liệt kê.
    expect(onChange).toHaveBeenCalledWith("pn-a-20260915-floor25");
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual(["pn-a-20260915-floor25", "pn-a-20260901-floor25"]);
  });

  it("tóm tắt số lớp / số mẫu / sàn của hiện vật đang chọn", () => {
    render(
      <OperationalSplitPicker
        splits={SPLITS}
        loading={false}
        selectedDialects={["pn-a"]}
        value="pn-a-20260915-floor25"
        onChange={() => {}}
      />,
    );
    expect(screen.getByTestId("operational-split-summary").textContent).toContain("7 lớp");
    expect(screen.getByTestId("operational-split-summary").textContent).toContain("train 570 / val 122 / test 122");
    expect(screen.getByTestId("operational-split-summary").textContent).toContain("sàn 25");
  });

  it("người dùng đổi lựa chọn → báo lên", () => {
    const onChange = vi.fn();
    render(
      <OperationalSplitPicker
        splits={SPLITS}
        loading={false}
        selectedDialects={["pn-a"]}
        value="pn-a-20260915-floor25"
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByLabelText("Tập chia dùng cho lượt này"), { target: { value: "pn-a-20260901-floor25" } });
    expect(onChange).toHaveBeenCalledWith("pn-a-20260901-floor25");
  });

  it("không có hiện vật khớp → bỏ chọn và hiện lệnh dựng thay vì ô chọn rỗng", () => {
    const onChange = vi.fn();
    render(
      <OperationalSplitPicker
        splits={SPLITS}
        loading={false}
        selectedDialects={["pn-c"]}
        value="pn-a-20260915-floor25"
        onChange={onChange}
      />,
    );
    expect(onChange).toHaveBeenCalledWith(null);
    expect(screen.getByTestId("operational-split-empty")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText(/make_splits\.py .*--dialects pn-c/)).toBeInTheDocument();
  });
});
