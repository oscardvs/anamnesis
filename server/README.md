# anamnesis (server)

The Anamnesis **MCP memory server** for Claude Code. Python + [FastMCP](https://github.com/jlowin/fastmcp).

> 🚧 Scaffold only - the server module is the first thing we build. See the (local-only)
> `docs/architecture.md` and `docs/roadmap.md` for the design and Phase-0 plan.

## Planned MCP tools

| Tool             | Purpose                                                        |
| ---------------- | -------------------------------------------------------------- |
| `memory_search`  | Keyword/BM25 search over memory (FTS5), scoped by project.     |
| `memory_write`   | Write a durable memory note (markdown + indexed metadata).     |
| `memory_list`    | List memories for a project.                                   |
| `memory_sync`    | Pull/push the markdown store over git (Tailscale).             |
| `memory_status`  | Sync status, machine list, last-sync timestamps.               |

Read-only query tools (`memory_search`, `memory_list`, `memory_status`) are designed to be safe to
auto-approve so memory "just works" at session start.

## Development

```bash
# from server/
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

ruff check . && ruff format --check .
mypy src
pytest
```

## Storage layout (runtime)

Memory lives in `~/.anamnesis/` (never in this repo):

```
~/.anamnesis/
├── memory/            # markdown notes - the source of truth (a git repo)
│   └── <project>/...
└── index.db           # SQLite FTS5 index - rebuilt locally, never synced
```
