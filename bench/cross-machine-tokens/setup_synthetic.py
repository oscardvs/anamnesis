"""Create the synthetic quotes-api project + seed the synthetic store.

Run (from repo root):
  ANAMNESIS_IMPORT_NATIVE=0 uv run --project server python \
    bench/cross-machine-tokens/setup_synthetic.py \
    --store /tmp/anamnesis-demo --project-dir /tmp/quotes-api

Then point the agent at --project-dir and inject from --store. Synthetic only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import lib

# A small but realistic Express + zod + repo project. The existing GET route uses
# the repo and a zod schema, but the error-envelope shape and the "no direct db
# client in handlers" rule are conventions a cold agent has to infer or guess.
FILES: dict[str, str] = {
    "package.json": (
        '{\n  "name": "quotes-api",\n  "private": true,\n'
        '  "type": "module",\n  "dependencies": { "express": "^5", "zod": "^4" }\n}\n'
    ),
    "src/db/repo.ts": (
        "// All database access lives here. Handlers call these, never the client.\n"
        "export type Quote = { id: string; text: string; author: string };\n\n"
        "const QUOTES: Quote[] = [];\n\n"
        "export async function listQuotes(): Promise<Quote[]> {\n"
        "  return QUOTES;\n}\n\n"
        "export async function createQuote(input: Omit<Quote, 'id'>): Promise<Quote> {\n"
        "  const q = { id: String(QUOTES.length + 1), ...input };\n"
        "  QUOTES.push(q);\n  return q;\n}\n"
    ),
    "src/routes/quotes.ts": (
        "import { Router } from 'express';\n"
        "import { listQuotes } from '../db/repo.js';\n\n"
        "export const quotes = Router();\n\n"
        "// GET /quotes - list all quotes.\n"
        "quotes.get('/quotes', async (_req, res) => {\n"
        "  res.json(await listQuotes());\n});\n"
    ),
    "src/app.ts": (
        "import express from 'express';\n"
        "import { quotes } from './routes/quotes.js';\n\n"
        "export const app = express();\n"
        "app.use(express.json());\n"
        "app.use(quotes);\n"
    ),
    "README.md": "# quotes-api\n\nA tiny quotes service. See src/.\n",
}


def write_project(root: Path) -> list[Path]:
    """Write the synthetic project tree + the .anamnesis/project marker."""
    written: list[Path] = []
    for rel, content in FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)
    marker = root / ".anamnesis" / "project"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("quotes-api\n", encoding="utf-8")
    written.append(marker)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Set up the synthetic quotes-api demo")
    ap.add_argument("--store", required=True, help="synthetic ANAMNESIS_HOME dir")
    ap.add_argument("--project-dir", required=True, help="synthetic project dir")
    args = ap.parse_args(argv)

    project = write_project(Path(args.project_dir))
    count = lib.seed_store(Path(args.store))
    print(f"setup: wrote {len(project)} project files, seeded {count} notes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
