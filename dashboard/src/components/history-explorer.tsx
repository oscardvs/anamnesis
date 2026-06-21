"use client";

import { useEffect, useState } from "react";

import { GitCommitVertical } from "lucide-react";

import { CommitGraph, machineColor } from "@/components/commit-graph";
import { FileDiffCard } from "@/components/diff-view";
import { EmptyState, Spinner } from "@/components/ui/misc";
import { absoluteTime, relativeTime } from "@/lib/format";
import type { Commit, FileDiff } from "@/lib/types";

/** Global commit history: pick a commit, see every file it changed. */
export function HistoryExplorer({ commits }: { commits: Commit[] }) {
  const [selected, setSelected] = useState<string | null>(commits[0]?.hash ?? null);
  const [files, setFiles] = useState<FileDiff[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selected) return;
    const id = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/commits/${selected}`, { cache: "no-store" });
        const d = (await res.json()) as { files: FileDiff[] };
        setFiles(d.files);
      } catch {
        setFiles([]);
      } finally {
        setLoading(false);
      }
    }, 0);
    return () => clearTimeout(id);
  }, [selected]);

  if (!commits.length) {
    return <EmptyState icon={<GitCommitVertical />} title="No commits in this repo yet" />;
  }

  const current = commits.find((c) => c.hash === selected);

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,420px)_1fr]">
      <div>
        <p className="mb-2 px-1 text-[11px] uppercase tracking-[0.12em] text-faint">
          Commits ({commits.length})
        </p>
        <CommitGraph commits={commits} selectedHash={selected} onSelect={setSelected} />
      </div>

      <div className="min-w-0 space-y-3">
        {current && (
          <div className="rounded-xl bezel bg-surface p-4">
            <p className="text-sm text-text">{current.subject}</p>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-faint">
              <span className="font-mono">{current.shortHash}</span>
              <span className="inline-flex items-center gap-1">
                <span
                  className="size-1.5 rounded-full"
                  style={{ background: machineColor(current.machineId) }}
                />
                {current.machineId}
              </span>
              <span title={absoluteTime(current.date)}>{relativeTime(current.date)}</span>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex justify-center rounded-xl bezel bg-surface py-12">
            <Spinner />
          </div>
        ) : files && files.length ? (
          <div className="space-y-5">
            {files.map((f) => (
              <FileDiffCard
                key={f.path}
                path={f.path}
                changeType={f.changeType}
                additions={f.additions}
                deletions={f.deletions}
                lines={f.lines}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-xl bezel bg-surface px-4 py-8 text-center text-xs text-faint">
            No file changes to show for this commit.
          </div>
        )}
      </div>
    </div>
  );
}
