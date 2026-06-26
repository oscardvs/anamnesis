import { CopyCommand } from '@/components/copy-command';
import { pipPackage } from '@/lib/shared';
import { Reveal } from './reveal';

export function InstallPill() {
  return (
    <section className="mx-auto w-full max-w-6xl px-6 py-16">
      <Reveal>
        <div className="bezel flex flex-col items-center gap-5 rounded-2xl bg-surface px-6 py-10 text-center">
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">Install</p>
          <h2 className="max-w-xl text-balance font-display text-2xl tracking-tight sm:text-3xl">
            One line wires up this machine.
          </h2>
          <CopyCommand className="mt-1" />
          <p className="max-w-2xl text-sm leading-relaxed text-fd-muted-foreground">
            The PyPI package is <code className="font-mono text-fd-foreground">{pipPackage}</code>; the
            command it installs is <code className="font-mono text-fd-foreground">anamnesis</code>. Then{' '}
            <code className="font-mono text-fd-foreground">anamnesis init</code> registers the MCP server,
            installs the hooks, and runs a first sync. See the docs for from-source and air-gapped setups.
          </p>
        </div>
      </Reveal>
    </section>
  );
}
