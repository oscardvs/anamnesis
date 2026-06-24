import Link from 'next/link';
import { repoUrl, docsRoute, appName } from '@/lib/shared';
import { Icon, ICONS } from './icons';
import { Wordmark } from '@/components/wordmark';

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-surface/40">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-6 py-16 md:flex-row md:items-start md:justify-between">
        <div className="max-w-sm">
          <Wordmark />
          <p className="mt-4 text-sm leading-relaxed text-fd-muted-foreground">
            ἀνάμνησις (anamnesis): Greek for recollection, the act of calling knowledge back to mind.
            A file-first, local-first memory layer for Claude Code.
          </p>
          <p className="mt-4 font-mono text-[0.72rem] uppercase tracking-[0.12em] text-fd-muted-foreground">
            Apache-2.0 · Open source
          </p>
        </div>

        <nav className="grid grid-cols-2 gap-x-12 gap-y-3 text-sm" aria-label="Footer">
          <div className="flex flex-col gap-3">
            <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-faint">Project</p>
            <Link href={docsRoute} className="text-fd-muted-foreground transition-colors hover:text-fd-foreground">
              Documentation
            </Link>
            <Link
              href="/#why"
              className="text-fd-muted-foreground transition-colors hover:text-fd-foreground"
            >
              Why Anamnesis
            </Link>
            <Link
              href={repoUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 text-fd-muted-foreground transition-colors hover:text-fd-foreground"
            >
              <Icon path={ICONS.github} size={16} />
              GitHub
            </Link>
          </div>
          <div className="flex flex-col gap-3">
            <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-faint">For agents</p>
            <Link
              href="/llms.txt"
              className="text-fd-muted-foreground transition-colors hover:text-fd-foreground"
            >
              llms.txt
            </Link>
            <Link
              href="/llms-full.txt"
              className="text-fd-muted-foreground transition-colors hover:text-fd-foreground"
            >
              llms-full.txt
            </Link>
          </div>
        </nav>
      </div>

      <div className="border-t border-line">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-2 px-6 py-6 text-xs text-fd-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>
            {appName}. Licensed under Apache-2.0. Memory stays on your machines, version-controlled
            and yours.
          </p>
          <Link
            href={repoUrl}
            target="_blank"
            rel="noreferrer"
            className="font-mono uppercase tracking-[0.1em] transition-colors hover:text-fd-foreground"
          >
            github.com/oscardvs/anamnesis
          </Link>
        </div>
      </div>
    </footer>
  );
}
