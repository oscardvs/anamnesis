"use client";

import { useEffect, useState } from "react";

import { GitCommitVertical } from "lucide-react";

import { CommitGraph } from "@/components/commit-graph";
import { FileDiffCard } from "@/components/diff-view";
import { EmptyState, Spinner } from "@/components/ui/misc";
import type { FileDiff, NoteCommit } from "@/lib/types";

/** Per-note version history: pick a commit, see the diff it introduced. */
export function NoteHistoryExplorer({
  noteId,
  commits,
}: {
  noteId: string;
  commits: NoteCommit[];
}) {
  const [selected, setSelected] = useState<string | null>(commits[0]?.hash ?? null);
  const [diff, setDiff] = useState<FileDiff | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selected) return;
    const id = setTimeout(async () => {
      setLoading(true);
      const from = encodeURIComponent(`${selected}^`);
      const to = encodeURIComponent(selected);
      try {
        const res = await fetch(`/api/notes/${noteId}/diff?from=${from}&to=${to}`, {
          cache: "no-store",
        });
        const d = (await res.json()) as { diff: FileDiff | null };
        setDiff(d.diff);
      } catch {
        setDiff(null);
      } finally {
        setLoading(false);
      }
    }, 0);
    return () => clearTimeout(id);
  }, [selected, noteId]);

  if (!commits.length) {
    return (
      <EmptyState
        icon={<GitCommitVertical />}
        title="No history yet"
        description="This note has not been committed to the memory repo yet."
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,360px)_1fr]">
      <div>
        <p className="mb-2 px-1 text-[11px] uppercase tracking-[0.12em] text-faint">
          Versions ({commits.length})
        </p>
        <CommitGraph commits={commits} selectedHash={selected} onSelect={setSelected} />
      </div>
      <div className="min-w-0">
        <p className="mb-2 px-1 text-[11px] uppercase tracking-[0.12em] text-faint">
          Change in this version
        </p>
        {loading ? (
          <div className="flex justify-center rounded-xl bezel bg-surface py-12">
            <Spinner />
          </div>
        ) : diff ? (
          <FileDiffCard
            path={diff.path}
            changeType={diff.changeType}
            additions={diff.additions}
            deletions={diff.deletions}
            lines={diff.lines}
          />
        ) : (
          <div className="rounded-xl bezel bg-surface px-4 py-8 text-center text-xs text-faint">
            Select a version to see what changed.
          </div>
        )}
      </div>
    </div>
  );
}
