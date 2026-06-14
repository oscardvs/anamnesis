# anamnesis (server)

The Anamnesis **MCP memory server** for Claude Code. Python + [FastMCP](https://gofastmcp.com).

Markdown files are the source of truth; a local SQLite (WAL + FTS5) index is derived from them
and can always be rebuilt. See the (local-only) `docs/architecture.md` and `docs/roadmap.md` for
the design and Phase-0 plan.

## MCP tools

| Tool             | Signature                                          | Approval            |
| ---------------- | -------------------------------------------------- | ------------------- |
| `memory_search`  | `(query, project?, type?, k=8)` -> ranked notes    | read-only           |
| `memory_list`    | `(project?, type?)` -> titles + metadata           | read-only           |
| `memory_status`  | `()` -> counts, store paths, sync state            | read-only           |
| `memory_write`   | `(type, title, body, project="global", tags?)`     | write - confirm     |
| `memory_sync`    | `(force=False)` -> stub until the sync layer lands | write - confirm     |

Read-only query tools carry the `readOnlyHint` annotation so a client can auto-approve them; the
write tool is flagged for confirmation. `type` is one of `procedural` / `semantic` / `episodic`.

## Run it

The server reads its store root from `ANAMNESIS_HOME` (default `~/.anamnesis`) and the
machine-of-origin for writes from `ANAMNESIS_MACHINE_ID` (default the hostname).

```bash
# from server/
uv venv --python 3.12
uv pip install -e ".[mcp,dev]"
anamnesis            # serves over stdio (Ctrl-C to stop)
```

### Register with Claude Code

The repo ships a project-scoped `.mcp.json` that launches the server:

```json
{
  "mcpServers": {
    "anamnesis": { "command": "uv", "args": ["run", "--project", "server", "anamnesis"] }
  }
}
```

To override `ANAMNESIS_HOME` / `ANAMNESIS_MACHINE_ID`, set them in that server's `"env"` block.
Claude Code launches MCP servers with a filtered environment, so shell exports are **not**
inherited - the `"env"` block is the place to set them.

## Development

```bash
# from server/
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy src
uv run pytest
```

> Machine-local note: if this host sources ROS 2 (it puts `launch_testing` on `PYTHONPATH`),
> run tests isolated from it: `PYTHONPATH= PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest`.

## Storage layout (runtime)

Memory lives in `~/.anamnesis/` (never in this repo):

```
~/.anamnesis/
├── memory/            # markdown notes - the source of truth (a git repo)
│   └── <type>/<id>.md
└── index.db           # SQLite FTS5 index - rebuilt locally, never synced
```
