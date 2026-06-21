"use client";

import { cn } from "@/lib/cn";
import { absoluteTime, relativeTime } from "@/lib/format";
import type { Commit, NoteCommit } from "@/lib/types";

function hashHue(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
  return h;
}

/** A stable, readable color per machine id (single lane stays gold-ish, others diverge). */
export function machineColor(machineId: string): string {
  return `oklch(0.78 0.11 ${hashHue(machineId)})`;
}

const CHANGE: Record<string, string> = {
  A: "added",
  M: "modified",
  D: "deleted",
  R: "renamed",
  T: "type changed",
};

/**
 * A vertical git-graph rail of commits. The memory sync history is mostly
 * linear, so a single themeable lane reads cleanly; nodes are colored by the
 * machine that authored the commit.
 */
export function CommitGraph({
  commits,
  selectedHash,
  onSelect,
}: {
  commits: (Commit | NoteCommit)[];
  selectedHash?: string | null;
  onSelect?: (hash: string) => void;
}) {
  const interactive = Boolean(onSelect);
  return (
    <div className="overflow-hidden rounded-2xl bezel bg-surface">
      {commits.map((c, i) => {
        const selected = c.hash === selectedHash;
        const color = machineColor(c.machineId);
        const changeType = "changeType" in c ? c.changeType : undefined;
        const RowTag = interactive ? "button" : "div";
        return (
          <RowTag
            key={c.hash}
            {...(interactive ? { type: "button" as const, onClick: () => onSelect?.(c.hash) } : {})}
            className={cn(
              "grid w-full grid-cols-[36px_1fr] items-stretch border-b border-line text-left transition-colors last:border-b-0",
              interactive && "hover:bg-highlight",
              selected && "bg-highlight",
            )}
          >
            <div className="relative flex justify-center">
              <span
                className={cn(
                  "absolute left-1/2 top-0 h-1/2 w-px -translate-x-1/2 bg-line",
                  i === 0 && "hidden",
                )}
              />
              <span
                className={cn(
                  "absolute bottom-0 left-1/2 h-1/2 w-px -translate-x-1/2 bg-line",
                  i === commits.length - 1 && "hidden",
                )}
              />
              <span
                className="absolute left-1/2 top-1/2 z-10 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-4 ring-surface"
                style={{
                  background: color,
                  boxShadow: selected ? "0 0 0 2px var(--accent)" : undefined,
                }}
              />
            </div>
            <div className="min-w-0 py-3 pr-4">
              <div className="flex items-baseline gap-2">
                <span className="min-w-0 flex-1 truncate text-[13.5px] text-text">{c.subject}</span>
                <span className="shrink-0 font-mono text-[11px] text-faint">{c.shortHash}</span>
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px] text-faint">
                <span className="inline-flex items-center gap-1">
                  <span className="size-1.5 rounded-full" style={{ background: color }} />
                  {c.machineId}
                </span>
                <span aria-hidden>·</span>
                <span title={absoluteTime(c.date)}>{relativeTime(c.date)}</span>
                {changeType && (
                  <>
                    <span aria-hidden>·</span>
                    <span>{CHANGE[changeType] ?? changeType}</span>
                  </>
                )}
              </div>
            </div>
          </RowTag>
        );
      })}
    </div>
  );
}
