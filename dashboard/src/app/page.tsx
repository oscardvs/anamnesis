import Link from "next/link";
import { ArrowUpRight, GitCommitVertical, Layers, Plus, Server, TriangleAlert } from "lucide-react";

import { CommitGraph } from "@/components/commit-graph";
import { NoteRow } from "@/components/note-row";
import { ReindexButton } from "@/components/reindex-button";
import { StatusDot } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";
import { EmptyState, PageHeader, Panel } from "@/components/ui/misc";
import { countsByMachine, indexExists, listMeta, stats } from "@/lib/db";
import { fleet, globalHistory, repoState } from "@/lib/git";
import { shortProject } from "@/lib/format";
import { describeRepo } from "@/lib/repo";
import { MEMORY_TYPES } from "@/lib/types";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const TYPE_COLOR: Record<string, string> = {
  procedural: "var(--type-procedural)",
  semantic: "var(--type-semantic)",
  episodic: "var(--type-episodic)",
};

export default async function OverviewPage() {
  const hasIndex = indexExists();
  const s = stats();
  const [commits, machines, repo] = await Promise.all([
    globalHistory(6),
    fleet(countsByMachine()),
    repoState(),
  ]);
  const recentNotes = listMeta({ limit: 6 });
  const { label: syncLabel, tone } = describeRepo(repo);
  const projectCount = Object.keys(s.byProject).length;
  const topProjects = Object.entries(s.byProject).slice(0, 4);

  return (
    <div className="animate-rise space-y-6">
      <PageHeader
        eyebrow="memory"
        title="Overview"
        description="A cross-machine, file-first memory layer for Claude Code - browsed like git."
        actions={
          <Button variant="primary" asChild>
            <Link href="/notes/new">
              <Plus strokeWidth={1.75} /> New note
            </Link>
          </Button>
        }
      />

      {!hasIndex && (
        <Panel className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <TriangleAlert size={18} strokeWidth={1.5} className="mt-0.5 text-warn" />
            <div>
              <p className="text-sm font-medium text-text">The search index has not been built yet</p>
              <p className="text-xs text-muted">
                Markdown is the source of truth; rebuild the SQLite index to enable search.
              </p>
            </div>
          </div>
          <ReindexButton label="Build index" />
        </Panel>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Panel className="p-5">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.12em] text-faint">
            <Layers size={14} strokeWidth={1.5} /> Memories
          </div>
          <p className="mt-3 font-mono text-4xl font-semibold tracking-tight text-text">{s.total}</p>
          <div className="mt-4 space-y-2">
            {MEMORY_TYPES.map((t) => {
              const count = s.byType[t] ?? 0;
              const pct = s.total ? Math.round((count / s.total) * 100) : 0;
              return (
                <div key={t} className="flex items-center gap-3">
                  <span className="w-20 shrink-0 text-xs capitalize text-muted">{t}</span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${pct}%`, background: TYPE_COLOR[t] }}
                    />
                  </div>
                  <span className="w-8 shrink-0 text-right font-mono text-xs text-faint">{count}</span>
                </div>
              );
            })}
          </div>
        </Panel>

        <Panel className="flex flex-col p-5">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.12em] text-faint">
            <Server size={14} strokeWidth={1.5} /> Sync
          </div>
          <div className="mt-3 flex items-center gap-2">
            <StatusDot tone={tone} pulse={tone === "danger"} />
            <span className="text-lg font-medium text-text">{syncLabel}</span>
          </div>
          <dl className="mt-4 space-y-1.5 text-xs">
            <div className="flex justify-between">
              <dt className="text-muted">Machines</dt>
              <dd className="font-mono text-text">{machines.length}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted">Head</dt>
              <dd className="font-mono text-text">{repo.head || "-"}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="shrink-0 text-muted">Remote</dt>
              <dd className="truncate font-mono text-faint">{repo.remote ?? "local only"}</dd>
            </div>
          </dl>
          <Link
            href="/machines"
            className="mt-auto inline-flex items-center gap-1 pt-4 text-xs font-medium text-accent hover:underline"
          >
            View fleet <ArrowUpRight size={13} strokeWidth={1.75} />
          </Link>
        </Panel>

        <Panel className="flex flex-col p-5">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.12em] text-faint">
            <Layers size={14} strokeWidth={1.5} /> Projects
          </div>
          <p className="mt-3 font-mono text-4xl font-semibold tracking-tight text-text">
            {projectCount}
          </p>
          <div className="mt-4 space-y-1.5">
            {topProjects.map(([proj, count]) => (
              <Link
                key={proj}
                href={`/browse?project=${encodeURIComponent(proj)}`}
                className="flex items-center justify-between gap-2 rounded-md px-1.5 py-1 text-xs transition-colors hover:bg-highlight"
              >
                <span className="min-w-0 truncate text-muted">{shortProject(proj)}</span>
                <span className="shrink-0 font-mono text-faint">{count}</span>
              </Link>
            ))}
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between px-1">
            <h2 className="flex items-center gap-2 text-sm font-medium text-text">
              <GitCommitVertical size={16} strokeWidth={1.5} className="text-faint" /> Recent syncs
            </h2>
            <Link href="/history" className="text-xs font-medium text-accent hover:underline">
              Full history
            </Link>
          </div>
          {commits.length ? (
            <CommitGraph commits={commits} />
          ) : (
            <EmptyState icon={<GitCommitVertical />} title="No commits yet" />
          )}
        </div>

        <div>
          <div className="mb-3 flex items-center justify-between px-1">
            <h2 className="text-sm font-medium text-text">Recently updated</h2>
            <Link href="/browse" className="text-xs font-medium text-accent hover:underline">
              Browse all
            </Link>
          </div>
          {recentNotes.length ? (
            <Panel className="p-1.5">
              <div className="divide-y divide-line">
                {recentNotes.map((note) => (
                  <NoteRow key={note.id} note={note} />
                ))}
              </div>
            </Panel>
          ) : (
            <EmptyState icon={<Layers />} title="No notes yet" />
          )}
        </div>
      </div>
    </div>
  );
}
