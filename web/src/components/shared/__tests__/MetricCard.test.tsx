import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SaltProvider } from "@salt-ds/core";
import { MetricCard } from "../MetricCard";

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <SaltProvider mode="light">{children}</SaltProvider>
);

describe("MetricCard", () => {
  it("renders label and value", () => {
    render(<MetricCard label="Doc Pages" value="24" />, { wrapper });
    expect(screen.getByText("Doc Pages")).toBeDefined();
    expect(screen.getByText("24")).toBeDefined();
  });

  it("renders icon when provided", () => {
    render(<MetricCard label="Doc Pages" value="24" icon="description" />, { wrapper });
    const icon = screen.getByText("description");
    expect(icon).toBeDefined();
    expect(icon.className).toContain("material-symbols-outlined");
  });

  it("does not render icon container when icon is omitted", () => {
    const { container } = render(<MetricCard label="Score" value="8.2" />, { wrapper });
    expect(container.querySelector(".material-symbols-outlined")).toBeNull();
  });
});
