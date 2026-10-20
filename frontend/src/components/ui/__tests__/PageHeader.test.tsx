import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PageHeader from "../PageHeader";

vi.mock("react-router-dom", () => ({
  Link: ({ to, children, className }: {
    to: string; children: React.ReactNode; className?: string;
  }) => <a href={to} className={className}>{children}</a>,
}));

/**
 * The reported bug was "the Dashboard breadcrumb does nothing when clicked".
 *
 * The cause was not a missing link. Every crumb that was not the last one got
 * `hover:text-slate-700` whether or not it had an `href`, so a plain label lit
 * up under the cursor and then went nowhere — which reads as a broken link
 * rather than as text. Two properties, and the second is the one that was
 * actually wrong.
 */
describe("PageHeader breadcrumb", () => {
  it("renders a crumb with an href as a real link", () => {
    render(<PageHeader title="Huấn luyện"
                       breadcrumb={[{ label: "Dashboard", href: "/" }, "Huấn luyện"]} />);
    expect(screen.getByRole("link", { name: "Dashboard" }))
      .toHaveAttribute("href", "/");
  });

  it("does not give a hover affordance to a crumb that cannot be clicked", () => {
    render(<PageHeader title="Nhãn" breadcrumb={["Dữ liệu", "Nhãn"]} />);
    const crumb = screen.getByText("Dữ liệu");
    expect(crumb.tagName).toBe("SPAN");
    expect(crumb.className).not.toContain("hover:");
  });

  it("never links the current page, even when given an href", () => {
    // The last crumb IS where the reader already is. Linking it invites a
    // click that reloads the same screen.
    render(<PageHeader title="Nhãn"
                       breadcrumb={[{ label: "Dữ liệu", href: "/data" },
                                    { label: "Nhãn", href: "/labels" }]} />);
    expect(screen.queryByRole("link", { name: "Nhãn" })).toBeNull();
    expect(screen.getByRole("link", { name: "Dữ liệu" })).toBeTruthy();
  });
});
