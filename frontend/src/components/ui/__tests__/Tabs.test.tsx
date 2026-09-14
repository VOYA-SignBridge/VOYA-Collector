import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import Tabs, { useUrlTab, type TabItem } from "../Tabs";

const TABS: TabItem<"a" | "b" | "c">[] = [
  { id: "a", label: "Tổng quan" },
  { id: "b", label: "Phiên bản", count: 3 },
  { id: "c", label: "Lịch sử" },
];

function Harness() {
  const [tab, setTab] = useUrlTab("tab", TABS, "a");
  return (
    <Tabs tabs={TABS} value={tab} onChange={setTab} label="Mục">
      <p>panel {tab}</p>
    </Tabs>
  );
}

function show(path = "/x") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Harness />
    </MemoryRouter>,
  );
}

describe("Tabs", () => {
  it("ARIA: tablist / tab / aria-selected / tabpanel nối nhau", () => {
    show();
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(3);
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveAccessibleName("Tổng quan");
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("bấm chuyển tab, và chỉ tab đang chọn nằm trong thứ tự Tab", () => {
    show();
    fireEvent.click(screen.getByRole("tab", { name: /Phiên bản/ }));
    expect(screen.getByText("panel b")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Phiên bản/ })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tab", { name: "Tổng quan" })).toHaveAttribute("tabindex", "-1");
  });

  it("mũi tên phải/trái và Home/End chuyển tab, vòng tròn", () => {
    show();
    const list = screen.getByRole("tablist");
    fireEvent.keyDown(list, { key: "ArrowLeft" });
    expect(screen.getByText("panel c")).toBeInTheDocument();
    fireEvent.keyDown(list, { key: "ArrowRight" });
    expect(screen.getByText("panel a")).toBeInTheDocument();
    fireEvent.keyDown(list, { key: "End" });
    expect(screen.getByText("panel c")).toBeInTheDocument();
    fireEvent.keyDown(list, { key: "Home" });
    expect(screen.getByText("panel a")).toBeInTheDocument();
  });

  it("mở bằng ?tab= thì đúng mục; giá trị lạ về mục mặc định", () => {
    show("/x?tab=c");
    expect(screen.getByText("panel c")).toBeInTheDocument();
  });

  it("giá trị lạ trên URL không làm vỡ: về mục mặc định", () => {
    show("/x?tab=khong-co");
    expect(screen.getByText("panel a")).toBeInTheDocument();
  });
});
