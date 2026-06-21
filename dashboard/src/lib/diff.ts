/**
 * Line-level diffs between two versions of a note, rendered full-file (notes are
 * small) so the whole memory is visible with changes highlighted. Diffs are
 * computed from two markdown strings (jsdiff), which the caller obtains either
 * from two git revisions or from a working-tree edit.
 */
import { diffLines } from "diff";

import type { DiffLine } from "./types";

export interface DiffStat {
  additions: number;
  deletions: number;
}

/** Compute a full-file, GitHub-style line diff between old and new text. */
export function computeLineDiff(oldText: string, newText: string): DiffLine[] {
  const parts = diffLines(oldText ?? "", newText ?? "");
  const lines: DiffLine[] = [];
  let oldNo = 1;
  let newNo = 1;
  for (const part of parts) {
    const segments = part.value.split("\n");
    if (segments.length && segments[segments.length - 1] === "") segments.pop();
    for (const content of segments) {
      if (part.added) {
        lines.push({ type: "add", oldNumber: null, newNumber: newNo++, content });
      } else if (part.removed) {
        lines.push({ type: "del", oldNumber: oldNo++, newNumber: null, content });
      } else {
        lines.push({ type: "context", oldNumber: oldNo++, newNumber: newNo++, content });
      }
    }
  }
  return lines;
}

/** Count additions/deletions in a computed diff. */
export function diffStat(lines: DiffLine[]): DiffStat {
  let additions = 0;
  let deletions = 0;
  for (const l of lines) {
    if (l.type === "add") additions++;
    else if (l.type === "del") deletions++;
  }
  return { additions, deletions };
}
