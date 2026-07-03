// GĐ 0 smoke test — proves the Vitest + RTL pipeline works (Roadmap v2 §7.5).
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Button from "../components/ui/Button";

describe("Button (shared UI)", () => {
  it("renders its children", () => {
    render(<Button>Lưu Video</Button>);
    expect(screen.getByRole("button", { name: "Lưu Video" })).toBeInTheDocument();
  });

  it("is disabled while loading", () => {
    render(<Button loading>Đang xử lý</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
