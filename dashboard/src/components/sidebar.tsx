"use client";

import { useEffect, useState } from "react";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { GitCommitVertical, LayoutDashboard, Library, Plus, Server, Sparkles } from "lucide-react";

import { BrandMark } from "@/components/brand-mark";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { shortProject } from "@/lib/format";

const NAV = [
  { label: "Overview", href: "/", icon: LayoutDashboard },
  { label: "Browse", href: "/browse", icon: Library },
  { label: "Review", href: "/review", icon: Sparkles },
  { label: "History", href: "/history", icon: GitCommitVertical },
  { label: "Machines", href: "/machines", icon: Server },
];

export function Sidebar() {
  const pathname = usePathname();
  const [projects, setProjects] = useState<[string, number][]>([]);
  const [pending, setPending] = useState(0);

  useEffect(() => {
    fetch("/api/overview", { cache: "no-store" })
      .then((r) => r.json())
      .then((d: { stats?: { byProject?: Record<string, number> }; pendingReflections?: number }) => {
        setProjects(Object.entries(d.stats?.byProject ?? {}));
        setPending(d.pendingReflections ?? 0);
      })
      .catch(() => {});
  }, []);

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <aside className="sticky top-0 z-20 hidden h-[100dvh] w-60 shrink-0 flex-col border-r border-line bg-surface/50 md:flex">
      <div className="flex h-14 items-center gap-2.5 px-5">
        <BrandMark className="size-6" />
        <span className="text-[15px] font-semibold tracking-tight">anamnesis</span>
      </div>

      <div className="px-3 pt-1">
        <Button variant="primary" className="w-full justify-start gap-2" asChild>
          <Link href="/notes/new">
            <Plus strokeWidth={1.75} /> New note
          </Link>
        </Button>
      </div>

      <nav className="mt-4 flex flex-col gap-0.5 px-3">
        {NAV.map((item) => {
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors duration-150",
                active ? "bg-highlight font-medium text-text" : "text-muted hover:bg-highlight hover:text-text",
              )}
            >
              <item.icon
                size={16}
                strokeWidth={1.5}
                className={active ? "text-accent" : "text-faint"}
              />
              {item.label}
              {item.href === "/review" && pending > 0 && (
                <span className="ml-auto inline-flex min-w-5 items-center justify-center rounded-full bg-warn/15 px-1.5 text-[10px] font-semibold text-warn">
                  {pending}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="mt-6 flex min-h-0 flex-1 flex-col px-3">
        <p className="px-2.5 pb-1.5 text-[10px] font-medium uppercase tracking-[0.14em] text-faint">
          Projects
        </p>
        <div className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto pb-3">
          {projects.map(([proj, count]) => (
            <Link
              key={proj}
              href={`/browse?project=${encodeURIComponent(proj)}`}
              className="flex items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-[13px] text-muted transition-colors hover:bg-highlight hover:text-text"
            >
              <span className="min-w-0 truncate">{shortProject(proj)}</span>
              <span className="shrink-0 font-mono text-[11px] text-faint">{count}</span>
            </Link>
          ))}
        </div>
      </div>

      <div className="border-t border-line px-5 py-3 text-[11px] text-faint">
        file-first memory · Apache-2.0
      </div>
    </aside>
  );
}
