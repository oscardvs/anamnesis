/**
 * Map the memory repo's working/sync state to a human label + status tone.
 * Shared by the topbar sync control and the machines/fleet view.
 */
import type { RepoState } from "./types";

export type StatusTone = "neutral" | "accent" | "ok" | "warn" | "info" | "danger";

export function describeRepo(repo: RepoState | null | undefined): {
  label: string;
  tone: StatusTone;
} {
  if (!repo || !repo.initialized) return { label: "no repo", tone: "neutral" };
  if (repo.conflicted) return { label: "conflict", tone: "danger" };
  if (repo.dirty) return { label: "uncommitted", tone: "warn" };
  if (repo.ahead > 0 && repo.behind > 0) {
    return { label: `${repo.ahead} ahead, ${repo.behind} behind`, tone: "warn" };
  }
  if (repo.ahead > 0) return { label: `${repo.ahead} to push`, tone: "info" };
  if (repo.behind > 0) return { label: `${repo.behind} to pull`, tone: "info" };
  if (!repo.remote) return { label: "local only", tone: "neutral" };
  return { label: "synced", tone: "ok" };
}
