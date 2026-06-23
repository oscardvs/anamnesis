/**
 * Map a note's provenance to its "quiet by default" chip. Human notes get no
 * chip; session-end/import get a muted chip; reflection gets a warn (amber)
 * chip with its confidence score. Pure (no React) so it is DOM-free testable.
 */
import type { ProvSource } from "./types";

/** A subset of the Badge tones used for provenance. */
export type ProvTone = "info" | "neutral" | "warn";

const PROV_META: Record<ProvSource, { label: string; tone: ProvTone } | null> = {
  human: null,
  "session-end": { label: "session", tone: "info" },
  import: { label: "import", tone: "neutral" },
  reflection: { label: "reflection", tone: "warn" },
};

export function provenanceBadge(
  source: ProvSource,
  confidence: number,
): { label: string; tone: ProvTone } | null {
  const m = PROV_META[source];
  if (!m) return null;
  const label = confidence < 1 ? `${m.label} · ${confidence}` : m.label;
  return { label, tone: m.tone };
}
