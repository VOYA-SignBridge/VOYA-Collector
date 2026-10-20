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

describe("OperationalSplitPicker — nút Dựng tập chia mới", () => {
  it("bấm dựng → hỏi tiến độ → xong thì báo lên với id vừa dựng", async () => {
    vi.useFakeTimers();
    const onPrepare = vi.fn(async () => ({ run_id: "abc123" }));
    const reports = [
      { status: "running", current_step: "operational_split:pn-c", steps: [{ step: "operational_split:pn-c" }], operational_splits: [], research_splits: [], warnings: [] },
      { status: "completed", current_step: null, steps: [{ step: "operational_split:pn-c", ok: true }],
        operational_splits: [{ split_id: "pn-c-20260915-abc123-floor25", dialect: "pn-c", ok: true }], research_splits: [], warnings: [] },
    ];
    let i = 0;
    const getPreparation = vi.fn(async () => ({ run_id: "abc123", dialects: ["pn-c"], min_samples_per_class: 25, ...reports[Math.min(i++, 1)] }));
    const onPrepared = vi.fn();
    render(
      <OperationalSplitPicker
        splits={[]} loading={false} selectedDialects={["pn-c"]} value={null} onChange={() => {}}
        onPrepare={onPrepare} getPreparation={getPreparation} onPrepared={onPrepared}
      />,
    );
    // Chưa có tập → gợi ý bấm nút thay vì in lệnh terminal.
    expect(screen.queryByText(/make_splits\.py/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Dựng tập chia mới" }));
    await vi.waitFor(() => expect(onPrepare).toHaveBeenCalledWith(["pn-c"]));
    await vi.waitFor(() => expect(screen.getByTestId("operational-split-progress").textContent).toContain("Đang chia tập cho phương ngữ pn-c"));
    await vi.advanceTimersByTimeAsync(3000);
    await vi.waitFor(() => expect(onPrepared).toHaveBeenCalledWith(["pn-c-20260915-abc123-floor25"]));
    await vi.waitFor(() => expect(screen.getByTestId("operational-split-progress").textContent).toContain("Đã dựng xong 1 tập chia"));
    vi.useRealTimers();
  });

  it("dựng thất bại → hiện lý do của từng phương ngữ", async () => {
    const onPrepare = vi.fn(async () => ({ run_id: "abc123" }));
    const getPreparation = vi.fn(async () => ({
      run_id: "abc123", dialects: ["pn-c"], min_samples_per_class: 25, status: "failed", current_step: null,
      error: "không dựng được hiện vật vận hành nào", steps: [],
      operational_splits: [{ split_id: "x", dialect: "pn-c", ok: false, error: "[floor] còn 1 lớp" }],
      research_splits: [], warnings: [],
    }));
    render(
      <OperationalSplitPicker
        splits={[]} loading={false} selectedDialects={["pn-c"]} value={null} onChange={() => {}}
        onPrepare={onPrepare} getPreparation={getPreparation}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Dựng tập chia mới" }));
    await vi.waitFor(() => expect(screen.getByTestId("operational-split-failures").textContent).toContain("pn-c: [floor] còn 1 lớp"));
    expect(screen.getByRole("button", { name: "Dựng tập chia mới" })).toBeEnabled();
  });
});
