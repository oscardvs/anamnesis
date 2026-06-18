<div align="center">

# Anamnesis

**Cross-machine memory for Claude Code - that just works.**

*Your coding agent's memory, written on your desktop, already on your laptop 1,000 km away.*

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange.svg)](#status)

</div>

---

> **ἀνάμνησις** *(anamnesis)* - Greek for *recollection*; the act of calling knowledge back to mind.

Anamnesis is a **local-first, file-based memory layer for [Claude Code](https://claude.com/claude-code)** that
syncs automatically across all of *your own* machines. Everything Claude learns about your projects -
conventions, architecture decisions, fixes that worked, what you did yesterday - is captured as plain
markdown, indexed for fast retrieval, and kept in sync across your fleet over your private network.

No cloud account required. Your memory stays on your machines, version-controlled, human-readable, and yours.

## The problem

Claude Code's memory is trapped on one machine. Move to your laptop and it starts from zero. The existing
fixes - syncing a SQLite file through Dropbox or iCloud - are fragile and corrupt the database. Cloud memory
APIs solve cross-*tool* sharing on a single device, but **nobody solves seamless background sync of a coding
agent's memory across the machines you already own.** That gap is Anamnesis.

## How it works

```
  ┌─────────────┐        git over your private mesh        ┌─────────────┐
  │  desktop    │  ◄────────────  (Tailscale)  ────────►   │  laptop     │
  │             │                                          │             │
  │  Claude Code│                                          │  Claude Code│
  │     ▼       │                                          │     ▼       │
  │  MCP server │   markdown (source of truth)             │  MCP server │
  │     ▼       │   + SQLite FTS index (rebuilt locally)   │     ▼       │
  │ ~/.anamnesis│                                          │ ~/.anamnesis│
  └─────────────┘                                          └─────────────┘
```

- **File-first.** Memory is markdown - human-readable, `git diff`-able, and exactly the shape the latest
  models are best at using. (The research is unambiguous that simple files beat heavyweight graph stores
  for this job; see the architecture notes.)
- **Structured where it counts.** A SQLite FTS5 index gives sub-millisecond keyword recall; optional vectors
  are added only when keyword search demonstrably falls short.
- **Robust sync.** Markdown is synced via git over your private [Tailscale](https://tailscale.com) mesh and
  the index is rebuilt locally - so the database file is never synced and never corrupts.
- **Claude-Code-native.** Ships as an MCP server with read-only auto-query tools, plus session hooks that
  surface relevant memory at the start of a session and capture durable notes at the end.
- **A git-like memory GUI.** A dashboard to browse, search, edit, and see the history of your memory across
  every machine.

## Quickstart

Anamnesis runs as a local MCP server over a store at `~/.anamnesis` (markdown notes plus a SQLite
index that is rebuilt locally).

```bash
cd server
uv venv --python 3.12
uv pip install -e ".[mcp,dev]"
```

Then wire this machine up in one command. `anamnesis init` registers the MCP server at user
scope, installs the SessionStart / SessionEnd / PreCompact hooks, configures the store and your
sync remote, and runs a first sync. It is idempotent (backs up `settings.json`, never duplicates
a hook) and `--print` shows the full plan without writing anything:

```bash
uv run anamnesis init            # interactive: confirm store dir, machine id, remote
uv run anamnesis init --print    # dry-run: show exactly what it would do
```

Once the package is published you will be able to do the whole thing in one line:
`uv tool install anamnesis && anamnesis init`.

The repo ships a project-scoped `.mcp.json` that registers the server with Claude Code, exposing five
tools: `memory_search` / `memory_list` / `memory_status` (read-only, auto-approvable), `memory_write`,
and `memory_sync`. Configure it via the server's `.mcp.json` `"env"` block - `ANAMNESIS_HOME`,
`ANAMNESIS_MACHINE_ID`, `ANAMNESIS_GIT_REMOTE` (Claude Code launches MCP servers with a filtered
environment, so shell exports are not inherited). Full server docs: [`server/README.md`](./server/README.md).

## Cross-machine sync

Memory is a git repo (`~/.anamnesis/memory/`) that syncs over your private
[Tailscale](https://tailscale.com) mesh. Markdown is the only thing synced; the SQLite index is rebuilt
locally on every machine, so the database file never travels and never corrupts.

Set it up once:

1. **Put every machine on the same tailnet.** Install [Tailscale](https://tailscale.com/download) on each
   machine and sign in to the same account (`tailscale up`). Pick one always-on machine (a desktop, a home
   server, a NAS) to host the shared repo and note its MagicDNS name, which `tailscale status` prints (for
   example `host.your-tailnet.ts.net`).

2. **Create one shared bare repo on the host node:**
   ```bash
   git init --bare -b main ~/anamnesis-memory.git
   ```
   Confirm you can reach it over SSH from your other machines (`ssh you@host.your-tailnet.ts.net` should log
   in; add your public key to the host's `~/.ssh/authorized_keys` if it does not).

3. **Point each machine at it** when you run the installer:
   ```bash
   uv run anamnesis init --remote 'you@host.your-tailnet.ts.net:anamnesis-memory.git'
   ```
   The host node itself can use a local path instead: `--remote "$HOME/anamnesis-memory.git"`.

`memory_sync` (and the background SessionStart sync hook) runs `commit -> pull --rebase -> push` and
rebuilds the local index after pulling, so a note written on one machine is searchable on the others within
a sync cycle. Diverging edits to the same note surface as a git conflict for you to resolve rather than
being silently dropped. Only markdown is synced; the database file is never synced, so it never corrupts.

Working on a single machine for now? Run `anamnesis init --local-only` and add a remote later by re-running
`init`; nothing else changes.

## Hands-off capture and sync (hooks)

Claude Code hooks make memory automatic, so the cross-machine round-trip needs zero manual steps:

- **SessionStart** injects the most relevant notes for the current project (your global preferences, plus
  the project's durable notes and a couple of recent session summaries) and kicks off a background sync.
- **SessionEnd** captures a durable episodic note from the session transcript (the ask, the files touched,
  the outcome) and syncs it, so it is on your other machines by the next session.
- **PreCompact** captures the same kind of note before the context is compacted, so nothing is lost.

`anamnesis init` (see Quickstart) installs these hooks for you. To set them up by hand instead,
copy [`examples/hooks.settings.json`](./examples/hooks.settings.json) into your per-machine
`~/.claude/settings.json` and replace `/ABSOLUTE/PATH/TO/anamnesis/server` with this machine's
checkout path. `settings.json` is per-machine and
is not synced, so each machine points at its own checkout. The thin `anamnesis` CLI the hooks call
(`inject` / `capture` / `sync` / `status`, alongside `serve`) reads the same `ANAMNESIS_*` configuration
as the server.

The session-end summary is deterministic by default and needs no API key; the summarization model is a
swappable config value (`ANAMNESIS_REFLECTION_PROVIDER`) for when a reflection model is plugged in later.

## Status

**Phase 0 works - the local-first core.** The file-first store, the FastMCP server
(`memory_search` / `list` / `status` / `write` / `sync`), and git-over-Tailscale sync are built,
tested, and validated on real hardware: a note written on the desktop is searchable on the laptop,
and a full personal corpus round-trips across machines. Auto-capture and auto-sync **session hooks**
(SessionStart inject plus background sync, SessionEnd and PreCompact capture) are built and tested, and a
one-command installer (`anamnesis init`) wires up the MCP server, hooks, store, and first sync.
**Next:** publishing to PyPI for a one-line install and the git-like dashboard.

> Pre-alpha: APIs and setup may still change. Watch/star to follow along.

## Repository layout

| Path          | What                                                                 |
| ------------- | -------------------------------------------------------------------- |
| `server/`     | The MCP memory server (Python, [FastMCP](https://gofastmcp.com)). |
| `dashboard/`  | The git-like memory GUI (Next.js).                                   |
| `scripts/`    | Dev & ops helper scripts.                                            |

## Contributing

Issues and discussion are welcome. Contribution guidelines will land alongside the first release.

## License

[Apache License 2.0](./LICENSE) - see [`NOTICE`](./NOTICE).
