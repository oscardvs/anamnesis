import { Reveal } from './reveal';

/* Screen-reader words for the glyph cells, so the table is not gibberish. */
const GLYPH_LABEL: Record<string, string> = {
  '✓': 'Yes',
  '✗': 'No',
  '~': 'Partial',
};

function Cell({ v, accent = false }: { v: string; accent?: boolean }) {
  const label = GLYPH_LABEL[v];
  const tone = accent ? 'text-accent' : 'text-fd-muted-foreground';
  if (label) {
    return (
      <span className={tone}>
        <span aria-hidden>{v}</span>
        <span className="sr-only">{label}</span>
      </span>
    );
  }
  return <span className={`text-xs ${tone}`}>{v}</span>;
}

type Row = [feature: string, anamnesis: string, builtin: string, nothing: string];

const ROWS: Row[] = [
  ['Memory persists between sessions', '✓', '✓', '✗'],
  ['Captured automatically at session end', '✓', '✗', '✗'],
  ['Injected automatically at session start', '✓', '~', '✗'],
  ['Syncs across your own machines', '✓', '✗', '✗'],
  ['Stored as markdown you own and can edit', '✓', '✓', '✗'],
  ['Keyword and BM25 search over all notes', '✓', '✗', '✗'],
  ['Browsable dashboard and history view', '✓', '✗', '✗'],
  ['No cloud account required', '✓', '✓', '✓'],
];

export function Comparison() {
  return (
    <section className="mx-auto w-full max-w-5xl px-6 py-24">
      <Reveal>
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">An honest comparison</p>
        <h2 className="mt-4 max-w-2xl font-display text-3xl tracking-tight sm:text-4xl">
          Anamnesis, built-in project memory, or nothing.
        </h2>
        <p className="mt-4 max-w-2xl text-fd-muted-foreground">
          Claude Code already supports per-project memory files (the CLAUDE.md you edit by hand).
          They are real and useful. They are also scoped to one project on one machine, and you
          maintain them yourself.
        </p>
      </Reveal>

      <Reveal delay={80}>
        <div className="bezel mt-10 overflow-x-auto rounded-2xl bg-surface">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">
              How Anamnesis compares to Claude Code built-in per-project memory and to using no memory layer
            </caption>
            <thead>
              <tr className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-fd-muted-foreground">
                <th scope="col" className="p-4 text-left font-medium">
                  <span className="sr-only">Capability</span>
                </th>
                <th scope="col" className="p-4 text-center font-medium text-accent">
                  Anamnesis
                </th>
                <th scope="col" className="p-4 text-center font-medium">
                  Built-in project memory
                </th>
                <th scope="col" className="p-4 text-center font-medium">
                  Nothing
                </th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((row) => (
                <tr key={row[0]} className="border-t border-line">
                  <th scope="row" className="p-4 text-left font-normal text-fd-foreground">
                    {row[0]}
                  </th>
                  <td className="p-4 text-center">
                    <Cell v={row[1]} accent />
                  </td>
                  <td className="p-4 text-center">
                    <Cell v={row[2]} />
                  </td>
                  <td className="p-4 text-center">
                    <Cell v={row[3]} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Reveal>

      <Reveal delay={120}>
        <p className="mt-5 max-w-3xl text-sm leading-relaxed text-fd-muted-foreground">
          The built-in injection cell is marked partial because Claude Code reads the project
          CLAUDE.md you keep current by hand. Anamnesis writes those notes for you and carries them
          to every machine you own.
        </p>
      </Reveal>
    </section>
  );
}
