import Link from "next/link";
import { ArrowUpRight, GitCommitVertical, Layers, Network, TriangleAlert } from "lucide-react";

import { CommitGraph } from "@/components/commit-graph";
import { CountUp } from "@/components/count-up";
import { HeroCanvas } from "@/components/hero-canvas";
import { NoteRow } from "@/components/note-row";
import { ReindexButton } from "@/components/reindex-button";
import { StatusDot } from "@/components/ui/badges";
import { EmptyState, Panel } from "@/components/ui/misc";
import { countsByMachine, indexExists, listMeta, stats } from "@/lib/db";
import { relativeTime, shortProject } from "@/lib/format";
import { fleet, globalHistory, repoState } from "@/lib/git";
import { describeRepo } from "@/lib/repo";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const TYPES = [
  { key: "semantic", label: "Semantic", color: "var(--type-semantic)" },
  { key: "procedural", label: "Procedural", color: "var(--type-procedural)" },
  { key: "episodic", label: "Episodic", color: "var(--type-episodic)" },
] as const;

export default async function OverviewPage() {
  const hasIndex = indexExists();
  const s = stats();
  const [commits, machines, repo] = await Promise.all([
    globalHistory(6),
    fleet(countsByMachine()),
    repoState(),
  ]);
  const recentNotes = listMeta({ limit: 5 });
  const { label: syncLabel, tone } = describeRepo(repo);

  const projects = Object.entries(s.byProject);
  const topProject = projects[0];
  const activeMachines = machines.filter((m) => m.lastSync).length;
  const head = commits[0];
  const pct = (x: number) => (s.total ? (x / s.total) * 100 : 0);

  return (
    <div className="animate-rise space-y-4 md:space-y-5">
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

      {/* HERO */}
      <section
        className="relative overflow-hidden rounded-3xl p-6 md:p-10"
        style={{
          background: "var(--hero-bg)",
          border: "var(--hero-border)",
          boxShadow: "var(--hero-shadow)",
        }}
      >
        <HeroCanvas />
        <div
          className="animate-float-orb pointer-events-none absolute -right-10 -top-10 size-60 rounded-full"
          style={{ background: "radial-gradient(circle, oklch(0.62 0.2 290 / .3), transparent 70%)", filter: "blur(10px)" }}
          aria-hidden
        />
        <div className="relative flex flex-col gap-8 lg:flex-row lg:justify-between">
          <div className="min-w-0 flex-1">
            <div className="mb-4 flex items-center gap-2.5">
              <span className="text-[10.5px] font-bold uppercase tracking-[0.22em]" style={{ color: "var(--hero-eyebrow)" }}>
                Memory
              </span>
              <span className="size-1 rounded-full" style={{ background: "var(--hero-faint)" }} />
              <span className="text-[10.5px] uppercase tracking-[0.18em]" style={{ color: "var(--hero-faint)" }}>
                live · cross-machine
              </span>
            </div>
            <h1 className="font-display text-3xl font-semibold tracking-tight md:text-[2.4rem]" style={{ color: "var(--hero-ink)" }}>
              Overview
            </h1>
            <p className="mt-2 max-w-md text-sm leading-relaxed" style={{ color: "var(--hero-sub)" }}>
              A cross-machine, file-first memory layer for Claude Code, versioned, synced, and
              browsed like git.
            </p>

            <div className="mt-7 flex items-end gap-4">
              <CountUp
                value={s.total}
                className="font-mono text-[56px] font-semibold leading-none tracking-tighter md:text-[68px]"
                style={{ color: "var(--hero-num)", textShadow: "var(--hero-num-shadow)" }}
              />
              <span className="pb-2 text-xs leading-tight" style={{ color: "var(--hero-sub)" }}>
                memories
                <br />
                in the lattice
              </span>
            </div>

            <div className="mt-6 max-w-md">
              <div className="flex h-2.5 overflow-hidden rounded-full" style={{ background: "var(--hero-track)" }}>
                {TYPES.map((t) => (
                  <div key={t.key} style={{ width: `${pct(s.byType[t.key] ?? 0)}%`, background: t.color }} />
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
                {TYPES.map((t) => (
                  <div key={t.key} className="flex items-center gap-1.5">
                    <span className="size-2 rounded-sm" style={{ background: t.color }} />
                    <span className="text-xs" style={{ color: "var(--hero-sub)" }}>{t.label}</span>
                    <span className="font-mono text-xs font-semibold" style={{ color: "var(--hero-strong)" }}>
                      {s.byType[t.key] ?? 0}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <aside
            className="flex w-full shrink-0 flex-col gap-2.5 rounded-2xl p-[18px] backdrop-blur-md lg:w-[248px]"
            style={{ background: "var(--hero-panel)", border: "1px solid var(--hero-panel-line)" }}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-[0.18em]" style={{ color: "var(--hero-faint)" }}>
                Sync state
              </span>
              <span className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--ok)" }}>
                <StatusDot tone={tone} pulse={tone === "danger"} />
                {syncLabel}
              </span>
            </div>
            <div className="h-px" style={{ background: "var(--hero-panel-line)" }} />
            {[
              ["Machines", String(machines.length)],
              ["Head", repo.head || "-"],
              ["Ahead / behind", `${repo.ahead} / ${repo.behind}`],
            ].map(([k, v]) => (
              <div key={k} className="flex items-center justify-between">
                <span className="text-xs" style={{ color: "var(--hero-sub)" }}>{k}</span>
                <span className="font-mono text-xs font-semibold" style={{ color: "var(--hero-strong)" }}>{v}</span>
              </div>
            ))}
            <div className="flex flex-col gap-0.5">
              <span className="text-xs" style={{ color: "var(--hero-sub)" }}>Remote</span>
              <span className="break-all font-mono text-[10.5px]" style={{ color: "var(--hero-faint)" }}>
                {repo.remote ?? "local only"}
              </span>
            </div>
            <Link
              href="/machines"
              className="tap mt-1 flex h-8 items-center justify-center gap-1.5 rounded-lg text-xs font-medium transition-colors hover:bg-accent-tint"
              style={{ border: "1px solid var(--hero-panel-line)", color: "var(--hero-strong)" }}
            >
              View fleet <ArrowUpRight size={13} strokeWidth={2} />
            </Link>
          </aside>
        </div>
      </section>

      {/* STAT STRIP */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
        <StatCard label="Projects" value={String(projects.length)}>
          {topProject ? `${shortProject(topProject[0])} leads · ${topProject[1]} notes` : "no projects yet"}
        </StatCard>
        <StatCard label="Machines" value={String(machines.length)}>
          <span className="text-ok">{activeMachines} active</span> in the fleet
        </StatCard>
        <StatCard label="Head" value={repo.head || "-"} valueClass="font-mono text-xl text-accent">
          {head ? `latest by ${head.machineId}` : "no commits yet"}
        </StatCard>
        <StatCard
          label="Last sync"
          value={head ? relativeTime(head.date) : "-"}
          valueClass="text-xl"
        >
          {head ? `from ${head.machineId}` : "never synced"}
        </StatCard>
      </div>

      {/* MEMORY MAP (filled in by the 3D map step) */}
      <section>
        <div className="mb-3 flex items-end justify-between px-0.5">
          <h2 className="flex items-center gap-2 font-display text-[15px] font-semibold">
            <Network size={17} strokeWidth={1.6} className="text-accent" /> Memory map
          </h2>
          <span className="hidden text-[11.5px] text-faint sm:block">
            drag to pan · scroll to zoom · click a node
          </span>
        </div>
        <div
          className="relative flex h-[60vh] max-h-[520px] min-h-[360px] items-center justify-center overflow-hidden rounded-3xl border border-line shadow-[var(--shadow)]"
          style={{
            background:
              "radial-gradient(120% 120% at 50% 38%, color-mix(in oklab, var(--accent) 8%, var(--surface)), var(--surface))",
          }}
        >
          <span className="text-sm text-faint">3D memory map loads here</span>
        </div>
      </section>

      {/* TWO COLUMN */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.55fr_1fr]">
        <div>
          <div className="mb-3 flex items-center justify-between px-1">
            <h2 className="flex items-center gap-2 font-display text-[15px] font-semibold text-text">
              <GitCommitVertical size={16} strokeWidth={1.6} className="text-accent" /> Recent syncs
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
            <h2 className="font-display text-[15px] font-semibold text-text">Recently updated</h2>
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

function StatCard({
  label,
  value,
  valueClass = "font-mono text-3xl",
  children,
}: {
  label: string;
  value: string;
  valueClass?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="has-reveal lift cursor-default rounded-2xl border border-line bg-surface p-[18px] shadow-[var(--shadow)] hover:border-line-strong">
      <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">{label}</span>
      <p className={`mt-2 font-semibold tracking-tight text-text ${valueClass}`}>{value}</p>
      <div className="reveal">
        <div>
          <p className="mt-2 border-t border-dashed border-line pt-2 text-[11px] text-muted">{children}</p>
        </div>
      </div>
    </div>
  );
}
