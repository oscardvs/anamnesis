# dashboard

The Anamnesis **memory GUI**: a git-like visual interface for your cross-machine memory. A thin
read/write client over the local store, built with Next.js (App Router).

It does not own any data. Markdown files under `~/.anamnesis/memory` are the source of truth, the
SQLite FTS5 index is derived, and the git history of that folder is the memory history. No business
logic lives here that the Python server does not also enforce.

## Features (Phase 1)

- **Browse + full-text search** over every note, backed by the SQLite FTS5 (BM25) index, plus a
  Cmd-K command palette.
- **Note view** with rendered markdown and the full YAML front-matter metadata.
- **Git-like history**: a per-note and global commit graph driven by the real git log, with the diff
  each version introduced.
- **Machines / fleet view**: every machine that has synced into the store (derived from commit
  authorship), with last-sync timestamps and a sync-status badge.
- **Create + edit** notes that write back to markdown, commit locally to the memory repo, and trigger
  a reindex. A separate **Sync** action runs pull/push and surfaces last-writer-wins conflicts.

## Running it

```bash
npm install
npm run dev      # http://localhost:3000
# production:
npm run build && npm run start
```

It reads the same store the Python server uses. Configuration is by environment variable:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANAMNESIS_HOME` | `~/.anamnesis` | Store root (markdown + `index.db`). |
| `ANAMNESIS_MACHINE_ID` | hostname | Machine id stamped on dashboard-authored commits. |
| `ANAMNESIS_GIT_REMOTE` | unset | Passed through to `anamnesis sync`; unset means commit locally only. |
| `ANAMNESIS_CLI` | (derived) | Full CLI command prefix, e.g. `anamnesis`. Overrides the default below. |
| `ANAMNESIS_UV` | `uv` | uv binary used for the default `uv run --project ../server anamnesis`. |
| `ANAMNESIS_SERVER` | `../server` | Server project dir for the default uv invocation. |

Writes (create/edit, reindex, sync) shell out to the `anamnesis` CLI so the Python store stays the
single indexer. By default that is `uv run --project ../server anamnesis ...`, run from the dashboard
directory. Set `ANAMNESIS_CLI` if the CLI is installed elsewhere or on `PATH`.

## Install as an app

The dashboard is one Next.js server (`output: "standalone"`) delivered three ways. All three read the
machine-local `~/.anamnesis` store and need `git`, `uv`, `python`, and Node 20 present on any machine
that runs a server instance (runtimes are not bundled).

1. **Web (dev or local).** `npm run dev`, or `npm run build && npm run start`, then open
   http://localhost:3000.
2. **Phone + laptop over the tailnet (PWA).** Run one always-on instance on the hub and publish it
   tailnet-only with `tailscale serve`, then install it to a home screen. See `deploy/README.md`. In
   short: on iPhone open the tailnet URL in Safari and use Share, Add to Home Screen; on a laptop open
   it in Chrome or Edge and use Install app.
3. **Desktop app (Electron).** Build a packaged app:

   ```bash
   npm run desktop:build   # Linux: dist/*.AppImage and dist/*.deb
   ```

   Launch the AppImage (or install the deb). It runs its own local server against this machine's store,
   so it works offline for reads. The build pins Electron 34 (Node 20, V8 13.2) so the Node-20
   `better-sqlite3` native module compiles for Electron's ABI, then restores the Node-ABI build so the
   web flow keeps working.

Cross-platform: Linux is built and verified locally. macOS (dmg) and Windows (nsis) are produced by the
`desktop build` GitHub Actions workflow (`.github/workflows/desktop.yml`) and are shipped unsigned and
unverified until that hardware is available.

## Settings

The `/settings` page reads and writes `~/.anamnesis/config.json` (machine-local, never synced, mode
0600) via the `anamnesis config` CLI (`list`, `get`, `set`, `unset`, `test`). The reflection API key
is stored there and never shown in full - the page displays a masked preview with Replace and Clear
actions. Environment variables (e.g. `ANAMNESIS_REFLECTION_PROVIDER`) override the file when set.

## Testing

```bash
npm test         # vitest: front-matter codec, FTS match builder, diff, formatting
npm run lint
npm run typecheck
```

The codec tests pin byte-compatibility with the Python store's serializer (key order, single-quoted
timestamps, unindented tag sequences), so notes written here round-trip through `yaml.safe_load`
without timestamps being coerced to `datetime`.

## Choices (framework / libraries / styling)

Verified against current sources in June 2026.

- **Next.js 16 (App Router), React 19, Node.js runtime.** App Router is the repo standard and remains
  the recommended default; confirmed still current. Route handlers use the Node runtime (the default)
  because they read local SQLite, git, and the filesystem - never edge.
- **Tailwind v4 (CSS-first) + hand-built components.** A small set of shadcn-idiom primitives
  (`class-variance-authority` + `tailwind-merge`) gives full control over the dark "Console" aesthetic
  without a heavy component library. Focused primitives are pulled in only where they earn their keep:
  `cmdk` (Cmd-K), `react-markdown` + `remark-gfm` (note bodies), `lucide-react`, `next-themes`,
  `sonner`, and Radix `Slot` for polymorphic buttons.
- **Hand-rolled git visuals.** The sync history is mostly linear, so a small SVG commit-lane renderer
  and a `jsdiff`-based line-diff renderer are lighter, fully themeable, and React-19-native, versus the
  archived off-the-shelf gitgraph libraries.

## Data-layer decision

**Reads go straight to SQLite from Node; writes go through the Python CLI.**

- **Search and list** read the FTS5 index directly with `better-sqlite3` (opened read-only, with a
  `busy_timeout`, never changing `journal_mode`). This avoids spawning a Python process per request and
  keeps the hot path fast. The FTS5 MATCH expression is built with the same quote-and-AND rule as the
  Python `_fts_query`, so arbitrary input cannot break the query parser. `better-sqlite3` is pinned to
  `12.9.0`, the last release that ships Node 20 prebuilt binaries.
- **Content, history, and diffs** read markdown files and the git log/show directly (markdown is the
  source of truth; git is the history).
- **Writes** (create/edit) write the markdown file in the exact store format, commit it locally to the
  memory repo, then trigger a rebuild via a small `anamnesis reindex` CLI subcommand. Keeping the
  Python store as the single indexer means the dashboard never duplicates indexing logic, and edits
  appear in history immediately. Sync (pull/push) is a separate, explicit action so saving never does
  surprise network I/O; conflicts that last-writer-wins leaves behind surface in the machines view.
