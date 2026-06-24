import { Icon, ICONS } from './icons';
import { Reveal } from './reveal';

type Feature = {
  icon: string;
  label: string;
  title: string;
  body: string;
  span: string;
};

const FEATURES: Feature[] = [
  {
    icon: ICONS.file,
    label: 'file-first',
    title: 'Markdown you own',
    body: 'Every note is a plain markdown file under ~/.anamnesis/memory. Human-readable, git diff-able, and exactly the shape current models read best. The files are the source of truth, not a database you cannot inspect.',
    span: 'md:col-span-4',
  },
  {
    icon: ICONS.database,
    label: 'local-first',
    title: 'SQLite FTS5, no cloud',
    body: 'A SQLite FTS5 index gives keyword and BM25 recall, rebuilt locally on each machine. No cloud account, no API key required for the core.',
    span: 'md:col-span-2',
  },
  {
    icon: ICONS.machines,
    label: 'cross-machine',
    title: 'Git over your Tailscale mesh',
    body: 'Markdown syncs as a git repo over your own private Tailscale network. Only the markdown travels; the index is rebuilt on each machine, so the database file never syncs and never corrupts.',
    span: 'md:col-span-3',
  },
  {
    icon: ICONS.bolt,
    label: 'automatic',
    title: 'Injects at start, captures at end',
    body: 'A SessionStart hook injects your global preferences plus the project notes and recent session summaries. A SessionEnd hook (and PreCompact) captures a durable note: the ask, the files touched, the outcome.',
    span: 'md:col-span-3',
  },
  {
    icon: ICONS.shield,
    label: 'private',
    title: 'Machine-local scope',
    body: 'settings.json is per-machine and is never synced, so each machine points at its own checkout. The session summarizer is deterministic by default and needs no API key.',
    span: 'md:col-span-3',
  },
  {
    icon: ICONS.map,
    label: 'browsable',
    title: 'Dashboard and 3D memory map',
    body: 'A git-like Next.js dashboard to browse, full-text search, edit, and read the history of every note across your fleet, plus a 3D memory map of how your notes connect.',
    span: 'md:col-span-3',
  },
];

export function FeatureBento() {
  return (
    <section id="why" className="mx-auto w-full max-w-6xl scroll-mt-20 px-6 py-24">
      <Reveal>
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">What you get</p>
        <h2 className="mt-4 max-w-2xl font-display text-3xl tracking-tight sm:text-4xl">
          A memory layer that stays yours.
        </h2>
        <p className="mt-4 max-w-2xl text-fd-muted-foreground">
          File-first and local-first by design. Nothing leaves your machines except git commits over
          your own network.
        </p>
      </Reveal>

      <div className="mt-12 grid auto-rows-fr gap-4 md:grid-cols-6">
        {FEATURES.map((f, i) => (
          <Reveal key={f.title} delay={i * 60} className={f.span}>
            <div className="lift bezel group flex h-full flex-col gap-3 rounded-2xl bg-surface p-6">
              <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-accent-tint text-accent">
                <Icon path={f.icon} />
              </span>
              <p className="font-mono text-[0.68rem] uppercase tracking-[0.16em] text-fd-muted-foreground">
                {f.label}
              </p>
              <h3 className="font-display text-lg tracking-tight text-fd-foreground">{f.title}</h3>
              <p className="text-sm leading-relaxed text-fd-muted-foreground">{f.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
