import Link from 'next/link';
import { CopyCommand } from '@/components/copy-command';
import { repoUrl, docsRoute } from '@/lib/shared';
import { Icon, ICONS } from './icons';

/* The hero diagram: two machines, the same note, one private mesh between them. */
function MeshCard() {
  return (
    <div className="bezel lift sheen relative overflow-hidden rounded-2xl bg-surface p-6">
      <div className="flex items-center gap-2 border-b border-line pb-3">
        <span className="h-2.5 w-2.5 rounded-full bg-fd-foreground/15" />
        <span className="h-2.5 w-2.5 rounded-full bg-fd-foreground/15" />
        <span className="h-2.5 w-2.5 rounded-full bg-fd-foreground/15" />
        <span className="ml-2 font-mono text-[0.7rem] uppercase tracking-[0.14em] text-fd-muted-foreground">
          ~/.anamnesis/memory
        </span>
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 py-6">
        <Node label="desktop" sub="Amsterdam" />
        <div className="flex flex-col items-center gap-1 text-fd-muted-foreground">
          <Icon path={ICONS.sync} size={22} className="animate-float-orb text-accent" />
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.12em]">git over Tailscale</span>
        </div>
        <Node label="laptop" sub="on the train" />
      </div>

      <div className="rounded-xl bg-surface-2 p-4 font-mono text-[0.78rem] leading-relaxed">
        <p className="text-fd-muted-foreground">## [semantic] Postgres connection pooling</p>
        <p className="mt-1 text-fd-foreground">
          Use a single pool per process. The 25-connection cap was the cause of the
          Friday timeout.
        </p>
        <p className="mt-2 text-accent">written on desktop · already searchable on laptop</p>
      </div>
    </div>
  );
}

function Node({ label, sub }: { label: string; sub: string }) {
  return (
    <div className="bezel rounded-xl bg-surface-2 px-3 py-3 text-center">
      <p className="font-display text-sm tracking-tight text-fd-foreground">{label}</p>
      <p className="font-mono text-[0.62rem] uppercase tracking-[0.12em] text-fd-muted-foreground">
        {sub}
      </p>
    </div>
  );
}

export function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-line">
      {/* soft accent glow behind the headline */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 left-1/2 h-[36rem] w-[36rem] -translate-x-1/2 rounded-full opacity-60 blur-3xl"
        style={{ background: 'radial-gradient(circle, var(--accent-tint), transparent 65%)' }}
      />
      <div className="relative mx-auto grid max-w-6xl items-center gap-14 px-6 py-24 md:grid-cols-[1.05fr_minmax(0,0.95fr)] md:py-32">
        <div>
          <span className="animate-rise inline-flex items-center gap-2 rounded-full bezel bg-surface/70 px-3 py-1 font-mono text-[0.7rem] uppercase tracking-[0.16em] text-accent">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Open source memory for Claude Code
          </span>

          <h1
            className="animate-rise mt-6 text-balance font-display text-[2.6rem] leading-[1.05] tracking-tight sm:text-6xl"
            style={{ animationDelay: '60ms' }}
          >
            Memory for Claude Code that follows you across your machines.
          </h1>

          <p
            className="animate-rise mt-6 max-w-xl text-lg leading-relaxed text-fd-muted-foreground"
            style={{ animationDelay: '140ms' }}
          >
            Anamnesis is a file-first memory layer for Claude Code. What your agent learns
            (your conventions, decisions, and fixes that worked) is captured as markdown,
            indexed locally, and synced across the machines you already own.
          </p>

          <p
            className="animate-rise mt-5 max-w-xl border-l-2 border-accent/40 pl-4 text-base leading-relaxed text-fd-foreground"
            style={{ animationDelay: '200ms' }}
          >
            Write a note on your desktop in Amsterdam. Open your laptop on the train, and the
            memory is already there. No copy-paste, no re-explaining, no cloud account.
          </p>

          <div
            className="animate-rise mt-8 flex flex-wrap items-center gap-3"
            style={{ animationDelay: '280ms' }}
          >
            <Link
              href={docsRoute}
              className="tap sheen inline-flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2.5 font-medium text-accent-contrast"
            >
              Read the docs
              <Icon path={ICONS.arrow} size={18} />
            </Link>
            <Link
              href={repoUrl}
              target="_blank"
              rel="noreferrer"
              className="tap bezel inline-flex items-center gap-2 rounded-full bg-surface/70 px-5 py-2.5 font-medium text-fd-foreground transition-colors hover:border-accent/40"
            >
              <Icon path={ICONS.github} size={18} className="text-fd-muted-foreground" />
              View on GitHub
            </Link>
          </div>

          <p
            className="animate-rise mt-6 font-mono text-[0.72rem] uppercase tracking-[0.12em] text-fd-muted-foreground"
            style={{ animationDelay: '340ms' }}
          >
            Apache-2.0 · Local-first · Pre-alpha
          </p>
        </div>

        <div className="animate-rise" style={{ animationDelay: '180ms' }}>
          <MeshCard />
        </div>
      </div>
    </section>
  );
}
