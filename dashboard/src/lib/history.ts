/**
 * Higher-level history/diff helpers used by the API routes: diff a note between
 * two git refs, and expand a commit into per-file diffs. Diffs are computed from
 * file contents (jsdiff) so rendering is uniform whether the source is two git
 * revisions or a working-tree edit.
 */
import { computeLineDiff, diffStat } from "./diff";
import { commitFiles, noteContentAtCommit } from "./git";
import { noteRelPath, readNoteText } from "./store";
import type { FileDiff } from "./types";

/**
 * Diff one note between two refs. `from === "empty"` treats the old side as a
 * new file; `to === "working"` diffs against the current working-tree file.
 */
export async function noteDiff(id: string, from: string, to: string): Promise<FileDiff | null> {
  const rel = noteRelPath(id);
  if (!rel) return null;
  const oldText = from === "empty" ? "" : ((await noteContentAtCommit(from, rel)) ?? "");
  const newText =
    to === "working"
      ? ((await readNoteText(id)) ?? "")
      : ((await noteContentAtCommit(to, rel)) ?? "");
  const lines = computeLineDiff(oldText, newText);
  return { path: rel, changeType: "M", lines, ...diffStat(lines) };
}

/** Expand a commit into the per-file diffs it introduced (parent vs commit). */
export async function commitDetail(hash: string): Promise<FileDiff[]> {
  const files = await commitFiles(hash);
  const out: FileDiff[] = [];
  for (const f of files.slice(0, 100)) {
    const oldText = f.changeType === "A" ? "" : ((await noteContentAtCommit(`${hash}^`, f.path)) ?? "");
    const newText = f.changeType === "D" ? "" : ((await noteContentAtCommit(hash, f.path)) ?? "");
    const lines = computeLineDiff(oldText, newText);
    out.push({ path: f.path, changeType: f.changeType, lines, ...diffStat(lines) });
  }
  return out;
}
