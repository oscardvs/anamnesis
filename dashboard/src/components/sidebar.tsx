"use client";

import { useEffect, useState } from "react";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowUpRight,
  BookText,
  GitCommitVertical,
  LayoutDashboard,
  Library,
  Plus,
  Server,
  Sparkles,
  X,
} from "lucide-react";

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

/** Public documentation site (Fumadocs, deployed to GitHub Pages). */
const DOCS_URL = "https://oscardvs.github.io/anamnesis/docs";

function useOverviewMeta() {
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
  return { projects, pending };
}

/** The shared sidebar body, used by both the desktop rail and the mobile drawer. */
function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { projects, pending } = useOverviewMeta();
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <>
      <div className="flex h-14 items-center gap-2.5 px-5">
        <BrandMark className="size-7 shrink-0" />
        <div className="flex flex-col leading-none">
          <span className="font-display text-[15px] font-semibold tracking-tight">anamnesis</span>
          <span className="mt-0.5 text-[9px] font-medium uppercase tracking-[0.22em] text-faint">
            memory lattice
          </span>
        </div>
      </div>

      <div className="px-3 pt-1">
        <Button variant="primary" className="w-full justify-center gap-2" asChild>
          <Link href="/notes/new" onClick={onNavigate}>
            <Plus strokeWidth={2} /> New note
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
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors duration-150",
                active
                  ? "bg-accent-tint font-medium text-text"
                  : "text-muted hover:bg-highlight hover:text-text",
              )}
            >
              <item.icon
                size={16}
                strokeWidth={1.6}
                className={active ? "text-accent" : "text-faint"}
              />
              {item.label}
              {item.href === "/review" && pending > 0 && (
                <span className="ml-auto inline-flex min-w-5 items-center justify-center rounded-full bg-accent-tint px-1.5 text-[10px] font-semibold text-accent">
                  {pending}
                </span>
              )}
            </Link>
          );
        })}
        <a
          href={DOCS_URL}
          target="_blank"
          rel="noreferrer"
          onClick={onNavigate}
          className="group flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-muted transition-colors duration-150 hover:bg-highlight hover:text-text"
        >
          <BookText size={16} strokeWidth={1.6} className="text-faint" />
          Docs
          <ArrowUpRight
            size={13}
            strokeWidth={1.8}
            className="ml-auto text-faint opacity-0 transition-opacity group-hover:opacity-100"
          />
        </a>
      </nav>

      <div className="mt-6 flex min-h-0 flex-1 flex-col px-3">
        <div className="flex items-center justify-between px-2.5 pb-1.5">
          <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-faint">Projects</p>
          <span className="font-mono text-[10px] text-faint">{projects.length}</span>
        </div>
        <div className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto pb-3">
          {projects.map(([proj, count]) => (
            <Link
              key={proj}
              href={`/browse?project=${encodeURIComponent(proj)}`}
              onClick={onNavigate}
              className="flex items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-[13px] text-muted transition-colors hover:bg-accent-tint hover:text-text"
            >
              <span className="min-w-0 truncate">{shortProject(proj)}</span>
              <span className="shrink-0 font-mono text-[11px] text-faint">{count}</span>
            </Link>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-1.5 border-t border-line px-5 py-3 text-[11px] text-faint">
        <span className="size-1.5 rounded-full bg-ok" />
        file-first memory · Apache-2.0
      </div>
    </>
  );
}

/** Desktop rail: a sticky sidebar shown from the md breakpoint up. */
export function Sidebar() {
  return (
    <aside className="sticky top-0 z-20 hidden h-[100dvh] w-60 shrink-0 flex-col border-r border-line bg-gradient-to-b from-surface to-bg md:flex">
      <SidebarContent />
    </aside>
  );
}

/** Mobile drawer: slides in over the content, opened by the topbar hamburger. */
export function MobileNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className={cn("fixed inset-0 z-50 md:hidden", open ? "" : "pointer-events-none")}
      aria-hidden={!open}
    >
      <div
        onClick={onClose}
        className={cn(
          "absolute inset-0 bg-black/45 backdrop-blur-sm transition-opacity duration-300",
          open ? "opacity-100" : "opacity-0",
        )}
      />
      <aside
        className={cn(
          "absolute left-0 top-0 flex h-full w-[280px] max-w-[84%] flex-col border-r border-line bg-gradient-to-b from-surface to-bg shadow-2xl transition-transform duration-300 ease-[var(--ease-out-soft)]",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <button
          onClick={onClose}
          aria-label="Close menu"
          className="tap absolute right-3 top-4 z-10 flex size-8 items-center justify-center rounded-lg text-muted hover:bg-highlight hover:text-text"
        >
          <X size={16} strokeWidth={1.8} />
        </button>
        <SidebarContent onNavigate={onClose} />
      </aside>
    </div>
  );
}
