// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MaterialIcon } from "../MaterialIcon";

describe("MaterialIcon", () => {
  it("renders a span with the correct icon name", () => {
    render(<MaterialIcon name="home" />);
    const icon = screen.getByText("home");
    expect(icon).toBeDefined();
    expect(icon.className).toContain("material-symbols-outlined");
  });

  it("applies custom size via fontSize", () => {
    render(<MaterialIcon name="settings" size={20} />);
    const icon = screen.getByText("settings");
    expect(icon.style.fontSize).toBe("20px");
  });

  it("does not set fontSize when size is omitted", () => {
    render(<MaterialIcon name="search" />);
    const icon = screen.getByText("search");
    expect(icon.style.fontSize).toBe("");
  });

  it("passes through className", () => {
    render(<MaterialIcon name="folder" className="custom-class" />);
    const icon = screen.getByText("folder");
    expect(icon.className).toContain("material-symbols-outlined");
    expect(icon.className).toContain("custom-class");
  });
});
