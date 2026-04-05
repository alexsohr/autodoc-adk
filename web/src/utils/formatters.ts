/**
 * Pure formatting utility functions for the AutoDoc dashboard.
 */

const MINUTE = 60;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const WEEK = 7 * DAY;

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
] as const;

/**
 * Format a timestamp as a human-readable relative time string.
 *
 * - "just now" for < 1 min
 * - "5m ago" for < 1 hour
 * - "3h ago" for < 24 hours
 * - "2d ago" for < 7 days
 * - "Mar 15" for < 1 year
 * - "Mar 15, 2025" for >= 1 year
 */
export function formatRelativeTime(timestamp: string | Date, now: Date = new Date()): string {
  const date = timestamp instanceof Date ? timestamp : new Date(timestamp);

  if (isNaN(date.getTime())) {
    return "\u2014";
  }

  const diffSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  // Future timestamps or essentially "now"
  if (diffSeconds < 0) {
    return "just now";
  }

  if (diffSeconds < MINUTE) {
    return "just now";
  }

  if (diffSeconds < HOUR) {
    const minutes = Math.floor(diffSeconds / MINUTE);
    return `${minutes}m ago`;
  }

  if (diffSeconds < DAY) {
    const hours = Math.floor(diffSeconds / HOUR);
    return `${hours}h ago`;
  }

  if (diffSeconds < WEEK) {
    const days = Math.floor(diffSeconds / DAY);
    return `${days}d ago`;
  }

  const month = MONTHS[date.getMonth()];
  const day = date.getDate();

  // Check if same year
  if (date.getFullYear() === now.getFullYear()) {
    return `${month} ${day}`;
  }

  return `${month} ${day}, ${date.getFullYear()}`;
}

/**
 * Format a quality score as "X.Y" with one decimal place.
 * Returns "\u2014" for null/undefined.
 */
export function formatScore(score: number | null | undefined): string {
  if (score == null) {
    return "\u2014";
  }

  return score.toFixed(1);
}

/**
 * Format a token count with SI suffixes (K, M).
 * Returns "\u2014" for null/undefined.
 */
export function formatTokens(count: number | null | undefined): string {
  if (count == null) {
    return "\u2014";
  }

  if (count < 0) {
    return "\u2014";
  }

  if (count === 0) {
    return "0";
  }

  if (count >= 1_000_000) {
    const millions = count / 1_000_000;
    return `${parseFloat(millions.toFixed(1))}M`;
  }

  if (count >= 1_000) {
    const thousands = count / 1_000;
    return `${parseFloat(thousands.toFixed(1))}K`;
  }

  return String(count);
}

/**
 * Format a duration in seconds as a human-readable string.
 * Returns "\u2014" for null/undefined.
 *
 * - "0s" for 0
 * - "45s" for < 60
 * - "2m 30s" for < 3600
 * - "1h 5m" for >= 3600
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) {
    return "\u2014";
  }

  if (seconds < 0) {
    return "\u2014";
  }

  if (seconds === 0) {
    return "0s";
  }

  const hours = Math.floor(seconds / HOUR);
  const minutes = Math.floor((seconds % HOUR) / MINUTE);
  const secs = Math.floor(seconds % MINUTE);

  if (hours > 0) {
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }

  if (minutes > 0) {
    return secs > 0 ? `${minutes}m ${secs}s` : `${minutes}m`;
  }

  return `${secs}s`;
}
