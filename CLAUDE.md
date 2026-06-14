# CLAUDE.md - working in the Anamnesis repo

Guidance for Claude Code (and contributors' agents) working in this repository.

## What this is

**Anamnesis** is a cross-machine, file-first **memory layer for Claude Code**. Memory is stored as markdown
(source of truth) + a SQLite FTS5 index (rebuilt locally), synced across a user's own machines via **git over
a Tailscale mesh**, exposed to Claude Code via an **MCP server**, and browsed through a git-like **Next.js**
dashboard. Open-core: the local-first core is Apache-2.0.

## Architecture decisions (do not relitigate without evidence)

- **File-first, not graph.** Markdown is the source of truth. We do **not** build a knowledge-graph memory or
  a custom context compressor for v1 - the research shows files + keyword search are competitive and graphs
  add cost without proportional benefit. Revisit only if recall quality on real usage demonstrably suffers.
- **SQLite is first-class, not an afterthought.** FTS5 for keyword/BM25 recall; use **WAL mode** so multiple
  concurrent Claude Code sessions don't hit file-locking conflicts. Add `sqlite-vec` vectors only when
  keyword search measurably fails on paraphrase queries.
- **Never sync the raw DB file** over cloud folders (the claude-brain corruption lesson). Sync **markdown via
  git**; rebuild the index locally on each machine.
- **Sync evolution:** git-as-sync for the MVP → Turso/libSQL embedded replicas when multi-user lands → CRDTs
  only if true concurrent multi-writer editing appears.
- **The reflection/compression model is swappable.** Never hardcode it - the price/quality frontier moves
  weekly (see `docs/research/model-landscape.md`, local-only).

## Repository layout

- `server/` - Python MCP server (FastMCP). Package source in `server/src/anamnesis/`, tests in `server/tests/`.
- `dashboard/` - Next.js App Router dashboard (the memory GUI).
- `scripts/` - helper scripts.
- `docs/` - **PRIVATE, git-ignored, local-only.** Roadmap, architecture, business case, market analysis, and
  research live here. They are the source of truth for *why* and *what next* - **read them locally before
  planning work.** Never commit anything under `docs/`.

## Conventions

**Python (`server/`)**
- Target Python ≥ 3.11. Prefer **`uv`** for envs/installs (`uv venv`, `uv pip install -e ".[dev]"`).
- Lint/format with **ruff**; type-check with **mypy**; test with **pytest**.
- Keep MCP tools small and well-documented; read-only query tools should be safe to auto-approve.

**TypeScript (`dashboard/`)**
- Next.js **App Router**. Keep the dashboard a thin read/write client over the local memory store/API.

**General**
- Match the style of surrounding code. Small, reviewable commits. Tests alongside behavior changes.
- Don't introduce a database server, a graph DB, or a vector DB "just in case" - stay local-first and simple.

## Staying current

This project tracks a fast-moving field. `docs/research/model-landscape.md` (local-only) is the living record
of current models/techniques and the triggers that would change our architecture. Keep it fresh; prefer
verifying model/pricing/benchmark facts against current sources over relying on training data.

## Privacy boundary

The repo is **public**; our strategy is **not**. `docs/`, `private/`, `*.private.md`, and `NOTES.local.md` are
git-ignored. Before any commit, sanity-check `git status` to confirm nothing under `docs/` is staged.
