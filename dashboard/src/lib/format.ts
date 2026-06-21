/**
 * Small, dependency-free formatting helpers shared across the UI.
 */

/** A compact relative time like "3h ago" / "just now" (UTC-safe on ISO input). */
export function relativeTime(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "unknown";
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "unknown";
  const sec = Math.round((now - then) / 1000);
  if (sec < 0) return "in the future";
  if (sec < 45) return "just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 30) return `${day}d ago`;
  const mon = Math.round(day / 30);
  if (mon < 12) return `${mon}mo ago`;
  return `${Math.round(mon / 12)}y ago`;
}

/** An absolute timestamp like "2026-06-18 07:02" (local), for tooltips/details. */
export function absoluteTime(iso: string | null | undefined): string {
  if (!iso) return "unknown";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unknown";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Shorten a project key for chips: drops a leading git host, keeps owner/repo tail. */
export function shortProject(project: string): string {
  if (!project) return "global";
  const noHost = project.replace(/^github\.com\//, "");
  return noHost;
}
