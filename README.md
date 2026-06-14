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

## Status

🚧 **Pre-alpha - under active construction.** The architecture is settled and the build is underway.
Installation instructions and the first release are coming soon. Watch/star to follow along.

## Repository layout

| Path          | What                                                                 |
| ------------- | -------------------------------------------------------------------- |
| `server/`     | The MCP memory server (Python, [FastMCP](https://github.com/jlowin/fastmcp)). |
| `dashboard/`  | The git-like memory GUI (Next.js).                                   |
| `scripts/`    | Dev & ops helper scripts.                                            |

## Contributing

Issues and discussion are welcome. Contribution guidelines will land alongside the first release.

## License

[Apache License 2.0](./LICENSE) - see [`NOTICE`](./NOTICE).
