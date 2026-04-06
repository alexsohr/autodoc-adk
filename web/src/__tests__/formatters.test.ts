import { describe, it, expect } from "vitest";
import {
  formatRelativeTime,
  formatScore,
  formatTokens,
  formatDuration,
} from "@/utils/formatters";

describe("formatRelativeTime", () => {
  const now = new Date("2026-04-04T12:00:00Z");

  it("returns 'just now' for timestamps less than 1 minute ago", () => {
    const thirtySecondsAgo = new Date("2026-04-04T11:59:30Z");
    expect(formatRelativeTime(thirtySecondsAgo, now)).toBe("just now");
  });

  it("returns minutes ago for timestamps less than 1 hour ago", () => {
    const fiveMinutesAgo = new Date("2026-04-04T11:55:00Z");
    expect(formatRelativeTime(fiveMinutesAgo, now)).toBe("5m ago");
  });

  it("returns hours ago for timestamps less than 24 hours ago", () => {
    const threeHoursAgo = new Date("2026-04-04T09:00:00Z");
    expect(formatRelativeTime(threeHoursAgo, now)).toBe("3h ago");
  });

  it("returns days ago for timestamps less than 7 days ago", () => {
    const twoDaysAgo = new Date("2026-04-02T12:00:00Z");
    expect(formatRelativeTime(twoDaysAgo, now)).toBe("2d ago");
  });

  it("returns 'Mon DD' for timestamps in the same year but older than 7 days", () => {
    const twoWeeksAgo = new Date("2026-03-15T12:00:00Z");
    expect(formatRelativeTime(twoWeeksAgo, now)).toBe("Mar 15");
  });

  it("returns 'Mon DD, YYYY' for timestamps in a different year", () => {
    const lastYear = new Date("2025-03-15T12:00:00Z");
    expect(formatRelativeTime(lastYear, now)).toBe("Mar 15, 2025");
  });

  it("returns 'just now' for future timestamps", () => {
    const future = new Date("2026-04-04T13:00:00Z");
    expect(formatRelativeTime(future, now)).toBe("just now");
  });

  it("handles ISO string input", () => {
    expect(formatRelativeTime("2026-04-04T11:55:00Z", now)).toBe("5m ago");
  });

  it("returns em dash for invalid date string", () => {
    expect(formatRelativeTime("not-a-date", now)).toBe("\u2014");
  });
});

describe("formatScore", () => {
  it("formats a score with one decimal place", () => {
    expect(formatScore(8.5)).toBe("8.5");
  });

  it("formats an integer score with trailing .0", () => {
    expect(formatScore(9)).toBe("9.0");
  });

  it("rounds to one decimal place", () => {
    expect(formatScore(7.86)).toBe("7.9");
  });

  it("returns em dash for null", () => {
    expect(formatScore(null)).toBe("\u2014");
  });

  it("returns em dash for undefined", () => {
    expect(formatScore(undefined)).toBe("\u2014");
  });

  it("formats zero correctly", () => {
    expect(formatScore(0)).toBe("0.0");
  });

  it("formats negative score", () => {
    expect(formatScore(-1.5)).toBe("-1.5");
  });
});

describe("formatTokens", () => {
  it("returns '0' for zero", () => {
    expect(formatTokens(0)).toBe("0");
  });

  it("returns raw number for counts under 1000", () => {
    expect(formatTokens(500)).toBe("500");
  });

  it("formats thousands with K suffix", () => {
    expect(formatTokens(1200)).toBe("1.2K");
  });

  it("formats millions with M suffix", () => {
    expect(formatTokens(3_400_000)).toBe("3.4M");
  });

  it("drops trailing zero in suffix (e.g. 2K not 2.0K)", () => {
    expect(formatTokens(2000)).toBe("2K");
  });

  it("returns em dash for null", () => {
    expect(formatTokens(null)).toBe("\u2014");
  });

  it("returns em dash for undefined", () => {
    expect(formatTokens(undefined)).toBe("\u2014");
  });

  it("returns em dash for negative numbers", () => {
    expect(formatTokens(-100)).toBe("\u2014");
  });

  it("handles very large numbers", () => {
    expect(formatTokens(1_500_000_000)).toBe("1500M");
  });
});

describe("formatDuration", () => {
  it("returns '0s' for zero seconds", () => {
    expect(formatDuration(0)).toBe("0s");
  });

  it("formats seconds under a minute", () => {
    expect(formatDuration(45)).toBe("45s");
  });

  it("formats minutes and seconds", () => {
    expect(formatDuration(150)).toBe("2m 30s");
  });

  it("formats exact minutes without trailing seconds", () => {
    expect(formatDuration(120)).toBe("2m");
  });

  it("formats hours and minutes", () => {
    expect(formatDuration(3900)).toBe("1h 5m");
  });

  it("formats exact hours without trailing minutes", () => {
    expect(formatDuration(3600)).toBe("1h");
  });

  it("returns em dash for null", () => {
    expect(formatDuration(null)).toBe("\u2014");
  });

  it("returns em dash for undefined", () => {
    expect(formatDuration(undefined)).toBe("\u2014");
  });

  it("returns em dash for negative seconds", () => {
    expect(formatDuration(-10)).toBe("\u2014");
  });

  it("handles very large durations", () => {
    // 100 hours = 360000 seconds
    expect(formatDuration(360000)).toBe("100h");
  });
});
