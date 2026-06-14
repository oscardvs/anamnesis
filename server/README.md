# anamnesis (server)

The Anamnesis **MCP memory server** for Claude Code. Python + [FastMCP](https://gofastmcp.com).

Markdown files are the source of truth; a local SQLite (WAL + FTS5) index is derived from them and
can always be rebuilt. Memory syncs across your own machines as a git repo over a private Tailscale
mesh; the index is never synced (it is rebuilt locally). See the (local-only) `docs/architecture.md`
and `docs/roadmap.md` for the full design.

## MCP tools

| Tool             | Signature                                       | Approval        |
| ---------------- | ----------------------------------------------- | --------------- |
| `memory_search`  | `(query, project?, type?, k=8)` -> ranked notes | read-only       |
| `memory_list`    | `(project?, type?)` -> titles + metadata        | read-only       |
| `memory_status`  | `()` -> counts, store paths, git sync state     | read-only       |
| `memory_write`   | `(type, title, body, project="global", tags?)`  | write - confirm |
| `memory_sync`    | `(force=False)` -> commit, pull --rebase, push  | write - confirm |

Read-only query tools carry the `readOnlyHint` annotation so a client can auto-approve them; writes
are flagged for confirmation. `type` is one of `procedural` / `semantic` / `episodic`. `memory_sync`
rebuilds the local index after pulling, so notes from other machines are immediately searchable.

## Configuration (environment)

| Variable               | Default        | Purpose                                          |
| ---------------------- | -------------- | ------------------------------------------------ |
| `ANAMNESIS_HOME`       | `~/.anamnesis` | Store root (`memory/` markdown + `index.db`).    |
| `ANAMNESIS_MACHINE_ID` | the hostname   | Machine-of-origin stamped on notes you write.    |
| `ANAMNESIS_GIT_REMOTE` | (unset)        | Git remote for sync; unset = local commits only. |

## Run it

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

Set `ANAMNESIS_HOME` / `ANAMNESIS_MACHINE_ID` / `ANAMNESIS_GIT_REMOTE` in that server's `"env"`
block. Claude Code launches MCP servers with a filtered environment, so shell exports are **not**
inherited - the `"env"` block is the place to set them. Keep your real `ANAMNESIS_GIT_REMOTE` out of
the public repo (use a local or user-scoped MCP config).

## Cross-machine sync (git over Tailscale)

Memory is a git repo (`~/.anamnesis/memory/`) pushed and pulled over your
[Tailscale](https://tailscale.com) mesh. Point every machine at one shared **bare** repo (on an
always-on node, or peer-to-peer):

```bash
# once, on the node that hosts the shared repo:
git init --bare -b main ~/anamnesis-memory.git

# on each machine (Tailscale MagicDNS resolves the node name on your tailnet):
export ANAMNESIS_GIT_REMOTE='you@host.your-tailnet.ts.net:anamnesis-memory.git'
```

Then `memory_sync` (commit -> pull --rebase -> push) keeps every machine in step. The SQLite index
is never pushed; it is rebuilt locally after each pull. On a same-note conflict, v0 surfaces it and
keeps your local edits rather than dropping either side.

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
├── memory/            # markdown notes - the source of truth (a git repo, synced)
│   └── <type>/<id>.md
└── index.db           # SQLite FTS5 index - rebuilt locally, never synced
```
