import { Icon, ICONS } from './icons';
import { Reveal } from './reveal';

type Step = {
  n: string;
  icon: string;
  title: string;
  body: string;
};

const STEPS: Step[] = [
  {
    n: '01',
    icon: ICONS.terminal,
    title: 'Install once per machine',
    body: 'Run anamnesis init on each machine. It registers the MCP server, installs the SessionStart, SessionEnd, and PreCompact hooks, configures the store at ~/.anamnesis, and runs a first sync. It is idempotent and --print shows the plan without writing.',
  },
  {
    n: '02',
    icon: ICONS.bolt,
    title: 'Use Claude Code normally',
    body: 'Nothing changes in how you work. At session start, your global preferences and the project notes are injected. At session end (and before a compact), a durable note is captured: the ask, the files touched, the outcome.',
  },
  {
    n: '03',
    icon: ICONS.machines,
    title: 'Your memory follows you',
    body: 'Each sync runs commit, pull --rebase, push over your private Tailscale mesh and rebuilds the local index. A note written on one machine is searchable on the others within a sync cycle. Diverging edits surface as a git conflict, never silently dropped.',
  },
];

export function HowItWorks() {
  return (
    <section className="border-y border-line bg-surface/40">
      <div className="mx-auto w-full max-w-6xl px-6 py-24">
        <Reveal>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">How it works</p>
          <h2 className="mt-4 max-w-2xl font-display text-3xl tracking-tight sm:text-4xl">
            Install, use Claude normally, your memory follows you.
          </h2>
        </Reveal>

        <ol className="mt-12 grid gap-4 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <Reveal key={s.n} delay={i * 80} as="li">
              <div className="bezel lift row-acc flex h-full flex-col gap-4 rounded-2xl bg-surface p-6">
                <div className="flex items-center justify-between">
                  <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-accent-tint text-accent">
                    <Icon path={s.icon} />
                  </span>
                  <span className="font-mono text-2xl tracking-tight text-faint">{s.n}</span>
                </div>
                <h3 className="font-display text-lg tracking-tight text-fd-foreground">{s.title}</h3>
                <p className="text-sm leading-relaxed text-fd-muted-foreground">{s.body}</p>
              </div>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}
