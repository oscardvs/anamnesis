"use client";

import { useCallback, useEffect, useState } from "react";

import { Check, MonitorSmartphone, RefreshCw, TriangleAlert } from "lucide-react";
import { toast } from "sonner";

import { machineColor } from "@/components/commit-graph";
import { ReindexButton } from "@/components/reindex-button";
import { StatusDot } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";
import { Panel, Spinner } from "@/components/ui/misc";
import { absoluteTime, relativeTime } from "@/lib/format";
import { describeRepo } from "@/lib/repo";
import type { MachineInfo, RepoState } from "@/lib/types";

interface FleetData {
  machines: MachineInfo[];
  repo: RepoState;
}

export function MachinesView({ initial }: { initial: FleetData }) {
  const [data, setData] = useState<FleetData>(initial);
  const [syncing, setSyncing] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/fleet", { cache: "no-store" });
      setData((await res.json()) as FleetData);
    } catch {
      /* keep last known */
    }
  }, []);

  useEffect(() => {
    const id = setInterval(refresh, 20_000);
    return () => clearInterval(id);
  }, [refresh]);

  const onSync = async () => {
    setSyncing(true);
    try {
      const res = await fetch("/api/sync", { method: "POST" });
      const out = (await res.json()) as { conflicted: boolean; detail: string };
      if (out.conflicted) toast.error("Sync conflict", { description: out.detail });
      else toast.success("Synced", { description: out.detail || "up to date" });
      await refresh();
    } catch {
      toast.error("Sync failed", { description: "Could not reach the anamnesis CLI." });
    } finally {
      setSyncing(false);
    }
  };

  const { machines, repo } = data;
  const status = describeRepo(repo);
  const totalNotes = machines.reduce((sum, m) => sum + m.noteCount, 0);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="inline-flex items-center gap-2 rounded-full bezel bg-surface-2 px-3 py-1.5">
          <StatusDot tone={status.tone} pulse={status.tone === "danger"} />
          <span className="text-sm font-medium text-text">{status.label}</span>
          {repo.remote && (
            <span className="font-mono text-[11px] text-faint">· {repo.head}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <ReindexButton variant="secondary" />
          <Button variant="primary" onClick={onSync} disabled={syncing}>
            {syncing ? <Spinner /> : <RefreshCw strokeWidth={1.5} />} Sync now
          </Button>
        </div>
      </div>

      {repo.conflicted && (
        <Panel className="space-y-2 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-danger">
            <TriangleAlert size={16} strokeWidth={1.5} /> Sync conflict
          </div>
          <p className="text-xs text-muted">
            Last-writer-wins could not auto-merge these notes. Resolve them in the memory repo
            (markdown is the source of truth), then sync again.
          </p>
          <ul className="space-y-1 pt-1">
            {repo.conflictedPaths.map((p) => (
              <li key={p} className="font-mono text-[12px] text-del">
                {p}
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {machines.map((m) => (
          <Panel
            key={m.machineId}
            className="lift has-reveal cursor-default p-4 transition-[transform,box-shadow,border-color] hover:border-line-strong"
          >
            <div className="flex items-center justify-between">
              <div className="flex min-w-0 items-center gap-2">
                <span
                  className="flex size-7 shrink-0 items-center justify-center rounded-lg"
                  style={{ background: `${machineColor(m.machineId)}26` }}
                >
                  <MonitorSmartphone
                    size={15}
                    strokeWidth={1.5}
                    style={{ color: machineColor(m.machineId) }}
                  />
                </span>
                <span className="truncate font-medium text-text">{m.machineId}</span>
              </div>
              {m.isCurrent && (
                <span className="inline-flex items-center gap-1 rounded-full bg-accent-tint px-1.5 py-0.5 text-[10px] font-medium text-accent">
                  <Check size={10} strokeWidth={2.5} /> this machine
                </span>
              )}
            </div>
            <div className="mt-4 flex items-end justify-between">
              <div>
                <p className="font-mono text-2xl font-semibold tracking-tight text-text">
                  {m.noteCount}
                </p>
                <p className="text-[11px] text-faint">notes</p>
              </div>
              <div className="text-right">
                <p className="text-xs text-muted" title={m.lastSync ? absoluteTime(m.lastSync) : ""}>
                  {m.lastSync ? relativeTime(m.lastSync) : "never synced"}
                </p>
                {m.lastCommit && <p className="font-mono text-[11px] text-faint">{m.lastCommit}</p>}
              </div>
            </div>
            <div className="reveal">
              <div>
                <div className="mt-3 border-t border-dashed border-line pt-3">
                  <div className="mb-1.5 flex justify-between text-[10.5px] text-faint">
                    <span>share of store</span>
                    <span className="font-mono text-muted">
                      {totalNotes ? Math.round((m.noteCount / totalNotes) * 100) : 0}%
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
                    <div
                      className="bg-accent-gradient h-full rounded-full"
                      style={{ width: `${totalNotes ? (m.noteCount / totalNotes) * 100 : 0}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </Panel>
        ))}
      </div>

      <Panel className="px-4 py-2">
        <dl className="divide-y divide-line text-sm">
          <div className="flex items-center justify-between py-2.5">
            <dt className="text-muted">Remote</dt>
            <dd className="font-mono text-[12px] text-text">{repo.remote ?? "local only"}</dd>
          </div>
          <div className="flex items-center justify-between py-2.5">
            <dt className="text-muted">Head</dt>
            <dd className="font-mono text-[12px] text-text">{repo.head || "-"}</dd>
          </div>
          <div className="flex items-center justify-between py-2.5">
            <dt className="text-muted">Ahead / behind remote</dt>
            <dd className="font-mono text-[12px] text-text">
              {repo.ahead} / {repo.behind}
            </dd>
          </div>
          <div className="flex items-center justify-between py-2.5">
            <dt className="text-muted">Uncommitted changes</dt>
            <dd className="font-mono text-[12px] text-text">{repo.dirty ? "yes" : "no"}</dd>
          </div>
        </dl>
      </Panel>
    </div>
  );
}
